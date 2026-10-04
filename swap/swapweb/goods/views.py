"""
商品相关视图
"""
import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Goods, GoodsImage, Favorite, CATEGORY_CHOICES, Ad, cleanup_expired_ads
from swapweb.users.utils import check_content_safety, validate_image_file
from swapweb.chat.models import Conversation


@require_GET
def ads_today(request):
    """首页广告栏 API：返回当日投放的广告列表（按优先级、上传顺序排序）"""
    cleanup_expired_ads()  # 自动清理投放已结束的广告及媒体文件
    today = timezone.localdate()
    ads = Ad.objects.filter(dates__date=today).distinct()
    return JsonResponse({
        'success': True,
        'ads': [
            {
                'id': ad.id,
                'image': request.build_absolute_uri(ad.image.url),
                'link': ad.link or '',
            }
            for ad in ads
        ],
    })


def index(request):
    """首页"""
    # 获取最新商品
    goods_list = Goods.objects.filter(status='on_sale').order_by('-created_at')[:20]
    # 获取分类
    categories = CATEGORY_CHOICES
    return render(request, 'goods/index.html', {
        'goods_list': goods_list,
        'categories': categories,
    })


def about(request):
    """关于我们页面"""
    return render(request, 'goods/about.html', {})


def goods_list(request):
    """商品列表页（搜索/筛选）"""
    queryset = Goods.objects.filter(status='on_sale')
    
    # 搜索关键词
    keyword = request.GET.get('keyword', '').strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword) | 
            Q(description__icontains=keyword) |
            Q(sub_category__icontains=keyword)
        )
    
    # 大分类筛选
    category = request.GET.get('category', '')
    if category:
        queryset = queryset.filter(category=category)
    
    # 小分类筛选
    sub_category = request.GET.get('sub_category', '').strip()
    if sub_category:
        queryset = queryset.filter(sub_category__icontains=sub_category)
    
    # 学校筛选
    school = request.GET.get('school', '').strip()
    if school:
        queryset = queryset.filter(school__icontains=school)
    
    # 交易方式筛选
    trade_type = request.GET.get('trade_type', '')
    if trade_type:
        queryset = queryset.filter(trade_type=trade_type)
    
    # 价格区间
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    if min_price:
        queryset = queryset.filter(price__gte=float(min_price))
    if max_price:
        queryset = queryset.filter(price__lte=float(max_price))
    
    # 排序
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        queryset = queryset.order_by('price')
    elif sort == 'price_desc':
        queryset = queryset.order_by('-price')
    elif sort == 'views':
        queryset = queryset.order_by('-views')
    else:
        queryset = queryset.order_by('-created_at')
    
    # 分页
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page)
    
    categories = CATEGORY_CHOICES
    
    return render(request, 'goods/list.html', {
        'goods_list': page_obj,
        'categories': categories,
        'keyword': keyword,
        'category': category,
        'sub_category': sub_category,
        'school': school,
        'trade_type': trade_type,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
    })


def goods_detail(request, goods_id):
    """商品详情页"""
    goods = get_object_or_404(Goods, id=goods_id)
    
    # 增加浏览量
    goods.views += 1
    goods.save(update_fields=['views'])
    
    # 是否收藏
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(user=request.user, goods=goods).exists()
    
    # 卖家其他商品
    seller_other = Goods.objects.filter(
        seller=goods.seller, status='on_sale'
    ).exclude(id=goods.id)[:6]
    
    return render(request, 'goods/detail.html', {
        'goods': goods,
        'is_favorited': is_favorited,
        'seller_other': seller_other,
    })


@login_required
def publish_page(request):
    """发布商品页面"""
    categories = CATEGORY_CHOICES
    return render(request, 'goods/publish.html', {
        'categories': categories,
    })


@login_required
@require_POST
def publish_goods(request):
    """发布商品接口"""
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    price = request.POST.get('price', '')
    original_price = request.POST.get('original_price', '')
    category = request.POST.get('category', '')
    sub_category = request.POST.get('sub_category', '').strip()
    trade_type = request.POST.get('trade_type', 'pickup')
    school = request.POST.get('school', '').strip()
    allow_repeat = request.POST.get('allow_repeat', '0') == '1'
    
    # 必填验证
    if not title:
        return JsonResponse({'success': False, 'msg': '请输入商品名称'})
    if not price:
        return JsonResponse({'success': False, 'msg': '请输入商品价格'})
    if not category:
        return JsonResponse({'success': False, 'msg': '请选择商品分类'})
    if not school:
        return JsonResponse({'success': False, 'msg': '请输入学校名称'})
    
    # 小分类长度限制
    if len(sub_category) > 20:
        return JsonResponse({'success': False, 'msg': '小分类不能超过20个字'})
    
    # 文本长度限制
    if len(title) > settings.MAX_TITLE_LENGTH:
        return JsonResponse({'success': False, 'msg': f'商品名称不能超过{settings.MAX_TITLE_LENGTH}个字'})
    if len(description) > settings.MAX_TEXT_LENGTH:
        return JsonResponse({'success': False, 'msg': f'商品描述不能超过{settings.MAX_TEXT_LENGTH}个字'})
    if len(school) > settings.MAX_SCHOOL_LENGTH:
        return JsonResponse({'success': False, 'msg': f'学校名称不能超过{settings.MAX_SCHOOL_LENGTH}个字'})
    
    # 内容安全检测
    all_text = f'{title} {description} {sub_category} {school}'
    is_safe, violations = check_content_safety(all_text)
    if not is_safe:
        return JsonResponse({'success': False, 'msg': '内容包含违规信息：' + '、'.join(violations)})
    
    # 图片处理
    images = request.FILES.getlist('images')
    if len(images) == 0:
        return JsonResponse({'success': False, 'msg': '请至少上传一张商品图片'})
    if len(images) > settings.MAX_IMAGES_PER_GOODS:
        return JsonResponse({'success': False, 'msg': f'最多上传{settings.MAX_IMAGES_PER_GOODS}张图片'})
    
    # 检查每张图片大小与真实类型
    for idx, img in enumerate(images):
        if img.size > settings.MAX_IMAGE_SIZE:
            return JsonResponse({'success': False, 'msg': f'第{idx+1}张图片过大，请压缩后重新上传'})
        is_valid, err = validate_image_file(img)
        if not is_valid:
            return JsonResponse({'success': False, 'msg': f'第{idx+1}张图片无效：{err}'})
    
    try:
        price_val = float(price)
        if price_val < 0:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'msg': '价格格式不正确'})
    
    original_price_val = None
    if original_price:
        try:
            original_price_val = float(original_price)
        except (ValueError, TypeError):
            pass
    
    # 创建商品
    goods = Goods.objects.create(
        seller=request.user,
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
    
    # 保存图片
    for idx, img in enumerate(images):
        GoodsImage.objects.create(
            goods=goods,
            image=img,
            sort=idx,
        )
    
    return JsonResponse({'success': True, 'msg': '发布成功', 'goods_id': goods.id})


@login_required
@require_POST
def toggle_favorite(request):
    """收藏/取消收藏"""
    data = json.loads(request.body)
    goods_id = data.get('goods_id')
    
    goods = get_object_or_404(Goods, id=goods_id)
    fav, created = Favorite.objects.get_or_create(
        user=request.user,
        goods=goods,
    )
    
    if not created:
        fav.delete()
        goods.favorites = max(0, goods.favorites - 1)
        is_favorited = False
    else:
        goods.favorites += 1
        is_favorited = True
    
    goods.save(update_fields=['favorites'])
    
    return JsonResponse({'success': True, 'is_favorited': is_favorited})


@login_required
def transactions(request):
    """交易信息（包含我发布的商品 + 我的交易会话）"""
    tab = request.GET.get('tab', 'goods')  # goods=我发布的，trade=我的交易
    status = request.GET.get('status', 'on_sale')
    user = request.user

    # 我发布的商品
    goods_list = []
    # 我的交易会话
    conversations = []

    if tab == 'goods':
        # 商品状态子分类
        if status == 'on_sale':
            goods_list = Goods.objects.filter(seller=user, status='on_sale').order_by('-created_at')
        elif status == 'sold':
            goods_list = Goods.objects.filter(seller=user, status='sold').order_by('-updated_at')
        elif status == 'offline':
            goods_list = Goods.objects.filter(seller=user, status='offline').order_by('-updated_at')
        else:
            goods_list = Goods.objects.filter(seller=user).order_by('-created_at')

    elif tab == 'trade':
        # 交易会话：只显示作为买家的交易（卖家的在"我发布的"里管理）
        all_convs = Conversation.objects.filter(buyer=user)
        if status == 'trading':
            convs = all_convs.filter(status__in=['trading', 'confirmed'])
        elif status == 'completed':
            convs = all_convs.filter(status='completed')
        elif status == 'cancelled':
            convs = all_convs.filter(status='cancelled')
        else:
            convs = all_convs
        conversations = convs.select_related('goods', 'seller').order_by('-updated_at')

    return render(request, 'goods/transactions.html', {
        'tab': tab,
        'status': status,
        'goods_list': goods_list,
        'conversations': conversations,
    })


@login_required
@require_POST
def update_goods_status(request):
    """更新商品状态（下架/售出/重新上架）"""
    data = json.loads(request.body)
    goods_id = data.get('goods_id')
    status = data.get('status')
    
    goods = get_object_or_404(Goods, id=goods_id, seller=request.user)
    
    if status in ['on_sale', 'sold', 'offline']:
        goods.status = status

        # 下架商品时，自动取消所有进行中的交易会话
        if status == 'offline':
            from swapweb.chat.models import Conversation
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
        return JsonResponse({'success': True, 'msg': '操作成功'})
    
    return JsonResponse({'success': False, 'msg': '无效的状态'})


@login_required
@require_POST
def toggle_repeat(request):
    """切换商品是否允许重复售卖"""
    data = json.loads(request.body or '{}')
    goods_id = data.get('goods_id')
    allow_repeat = data.get('allow_repeat', False)

    goods = get_object_or_404(Goods, id=goods_id, seller=request.user)
    goods.allow_repeat = bool(allow_repeat)

    # 关闭重复售卖时，如果已有完成的交易，则自动将商品标记为已售出
    if not allow_repeat and goods.status == 'on_sale':
        has_completed = goods.conversations.filter(status='completed').exists()
        if has_completed:
            goods.status = 'sold'

    goods.save()
    return JsonResponse({'success': True, 'allow_repeat': goods.allow_repeat, 'status': goods.status})


@login_required
def my_favorites(request):
    """我的收藏"""
    fav_list = Favorite.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'goods/my_favorites.html', {
        'fav_list': fav_list,
    })
