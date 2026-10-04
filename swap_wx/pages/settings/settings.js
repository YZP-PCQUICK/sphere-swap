const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const settingsStore = require('../../utils/settings');

Page({
  data: {
    t: {},
    _lang: 'zh',
    isLogin: false,
    notifyLocal: true,
    notifyPush: false,
    quickNav: false,
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
    pwdError: '',
    pwdSubmitting: false
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('st_title') });
    this.setData({
      isLogin: api.isLogin(),
      notifyLocal: settingsStore.getNotifyLocal(),
      notifyPush: settingsStore.getNotifyPush(),
      quickNav: settingsStore.getQuickNav()
    });
  },

  // 本地提醒开关
  onNotifyLocalChange(e) {
    const on = e.detail.value;
    settingsStore.setNotifyLocal(on);
    wx.showToast({ title: i18n.t(on ? 'st_notify_on' : 'st_notify_off'), icon: 'none' });
  },

  // 订阅消息推送开关（开启时申请微信授权）
  onNotifyPushChange(e) {
    const on = e.detail.value;
    if (!on) {
      settingsStore.setNotifyPush(false);
      wx.showToast({ title: i18n.t('st_push_off'), icon: 'none' });
      return;
    }
    settingsStore.requestPushSubscription().then((result) => {
      if (result === 'accept') {
        settingsStore.setNotifyPush(true);
        this.setData({ notifyPush: true });
        wx.showToast({ title: i18n.t('st_push_ok'), icon: 'none' });
      } else if (result === 'not_configured') {
        this.setData({ notifyPush: false });
        wx.showToast({ title: i18n.t('st_push_need_cfg'), icon: 'none', duration: 2500 });
      } else if (result === 'reject') {
        this.setData({ notifyPush: false });
        wx.showToast({ title: i18n.t('st_push_reject'), icon: 'none' });
      } else {
        this.setData({ notifyPush: false });
        wx.showToast({ title: i18n.t('st_push_fail'), icon: 'none' });
      }
    });
  },

  // 快捷跳转浮球开关
  onQuickNavChange(e) {
    const on = e.detail.value;
    settingsStore.setQuickNav(on);
    wx.showToast({ title: i18n.t(on ? 'st_quicknav_on' : 'st_quicknav_off'), icon: 'none' });
  },

  setZh() {
    this.switchLang('zh');
  },

  setEn() {
    this.switchLang('en');
  },

  switchLang(lang) {
    if (i18n.getLang() === lang) return;
    i18n.setLang(lang);
    i18n.apply(this);
    i18n.applyTabBar();
    wx.setNavigationBarTitle({ title: i18n.t('st_title') });
    wx.showToast({ title: i18n.t(lang === 'en' ? 'st_lang_switched_en' : 'st_lang_switched_zh'), icon: 'none' });
  },

  onOldInput(e) {
    this.setData({ oldPassword: e.detail.value, pwdError: '' });
  },

  onNewInput(e) {
    this.setData({ newPassword: e.detail.value, pwdError: '' });
  },

  onConfirmInput(e) {
    this.setData({ confirmPassword: e.detail.value, pwdError: '' });
  },

  submitPassword() {
    const d = this.data;
    if (d.pwdSubmitting) return;
    if (!api.isLogin()) {
      wx.showToast({ title: i18n.t('st_login_required'), icon: 'none' });
      return;
    }
    if (!d.oldPassword) {
      this.setData({ pwdError: i18n.t('pwd_err_old') });
      return;
    }
    if (d.newPassword.length < 6) {
      this.setData({ pwdError: i18n.t('reset_err_pwd_short') });
      return;
    }
    if (d.newPassword !== d.confirmPassword) {
      this.setData({ pwdError: i18n.t('reset_err_pwd_mismatch') });
      return;
    }
    if (d.newPassword === d.oldPassword) {
      this.setData({ pwdError: i18n.t('pwd_err_same') });
      return;
    }

    this.setData({ pwdSubmitting: true, pwdError: '' });
    api.post('/wx/api/auth/change-password/', {
      old_password: d.oldPassword,
      new_password: d.newPassword,
      confirm_password: d.confirmPassword
    }, { silent: true, noAuthJump: true })
      .then((res) => {
        if (res.success) {
          wx.showToast({ title: i18n.t('st_pwd_ok'), icon: 'none', duration: 2500 });
          // 改密成功后端已作废令牌，本地清理并回登录页
          api.clearToken();
          const app = getApp();
          if (app && app.clearUser) app.clearUser();
          setTimeout(() => {
            wx.navigateTo({ url: '/pages/login/login' });
          }, 1800);
        } else {
          this.setData({ pwdError: res.msg || i18n.t('pwd_err_fail') });
        }
      })
      .catch((err) => {
        const body = err && err.data ? err.data : {};
        this.setData({ pwdError: body.msg || i18n.t('pwd_err_fail') });
      })
      .then(() => {
        this.setData({ pwdSubmitting: false });
      });
  },

  // 忘记密码：跳转登录页重置面板，通过邮箱验证码重置
  goForgotPassword() {
    wx.navigateTo({ url: '/pages/login/login?panel=reset' });
  },

  // 关于平台
  goAbout() {
    wx.navigateTo({ url: '/pages/about/about' });
  },

  // 退出登录（与「我的」页一致：调登出接口作废令牌）
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
            this.setData({ isLogin: false });
            wx.showToast({ title: i18n.t('profile_logged_out'), icon: 'none' });
          });
      }
    });
  },

  clearCache() {
    wx.showModal({
      title: i18n.t('st_cache_confirm_title'),
      content: i18n.t('st_cache_confirm_text'),
      confirmText: i18n.t('ok'),
      cancelText: i18n.t('cancel'),
      success: (res) => {
        if (!res.confirm) return;
        let removed = 0;
        try {
          const info = wx.getStorageInfoSync();
          info.keys.forEach((k) => {
            // 只清聊天记录等缓存，保留登录令牌、用户信息与语言偏好
            if (k.indexOf('swap_chat_') === 0 || /^\d+$/.test(k)) {
              wx.removeStorageSync(k);
              removed++;
            }
          });
        } catch (e) { }
        wx.showToast({ title: i18n.t('st_cache_cleared') + ' (' + removed + ')', icon: 'none' });
      }
    });
  }
});
