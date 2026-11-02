from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, db_index=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, db_index=True)),
                ('is_sharing_enabled', models.BooleanField(db_index=True, default=False, verbose_name='സുഹൃത്തുക്കളുമായി ലൊക്കേഷൻ പങ്കിടുക (Share with Friends)')),
                ('is_paused', models.BooleanField(default=False, verbose_name='താല്കാലികമായി നിർത്തുക (Pause Sharing)')),
                ('share_precision', models.CharField(choices=[('exact', 'കൃത്യമായ സ്ഥലം (Exact)'), ('approximate', 'ഏകദേശ സ്ഥലം (Approximate ~500m)')], default='exact', max_length=20, verbose_name='ലൊക്കേഷൻ കൃത്യത (Location Precision)')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='location', to=settings.AUTH_USER_MODEL, verbose_name='ഉപയോക്താവ് (User)')),
            ],
            options={
                'verbose_name': 'ഉപയോക്തൃ ലൊക്കേഷൻ (User Location)',
                'verbose_name_plural': 'ഉപയോക്തൃ ലൊക്കേഷനുകൾ (User Locations)',
            },
        ),
    ]
