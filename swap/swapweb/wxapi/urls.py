"""
微信小程序接口路由（统一前缀 /wx/api/）
"""
from django.urls import path
from . import views

urlpatterns = [
    # 认证（方案A：邮箱+密码，与网站一致）
    path('auth/send-code/', views.auth_send_code, name='wx_auth_send_code'),
    path('auth/register/', views.auth_register, name='wx_auth_register'),
    path('auth/login/', views.auth_login, name='wx_auth_login'),
    path('auth/logout/', views.auth_logout, name='wx_auth_logout'),
    path('auth/reset-password/', views.auth_reset_password, name='wx_auth_reset_password'),
    path('auth/check-email/', views.auth_check_email, name='wx_auth_check_email'),
    path('auth/change-password/', views.auth_change_password, name='wx_auth_change_password'),

    # 首页 / 商品（匿名可访问）
    path('home/', views.home, name='wx_home'),
    path('goods/', views.goods_list, name='wx_goods_list'),
    path('goods/detail/', views.goods_detail_by_query, name='wx_goods_detail_query'),
    path('goods/<int:goods_id>/', views.goods_detail, name='wx_goods_detail'),

    # 个人中心
    path('user/me/', views.user_me, name='wx_user_me'),
    path('user/profile/', views.user_update_profile, name='wx_user_profile'),
    path('user/avatar/', views.user_upload_avatar, name='wx_user_avatar'),
    path('user/qrcode/', views.user_upload_qrcode, name='wx_user_qrcode'),
    path('user/favorites/', views.my_favorites, name='wx_my_favorites'),
    path('user/goods/', views.my_goods, name='wx_my_goods'),
    path('user/trades/', views.my_trades, name='wx_my_trades'),

    # 商品操作
    path('goods/upload-image/', views.upload_tmp_image, name='wx_upload_tmp_image'),
    path('goods/publish/', views.goods_publish, name='wx_goods_publish'),
    path('goods/favorite/', views.goods_favorite, name='wx_goods_favorite'),
    path('goods/status/', views.goods_update_status, name='wx_goods_status'),
    path('goods/toggle-repeat/', views.goods_toggle_repeat, name='wx_goods_toggle_repeat'),

    # 聊天
    path('chats/', views.chat_list, name='wx_chat_list'),
    path('chat/start/', views.chat_start, name='wx_chat_start'),
    path('chat/messages/', views.chat_messages, name='wx_chat_messages'),
    path('chat/send/', views.chat_send, name='wx_chat_send'),
    path('chat/confirm/', views.chat_confirm, name='wx_chat_confirm'),
    path('chat/complete/', views.chat_complete, name='wx_chat_complete'),
    path('chat/cancel/', views.chat_cancel, name='wx_chat_cancel'),
]
