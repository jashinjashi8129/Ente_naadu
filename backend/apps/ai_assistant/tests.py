from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import Area, User
from apps.shops.models import ShopCategory, Shop
from apps.events.models import EventNotice
from apps.directory.models import DirectoryEntry

class AIAssistantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="AI Test Area", district="Wayanad")
        self.category = ShopCategory.objects.create(name="AI Grocery")
        self.owner = User.objects.create_user(
            phone_number="9900000001",
            password="password123",
            full_name="AI Shop Owner",
            role=User.Role.SHOP_OWNER
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Wayanad Organic Spices",
            category=self.category,
            area=self.area,
            ward_number=7,
            address="Vythiri",
            contact_phone="9988776655",
            is_verified=True,
            is_open=True
        )
        self.entry = DirectoryEntry.objects.create(
            name="Primary Health Center",
            category=DirectoryEntry.Category.DOCTOR_CLINIC,
            phone_number="04936200000",
            is_emergency_service=True,
            is_verified=True
        )

    def test_empty_message_returns_400(self):
        url = reverse('nattu-sahayi-chat')
        response = self.client.post(url, {'message': '   '}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_local_fallback_emergency_query(self):
        url = reverse('nattu-sahayi-chat')
        response = self.client.post(url, {'message': 'ആംബുലൻസ് നമ്പർ തരുമോ?'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reply', response.data)
        self.assertIn('Primary Health Center', response.data['reply'])

    def test_local_fallback_shops_query(self):
        url = reverse('nattu-sahayi-chat')
        response = self.client.post(url, {'message': 'തുറന്ന കടകൾ ഏതൊക്കെയാണ്?'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Wayanad Organic Spices', response.data['reply'])
