from django.urls import path
from . import views

app_name = 'waitlist'

urlpatterns = [
    path('join/', views.join_waitlist, name='join'),
    path('stats/', views.waitlist_stats, name='stats'),
]