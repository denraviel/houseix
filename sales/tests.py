from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import JobPosition, ModulePermission
from customers.models import Customer
from products.models import Product
from rooms.models import Room
from stays.models import GuestStay

from .forms import SaleForm
from .models import Sale


class SalesAccessTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner@example.com',
            password='Owner@12345',
            full_name='Owner User',
            phone_number='08000000111',
            username='owner.user',
            role='owner',
            is_first_login=False,
        )
        self.barman_position, _ = JobPosition.objects.get_or_create(
            code='barman',
            defaults={
                'name': 'Barman',
                'description': 'Bar service and beverage sales.',
                'department': JobPosition.DEPARTMENT_FOOD_BEVERAGE,
                'is_active': True,
            },
        )
        self.sales_module = ModulePermission.objects.get(code='sales')
        self.barman = self.UserModel.objects.create_user(
            email='barman@example.com',
            password='Barman@12345',
            full_name='Bar User',
            phone_number='08000000112',
            username='bar.user',
            role='staff',
            is_first_login=False,
            module_permissions=[self.sales_module],
        )
        self.barman.positions.add(self.barman_position)
        self.bar_product = Product.objects.create(
            name='Premium Whisky',
            category='Bar',
            selling_price=15000,
            cost_price=9000,
            quantity_in_stock=12,
            unit_type='bottle',
            is_available=True,
        )
        self.kitchen_product = Product.objects.create(
            name='Chef Special Rice',
            category='Kitchen',
            selling_price=5000,
            cost_price=2500,
            quantity_in_stock=10,
            unit_type='plate',
            is_available=True,
        )
        self.customer = Customer.objects.create(
            full_name='Checked Out Guest',
            phone_number='08000000999',
            email='guest@example.com',
        )
        self.room = Room.objects.create(
            room_number='B101',
            room_type=Room.TYPE_SINGLE,
            daily_rate=25000,
            status=Room.STATUS_AVAILABLE,
        )
        self.checked_in_stay = GuestStay.objects.create(
            customer=self.customer,
            room=self.room,
            daily_rate=25000,
            status=GuestStay.STATUS_CHECKED_IN,
        )
        self.checked_out_stay = GuestStay.objects.create(
            customer=self.customer,
            room=Room.objects.create(
                room_number='B102',
                room_type=Room.TYPE_SINGLE,
                daily_rate=25000,
                status=Room.STATUS_AVAILABLE,
            ),
            daily_rate=25000,
            status=GuestStay.STATUS_CHECKED_OUT,
        )

    def test_barman_sale_form_only_shows_bar_products(self):
        form = SaleForm(user=self.barman)

        product_names = list(form.fields['product'].queryset.values_list('name', flat=True))

        self.assertIn(self.bar_product.name, product_names)
        self.assertNotIn(self.kitchen_product.name, product_names)

    def test_barman_can_access_sales_list_and_only_sees_own_sales(self):
        Sale.objects.create(
            product=self.bar_product,
            quantity=1,
            payment_method='cash',
            recorded_by=self.barman,
        )
        owner_product = Product.objects.create(
            name='Owner Reserve',
            category='Bar',
            selling_price=18000,
            cost_price=11000,
            quantity_in_stock=8,
            unit_type='bottle',
            is_available=True,
        )
        Sale.objects.create(
            product=owner_product,
            quantity=1,
            payment_method='card',
            recorded_by=self.owner,
        )

        self.client.force_login(self.barman)
        response = self.client.get(reverse('sales_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bar_product.name)
        self.assertNotContains(response, owner_product.name)

    def test_barman_cannot_submit_non_bar_product_sale(self):
        self.client.force_login(self.barman)

        response = self.client.post(
            reverse('sale_create'),
            {
                'product': self.kitchen_product.pk,
                'quantity': 1,
                'payment_method': 'cash',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertEqual(Sale.objects.count(), 0)

    def test_sale_form_only_shows_active_guest_stays(self):
        form = SaleForm(user=self.owner)

        stay_ids = list(form.fields['stay'].queryset.values_list('pk', flat=True))

        self.assertIn(self.checked_in_stay.pk, stay_ids)
        self.assertNotIn(self.checked_out_stay.pk, stay_ids)

    def test_cannot_record_sale_for_checked_out_guest(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('sale_create'),
            {
                'stay': self.checked_out_stay.pk,
                'product': self.bar_product.pk,
                'quantity': 1,
                'payment_method': 'cash',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertEqual(Sale.objects.count(), 0)

    def test_sale_model_rejects_checked_out_guest_stay(self):
        sale = Sale(
            stay=self.checked_out_stay,
            product=self.bar_product,
            quantity=1,
            payment_method='cash',
            recorded_by=self.owner,
        )

        with self.assertRaises(ValidationError) as error:
            sale.save()

        self.assertIn('Sales cannot be recorded for a guest who has already checked out or whose stay is closed.', error.exception.message_dict['stay'])
