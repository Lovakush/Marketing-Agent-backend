from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Main chatbot endpoint
    path('', views.chatbot, name='chatbot'),
    
    # User information management
    path('update-info/', views.update_user_info, name='update_user_info'),
    
    # Session management
    path('session/<uuid:session_id>/', views.get_session_info, name='get_session_info'),
    path('session/reset/', views.reset_session, name='reset_session'),
    path('session/close/', views.close_session, name='close_session'),  # NEW: Close and cleanup
]