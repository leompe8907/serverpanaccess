from django.urls import path
from wind import views

urlpatterns = [
    path('login/direct/', views.test_login_direct, name='test_login_direct'),
    path('login/client/', views.test_login_client, name='test_login_client'),
    path('login/complete/', views.test_login_complete, name='test_login_complete'),
]
