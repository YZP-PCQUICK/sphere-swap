# -*- coding: utf-8 -*-
"""小程序全页面静态检查：JSON / WXML 标签平衡 / WXSS 花括号 / JS 语法 / 图片引用 / 组件注册"""
import os, re, json, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(ROOT, 'pages')
COMPONENTS = os.path.join(ROOT, 'components')
issues = []

# app.json 注册的页面
app_json = json.load(open(os.path.join(ROOT, 'app.json'), encoding='utf-8'))
registered = [p.rstrip('/') for p in app_json.get('pages', [])]

# 全局组件
global_components = app_json.get('usingComponents', {})

WXML_TAGS = ['view', 'text', 'image', 'button', 'input', 'textarea', 'block', 'scroll-view',
             'swiper', 'swiper-item', 'video', 'form', 'switch', 'checkbox', 'radio',
             'picker', 'navigator', 'quicknav', 'canvas', 'map', 'cover-view', 'rich-text', 'slider']

for entry in registered:
    # entry 形如 pages/index/index，页面文件位于 pages/index/index.wxml
    pdir = os.path.normpath(os.path.join(ROOT, os.path.dirname(entry)))
    name = os.path.basename(entry)
    # 1. 四件套文件存在
    for ext in ['.wxml', '.json', '.js']:
        if not os.path.exists(os.path.join(pdir, name + ext)):
            issues.append(f'{entry}: 缺少 {name}{ext}')
    # wxss 可选但通常有
    has_wxss = os.path.exists(os.path.join(pdir, name + '.wxss'))

    # 2. JSON 可解析
    if os.path.exists(os.path.join(pdir, name + '.json')):
        try:
            pj = json.load(open(os.path.join(pdir, name + '.json'), encoding='utf-8'))
        except Exception as e:
            issues.append(f'{entry}: JSON 解析失败 {e}')
            pj = {}

    # 3. WXML 标签平衡
    wxml_path = os.path.join(pdir, name + '.wxml')
    if os.path.exists(wxml_path):
        content = open(wxml_path, encoding='utf-8').read()
        # 去掉注释
        content = re.sub(r'<!--.*?-->', '', content, flags=re.S)
        stack = []
        for m in re.finditer(r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|\'[^\']*\'|[^>"\'])*?)(/?)>', content):
            closing, tag, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
            if tag not in WXML_TAGS and not tag.islower():
                continue
            if selfclose == '/':
                continue
            if closing == '/':
                if not stack or stack[-1] != tag:
                    line = content[:m.start()].count('\n') + 1
                    issues.append(f'{entry}/{name}.wxml 第{line}行: </{tag}> 与栈顶 <{stack[-1] if stack else "空"}> 不匹配')
                    if stack and stack[-1] == tag:
                        stack.pop()
                else:
                    stack.pop()
            else:
                stack.append(tag)
        if stack:
            issues.append(f'{entry}/{name}.wxml: 未闭合标签 {stack}')

        # 4. 图片引用存在（跳过 {{}} 动态拼接路径）
        for m in re.finditer(r'src="(/images/[^"]+)"', content):
            img = m.group(1)
            if '{{' in img:
                continue
            if not os.path.exists(os.path.join(ROOT, img.lstrip('/'))):
                issues.append(f'{entry}/{name}.wxml: 图片不存在 {img}')

    # 5. WXSS 花括号平衡
    wxss_path = os.path.join(pdir, name + '.wxss')
    if has_wxss:
        css = open(wxss_path, encoding='utf-8').read()
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        if css.count('{') != css.count('}'):
            issues.append(f'{entry}/{name}.wxss: 花括号不平衡 {{={css.count("{")} }}={css.count("}")}')

    # 6. JS 语法
    js_path = os.path.join(pdir, name + '.js')
    if os.path.exists(js_path):
        r = subprocess.run(['node', '--check', js_path], capture_output=True, text=True)
        if r.returncode != 0:
            issues.append(f'{entry}/{name}.js: 语法错误 {r.stderr.strip()[:200]}')

# 组件同样检查
if os.path.isdir(COMPONENTS):
    for comp in os.listdir(COMPONENTS):
        cdir = os.path.join(COMPONENTS, comp)
        if not os.path.isdir(cdir):
            continue
        for ext in ['.js', '.json', '.wxml', '.wxss']:
            if not os.path.exists(os.path.join(cdir, comp + ext)):
                issues.append(f'components/{comp}: 缺少 {comp}{ext}')
        js_path = os.path.join(cdir, comp + '.js')
        if os.path.exists(js_path):
            r = subprocess.run(['node', '--check', js_path], capture_output=True, text=True)
            if r.returncode != 0:
                issues.append(f'components/{comp}.js: 语法错误 {r.stderr.strip()[:200]}')
        css = open(os.path.join(cdir, comp + '.wxss'), encoding='utf-8').read()
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        if css.count('{') != css.count('}'):
            issues.append(f'components/{comp}.wxss: 花括号不平衡')
        wxml = open(os.path.join(cdir, comp + '.wxml'), encoding='utf-8').read()
        for m in re.finditer(r'src="(/images/[^"]+)"', wxml):
            img = m.group(1)
            if not os.path.exists(os.path.join(ROOT, img.lstrip('/'))):
                issues.append(f'components/{comp}.wxml: 图片不存在 {img}')

# app.js / app.wxss / utils
for js in ['app.js'] + [os.path.join('utils', f) for f in os.listdir(os.path.join(ROOT, 'utils')) if f.endswith('.js')]:
    r = subprocess.run(['node', '--check', os.path.join(ROOT, js)], capture_output=True, text=True)
    if r.returncode != 0:
        issues.append(f'{js}: 语法错误 {r.stderr.strip()[:200]}')

print(f'registered pages: {len(registered)}')
if issues:
    print(f'发现 {len(issues)} 个问题:')
    for i in issues:
        print(' -', i)
    sys.exit(1)
else:
    print('全部检查通过')
