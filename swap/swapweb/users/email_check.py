"""
邮箱可送达性校验
1. 语法严格校验（本地部分/域名结构/TLD）
2. DNS MX 记录查询（原生 socket 实现，无第三方依赖；无 MX 时按 RFC 5321 回退 A 记录）
3. SMTP RCPT TO 收件人探测（尽力而为：无法判定时放行，由真实发送的同步错误兜底）
"""
import logging
import os
import re
import smtplib
import socket
import struct

from django.conf import settings

logger = logging.getLogger(__name__)

# 严格语法：local@domain.tld（local 不超过64字符，整体不超过254字符）
EMAIL_SYNTAX_RE = re.compile(r'^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$')

# 公共 DNS 解析服务器（依次尝试，可经 settings.EMAIL_DNS_SERVERS 覆盖）
DEFAULT_DNS_SERVERS = ['223.5.5.5', '119.29.29.29', '8.8.8.8']
DNS_TIMEOUT = 2
# 收件人探测必须快：接口是同步调用本探测，超时过长会导致客户端请求超时（云服务器常封25端口，会等满超时）
SMTP_PROBE_TIMEOUT = 3
SMTP_PROBE_MAX_HOSTS = 1

# RCPT TO 明确拒绝的 SMTP 状态码
RCPT_REFUSED_CODES = (550, 551, 553)

# 常见大厂邮箱域名：跳过可达性探测，加快验证码接口响应
COMMON_MAIL_DOMAINS = {
    'qq.com', 'foxmail.com', '163.com', '126.com', 'yeah.net',
    'gmail.com', 'outlook.com', 'hotmail.com', 'live.com',
    'sina.com', 'sina.cn', 'sohu.com', '139.com', '189.cn', 'aliyun.com',
}


def validate_email_syntax(email):
    """严格语法校验，返回 bool"""
    if not email or not isinstance(email, str) or len(email) > 254:
        return False
    if not EMAIL_SYNTAX_RE.match(email):
        return False
    local, domain = email.rsplit('@', 1)
    labels = domain.split('.')
    if any(not l or l.startswith('-') or l.endswith('-') for l in labels):
        return False
    if labels[-1].isdigit():
        return False
    if local.startswith('.') or local.endswith('.') or '..' in local:
        return False
    return True


# ============ 原生 DNS 查询（UDP 53） ============

def _build_query(name, qtype):
    parts = b''
    for label in name.split('.'):
        encoded = label.encode('ascii')
        parts += bytes([len(encoded)]) + encoded
    parts += b'\x00'
    return parts + struct.pack('>HH', qtype, 1)


def _read_name(data, offset):
    """读取（可能压缩的）域名，返回 (域名, 下一偏移)"""
    labels = []
    next_offset = None
    seen = set()
    while True:
        if offset in seen or offset >= len(data):
            break
        seen.add(offset)
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if next_offset is None:
                next_offset = offset + 2
            offset = struct.unpack('>H', data[offset:offset + 2])[0] & 0x3FFF
            continue
        offset += 1
        if length == 0:
            if next_offset is None:
                next_offset = offset
            break
        labels.append(data[offset:offset + length].decode('ascii', 'ignore'))
        offset += length
    return '.'.join(labels), next_offset if next_offset is not None else offset


def _parse_answers(data, ancount):
    """解析应答区的 MX/A 记录，返回 [(pref, host)]"""
    idx = 12
    _, idx = _read_name(data, idx)
    idx += 4  # 跳过 QTYPE/QCLASS
    records = []
    for _ in range(ancount):
        _, idx = _read_name(data, idx)
        rtype, _cls, _ttl, rdlen = struct.unpack('>HHIH', data[idx:idx + 10])
        idx += 10
        rdata = data[idx:idx + rdlen]
        if rtype == 15 and rdlen > 2:  # MX
            pref = struct.unpack('>H', rdata[:2])[0]
            exchange, _ = _read_name(data, idx + 2)
            records.append((pref, exchange))
        elif rtype == 1 and rdlen == 4:  # A
            records.append((0, socket.inet_ntoa(rdata)))
        idx += rdlen
    return records


def _dns_query(name, qtype):
    """
    返回记录列表；域名不存在(NXDOMAIN)返回 []；所有解析服务器不可用返回 None
    """
    servers = getattr(settings, 'EMAIL_DNS_SERVERS', None) or DEFAULT_DNS_SERVERS
    # DNS报文头12字节：ID(2) + Flags + QDCOUNT + ANCOUNT + NSCOUNT + ARCOUNT
    query = os.urandom(2) + struct.pack('>HHHHH', 0x0100, 1, 0, 0, 0) + _build_query(name, qtype)
    for server in servers:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(DNS_TIMEOUT)
            sock.sendto(query, (server, 53))
            data, _addr = sock.recvfrom(4096)
            if data[:2] != query[:2]:
                continue
            flags = struct.unpack('>H', data[2:4])[0]
            rcode = flags & 0x000F
            if rcode == 3:  # NXDOMAIN
                return []
            if rcode != 0:
                continue
            ancount = struct.unpack('>H', data[6:8])[0]
            return _parse_answers(data, ancount)
        except (socket.timeout, OSError):
            continue
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    return None


def get_mail_hosts(domain):
    """
    获取可投递主机列表
    返回: 主机列表；[] 表示域名不存在；None 表示 DNS 不可用（无法判定）
    """
    try:
        ascii_domain = domain.encode('idna').decode('ascii')
    except Exception:
        return []
    mx = _dns_query(ascii_domain, 15)
    if mx is None:
        return None
    if mx:
        hosts = [h for _, h in sorted(mx) if h]
        return hosts or None
    # 无 MX 记录，按 RFC 5321 回退查询 A 记录
    a = _dns_query(ascii_domain, 1)
    if a is None:
        return None
    return [ascii_domain] if a else []


# ============ SMTP 收件人探测（尽力而为） ============

def smtp_mailbox_exists(email, hosts):
    """
    通过 RCPT TO 探测收件箱是否存在
    返回: True 明确存在 / False 明确不存在 / None 无法判定（放行）
    仅在能建立连接且服务器给出明确拒绝时返回 False，避免误伤
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    helo_domain = from_email.rsplit('@', 1)[-1] if '@' in from_email else 'localhost'
    if not hosts:
        return None
    for host in hosts[:SMTP_PROBE_MAX_HOSTS]:
        try:
            with smtplib.SMTP(host, 25, timeout=SMTP_PROBE_TIMEOUT) as smtp:
                code, _ = smtp.ehlo(helo_domain)
                if code >= 400:
                    continue
                code, _ = smtp.docmd('MAIL', 'FROM:<>')
                if code != 250:
                    return None
                code, _ = smtp.docmd('RCPT', 'TO:<%s>' % email)
                if code in (250, 251):
                    return True
                if code in RCPT_REFUSED_CODES:
                    return False
                return None  # 4xx 临时拒绝等，不判定
        except (smtplib.SMTPException, OSError) as e:
            logger.info('SMTP收件人探测未成功 host=%s: %s', host, e)
            continue
    return None


def check_email_deliverable(email):
    """
    校验邮箱是否真实存在且可接收邮件
    返回 (deliverable, msg):
      - (False, msg): 校验不通过，应拒绝发送
      - (True, ''): 通过或无法判定（放行，由真实发送兜底）
    """
    if not validate_email_syntax(email):
        return False, '请输入有效的邮箱地址'

    domain = email.rsplit('@', 1)[1]

    # 大厂邮箱域名跳过探测（探测耗时数秒且绝无意义），由真实发送结果兜底
    if domain.lower() in COMMON_MAIL_DOMAINS:
        return True, ''

    hosts = get_mail_hosts(domain)
    if hosts == []:
        return False, '该邮箱域名不存在或无法接收邮件'
    if hosts is None:
        # DNS 全部不可用时不拦截，交由真实发送结果兜底
        logger.warning('DNS解析不可用，跳过邮箱可送达性校验: %s', email)
        return True, ''

    probe = smtp_mailbox_exists(email, hosts)
    if probe is False:
        return False, '该邮箱不存在或无法接收邮件'
    return True, ''
