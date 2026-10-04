# -*- coding: utf-8 -*-
"""清理 wxapi 测试数据（临时，用后即删）"""
import os
import sys

import django

sys.path.insert(0, r'e:\YZP\YZP_work\PCQUICK\project\swapweb\swap')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swapweb.settings')
django.setup()

from swapweb.goods.models import Goods, GoodsImage
from swapweb.users.models import User

test_users = list(User.objects.filter(email__startswith='wxtest_'))
paths = []

for u in test_users:
    if u.avatar:
        paths.append(u.avatar.path)
    if u.payment_qrcode:
        paths.append(u.payment_qrcode.path)
    for g in Goods.objects.filter(seller=u):
        for img in GoodsImage.objects.filter(goods=g):
            try:
                paths.append(img.image.path)
            except Exception:
                pass
    # wx 临时上传文件
    for f in u.wx_temp_files.all():
        try:
            paths.append(f.file.path)
        except Exception:
            pass

names = [u.email for u in test_users]
deleted_users = User.objects.filter(email__in=names).delete()
print('删除用户:', names)
print('用户级联删除结果:', deleted_users)

removed = 0
for p in paths:
    try:
        if os.path.isfile(p):
            os.remove(p)
            removed += 1
    except Exception as e:
        print('文件删除失败:', p, e)
print('删除媒体文件:', removed)

# 清理空的 wx_tmp / goods 目录残留（不动已有真实文件）
for d in ['wx_tmp']:
    full = os.path.join('data', 'media', d)
    if os.path.isdir(full):
        print(d, '剩余文件:', os.listdir(full))
