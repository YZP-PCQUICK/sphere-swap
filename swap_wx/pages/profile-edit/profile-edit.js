const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

Page({
  data: {
    form: {
      avatar: '',
      nickname: '',
      school: '',
      phone: '',
      bio: '',
      payment_qrcode: ''
    },
    saving: false
  },

  // 已保存的基线快照，用于判断是否有未保存的修改
  _savedSnapshot: null,

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('pe_title') });
    this.loadUser();
  },

  loadUser() {
    api.get('/wx/api/user/me/', null, { loading: i18n.t('loading') })
      .then((res) => {
        if (res.success) {
          const u = res.user;
          const form = {
            avatar: u.avatar || '',
            nickname: u.nickname || '',
            school: u.school || '',
            phone: u.phone || '',
            bio: u.bio || '',
            payment_qrcode: u.payment_qrcode || ''
          };
          this._savedSnapshot = JSON.stringify([form.nickname, form.school, form.phone, form.bio]);
          this.setData({ form });
        }
      })
      .catch(() => {});
  },

  // 是否有未保存的资料修改（收款码不算，它上传即生效）
  hasUnsavedChanges() {
    if (this._savedSnapshot === null) return false;
    const f = this.data.form;
    return JSON.stringify([f.nickname, f.school, f.phone, f.bio]) !== this._savedSnapshot;
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ ['form.' + field]: e.detail.value });
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
              this.setData({ 'form.avatar': r.avatar_url });
              // 同步全局用户缓存，保证"我的"页头像即时更新
              const cached = api.getCachedUser();
              if (cached) {
                cached.avatar = r.avatar_url;
                api.cacheUser(cached);
              }
            }
          })
          .catch(() => {});
      }
    });
  },

  save() {
    if (this.data.saving) return;
    const f = this.data.form;
    if (!f.nickname.trim()) {
      wx.showToast({ title: i18n.t('pe_err_nickname'), icon: 'none' });
      return;
    }
    this.setData({ saving: true });
    api.post('/wx/api/user/profile/', {
      nickname: f.nickname.trim(),
      school: f.school.trim(),
      phone: f.phone.trim(),
      bio: f.bio.trim()
    }, { loading: i18n.t('st_saving') })
      .then((res) => {
        this.setData({ saving: false });
        if (res.success) {
          api.cacheUser(res.user);
          const f = this.data.form;
          this._savedSnapshot = JSON.stringify([f.nickname.trim(), f.school.trim(), f.phone.trim(), f.bio.trim()]);
          wx.showToast({ title: i18n.t('pe_save_ok'), icon: 'success' });
          setTimeout(() => wx.navigateBack(), 800);
        } else {
          wx.showToast({ title: res.msg || i18n.t('pe_save_fail'), icon: 'none' });
        }
      })
      .catch((err) => {
        this.setData({ saving: false });
        const body = err && err.data ? err.data : {};
        if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
      });
  },

  changeQrcode() {
    // 有未保存的资料修改时先提醒，避免上传后页面刷新丢失
    if (this.hasUnsavedChanges()) {
      wx.showModal({
        title: i18n.t('pe_unsaved_title'),
        content: i18n.t('pe_unsaved_msg'),
        confirmText: i18n.t('pe_unsaved_save'),
        cancelText: i18n.t('pe_unsaved_upload'),
        confirmColor: '#4A90E2',
        success: (res) => {
          if (res.confirm) {
            this.save();
          } else if (res.cancel) {
            this.chooseAndUploadQrcode();
          }
        }
      });
      return;
    }
    this.chooseAndUploadQrcode();
  },

  chooseAndUploadQrcode() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath;
        api.upload('/wx/api/user/qrcode/', path, 'payment_qrcode', { loading: i18n.t('pe_uploading_qrcode') })
          .then((r) => {
            if (r.success) {
              wx.showToast({ title: i18n.t('pe_qrcode_updated'), icon: 'success' });
              this.setData({ 'form.payment_qrcode': r.payment_qrcode_url });
            }
          })
          .catch(() => {});
      }
    });
  },

  previewQrcode() {
    wx.previewImage({
      current: this.data.form.payment_qrcode,
      urls: [this.data.form.payment_qrcode]
    });
  }
});
