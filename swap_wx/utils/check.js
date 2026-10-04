// 小程序静态校验脚本（临时，用后即删）
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const appJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'));
let errors = [];
let warnings = [];

// 1. 页面四件套检查
const pages = appJson.pages || [];
for (const p of pages) {
  for (const ext of ['.js', '.wxml', '.wxss', '.json']) {
    const f = path.join(ROOT, p + ext);
    if (!fs.existsSync(f)) errors.push(`缺少页面文件: ${p}${ext}`);
  }
  if (fs.existsSync(path.join(ROOT, p + '.json'))) {
    try {
      JSON.parse(fs.readFileSync(path.join(ROOT, p + '.json'), 'utf8'));
    } catch (e) {
      errors.push(`JSON 解析失败: ${p}.json -> ${e.message}`);
    }
  }
}

// tabBar 页面必须在 pages 里且图标存在
const tabBarPages = (appJson.tabBar && appJson.tabBar.list) || [];
for (const t of tabBarPages) {
  if (!pages.includes(t.pagePath)) errors.push(`tabBar 页面未注册: ${t.pagePath}`);
  for (const icon of [t.iconPath, t.selectedIconPath]) {
    if (icon && !fs.existsSync(path.join(ROOT, icon))) errors.push(`tabBar 图标缺失: ${icon}`);
  }
}

// 2. JS 语法检查（require + new Function 包裹做近似编译）
function walk(dir) {
  let out = [];
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) out = out.concat(walk(full));
    else if (name.endsWith('.js')) out.push(full);
  }
  return out;
}
for (const f of walk(ROOT)) {
  if (f.includes('node_modules')) continue;
  const src = fs.readFileSync(f, 'utf8');
  try {
    // 用 Function 构造做语法检查（不执行）
    new Function('require', 'module', 'exports', 'wx', 'App', 'Page', 'getApp', 'getCurrentPages', src);
  } catch (e) {
    errors.push(`JS 语法错误: ${path.relative(ROOT, f)} -> ${e.message}`);
  }
}

// 3. WXML 引用的本地图片存在性
for (const p of pages) {
  const wxmlPath = path.join(ROOT, p + '.wxml');
  if (!fs.existsSync(wxmlPath)) continue;
  const src = fs.readFileSync(wxmlPath, 'utf8');
  const re = /src="(\/images\/[^"{}]+?)"/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const img = m[1];
    if (!fs.existsSync(path.join(ROOT, img))) errors.push(`WXML 图片缺失: ${p}.wxml -> ${img}`);
  }
  // 静态拼接 /images/cat-{{item.key}}.png 之类：收集 cat-*.png 校验 categories keys
}

// 4. 分类图标齐全性（cat-xxx.png 覆盖 models 的 CATEGORY_CHOICES）
const modelsPath = path.join(ROOT, '..', 'swap', 'swapweb', 'goods', 'models.py');
if (fs.existsSync(modelsPath)) {
  const models = fs.readFileSync(modelsPath, 'utf8');
  const block = models.match(/CATEGORY_CHOICES = \[([\s\S]*?)\]/);
  if (block) {
    const keys = [...block[1].matchAll(/'([a-z_]+)',/g)].map(x => x[1]);
    for (const k of keys) {
      if (!fs.existsSync(path.join(ROOT, 'images', `cat-${k}.png`))) {
        errors.push(`分类图标缺失: images/cat-${k}.png`);
      }
    }
  }
}

// 5. wxss 大括号配对检查
for (const p of pages.concat(['app'])) {
  const f = path.join(ROOT, p + '.wxss');
  if (!fs.existsSync(f)) continue;
  const src = fs.readFileSync(f, 'utf8');
  const open = (src.match(/{/g) || []).length;
  const close = (src.match(/}/g) || []).length;
  if (open !== close) errors.push(`WXSS 括号不配对: ${p}.wxss (${open} vs ${close})`);
}

console.log('检查页面数:', pages.length);
if (warnings.length) console.log('警告:\n' + warnings.join('\n'));
if (errors.length) {
  console.log('错误:\n' + errors.join('\n'));
  process.exit(1);
}
console.log('全部静态校验通过');
