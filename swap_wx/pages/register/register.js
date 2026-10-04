const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

Page({
  data: {
    form: { email: '', password: '', confirmPassword: '', code: '' },
    emailHint: { text: '', cls: 'form-hint' },
    passwordHint: { text: '', cls: 'form-hint' },
    confirmHint: { text: '', cls: 'form-hint' },
    strengthClass: '',
    codeError: '',
    loading: false,
    countdown: 0,
    emailValid: false,
    passwordValid: false,
    confirmValid: false
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer);
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('register_title') });
  },

  onEmail(e) {
    const email = e.detail.value.trim();
    this.setData({ 'form.email': email, emailValid: false });
    // 与网站对齐：输入即触发邮箱占用检测（400ms 防抖）
    this.checkEmail();
  },

  checkEmail() {
    const email = this.data.form.email;
    if (!email) {
      this.setData({ emailHint: { text: '', cls: 'form-hint' }, emailValid: false });
      return;
    }
    if (email.indexOf('@') === -1) {
      this.setData({ emailHint: { text: i18n.t('login_err_email_invalid'), cls: 'form-error' }, emailValid: false });
      return;
    }
    this.setData({ emailHint: { text: i18n.t('reset_checking'), cls: 'form-hint' }, emailValid: false });
    if (this._emailTimer) clearTimeout(this._emailTimer);
    this._emailTimer = setTimeout(() => {
      api.post('/wx/api/auth/check-email/', { email: email }, { silent: true })
        .then((res) => {
          if (res.exists) {
            this.setData({ emailHint: { text: i18n.t('reg_email_exists'), cls: 'form-error' }, emailValid: false });
          } else {
            this.setData({ emailHint: { text: i18n.t('reg_email_ok'), cls: 'form-success' }, emailValid: true });
          }
        })
        .catch(() => {
          this.setData({ emailHint: { text: '', cls: 'form-hint' } });
        });
    }, 400);
  },

  onPassword(e) {
    const pwd = e.detail.value;
    this.setData({ 'form.password': pwd });
    this.checkPassword(pwd);
  },

  checkPassword(pwd) {
    if (!pwd) {
      this.setData({ passwordHint: { text: '', cls: 'form-hint' }, strengthClass: '', passwordValid: false });
      return;
    }
    if (pwd.length < 6) {
      this.setData({ passwordHint: { text: i18n.t('reg_pwd_short'), cls: 'form-error' }, strengthClass: '', passwordValid: false });
      return;
    }
    let strength = 0;
    if (pwd.length >= 8) strength++;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) strength++;
    if (/\d/.test(pwd)) strength++;
    if (/[^a-zA-Z0-9]/.test(pwd)) strength++;

    let cls = 'strength-weak';
    let text = i18n.t('reg_strength_weak');
    if (strength <= 1) {
      cls = 'strength-weak';
      text = i18n.t('reg_strength_weak');
    } else if (strength <= 2) {
      cls = 'strength-medium';
      text = i18n.t('reg_strength_medium');
    } else {
      cls = 'strength-strong';
      text = i18n.t('reg_strength_strong');
    }
    this.setData({ passwordHint: { text: text, cls: 'form-hint' }, strengthClass: cls, passwordValid: true });
    if (this.data.form.confirmPassword) this.checkConfirm(pwd, this.data.form.confirmPassword);
  },

  onConfirm(e) {
    const confirm = e.detail.value;
    this.setData({ 'form.confirmPassword': confirm });
    this.checkConfirm(this.data.form.password, confirm);
  },

  checkConfirm(pwd, confirm) {
    if (!confirm) {
      this.setData({ confirmHint: { text: '', cls: 'form-hint' }, confirmValid: false });
      return;
    }
    if (pwd !== confirm) {
      this.setData({ confirmHint: { text: i18n.t('reg_pwd_mismatch_reenter'), cls: 'form-error' }, confirmValid: false });
    } else {
      this.setData({ confirmHint: { text: i18n.t('reg_pwd_match'), cls: 'form-success' }, confirmValid: true });
    }
  },

  onCode(e) {
    this.setData({ 'form.code': e.detail.value.trim() });
    if (this.data.codeError) this.setData({ codeError: '' });
  },

  sendCode() {
    const email = this.data.form.email;
    if (!email || email.indexOf('@') === -1) {
      wx.showToast({ title: i18n.t('login_err_email_invalid'), icon: 'none' });
      return;
    }
    if (this.data.countdown > 0) return;

    api.post('/wx/api/auth/send-code/', { email: email, purpose: 'register' })
      .then((res) => {
        if (res.success) {
          wx.showToast({ title: i18n.t('reset_code_sent_email'), icon: 'none' });
          this.startCountdown(60);
        } else {
          const msg = res.msg || i18n.t('reset_send_failed');
          if (msg.indexOf('邮箱') !== -1) {
            this.setData({ emailHint: { text: msg, cls: 'form-error' } });
          } else {
            this.setData({ codeError: msg });
          }
        }
      })
      .catch(() => {});
  },

  startCountdown(seconds) {
    this.setData({ countdown: seconds });
    this._timer = setInterval(() => {
      const left = this.data.countdown - 1;
      if (left > 0) {
        this.setData({ countdown: left });
      } else {
        clearInterval(this._timer);
        this._timer = null;
        this.setData({ countdown: 0 });
      }
    }, 1000);
  },

  handleRegister() {
    const f = this.data.form;

    if (!f.email || f.email.indexOf('@') === -1) {
      this.setData({ emailHint: { text: i18n.t('login_err_email_invalid'), cls: 'form-error' } });
      return;
    }
    if (!this.data.passwordValid) {
      this.setData({ passwordHint: { text: i18n.t('reg_pwd_short'), cls: 'form-error' } });
      return;
    }
    if (!this.data.confirmValid) {
      this.setData({ confirmHint: { text: i18n.t('reset_err_pwd_mismatch'), cls: 'form-error' } });
      return;
    }
    if (!f.code) {
      this.setData({ codeError: i18n.t('register_code_ph') });
      return;
    }

    this.setData({ loading: true });
    api.post('/wx/api/auth/register/', {
      email: f.email,
      password: f.password,
      confirm_password: f.confirmPassword,
      code: f.code
    })
      .then((res) => {
        if (res.success && res.token) {
          api.setToken(res.token);
          api.cacheUser(res.user);
          const app = getApp();
          if (app) {
            app.globalData.user = res.user;
            app.globalData.userLoaded = true;
          }
          wx.showToast({ title: i18n.t('reg_ok_redirect'), icon: 'none' });
          setTimeout(() => {
            const pages = getCurrentPages();
            if (pages.length > 1) {
              wx.navigateBack();
            } else {
              wx.switchTab({ url: '/pages/index/index' });
            }
          }, 1000);
        } else {
          this.setData({ loading: false });
          this.showRegisterError(res.msg || i18n.t('register_failed'));
        }
      })
      .catch((err) => {
        this.setData({ loading: false });
        const body = err && err.data ? err.data : {};
        if (body.msg) this.showRegisterError(body.msg);
      });
  },

  showRegisterError(msg) {
    if (msg.indexOf('验证码') !== -1) {
      this.setData({ codeError: msg });
    } else if (msg.indexOf('邮箱') !== -1 || msg.indexOf('未注册') !== -1) {
      this.setData({ emailHint: { text: msg, cls: 'form-error' } });
    } else if (msg.indexOf('不一致') !== -1) {
      this.setData({ confirmHint: { text: msg, cls: 'form-error' } });
    } else if (msg.indexOf('密码') !== -1) {
      this.setData({ passwordHint: { text: msg, cls: 'form-error' } });
    } else {
      wx.showToast({ title: msg, icon: 'none' });
    }
  },

  goLogin() {
    wx.navigateBack({
      fail: () => {
        wx.redirectTo({ url: '/pages/login/login' });
      }
    });
  }
});
