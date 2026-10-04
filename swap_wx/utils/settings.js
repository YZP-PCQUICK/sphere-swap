/**
 * 小程序本地设置开关（消息提醒 / 订阅推送 / 快捷跳转）
 * 与网页版设置页行为对齐，仅存本机 storage，不上传服务器
 */
const { SUBSCRIBE_TMPL_IDS } = require('../config');

const KEY_NOTIFY_LOCAL = 'swap_notify_local'; // 本地提醒：角标 + 振动
const KEY_NOTIFY_PUSH = 'swap_notify_push';   // 微信订阅消息推送
const KEY_QUICKNAV = 'swap_quicknav';         // 快捷跳转浮球

function getBool(key, def) {
  try {
    const v = wx.getStorageSync(key);
    if (v === '' || v === undefined || v === null) return def;
    return v === true || v === 'true';
  } catch (e) {
    return def;
  }
}

function setBool(key, value) {
  try {
    wx.setStorageSync(key, value === true || value === 'true');
  } catch (e) { }
}

// 本地提醒（默认开）
function getNotifyLocal() {
  return getBool(KEY_NOTIFY_LOCAL, true);
}

function setNotifyLocal(on) {
  setBool(KEY_NOTIFY_LOCAL, on);
}

// 订阅消息推送（默认关）
function getNotifyPush() {
  return getBool(KEY_NOTIFY_PUSH, false);
}

function setNotifyPush(on) {
  setBool(KEY_NOTIFY_PUSH, on);
}

// 快捷跳转浮球（默认关）
function getQuickNav() {
  return getBool(KEY_QUICKNAV, false);
}

function setQuickNav(on) {
  setBool(KEY_QUICKNAV, on);
}

// 申请微信订阅消息授权；未配置模板 ID 时返回 'not_configured'
function requestPushSubscription() {
  return new Promise((resolve) => {
    if (!SUBSCRIBE_TMPL_IDS || !SUBSCRIBE_TMPL_IDS.length) {
      resolve('not_configured');
      return;
    }
    if (!wx.requestSubscribeMessage) {
      resolve('unsupported');
      return;
    }
    wx.requestSubscribeMessage({
      tmplIds: SUBSCRIBE_TMPL_IDS,
      success: (res) => {
        // 任一模板结果为 accept 视为订阅成功
        const accepted = SUBSCRIBE_TMPL_IDS.some((id) => res[id] === 'accept');
        resolve(accepted ? 'accept' : 'reject');
      },
      fail: () => resolve('fail')
    });
  });
}

module.exports = {
  getNotifyLocal,
  setNotifyLocal,
  getNotifyPush,
  setNotifyPush,
  getQuickNav,
  setQuickNav,
  requestPushSubscription
};
