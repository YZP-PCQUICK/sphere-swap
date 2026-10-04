"""
微信小程序接口专用模型

- WxToken: 小程序登录令牌（邮箱+密码登录成功后签发，替代 Web 端 Session）
- WxTempFile: 发布商品前先上传的临时图片（发布成功后移动到 goods/ 目录）
"""
from django.db import models
from django.conf import settings


class WxToken(models.Model):
    """小程序登录令牌"""
    key = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='令牌')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wx_tokens', verbose_name='用户'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    last_used_at = models.DateTimeField(auto_now=True, verbose_name='最近使用时间')

    class Meta:
        db_table = 'swap_wx_token'
        verbose_name = '小程序令牌'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.email} - {self.key[:8]}...'


class WxTempFile(models.Model):
    """小程序发布商品前上传的临时图片"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wx_temp_files', verbose_name='上传者'
    )
    file = models.FileField(upload_to='wx_tmp/', verbose_name='临时文件')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        db_table = 'swap_wx_temp_file'
        verbose_name = '小程序临时文件'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return self.file.name
