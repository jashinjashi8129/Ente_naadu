# Generated manually for Ente Naadu Phase 4 Local Community Services

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0001_initial'),
        ('directory', '0002_directoryentry_submitted_by_alter_directoryentry_is_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifiedad',
            name='condition',
            field=models.CharField(
                blank=True,
                choices=[
                    ('new', 'പുതിയത് (Brand New)'),
                    ('like_new', 'വളരെ നല്ല അവസ്ഥ (Like New)'),
                    ('used', 'ഉപയോഗിച്ചത് (Gently Used)'),
                    ('for_parts', 'പാർട്സുകൾക്കായി (For Parts)')
                ],
                default='used',
                max_length=30,
                verbose_name='അവസ്ഥ (Condition)'
            ),
        ),
        migrations.AddField(
            model_name='classifiedad',
            name='location',
            field=models.CharField(blank=True, max_length=200, verbose_name='സ്ഥലം (Location / Landmark)'),
        ),
        migrations.CreateModel(
            name='JobListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=200, verbose_name='സ്ഥാപനം / തൊഴിൽ ദാതാവ് (Company Name)')),
                ('employer_bio', models.TextField(blank=True, verbose_name='തൊഴിൽ ദാതാവിന്റെ വിവരങ്ങൾ (Employer Bio)')),
                ('title', models.CharField(max_length=200, verbose_name='തൊഴിൽ തസ്തിക (Job Title)')),
                ('category', models.CharField(
                    choices=[
                        ('driver', 'ഡ്രൈവർ (Driver)'),
                        ('sales', 'സെയിൽസ് / കടകൾ (Sales / Retail)'),
                        ('office', 'ഓഫീസ് / ക്ലർക്ക് (Office / Clerk)'),
                        ('cook', 'പാചകം / കാറ്ററിംഗ് (Cook / Catering)'),
                        ('construction', 'നിർമ്മാണം / പണിക്കാർ (Construction & Labor)'),
                        ('cleaner', 'ഹൗസ് കീപ്പിംഗ് (Housekeeping / Cleaning)'),
                        ('security', 'സെക്യൂരിറ്റി (Security Guard)'),
                        ('technician', 'ടെക്നീഷ്യൻ / ഇലക്ട്രിക്കൽ (Technician)'),
                        ('other', 'മറ്റുള്ളവ (Other Jobs)')
                    ],
                    default='other',
                    max_length=30,
                    verbose_name='വിഭാഗം (Category)'
                )),
                ('job_type', models.CharField(
                    choices=[
                        ('full_time', 'മുഴുസമയ ജോലി (Full Time)'),
                        ('part_time', 'ഭാഗിക സമയ ജോലി (Part Time)'),
                        ('daily_wage', 'ദിവസ വേതനം (Daily Wage)'),
                        ('contract', 'കരാർ ജോലി (Contract)')
                    ],
                    default='full_time',
                    max_length=20,
                    verbose_name='തൊഴിൽ രീതി (Job Type)'
                )),
                ('description', models.TextField(verbose_name='വിശദവിവരങ്ങൾ (Description)')),
                ('requirements', models.TextField(blank=True, verbose_name='യോഗ്യതകൾ / നിബന്ധനകൾ (Requirements)')),
                ('salary_range', models.CharField(blank=True, max_length=100, verbose_name='ശമ്പളം / വേതനം (Salary / Wage)')),
                ('location', models.CharField(max_length=200, verbose_name='ജോലി സ്ഥലം (Job Location / Landmark)')),
                ('ward_number', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='വാർഡ് നമ്പർ (Ward)')),
                ('contact_phone', models.CharField(max_length=17, verbose_name='ബന്ധപ്പെടേണ്ട ഫോൺ നമ്പർ')),
                ('is_active', models.BooleanField(default=True, verbose_name='സജീവം (Active / Hiring Open)')),
                ('is_approved', models.BooleanField(default=False, verbose_name='അഡ്മിൻ അനുമതി നൽകിയത് (Admin Approved)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('area', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='job_listings',
                    to='accounts.area',
                    verbose_name='പ്രദേശം (Area)'
                )),
                ('employer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='job_listings',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='തൊഴിൽ നൽകുന്നയാൾ (Employer)'
                )),
            ],
            options={
                'verbose_name': 'തൊഴിൽ ഒഴിവ് (Job Listing)',
                'verbose_name_plural': 'തൊഴിൽ ഒഴിവുകൾ (Job Listings)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='JobApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=150, verbose_name='അപേക്ഷകന്റെ പേര്')),
                ('contact_phone', models.CharField(max_length=17, verbose_name='ബന്ധപ്പെടേണ്ട ഫോൺ നമ്പർ')),
                ('experience_summary', models.TextField(verbose_name='മുൻപരിചയവും യോഗ്യതയും (Experience Summary)')),
                ('status', models.CharField(
                    choices=[
                        ('submitted', 'സമർപ്പിച്ചു (Submitted)'),
                        ('reviewed', 'പരിശോധിച്ചു (Under Review)'),
                        ('shortlisted', 'ഷോർട്ട് ലിസ്റ്റ് ചെയ്തു (Shortlisted)'),
                        ('accepted', 'തിരഞ്ഞെടുത്തു (Hired / Accepted)'),
                        ('rejected', 'നിരസിച്ചു (Rejected)')
                    ],
                    default='submitted',
                    max_length=20,
                    verbose_name='സ്റ്റാറ്റസ് (Application Status)'
                )),
                ('employer_notes', models.TextField(blank=True, verbose_name='തൊഴിൽ ദാതാവിന്റെ മറുപടി / കുറിപ്പ് (Employer Feedback)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('applicant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='job_applications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='അപേക്ഷകൻ (Applicant)'
                )),
                ('job', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='applications',
                    to='directory.joblisting',
                    verbose_name='തൊഴിൽ (Job Listing)'
                )),
            ],
            options={
                'verbose_name': 'തൊഴിൽ അപേക്ഷ (Job Application)',
                'verbose_name_plural': 'തൊഴിൽ അപേക്ഷകൾ (Job Applications)',
                'ordering': ['-created_at'],
                'unique_together': {('job', 'applicant')},
            },
        ),
    ]
