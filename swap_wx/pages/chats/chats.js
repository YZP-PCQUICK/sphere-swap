const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const settingsStore = require('../../utils/settings');

Page({
  data: {
    conversations: [],
    isLogin: false,
    loaded: false
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 });
    }
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('chats_title') });
    this._stopTimer();
    const isLogin = api.isLogin();
    this.setData({ isLogin: isLogin });
    if (isLogin) {
      this.loadChats();
      // 与网站一致（base.js 全局 2s 轮询未读、实时更新会话角标）：
      // TODO: 后端缺少接口：wxapi 无 /chat/api/unread/ 等价接口，
      // 复用 /wx/api/chats/ 的 unread_total 与每个会话的 unread 字段实现轮询
      this._timer = setInterval(() => this.loadChats(true), 2000);
    } else {
      this.setData({ conversations: [], loaded: true });
    }
  },

  onHide() {
    this._stopTimer();
  },

  onUnload() {
    this._stopTimer();
  },

  _stopTimer() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  onPullDownRefresh() {
    if (api.isLogin()) {
      this.loadChats().then(() => wx.stopPullDownRefresh());
    } else {
      wx.stopPullDownRefresh();
    }
  },

  // 会话列表项（字段与网站 chat/list.html 展示一致：商品图/商品标题/最后消息/价格/状态/未读数）
  _mapConv(c) {
    c.goods_initial = (c.goods && c.goods.title ? c.goods.title : '?').charAt(0);
    c.peer_initial = (c.peer && c.peer.nickname ? c.peer.nickname : '?').charAt(0).toUpperCase();
    // 后端 status_name 为中文，按语言映射（无对应 key 时保留后端文案）
    const statusKey = 'chat_status_' + c.status;
    const statusLabel = i18n.t(statusKey);
    if (statusLabel !== statusKey) c.status_name = statusLabel;
    return c;
  },

  loadChats(poll) {
    return api.get('/wx/api/chats/', null, { silent: true })
      .then((res) => {
        this.setData({
          conversations: (res.conversations || []).map((c) => this._mapConv(c)),
          loaded: true
        });
        // 同步 tabBar 未读角标（受设置页「本地提醒」开关控制）
        this._syncBadge(res.unread_total || 0);
      })
      .catch(() => {
        if (!poll) this.setData({ loaded: true });
      });
  },

  _syncBadge(total) {
    if (!settingsStore.getNotifyLocal()) total = 0;
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().updateBadge(total);
    }
    if (total > 0) {
      wx.setTabBarBadge({ index: 1, text: String(total > 99 ? '99+' : total), fail: () => { } });
    } else {
      wx.removeTabBarBadge({ index: 1, fail: () => { } });
    }
  },

  goRoom(e) {
    wx.navigateTo({ url: '/pages/chat/chat?id=' + e.currentTarget.dataset.id });
  },

  // 空态「去逛逛」（网站空态按钮指向商品列表）
  goBrowse() {
    wx.navigateTo({ url: '/pages/list/list' });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
