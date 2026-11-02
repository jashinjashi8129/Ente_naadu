from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.directory.models import Area
from apps.shops.models import ShopCategory, Shop
from apps.chat.models import FriendRequest, Friendship, Conversation, Message, SocialNotification

User = get_user_model()

class ChatAndFriendsSystemTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="Test Area", pincode="670001")
        self.user1 = User.objects.create_user(
            phone_number="9876543210",
            full_name="User One",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )
        self.user2 = User.objects.create_user(
            phone_number="9876543211",
            full_name="User Two",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )
        self.user3 = User.objects.create_user(
            phone_number="9876543212",
            full_name="User Three",
            role="citizen",
            area=self.area,
            ward_number=2,
            password="password123"
        )

        self.client = APIClient()

    def test_user_discovery_and_friend_request_flow(self):
        # 1. Login user1
        self.client.force_authenticate(user=self.user1)

        # 2. Send friend request from user1 to user2
        url = reverse('friend-request-send', args=[self.user2.id])
        # Using web client or API client. Let's test API view or web view.
        # Let's test API endpoints for robust verification
        api_send_url = f'/api/v1/chat/requests/send/'
        response = self.client.post(api_send_url, {'to_user_id': self.user2.id}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(FriendRequest.objects.filter(sender=self.user1, receiver=self.user2, status=FriendRequest.Status.PENDING).exists())

        req = FriendRequest.objects.get(sender=self.user1, receiver=self.user2)

        # 3. User2 accepts the request
        self.client.force_authenticate(user=self.user2)
        api_accept_url = f'/api/v1/chat/requests/{req.id}/accept/'
        response = self.client.post(api_accept_url, format='json')
        self.assertEqual(response.status_code, 200)

        # Verify friendship exists and canonical order is enforced
        self.assertTrue(Friendship.are_friends(self.user1, self.user2))
        self.assertTrue(Conversation.objects.filter(user1=min(self.user1, self.user2, key=lambda u: u.id), user2=max(self.user1, self.user2, key=lambda u: u.id)).exists())

    def test_chat_message_sending_and_security(self):
        # Establish friendship between user1 and user2
        Friendship.objects.create(
            user1=min(self.user1, self.user2, key=lambda u: u.id),
            user2=max(self.user1, self.user2, key=lambda u: u.id)
        )
        conv = Conversation.get_or_create_for(self.user1, self.user2)

        # User1 sends message
        self.client.force_authenticate(user=self.user1)
        send_msg_url = f'/api/v1/chat/conversations/{conv.id}/messages/send/'
        response = self.client.post(send_msg_url, {'text': 'Hello User Two!'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Message.objects.count(), 1)

        # Non-friend (user3) attempts to send message to user1 or view conversation -> should be forbidden or unauthorized
        self.client.force_authenticate(user=self.user3)
        response = self.client.post(send_msg_url, {'text': 'Hacking chat!'}, format='json')
        self.assertIn(response.status_code, [403, 404])

    def test_unfriending_immediately_blocks_subsequent_chat_messages(self):
        """Unfriending a user preserves history but immediately blocks further messages."""
        Friendship.make_friends(self.user1, self.user2)
        conv = Conversation.get_or_create_between(self.user1, self.user2)

        # Send an initial message while friends
        self.client.force_authenticate(user=self.user1)
        res_ok = self.client.post(f'/api/v1/chat/conversations/{conv.id}/messages/send/', {'text': 'Hi friend!'}, format='json')
        self.assertEqual(res_ok.status_code, status.HTTP_201_CREATED)

        # User 1 unfriends User 2
        unfriend_url = f'/api/v1/chat/friends/{self.user2.id}/unfriend/'
        res_unfriend = self.client.post(unfriend_url)
        self.assertEqual(res_unfriend.status_code, status.HTTP_200_OK)
        self.assertFalse(Friendship.are_friends(self.user1, self.user2))

        # User 1 tries to send another message -> HTTP 403 Forbidden
        res_blocked = self.client.post(f'/api/v1/chat/conversations/{conv.id}/messages/send/', {'text': 'Are you there?'}, format='json')
        self.assertEqual(res_blocked.status_code, status.HTTP_403_FORBIDDEN)

        # Message history is safely preserved
        self.assertEqual(conv.messages.count(), 1)

    def test_unread_summary_and_notifications(self):
        """Unread message counts and social notifications are updated accurately."""
        Friendship.make_friends(self.user1, self.user2)
        conv = Conversation.get_or_create_between(self.user1, self.user2)

        # User 1 sends message to User 2
        self.client.force_authenticate(user=self.user1)
        self.client.post(f'/api/v1/chat/conversations/{conv.id}/messages/send/', {'text': 'Unread test message'}, format='json')

        # Check User 2's unread summary
        self.client.force_authenticate(user=self.user2)
        res_summary = self.client.get('/api/v1/chat/unread-count/')
        self.assertEqual(res_summary.status_code, status.HTTP_200_OK)
        self.assertEqual(res_summary.data['unread_messages'], 1)
        self.assertGreaterEqual(res_summary.data['total_alerts'], 1)

        # User 2 views conversation -> mark as read
        res_view = self.client.get(f'/api/v1/chat/conversations/{conv.id}/messages/')
        self.assertEqual(res_view.status_code, status.HTTP_200_OK)

        # Unread message count now 0
        res_summary2 = self.client.get('/api/v1/chat/unread-count/')
        self.assertEqual(res_summary2.data['unread_messages'], 0)



class NearbyFriendsSecurityTests(TestCase):
    def setUp(self):
        from apps.accounts.models import UserLocation
        from datetime import timedelta
        from django.utils import timezone

        self.area = Area.objects.create(name="Aluva Area", pincode="683101")
        self.client = APIClient()

        # User A: Observer
        self.user_a = User.objects.create_user(
            phone_number="9847000001",
            full_name="User A (Observer)",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )
        # User B: Friend near User A (~3 km)
        self.user_b = User.objects.create_user(
            phone_number="9847000002",
            full_name="User B (Near Friend)",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )
        # User C: Friend far away (~80 km)
        self.user_c = User.objects.create_user(
            phone_number="9847000003",
            full_name="User C (Far Friend)",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )
        # User D: Stranger near User A (~2 km) - NOT friends
        self.user_d = User.objects.create_user(
            phone_number="9847000004",
            full_name="User D (Stranger)",
            role="citizen",
            area=self.area,
            ward_number=1,
            password="password123"
        )

        # Establish mutual friendships: A <-> B and A <-> C
        Friendship.create_mutual(self.user_a, self.user_b)
        Friendship.create_mutual(self.user_a, self.user_c)

        # Base coord for User A: Kochi (10.0159, 76.3419)
        self.base_lat = 10.0159
        self.base_lng = 76.3419

        # Setup User B location: ~3 km away, sharing enabled, exact
        self.loc_b, _ = UserLocation.objects.get_or_create(user=self.user_b)
        self.loc_b.latitude = 10.0350
        self.loc_b.longitude = 76.3500
        self.loc_b.is_sharing_enabled = True
        self.loc_b.is_paused = False
        self.loc_b.share_precision = 'exact'
        self.loc_b.save()

        # Setup User C location: ~80 km away, sharing enabled
        self.loc_c, _ = UserLocation.objects.get_or_create(user=self.user_c)
        self.loc_c.latitude = 10.8505
        self.loc_c.longitude = 76.2711
        self.loc_c.is_sharing_enabled = True
        self.loc_c.is_paused = False
        self.loc_c.share_precision = 'exact'
        self.loc_c.save()

        # Setup User D (Stranger) location: ~2 km away, sharing enabled
        self.loc_d, _ = UserLocation.objects.get_or_create(user=self.user_d)
        self.loc_d.latitude = 10.0200
        self.loc_d.longitude = 76.3450
        self.loc_d.is_sharing_enabled = True
        self.loc_d.is_paused = False
        self.loc_d.save()

    def test_nearby_friends_within_radius(self):
        """Returns accepted friends within radius and excludes distant friends."""
        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=10'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        friend_ids = [f['id'] for f in res.data['friends']]
        self.assertIn(self.user_b.id, friend_ids)
        self.assertNotIn(self.user_c.id, friend_ids)  # Excluded because > 10 km

    def test_nearby_friends_excludes_strangers_completely(self):
        """A stranger who is 2 km away is NEVER returned to User A."""
        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=25'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        friend_ids = [f['id'] for f in res.data['friends']]
        self.assertNotIn(self.user_d.id, friend_ids)  # Stranger must NOT leak

    def test_nearby_friends_respects_sharing_disabled(self):
        """If friend turns off is_sharing_enabled, they disappear from nearby map."""
        self.loc_b.is_sharing_enabled = False
        self.loc_b.save()

        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=10'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        friend_ids = [f['id'] for f in res.data['friends']]
        self.assertNotIn(self.user_b.id, friend_ids)

    def test_nearby_friends_respects_paused_sharing(self):
        """If friend pauses sharing, they are hidden from nearby friends."""
        self.loc_b.is_paused = True
        self.loc_b.save()

        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=10'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        friend_ids = [f['id'] for f in res.data['friends']]
        self.assertNotIn(self.user_b.id, friend_ids)

    def test_nearby_friends_excludes_stale_locations(self):
        """Locations older than 24 hours automatically expire."""
        from datetime import timedelta
        from django.utils import timezone

        # Set User B's coordinate to 25 hours ago in DB
        from apps.accounts.models import UserLocation
        UserLocation.objects.filter(pk=self.loc_b.pk).update(updated_at=timezone.now() - timedelta(hours=25))


        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=10'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        friend_ids = [f['id'] for f in res.data['friends']]
        self.assertNotIn(self.user_b.id, friend_ids)

    def test_nearby_friends_approximate_precision_rounds_coordinates(self):
        """Approximate precision rounds coordinates to 2 decimal places."""
        self.loc_b.share_precision = 'approximate'
        self.loc_b.latitude = 10.034567
        self.loc_b.longitude = 76.356789
        self.loc_b.save()

        self.client.force_authenticate(user=self.user_a)
        url = f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=10'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        user_b_data = next((f for f in res.data['friends'] if f['id'] == self.user_b.id), None)
        self.assertIsNotNone(user_b_data)
        self.assertEqual(user_b_data['latitude'], 10.03)
        self.assertEqual(user_b_data['longitude'], 76.36)
        self.assertTrue(user_b_data['is_approximate'])

    def test_shop_location_is_distinct_from_owner_personal_gps(self):
        """
        Verify that a business owner's personal GPS (UserLocation) remains private,
        and is completely separate from their Shop's physical public coordinates.
        """
        owner = self.user_b
        # Owner personal location is at (10.0350, 76.3500)
        cat = ShopCategory.objects.create(name="Bakery", interaction_mode=ShopCategory.InteractionMode.ORDER)
        shop = Shop.objects.create(
            owner=owner,
            name="Owner B Bakehouse",
            category=cat,
            ward_number=1,
            address="Commercial Complex, Junction",
            latitude=10.0800,  # Shop is at 10.0800
            longitude=76.3900,
            is_verified=True,
            is_open=True
        )

        # 1. Nearby Shops API returns the SHOP's coordinates (10.0800, 76.3900)
        res_shop = self.client.get(f'/api/v1/shops/nearby/?lat=10.0800&lng=76.3900&radius=5')
        self.assertEqual(res_shop.status_code, 200)
        shop_entry = next((s for s in res_shop.data['shops'] if s['id'] == shop.id), None)
        self.assertIsNotNone(shop_entry)
        self.assertEqual(shop_entry['latitude'], 10.0800)
        self.assertEqual(shop_entry['longitude'], 76.3900)

        # 2. When Owner disables personal GPS sharing, the Shop still appears on Nearby Shops map!
        self.loc_b.is_sharing_enabled = False
        self.loc_b.save()

        res_shop_after = self.client.get(f'/api/v1/shops/nearby/?lat=10.0800&lng=76.3900&radius=5')
        self.assertEqual(res_shop_after.status_code, 200)
        self.assertTrue(any(s['id'] == shop.id for s in res_shop_after.data['shops']))

        # 3. But on Nearby Friends map, the Owner's personal GPS is completely absent!
        self.client.force_authenticate(user=self.user_a)
        res_friends = self.client.get(f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}&radius=20')
        friend_ids = [f['id'] for f in res_friends.data['friends']]
        self.assertNotIn(owner.id, friend_ids)

    def test_never_expose_personal_gps_publicly(self):
        """Unauthenticated or non-friend requests cannot access personal GPS locations."""
        # Unauthenticated request to nearby friends returns 401 Unauthorized
        anon_client = APIClient()
        res_anon = anon_client.get(f'/api/v1/chat/friends/nearby/?lat={self.base_lat}&lng={self.base_lng}')
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # User Discovery API never includes personal GPS coordinates
        self.client.force_authenticate(user=self.user_a)
        res_users = self.client.get('/api/v1/chat/users/')
        self.assertEqual(res_users.status_code, 200)
        for u in res_users.data.get('results', res_users.data):
            self.assertNotIn('latitude', u)
            self.assertNotIn('longitude', u)
            self.assertNotIn('location', u)


