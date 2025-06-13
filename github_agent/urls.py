from django.urls import path
from .views import GitHubCommandAPIView

urlpatterns = [
    path('command/', GitHubCommandAPIView.as_view(), name='github_command_api'),
]
