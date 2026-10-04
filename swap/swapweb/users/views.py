"""
用户相关视图
"""
import random
import time
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from .models import User, VerifyCode
from .utils import check_content_safety, validate_image_file, build_verify_code_email
from .email_check import validate_email_syntax, check_email_deliverable

# 验证码最大错误尝试次数（达到后验证码作废，防暴破）
MAX_CODE_ATTEMPTS = 5
# 登录失败限速参数（同一账号+IP 15分钟内最多失败10次）
LOGIN_MAX_FAILURES = 10
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60


# ============ 页面视图 ============

@ensure_csrf_cookie
def login_page(request):
    """登录页面"""
    return render(request, 'users/login.html')


@ensure_csrf_cookie
def register_page(request):
    """注册页面"""
    return render(request, 'users/register.html')


def logout_view(request):
    """退出登录"""
    logout(request)
    return redirect('/users/login/')


@login_required
def profile_page(request):
    """个人中心页面"""
    return render(request, 'users/profile.html')


@login_required
def profile_edit_page(request):
    """编辑个人信息页面"""
    return render(request, 'users/profile_edit.html')


# ============ API 接口 ============

def _check_verify_code(email, code, purpose):
    """
    统一验证码校验，带错误尝试次数上限（防暴破）
    返回 (verify_code_obj或None, 错误消息)
    """
    latest_code = VerifyCode.objects.filter(
        email=email,
        purpose=purpose,
        is_used=False,
        created_at__gte=timezone.now() - timedelta(seconds=settings.VERIFY_CODE_EXPIRE_SECONDS)
    ).order_by('-created_at').first()

    if not latest_code:
        return None, '验证码已过期，请重新获取'

    if latest_code.attempts >= MAX_CODE_ATTEMPTS:
        latest_code.is_used = True
        latest_code.save(update_fields=['is_used'])
        return None, '验证码错误次数过多已作废，请重新获取'

    if latest_code.code != code:
        latest_code.attempts += 1
        remaining = MAX_CODE_ATTEMPTS - latest_code.attempts
        if remaining <= 0:
            latest_code.is_used = True
            latest_code.save(update_fields=['attempts', 'is_used'])
            return None, '验证码错误次数过多已作废，请重新获取'
        latest_code.save(update_fields=['attempts'])
        return None, f'验证码错误，请重新输入（还可尝试{remaining}次）'

    return latest_code, ''


def _record_login_failure(email, ip):
    """记录登录失败次数（15分钟滑动窗口）"""
    key = f'login_fail:{email}:{ip}'
    count = cache.get(key, 0) + 1
    cache.set(key, count, LOGIN_FAILURE_WINDOW_SECONDS)
    return count


def _login_is_throttled(email, ip):
    """登录失败次数是否已达上限"""
    return cache.get(f'login_fail:{email}:{ip}', 0) >= LOGIN_MAX_FAILURES


def _clear_login_failures(email, ip):
    """登录成功后清除失败计数"""
    cache.delete(f'login_fail:{email}:{ip}')

@require_POST
def check_email(request):
    """检查邮箱是否已注册"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'exists': False, 'msg': '请求格式错误'}, status=400)
    
    email = data.get('email', '').strip()
    
    if not email:
        return JsonResponse({'exists': False, 'msg': '邮箱不能为空'})
    
    try:
        exists = User.objects.filter(email=email).exists()
        return JsonResponse({'exists': exists})
    except Exception:
        # 对外返回通用提示，详细信息只写入日志
        import logging
        logger = logging.getLogger(__name__)
        logger.error("检查邮箱接口发生异常", exc_info=True)
        return JsonResponse({'exists': False, 'msg': '服务器繁忙，请稍后重试'}, status=500)





@require_POST
def send_verify_code(request):
    """发送邮箱验证码"""
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    purpose = data.get('purpose', 'login')  # login / register / reset
    
    # 验证邮箱格式（严格语法）
    if not validate_email_syntax(email):
        return JsonResponse({'success': False, 'msg': '请输入有效的邮箱地址'})

    # 注册时检查邮箱是否已存在
    if purpose == 'register':
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'msg': '该邮箱已注册，请直接登录'})
    # 登录/重置密码时检查邮箱是否存在
    elif purpose in ('login', 'reset'):
        if not User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'msg': '该邮箱未注册，请先注册'})
    
    # 检查60秒内是否已发送
    recent = VerifyCode.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=settings.VERIFY_CODE_RESEND_SECONDS)
    ).first()
    
    if recent:
        return JsonResponse({'success': False, 'msg': '验证码发送太频繁，请稍后再试'})

    # 校验邮箱真实可收信（DNS域名检查 + SMTP收件人探测，探测无法判定时放行）
    deliverable, deliver_err = check_email_deliverable(email)
    if deliverable is False:
        return JsonResponse({'success': False, 'msg': deliver_err})

    # 生成6位验证码
    code = ''.join(random.choices('0123456789', k=6))

    # 保存验证码
    VerifyCode.objects.create(email=email, code=code, purpose=purpose)

    # 后台线程发送邮件，接口立即返回（SMTP发信耗时数秒，同步发送会导致客户端超时）
    subject, text_msg, html_msg = build_verify_code_email(code)

    import logging
    import threading

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
            logger = logging.getLogger(__name__)
            logger.error(f"验证码邮件发送失败: {email}", exc_info=True)

    threading.Thread(target=_deliver, daemon=True).start()
    return JsonResponse({'success': True, 'msg': '验证码已发送'})


@require_POST
def register_api(request):
    """注册接口"""
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    code = data.get('code', '')
    
    # 基本验证
    if not email or '@' not in email:
        return JsonResponse({'success': False, 'msg': '请输入有效的邮箱地址'})
    
    if len(password) < 6:
        return JsonResponse({'success': False, 'msg': '密码至少6位'})
    
    if password != confirm_password:
        return JsonResponse({'success': False, 'msg': '两次密码输入不一致'})
    
    if User.objects.filter(email=email).exists():
        return JsonResponse({'success': False, 'msg': '该邮箱已注册'})

    # 验证验证码（带错误次数上限，防暴破）
    latest_code, code_err = _check_verify_code(email, code, 'register')
    if not latest_code:
        return JsonResponse({'success': False, 'msg': code_err})

    # 创建用户
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        nickname=f'用户{random.randint(1000, 9999)}',
    )

    # 标记验证码已使用
    latest_code.is_used = True
    latest_code.save()
    
    # 自动登录
    login(request, user)
    
    return JsonResponse({'success': True, 'msg': '注册成功'})


@require_POST
def login_api(request):
    """登录接口（邮箱+密码）"""
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or '@' not in email:
        return JsonResponse({'success': False, 'msg': '请输入有效的邮箱地址'})

    if not password:
        return JsonResponse({'success': False, 'msg': '请输入密码'})

    # 登录失败限速（同一账号+IP），防密码暴破
    ip = request.META.get('REMOTE_ADDR', '')
    if _login_is_throttled(email, ip):
        return JsonResponse({'success': False, 'msg': '失败次数过多，请15分钟后再试'}, status=429)

    # 检查用户是否存在
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        _record_login_failure(email, ip)
        return JsonResponse({'success': False, 'msg': '该邮箱未注册，请先注册'})

    # 校验密码
    if not user.check_password(password):
        _record_login_failure(email, ip)
        return JsonResponse({'success': False, 'msg': '邮箱或密码错误'})

    # 登录（勾选"记住登录"时保持14天，否则关闭浏览器即失效）
    login(request, user)
    if data.get('remember'):
        request.session.set_expiry(14 * 24 * 60 * 60)
    else:
        request.session.set_expiry(0)
    _clear_login_failures(email, ip)

    return JsonResponse({'success': True, 'msg': '登录成功'})


@require_POST
def reset_password_api(request):
    """重置密码接口（邮箱验证码验证 + 两次新密码）"""
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    code = data.get('code', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not email or '@' not in email:
        return JsonResponse({'success': False, 'msg': '请输入有效的邮箱地址'})

    if not code:
        return JsonResponse({'success': False, 'msg': '请输入验证码'})

    if len(new_password) < 6:
        return JsonResponse({'success': False, 'msg': '密码至少6位'})

    if new_password != confirm_password:
        return JsonResponse({'success': False, 'msg': '两次密码输入不一致'})

    # 检查用户是否存在
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'msg': '该邮箱未注册，请先注册'})

    # 验证验证码（带错误次数上限，防暴破）
    latest_code, code_err = _check_verify_code(email, code, 'reset')
    if not latest_code:
        return JsonResponse({'success': False, 'msg': code_err})

    # 重置密码
    user.set_password(new_password)
    user.save()

    # 标记验证码已使用
    latest_code.is_used = True
    latest_code.save()

    return JsonResponse({'success': True, 'msg': '密码重置成功，请使用新密码登录'})


@login_required
@require_POST
def update_profile(request):
    """更新个人信息"""
    data = json.loads(request.body)
    user = request.user
    
    nickname = data.get('nickname', '').strip()
    school = data.get('school', '').strip()
    phone = data.get('phone', '').strip()
    bio = data.get('bio', '').strip()
    
    # 内容安全检测
    all_text = f'{nickname} {school} {bio}'
    is_safe, violations = check_content_safety(all_text)
    if not is_safe:
        return JsonResponse({'success': False, 'msg': '内容包含违规信息：' + '、'.join(violations)})
    
    # 文本长度限制
    if len(nickname) > settings.MAX_NICKNAME_LENGTH:
        return JsonResponse({'success': False, 'msg': f'昵称不能超过{settings.MAX_NICKNAME_LENGTH}个字'})
    if len(school) > settings.MAX_SCHOOL_LENGTH:
        return JsonResponse({'success': False, 'msg': f'学校名称不能超过{settings.MAX_SCHOOL_LENGTH}个字'})
    if len(bio) > settings.MAX_TEXT_LENGTH:
        return JsonResponse({'success': False, 'msg': f'个人简介不能超过{settings.MAX_TEXT_LENGTH}个字'})
    
    if nickname:
        user.nickname = nickname
    if school:
        user.school = school
    if phone:
        user.phone = phone[:20]
    if bio:
        user.bio = bio
    
    user.save()
    
    return JsonResponse({'success': True, 'msg': '保存成功'})


@login_required
@require_POST
def upload_avatar(request):
    """上传头像"""
    user = request.user
    if 'avatar' in request.FILES:
        avatar = request.FILES['avatar']
        # 限制大小 20MB
        if avatar.size > 20 * 1024 * 1024:
            return JsonResponse({'success': False, 'msg': '图片大小不能超过20MB'})
        # 真实类型校验，拒绝伪装成图片的可执行文件
        is_valid, err = validate_image_file(avatar)
        if not is_valid:
            return JsonResponse({'success': False, 'msg': err})
        user.avatar = avatar
        user.save()
        return JsonResponse({'success': True, 'avatar_url': user.avatar.url})
    return JsonResponse({'success': False, 'msg': '请选择图片'})


@login_required
@require_POST
def upload_payment_qrcode(request):
    """上传收款码"""
    user = request.user
    if 'payment_qrcode' in request.FILES:
        qrcode = request.FILES['payment_qrcode']
        if qrcode.size > 20 * 1024 * 1024:
            return JsonResponse({'success': False, 'msg': '图片大小不能超过20MB'})
        # 真实类型校验，拒绝伪装成图片的可执行文件
        is_valid, err = validate_image_file(qrcode)
        if not is_valid:
            return JsonResponse({'success': False, 'msg': err})
        user.payment_qrcode = qrcode
        user.save()
        return JsonResponse({'success': True, 'payment_qrcode_url': user.payment_qrcode.url})
    return JsonResponse({'success': False, 'msg': '请选择图片'})


@login_required
@require_POST
def change_password(request):
    """修改密码（需验证旧密码，网页/小程序共用）"""
    # 兼容 JSON 与表单两种提交方式
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body or '{}')
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'success': False, 'msg': '请求格式错误'})
    else:
        data = request.POST

    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not old_password:
        return JsonResponse({'success': False, 'msg': '请输入当前密码'})
    if not request.user.check_password(old_password):
        return JsonResponse({'success': False, 'msg': '当前密码不正确'})
    if not new_password:
        return JsonResponse({'success': False, 'msg': '请输入新密码'})
    if len(new_password) < 6:
        return JsonResponse({'success': False, 'msg': '新密码至少6位'})
    if new_password != confirm_password:
        return JsonResponse({'success': False, 'msg': '两次输入的新密码不一致'})
    if new_password == old_password:
        return JsonResponse({'success': False, 'msg': '新密码不能与当前密码相同'})

    request.user.set_password(new_password)
    request.user.save()
    # 保持当前网页会话不因改密失效（小程序令牌不受影响）
    update_session_auth_hash(request, request.user)
    return JsonResponse({'success': True, 'msg': '密码修改成功'})
