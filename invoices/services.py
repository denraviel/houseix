from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from sales.models import Sale
from stays.models import GuestStay

from .models import Invoice, InvoiceAuditLog, InvoicePayment


def format_currency(value):
    amount = value or Decimal('0.00')
    return f"N{amount:,.2f}"


class InvoiceCalculationService:
    def __init__(self, invoice):
        self.invoice = invoice

    @property
    def stay(self):
        return self.invoice.stay

    @property
    def is_sales_invoice(self):
        return self.invoice.is_sales_invoice

    @property
    def is_guest_stay_invoice(self):
        return self.invoice.is_guest_stay_invoice

    def linked_sales(self):
        if self.is_sales_invoice:
            return Sale.objects.filter(
                invoice_link__invoice=self.invoice
            ).select_related('product', 'recorded_by', 'customer').order_by('created_at')
        return Sale.objects.filter(stay=self.stay).select_related('product', 'recorded_by').order_by('created_at')

    def charge_end_date(self):
        if self.is_sales_invoice:
            return None
        if self.stay.check_out_date:
            return self.stay.check_out_date
        if self.stay.is_closed:
            return self.stay.check_in_date
        return timezone.localdate()

    def is_provisional(self):
        if self.is_sales_invoice:
            return False
        return not self.stay.is_closed and not self.stay.check_out_date

    def billable_days(self):
        if self.is_sales_invoice:
            return 0
        end_date = self.charge_end_date()
        if not end_date or end_date <= self.stay.check_in_date:
            return 0
        return (end_date - self.stay.check_in_date).days

    def room_charge_total(self):
        if self.is_sales_invoice:
            return Decimal('0.00')
        return Decimal(self.billable_days()) * self.stay.daily_rate

    def sales_queryset(self):
        return self.linked_sales()

    def product_charge_total(self):
        return self.sales_queryset().aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    def payments_queryset(self):
        return self.invoice.payments.active().select_related('received_by').order_by('-received_at', '-created_at')

    def room_payments_total(self):
        if self.is_sales_invoice:
            return Decimal('0.00')
        return self.payments_queryset().filter(payment_type=InvoicePayment.TYPE_ROOM).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    def product_payments_total(self):
        return self.payments_queryset().filter(payment_type=InvoicePayment.TYPE_PRODUCT).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    def total_payments(self):
        return self.room_payments_total() + self.product_payments_total()

    def grand_total(self):
        return self.room_charge_total() + self.product_charge_total()

    def room_balance(self):
        return max(self.room_charge_total() - self.room_payments_total(), Decimal('0.00'))

    def product_balance(self):
        return max(self.product_charge_total() - self.product_payments_total(), Decimal('0.00'))

    def balance(self):
        return max(self.grand_total() - self.total_payments(), Decimal('0.00'))

    def customer_or_none(self):
        if self.is_sales_invoice:
            sales = list(self.sales_queryset())
            if sales:
                return sales[0].customer
            return self.invoice.customer
        return self.stay.customer

    def room_or_none(self):
        if self.is_sales_invoice:
            return None
        return self.stay.room

    def sale_payment_method(self):
        if self.is_sales_invoice:
            sales = list(self.sales_queryset())
            if sales:
                return sales[0].get_payment_method_display()
            return None
        return None

    def sale_recorded_by(self):
        if self.is_sales_invoice:
            sales = list(self.sales_queryset())
            if sales:
                return sales[0].recorded_by
            return None
        return None

    def sale_created_at(self):
        if self.is_sales_invoice:
            sales = list(self.sales_queryset())
            if sales:
                return sales[0].created_at
            return None
        return None

    def build_context(self):
        sales = list(self.sales_queryset())
        payments = list(self.payments_queryset())
        room_charge_total = self.room_charge_total()
        product_charge_total = self.product_charge_total()
        room_payments_total = self.room_payments_total()
        product_payments_total = self.product_payments_total()
        grand_total = room_charge_total + product_charge_total
        total_payments = room_payments_total + product_payments_total
        balance = max(grand_total - total_payments, Decimal('0.00'))

        context = {
            'invoice': self.invoice,
            'is_sales_invoice': self.is_sales_invoice,
            'is_guest_stay_invoice': self.is_guest_stay_invoice,
            'customer': self.customer_or_none(),
            'room': self.room_or_none(),
            'product_sales': sales,
            'payments': payments,
            'room_charge_total': room_charge_total,
            'product_charge_total': product_charge_total,
            'room_payments_total': room_payments_total,
            'product_payments_total': product_payments_total,
            'grand_total': grand_total,
            'total_payments': total_payments,
            'room_balance': max(room_charge_total - room_payments_total, Decimal('0.00')),
            'product_balance': max(product_charge_total - product_payments_total, Decimal('0.00')),
            'balance': balance,
            'balance_paid_in_full': balance == Decimal('0.00') and grand_total > Decimal('0.00'),
        }

        if self.is_sales_invoice:
            context.update({
                'sale_payment_method': self.sale_payment_method(),
                'sale_recorded_by': self.sale_recorded_by(),
                'sale_created_at': self.sale_created_at(),
                'charge_end_date': None,
                'is_provisional': False,
                'billable_days': 0,
                'stay': None,
                'room_charge_rows': [],
            })
        else:
            context.update({
                'stay': self.stay,
                'charge_end_date': self.charge_end_date(),
                'is_provisional': self.is_provisional(),
                'billable_days': self.billable_days(),
                'room_charge_rows': [
                    {
                        'description': f"Room {self.stay.room.room_number} ({self.stay.room.get_room_type_display()})",
                        'date_range': f"{self.stay.check_in_date} to {self.charge_end_date()}",
                        'daily_rate': self.stay.daily_rate,
                        'days': self.billable_days(),
                        'total': room_charge_total,
                    }
                ],
            })

        return context


class InvoiceStatusService:
    @staticmethod
    def calculate(invoice):
        calculations = InvoiceCalculationService(invoice)
        grand_total = calculations.grand_total()
        total_payments = calculations.total_payments()
        if grand_total <= Decimal('0.00'):
            return Invoice.STATUS_DRAFT
        if total_payments <= Decimal('0.00'):
            return Invoice.STATUS_UNPAID
        if calculations.balance() <= Decimal('0.00'):
            return Invoice.STATUS_PAID
        return Invoice.STATUS_PARTIALLY_PAID

    @classmethod
    def refresh(cls, invoice, *, user=None, notes=''):
        new_status = cls.calculate(invoice)
        if invoice.status != new_status:
            previous = invoice.get_status_display()
            invoice.status = new_status
            invoice.save(update_fields=['status', 'updated_at'])
            InvoiceAuditLog.log(
                invoice=invoice,
                action_type=InvoiceAuditLog.ACTION_STATUS_CHANGED,
                user=user,
                notes=notes or f"Status changed from {previous} to {invoice.get_status_display()}.",
            )
        return invoice


class InvoiceGeneratorService:
    @staticmethod
    @transaction.atomic
    def generate(*, stay, user, invoice_date=None, notes='', assigned_to=None):
        if stay is None:
            raise ValidationError('A guest stay is required to generate an invoice.')
        if stay.status == GuestStay.STATUS_CANCELLED:
            raise ValidationError('Cancelled stays cannot have invoices.')
        if hasattr(stay, 'invoice'):
            raise ValidationError('This guest stay already has an invoice.')

        invoice = Invoice.objects.create(
            stay=stay,
            invoice_date=invoice_date or timezone.localdate(),
            notes=notes or '',
            assigned_to=assigned_to,
            created_by=user,
            updated_by=user,
        )
        InvoiceAuditLog.log(
            invoice=invoice,
            action_type=InvoiceAuditLog.ACTION_CREATED,
            user=user,
            notes=f"Invoice generated for stay #{stay.pk}.",
        )
        InvoiceStatusService.refresh(invoice, user=user, notes='Initial invoice status set.')
        return invoice

    @staticmethod
    @transaction.atomic
    def generate_for_sale(*, sale, user, invoice_date=None, notes='', assigned_to=None):
        from .models import InvoiceSale

        if sale is None:
            raise ValidationError('A sale is required to generate a sales invoice.')

        if hasattr(sale, 'invoice_link') and sale.invoice_link_id:
            return sale.invoice_link.invoice

        invoice = Invoice.objects.create(
            invoice_type=Invoice.TYPE_SALE,
            stay=None,
            customer=sale.customer,
            invoice_date=invoice_date or timezone.localdate(),
            notes=notes or '',
            assigned_to=assigned_to,
            created_by=user,
            updated_by=user,
        )
        InvoiceSale.objects.create(invoice=invoice, sale=sale)
        InvoiceAuditLog.log(
            invoice=invoice,
            action_type=InvoiceAuditLog.ACTION_CREATED,
            user=user,
            notes=f"Standalone sales invoice generated for sale #{sale.pk}.",
        )
        InvoiceStatusService.refresh(invoice, user=user, notes='Initial sales invoice status set.')
        return invoice

    @staticmethod
    @transaction.atomic
    def update_invoice(*, invoice, user, invoice_date, notes, assigned_to):
        invoice.invoice_date = invoice_date
        invoice.notes = notes or ''
        invoice.assigned_to = assigned_to
        invoice.updated_by = user
        invoice.save()
        InvoiceAuditLog.log(
            invoice=invoice,
            action_type=InvoiceAuditLog.ACTION_UPDATED,
            user=user,
            notes='Invoice details updated.',
        )
        InvoiceStatusService.refresh(invoice, user=user, notes='Invoice refreshed after update.')
        return invoice


class InvoicePaymentService:
    @staticmethod
    @transaction.atomic
    def record_payment(*, invoice, cleaned_data, user):
        payment = InvoicePayment(
            invoice=invoice,
            payment_type=cleaned_data['payment_type'],
            amount=cleaned_data['amount'],
            payment_method=cleaned_data['payment_method'],
            reference=cleaned_data.get('reference', '') or '',
            notes=cleaned_data.get('notes', '') or '',
            received_by=user,
            received_by_full_name=(getattr(user, 'full_name', '') or ''),
            received_by_username=(getattr(user, 'email', '') or ''),
            received_by_role=(getattr(user, 'role', '') or ''),
        )
        payment.save()
        InvoiceAuditLog.log(
            invoice=invoice,
            payment=payment,
            action_type=InvoiceAuditLog.ACTION_PAYMENT_RECORDED,
            user=user,
            notes=f"Recorded {payment.get_payment_type_display().lower()} payment of {format_currency(payment.amount)}.",
        )
        InvoiceStatusService.refresh(invoice, user=user, notes='Invoice refreshed after payment.')
        return payment


class InvoicePDFService:
    @staticmethod
    def render(invoice):
        context = InvoiceCalculationService(invoice).build_context()
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()

        if context['is_sales_invoice']:
            story = [
                Paragraph("HouseIX Ops", styles['Title']),
                Paragraph("Sales Invoice", styles['Heading2']),
                Spacer(1, 8),
            ]

            customer_name = context['customer'].full_name if context['customer'] else 'Walk-in Customer'
            customer_id = context['customer'].customer_id if context['customer'] and context['customer'].customer_id else '-'
            sale_date = context['sale_created_at'].strftime('%Y-%m-%d %H:%M') if context['sale_created_at'] else '-'
            sale_payment_method = context['sale_payment_method'] or '-'
            recorded_by = context['sale_recorded_by'].full_name if context['sale_recorded_by'] else '-'

            metadata_rows = [
                ['Invoice Number', invoice.invoice_number],
                ['Invoice Date', str(invoice.invoice_date)],
                ['Status', invoice.get_status_display()],
                ['Invoice Type', 'Standalone Sales'],
                ['Customer', customer_name],
                ['Customer ID', customer_id],
                ['Sale Date', sale_date],
                ['Sale Payment Method', sale_payment_method],
                ['Recorded By', recorded_by],
            ]
        else:
            story = [
                Paragraph("HouseIX Ops", styles['Title']),
                Paragraph("Hotel Invoice", styles['Heading2']),
                Spacer(1, 8),
            ]

            metadata_rows = [
                ['Invoice Number', invoice.invoice_number],
                ['Invoice Date', str(invoice.invoice_date)],
                ['Status', invoice.get_status_display()],
                ['Guest', context['customer'].full_name],
                ['Customer ID', context['customer'].customer_id or '-'],
                ['Room', context['room'].room_number],
                ['Stay Dates', f"{context['stay'].check_in_date} to {context['charge_end_date']}"],
            ]

        metadata_table = Table(metadata_rows, colWidths=[110 * mm, 70 * mm])
        metadata_table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([metadata_table, Spacer(1, 10)])

        if context['is_guest_stay_invoice']:
            room_rows = [['Description', 'Days', 'Daily Rate', 'Total']]
            for row in context['room_charge_rows']:
                room_rows.append([
                    row['description'],
                    str(row['days']),
                    format_currency(row['daily_rate']),
                    format_currency(row['total']),
                ])
            room_table = Table(room_rows, colWidths=[85 * mm, 20 * mm, 35 * mm, 35 * mm])
            room_table.setStyle(_table_style())
            story.extend([Paragraph("Room Charges", styles['Heading3']), room_table, Spacer(1, 10)])

        product_rows = [['Product', 'Qty', 'Unit Price', 'Total']]
        if context['product_sales']:
            for sale in context['product_sales']:
                product_rows.append([
                    sale.product.name,
                    str(sale.quantity),
                    format_currency(sale.unit_price),
                    format_currency(sale.total_amount),
                ])
        else:
            no_sales_msg = 'No product sales linked to this stay.' if context['is_guest_stay_invoice'] else 'No items on this sales invoice.'
            product_rows.append([no_sales_msg, '-', '-', format_currency(Decimal('0.00'))])
        product_table = Table(product_rows, colWidths=[85 * mm, 20 * mm, 35 * mm, 35 * mm])
        product_table.setStyle(_table_style())
        product_title = "Product Charges" if context['is_guest_stay_invoice'] else "Invoice Items"
        story.extend([Paragraph(product_title, styles['Heading3']), product_table, Spacer(1, 10)])

        payment_rows = [['Date', 'Type', 'Method', 'Reference', 'Amount']]
        if context['payments']:
            for payment in context['payments']:
                payment_rows.append([
                    timezone.localtime(payment.received_at).strftime('%Y-%m-%d %H:%M'),
                    payment.get_payment_type_display(),
                    payment.get_payment_method_display(),
                    payment.reference or '-',
                    format_currency(payment.amount),
                ])
        else:
            payment_rows.append(['-', 'No payments recorded', '-', '-', format_currency(Decimal('0.00'))])
        payment_table = Table(payment_rows, colWidths=[35 * mm, 25 * mm, 35 * mm, 45 * mm, 30 * mm])
        payment_table.setStyle(_table_style())
        story.extend([Paragraph("Payments", styles['Heading3']), payment_table, Spacer(1, 10)])

        if context['is_sales_invoice']:
            totals_rows = [
                ['Product Total', format_currency(context['product_charge_total'])],
                ['Grand Total', format_currency(context['grand_total'])],
                ['Payments Received', format_currency(context['total_payments'])],
                ['Outstanding Balance', format_currency(context['balance'])],
            ]
        else:
            totals_rows = [
                ['Room Total', format_currency(context['room_charge_total'])],
                ['Product Total', format_currency(context['product_charge_total'])],
                ['Grand Total', format_currency(context['grand_total'])],
                ['Payments Received', format_currency(context['total_payments'])],
                ['Outstanding Balance', format_currency(context['balance'])],
            ]
        totals_table = Table(totals_rows, colWidths=[110 * mm, 70 * mm])
        totals_table.setStyle(_table_style())
        story.extend([Paragraph("Totals", styles['Heading3']), totals_table, Spacer(1, 8)])
        story.append(Paragraph("Generated by HouseIX Ops invoice service.", styles['Italic']))

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{invoice.invoice_number}.pdf"'
        return response


def _table_style():
    return TableStyle(
        [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]
    )
