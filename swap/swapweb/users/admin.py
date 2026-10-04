"""
users admin 配置
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, VerifyCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'nickname', 'school', 'is_staff', 'created_at']
    list_filter = ['is_staff', 'is_active']
    search_fields = ['email', 'nickname', 'school']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    fieldsets = (
        ('基本信息', {
            'fields': ('email', 'username', 'password', 'nickname', 'avatar', 'school', 'phone', 'bio')
        }),
        ('微信相关（预留）', {
            'fields': ('wx_openid', 'wx_unionid'),
        }),
        ('收款信息', {
            'fields': ('payment_qrcode',),
        }),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('时间', {
            'fields': ('last_login', 'created_at', 'updated_at'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )


@admin.register(VerifyCode)
class VerifyCodeAdmin(admin.ModelAdmin):
    list_display = ['email', 'code', 'purpose', 'is_used', 'created_at']
    list_filter = ['purpose', 'is_used']
    search_fields = ['email', 'code']
    ordering = ['-created_at']



