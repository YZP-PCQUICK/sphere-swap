"""
聊天模型：会话和消息

设计说明：
- 会话(Conversation)关联商品与买卖双方，含状态流转（洽谈中->双方确认->已收货）
- 消息(Message)仅作【短期中转】，交易完成（买家确认收货）后由程序删除，不长期保留
- 长期聊天历史由前端存入浏览器 localStorage
"""
from django.db import models
from django.conf import settings
from swapweb.goods.models import Goods


# 会话状态
CONV_STATUS_CHOICES = [
    ('trading', '洽谈中'),      # 双方在聊
    ('confirmed', '交易确认'),  # 双方都确认交易
    ('completed', '已完成'),    # 买家确认收货，交易完成
    ('cancelled', '已取消'),    # 买家取消交易
]

# 消息类型
MSG_TYPE_CHOICES = [
    ('text', '文字'),
    ('image', '图片'),
    ('video', '视频'),
]


class Conversation(models.Model):
    """交易会话"""
    goods = models.ForeignKey(
        Goods, on_delete=models.CASCADE,
        related_name='conversations', verbose_name='商品'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sale_conversations', verbose_name='买家'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sell_conversations', verbose_name='卖家'
    )
    # 状态
    status = models.CharField(
        max_length=20, choices=CONV_STATUS_CHOICES,
        default='trading', verbose_name='状态', db_index=True
    )
    # 买/卖双方是否确认交易
    buyer_confirmed = models.BooleanField(default=False, verbose_name='买家确认')
    seller_confirmed = models.BooleanField(default=False, verbose_name='卖家确认')
    # 是否有未读消息（按接收方计数简化：分别存买卖双方未读数）
    buyer_unread = models.IntegerField(default=0, verbose_name='买家未读数')
    seller_unread = models.IntegerField(default=0, verbose_name='卖家未读数')
    # 最近消息预览（仅展示用，不保留明细）
    last_message = models.CharField(max_length=255, blank=True, default='', verbose_name='最近消息')
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='最近消息时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'swap_conversation'
        verbose_name = '交易会话'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
        # 同一商品同一买家只允许一个进行中的会话
        constraints = [
            models.UniqueConstraint(
                fields=['goods', 'buyer'],
                condition=models.Q(status__in=['trading', 'confirmed']),
                name='unique_active_conv_per_buyer'
            )
        ]

    def __str__(self):
        return f'{self.goods.title} - {self.buyer.email}'


class Message(models.Model):
    """消息（短期中转，交易完成后删除）"""
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages', verbose_name='会话'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='chat_messages', verbose_name='发送者'
    )
    msg_type = models.CharField(
        max_length=10, choices=MSG_TYPE_CHOICES,
        default='text', verbose_name='消息类型'
    )
    # 文字内容
    content = models.TextField(blank=True, default='', verbose_name='内容')
    # 图片/视频（临时中转存储）
    file = models.FileField(upload_to='chat_tmp/', blank=True, null=True, verbose_name='附件')
    # 已读状态（接收方读取后置True；发送者自己的消息视为已读，统计时排除）
    is_read = models.BooleanField(default=False, verbose_name='已读', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发送时间', db_index=True)

    class Meta:
        db_table = 'swap_message'
        verbose_name = '消息'
        verbose_name_plural = verbose_name
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.sender.email}: {self.content or f"[{self.get_msg_type_display()}]"}'