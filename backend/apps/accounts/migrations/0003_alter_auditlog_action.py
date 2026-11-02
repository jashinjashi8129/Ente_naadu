from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_userlocation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('block_user', 'യൂസറെ ബ്ലോക്ക് ചെയ്തു'),
                    ('unblock_user', 'യൂസറുടെ ബ്ലോക്ക് നീക്കി'),
                    ('approve_shop', 'കട അപ്രൂവ് ചെയ്തു'),
                    ('reject_shop', 'കട നിരസിച്ചു'),
                    ('remove_content', 'ഉള്ളടക്കം നീക്കം ചെയ്തു'),
                    ('reset_password', 'പാസ്‌വേഡ് റീസെറ്റ് ചെയ്തു'),
                    ('product_create', 'ഉൽപ്പന്നം ചേർത്തു'),
                    ('product_update', 'ഉൽപ്പന്നം പുതുക്കി'),
                    ('product_delete', 'ഉൽപ്പന്നം നീക്കം ചെയ്തു'),
                    ('product_stock_toggle', 'സ്റ്റോക്ക് മാറ്റി'),
                    ('order_status_update', 'ഓർഡർ സ്റ്റാറ്റസ് മാറ്റി'),
                    ('order_cancel', 'ഓർഡർ റദ്ദാക്കി'),
                    ('booking_status_update', 'ബുക്കിംഗ് സ്റ്റാറ്റസ് മാറ്റി'),
                    ('booking_cancel', 'ബുക്കിംഗ് റദ്ദാക്കി'),
                    ('directory_approve', 'ഡയറക്ടറി അപ്രൂവ് ചെയ്തു'),
                    ('directory_reject', 'ഡയറക്ടറി നിരസിച്ചു'),
                    ('complaint_resolve', 'പരാതി പരിഹരിച്ചു'),
                ],
                max_length=50,
                verbose_name='നടപടി'
            ),
        ),
    ]
