"""
users app 配置
"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'swapweb.users'
    verbose_name = '用户管理'
