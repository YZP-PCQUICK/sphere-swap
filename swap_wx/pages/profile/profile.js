const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

Page({
  data: {
    isLogin: false,
    user: null
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 });
      this.getTabBar().refresh();
    }
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('tab_profile') });
    this.refresh();
  },

  refresh() {
    const isLogin = api.isLogin();
    this.setData({ isLogin: isLogin });
    if (!isLogin) {
      this.setData({ user: null });
      return;
    }
    // 先用缓存快速渲染，再拉取最新
    const cached = api.getCachedUser();
    if (cached) this.setData({ user: this.decorateUser(cached) });
    api.get('/wx/api/user/me/', null, { silent: true })
      .then((res) => {
        if (res.success) {
          api.cacheUser(res.user);
          this.setData({ user: this.decorateUser(res.user) });
        } else {
          this.setData({ isLogin: false, user: null });
        }
      })
      .catch(() => {});
  },

  // 与网站 profile.html 展示规则一致：空值显示默认占位文案
  decorateUser(u) {
    if (!u) return u;
    u.nickname_display = (u.nickname && u.nickname !== u.email) ? u.nickname : i18n.t('profile_no_nickname');
    u.school_display = u.school || i18n.t('profile_no_school');
    u.bio_display = u.bio || i18n.t('profile_no_bio');
    return u;
  },

  onPullDownRefresh() {
    this.refresh();
    wx.stopPullDownRefresh();
  },

  changeAvatar() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath;
        api.upload('/wx/api/user/avatar/', path, 'avatar', { loading: i18n.t('profile_uploading_avatar') })
          .then((r) => {
            if (r.success) {
              wx.showToast({ title: i18n.t('profile_avatar_updated'), icon: 'success' });
              this.refresh();
            }
          })
          .catch(() => {});
      }
    });
  },

  logout() {
    wx.showModal({
      title: i18n.t('profile_logout'),
      content: i18n.t('profile_logout_confirm'),
      confirmText: i18n.t('profile_logout_ok'),
      cancelText: i18n.t('cancel'),
      confirmColor: '#F5222D',
      success: (res) => {
        if (!res.confirm) return;
        api.post('/wx/api/auth/logout/', {}, { silent: true, noAuthJump: true })
          .catch(() => {})
          .then(() => {
            const app = getApp();
            if (app) app.clearUser();
            this.setData({ isLogin: false, user: null });
            wx.showToast({ title: i18n.t('profile_logged_out'), icon: 'none' });
          });
      }
    });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/register/register' });
  },

  goMyGoods() {
    wx.navigateTo({ url: '/pages/transactions/transactions?tab=goods' });
  },

  goPublish() {
    if (!api.isLogin()) {
      wx.showToast({ title: i18n.t('api_please_login'), icon: 'none' });
      setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 600);
      return;
    }
    wx.navigateTo({ url: '/pages/publish/publish' });
  },

  goFavorites() {
    wx.navigateTo({ url: '/pages/favorites/favorites' });
  },

  goTransactions() {
    wx.navigateTo({ url: '/pages/transactions/transactions?tab=trade' });
  },

  goProfileEdit() {
    wx.navigateTo({ url: '/pages/profile-edit/profile-edit' });
  },

  // 查看收款码大图（与网站 profile 页展示收款码一致）
  previewQrcode() {
    if (!this.data.user || !this.data.user.payment_qrcode) return;
    wx.previewImage({
      current: this.data.user.payment_qrcode,
      urls: [this.data.user.payment_qrcode]
    });
  },

  goSettings() {
    wx.navigateTo({ url: '/pages/settings/settings' });
  },

  goAbout() {
    wx.navigateTo({ url: '/pages/about/about' });
  }
});
