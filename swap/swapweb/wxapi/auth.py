"""
小程序 Token 认证
- 请求头 Authorization: Token <key>（也接受 X-WX-Token）
- wx_login_required 装饰器：未带有效令牌返回 401 JSON
"""
import functools

from .models import WxToken


def get_token_key(request):
    """从请求头提取令牌字符串"""
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.lower().startswith('token '):
        return auth[6:].strip()
    return (request.META.get('HTTP_X_WX_TOKEN') or '').strip()


def get_token_user(request):
    """根据令牌返回用户，无效返回 None"""
    key = get_token_key(request)
    if not key:
        return None
    token = WxToken.objects.select_related('user').filter(key=key).first()
    if not token:
        return None
    # 触发 last_used_at 更新（auto_now）
    token.save(update_fields=['last_used_at'])
    return token.user


def wx_login_required(view):
    """小程序接口登录校验装饰器（替代 session 的 login_required）"""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        user = get_token_user(request)
        if not user:
            return JsonResponse_unauthorized()
        request.wx_user = user
        return view(request, *args, **kwargs)
    return wrapper


def JsonResponse_unauthorized():
    from django.http import JsonResponse
    return JsonResponse({'success': False, 'msg': '请先登录', 'need_login': True}, status=401)
