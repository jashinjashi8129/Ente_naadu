from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Area
from .models import Complaint

class ComplaintsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="North Ward", district="Thrissur")

        self.citizen_a = User.objects.create_user(
            phone_number="9600000001",
            password="password123",
            full_name="Citizen A",
            role=User.Role.CITIZEN,
            ward_number=3
        )

        self.citizen_b = User.objects.create_user(
            phone_number="9600000002",
            password="password123",
            full_name="Citizen B",
            role=User.Role.CITIZEN,
            ward_number=3
        )

        self.admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

        self.complaint = Complaint.objects.create(
            citizen=self.citizen_a,
            area=self.area,
            title="Broken Street Light",
            description="Dark at junction",
            ward_number=3,
            status=Complaint.Status.SUBMITTED
        )

    def test_citizen_b_cannot_delete_citizen_a_complaint(self):
        """Citizen B cannot delete Citizen A's complaint."""
        self.client.force_authenticate(user=self.citizen_b)
        url = f"/api/v1/complaints/{self.complaint.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Complaint.objects.filter(id=self.complaint.id).exists())

    def test_citizen_b_cannot_retrieve_citizen_a_unresolved_complaint(self):
        """Citizen B cannot view Citizen A's private, unresolved complaint (404 Not Found for privacy)."""
        self.client.force_authenticate(user=self.citizen_b)
        url = f"/api/v1/complaints/{self.complaint.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_citizen_cannot_edit_complaint_in_progress(self):
        """Citizen cannot edit complaint once it has been processed to in_progress or resolved."""
        self.complaint.status = Complaint.Status.IN_PROGRESS
        self.complaint.save()

        self.client.force_authenticate(user=self.citizen_a)
        url = f"/api/v1/complaints/{self.complaint.id}/"
        response = self.client.patch(url, {"title": "Changed Complaint"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_citizen_cannot_update_complaint_status_directly(self):
        """Only administrators can change complaint status via update-status."""
        self.client.force_authenticate(user=self.citizen_a)
        url = f"/api/v1/complaints/{self.complaint.id}/update-status/"
        response = self.client.post(url, {"status": "resolved", "remarks": "I resolved it"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.SUBMITTED)

    def test_admin_can_update_complaint_status(self):
        """Admin can change complaint status and add official remarks."""
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/complaints/{self.complaint.id}/update-status/"
        response = self.client.post(url, {"status": "resolved", "remarks": "Repaired by KSEB"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.RESOLVED)
        self.assertEqual(self.complaint.admin_remarks, "Repaired by KSEB")

    # ==================== Phase 4: Public Complaints Geotagging & Notification Tests ====================

    def test_complaint_creation_with_gps_location_and_photo(self):
        """Citizens can submit complaints with precise GPS coordinates for civic staff to locate."""
        self.client.force_authenticate(user=self.citizen_a)
        url = "/api/v1/complaints/"
        payload = {
            "title": "Major Pothole on Market Road",
            "description": "Hazardous crater near Bus Stop risking two-wheelers",
            "category": Complaint.Category.ROADS,
            "ward_number": 3,
            "location_details": "Opposite Primary Health Centre",
            "latitude": "10.527641",
            "longitude": "76.214432",
            "is_anonymous": False
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        complaint = Complaint.objects.get(id=res.data['id'])
        self.assertEqual(float(complaint.latitude), 10.527641)
        self.assertEqual(float(complaint.longitude), 76.214432)
        self.assertEqual(complaint.status, Complaint.Status.SUBMITTED)

    def test_complaint_status_update_notifies_citizen(self):
        """When ward staff or admin updates status, citizen receives an in-app SocialNotification."""
        from apps.chat.models import SocialNotification

        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/complaints/{self.complaint.id}/update-status/"
        payload = {
            "status": Complaint.Status.IN_PROGRESS,
            "remarks": "Panchayat engineering wing inspected site, work scheduled for tomorrow morning."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check citizen received notification
        notif = SocialNotification.objects.filter(recipient=self.citizen_a).latest('created_at')
        self.assertIn("പരാതി പരിഹാര അപ്ഡേറ്റ്", notif.title)
        self.assertIn("നടപടി സ്വീകരിക്കുന്നു", notif.body)

    def test_anonymous_complaint_protects_citizen_identity(self):
        """Anonymous complaints do not reveal citizen's identity in the public list."""
        anon_complaint = Complaint.objects.create(
            citizen=self.citizen_a,
            area=self.area,
            title="Illegal Waste Dumping in Canal",
            description="Dumping commercial plastic waste at midnight",
            ward_number=3,
            is_anonymous=True,
            status=Complaint.Status.RESOLVED  # Publicly visible once resolved
        )

        # Any public visitor viewing the complaint sees anonymous label
        res = self.client.get(f"/api/v1/complaints/{anon_complaint.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['citizen_name'], "രഹസ്യം (Anonymous Citizen)")

