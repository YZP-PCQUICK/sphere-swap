"""
goods app 配置
"""
from django.apps import AppConfig


class GoodsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'swapweb.goods'
    verbose_name = '商品管理'
