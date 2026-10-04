"""
用户模型
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """自定义用户模型"""
    # 邮箱作为登录账号
    email = models.EmailField(_('邮箱'), unique=True)
    # 微信 openid（预留）
    wx_openid = models.CharField(max_length=100, blank=True, null=True, unique=True)
    # 微信 unionid（预留）
    wx_unionid = models.CharField(max_length=100, blank=True, null=True, unique=True)
    # 昵称（与settings.MAX_NICKNAME_LENGTH一致）
    nickname = models.CharField(max_length=20, blank=True, default='')
    # 头像
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    # 学校
    school = models.CharField(max_length=100, blank=True, default='')
    # 个人收款码图片
    payment_qrcode = models.ImageField(upload_to='payment_qrcodes/', blank=True, null=True)
    # 手机号
    phone = models.CharField(max_length=20, blank=True, default='')
    # 简介（与settings.MAX_TEXT_LENGTH一致）
    bio = models.TextField(max_length=5000, blank=True, default='')
    # 注册时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'swap_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.email


class VerifyCode(models.Model):
    """邮箱验证码"""
    email = models.EmailField(verbose_name='邮箱', db_index=True)
    code = models.CharField(max_length=6, verbose_name='验证码')
    # 用途：register-注册, login-登录, reset-重置密码
    purpose = models.CharField(max_length=20, default='login', verbose_name='用途')
    # 是否已使用
    is_used = models.BooleanField(default=False, verbose_name='已使用')
    # 错误尝试次数（达到上限自动作废，防暴破）
    attempts = models.IntegerField(default=0, verbose_name='错误尝试次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'swap_verify_code'
        verbose_name = '验证码'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} - {self.code}'



