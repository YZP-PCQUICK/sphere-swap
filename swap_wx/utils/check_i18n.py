# -*- coding: utf-8 -*-
"""校验小程序页面引用的 i18n key 是否都存在于字典（中/英）"""
import re, os, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 读取 i18n.js 字典
i18n_path = os.path.join(ROOT, 'utils', 'i18n.js')
src = open(i18n_path, encoding='utf-8').read()

def extract_dict(name):
    m = re.search(name + r':\s*\{(.*?)\n\s*\}', src, re.S)
    return set(re.findall(r"([a-zA-Z0-9_]+)\s*:", m.group(1)))

zh_keys = extract_dict('zh')
en_keys = extract_dict('en')

missing_report = []
pages_dir = os.path.join(ROOT, 'pages')
scan_dirs = [pages_dir, os.path.join(ROOT, 'components')]
for base in scan_dirs:
    for page in sorted(os.listdir(base)):
        pdir = os.path.join(base, page)
        if not os.path.isdir(pdir):
            continue
        for fn in os.listdir(pdir):
            if not fn.endswith(('.wxml', '.js')):
                continue
            path = os.path.join(pdir, fn)
            content = open(path, encoding='utf-8').read()
            # wxml 中 {{t.xxx}} 引用
            used = set(re.findall(r'\{\{\s*t\.([a-zA-Z0-9_]+)', content))
            # js 中 i18n.t('xxx') 引用
            content2 = content
            used |= set(re.findall(r"i18n\.t\(\s*'([a-zA-Z0-9_]+)'", content2))
            miss_zh = [k for k in used if k not in zh_keys]
            miss_en = [k for k in used if k not in en_keys]
            if miss_zh or miss_en:
                rel = os.path.relpath(path, ROOT)
                missing_report.append((rel, sorted(set(miss_zh)), sorted(set(miss_en))))

# 中英字典 key 一致性
only_zh = zh_keys - en_keys
only_en = en_keys - zh_keys

print("=== 中英字典 key 差异 ===")
if only_zh: print("仅中文有:", sorted(only_zh))
if only_en: print("仅英文有:", sorted(only_en))
if not only_zh and not only_en: print("一致，共 %d 个 key" % len(zh_keys))

print("\n=== 页面缺失 key ===")
if not missing_report:
    print("全部通过")
else:
    for f, mz, me in missing_report:
        print(f, "| 缺中文:", mz, "| 缺英文:", me)
    sys.exit(1)
