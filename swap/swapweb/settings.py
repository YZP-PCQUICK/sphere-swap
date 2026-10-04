"""
Django settings for swapweb project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# 项目根目录（swapweb上一级，即swap目录）
PROJECT_ROOT = BASE_DIR.parent

# ============ 读取.env秘密配置 ============
def _load_env_file():
    """从项目根目录的.env文件加载环境变量（不覆盖已存在的系统环境变量）"""
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        return
    try:
        with open(env_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                # 去掉行尾注释
                if ' #' in value and not value.startswith(("'", '"')):
                    value = value.split(' #')[0].strip()
                # 去除成对引号
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError:
        pass

_load_env_file()

def _get_secret(name, fallback_random=False):
    """获取环境变量秘密值；缺失且允许时生成随机临时值（仅保证本地能启动）"""
    value = os.environ.get(name)
    if value:
        return value
    if fallback_random:
        from django.core.management.utils import get_random_string
        return get_random_string(50)
    return ''

# ============ .env加载结束 ============

# SECRET_KEY 从.env读取（SWAP_SECRET_KEY），缺失时生成随机临时值保证本地能启动
SECRET_KEY = _get_secret('SWAP_SECRET_KEY', fallback_random=True)

# SECURITY WARNING: don't run with debug turned on in production!
# 生产环境在 .env 中设置 SWAP_DEBUG=False
DEBUG = os.environ.get('SWAP_DEBUG', 'True').lower() != 'false'

ALLOWED_HOSTS = ['*']

# 生产域名（HTTPS 下的 POST 请求必须加入此列表，否则 CSRF 校验返回 403）
CSRF_TRUSTED_ORIGINS = ['https://swap.pcquick.cn', 'https://www.pcquick.cn']

# 生产环境加固：nginx 反代下让 Django 正确识别 https（scheme/CSRF/cookie 安全判定）
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if not DEBUG:
    # HTTPS-only 时 cookie 仅通过安全连接传输
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "swapweb.users",
    "swapweb.goods",
    "swapweb.chat",
    "swapweb.dashboard",
    "swapweb.wxapi",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "swapweb.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(os.path.dirname(__file__), 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "swapweb.wsgi.application"

# 点击劫持防护：仅允许同源页面嵌入 iframe（仍阻止第三方网站嵌入，安全性不变）
X_FRAME_OPTIONS = "SAMEORIGIN"

# Database - SQLite（默认路径）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR.parent / "data" / "db.sqlite3",
    }
}

# 自定义用户模型
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

# Internationalization
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(os.path.dirname(__file__), 'static')]

# Media files - 默认路径
MEDIA_ROOT = BASE_DIR.parent / "data" / "media"
MEDIA_URL = '/media/'

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 邮箱 SMTP 配置
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.qq.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = _get_secret('SWAP_EMAIL_USER')
EMAIL_HOST_PASSWORD = _get_secret('SWAP_EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = f'SWAP校园交易平台 <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else ''

# 验证码有效期（秒）
VERIFY_CODE_EXPIRE_SECONDS = 300
# 验证码重发间隔（秒）
VERIFY_CODE_RESEND_SECONDS = 60



# 登录后跳转
LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'

# 商品图片最大大小（字节）20MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024
# 商品最多图片数
MAX_IMAGES_PER_GOODS = 6

# 聊天附件最大大小（字节）50MB（图片/视频）
MAX_MEDIA_SIZE = 50 * 1024 * 1024

# 全局请求体最大大小（字节）60MB，防止恶意大体积请求
DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024

# 文本内容最大长度限制
MAX_TEXT_LENGTH = 5000          # 通用文本（商品描述等）
MAX_TITLE_LENGTH = 100          # 商品标题
MAX_MESSAGE_LENGTH = 2000       # 聊天消息
MAX_NICKNAME_LENGTH = 20        # 昵称
MAX_SCHOOL_LENGTH = 50          # 学校名称
