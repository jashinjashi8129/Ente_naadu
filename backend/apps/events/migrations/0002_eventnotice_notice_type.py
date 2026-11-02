# Generated manually for Ente Naadu Phase 4 Local News / Announcements filter

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventnotice',
            name='notice_type',
            field=models.CharField(
                choices=[
                    ('announcement', 'പൊതു അറിയിപ്പ് / വാർത്ത (Announcement / News)'),
                    ('event', 'പരിപാടി / സമ്മേളനം (Event / Gathering)')
                ],
                default='announcement',
                max_length=20,
                verbose_name='അറിയിപ്പ് തരം (Type)'
            ),
        ),
    ]
