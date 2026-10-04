const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

Page({
  data: {
    panel: 'login',
    loginForm: { email: '', password: '' },
    loginErrors: {},
    loginLoading: false,
    remember: true,
    showPwd: false,
    resetForm: { email: '', code: '', newPassword: '', confirmPassword: '' },
    resetErrors: {},
    resetHint: { text: '', cls: '' },
    resetLoading: false,
    showNewPwd: false,
    showConfirmPwd: false,
    countdown: 0
  },

  onLoad(options) {
    i18n.apply(this);
    // 支持从设置页"忘记密码"直达重置面板
    if (options && options.panel === 'reset') {
      this.setData({ panel: 'reset' });
    }
    const resetTimer = wx.getStorageSync('swap_reset_countdown_until');
    if (resetTimer && resetTimer > Date.now()) {
      this.startCountdown(Math.ceil((resetTimer - Date.now()) / 1000));
    }
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('login_title') });
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer);
  },

  // ===== 登录面板 =====
  onLoginEmail(e) {
    this.setData({ 'loginForm.email': e.detail.value.trim() });
    if (this.data.loginErrors.email) this.setData({ 'loginErrors.email': '' });
  },

  onLoginPassword(e) {
    this.setData({ 'loginForm.password': e.detail.value });
    if (this.data.loginErrors.password) this.setData({ 'loginErrors.password': '' });
  },

  togglePassword() {
    this.setData({ showPwd: !this.data.showPwd });
  },

  toggleRemember() {
    this.setData({ remember: !this.data.remember });
  },

  handleLogin() {
    const email = this.data.loginForm.email;
    const password = this.data.loginForm.password;
    const errors = {};

    if (!email) errors.email = i18n.t('login_err_email');
    else if (email.indexOf('@') === -1) errors.email = i18n.t('login_err_email_invalid');
    if (!password) errors.password = i18n.t('login_password_ph');

    if (Object.keys(errors).length) {
      this.setData({ loginErrors: errors });
      return;
    }

    this.setData({ loginLoading: true });
    // 与网站对齐：传递 remember 参数（后端可据此决定令牌有效期）
    api.post('/wx/api/auth/login/', { email: email, password: password, remember: this.data.remember })
      .then((res) => {
        if (res.success && res.token) {
          api.setToken(res.token);
          api.cacheUser(res.user);
          const app = getApp();
          if (app) {
            app.globalData.user = res.user;
            app.globalData.userLoaded = true;
          }
          wx.showToast({ title: i18n.t('login_ok'), icon: 'success' });
          setTimeout(() => {
            const pages = getCurrentPages();
            if (pages.length > 1) {
              wx.navigateBack();
            } else {
              wx.switchTab({ url: '/pages/index/index' });
            }
          }, 800);
        } else {
          this.setData({ loginLoading: false });
          this.showLoginError(res.msg || i18n.t('login_failed'));
        }
      })
      .catch((err) => {
        this.setData({ loginLoading: false });
        const body = err && err.data ? err.data : {};
        if (body.msg) this.showLoginError(body.msg);
      });
  },

  showLoginError(msg) {
    const errors = {};
    if (msg.indexOf('未注册') !== -1) {
      errors.email = msg;
    } else if (msg.indexOf('邮箱') !== -1 || msg.indexOf('密码') !== -1) {
      errors.password = msg;
    } else {
      wx.showToast({ title: msg, icon: 'none' });
    }
    this.setData({ loginErrors: errors });
  },

  // ===== 重置面板 =====
  showResetPanel() {
    const email = this.data.loginForm.email;
    this.setData({
      panel: 'reset',
      loginErrors: {},
      'resetForm.email': this.data.resetForm.email || email
    });
  },

  showLoginPanel() {
    const email = this.data.resetForm.email;
    this.setData({
      panel: 'login',
      resetErrors: {},
      resetHint: { text: '', cls: '' },
      'loginForm.email': this.data.loginForm.email || email
    });
  },

  onResetEmail(e) {
    this.setData({ 'resetForm.email': e.detail.value.trim() });
  },

  onResetCode(e) {
    this.setData({ 'resetForm.code': e.detail.value.trim() });
    if (this.data.resetErrors.code) this.setData({ 'resetErrors.code': '' });
  },

  onNewPassword(e) {
    this.setData({ 'resetForm.newPassword': e.detail.value });
    if (this.data.resetErrors.password) this.setData({ 'resetErrors.password': '' });
  },

  onConfirmPassword(e) {
    this.setData({ 'resetForm.confirmPassword': e.detail.value });
    if (this.data.resetErrors.confirm) this.setData({ 'resetErrors.confirm': '' });
  },

  toggleNewPwd() {
    this.setData({ showNewPwd: !this.data.showNewPwd });
  },

  toggleConfirmPwd() {
    this.setData({ showConfirmPwd: !this.data.showConfirmPwd });
  },

  checkResetEmail() {
    const email = this.data.resetForm.email;
    if (!email) {
      this.setData({ resetHint: { text: '', cls: 'form-hint' } });
      return;
    }
    if (email.indexOf('@') === -1) {
      this.setData({ resetHint: { text: i18n.t('login_err_email_invalid'), cls: 'form-error' } });
      return;
    }
    this.setData({ resetHint: { text: i18n.t('reset_checking'), cls: 'form-hint' } });
    if (this._emailTimer) clearTimeout(this._emailTimer);
    this._emailTimer = setTimeout(() => {
      api.post('/wx/api/auth/check-email/', { email: email }, { silent: true })
        .then((res) => {
          if (res.exists) {
            this.setData({ resetHint: { text: '', cls: 'form-hint' } });
          } else {
            this.setData({ resetHint: { text: i18n.t('reset_email_not_registered'), cls: 'form-error' } });
          }
        })
        .catch(() => {
          this.setData({ resetHint: { text: '', cls: 'form-hint' } });
        });
    }, 300);
  },

  sendResetCode() {
    const email = this.data.resetForm.email;
    if (!email || email.indexOf('@') === -1) {
      wx.showToast({ title: i18n.t('login_err_email_invalid'), icon: 'none' });
      return;
    }
    if (this.data.countdown > 0) return;

    api.post('/wx/api/auth/send-code/', { email: email, purpose: 'reset' })
      .then((res) => {
        if (res.success) {
          wx.showToast({ title: i18n.t('reset_code_sent_email'), icon: 'none' });
          this.startCountdown(60);
        } else {
          wx.showToast({ title: res.msg || i18n.t('reset_send_failed'), icon: 'none' });
        }
      })
      .catch(() => {});
  },

  startCountdown(seconds) {
    const until = Date.now() + seconds * 1000;
    wx.setStorageSync('swap_reset_countdown_until', until);
    this.setData({ countdown: seconds });
    this._timer = setInterval(() => {
      const left = Math.ceil((wx.getStorageSync('swap_reset_countdown_until') - Date.now()) / 1000);
      if (left > 0) {
        this.setData({ countdown: left });
      } else {
        clearInterval(this._timer);
        this._timer = null;
        wx.removeStorageSync('swap_reset_countdown_until');
        this.setData({ countdown: 0 });
      }
    }, 1000);
  },

  handleReset() {
    const f = this.data.resetForm;
    const errors = {};

    if (!f.email || f.email.indexOf('@') === -1) {
      this.setData({ resetHint: { text: i18n.t('login_err_email_invalid'), cls: 'form-error' } });
      return;
    }
    if (!f.code) errors.code = i18n.t('register_code_ph');
    if (!f.newPassword || f.newPassword.length < 6) errors.password = i18n.t('reset_err_pwd_short');
    if (f.newPassword !== f.confirmPassword) errors.confirm = i18n.t('reset_err_pwd_mismatch');

    if (Object.keys(errors).length) {
      this.setData({ resetErrors: errors });
      return;
    }

    this.setData({ resetLoading: true });
    api.post('/wx/api/auth/reset-password/', {
      email: f.email,
      code: f.code,
      new_password: f.newPassword,
      confirm_password: f.confirmPassword
    })
      .then((res) => {
        this.setData({ resetLoading: false });
        if (res.success) {
          wx.showToast({ title: i18n.t('reset_ok'), icon: 'none' });
          setTimeout(() => {
            this.setData({
              panel: 'login',
              'resetForm.code': '',
              'resetForm.newPassword': '',
              'resetForm.confirmPassword': '',
              'loginForm.email': f.email
            });
          }, 800);
        } else {
          this.showResetError(res.msg || i18n.t('reset_failed'));
        }
      })
      .catch((err) => {
        this.setData({ resetLoading: false });
        const body = err && err.data ? err.data : {};
        if (body.msg) this.showResetError(body.msg);
      });
  },

  showResetError(msg) {
    const errors = {};
    if (msg.indexOf('验证码') !== -1) {
      errors.code = msg;
    } else if (msg.indexOf('不一致') !== -1) {
      errors.confirm = msg;
    } else if (msg.indexOf('密码') !== -1) {
      errors.password = msg;
    } else if (msg.indexOf('邮箱') !== -1 || msg.indexOf('未注册') !== -1) {
      this.setData({ resetHint: { text: msg, cls: 'form-error' } });
      return;
    } else {
      wx.showToast({ title: msg, icon: 'none' });
      return;
    }
    this.setData({ resetErrors: errors });
  },

  goRegister() {
    wx.navigateTo({ url: '/pages/register/register' });
  }
});
