const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const CHROME_PATH = 'C:\\Users\\ysm\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe';
const HTML_PATH = path.resolve(__dirname, 'index.html');
const WEBM_PATH = path.resolve(__dirname, 'swap_promo_2k.webm');
const MP4_PATH = path.resolve(__dirname, 'swap_promo_2k.mp4');
const FFMPEG_PATH = require('ffmpeg-static');
const DURATION_MS = 61000; // 61秒

(async () => {
  console.log('[1/6] 启动 Chrome（无头模式，2K视口）...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    defaultViewport: { width: 2560, height: 1440, deviceScaleFactor: 1 },
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=2560,1440',
      '--force-device-scale-factor=1',
      '--high-dpi-support=1',
      '--disable-gpu',
      '--autoplay-policy=no-user-gesture-required',
      '--allow-file-access-from-files',
      '--disable-web-security'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 2560, height: 1440, deviceScaleFactor: 1 });

  page.on('console', msg => {
    const t = msg.type();
    if (t === 'error' || t === 'warning') console.log(`[browser ${t}]`, msg.text());
  });
  page.on('pageerror', err => console.log('[page error]', err.message));

  console.log('[2/6] 打开动画页面...');
  await page.goto('file:///' + HTML_PATH.replace(/\\/g, '/'), {
    waitUntil: 'networkidle0',
    timeout: 30000
  });

  await new Promise(r => setTimeout(r, 500));

  const client = await page.target().createCDPSession();
  await client.send('Page.enable');

  console.log('[3/6] 启动 canvas 录制器（60fps）...');
  await page.evaluate(() => window.__startRecorder());

  console.log('[4/6] 开始 CDP 帧捕获（2K，everyNthFrame=1）...');
  const startTime = Date.now();
  let frameCount = 0;

  client.on('Page.screencastFrame', (params) => {
    frameCount++;
    client.send('Runtime.evaluate', {
      expression: 'window.__addFrame && window.__addFrame(' + JSON.stringify(params.data) + ')',
      awaitPromise: false,
      returnByValue: false
    }).catch(() => {});
    client.send('Page.screencastFrameAck', { sessionId: params.sessionId }).catch(() => {});
  });

  await client.send('Page.startScreencast', {
    format: 'jpeg',
    quality: 90,
    maxWidth: 2560,
    maxHeight: 1440,
    everyNthFrame: 1
  });

  await new Promise(r => setTimeout(r, DURATION_MS));

  console.log('[5/6] 停止捕获，保存 WebM...');
  await client.send('Page.stopScreencast').catch(() => {});

  await page.evaluate(() => {
    if (window.__stopRecorder) window.__stopRecorder();
  });

  await page.waitForFunction(
    () => window.__videoReady === true,
    { timeout: 15000, polling: 200 }
  );

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`    捕获帧数: ${frameCount}, 耗时: ${elapsed}s, 平均帧率: ${(frameCount / elapsed).toFixed(1)}fps`);

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
  fs.writeFileSync(WEBM_PATH, buffer);
  console.log(`    WebM 已保存: ${WEBM_PATH} (${(buffer.length / 1024 / 1024).toFixed(2)} MB)`);

  await browser.close();

  console.log('[6/6] ffmpeg 转码 MP4 + 插帧到 120fps...');
  try {
    execFileSync(FFMPEG_PATH, [
      '-y',
      '-i', WEBM_PATH,
      '-vf', 'minterpolate=fps=120:mi_mode=blend:scd=none',
      '-c:v', 'libx264',
      '-preset', 'medium',
      '-crf', '18',
      '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart',
      MP4_PATH
    ], { stdio: 'inherit' });

    const mp4Stat = fs.statSync(MP4_PATH);
    console.log(`    MP4 已保存: ${MP4_PATH} (${(mp4Stat.size / 1024 / 1024).toFixed(2)} MB)`);
    console.log('    分辨率: 2560x1440 (2K), 帧率: 120fps, 编码: H.264');
  } catch (e) {
    console.error('    ffmpeg 转码失败:', e.message);
    console.log('    WebM 文件仍可用:', WEBM_PATH);
  }

  console.log('完成！');
})().catch(err => {
  console.error('录制失败:', err.message);
  process.exit(1);
});
