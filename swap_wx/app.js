// SWAP 校园交易平台 - 小程序入口
const api = require('./utils/api');
const i18n = require('./utils/i18n');
const settingsStore = require('./utils/settings');

App({
  globalData: {
    // 登录用户信息（来自 wx/api/user/me 或登录接口）
    user: null,
    // 是否已加载过用户信息
    userLoaded: false,
    categories: []
  },

  onLaunch() {
    // 启动时按语言偏好同步底部导航文案
    i18n.applyTabBar();
    // 启动时恢复登录态
    if (api.getToken()) {
      this.loadUser();
    }
  },

  onShow() {
    // 刷新 TabBar 未读角标
    this.refreshChatBadge();
  },

  // 拉取当前用户信息
  loadUser() {
    return api.get('/wx/api/user/me/', null, { silent: true }).then(res => {
      if (res && res.success) {
        this.globalData.user = res.user;
      } else {
        // 令牌失效
        api.clearToken();
        this.globalData.user = null;
      }
      this.globalData.userLoaded = true;
      return res;
    }).catch(() => {
      this.globalData.userLoaded = true;
    });
  },

  // 更新全局用户缓存
  setUser(user) {
    this.globalData.user = user;
    this.globalData.userLoaded = true;
  },

  // 登出清理
  clearUser() {
    this.globalData.user = null;
    this.globalData.userLoaded = false;
    api.clearToken();
    this.refreshChatBadge(true);
  },

  // 刷新「消息」TabBar 未读角标（受设置页本地提醒开关控制）
  refreshChatBadge(clear) {
    const apply = (n) => {
      // 自定义 tabBar：通过当前页面实例同步角标
      const pages = getCurrentPages();
      const cur = pages[pages.length - 1];
      if (cur && typeof cur.getTabBar === 'function' && cur.getTabBar()) {
        cur.getTabBar().updateBadge(n);
      }
    };
    if (!api.getToken() || clear || !settingsStore.getNotifyLocal()) {
      wx.removeTabBarBadge({ index: 1, fail: () => {} });
      apply(0);
      return;
    }
    api.get('/wx/api/chats/', null, { silent: true }).then(res => {
      if (res && res.success) {
        const n = res.unread_total || 0;
        if (n > 0) {
          wx.setTabBarBadge({ index: 1, text: String(n > 99 ? '99+' : n), fail: () => {} });
        } else {
          wx.removeTabBarBadge({ index: 1, fail: () => {} });
        }
        apply(n);
      }
    }).catch(() => {});
  }
});
