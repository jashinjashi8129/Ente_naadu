import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        ('shops', '0002_product_medical_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='checkout_group_id',
            field=models.CharField(blank=True, db_index=True, max_length=50, verbose_name='ചെക്ക്ഔട്ട് ഗ്രൂപ്പ് ഐഡി (Checkout Group ID)'),
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cart', to=settings.AUTH_USER_MODEL, verbose_name='ഉപഭോക്താവ് (Customer)')),
            ],
            options={
                'verbose_name': 'ഷോപ്പിംഗ് കാർട്ട് (Shopping Cart)',
                'verbose_name_plural': 'ഷോപ്പിംഗ് കാർട്ടുകൾ (Shopping Carts)',
            },
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='എണ്ണം')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.cart', verbose_name='കാർട്ട്')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to='shops.product', verbose_name='ഉൽപ്പന്നം')),
            ],
            options={
                'verbose_name': 'കാർട്ട് ഐറ്റം (Cart Item)',
                'verbose_name_plural': 'കാർട്ട് ഐറ്റങ്ങൾ (Cart Items)',
                'ordering': ['created_at'],
                'unique_together': {('cart', 'product')},
            },
        ),
    ]
