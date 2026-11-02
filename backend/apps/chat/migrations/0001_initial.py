from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FriendRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'കാത്തിരിക്കുന്നു (Pending)'), ('accepted', 'സ്വീകരിച്ചു (Accepted)'), ('rejected', 'നിരസിച്ചു (Rejected)'), ('cancelled', 'റദ്ദാക്കി (Cancelled)')], db_index=True, default='pending', max_length=20, verbose_name='സ്റ്റാറ്റസ് (Status)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('receiver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_friend_requests', to=settings.AUTH_USER_MODEL, verbose_name='സ്വീകരിച്ചയാൾ (Receiver)')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_friend_requests', to=settings.AUTH_USER_MODEL, verbose_name='അയച്ചയാൾ (Sender)')),
            ],
            options={
                'verbose_name': 'ഫ്രണ്ട് റിക്വസ്റ്റ് (Friend Request)',
                'verbose_name_plural': 'ഫ്രണ്ട് റിക്വസ്റ്റുകൾ (Friend Requests)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='friendrequest',
            constraint=models.CheckConstraint(check=models.Q(('sender', models.F('receiver')), _negated=True), name='chat_prevent_self_friend_request'),
        ),
        migrations.CreateModel(
            name='Friendship',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='friendships_as_user1', to=settings.AUTH_USER_MODEL, verbose_name='യൂസർ 1')),
                ('user2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='friendships_as_user2', to=settings.AUTH_USER_MODEL, verbose_name='യൂസർ 2')),
            ],
            options={
                'verbose_name': 'സൗഹൃദം (Friendship)',
                'verbose_name_plural': 'സൗഹൃദങ്ങൾ (Friendships)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='friendship',
            constraint=models.UniqueConstraint(fields=('user1', 'user2'), name='unique_canonical_friendship'),
        ),
        migrations.AddConstraint(
            model_name='friendship',
            constraint=models.CheckConstraint(check=models.Q(('user1_id__lt', models.F('user2_id'))), name='chat_canonical_friendship_order'),
        ),
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('user1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations_user1', to=settings.AUTH_USER_MODEL)),
                ('user2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations_user2', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'സംഭാഷണം (Conversation)',
                'verbose_name_plural': 'സംഭാഷണങ്ങൾ (Conversations)',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='conversation',
            constraint=models.UniqueConstraint(fields=('user1', 'user2'), name='unique_canonical_conversation'),
        ),
        migrations.AddConstraint(
            model_name='conversation',
            constraint=models.CheckConstraint(check=models.Q(('user1_id__lt', models.F('user2_id'))), name='chat_canonical_conversation_users'),
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(max_length=2000, verbose_name='സന്ദേശം (Message)')),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='chat.conversation')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'സന്ദേശം (Message)',
                'verbose_name_plural': 'സന്ദേശങ്ങൾ (Messages)',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['conversation', 'created_at'], name='chat_messag_convers_3154fc_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['conversation', 'is_read'], name='chat_messag_convers_7d694b_idx'),
        ),
        migrations.CreateModel(
            name='SocialNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('friend_request', 'ഫ്രണ്ട് റിക്വസ്റ്റ് (Friend Request)'), ('friend_accept', 'സൗഹൃദം സ്വീകരിച്ചു (Friend Accepted)'), ('new_message', 'പുതിയ സന്ദേശം (New Message)')], db_index=True, max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('body', models.CharField(max_length=400)),
                ('link_url', models.CharField(blank=True, max_length=255)),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'അറിയിപ്പ് (Notification)',
                'verbose_name_plural': 'അറിയിപ്പുകൾ (Notifications)',
                'ordering': ['-created_at'],
            },
        ),
    ]
