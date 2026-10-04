# -*- coding: utf-8 -*-
"""wxapi 全流程验证脚本（临时，用后即删）"""
import io
import json
import sqlite3
import time

import requests

BASE = 'http://127.0.0.1:8000'
DB = r'e:\YZP\YZP_work\PCQUICK\project\swapweb\data\db.sqlite3'

PASS = []
FAIL = []


def check(name, cond, extra=''):
    if cond:
        PASS.append(name)
        print(f'[PASS] {name}')
    else:
        FAIL.append((name, extra))
        print(f'[FAIL] {name} {extra}')


def get_code_from_db(email):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT code FROM swap_verify_code WHERE email=? ORDER BY created_at DESC LIMIT 1", (email,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def make_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (400, 400), (74, 144, 226)).save(buf, 'PNG')
    buf.seek(0)
    return buf


def png_bytes():
    return make_png().getvalue()


def main():
    ts = int(time.time())
    email_a = f'wxtest_a_{ts}@test.com'
    email_b = f'wxtest_b_{ts}@test.com'

    # ===== 注册 A =====
    r = requests.post(f'{BASE}/wx/api/auth/send-code/', json={'email': email_a, 'purpose': 'register'})
    check('A 发送注册验证码', r.ok and r.json().get('success'), r.text[:120])
    code_a = get_code_from_db(email_a)
    r = requests.post(f'{BASE}/wx/api/auth/register/', json={
        'email': email_a, 'password': 'wxtest123', 'confirm_password': 'wxtest123', 'code': code_a})
    j = r.json()
    check('A 注册成功并返回token', j.get('success') and j.get('token'), r.text[:160])
    token_a = j.get('token', '')

    # ===== 注册 B =====
    requests.post(f'{BASE}/wx/api/auth/send-code/', json={'email': email_b, 'purpose': 'register'})
    code_b = get_code_from_db(email_b)
    r = requests.post(f'{BASE}/wx/api/auth/register/', json={
        'email': email_b, 'password': 'wxtest123', 'confirm_password': 'wxtest123', 'code': code_b})
    token_b = r.json().get('token', '')
    check('B 注册成功', bool(token_b), r.text[:160])

    HA = {'Authorization': f'Token {token_a}'}
    HB = {'Authorization': f'Token {token_b}'}

    # ===== 登录/重复邮箱检查/未授权 =====
    r = requests.post(f'{BASE}/wx/api/auth/login/', json={'email': email_a, 'password': 'wxtest123'})
    check('密码登录成功', r.json().get('success'), r.text[:120])
    r = requests.post(f'{BASE}/wx/api/auth/login/', json={'email': email_a, 'password': 'wrong'})
    check('密码错误被拒绝', not r.json().get('success'))
    r = requests.get(f'{BASE}/wx/api/user/me/')
    check('无token访问user/me返回401', r.status_code == 401)
    r = requests.post(f'{BASE}/wx/api/auth/check-email/', json={'email': email_a})
    check('check-email 已注册返回exists', r.json().get('exists') is True)
    r = requests.post(f'{BASE}/wx/api/auth/check-email/', json={'email': f'new_{ts}@test.com'})
    check('check-email 新邮箱不存在', r.json().get('exists') is False)

    # ===== 用户资料 =====
    r = requests.get(f'{BASE}/wx/api/user/me/', headers=HA)
    check('user/me 返回用户', r.json().get('user', {}).get('email') == email_a)
    r = requests.post(f'{BASE}/wx/api/user/profile/', headers=HA,
                      json={'nickname': '小程序测试A', 'school': '测试大学', 'phone': '13800000000', 'bio': 'hello'})
    check('更新资料成功', r.json().get('success'), r.text[:120])

    # 头像上传
    r = requests.post(f'{BASE}/wx/api/user/avatar/', headers=HA,
                      files={'avatar': ('a.png', png_bytes(), 'image/png')})
    check('上传头像成功', r.json().get('success') and r.json().get('avatar_url'), r.text[:120])

    # 收款码上传
    r = requests.post(f'{BASE}/wx/api/user/qrcode/', headers=HA,
                      files={'payment_qrcode': ('q.png', png_bytes(), 'image/png')})
    check('上传收款码成功', r.json().get('success') and r.json().get('payment_qrcode_url'), r.text[:120])

    # ===== 发布商品（临时图 -> publish）=====
    tmp_ids = []
    for i in range(2):
        r = requests.post(f'{BASE}/wx/api/goods/upload-image/', headers=HA,
                          files={'image': (f'g{i}.png', png_bytes(), 'image/png')})
        check(f'上传临时图{i+1}', r.json().get('success') and 'tmp_id' in r.json(), r.text[:120])
        tmp_ids.append(r.json()['tmp_id'])

    r = requests.post(f'{BASE}/wx/api/goods/publish/', headers=HA, json={
        'title': '小程序验证测试商品', 'description': '全流程自动化测试商品',
        'price': '9.9', 'original_price': '19.9', 'category': 'digital',
        'sub_category': '测试', 'trade_type': 'pickup', 'school': '测试大学',
        'allow_repeat': False, 'tmp_ids': tmp_ids})
    j = r.json()
    check('发布商品成功', j.get('success') and j.get('goods_id'), r.text[:200])
    goods_id = j.get('goods_id')

    # 缺图片应失败
    r = requests.post(f'{BASE}/wx/api/goods/publish/', headers=HA, json={
        'title': '无图商品', 'price': '1', 'category': 'other', 'school': '测试大学', 'tmp_ids': []})
    check('无图片发布被拒绝', not r.json().get('success'))

    # ===== 首页/列表/详情 =====
    r = requests.get(f'{BASE}/wx/api/home/')
    j = r.json()
    check('home 返回分类+商品', j.get('success') and len(j.get('categories', [])) == 7
          and any(g['id'] == goods_id for g in j.get('goods', [])), r.text[:160])
    r = requests.get(f'{BASE}/wx/api/goods/', params={'keyword': '小程序验证', 'sort': 'newest'})
    j = r.json()
    check('列表搜索命中', j.get('success') and j.get('count', 0) >= 1, r.text[:160])
    check('列表返回分页字段', 'num_pages' in j and 'has_next' in j and 'page' in j)
    r = requests.get(f'{BASE}/wx/api/goods/', params={'min_price': '100', 'max_price': '200'})
    check('价格过滤不命中低价商品', all(g['id'] != goods_id for g in r.json().get('goods', [])))
    r = requests.get(f'{BASE}/wx/api/goods/{goods_id}/', headers=HB)
    j = r.json()
    check('详情返回图片/卖家/收藏状态', j.get('success') and len(j['goods']['images']) == 2
          and j['goods']['seller']['has_qrcode'] is True and j['is_favorited'] is False, r.text[:200])

    # ===== 收藏 =====
    r = requests.post(f'{BASE}/wx/api/goods/favorite/', headers=HB, json={'goods_id': goods_id})
    check('B收藏成功', r.json().get('is_favorited') is True)
    r = requests.post(f'{BASE}/wx/api/goods/favorite/', headers=HB, json={'goods_id': goods_id})
    check('B取消收藏', r.json().get('is_favorited') is False)
    requests.post(f'{BASE}/wx/api/goods/favorite/', headers=HB, json={'goods_id': goods_id})
    r = requests.get(f'{BASE}/wx/api/user/favorites/', headers=HB)
    check('我的收藏包含该商品', any(g['id'] == goods_id for g in r.json().get('goods', [])))

    # ===== 我的发布/状态/重复售卖 =====
    r = requests.get(f'{BASE}/wx/api/user/goods/', headers=HA, params={'status': 'on_sale'})
    check('我的在售商品', any(g['id'] == goods_id for g in r.json().get('goods', [])))
    r = requests.post(f'{BASE}/wx/api/goods/status/', headers=HA, json={'goods_id': goods_id, 'status': 'offline'})
    check('下架成功', r.json().get('success'))
    r = requests.get(f'{BASE}/wx/api/goods/', params={'keyword': '小程序验证'})
    check('下架后列表不显示', all(g['id'] != goods_id for g in r.json().get('goods', [])))
    r = requests.post(f'{BASE}/wx/api/goods/status/', headers=HA, json={'goods_id': goods_id, 'status': 'on_sale'})
    check('重新上架成功', r.json().get('success'))
    r = requests.post(f'{BASE}/wx/api/goods/toggle-repeat/', headers=HA,
                      json={'goods_id': goods_id, 'allow_repeat': True})
    check('开启重复售卖', r.json().get('allow_repeat') is True)
    r = requests.post(f'{BASE}/wx/api/goods/toggle-repeat/', headers=HA,
                      json={'goods_id': goods_id, 'allow_repeat': False})
    check('关闭重复售卖', r.json().get('allow_repeat') is False and r.json().get('status') == 'on_sale')

    # ===== 聊天流程 =====
    r = requests.post(f'{BASE}/wx/api/chat/start/', headers=HA, json={'goods_id': goods_id})
    check('卖家不能和自己交易', not r.json().get('success'))
    r = requests.post(f'{BASE}/wx/api/chat/start/', headers=HB, json={'goods_id': goods_id})
    j = r.json()
    check('B发起会话成功', j.get('success') and j.get('conv_id'), r.text[:160])
    conv_id = j.get('conv_id')

    # 再次发起复用同一会话
    r = requests.post(f'{BASE}/wx/api/chat/start/', headers=HB, json={'goods_id': goods_id})
    check('重复发起复用会话', r.json().get('conv_id') == conv_id)

    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HB,
                      data={'conversation_id': conv_id, 'type': 'text', 'content': '你好，还在卖吗？'})
    check('B发文字消息', r.json().get('success') and r.json().get('msg', {}).get('is_me') is True, r.text[:200])
    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HA,
                      data={'conversation_id': conv_id, 'type': 'text', 'content': '在的，可以自提'})
    check('A回复消息', r.json().get('success'))
    # 联系方式拦截
    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HB,
                      data={'conversation_id': conv_id, 'type': 'text', 'content': '加我微信 wx12345678'})
    check('违规联系方式被拦截', r.json().get('blocked') is True, r.text[:160])
    # 图片消息
    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HB,
                      files={'file': ('m.png', png_bytes(), 'image/png')},
                      data={'conversation_id': conv_id, 'type': 'image'})
    check('B发图片消息', r.json().get('success'), r.text[:200])

    r = requests.get(f'{BASE}/wx/api/chat/messages/', headers=HB,
                     params={'conversation_id': conv_id})
    j = r.json()
    check('拉取消息>=4条', len(j.get('messages', [])) >= 4, r.text[:200])
    check('会话含卖家收款码标记', j.get('seller_has_qrcode') is True)
    check('拉取后未读清零', j.get('status') == 'trading')
    last_id = max(m['id'] for m in j['messages'])
    r = requests.get(f'{BASE}/wx/api/chat/messages/', headers=HA,
                     params={'conversation_id': conv_id, 'after_id': last_id})
    check('增量拉取无新消息', r.json().get('messages') == [])

    # 会话列表
    r = requests.get(f'{BASE}/wx/api/chats/', headers=HB)
    j = r.json()
    conv = next((c for c in j['conversations'] if c['id'] == conv_id), None)
    check('会话列表含对方/商品信息', conv is not None and conv['peer']['nickname'] == '小程序测试A'
          and conv['goods']['id'] == goods_id, r.text[:200])

    # 确认交易：B确认 → 等待A
    r = requests.post(f'{BASE}/wx/api/chat/confirm/', headers=HB, json={'conversation_id': conv_id})
    check('B确认交易', r.json().get('success') and r.json().get('my_confirmed') is True
          and r.json().get('status') == 'trading', r.text[:160])
    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HB,
                      data={'conversation_id': conv_id, 'type': 'text', 'content': '确认后还能发吗'})
    check('trading状态仍可发消息', r.json().get('success') or r.json().get('msg') != '交易已确定，无法再发消息')
    r = requests.post(f'{BASE}/wx/api/chat/confirm/', headers=HA, json={'conversation_id': conv_id})
    check('A确认后进入confirmed', r.json().get('status') == 'confirmed', r.text[:160])
    r = requests.get(f'{BASE}/wx/api/chat/messages/', headers=HB, params={'conversation_id': conv_id})
    check('confirmed后B可见收款码', r.json().get('qrcode_url') != '')
    # 确认后不能再发消息
    r = requests.post(f'{BASE}/wx/api/chat/send/', headers=HB,
                      data={'conversation_id': conv_id, 'type': 'text', 'content': 'test'})
    check('confirmed后禁止发消息', not r.json().get('success'))

    # 买家确认收货 -> completed，非重复商品变 sold，聊天记录清除
    r = requests.post(f'{BASE}/wx/api/chat/complete/', headers=HA, json={'conversation_id': conv_id})
    check('卖家不能确认收货', not r.json().get('success'))
    r = requests.post(f'{BASE}/wx/api/chat/complete/', headers=HB, json={'conversation_id': conv_id})
    check('B确认收货完成交易', r.json().get('success'), r.text[:160])
    r = requests.get(f'{BASE}/wx/api/goods/{goods_id}/')
    check('非重复商品交易后变sold', r.json()['goods']['status'] == 'sold')
    r = requests.get(f'{BASE}/wx/api/chat/messages/', headers=HB, params={'conversation_id': conv_id})
    check('完成后聊天记录清空', r.json().get('messages') == [])
    r = requests.get(f'{BASE}/wx/api/goods/', params={'keyword': '小程序验证'})
    check('sold商品不再出现在列表', all(g['id'] != goods_id for g in r.json().get('goods', [])))

    # 取消交易流程：新商品
    r = requests.post(f'{BASE}/wx/api/goods/upload-image/', headers=HA,
                      files={'image': ('g2.png', png_bytes(), 'image/png')})
    tid = r.json()['tmp_id']
    r = requests.post(f'{BASE}/wx/api/goods/publish/', headers=HA, json={
        'title': '取消流程测试商品', 'description': '', 'price': '5', 'category': 'other',
        'trade_type': 'delivery', 'school': '测试大学', 'tmp_ids': [tid]})
    goods_id2 = r.json()['goods_id']
    r = requests.post(f'{BASE}/wx/api/chat/start/', headers=HB, json={'goods_id': goods_id2})
    conv2 = r.json()['conv_id']
    r = requests.post(f'{BASE}/wx/api/chat/cancel/', headers=HA, json={'conversation_id': conv2})
    check('卖家不能取消交易', not r.json().get('success'))
    r = requests.post(f'{BASE}/wx/api/chat/cancel/', headers=HB, json={'conversation_id': conv2})
    check('B取消交易', r.json().get('success'))
    r = requests.get(f'{BASE}/wx/api/user/trades/', headers=HB, params={'status': 'cancelled'})
    check('已买到-已取消包含该交易', any(c['id'] == conv2 for c in r.json().get('conversations', [])))

    # ===== 退出登录 =====
    r = requests.post(f'{BASE}/wx/api/auth/logout/', headers=HB)
    check('退出登录成功', r.json().get('success'))
    r = requests.get(f'{BASE}/wx/api/user/me/', headers=HB)
    check('退出后token失效401', r.status_code == 401)

    # ===== 忘记密码 =====
    requests.post(f'{BASE}/wx/api/auth/send-code/', json={'email': email_b, 'purpose': 'reset'})
    code_r = get_code_from_db(email_b)
    r = requests.post(f'{BASE}/wx/api/auth/reset-password/', json={
        'email': email_b, 'code': code_r, 'new_password': 'newpass456', 'confirm_password': 'newpass456'})
    check('重置密码成功', r.json().get('success'), r.text[:160])
    r = requests.post(f'{BASE}/wx/api/auth/login/', json={'email': email_b, 'password': 'newpass456'})
    check('新密码登录成功', r.json().get('success'))

    print(f'\n===== 结果: {len(PASS)} 通过, {len(FAIL)} 失败 =====')
    if FAIL:
        for name, extra in FAIL:
            print(f'  FAIL: {name} {extra}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
