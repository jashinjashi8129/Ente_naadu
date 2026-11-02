# Generated manually for Ente Naadu Phase 4 Public Complaints GPS Geotagging

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('complaints', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='complaint',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name='ലൊക്കേഷൻ അക്ഷാംശം (Latitude)'
            ),
        ),
        migrations.AddField(
            model_name='complaint',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name='ലൊക്കേഷൻ രേഖാംശം (Longitude)'
            ),
        ),
    ]
