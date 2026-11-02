from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0002_product_medical_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopcategory',
            name='business_type',
            field=models.CharField(
                choices=[
                    ('general', 'ജനറൽ സ്റ്റോർ (General Shop)'),
                    ('beauty_parlour', 'ബ്യൂട്ടി പാർലർ / സലൂൺ (Beauty Parlour)'),
                    ('medical', 'മെഡിക്കൽ ഷോപ്പ് (Medical Shop)'),
                    ('repair', 'റിപ്പയർ / സർവീസ് (Repair Shop)'),
                    ('restaurant', 'ഹോട്ടൽ / റസ്റ്റോറന്റ് (Restaurant)'),
                    ('other_service', 'മറ്റു സേവനങ്ങൾ (Other Services)'),
                ],
                default='general',
                max_length=30,
                verbose_name='സ്ഥാപന തരം (Business Type)',
            ),
        ),
    ]
