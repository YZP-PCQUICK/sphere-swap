"""
goods app URL配置
"""
from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'goods'

urlpatterns = [
    # 页面
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('advertise/', TemplateView.as_view(template_name='goods/advertise.html'), name='advertise'),
    path('support/', TemplateView.as_view(template_name='goods/support.html'), name='support'),
    path('list/', views.goods_list, name='list'),
    path('detail/<int:goods_id>/', views.goods_detail, name='detail'),
    path('publish/', views.publish_page, name='publish'),
    path('transactions/', views.transactions, name='transactions'),
    path('favorites/', views.my_favorites, name='my_favorites'),
    
    # API
    path('api/ads/today/', views.ads_today, name='ads_today'),
    path('api/publish/', views.publish_goods, name='publish_api'),
    path('api/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('api/status/', views.update_goods_status, name='update_status'),
    path('api/toggle-repeat/', views.toggle_repeat, name='toggle_repeat'),
    path('privacy/', TemplateView.as_view(template_name='goods/privacy.html'), name='privacy'),
     path('terms/', TemplateView.as_view(template_name='goods/terms.html'), name='terms'),
     path('settings/', TemplateView.as_view(template_name='goods/settings.html'), name='settings'),
]
