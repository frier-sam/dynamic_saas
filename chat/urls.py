from django.urls import path
from . import views

urlpatterns = [
    # Web views
    path('', views.chat_view, name='chat'),
    path('<int:conversation_id>/', views.chat_view, name='conversation_detail'),
    
    # API endpoints
    path('api/conversations/', views.ConversationListAPI.as_view(), name='conversation_list_api'),
    path('api/conversations/<int:conversation_id>/', views.ConversationDetailAPI.as_view(), name='conversation_detail_api'),
    path('api/conversations/<int:conversation_id>/messages/', views.send_message, name='send_message_api'),
]