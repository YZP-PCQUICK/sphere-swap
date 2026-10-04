"""
users app URL配置
"""
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # 页面
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_page, name='profile'),
    path('profile/edit/', views.profile_edit_page, name='profile_edit'),
    
    # API
    path('api/check-email/', views.check_email, name='check_email'),
    path('api/send-code/', views.send_verify_code, name='send_code'),
    path('api/register/', views.register_api, name='register_api'),
    path('api/login/', views.login_api, name='login_api'),
    path('api/reset-password/', views.reset_password_api, name='reset_password'),
    path('api/update-profile/', views.update_profile, name='update_profile'),
    path('api/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('api/upload-payment-qrcode/', views.upload_payment_qrcode, name='upload_payment_qrcode'),
    path('api/change-password/', views.change_password, name='change_password'),
]
