from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0003_shopcategory_business_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shop',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='shop',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, db_index=True),
        ),
    ]
