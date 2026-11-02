from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Area
from apps.chat.models import Conversation, SocialNotification
from .models import DirectoryEntry, BloodDonor, ClassifiedAd, JobListing, JobApplication

class DirectorySecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="East Ward", district="Palakkad")

        self.user_a = User.objects.create_user(
            phone_number="9500000001",
            password="password123",
            full_name="User A",
            role=User.Role.CITIZEN
        )

        self.user_b = User.objects.create_user(
            phone_number="9500000002",
            password="password123",
            full_name="User B",
            role=User.Role.CITIZEN
        )

        self.admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

        self.donor = BloodDonor.objects.create(
            user=self.user_a,
            name="Donor User A",
            blood_group=BloodDonor.BloodGroup.O_POS,
            phone_number="9500000001",
            ward_number=4
        )

        self.ad = ClassifiedAd.objects.create(
            author=self.user_a,
            ad_type=ClassifiedAd.AdType.RENT,
            title="2 BHK House for Rent",
            description="Near temple",
            contact_phone="9500000001",
            is_approved=True
        )

        self.verified_service = DirectoryEntry.objects.create(
            name="Official Ambulance Service",
            category=DirectoryEntry.Category.AMBULANCE,
            phone_number="9447108108",
            address_or_stand="Govt Hospital",
            is_emergency_service=True,
            is_verified=True
        )

    def test_citizen_can_submit_directory_entry_unverified(self):
        """Citizens can submit service directory entry which defaults to is_verified=False pending approval."""
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/directory/services/"
        payload = {
            "name": "Manoj Electrician",
            "category": DirectoryEntry.Category.ELECTRICIAN,
            "phone_number": "9847112233",
            "address_or_stand": "Town Square",
            "ward_number": 3,
            "is_emergency_service": True  # Regular citizen cannot make emergency service
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry_id = response.data['id']
        entry = DirectoryEntry.objects.get(id=entry_id)
        self.assertEqual(entry.submitted_by, self.user_a)
        self.assertFalse(entry.is_verified)
        self.assertFalse(entry.is_emergency_service)  # Non-admin cannot set emergency service

    def test_unauthenticated_user_only_sees_verified_entries(self):
        """Unauthenticated public users only see verified directory entries."""
        unverified = DirectoryEntry.objects.create(
            name="Unverified Plumber",
            category=DirectoryEntry.Category.PLUMBER,
            phone_number="9847998877",
            address_or_stand="Near Bridge",
            submitted_by=self.user_a,
            is_verified=False
        )
        url = "/api/v1/directory/services/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertIn(self.verified_service.id, ids)
        self.assertNotIn(unverified.id, ids)

    def test_citizen_can_see_their_own_pending_entry_but_not_others(self):
        """Citizen can see their own pending entries, but User B cannot see User A's pending entry."""
        unverified = DirectoryEntry.objects.create(
            name="User A Pending Auto",
            category=DirectoryEntry.Category.TAXI_AUTO,
            phone_number="9847123456",
            address_or_stand="Auto Stand",
            submitted_by=self.user_a,
            is_verified=False
        )
        # User A sees it
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/directory/services/"
        res_a = self.client.get(url)
        ids_a = [item['id'] for item in res_a.data.get('results', res_a.data)]
        self.assertIn(unverified.id, ids_a)

        # User B does NOT see it
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get(url)
        ids_b = [item['id'] for item in res_b.data.get('results', res_b.data)]
        self.assertNotIn(unverified.id, ids_b)

    def test_admin_can_approve_directory_entry(self):
        """Admin can approve pending directory entries."""
        entry = DirectoryEntry.objects.create(
            name="Ramesh Plumber",
            category=DirectoryEntry.Category.PLUMBER,
            phone_number="9847000111",
            address_or_stand="Ward 2",
            submitted_by=self.user_a,
            is_verified=False
        )
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/directory/services/{entry.id}/approve/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertTrue(entry.is_verified)

    def test_admin_can_reject_directory_entry(self):
        """Admin can reject and delete pending directory entries."""
        entry = DirectoryEntry.objects.create(
            name="Spam Entry",
            category=DirectoryEntry.Category.OTHER,
            phone_number="0000000000",
            address_or_stand="Nowhere",
            submitted_by=self.user_a,
            is_verified=False
        )
        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/directory/services/{entry.id}/reject/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(DirectoryEntry.objects.filter(id=entry.id).exists())

    def test_user_b_cannot_edit_or_delete_user_a_directory_entry(self):
        """User B cannot tamper with User A's submitted directory entry."""
        entry = DirectoryEntry.objects.create(
            name="User A Plumber",
            category=DirectoryEntry.Category.PLUMBER,
            phone_number="9847000222",
            address_or_stand="Ward 1",
            submitted_by=self.user_a,
            is_verified=True
        )
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/directory/services/{entry.id}/"
        # Try PATCH
        patch_res = self.client.patch(url, {"name": "Hacked Name"}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Try DELETE
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(DirectoryEntry.objects.filter(id=entry.id).exists())

    def test_editing_approved_entry_resets_verification(self):
        """When an author edits an approved directory entry, is_verified resets to False for re-verification."""
        entry = DirectoryEntry.objects.create(
            name="User A Electrician",
            category=DirectoryEntry.Category.ELECTRICIAN,
            phone_number="9847000333",
            address_or_stand="Ward 1",
            submitted_by=self.user_a,
            is_verified=True
        )
        self.client.force_authenticate(user=self.user_a)
        url = f"/api/v1/directory/services/{entry.id}/"
        response = self.client.patch(url, {"name": "User A Electrician & Solar"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.name, "User A Electrician & Solar")
        self.assertFalse(entry.is_verified)

    def test_user_b_cannot_delete_user_a_blood_donor(self):
        """User B cannot delete User A's blood donor profile."""
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/directory/blood-donors/{self.donor.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(BloodDonor.objects.filter(id=self.donor.id).exists())

    def test_user_b_cannot_delete_user_a_classified_ad(self):
        """User B cannot delete User A's classified ad."""
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/directory/classifieds/{self.ad.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ClassifiedAd.objects.filter(id=self.ad.id).exists())

    def test_editing_approved_ad_resets_is_approved_flag(self):
        """When an author edits an approved ad, is_approved resets to False for re-verification."""
        self.client.force_authenticate(user=self.user_a)
        url = f"/api/v1/directory/classifieds/{self.ad.id}/"
        response = self.client.patch(url, {"title": "Updated 2 BHK House"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ad.refresh_from_db()
        self.assertEqual(self.ad.title, "Updated 2 BHK House")
        self.assertFalse(self.ad.is_approved)

    def test_admin_can_approve_classified_ad(self):
        """Super Admin can approve classified ads."""
        self.ad.is_approved = False
        self.ad.save()

        self.client.force_authenticate(user=self.admin)
        url = f"/api/v1/directory/classifieds/{self.ad.id}/approve/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ad.refresh_from_db()
        self.assertTrue(self.ad.is_approved)

    # ==================== Phase 4: Buy & Sell Tests ====================

    def test_buy_and_sell_second_hand_listing_creation(self):
        """Citizens can list second-hand items with condition, price, and location."""
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/directory/classifieds/"
        payload = {
            "ad_type": ClassifiedAd.AdType.SALE,
            "title": "Used Royal Enfield Classic 350",
            "description": "2021 model, single owner, mint condition",
            "price_or_salary": "₹1,45,000",
            "condition": "like_new",
            "location": "Near Panchayat Office, East Ward",
            "contact_phone": "9500000001"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['condition'], 'like_new')
        self.assertEqual(res.data['location'], 'Near Panchayat Office, East Ward')
        # Citizen created ads require admin approval
        self.assertFalse(res.data['is_approved'])

    def test_buy_and_sell_filtering_by_condition_and_location(self):
        """Citizens can filter second hand listings by condition and location search."""
        ad_used = ClassifiedAd.objects.create(
            author=self.user_a,
            ad_type=ClassifiedAd.AdType.SALE,
            title="Used LG Refrigerator 260L",
            description="5 star inverter",
            condition="used",
            location="Alathur Junction",
            contact_phone="9500000001",
            is_approved=True
        )
        ad_new = ClassifiedAd.objects.create(
            author=self.user_a,
            ad_type=ClassifiedAd.AdType.SALE,
            title="Brand New Helmet Vega",
            description="Unused sealed pack",
            condition="new",
            location="Kollengode",
            contact_phone="9500000001",
            is_approved=True
        )

        # Filter by condition
        res = self.client.get("/api/v1/directory/classifieds/?condition=used")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        ids = [item['id'] for item in results]
        self.assertIn(ad_used.id, ids)
        self.assertNotIn(ad_new.id, ids)

        # Filter by location
        res_loc = self.client.get("/api/v1/directory/classifieds/?location=Alathur")
        self.assertEqual(res_loc.status_code, status.HTTP_200_OK)
        loc_results = res_loc.data.get('results', res_loc.data)
        loc_ids = [item['id'] for item in loc_results]
        self.assertIn(ad_used.id, loc_ids)
        self.assertNotIn(ad_new.id, loc_ids)

    def test_contact_seller_opens_private_chat_bridge(self):
        """Contacting seller returns 1-1 chat conversation URL without exposing personal GPS."""
        self.client.force_authenticate(user=self.user_b)
        url = f"/api/v1/directory/classifieds/{self.ad.id}/contact-seller/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['seller_id'], self.user_a.id)
        self.assertEqual(res.data['seller_name'], self.user_a.full_name)
        self.assertEqual(res.data['chat_url'], f"/chat/{self.user_a.id}/")
        self.assertIn('conversation_id', res.data)

        # Verify Conversation was created in DB
        self.assertTrue(Conversation.objects.filter(id=res.data['conversation_id']).exists())

    def test_contact_seller_cannot_chat_with_oneself(self):
        """User cannot initiate chat with themselves for their own classified listing."""
        self.client.force_authenticate(user=self.user_a)
        url = f"/api/v1/directory/classifieds/{self.ad.id}/contact-seller/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================== Phase 4: Local Jobs Tests ====================

    def test_employer_can_post_job_listing(self):
        """Local business owner / employer can post vacancies."""
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/directory/jobs/"
        payload = {
            "company_name": "Kerala Spices & Provisions",
            "employer_bio": "Family-run local grocery shop since 2010",
            "title": "Delivery Driver / Helper",
            "category": JobListing.JobCategory.DRIVER,
            "job_type": JobListing.JobType.FULL_TIME,
            "description": "Deliver grocery orders to local houses within 5km radius",
            "requirements": "Two-wheeler driving license required",
            "salary_range": "₹12,000 - ₹15,000 / month",
            "location": "Town Market, East Ward",
            "ward_number": 4,
            "contact_phone": "9500000001"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['company_name'], "Kerala Spices & Provisions")
        self.assertEqual(res.data['employer_name'], self.user_a.full_name)
        self.assertEqual(res.data['employer_chat_url'], f"/chat/{self.user_a.id}/")
        self.assertFalse(res.data['is_approved'])  # Citizen creation requires admin approval

    def test_candidate_can_apply_to_approved_job(self):
        """Candidate can apply for approved active job and employer receives in-app alert."""
        job = JobListing.objects.create(
            employer=self.user_a,
            company_name="Grand Bakery",
            title="Pastry Cook / Baker",
            category=JobListing.JobCategory.COOK,
            job_type=JobListing.JobType.FULL_TIME,
            description="Experience in making traditional tea snacks and cakes",
            location="East Ward Junction",
            contact_phone="9500000001",
            is_approved=True,
            is_active=True
        )

        self.client.force_authenticate(user=self.user_b)
        url = "/api/v1/directory/job-applications/"
        payload = {
            "job": job.id,
            "full_name": "User B Candidate",
            "contact_phone": "9500000002",
            "experience_summary": "3 years experience in local bakery. Skilled in snacks."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], JobApplication.Status.SUBMITTED)

        # Check that employer received a notification
        notif = SocialNotification.objects.filter(recipient=self.user_a).latest('created_at')
        self.assertIn("പുതിയ തൊഴിൽ അപേക്ഷ", notif.title)

    def test_candidate_cannot_apply_twice_to_same_job(self):
        """Prevent duplicate applications to the same job."""
        job = JobListing.objects.create(
            employer=self.user_a,
            company_name="Auto Garage",
            title="Assistant Mechanic",
            category=JobListing.JobCategory.TECHNICIAN,
            location="Main Road",
            contact_phone="9500000001",
            is_approved=True,
            is_active=True
        )
        JobApplication.objects.create(
            job=job,
            applicant=self.user_b,
            full_name="User B",
            contact_phone="9500000002",
            experience_summary="Mechanic helper for 1 year"
        )

        self.client.force_authenticate(user=self.user_b)
        url = "/api/v1/directory/job-applications/"
        payload = {
            "job": job.id,
            "full_name": "User B Second Attempt",
            "contact_phone": "9500000002",
            "experience_summary": "Trying again"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employer_cannot_apply_to_own_job(self):
        """Employer cannot submit an application to their own job."""
        job = JobListing.objects.create(
            employer=self.user_a,
            company_name="Auto Garage",
            title="Driver",
            location="Main Road",
            contact_phone="9500000001",
            is_approved=True,
            is_active=True
        )
        self.client.force_authenticate(user=self.user_a)
        url = "/api/v1/directory/job-applications/"
        payload = {
            "job": job.id,
            "full_name": "User A",
            "contact_phone="9500000001",
            "experience_summary": "I am the owner"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_can_advance_candidate_status(self):
        """Employer can shortlist or accept applicant, sending status alert to candidate."""
        job = JobListing.objects.create(
            employer=self.user_a,
            company_name="Local Clinic",
            title="Clinic Assistant",
            location="East Ward",
            contact_phone="9500000001",
            is_approved=True,
            is_active=True
        )
        application = JobApplication.objects.create(
            job=job,
            applicant=self.user_b,
            full_name="User B",
            contact_phone="9500000002",
            experience_summary="1 year at reception"
        )

        self.client.force_authenticate(user=self.user_a)
        url = f"/api/v1/directory/job-applications/{application.id}/update-status/"
        payload = {
            "status": JobApplication.Status.SHORTLISTED,
            "employer_notes": "Please attend interview on Monday at 10 AM"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApplication.Status.SHORTLISTED)
        self.assertEqual(application.employer_notes, "Please attend interview on Monday at 10 AM")

        # Verify candidate received notification
        notif = SocialNotification.objects.filter(recipient=self.user_b).latest('created_at')
        self.assertIn("തൊഴിൽ അപേക്ഷ അപ്ഡേറ്റ്", notif.title)

    def test_unauthorized_user_cannot_update_candidate_status(self):
        """User B (non-employer) cannot modify candidate application status."""
        job = JobListing.objects.create(
            employer=self.user_a,
            company_name="Local Clinic",
            title="Clinic Assistant",
            location="East Ward",
            contact_phone="9500000001",
            is_approved=True,
            is_active=True
        )
        application = JobApplication.objects.create(
            job=job,
            applicant=self.user_b,
            full_name="User B",
            contact_phone="9500000002",
            experience_summary="1 year at reception"
        )

        user_c = User.objects.create_user(
            phone_number="9500000003",
            password="password123",
            full_name="User C",
            role=User.Role.CITIZEN
        )
        self.client.force_authenticate(user=user_c)
        url = f"/api/v1/directory/job-applications/{application.id}/update-status/"
        res = self.client.post(url, {"status": JobApplication.Status.ACCEPTED})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

