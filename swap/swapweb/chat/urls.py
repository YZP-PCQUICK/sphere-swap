from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # 页面
    path('', views.my_conversations, name='list'),
    path('<int:conv_id>/', views.chat_room, name='room'),
    # API
    path('api/start/', views.start_conversation, name='api_start'),
    path('api/unread/', views.api_unread, name='api_unread'),
    path('api/messages/', views.api_messages, name='api_messages'),
    path('api/send/', views.api_send_message, name='api_send'),
    path('api/confirm/', views.api_confirm, name='api_confirm'),
    path('api/complete/', views.api_complete, name='api_complete'),
    path('api/cancel/', views.api_cancel, name='api_cancel'),
]