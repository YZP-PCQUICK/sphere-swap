"""
微信小程序专用 JSON 接口

设计原则：
- 复用现有业务模型与校验逻辑（users/goods/chat），与网站共用同一数据库
- 认证：Token（Authorization: Token <key>），由登录/注册接口签发（方案A：邮箱+密码，与网站一致）
- 所有媒体返回绝对 URL，小程序 image/video 可直接加载
- 全部 csrf_exempt（无 Cookie 场景，令牌即凭证）
"""
import json
import os
import shutil
import secrets
import random
import threading
import logging
import smtplib

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.mail import send_mail
from datetime import timedelta

from swapweb.users.models import User, VerifyCode
from swapweb.users.utils import check_content_safety, validate_image_file, validate_video_file, build_verify_code_email
from swapweb.users.email_check import validate_email_syntax, check_email_deliverable
from swapweb.users.views import (
    _check_verify_code, _record_login_failure,
    _login_is_throttled, _clear_login_failures,
)
from swapweb.goods.models import Goods, GoodsImage, Favorite
from swapweb.chat.models import Conversation, Message

from .models import WxToken, WxTempFile
from .auth import wx_login_required, get_token_user
from . import serializers as S

logger = logging.getLogger(__name__)

OK = lambda **kw: JsonResponse({'success': True, **kw})
ERR = lambda msg, status=400: JsonResponse({'success': False, 'msg': msg}, status=status)


def _body(request):
    """解析 JSON 请求体"""
    try:
        return json.loads(request.body or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


# ============================================================
# 认证：发送验证码 / 注册 / 登录 / 登出（方案A，与网站同一套逻辑）
# ============================================================

@csrf_exempt
@require_POST
def auth_send_code(request):
    """发送邮箱验证码（与网站 users.send_verify_code 同规则）"""
    data = _body(request)
    email = (data.get('email') or '').strip()
    purpose = data.get('purpose', 'login')  # login / register / reset

    if not validate_email_syntax(email):
        return ERR('请输入有效的邮箱地址')

    if purpose == 'register':
        if User.objects.filter(email=email).exists():
            return ERR('该邮箱已注册，请直接登录')
    elif purpose in ('login', 'reset'):
        if not User.objects.filter(email=email).exists():
            return ERR('该邮箱未注册，请先注册')

    recent = VerifyCode.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=settings.VERIFY_CODE_RESEND_SECONDS)
    ).first()
    if recent:
        return ERR('验证码发送太频繁，请稍后再试')

    # 校验邮箱真实可收信（DNS域名检查 + SMTP收件人探测，探测无法判定时放行）
    deliverable, deliver_err = check_email_deliverable(email)
    if deliverable is False:
        return ERR(deliver_err)

    code = ''.join(random.choices('0123456789', k=6))
    VerifyCode.objects.create(email=email, code=code, purpose=purpose)

    # 后台线程发送邮件，接口立即返回（SMTP发信耗时数秒，同步发送会导致客户端超时）
    subject, text_msg, html_msg = build_verify_code_email(code)

    def _deliver():
        try:
            send_mail(
                subject=subject,
                message=text_msg,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_msg,
                fail_silently=False,
            )
        except Exception:
            logger.error(f"[wx] 验证码邮件发送失败: {email}", exc_info=True)

    threading.Thread(target=_deliver, daemon=True).start()
    return OK(msg='验证码已发送')


@csrf_exempt
@require_POST
def auth_register(request):
    """注册（邮箱+验证码+密码），成功后直接签发令牌"""
    data = _body(request)
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''
    code = (data.get('code') or '').strip()

    if not validate_email_syntax(email):
        return ERR('请输入有效的邮箱地址')
    if len(password) < 6:
        return ERR('密码至少6位')
    if password != confirm_password:
        return ERR('两次密码输入不一致')
    if User.objects.filter(email=email).exists():
        return ERR('该邮箱已注册')

    latest_code, code_err = _check_verify_code(email, code, 'register')
    if not latest_code:
        return ERR(code_err)

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        nickname=f'用户{random.randint(1000, 9999)}',
    )
    latest_code.is_used = True
    latest_code.save(update_fields=['is_used'])

    token = WxToken.objects.create(key=secrets.token_hex(32), user=user)
    return OK(msg='注册成功', token=token.key, user=S.user_brief(user, request))


@csrf_exempt
@require_POST
def auth_login(request):
    """登录（邮箱+密码），签发令牌；失败限速与网站共用同一缓存计数"""
    data = _body(request)
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not validate_email_syntax(email):
        return ERR('请输入有效的邮箱地址')
    if not password:
        return ERR('请输入密码')

    ip = request.META.get('REMOTE_ADDR', '')
    if _login_is_throttled(email, ip):
        return JsonResponse({'success': False, 'msg': '失败次数过多，请15分钟后再试'}, status=429)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        _record_login_failure(email, ip)
        return ERR('该邮箱未注册，请先注册')

    if not user.check_password(password):
        _record_login_failure(email, ip)
        return ERR('邮箱或密码错误')

    _clear_login_failures(email, ip)
    token = WxToken.objects.create(key=secrets.token_hex(32), user=user)
    return OK(msg='登录成功', token=token.key, user=S.user_brief(user, request))


@csrf_exempt
@wx_login_required
@require_POST
def auth_logout(request):
    """登出：作废当前令牌"""
    from .auth import get_token_key
    WxToken.objects.filter(key=get_token_key(request), user=request.wx_user).delete()
    return OK(msg='已退出登录')


@csrf_exempt
@require_POST
def auth_reset_password(request):
    """重置密码（邮箱验证码 + 两次新密码，与网站同规则）"""
    data = _body(request)
    email = (data.get('email') or '').strip()
    code = (data.get('code') or '').strip()
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not validate_email_syntax(email):
        return ERR('请输入有效的邮箱地址')
    if not code:
        return ERR('请输入验证码')
    if len(new_password) < 6:
        return ERR('密码至少6位')
    if new_password != confirm_password:
        return ERR('两次密码输入不一致')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return ERR('该邮箱未注册，请先注册')

    latest_code, code_err = _check_verify_code(email, code, 'reset')
    if not latest_code:
        return ERR(code_err)

    user.set_password(new_password)
    user.save()
    latest_code.is_used = True
    latest_code.save(update_fields=['is_used'])
    # 密码变更后作废该用户所有小程序令牌，要求重新登录
    WxToken.objects.filter(user=user).delete()
    return OK(msg='密码重置成功，请使用新密码登录')


@csrf_exempt
@require_POST
def auth_check_email(request):
    """检查邮箱是否已注册"""
    data = _body(request)
    email = (data.get('email') or '').strip()
    if not email:
        return JsonResponse({'exists': False, 'msg': '邮箱不能为空'})
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})


@csrf_exempt
@wx_login_required
@require_POST
def auth_change_password(request):
    """修改密码（验证旧密码，成功后作废该用户所有小程序令牌）"""
    user = request.wx_user
    data = _body(request)
    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not old_password:
        return ERR('请输入当前密码')
    if not user.check_password(old_password):
        return ERR('当前密码不正确')
    if not new_password:
        return ERR('请输入新密码')
    if len(new_password) < 6:
        return ERR('新密码至少6位')
    if new_password != confirm_password:
        return ERR('两次输入的新密码不一致')
    if new_password == old_password:
        return ERR('新密码不能与当前密码相同')

    user.set_password(new_password)
    user.save()
    # 密码变更后作废该用户所有小程序令牌，要求重新登录
    WxToken.objects.filter(user=user).delete()
    return OK(msg='密码修改成功，请使用新密码重新登录')


# ============================================================
# 首页 / 商品列表 / 商品详情（匿名可访问）
# ============================================================

@csrf_exempt
@require_GET
def home(request):
    """首页：分类 + 最新商品（与网站 index 视图同数据）"""
    goods_list = Goods.objects.filter(status='on_sale').order_by('-created_at')[:20]
    return OK(
        categories=S.categories(),
        goods=[S.goods_card(g, request) for g in goods_list],
    )


@csrf_exempt
@require_GET
def goods_list(request):
    """商品列表：搜索/筛选/排序/分页（与网站 goods_list 视图同规则）"""
    queryset = Goods.objects.filter(status='on_sale')

    keyword = request.GET.get('keyword', '').strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(sub_category__icontains=keyword)
        )

    category = request.GET.get('category', '')
    if category:
        queryset = queryset.filter(category=category)

    sub_category = request.GET.get('sub_category', '').strip()
    if sub_category:
        queryset = queryset.filter(sub_category__icontains=sub_category)

    school = request.GET.get('school', '').strip()
    if school:
        queryset = queryset.filter(school__icontains=school)

    trade_type = request.GET.get('trade_type', '')
    if trade_type:
        queryset = queryset.filter(trade_type=trade_type)

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    if min_price:
        try:
            queryset = queryset.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            queryset = queryset.filter(price__lte=float(max_price))
        except ValueError:
            pass

    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        queryset = queryset.order_by('price')
    elif sort == 'price_desc':
        queryset = queryset.order_by('-price')
    elif sort == 'views':
        queryset = queryset.order_by('-views')
    else:
        queryset = queryset.order_by('-created_at')

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page)

    return OK(
        count=paginator.count,
        num_pages=paginator.num_pages,
        page=page_obj.number,
        has_next=page_obj.has_next(),
        has_previous=page_obj.has_previous(),
        goods=[S.goods_card(g, request) for g in page_obj.object_list],
    )


@csrf_exempt
@require_GET
def goods_detail(request, goods_id):
    """商品详情（浏览量+1，与网站一致）"""
    goods = get_object_or_404(Goods, id=goods_id)
    goods.views += 1
    goods.save(update_fields=['views'])

    user = get_token_user(request)
    is_favorited = False
    if user:
        is_favorited = Favorite.objects.filter(user=user, goods=goods).exists()

    seller_other = Goods.objects.filter(
        seller=goods.seller, status='on_sale'
    ).exclude(id=goods.id)[:6]

    return OK(
        goods=S.goods_detail(goods, request),
        is_favorited=is_favorited,
        seller_other=[S.goods_card(g, request) for g in seller_other],
        is_mine=bool(user and goods.seller_id == user.id),
    )


@csrf_exempt
@require_GET
def goods_detail_by_query(request):
    """商品详情（?goods_id= 形式，便于部分调用场景）"""
    goods_id = request.GET.get('goods_id')
    if not goods_id or not str(goods_id).isdigit():
        return ERR('请提供 goods_id')
    request.GET = request.GET.copy()
    return goods_detail(request, int(goods_id))


# ============================================================
# 个人中心（需登录）
# ============================================================

@csrf_exempt
@wx_login_required
@require_GET
def user_me(request):
    """我的信息"""
    return OK(user=S.user_brief(request.wx_user, request))


@csrf_exempt
@wx_login_required
@require_POST
def user_update_profile(request):
    """更新个人信息（与网站 update_profile 同规则）"""
    data = _body(request)
    user = request.wx_user

    nickname = (data.get('nickname') or '').strip()
    school = (data.get('school') or '').strip()
    phone = (data.get('phone') or '').strip()
    bio = (data.get('bio') or '').strip()

    is_safe, violations = check_content_safety(f'{nickname} {school} {bio}')
    if not is_safe:
        return ERR('内容包含违规信息：' + '、'.join(violations))

    if len(nickname) > settings.MAX_NICKNAME_LENGTH:
        return ERR(f'昵称不能超过{settings.MAX_NICKNAME_LENGTH}个字')
    if len(school) > settings.MAX_SCHOOL_LENGTH:
        return ERR(f'学校名称不能超过{settings.MAX_SCHOOL_LENGTH}个字')
    if len(bio) > settings.MAX_TEXT_LENGTH:
        return ERR(f'个人简介不能超过{settings.MAX_TEXT_LENGTH}个字')

    if nickname:
        user.nickname = nickname
    if school:
        user.school = school
    if phone:
        user.phone = phone[:20]
    if bio:
        user.bio = bio
    user.save()

    return OK(msg='保存成功', user=S.user_brief(user, request))


def _reencode_jpeg(dj_file):
    """用 Pillow 统一转码为 JPEG（iPhone 的 HEIC、部分 WebP 小程序 image 组件无法解码会显示空白，previewImage 却正常）"""
    import io
    from PIL import Image, ImageOps
    from django.core.files.uploadedfile import InMemoryUploadedFile
    img = Image.open(dj_file)
    img = ImageOps.exif_transpose(img)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    size = buf.getbuffer().nbytes
    buf.seek(0)
    return InMemoryUploadedFile(buf, None, 'img_' + secrets.token_hex(8) + '.jpg', 'image/jpeg', size, None)


@csrf_exempt
@wx_login_required
@require_POST
def user_upload_avatar(request):
    """上传头像（multipart: avatar，与网站同校验）"""
    user = request.wx_user
    if 'avatar' not in request.FILES:
        return ERR('请选择图片')
    avatar = request.FILES['avatar']
    if avatar.size > 20 * 1024 * 1024:
        return ERR('图片大小不能超过20MB')
    is_valid, err = validate_image_file(avatar)
    if not is_valid:
        return ERR(err)
    user.avatar = _reencode_jpeg(avatar)
    user.save()
    return OK(avatar_url=S.abs_url(request, user.avatar.url))


@csrf_exempt
@wx_login_required
@require_POST
def user_upload_qrcode(request):
    """上传收款码（multipart: payment_qrcode，与网站同校验）"""
    user = request.wx_user
    if 'payment_qrcode' not in request.FILES:
        return ERR('请选择图片')
    qrcode = request.FILES['payment_qrcode']
    if qrcode.size > 20 * 1024 * 1024:
        return ERR('图片大小不能超过20MB')
    is_valid, err = validate_image_file(qrcode)
    if not is_valid:
        return ERR(err)
    user.payment_qrcode = _reencode_jpeg(qrcode)
    user.save()
    return OK(payment_qrcode_url=S.abs_url(request, user.payment_qrcode.url))


# ============================================================
# 商品发布 / 收藏 / 我的发布与交易（需登录）
# ============================================================

@csrf_exempt
@wx_login_required
@require_POST
def upload_tmp_image(request):
    """发布前上传单张商品图到临时区（multipart: image），发布时绑定到商品"""
    f = request.FILES.get('image')
    if not f:
        return ERR('请选择图片')
    if f.size > settings.MAX_IMAGE_SIZE:
        return ERR('图片过大，请压缩后重新上传')
    is_valid, err = validate_image_file(f)
    if not is_valid:
        return ERR(err)
    count = WxTempFile.objects.filter(user=request.wx_user).count()
    if count >= settings.MAX_IMAGES_PER_GOODS:
        return ERR(f'最多上传{settings.MAX_IMAGES_PER_GOODS}张图片')
    rec = WxTempFile.objects.create(user=request.wx_user, file=f)
    return OK(tmp_id=rec.id)


def _move_tmp_to_goods(request, tmp_ids, goods):
    """把临时图片移动到 goods/ 目录并创建 GoodsImage"""
    goods_dir = os.path.join(str(settings.MEDIA_ROOT), 'goods')
    os.makedirs(goods_dir, exist_ok=True)
    saved = 0
    for idx, tid in enumerate(tmp_ids):
        rec = WxTempFile.objects.filter(id=tid, user=request.wx_user).first()
        if not rec:
            continue
        try:
            old_path = rec.file.path
            base_name = os.path.basename(rec.file.name)
            new_name = f'goods_{goods.id}_{idx}_{base_name}'
            new_path = os.path.join(goods_dir, new_name)
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
            img = GoodsImage(goods=goods, sort=idx)
            img.image.name = f'goods/{new_name}'
            img.save()
            saved += 1
        except Exception:
            logger.error(f"[wx] 临时图片绑定失败 tmp_id={tid}", exc_info=True)
        finally:
            rec.delete()
    return saved


@csrf_exempt
@wx_login_required
@require_POST
def goods_publish(request):
    """发布商品（与网站 publish_goods 同规则）
    流程：先用 upload_tmp_image 上传图片得到 tmp_ids，再提交本接口
    """
    data = _body(request)
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    price = (data.get('price') or '').strip()
    original_price = (data.get('original_price') or '').strip()
    category = (data.get('category') or '').strip()
    sub_category = (data.get('sub_category') or '').strip()
    trade_type = (data.get('trade_type') or 'pickup').strip()
    school = (data.get('school') or '').strip()
    allow_repeat = bool(data.get('allow_repeat'))
    tmp_ids = data.get('tmp_ids') or []

    if not title:
        return ERR('请输入商品名称')
    if not price:
        return ERR('请输入商品价格')
    if not category:
        return ERR('请选择商品分类')
    if not school:
        return ERR('请输入学校名称')

    if len(sub_category) > 20:
        return ERR('小分类不能超过20个字')
    if len(title) > settings.MAX_TITLE_LENGTH:
        return ERR(f'商品名称不能超过{settings.MAX_TITLE_LENGTH}个字')
    if len(description) > settings.MAX_TEXT_LENGTH:
        return ERR(f'商品描述不能超过{settings.MAX_TEXT_LENGTH}个字')
    if len(school) > settings.MAX_SCHOOL_LENGTH:
        return ERR(f'学校名称不能超过{settings.MAX_SCHOOL_LENGTH}个字')

    all_text = f'{title} {description} {sub_category} {school}'
    is_safe, violations = check_content_safety(all_text)
    if not is_safe:
        return ERR('内容包含违规信息：' + '、'.join(violations))

    if not tmp_ids:
        return ERR('请至少上传一张商品图片')
    if len(tmp_ids) > settings.MAX_IMAGES_PER_GOODS:
        return ERR(f'最多上传{settings.MAX_IMAGES_PER_GOODS}张图片')

    try:
        price_val = float(price)
        if price_val < 0:
            raise ValueError
    except (ValueError, TypeError):
        return ERR('价格格式不正确')

    original_price_val = None
    if original_price:
        try:
            original_price_val = float(original_price)
        except (ValueError, TypeError):
            pass

    if category not in dict(Goods._meta.get_field('category').choices):
        return ERR('无效的商品分类')
    if trade_type not in ('pickup', 'delivery'):
        return ERR('无效的交易方式')

    goods = Goods.objects.create(
        seller=request.wx_user,
        title=title[:100],
        description=description[:2000],
        price=price_val,
        original_price=original_price_val,
        category=category,
        sub_category=sub_category[:20],
        trade_type=trade_type,
        school=school[:100],
        allow_repeat=allow_repeat,
    )
    saved = _move_tmp_to_goods(request, tmp_ids, goods)
    if saved == 0:
        # 一张图都没绑定成功则回滚，保证与网站一致：商品必有图
        goods.delete()
        return ERR('图片上传失败，请重新上传')

    return OK(msg='发布成功', goods_id=goods.id)


@csrf_exempt
@wx_login_required
@require_POST
def goods_favorite(request):
    """收藏/取消收藏（与网站 toggle_favorite 同规则）"""
    data = _body(request)
    goods_id = data.get('goods_id')
    goods = get_object_or_404(Goods, id=goods_id)
    fav, created = Favorite.objects.get_or_create(user=request.wx_user, goods=goods)
    if not created:
        fav.delete()
        goods.favorites = max(0, goods.favorites - 1)
        is_favorited = False
    else:
        goods.favorites += 1
        is_favorited = True
    goods.save(update_fields=['favorites'])
    return OK(is_favorited=is_favorited)


@csrf_exempt
@wx_login_required
@require_GET
def my_favorites(request):
    """我的收藏"""
    fav_list = Favorite.objects.filter(user=request.wx_user).select_related('goods').order_by('-created_at')
    return OK(goods=[S.goods_card(f.goods, request) for f in fav_list])


@csrf_exempt
@wx_login_required
@require_GET
def my_goods(request):
    """我发布的商品（status: on_sale/sold/offline/all，与网站 transactions 同规则）"""
    status = request.GET.get('status', 'on_sale')
    user = request.wx_user
    if status == 'on_sale':
        qs = Goods.objects.filter(seller=user, status='on_sale').order_by('-created_at')
    elif status == 'sold':
        qs = Goods.objects.filter(seller=user, status='sold').order_by('-updated_at')
    elif status == 'offline':
        qs = Goods.objects.filter(seller=user, status='offline').order_by('-updated_at')
    else:
        qs = Goods.objects.filter(seller=user).order_by('-created_at')
    return OK(goods=[S.goods_card(g, request) for g in qs])


@csrf_exempt
@wx_login_required
@require_GET
def my_trades(request):
    """我买到的（作为买家的交易会话，与网站 transactions tab=trade 同规则）"""
    status = request.GET.get('status', 'trading')
    user = request.wx_user
    all_convs = Conversation.objects.filter(buyer=user).select_related('goods', 'seller')
    if status == 'trading':
        convs = all_convs.filter(status__in=['trading', 'confirmed'])
    elif status == 'completed':
        convs = all_convs.filter(status='completed')
    elif status == 'cancelled':
        convs = all_convs.filter(status='cancelled')
    else:
        convs = all_convs
    convs = convs.order_by('-updated_at')
    return OK(conversations=[S.conversation_brief(c, request, user.id) for c in convs])


@csrf_exempt
@wx_login_required
@require_POST
def goods_update_status(request):
    """更新商品状态（下架时自动取消进行中会话，与网站同规则）"""
    data = _body(request)
    goods_id = data.get('goods_id')
    status = data.get('status')
    goods = get_object_or_404(Goods, id=goods_id, seller=request.wx_user)

    if status not in ('on_sale', 'sold', 'offline'):
        return ERR('无效的状态')

    goods.status = status
    if status == 'offline':
        active_convs = Conversation.objects.filter(
            goods=goods, status__in=['trading', 'confirmed']
        )
        for conv in active_convs:
            conv.status = 'cancelled'
            conv.buyer_confirmed = False
            conv.seller_confirmed = False
            conv.last_message = '商品已下架，交易取消'
            conv.save(update_fields=['status', 'buyer_confirmed', 'seller_confirmed', 'last_message'])

    goods.save()
    return OK(msg='操作成功')


@csrf_exempt
@wx_login_required
@require_POST
def goods_toggle_repeat(request):
    """切换允许重复售卖（与网站 toggle_repeat 同规则）"""
    data = _body(request)
    goods_id = data.get('goods_id')
    allow_repeat = bool(data.get('allow_repeat'))
    goods = get_object_or_404(Goods, id=goods_id, seller=request.wx_user)
    goods.allow_repeat = allow_repeat
    if not allow_repeat and goods.status == 'on_sale':
        if goods.conversations.filter(status='completed').exists():
            goods.status = 'sold'
    goods.save()
    return OK(allow_repeat=goods.allow_repeat, status=goods.status)


# ============================================================
# 聊天（需登录）：会话列表 / 发起 / 拉消息 / 发送 / 确认 / 收货 / 取消
# ============================================================

def _conv_allowed(conv, user):
    return conv.buyer_id == user.id or conv.seller_id == user.id


def _clear_unread(conv, user):
    if conv.buyer_id == user.id and conv.buyer_unread:
        conv.buyer_unread = 0
        conv.save(update_fields=['buyer_unread'])
    elif conv.seller_id == user.id and conv.seller_unread:
        conv.seller_unread = 0
        conv.save(update_fields=['seller_unread'])


@csrf_exempt
@wx_login_required
@require_GET
def chat_list(request):
    """我的会话列表（买卖双方）"""
    user = request.wx_user
    convs = Conversation.objects.filter(
        Q(buyer=user) | Q(seller=user)
    ).select_related('goods', 'buyer', 'seller')
    total_unread = sum(
        (c.buyer_unread if c.buyer_id == user.id else c.seller_unread) or 0 for c in convs
    )
    return OK(
        conversations=[S.conversation_brief(c, request, user.id) for c in convs],
        unread_total=total_unread,
    )


@csrf_exempt
@wx_login_required
@require_POST
def chat_start(request):
    """发起会话（创建或复用进行中的会话，含开场消息，与网站同规则）"""
    data = _body(request)
    goods_id = data.get('goods_id')
    goods = get_object_or_404(Goods, id=goods_id)

    if goods.seller_id == request.wx_user.id:
        return ERR('不能和自己交易')
    if goods.status != 'on_sale':
        return ERR('该商品当前不可交易')

    conv = Conversation.objects.filter(
        goods=goods, buyer=request.wx_user, status__in=['trading', 'confirmed']
    ).first()
    if not conv:
        conv = Conversation.objects.create(
            goods=goods, buyer=request.wx_user, seller=goods.seller
        )
        msg = Message.objects.create(
            conversation=conv,
            sender=request.wx_user,
            msg_type='text',
            content=f'你好，我看上了你的「{goods.title}」，请问还在卖吗？'
        )
        conv.last_message = msg.content[:50]
        conv.last_message_at = msg.created_at
        conv.save(update_fields=['last_message', 'last_message_at'])

    return OK(conv_id=conv.id)


@csrf_exempt
@wx_login_required
@require_GET
def chat_messages(request):
    """拉取消息（轮询，与网站 api_messages 字段一致）
    - 无 after_id：返回全部（作为本地记录种子）
    - 有 after_id：增量
    """
    conv_id = request.GET.get('conversation_id')
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _conv_allowed(conv, request.wx_user):
        return ERR('无权访问', status=403)

    qs = Message.objects.filter(conversation=conv)
    after_id = request.GET.get('after_id')
    if after_id and str(after_id).isdigit():
        qs = qs.filter(id__gt=int(after_id))
    qs = qs.order_by('created_at', 'id')

    _clear_unread(conv, request.wx_user)

    my_confirmed = (conv.buyer_confirmed if conv.buyer_id == request.wx_user.id
                    else conv.seller_confirmed)
    other_confirmed = (conv.seller_confirmed if conv.buyer_id == request.wx_user.id
                       else conv.buyer_confirmed)

    goods = conv.goods
    gimg = goods.images.first()
    return OK(
        conversation_id=conv.id,
        status=conv.status,
        my_confirmed=my_confirmed,
        other_confirmed=other_confirmed,
        seller_has_qrcode=bool(conv.seller.payment_qrcode),
        qrcode_url=S.abs_url(request, conv.seller.payment_qrcode.url) if conv.seller.payment_qrcode else '',
        goods={
            'id': goods.id,
            'title': goods.title,
            'price': str(goods.price),
            'image': S.abs_url(request, gimg.image.url) if gimg else '',
            'status': goods.status,
            'allow_repeat': goods.allow_repeat,
        },
        messages=[S.message_brief(m, request, request.wx_user.id) for m in qs],
    )


@csrf_exempt
@wx_login_required
@require_POST
def chat_send(request):
    """发送消息（文字用 form-urlencoded；图片/视频用 multipart 文件），与网站同校验"""
    conv_id = request.POST.get('conversation_id')
    conv = get_object_or_404(Conversation, id=conv_id)
    if not _conv_allowed(conv, request.wx_user):
        return ERR('无权发送', status=403)
    if conv.status != 'trading':
        return ERR('交易已确定，无法再发消息')

    msg_type = request.POST.get('type', 'text')
    content = (request.POST.get('content') or '').strip()
    file = request.FILES.get('file')

    if msg_type == 'text':
        if not content:
            return ERR('消息内容不能为空')
        if len(content) > settings.MAX_MESSAGE_LENGTH:
            return ERR(f'消息内容不能超过{settings.MAX_MESSAGE_LENGTH}个字')
        is_safe, violations = check_content_safety(content)
        if not is_safe:
            return JsonResponse({
                'success': False,
                'msg': '消息中包含联系方式或违规内容，已被拦截：' + '、'.join(violations),
                'blocked': True,
            })

    if msg_type in ('image', 'video'):
        if not file:
            return ERR('请选择要发送的文件')
        if file.size > settings.MAX_MEDIA_SIZE:
            return ERR('文件过大，无法发送')
        if msg_type == 'image':
            is_valid, err = validate_image_file(file)
        else:
            is_valid, err = validate_video_file(file)
        if not is_valid:
            return ERR(err)

    msg = Message.objects.create(
        conversation=conv,
        sender=request.wx_user,
        msg_type=msg_type,
        content=content if msg_type == 'text' else '',
        file=file if msg_type in ('image', 'video') else None,
    )
    if msg.msg_type == 'text':
        conv.last_message = msg.content[:50]
    elif msg.msg_type == 'image':
        conv.last_message = '[图片]'
    else:
        conv.last_message = '[视频]'
    conv.last_message_at = msg.created_at
    conv.save(update_fields=['last_message', 'last_message_at'])

    if conv.buyer_id == request.wx_user.id:
        conv.seller_unread += 1
        conv.save(update_fields=['seller_unread'])
    else:
        conv.buyer_unread += 1
        conv.save(update_fields=['buyer_unread'])

    return OK(msg=S.message_brief(msg, request, request.wx_user.id))


@csrf_exempt
@wx_login_required
@require_POST
def chat_confirm(request):
    """双方确认交易（与网站 api_confirm 同规则）"""
    data = _body(request)
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if not _conv_allowed(conv, request.wx_user):
        return ERR('无权操作', status=403)
    if conv.status != 'trading':
        return ERR('交易状态已变化')

    if conv.buyer_id == request.wx_user.id:
        conv.buyer_confirmed = True
    else:
        conv.seller_confirmed = True
    conv.save(update_fields=['buyer_confirmed', 'seller_confirmed'])

    if conv.buyer_confirmed and conv.seller_confirmed:
        conv.status = 'confirmed'
        conv.save(update_fields=['status'])
        sys_msg = Message.objects.create(
            conversation=conv, sender=conv.seller, msg_type='text',
            content='【系统】买卖双方已确认交易，买家可扫描卖家收款码付款。'
        )
        conv.last_message = sys_msg.content[:50]
        conv.last_message_at = sys_msg.created_at
        conv.save(update_fields=['last_message', 'last_message_at'])

    my_confirmed = (conv.buyer_confirmed if conv.buyer_id == request.wx_user.id
                    else conv.seller_confirmed)
    other_confirmed = (conv.seller_confirmed if conv.buyer_id == request.wx_user.id
                       else conv.buyer_confirmed)
    return OK(status=conv.status, my_confirmed=my_confirmed, other_confirmed=other_confirmed)


@csrf_exempt
@wx_login_required
@require_POST
def chat_complete(request):
    """买家确认收货：交易完成，删除服务器聊天记录（与网站 api_complete 同规则）"""
    data = _body(request)
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if conv.buyer_id != request.wx_user.id:
        return ERR('只有买家可以确认收货', status=403)
    if conv.status != 'confirmed':
        return ERR('交易尚未确认，无法收货')

    conv.status = 'completed'
    conv.save(update_fields=['status'])

    goods = conv.goods
    if not goods.allow_repeat:
        goods.status = 'sold'
        goods.save(update_fields=['status'])

    for m in Message.objects.filter(conversation=conv):
        m.delete()
    conv.last_message = '交易已完成'
    conv.save(update_fields=['last_message'])

    return OK(msg='交易完成，服务器聊天记录已清除')


@csrf_exempt
@wx_login_required
@require_POST
def chat_cancel(request):
    """买家取消交易（与网站 api_cancel 同规则）"""
    data = _body(request)
    conv = get_object_or_404(Conversation, id=data.get('conversation_id'))
    if conv.buyer_id != request.wx_user.id:
        return ERR('只有买家可以取消交易', status=403)
    if conv.status not in ('trading', 'confirmed'):
        return ERR('当前状态无法取消交易')

    conv.status = 'cancelled'
    conv.buyer_confirmed = False
    conv.seller_confirmed = False
    conv.last_message = '交易已取消'
    conv.save(update_fields=['status', 'buyer_confirmed', 'seller_confirmed', 'last_message'])

    return OK(msg='交易已取消')
