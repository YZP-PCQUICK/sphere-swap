from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.utils import timezone
from django.core.files.base import ContentFile
from datetime import date, timedelta
import hmac
import os
from PIL import Image as PILImage
from swapweb.users.models import User
from swapweb.goods.models import Goods, Ad, AdSlot, AD_DAILY_LIMIT, cleanup_expired_ads, get_ad_day_counts
from swapweb.users.utils import validate_image_file
from swapweb.chat.models import Conversation, Message

# 后台管理的TOKEN从.env环境变量读取（位于项目根目录，已被.gitignore排除）
DASHBOARD_TOKEN = os.environ.get('SWAP_DASHBOARD_TOKEN', '')

def dashboard_login_required(view_func):
    """装饰器：验证用户是否已登录后台管理"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('dashboard_authenticated', False):
            return redirect('dashboard:login')
        return view_func(request, *args, **kwargs)
    return wrapper

def login(request):
    """后台登录页面，验证TOKEN"""
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        # 恒定时间比较，防止时序侧信道
        if DASHBOARD_TOKEN and hmac.compare_digest(token, DASHBOARD_TOKEN):
            request.session['dashboard_authenticated'] = True
            request.session.set_expiry(3600)  # 1小时过期
            return redirect('dashboard:index')
        else:
            return render(request, 'dashboard/login.html', {'error': '无效的TOKEN，请重试'})
    return render(request, 'dashboard/login.html')

@dashboard_login_required
def logout(request):
    """后台登出"""
    if 'dashboard_authenticated' in request.session:
        del request.session['dashboard_authenticated']
    return redirect('dashboard:login')

@dashboard_login_required
def index(request):
    """后台管理首页，展示统计数据"""
    # 用户统计
    total_users = User.objects.count()
    recent_users = User.objects.order_by('-date_joined')[:5]
    
    # 商品统计
    total_goods = Goods.objects.count()
    total_published_goods = Goods.objects.filter(is_active=True).count() if hasattr(Goods._meta, 'is_active') else Goods.objects.count()
    recent_goods = Goods.objects.order_by('-created_at')[:5]
    
    # 交易会话统计
    total_conversations = Conversation.objects.count()
    completed_trades = Conversation.objects.filter(status='completed').count()
    active_trades = Conversation.objects.filter(status__in=['trading', 'confirmed']).count()
    recent_trades = Conversation.objects.order_by('-updated_at')[:5]

    context = {
        'total_users': total_users,
        'recent_users': recent_users,
        'total_goods': total_goods,
        'total_published_goods': total_published_goods,
        'recent_goods': recent_goods,
        'total_conversations': total_conversations,
        'completed_trades': completed_trades,
        'active_trades': active_trades,
        'recent_trades': recent_trades,
    }
    return render(request, 'dashboard/index.html', context)

@dashboard_login_required
def user_list(request):
    """用户列表页面"""
    users_queryset = User.objects.all().order_by('-date_joined')
    # 分页
    paginator = Paginator(users_queryset, 10)
    page = request.GET.get('page')
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)
    
    context = {
        'users': users_page,
    }
    return render(request, 'dashboard/user_list.html', context)

@dashboard_login_required
def user_detail(request, user_id):
    """用户详情页面"""
    user = get_object_or_404(User, id=user_id)
    # 用户发布的商品
    user_goods = Goods.objects.filter(seller=user).order_by('-created_at')[:10]
    # 用户参与的会话
    user_conversations = Conversation.objects.filter(buyer=user) | Conversation.objects.filter(seller=user)
    user_conversations = user_conversations.order_by('-updated_at')[:10]
    
    context = {
        'user': user,
        'user_goods': user_goods,
        'user_conversations': user_conversations,
    }
    return render(request, 'dashboard/user_detail.html', context)

@dashboard_login_required
def goods_list(request):
    """商品列表页面"""
    goods_queryset = Goods.objects.all().order_by('-created_at')
    # 分页
    paginator = Paginator(goods_queryset, 10)
    page = request.GET.get('page')
    try:
        goods_page = paginator.page(page)
    except PageNotAnInteger:
        goods_page = paginator.page(1)
    except EmptyPage:
        goods_page = paginator.page(paginator.num_pages)
    
    context = {
        'goods': goods_page,
    }
    return render(request, 'dashboard/goods_list.html', context)

@dashboard_login_required
def goods_detail(request, goods_id):
    """商品详情页面"""
    good = get_object_or_404(Goods, id=goods_id)
    context = {
        'good': good,
    }
    return render(request, 'dashboard/goods_detail.html', context)

@dashboard_login_required
def conversation_list(request):
    """交易会话列表页面"""
    conv_queryset = Conversation.objects.all().order_by('-updated_at')
    # 分页
    paginator = Paginator(conv_queryset, 10)
    page = request.GET.get('page')
    try:
        conv_page = paginator.page(page)
    except PageNotAnInteger:
        conv_page = paginator.page(1)
    except EmptyPage:
        conv_page = paginator.page(paginator.num_pages)
    
    context = {
        'conversations': conv_page,
    }
    return render(request, 'dashboard/conversation_list.html', context)

@dashboard_login_required
def conversation_detail(request, conv_id):
    """交易会话详情页面"""
    conversation = get_object_or_404(Conversation, id=conv_id)
    messages = Message.objects.filter(conversation=conversation).order_by('created_at')

    context = {
        'conversation': conversation,
        'messages': messages,
    }
    return render(request, 'dashboard/conversation_detail.html', context)


# ============ 广告管理 ============

def _compress_ad_image(file_obj):
    """
    压缩广告图片：最长边限制1600px，统一转JPEG质量85
    返回 (ContentFile, 新文件名)；失败返回 (None, 错误信息)
    """
    try:
        file_obj.seek(0)
        img = PILImage.open(file_obj)
        img.load()
    except Exception:
        return None, '图片文件损坏或不是有效的图片'

    # GIF/WebP 动图取第一帧并转为静态图
    if getattr(img, 'is_animated', False):
        img.seek(0)

    if img.mode != 'RGB':
        img = img.convert('RGB')

    img.thumbnail((1600, 1600), PILImage.LANCZOS)

    import io
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read()), ''


@dashboard_login_required
def ad_list(request):
    """广告管理页面：广告列表 + 每日投放数量统计"""
    cleanup_expired_ads()  # 清理投放已结束的广告及媒体文件
    today = timezone.localdate()
    ads = Ad.objects.all().order_by('-priority', 'id')

    # 统计当日（今天 ~ 一年后）每日广告数量
    counts = get_ad_day_counts(today, today + timedelta(days=365))

    context = {
        'ads': ads,
        'ad_counts': counts,
        'today': today.isoformat(),
        'ad_daily_limit': AD_DAILY_LIMIT,
    }
    return render(request, 'dashboard/ads.html', context)


@dashboard_login_required
def ad_create(request):
    """创建广告（图片上传 + 链接 + 投放日期区间 + 优先级）"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'msg': '请求方式错误'}, status=405)

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'success': False, 'msg': '请上传广告图片'})

    ok, err = validate_image_file(image_file)
    if not ok:
        return JsonResponse({'success': False, 'msg': err})

    link = (request.POST.get('link') or '').strip()
    if link and not link.startswith(('http://', 'https://')):
        return JsonResponse({'success': False, 'msg': '链接必须以 http:// 或 https:// 开头'})
    if len(link) > 500:
        return JsonResponse({'success': False, 'msg': '链接过长（最多500字）'})

    # 多选投放日期：逗号分隔的 ISO 日期字符串
    raw_dates = (request.POST.get('dates') or '').strip()
    if not raw_dates:
        return JsonResponse({'success': False, 'msg': '请在日历上选择至少一个投放日期'})

    today = timezone.localdate()
    try:
        dates = sorted({date.fromisoformat(d.strip()) for d in raw_dates.split(',') if d.strip()})
    except ValueError:
        return JsonResponse({'success': False, 'msg': '投放日期格式不正确'})

    if dates[0] < today:
        return JsonResponse({'success': False, 'msg': '投放日期不能早于今天'})
    if dates[-1] > today + timedelta(days=365):
        return JsonResponse({'success': False, 'msg': '投放日期最多可设置到一年后'})

    try:
        priority = int(request.POST.get('priority') or 0)
    except ValueError:
        return JsonResponse({'success': False, 'msg': '优先级必须是数字'})

    # 单日投放上限校验：每个选中日期都不能超过上限
    counts = get_ad_day_counts(dates[0], dates[-1])
    for d in dates:
        key = d.isoformat()
        if counts.get(key, 0) >= AD_DAILY_LIMIT:
            return JsonResponse({'success': False, 'msg': f'{key} 已有 {counts[key]} 个广告，达到单日上限 {AD_DAILY_LIMIT} 个，请选择其他日期'})

    content, err = _compress_ad_image(image_file)
    if content is None:
        return JsonResponse({'success': False, 'msg': err})

    name = image_file.name.rsplit('.', 1)[0][:50] or 'ad'
    ad = Ad(link=link, priority=priority)
    ad.image.save(f'{name}.jpg', content, save=True)
    AdSlot.objects.bulk_create([AdSlot(ad=ad, date=d) for d in dates])

    return JsonResponse({'success': True, 'msg': '广告创建成功'})


@dashboard_login_required
def ad_delete(request, ad_id):
    """删除广告（记录 + 媒体文件）"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'msg': '请求方式错误'}, status=405)
    ad = get_object_or_404(Ad, id=ad_id)
    ad.delete()  # 模型 delete 已同步删除图片文件
    return JsonResponse({'success': True, 'msg': '广告已删除'})
