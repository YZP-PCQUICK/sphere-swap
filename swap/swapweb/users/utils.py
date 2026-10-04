"""
内容安全检测工具
检测联系方式（电话、微信、QQ等）和违禁内容
提供上传文件类型白名单校验（防存储型XSS）
"""
import re
from PIL import Image

# 联系方式正则
PHONE_PATTERNS = [
    # 手机号
    r'1[3-9]\d{9}',
    # 座机号（带区号或不带）
    r'\d{3,4}[-\s]?\d{7,8}',
    # 400电话
    r'400[-\s]?\d{3}[-\s]?\d{4}',
]

WECHAT_PATTERNS = [
    r'微信[：:]\s*\w+',
    r'wx[：:]\s*\w+',
    r'VX[：:]\s*\w+',
    r'加微\w*',
    r'微\s*信\s*号?[：:]?\s*\w+',
    r'威信[：:]\s*\w+',
]

QQ_PATTERNS = [
    r'QQ[：:]\s*\d{5,12}',
    r'qq[：:]\s*\d{5,12}',
    r'扣扣[：:]\s*\d{5,12}',
    r'企鹅[：:]\s*\d{5,12}',
]

# 违禁词（黄赌毒等）
FORBIDDEN_WORDS = [
    # 涉黄
    '色情', '黄片', '黄色', '淫', '嫖娼', '约炮', '一夜情', '援交',
    '裸聊', '裸照', '福利姬', '成人片',
    # 涉赌
    '赌博', '赌球', '网赌', '棋牌', '博彩', '彩票代打', '跑分',
    # 涉毒
    '毒品', '冰毒', '海洛因', '大麻', 'k粉', '摇头丸', '吸毒',
    # 其他违法
    '枪支', '弹药', '假币', '假证', '发票', '刷单', '诈骗',
    '代考', '代写', '外挂', '破解',
]

# 联系方式关键词（用于模糊匹配）
CONTACT_KEYWORDS = [
    '电话', '手机', '联系我', '联系方式', '加我', '私聊',
    '扣扣', '微信', 'vx', 'qq', '企鹅',
]


def detect_contact_info(text):
    """检测联系方式，返回检测到的违规项列表"""
    if not text:
        return []
    
    violations = []
    text_lower = text.lower()
    
    # 检测手机号
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append(f'检测到电话号码: {matches[0]}')
            break
    
    # 检测微信号
    for pattern in WECHAT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append('检测到微信联系方式')
            break
    
    # 检测QQ号
    for pattern in QQ_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append('检测到QQ联系方式')
            break
    
    return violations


def detect_forbidden_content(text):
    """检测违禁内容，返回检测到的违规项列表"""
    if not text:
        return []
    
    violations = []
    text_lower = text.lower()
    
    for word in FORBIDDEN_WORDS:
        if word in text_lower:
            violations.append(f'包含违禁词: {word}')
    
    return violations


def check_content_safety(text):
    """
    综合内容安全检测
    返回 (is_safe: bool, violations: list)
    """
    violations = []
    violations.extend(detect_contact_info(text))
    violations.extend(detect_forbidden_content(text))
    return (len(violations) == 0, violations)


# ============ 上传文件类型校验（防存储型XSS） ============

# 允许的图片扩展名与PIL格式对应
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_PIL_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}

# 允许的视频扩展名
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'm4v'}


def validate_image_file(file_obj):
    """
    校验上传文件是否为真实图片
    1. 扩展名白名单（拒绝svg/html等可执行类型）
    2. Pillow真实解码校验（伪造扩展名的文件、含恶意脚本的伪装文件均被拒绝）
    返回 (is_valid: bool, error_msg: str)
    """
    name = file_obj.name or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, '图片格式仅支持 JPG/PNG/GIF/WEBP'

    try:
        file_obj.seek(0)
    except Exception:
        pass

    try:
        img = Image.open(file_obj)
        img_format = (img.format or '').upper()
        if img_format not in ALLOWED_PIL_FORMATS:
            return False, '图片格式仅支持 JPG/PNG/GIF/WEBP'
        # 完整解码验证（检测恶意构造的图片）
        img.verify()
    except Exception:
        return False, '图片文件损坏或不是有效的图片'

    try:
        file_obj.seek(0)
    except Exception:
        pass
    return True, ''


def validate_video_file(file_obj):
    """
    校验上传文件是否为真实视频（扩展名白名单 + magic bytes嗅探）
    返回 (is_valid: bool, error_msg: str)
    """
    name = file_obj.name or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        return False, '视频格式仅支持 MP4/WEBM/MOV'

    try:
        file_obj.seek(0)
        header = file_obj.read(12)
        file_obj.seek(0)
    except Exception:
        return False, '文件读取失败'

    if len(header) < 12:
        return False, '视频文件无效'

    # MP4/MOV: 第4-8字节为 'ftyp'；WEBM: 0x1A45DFA3 开头
    is_mp4_mov = header[4:8] == b'ftyp'
    is_webm = header[:4] == b'\x1a\x45\xdf\xa3'
    if not (is_mp4_mov or is_webm):
        return False, '视频文件无效'

    return True, ''


def build_verify_code_email(code):
    """构造验证码邮件的主题、纯文本与 HTML 正文（网站/小程序共用）"""
    subject = 'SWAP校园交易平台 - 验证码'
    text = (
        f'【SWAP】您的验证码是：{code}\n'
        '该验证码5分钟内有效，请勿泄露给他人。\n'
        '如果您没有请求此验证码，请忽略本邮件。'
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F5F9FC;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F5F9FC;padding:32px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:420px;background-color:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(74,144,226,0.12);">
    <!-- 顶部品牌区 -->
    <tr><td style="background-color:#4A90E2;padding:32px 40px;text-align:center;">
      <span style="font-size:26px;font-weight:bold;color:#FFFFFF;letter-spacing:2px;">SWAP</span><br/>
      <span style="font-size:13px;color:rgba(255,255,255,0.85);">校园二手交易平台</span>
    </td></tr>
    <!-- 正文 -->
    <tr><td style="padding:36px 40px 8px;font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
      <p style="margin:0 0 8px;font-size:17px;font-weight:bold;color:#1F2937;">您正在验证身份</p>
      <p style="margin:0 0 24px;font-size:14px;color:#6B7280;line-height:1.7;">请输入以下验证码完成操作，验证码 <strong style="color:#4A90E2;">5 分钟</strong>内有效：</p>
      <!-- 验证码：点选即可复制 -->
      <div style="background-color:#F0F7FF;border:1px dashed #4A90E2;border-radius:12px;padding:20px 16px;text-align:center;">
        <span style="display:inline-block;font-family:Consolas,Menlo,monospace;font-size:34px;font-weight:bold;letter-spacing:10px;color:#1F2937;user-select:all;cursor:pointer;">{code}</span>
      </div>
      <p style="margin:12px 0 0;font-size:12px;color:#9CA3AF;text-align:center;">点击验证码即可选中，长按可复制</p>
    </td></tr>
    <!-- 安全提醒 -->
    <tr><td style="padding:24px 40px 36px;">
      <div style="background-color:#FFF8E6;border-radius:10px;padding:16px 18px;">
        <p style="margin:0 0 8px;font-size:13px;font-weight:bold;color:#B45309;">安全提醒</p>
        <p style="margin:0;font-size:12px;color:#92400E;line-height:1.9;">
          · SWAP 工作人员绝不会向您索取验证码<br/>
          · 请勿将验证码告知任何人，包括自称客服的人<br/>
          · 如果您没有请求此验证码，请忽略本邮件
        </p>
      </div>
    </td></tr>
    <!-- 底部 -->
    <tr><td style="padding:20px 40px;background-color:#FAFBFC;border-top:1px solid #F0F2F5;text-align:center;">
      <p style="margin:0;font-size:12px;color:#9CA3AF;">SWAP 校园交易平台 · 让闲置流转起来</p>
      <p style="margin:4px 0 0;font-size:12px;color:#9CA3AF;">swap.pcquick.cn · 本邮件由系统自动发送，请勿回复</p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""
    return subject, text, html


def build_contact_seller_email(goods_title, goods_url, buyer_name, buyer_contact):
    """构造「商品咨询」通知邮件的主题、纯文本与 HTML 正文（发往卖家注册邮箱）"""
    subject = 'SWAP校园交易平台 - 有人对您的商品感兴趣'
    text = (
        f'【SWAP】您好！有用户对您的商品「{goods_title}」表示了购买意向。\n'
        f'意向购买用户：{buyer_name}\n'
        f'联系方式：{buyer_contact}\n'
        f'商品链接：{goods_url}\n'
        '请登录 SWAP 查看会话详情并及时回复。'
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F5F9FC;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F5F9FC;padding:32px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:420px;background-color:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(74,144,226,0.12);">
    <!-- 顶部品牌区 -->
    <tr><td style="background-color:#4A90E2;padding:32px 40px;text-align:center;">
      <span style="font-size:26px;font-weight:bold;color:#FFFFFF;letter-spacing:2px;">SWAP</span><br/>
      <span style="font-size:13px;color:rgba(255,255,255,0.85);">校园二手交易平台</span>
    </td></tr>
    <!-- 正文 -->
    <tr><td style="padding:36px 40px 8px;font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;">
      <p style="margin:0 0 8px;font-size:17px;font-weight:bold;color:#1F2937;">您有新的商品咨询</p>
      <p style="margin:0 0 20px;font-size:14px;color:#6B7280;line-height:1.7;">有用户对您的商品表示了<strong style="color:#4A90E2;">购买意向</strong>，快登录 SWAP 查看会话并回复吧：</p>
      <!-- 商品信息 -->
      <div style="background-color:#F0F7FF;border:1px solid #D6E9FB;border-radius:12px;padding:18px 20px;">
        <p style="margin:0 0 6px;font-size:12px;color:#9CA3AF;">意向商品</p>
        <p style="margin:0 0 12px;font-size:15px;font-weight:bold;color:#1F2937;">{goods_title}</p>
        <a href="{goods_url}" style="display:inline-block;background-color:#4A90E2;color:#FFFFFF;font-size:13px;text-decoration:none;padding:8px 20px;border-radius:20px;">查看商品</a>
      </div>
      <!-- 意向用户信息 -->
      <div style="margin-top:14px;background-color:#FAFBFC;border:1px solid #F0F2F5;border-radius:12px;padding:16px 20px;">
        <p style="margin:0 0 6px;font-size:12px;color:#9CA3AF;">意向购买用户</p>
        <p style="margin:0;font-size:14px;color:#1F2937;">{buyer_name}</p>
        <p style="margin:2px 0 0;font-size:13px;color:#6B7280;">{buyer_contact}</p>
      </div>
    </td></tr>
    <!-- 温馨提醒 -->
    <tr><td style="padding:24px 40px 36px;">
      <div style="background-color:#FFF8E6;border-radius:10px;padding:16px 18px;">
        <p style="margin:0 0 8px;font-size:13px;font-weight:bold;color:#B45309;">温馨提醒</p>
        <p style="margin:0;font-size:12px;color:#92400E;line-height:1.9;">
          · 请在平台内完成沟通与交易，保障双方权益<br/>
          · 及时回复可以提升成交率哦<br/>
          · 请勿点击邮件以外的陌生链接
        </p>
      </div>
    </td></tr>
    <!-- 底部 -->
    <tr><td style="padding:20px 40px;background-color:#FAFBFC;border-top:1px solid #F0F2F5;text-align:center;">
      <p style="margin:0;font-size:12px;color:#9CA3AF;">SWAP 校园交易平台 · 让闲置流转起来</p>
      <p style="margin:4px 0 0;font-size:12px;color:#9CA3AF;">swap.pcquick.cn · 本邮件由系统自动发送，请勿回复</p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""
    return subject, text, html
