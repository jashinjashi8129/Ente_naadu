from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='requires_prescription',
            field=models.BooleanField(default=False, verbose_name='ഡോക്ടറുടെ കുറിപ്പടി ആവശ്യമുള്ളത് (Requires Prescription)'),
        ),
        migrations.AddField(
            model_name='product',
            name='expiry_info',
            field=models.CharField(blank=True, max_length=100, verbose_name='കാലാവധി വിവരങ്ങൾ (Expiry Info)'),
        ),
    ]
