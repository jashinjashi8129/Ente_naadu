from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DirectoryEntryViewSet,
    BloodDonorViewSet,
    ClassifiedAdViewSet,
    JobListingViewSet,
    JobApplicationViewSet
)

router = DefaultRouter()
router.register(r'services', DirectoryEntryViewSet, basename='service-directory')
router.register(r'blood-donors', BloodDonorViewSet, basename='blood-donor')
router.register(r'classifieds', ClassifiedAdViewSet, basename='classified-ad')
router.register(r'jobs', JobListingViewSet, basename='job-listing')
router.register(r'job-applications', JobApplicationViewSet, basename='job-application')

urlpatterns = [
    path('', include(router.urls)),
]
