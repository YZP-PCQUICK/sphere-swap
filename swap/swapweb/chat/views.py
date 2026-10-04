"""
聊天视图
包含：会话管理、消息收发（轮询）、安全校验、交易确认/收货流程
"""
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.conf import settings

from .models import Conversation, Message
from swapweb.goods.models import Goods
from swapweb.users.utils import check_content_safety, validate_image_file, validate_video_file


def _conv_allowed(conv, user):
    """当前用户是否为会话参与者"""
    return conv.buyer_id == user.id or conv.seller_id == user.id


def _mark_conversation_read(conv, user):
    """
    将会话中对方发给我的未读消息标记为已读，并清除会话级未读计数。
    消息级已读状态存DB，多设备共用同一份数据，轮询接口3秒内同步到所有设备。
    """
    changed = Message.objects.filter(
        conversation=conv, is_read=False
    ).exclude(sender=user).update(is_read=True)

    if conv.buyer_id == user.id and conv.buyer_unread:
        conv.buyer_unread = 0
        conv.save(update_fields=['buyer_unread'])
    elif conv.seller_id == user.id and conv.seller_unread:
        conv.seller_unread = 0
        conv.save(update_fields=['seller_unread'])
    return changed


def _my_unread_snapshot(user):
    """当前用户未读消息统计：总数 + 各会话未读数"""
    rows = (Message.objects
            .filter(is_read=False)
            .filter(Q(conversation__buyer=user) | Q(conversation__seller=user))
            .exclude(sender=user)
            .values_list('conversation_id', flat=True))
    per_conv = {}
    for conv_id in rows:
        per_conv[conv_id] = per_conv.get(conv_id, 0) + 1
    return {'count': sum(per_conv.values()), 'conversations': per_conv}


def _conv_context(conv, user):
    """会话基础上下文（供页面和API复用）"""
    is_buyer = conv.buyer_id == user.id
    return {
        'conv': conv,
        'goods': conv.goods,
        'is_buyer': is_buyer,
    }


@login_required
def my_conversations(request):
    """我的会话列表"""
    convs = Conversation.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    )
    return render(request, 'chat/list.html', {
        'conversations': convs,
    })


@login_required
def chat_room(request, conv_id):
    """聊天页面"""
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _conv_allowed(conv, request.user):
        return render(request, 'chat/forbidden.html', status=403)
    # 注意：GET 本身不标记已读（防止预取/预览误标），进入聊天室后由
    # api_messages 轮询立即标记，延迟不超过一次轮询间隔
    ctx = _conv_context(conv, request.user)
    peer = (conv.seller if conv.buyer_id == request.user.id else conv.buyer)
    goods_sold = conv.goods.status == 'sold' and not conv.goods.allow_repeat
    return render(request, 'chat/room.html', {
        **ctx,
        'peer_name': f'{peer.nickname or peer.email}（{"卖家" if conv.buyer_id == request.user.id else "买家"}）',
        'peer_nickname': peer.nickname or peer.email,
        'peer_avatar': peer.avatar.url if peer.avatar else '',
        'my_avatar': request.user.avatar.url if request.user.avatar else '',
        'goods_sold': goods_sold,
        'csrf_token': None,
    })


@login_required
@require_POST
def start_conversation(request):
    """从商品详情发起会话（创建或复用进行中的会话）"""
    data = json.loads(request.body or '{}')
    goods_id = data.get('goods_id')
    goods = get_object_or_404(Goods, id=goods_id)

    if goods.seller_id == request.user.id:
        return JsonResponse({'success': False, 'msg': '不能和自己交易'})
    if goods.status != 'on_sale':
        return JsonResponse({'success': False, 'msg': '该商品当前不可交易'})

    # 复用进行中的会话
    conv = Conversation.objects.filter(
        goods=goods, buyer=request.user, status__in=['trading', 'confirmed']
    ).first()
    if not conv:
        conv = Conversation.objects.create(
            goods=goods, buyer=request.user, seller=goods.seller
        )
        # 开场消息
        Message.objects.create(
            conversation=conv,
            sender=request.user,
            msg_type='text',
            content=f'你好，我看上了你的「{goods.title}」，请问还在卖吗？'
        )
        _update_conv_preview(conv)
        # 新会话 = 新的购买意向，发邮件通知卖家（仅首次发起，避免重复点击骚扰）
        _notify_seller_interest(goods, request.user)

    return JsonResponse({'success': True, 'conv_id': conv.id})


def _notify_seller_interest(goods, buyer):
    """
    商品咨询邮件通知：买家发起会话时，通过QQ邮箱SMTP通知卖家。
    后台线程发送（接口不受SMTP耗时影响），失败自动重试，最多3次。
    """
    import logging
    import threading
    import time
    from django.core.mail import send_mail
    from swapweb.users.utils import build_contact_seller_email

    seller = goods.seller
    goods_url = f'https://swap.pcquick.cn/detail/{goods.id}/'
    buyer_name = buyer.nickname or buyer.email.split('@')[0]
    buyer_contact = buyer.email

    subject, text_msg, html_msg = build_contact_seller_email(
        goods_title=goods.title,
        goods_url=goods_url,
        buyer_name=buyer_name,
        buyer_contact=buyer_contact,
    )

    def _deliver():
        logger = logging.getLogger(__name__)
        for attempt in range(1, 4):  # 失败重试，最多3次
            try:
                send_mail(
                    subject=subject,
                    message=text_msg,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[seller.email],
                    html_message=html_msg,
                    fail_silently=False,
                )
                return
            except Exception:
                logger.error(f'商品咨询邮件发送失败（第{attempt}次）: goods={goods.id} seller={seller.email}', exc_info=True)
                if attempt < 3:
                    time.sleep(3)

    threading.Thread(target=_deliver, daemon=True).start()


@login_required
@require_GET
def api_messages(request):
    """拉取消息（轮询）
    - 无 after_id：返回服务器当前持有的全部消息（作localStorage种子）
    - 有 after_id：返回该id之后的新消息（增量）
    """
    conv_id = request.GET.get('conversation_id')
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _conv_allowed(conv, request.user):
        return JsonResponse({'success': False, 'msg': '无权访问'}, status=403)

    qs = Message.objects.filter(conversation=conv)
    after_id = request.GET.get('after_id')
    if after_id and str(after_id).isdigit():
        qs = qs.filter(id__gt=int(after_id))
    qs = qs.order_by('created_at', 'id')

    # 拉取消息即视为已读（多设备同步）
    _mark_conversation_read(conv, request.user)
    my_confirmed = (conv.buyer_confirmed if conv.buyer_id == request.user.id
                    else conv.seller_confirmed)
    other_confirmed = (conv.seller_confirmed if conv.buyer_id == request.user.id
                       else conv.buyer_confirmed)

    messages = [{
        'id': m.id,
        'sender': m.sender_id,
        'sender_email': m.sender.email,
        'nickname': m.sender.nickname or m.sender.email,
        'avatar': m.sender.avatar.url if m.sender.avatar else '',
        'is_me': m.sender_id == request.user.id,
        'is_read': m.is_read or m.sender_id == request.user.id,
        'type': m.msg_type,
        'content': m.content,
        'file': m.file.url if m.file else '',
        'created': m.created_at.strftime('%H:%M'),
    } for m in qs]

    return JsonResponse({
        'success': True,
        'conversation_id': conv.id,
        'status': conv.status,
        'my_confirmed': my_confirmed,
        'other_confirmed': other_confirmed,
        'unread': _my_unread_snapshot(request.user),
        # 我发出的消息中已被对方读取的最大ID（id<=该值的消息均已读），用于聊天室已读/未读回执
        'my_read_max_id': Message.objects.filter(
            conversation=conv, sender=request.user, is_read=True
        ).order_by('-id').values_list('id', flat=True).first() or 0,
        'seller_has_qrcode': bool(conv.seller.payment_qrcode),
        'qrcode_url': conv.seller.payment_qrcode.url if conv.seller.payment_qrcode else '',
        'goods': {
            'id': conv.goods.id,
            'title': conv.goods.title,
            'price': str(conv.goods.price),
            'image': conv.goods.get_first_image(),
            'status': conv.goods.status,
            'allow_repeat': conv.goods.allow_repeat,
        },
        'messages': messages,
    })


@login_required
@require_GET
def api_unread(request):
    """
    未读消息统计（全站轮询，3秒一次）
    返回：count=未读总数，conversations={会话ID: 该会话未读数}
    已读状态存DB，多设备共用，任一设备标记已读后其他设备3秒内同步
    """
    return JsonResponse({'success': True, **_my_unread_snapshot(request.user)})


@login_required
@require_POST
def api_send_message(request):
    """发送消息（文字/图片/视频）"""
    conv_id = request.POST.get('conversation_id')
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _conv_allowed(conv, request.user):
        return JsonResponse({'success': False, 'msg': '无权发送'}, status=403)
    if conv.status != 'trading':
        return JsonResponse({'success': False, 'msg': '交易已确定，无法再发消息'})

    msg_type = request.POST.get('type', 'text')
    content = request.POST.get('content', '').strip()
    file = request.FILES.get('file')

    # 安全校验（仅文字消息检查）
    if msg_type == 'text':
        if not content:
            return JsonResponse({'success': False, 'msg': '消息内容不能为空'})
        if len(content) > settings.MAX_MESSAGE_LENGTH:
            return JsonResponse({'success': False, 'msg': f'消息内容不能超过{settings.MAX_MESSAGE_LENGTH}个字'})
        is_safe, violations = check_content_safety(content)
        if not is_safe:
            return JsonResponse({
                'success': False,
                'msg': '消息中包含联系方式或违规内容，已被拦截：' + '、'.join(violations),
                'blocked': True,
            })

    if msg_type in ('image', 'video'):
        if not file:
            return JsonResponse({'success': False, 'msg': '请选择要发送的文件'})
        if file.size > settings.MAX_MEDIA_SIZE:
            return JsonResponse({'success': False, 'msg': '文件过大，无法发送'})
        # 真实类型校验，拒绝伪装成图片/视频的可执行文件
        if msg_type == 'image':
            is_valid, err = validate_image_file(file)
        else:
            is_valid, err = validate_video_file(file)
        if not is_valid:
            return JsonResponse({'success': False, 'msg': err})

    # 创建消息
    msg = Message.objects.create(
        conversation=conv,
        sender=request.user,
        msg_type=msg_type,
        content=content if msg_type == 'text' else '',
        file=file if msg_type in ('image', 'video') else None,
    )
    _update_conv_preview(conv, msg)
    # 接收方未读数 +1
    if conv.buyer_id == request.user.id:
        conv.seller_unread += 1
        conv.save(update_fields=['seller_unread'])
    else:
        conv.buyer_unread += 1
        conv.save(update_fields=['buyer_unread'])

    return JsonResponse({
        'success': True,
        'msg': {
            'id': msg.id,
            'sender': msg.sender_id,
            'is_me': True,
            'avatar': msg.sender.avatar.url if msg.sender.avatar else '',
            'type': msg.msg_type,
            'content': msg.content,
            'file': msg.file.url if msg.file else '',
            'created': msg.created_at.strftime('%H:%M'),
        }
    })


@login_required
@require_POST
def api_confirm(request):
    """双方确认交易"""
    data = json.loads(request.body or '{}')
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if not _conv_allowed(conv, request.user):
        return JsonResponse({'success': False, 'msg': '无权操作'}, status=403)
    if conv.status != 'trading':
        return JsonResponse({'success': False, 'msg': '交易状态已变化'})

    if conv.buyer_id == request.user.id:
        conv.buyer_confirmed = True
    else:
        conv.seller_confirmed = True
    conv.save(update_fields=['buyer_confirmed', 'seller_confirmed'])

    if conv.buyer_confirmed and conv.seller_confirmed:
        conv.status = 'confirmed'
        conv.save(update_fields=['status'])
        # 双方确认后发送系统提示
        Message.objects.create(
            conversation=conv, sender=conv.seller, msg_type='text',
            content='【系统】买卖双方已确认交易，买家可扫描卖家收款码付款。'
        )
        _update_conv_preview(conv)

    my_confirmed = (conv.buyer_confirmed if conv.buyer_id == request.user.id
                    else conv.seller_confirmed)
    other_confirmed = (conv.seller_confirmed if conv.buyer_id == request.user.id
                       else conv.buyer_confirmed)

    return JsonResponse({
        'success': True,
        'status': conv.status,
        'my_confirmed': my_confirmed,
        'other_confirmed': other_confirmed,
    })


@login_required
@require_POST
def api_complete(request):
    """买家确认收货：交易完成，删除服务器上的聊天记录（长期历史留在双方浏览器localStorage）"""
    data = json.loads(request.body or '{}')
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if conv.buyer_id != request.user.id:
        return JsonResponse({'success': False, 'msg': '只有买家可以确认收货'}, status=403)
    if conv.status != 'confirmed':
        return JsonResponse({'success': False, 'msg': '交易尚未确认，无法收货'})

    conv.status = 'completed'
    conv.save(update_fields=['status'])

    # 根据商品是否允许重复售卖决定商品状态
    goods = conv.goods
    if not goods.allow_repeat:
        goods.status = 'sold'
        goods.save(update_fields=['status'])

    # 删除服务器上的聊天记录（含物理文件）
    for m in Message.objects.filter(conversation=conv):
        m.delete()
    conv.last_message = '交易已完成'
    conv.save(update_fields=['last_message'])

    return JsonResponse({'success': True, 'msg': '交易完成，服务器聊天记录已清除'})


@login_required
@require_POST
def api_cancel(request):
    """买家取消交易"""
    data = json.loads(request.body or '{}')
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if conv.buyer_id != request.user.id:
        return JsonResponse({'success': False, 'msg': '只有买家可以取消交易'}, status=403)
    if conv.status not in ('trading', 'confirmed'):
        return JsonResponse({'success': False, 'msg': '当前状态无法取消交易'})

    conv.status = 'cancelled'
    conv.buyer_confirmed = False
    conv.seller_confirmed = False
    conv.last_message = '交易已取消'
    conv.save(update_fields=['status', 'buyer_confirmed', 'seller_confirmed', 'last_message'])

    return JsonResponse({'success': True, 'msg': '交易已取消'})


def _update_conv_preview(conv, msg=None):
    """更新会话最近消息预览"""
    if msg:
        if msg.msg_type == 'text':
            preview = msg.content[:50]
        elif msg.msg_type == 'image':
            preview = '[图片]'
        else:
            preview = '[视频]'
        conv.last_message = preview
        conv.last_message_at = msg.created_at
    conv.save(update_fields=['last_message', 'last_message_at'])