const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:\\Users\\ysm\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe';
const VIDEO_PATH = path.resolve(__dirname, 'swap_promo.webm');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    defaultViewport: { width: 1280, height: 720 },
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required']
  });
  const page = await browser.newPage();

  await page.goto('file:///' + VIDEO_PATH.replace(/\\/g, '/'));
  await new Promise(r => setTimeout(r, 1000));

  // 获取视频时长
  const duration = await page.evaluate(() => {
    const v = document.querySelector('video');
    return v ? v.duration : 0;
  });
  console.log('视频时长:', duration, '秒');

  // 截取几个关键帧
  const timestamps = [0, 10, 20, 30, 40, 50, 59];
  for (const t of timestamps) {
    if (t > duration) continue;
    await page.evaluate((time) => {
      const v = document.querySelector('video');
      if (v) { v.currentTime = time; v.pause(); }
    }, t);
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.resolve(__dirname, `frame_${t}s.png`) });
    console.log(`已截取 ${t}s 帧`);
  }

  await browser.close();
  console.log('验证完成');
})().catch(e => { console.error(e); process.exit(1); });
