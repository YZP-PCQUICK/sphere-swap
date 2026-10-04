"""
商品模型
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


# 大分类选项
CATEGORY_CHOICES = [
    ('digital', '数码电子'),
    ('books', '书籍教材'),
    ('daily', '生活用品'),
    ('clothing', '服饰鞋包'),
    ('sports', '运动器材'),
    ('service', '校园服务'),
    ('snack', '零食餐饮'),
    ('beauty', '美妆个护'),
    ('art', '乐器文创'),
    ('rental', '出租借用'),
    ('free', '免费赠送'),
    ('other', '其他'),
]

# 交易方式
TRADE_TYPE_CHOICES = [
    ('pickup', '自提'),
    ('delivery', '配送'),
]

# 商品状态
STATUS_CHOICES = [
    ('on_sale', '在售'),
    ('sold', '已售出'),
    ('offline', '已下架'),
]


class Goods(models.Model):
    """商品"""
    # 卖家
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='goods',
        verbose_name='卖家'
    )
    # 商品名称
    title = models.CharField(max_length=100, verbose_name='商品名称')
    # 商品描述
    description = models.TextField(max_length=2000, verbose_name='商品描述')
    # 价格
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='价格')
    # 原价
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        blank=True, null=True, verbose_name='原价'
    )
    # 大分类
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES,
        verbose_name='大分类'
    )
    # 小分类（用户自定义输入）
    sub_category = models.CharField(max_length=20, blank=True, default='', verbose_name='小分类')
    # 交易方式
    trade_type = models.CharField(
        max_length=20, choices=TRADE_TYPE_CHOICES,
        default='pickup', verbose_name='交易方式'
    )
    # 学校
    school = models.CharField(max_length=100, verbose_name='学校', db_index=True)
    # 商品状态
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='on_sale', verbose_name='状态', db_index=True
    )
    # 是否允许重复售卖（勾选后交易完成商品仍在售，可多次交易）
    allow_repeat = models.BooleanField(default=False, verbose_name='允许重复售卖')
    # 浏览量
    views = models.IntegerField(default=0, verbose_name='浏览量')
    # 收藏数
    favorites = models.IntegerField(default=0, verbose_name='收藏数')
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发布时间', db_index=True)
    # 更新时间
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'swap_goods'
        verbose_name = '商品'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_first_image(self):
        """获取第一张图片"""
        img = self.images.first()
        return img.image.url if img else ''


class GoodsImage(models.Model):
    """商品图片"""
    goods = models.ForeignKey(
        Goods, on_delete=models.CASCADE,
        related_name='images', verbose_name='商品'
    )
    image = models.ImageField(upload_to='goods/', verbose_name='图片')
    sort = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'swap_goods_image'
        verbose_name = '商品图片'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return f'{self.goods.title} - 图片{self.id}'


class Favorite(models.Model):
    """商品收藏"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='用户'
    )
    goods = models.ForeignKey(
        Goods, on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='商品'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')

    class Meta:
        db_table = 'swap_favorite'
        verbose_name = '收藏'
        verbose_name_plural = verbose_name
        unique_together = ('user', 'goods')

    def __str__(self):
        return f'{self.user.email} 收藏 {self.goods.title}'


# 单日广告投放上限
AD_DAILY_LIMIT = 5


class Ad(models.Model):
    """首页广告（可多选投放日期，全部投放结束后自动删除）"""
    image = models.ImageField(upload_to='ads/', verbose_name='广告图片')
    link = models.URLField(blank=True, max_length=500, verbose_name='跳转链接')
    priority = models.IntegerField(default=0, verbose_name='优先级')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'swap_ad'
        verbose_name = '广告'
        verbose_name_plural = verbose_name
        ordering = ['-priority', 'id']

    def __str__(self):
        return f'广告{self.id}'

    def delete(self, *args, **kwargs):
        """删除记录时同步删除媒体文件"""
        image = self.image
        super().delete(*args, **kwargs)
        if image:
            image.storage.delete(image.name)

    def is_active_today(self):
        """今天是否在投放日期内"""
        return self.dates.filter(date=timezone.localdate()).exists()


class AdSlot(models.Model):
    """广告投放日期（一个广告可投多天，单日所有广告总数受 AD_DAILY_LIMIT 限制）"""
    ad = models.ForeignKey(
        Ad, on_delete=models.CASCADE,
        related_name='dates', verbose_name='广告'
    )
    date = models.DateField(db_index=True, verbose_name='投放日期')

    class Meta:
        db_table = 'swap_ad_slot'
        verbose_name = '广告投放日期'
        verbose_name_plural = verbose_name
        unique_together = ('ad', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.ad_id} @ {self.date}'


def cleanup_expired_ads():
    """删除所有投放日期已全部结束的广告（含媒体文件），避免占用服务器空间"""
    today = timezone.localdate()
    expired = Ad.objects.exclude(dates__date__gte=today)
    count = expired.count()
    for ad in expired:
        ad.delete()
    return count


def get_ad_day_counts(start_date, end_date):
    """统计日期区间内每日投放的广告数量，返回 {'YYYY-MM-DD': n}"""
    from collections import Counter
    rows = AdSlot.objects.filter(
        date__gte=start_date, date__lte=end_date
    ).values_list('date', flat=True)
    counter = Counter(rows)
    counts = {}
    current = start_date
    while current <= end_date:
        counts[current.isoformat()] = counter.get(current, 0)
        current += timedelta(days=1)
    return counts
