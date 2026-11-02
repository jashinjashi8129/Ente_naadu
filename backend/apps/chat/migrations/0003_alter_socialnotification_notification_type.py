from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_rename_apps_chat_m_convers_a4c520_idx_chat_messag_convers_3154fc_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='socialnotification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('friend_request', 'ഫ്രണ്ട് റിക്വസ്റ്റ് (Friend Request)'),
                    ('friend_accept', 'സൗഹൃദം സ്വീകരിച്ചു (Friend Accepted)'),
                    ('new_message', 'പുതിയ സന്ദേശം (New Message)'),
                    ('order_update', 'ഓർഡർ അറിയിപ്പ് (Order Notification)'),
                    ('booking_update', 'ബുക്കിംഗ് അറിയിപ്പ് (Booking Notification)'),
                    ('service_update', 'സർവീസ് അറിയിപ്പ് (Service Notification)'),
                    ('directory_update', 'ഡയറക്ടറി അറിയിപ്പ് (Directory Notification)'),
                    ('complaint_update', 'പരാതി അറിയിപ്പ് (Complaint Notification)'),
                    ('system_alert', 'സിസ്റ്റം അറിയിപ്പ് (System Alert)'),
                ],
                db_index=True,
                max_length=30
            ),
        ),
    ]
