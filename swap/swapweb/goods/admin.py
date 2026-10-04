"""
goods admin 配置
"""
from django.contrib import admin
from .models import Goods, GoodsImage, Favorite


class GoodsImageInline(admin.TabularInline):
    model = GoodsImage
    extra = 0
    readonly_fields = ['image']


@admin.register(Goods)
class GoodsAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'price', 'category', 'school', 'status', 'views', 'created_at']
    list_filter = ['category', 'trade_type', 'status', 'school']
    search_fields = ['title', 'description', 'school', 'sub_category', 'seller__email']
    ordering = ['-created_at']
    list_per_page = 30
    readonly_fields = ['views', 'favorites', 'created_at', 'updated_at']
    inlines = [GoodsImageInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'price', 'original_price'),
        }),
        ('分类信息', {
            'fields': ('category', 'sub_category', 'trade_type', 'school'),
        }),
        ('卖家', {
            'fields': ('seller',),
        }),
        ('状态与统计', {
            'fields': ('status', 'views', 'favorites'),
        }),
        ('时间', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'goods', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'goods__title']
    ordering = ['-created_at']
