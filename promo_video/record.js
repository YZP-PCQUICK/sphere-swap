const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Users\\ysm\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe';
const HTML_PATH = path.resolve(__dirname, 'index.html');
const OUTPUT_PATH = path.resolve(__dirname, 'swap_promo.webm');
const DURATION_MS = 61000; // 61秒

(async () => {
  console.log('[1/5] 启动 Chrome（无头模式）...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    defaultViewport: { width: 1920, height: 1080, deviceScaleFactor: 1 },
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=1920,1080',
      '--force-device-scale-factor=1',
      '--high-dpi-support=1',
      '--disable-gpu',
      '--autoplay-policy=no-user-gesture-required',
      '--allow-file-access-from-files',
      '--disable-web-security'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });

  page.on('console', msg => {
    const t = msg.type();
    if (t === 'error' || t === 'warning') console.log(`[browser ${t}]`, msg.text());
  });
  page.on('pageerror', err => console.log('[page error]', err.message));

  console.log('[2/5] 打开动画页面...');
  await page.goto('file:///' + HTML_PATH.replace(/\\/g, '/'), {
    waitUntil: 'networkidle0',
    timeout: 30000
  });

  // 等待动画启动
  await new Promise(r => setTimeout(r, 500));

  // 创建 CDP session
  const client = await page.target().createCDPSession();
  await client.send('Page.enable');

  console.log('[3/5] 启动 canvas 录制器...');
  await page.evaluate(() => window.__startRecorder());

  console.log('[4/5] 开始 CDP 帧捕获（' + (DURATION_MS / 1000) + '秒）...');
  const startTime = Date.now();
  let frameCount = 0;

  client.on('Page.screencastFrame', (params) => {
    frameCount++;
    // fire-and-forget：不等待帧传递完成，避免阻塞捕获
    client.send('Runtime.evaluate', {
      expression: 'window.__addFrame && window.__addFrame(' + JSON.stringify(params.data) + ')',
      awaitPromise: false,
      returnByValue: false
    }).catch(() => {});
    // 立即确认帧
    client.send('Page.screencastFrameAck', { sessionId: params.sessionId }).catch(() => {});
  });

  await client.send('Page.startScreencast', {
    format: 'jpeg',
    quality: 80,
    maxWidth: 1920,
    maxHeight: 1080,
    everyNthFrame: 2
  });

  // 等待录制时长
  await new Promise(r => setTimeout(r, DURATION_MS));

  console.log('[5/5] 停止捕获并保存视频...');
  await client.send('Page.stopScreencast').catch(() => {});

  // 停止页面中的录制器
  await page.evaluate(() => {
    if (window.__stopRecorder) window.__stopRecorder();
  });

  // 等待视频编码完成
  await page.waitForFunction(
    () => window.__videoReady === true,
    { timeout: 15000, polling: 200 }
  );

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`    捕获帧数: ${frameCount}, 耗时: ${elapsed}s`);

  // 读取视频 blob
  const base64 = await page.evaluate(async () => {
    const blob = window.__videoBlob;
    if (!blob) throw new Error('video blob not found');
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  });

  const buffer = Buffer.from(base64, 'base64');
  fs.writeFileSync(OUTPUT_PATH, buffer);
  console.log(`    视频已保存: ${OUTPUT_PATH}`);
  console.log(`    文件大小: ${(buffer.length / 1024 / 1024).toFixed(2)} MB`);

  await browser.close();
  console.log('完成！');
})().catch(err => {
  console.error('录制失败:', err.message);
  process.exit(1);
});
