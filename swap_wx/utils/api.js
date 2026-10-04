/**
 * SWAP 小程序请求封装
 * 认证：Authorization: Token <key>（登录/注册签发，与网站共用账号体系）
 */
const { BASE_URL } = require('../config');
const i18n = require('./i18n');

const TOKEN_KEY = 'swap_token';
const USER_KEY = 'swap_user';

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function setToken(token) {
  wx.setStorageSync(TOKEN_KEY, token);
}

function clearToken() {
  try {
    wx.removeStorageSync(TOKEN_KEY);
    wx.removeStorageSync(USER_KEY);
  } catch (e) { }
}

function getCachedUser() {
  try {
    return wx.getStorageSync(USER_KEY) || null;
  } catch (e) {
    return null;
  }
}

function cacheUser(user) {
  try {
    if (user) {
      wx.setStorageSync(USER_KEY, user);
    } else {
      wx.removeStorageSync(USER_KEY);
    }
  } catch (e) { }
}

function authHeader() {
  const t = getToken();
  return t ? { Authorization: 'Token ' + t } : {};
}

/**
 * 基础请求
 * opts: { silent(不弹网络错误), noAuthJump(401不跳登录), loading(显示加载框文案) }
 */
function request(method, path, data, opts) {
  opts = opts || {};
  if (opts.loading) {
    wx.showLoading({ title: opts.loading, mask: true });
  }
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method: method,
      data: data || {},
      timeout: 20000,
      header: Object.assign({
        'Content-Type': 'application/json'
      }, authHeader(), opts.header || {}),
      success(res) {
        if (opts.loading) wx.hideLoading();
        // 令牌失效：清理并引导登录
        if (res.statusCode === 401 && !opts.noAuthJump) {
          clearToken();
          cacheUser(null);
          const app = getApp();
          if (app) app.clearUser();
          if (!opts.silent) {
            wx.showToast({ title: i18n.t('api_please_login'), icon: 'none' });
          }
          wx.navigateTo({ url: '/pages/login/login' });
          reject(res);
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          // 业务错误（Django 返回的 JSON 含 msg）
          const body = res.data || {};
          if (!opts.silent && body.msg) {
            wx.showToast({ title: body.msg, icon: 'none' });
          }
          reject(res);
        }
      },
      fail(err) {
        if (opts.loading) wx.hideLoading();
        if (!opts.silent) {
          wx.showToast({ title: i18n.t('api_network'), icon: 'none' });
        }
        reject(err);
      }
    });
  });
}

function get(path, data, opts) {
  // GET 参数拼接到 URL（wx.request 的 GET data 也可以，但显式拼接便于调试）
  let url = path;
  if (data) {
    const qs = Object.keys(data)
      .filter(k => data[k] !== undefined && data[k] !== null && data[k] !== '')
      .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(data[k]))
      .join('&');
    if (qs) url += (path.indexOf('?') === -1 ? '?' : '&') + qs;
  }
  return request('GET', url, null, opts);
}

function post(path, data, opts) {
  return request('POST', path, data, opts);
}

/**
 * 文件上传（单文件）
 * path / filePath / name / formData
 */
function upload(path, filePath, name, formData, opts) {
  opts = opts || {};
  if (opts.loading) {
    wx.showLoading({ title: opts.loading, mask: true });
  }
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE_URL + path,
      filePath: filePath,
      name: name || 'file',
      formData: formData || {},
      timeout: 60000,
      header: authHeader(),
      success(res) {
        if (opts.loading) wx.hideLoading();
        let body = {};
        try {
          body = JSON.parse(res.data);
        } catch (e) {
          body = { success: false, msg: i18n.t('api_server_error') };
        }
        if (res.statusCode === 401 && !opts.noAuthJump) {
          clearToken();
          cacheUser(null);
          const app = getApp();
          if (app) app.clearUser();
          wx.navigateTo({ url: '/pages/login/login' });
          reject(body);
          return;
        }
        if (!body.success && body.msg && !opts.silent) {
          wx.showToast({ title: body.msg, icon: 'none' });
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.success !== false) {
          resolve(body);
        } else {
          reject(body);
        }
      },
      fail(err) {
        if (opts.loading) wx.hideLoading();
        if (!opts.silent) {
          wx.showToast({ title: i18n.t('api_upload_failed'), icon: 'none' });
        }
        reject(err);
      }
    });
  });
}

/**
 * 发送聊天文字消息（form-urlencoded，与后端 request.POST 对齐）
 */
function postForm(path, data, opts) {
  opts = opts || {};
  const pairs = Object.keys(data || {})
    .filter(k => data[k] !== undefined && data[k] !== null)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(data[k]))
    .join('&');
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method: 'POST',
      data: pairs,
      timeout: 20000,
      header: Object.assign({
        'Content-Type': 'application/x-www-form-urlencoded'
      }, authHeader()),
      success(res) {
        const body = res.data || {};
        if (res.statusCode === 401 && !opts.noAuthJump) {
          clearToken();
          cacheUser(null);
          const app = getApp();
          if (app) app.clearUser();
          wx.navigateTo({ url: '/pages/login/login' });
          reject(body);
          return;
        }
        if (!body.success && body.msg && !opts.silent) {
          wx.showToast({ title: body.msg, icon: 'none' });
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(body);
        } else {
          reject(body);
        }
      },
      fail(err) {
        if (!opts.silent) {
          wx.showToast({ title: i18n.t('api_network'), icon: 'none' });
        }
        reject(err);
      }
    });
  });
}

/**
 * 是否已登录（本地令牌判断）
 */
function isLogin() {
  return !!getToken();
}

/**
 * 需要登录的页面入口守卫：未登录跳登录页，返回 false
 */
function requireLogin(tip) {
  if (isLogin()) return true;
  wx.showToast({ title: tip || i18n.t('api_please_login'), icon: 'none' });
  wx.navigateTo({ url: '/pages/login/login' });
  return false;
}

module.exports = {
  BASE_URL,
  getToken,
  setToken,
  clearToken,
  getCachedUser,
  cacheUser,
  get,
  post,
  postForm,
  upload,
  isLogin,
  requireLogin
};
