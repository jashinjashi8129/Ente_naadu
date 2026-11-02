from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Area
from .models import EventNotice, EventRSVP

class EventsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="South Village Area", district="Kottayam")

        self.user_a = User.objects.create_user(
            phone_number="9700000001",
            password="password123",
            full_name="Citizen A",
            role=User.Role.CITIZEN
        )

        self.user_b = User.objects.create_user(
            phone_number="9700000002",
            password="password123",
            full_name="Citizen B",
            role=User.Role.CITIZEN
        )

        self.admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

        self.notice = EventNotice.objects.create(
            author=self.user_a,
            area=self.area,
            title="Ward Meeting Notice",
            description="Discussing road repairs",
            category=EventNotice.Category.GENERAL,
            is_emergency=False
        )

    def test_citizen_cannot_post_emergency_alert(self):
        """Regular citizen cannot publish an urgent emergency alert directly."""
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/events/notices/"
        data = {
            "title": "Fake Flood Alert",
            "description": "Evacuate now",
            "category": "emergency",
            "is_emergency": True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notice = EventNotice.objects.get(id=response.data['id'])
        # is_emergency is forcibly stripped to False for non-admins
        self.assertFalse(notice.is_emergency)

    def test_admin_can_post_emergency_alert(self):
        """Admin can publish emergency alerts."""
        self.client.force_authenticate(user=self.admin)
        url = "/api/v1/events/notices/"
        data = {
            "title": "Official Power Cut Alert",
            "description": "Substation maintenance today",
            "category": "emergency",
            "is_emergency": True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notice = EventNotice.objects.get(id=response.data['id'])
        self.assertTrue(notice.is_emergency)

    def test_user_b_cannot_delete_user_a_notice(self):
        """User B cannot delete User A's notice (IDOR prevention)."""
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/events/notices/{self.notice.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(EventNotice.objects.filter(id=self.notice.id).exists())

    def test_user_b_cannot_edit_user_a_notice(self):
        """User B cannot edit User A's notice."""
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/events/notices/{self.notice.id}/"
        response = self.client.patch(url, {"title": "Defaced Notice"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.title, "Ward Meeting Notice")

    # ==================== Phase 4: Local News & Events Tests ====================

    def test_local_news_and_events_filtering(self):
        """Citizens can filter by notice_type (announcements vs events), category, and area."""
        other_area = Area.objects.create(name="North Ward", district="Kottayam")

        announcement = EventNotice.objects.create(
            author=self.user_a,
            area=self.area,
            notice_type=EventNotice.NoticeType.ANNOUNCEMENT,
            title="Gramasabha Meeting Next Friday",
            description="All ward members requested to attend",
            category=EventNotice.Category.PANCHAYAT
        )

        event = EventNotice.objects.create(
            author=self.user_a,
            area=other_area,
            notice_type=EventNotice.NoticeType.EVENT,
            title="Village Football Tournament",
            description="Under-19 7s football cup",
            category=EventNotice.Category.SPORTS,
            venue="Panchayat Stadium"
        )

        # Filter by notice_type = announcement
        res_ann = self.client.get("/api/v1/events/notices/?notice_type=announcement")
        self.assertEqual(res_ann.status_code, status.HTTP_200_OK)
        ann_ids = [item['id'] for item in res_ann.data.get('results', res_ann.data)]
        self.assertIn(announcement.id, ann_ids)
        self.assertNotIn(event.id, ann_ids)

        # Filter by category = sports
        res_sports = self.client.get("/api/v1/events/notices/?category=sports")
        self.assertEqual(res_sports.status_code, status.HTTP_200_OK)
        sports_ids = [item['id'] for item in res_sports.data.get('results', res_sports.data)]
        self.assertIn(event.id, sports_ids)
        self.assertNotIn(announcement.id, sports_ids)

        # Filter by area
        res_area = self.client.get(f"/api/v1/events/notices/?area={self.area.id}")
        self.assertEqual(res_area.status_code, status.HTTP_200_OK)
        area_ids = [item['id'] for item in res_area.data.get('results', res_area.data)]
        self.assertIn(announcement.id, area_ids)
        self.assertNotIn(event.id, area_ids)

    def test_event_rsvp_attendance(self):
        """Citizens can RSVP (going, not going, maybe) to local community events."""
        event = EventNotice.objects.create(
            author=self.user_a,
            area=self.area,
            notice_type=EventNotice.NoticeType.EVENT,
            title="Free Medical & Blood Donation Camp",
            description="Govt High School Auditorium",
            category=EventNotice.Category.MEDICAL
        )

        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/events/notices/{event.id}/rsvp/"
        res = self.client.post(url, {"status": EventRSVP.Status.GOING}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], EventRSVP.Status.GOING)

        # Retrieve notice and check going_count
        res_detail = self.client.get(f"/api/v1/events/notices/{event.id}/")
        self.assertEqual(res_detail.data['going_count'], 1)
        self.assertEqual(res_detail.data['my_rsvp'], EventRSVP.Status.GOING)

