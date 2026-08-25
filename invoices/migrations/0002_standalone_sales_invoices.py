from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0003_customer_created_by_full_name_and_more"),
        ("invoices", "0001_initial"),
        ("sales", "0005_alter_sale_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="invoice_type",
            field=models.CharField(
                choices=[
                    ("guest_stay", "Guest Stay"),
                    ("sale", "Sales"),
                ],
                db_index=True,
                default="guest_stay",
                max_length=20,
            ),
        ),

        migrations.AddField(
            model_name="invoice",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoices",
                to="customers.customer",
            ),
        ),

        migrations.AlterField(
            model_name="invoice",
            name="stay",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoice",
                to="stays.gueststay",
            ),
        ),

        migrations.CreateModel(
            name="InvoiceSale",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sales",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "sale",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoice_link",
                        to="sales.sale",
                    ),
                ),
            ],
            options={
                "ordering": ["sale__created_at"],
            },
        ),

        migrations.AddConstraint(
            model_name="invoicesale",
            constraint=models.UniqueConstraint(
                fields=("invoice", "sale"),
                name="unique_invoice_sale",
            ),
        ),
    ]