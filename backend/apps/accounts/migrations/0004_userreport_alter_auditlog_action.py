# Generated manually for Ente Naadu Phase 4 Trust & Moderation (UserReport & extended AuditLog actions)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_auditlog_action'),
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
                    ('report_resolve', 'റിപ്പോർട്ടിൽ നടപടി സ്വീകരിച്ചു'),
                    ('report_dismiss', 'റിപ്പോർട്ട് തള്ളി'),
                    ('classified_approve', 'ക്ലാസിഫൈഡ് അപ്രൂവ് ചെയ്തു'),
                    ('job_approve', 'തൊഴിൽ പരസ്യം അപ്രൂവ് ചെയ്തു'),
                ],
                max_length=50,
                verbose_name='നടപടി'
            ),
        ),
        migrations.CreateModel(
            name='UserReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.CharField(default='user', max_length=50, verbose_name='ഉള്ളടക്ക തരം (Target Type: user, shop, classified, job, message)')),
                ('content_id', models.IntegerField(blank=True, null=True, verbose_name='ഉള്ളടക്ക ഐഡി (Target Content ID)')),
                ('reason', models.CharField(
                    choices=[
                        ('spam', 'സ്പാം / പരസ്യ ശല്യം (Spam & Advertising)'),
                        ('abuse', 'അസഭ്യം / ഭീഷണി (Abuse & Harassment)'),
                        ('fraud', 'തട്ടിപ്പ് / വ്യാജം (Fraud & Scam)'),
                        ('misinformation', 'വ്യാജ വാർത്ത (Misinformation)'),
                        ('offensive', 'മോശമായ ഉള്ളടക്കം (Inappropriate Content)'),
                        ('other', 'മറ്റുള്ളവ (Other Violation)')
                    ],
                    default='spam',
                    max_length=30,
                    verbose_name='കാരണം (Reason)'
                )),
                ('description', models.TextField(blank=True, verbose_name='വിശദവിവരങ്ങൾ (Detailed Description)')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'പരിഗണനയിൽ (Pending Review)'),
                        ('investigating', 'അന്വേഷണത്തിൽ (Investigating)'),
                        ('resolved', 'നടപടി സ്വീകരിച്ചു (Resolved - Action Taken)'),
                        ('dismissed', 'തള്ളി (Dismissed - No Violation)')
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='സ്റ്റാറ്റസ് (Status)'
                )),
                ('admin_action_taken', models.CharField(blank=True, max_length=100, verbose_name='സ്വീകരിച്ച നടപടി (Admin Action)')),
                ('admin_notes', models.TextField(blank=True, verbose_name='അഡ്മിൻ കുറിപ്പുകൾ (Staff Notes)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reporter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='filed_reports',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='പരാതിപ്പെട്ടയാൾ (Reporter)'
                )),
                ('reported_user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='received_reports',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='ആരോപണവിധേയൻ (Reported User)'
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_reports',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='പരിശോധിച്ച അഡ്മിൻ'
                )),
            ],
            options={
                'verbose_name': 'ദുരുപയോഗ റിപ്പോർട്ട് (Abuse Report)',
                'verbose_name_plural': 'ദുരുപയോഗ റിപ്പോർട്ടുകൾ (Abuse Reports)',
                'ordering': ['-created_at'],
            },
        ),
    ]
