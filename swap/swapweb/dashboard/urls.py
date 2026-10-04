from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # 登录登出
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # 后台首页
    path('', views.index, name='index'),
    
    # 用户管理
    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    
    # 商品管理
    path('goods/', views.goods_list, name='goods_list'),
    path('goods/<int:goods_id>/', views.goods_detail, name='goods_detail'),
    
    # 交易会话管理
    path('conversations/', views.conversation_list, name='conversation_list'),
    path('conversations/<int:conv_id>/', views.conversation_detail, name='conversation_detail'),

    # 广告管理
    path('ads/', views.ad_list, name='ad_list'),
    path('ads/create/', views.ad_create, name='ad_create'),
    path('ads/<int:ad_id>/delete/', views.ad_delete, name='ad_delete'),
]
