from django.urls import path
from .views import NattuSahayiChatView

urlpatterns = [
    path('chat/', NattuSahayiChatView.as_view(), name='nattu-sahayi-chat'),
]
