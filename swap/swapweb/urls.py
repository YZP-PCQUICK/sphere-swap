"""
swapweb URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-panel/', include('swapweb.dashboard.urls')),
    path('wx/api/', include('swapweb.wxapi.urls')),
    path('users/', include('swapweb.users.urls')),
    path('chat/', include('swapweb.chat.urls')),
    path('', include('swapweb.goods.urls')),
]

# 开发环境下提供媒体文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else None)
