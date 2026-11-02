from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShopCategoryViewSet,
    ShopViewSet,
    ProductViewSet,
    ReviewViewSet,
    RatingCriterionViewSet,
    PublicShopRegisterView
)

router = DefaultRouter()
router.register(r'categories', ShopCategoryViewSet, basename='category')
router.register(r'shops', ShopViewSet, basename='api-shop')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'rating-criteria', RatingCriterionViewSet, basename='rating-criteria')

urlpatterns = [
    path('register/', PublicShopRegisterView.as_view(), name='shop-register'),
    path('nearby/', ShopViewSet.as_view({'get': 'nearby'}), name='api-nearby-shops'),
    path('<int:pk>/location/', ShopViewSet.as_view({'post': 'location'}), name='api-shop-location'),
    path('', include(router.urls)),
]
