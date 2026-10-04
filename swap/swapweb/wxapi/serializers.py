"""
序列化辅助：把现有模型转成小程序所需 JSON（媒体一律返回绝对 URL）
"""
from django.utils import timezone


def abs_url(request, fieldfile_url):
    """把媒体相对地址转为绝对地址，供小程序 image/video 组件直接加载"""
    if not fieldfile_url:
        return ''
    try:
        url = request.build_absolute_uri(fieldfile_url)
        # nginx 反代下 Django 误以为自己是 http，会拼出 http:// 图片地址；
        # 微信真机禁止加载 http 资源，站点已全站 HTTPS，这里强制升级
        return url.replace('http://', 'https://', 1)
    except Exception:
        return fieldfile_url


def goods_card(g, request):
    """商品卡片（首页/列表/收藏等通用）"""
    img = g.images.first()
    return {
        'id': g.id,
        'title': g.title,
        'price': str(g.price),
        'original_price': str(g.original_price) if g.original_price is not None else '',
        'category': g.category,
        'category_name': g.get_category_display(),
        'sub_category': g.sub_category,
        'trade_type': g.trade_type,
        'trade_type_name': g.get_trade_type_display(),
        'school': g.school,
        'status': g.status,
        'allow_repeat': g.allow_repeat,
        'views': g.views,
        'favorites': g.favorites,
        'image': abs_url(request, img.image.url) if img else '',
        'created_display': timezone.localtime(g.created_at).strftime('%m-%d %H:%M'),
        'created_iso': g.created_at.isoformat(),
    }


def goods_detail(g, request):
    """商品详情（含全部图片）"""
    data = goods_card(g, request)
    data.update({
        'description': g.description,
        'images': [abs_url(request, i.image.url) for i in g.images.all()],
        'created_full': timezone.localtime(g.created_at).strftime('%Y-%m-%d %H:%M'),
    })
    seller = g.seller
    data['seller'] = {
        'id': seller.id,
        'nickname': seller.nickname or seller.email,
        'school': seller.school or '未填写学校',
        'avatar': abs_url(request, seller.avatar.url) if seller.avatar else '',
        'has_qrcode': bool(seller.payment_qrcode),
    }
    return data


def user_brief(u, request):
    """用户信息（本人视角，含收款码）"""
    return {
        'id': u.id,
        'email': u.email,
        'nickname': u.nickname or u.email,
        'avatar': abs_url(request, u.avatar.url) if u.avatar else '',
        'school': u.school,
        'phone': u.phone,
        'bio': u.bio,
        'payment_qrcode': abs_url(request, u.payment_qrcode.url) if u.payment_qrcode else '',
        'created_display': timezone.localtime(u.created_at).strftime('%Y-%m-%d'),
        'goods_count': u.goods.count(),
        'favorites_count': u.favorites.count(),
    }


def user_public(u, request):
    """用户公开信息（他人视角，无收款码/手机号）"""
    return {
        'id': u.id,
        'nickname': u.nickname or u.email,
        'avatar': abs_url(request, u.avatar.url) if u.avatar else '',
        'school': u.school,
    }


def message_brief(m, request, my_user_id):
    """聊天消息（与 Web 端 api_messages 字段一致）"""
    return {
        'id': m.id,
        'sender': m.sender_id,
        'sender_email': m.sender.email,
        'nickname': m.sender.nickname or m.sender.email,
        'avatar': abs_url(request, m.sender.avatar.url) if m.sender.avatar else '',
        'is_me': m.sender_id == my_user_id,
        'type': m.msg_type,
        'content': m.content,
        'file': abs_url(request, m.file.url) if m.file else '',
        'created': timezone.localtime(m.created_at).strftime('%H:%M'),
    }


def conversation_brief(conv, request, my_user_id):
    """会话列表项（与 Web 端 chat/list.html 展示字段一致）"""
    is_buyer = conv.buyer_id == my_user_id
    unread = conv.buyer_unread if is_buyer else conv.seller_unread
    goods = conv.goods
    gimg = goods.images.first()
    peer = conv.seller if is_buyer else conv.buyer
    return {
        'id': conv.id,
        'is_buyer': is_buyer,
        'status': conv.status,
        'status_name': conv.get_status_display(),
        'unread': unread or 0,
        'last_message': conv.last_message or '开始交流吧',
        'last_message_at': timezone.localtime(conv.last_message_at).strftime('%m-%d %H:%M') if conv.last_message_at else '',
        'peer': user_public(peer, request),
        'goods': {
            'id': goods.id,
            'title': goods.title,
            'price': str(goods.price),
            'image': abs_url(request, gimg.image.url) if gimg else '',
            'status': goods.status,
            'allow_repeat': goods.allow_repeat,
        },
    }


def categories():
    """全部分类 [{key, name}]"""
    from swapweb.goods.models import CATEGORY_CHOICES
    return [{'key': k, 'name': n} for k, n in CATEGORY_CHOICES]
