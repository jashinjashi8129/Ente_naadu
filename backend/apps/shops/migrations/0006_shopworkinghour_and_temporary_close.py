from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0005_alter_shopcategory_interaction_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='shop',
            name='is_temporarily_closed',
            field=models.BooleanField(default=False, verbose_name='താൽക്കാലികമായി അടച്ചിട്ടിരിക്കുന്നു (Temporarily Closed)'),
        ),
        migrations.AddField(
            model_name='shop',
            name='temporary_close_reason',
            field=models.CharField(blank=True, max_length=255, verbose_name='അടച്ചിടാനുള്ള കാരണം (Reason)'),
        ),
        migrations.CreateModel(
            name='ShopWorkingHour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.PositiveSmallIntegerField(choices=[(0, 'തിങ്കൾ (Monday)'), (1, 'ചൊവ്വ (Tuesday)'), (2, 'ബുധൻ (Wednesday)'), (3, 'വ്യാഴം (Thursday)'), (4, 'വെള്ളി (Friday)'), (5, 'ശനി (Saturday)'), (6, 'ഞായർ (Sunday)')], verbose_name='ദിവസം (Day)')),
                ('opening_time', models.TimeField(blank=True, null=True, verbose_name='തുറക്കുന്ന സമയം (Opening Time)')),
                ('closing_time', models.TimeField(blank=True, null=True, verbose_name='അടയ്ക്കുന്ന സമയം (Closing Time)')),
                ('is_closed', models.BooleanField(default=False, verbose_name='അവധിദിനം / അടച്ചിരിക്കുന്നു (Closed / Holiday)')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='working_hours', to='shops.shop', verbose_name='സ്ഥാപനം (Shop)')),
            ],
            options={
                'verbose_name': 'പ്രവർത്തന സമയം (Working Hour)',
                'verbose_name_plural': 'പ്രവർത്തന സമയങ്ങൾ (Working Hours)',
                'ordering': ['day'],
                'unique_together': {('shop', 'day')},
            },
        ),
    ]
