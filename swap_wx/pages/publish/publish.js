const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

// 后端分类 key -> i18n 字典 cat_* key（与 images/cat-*.png 对应）
const CAT_LABEL = {
  daily: 'cat_life',
  clothing: 'cat_clothes'
};

// 与网站 publish.html 一致：最多6张、单张不超过20MB
const MAX_IMAGES = 6;
const MAX_IMAGE_SIZE = 20 * 1024 * 1024;

Page({
  data: {
    form: {
      title: '',
      price: '',
      original_price: '',
      description: '',
      category: '',
      sub_category: '',
      trade_type: 'pickup',
      school: '',
      allow_repeat: false
    },
    categories: [],
    // 学校默认值（与网站一致：默认取用户资料中的学校）
    schoolDefault: '',
    schoolHint: '',
    images: [],
    // 本地路径 -> tmp_id 映射（对应 /wx/api/goods/upload-image/ 返回）
    tmpIds: [],
    submitting: false
  },

  onLoad() {
    i18n.apply(this);
    this.loadCategories();
    this.prefillSchool();
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('publish_title') });
  },

  loadCategories() {
    const app = getApp();
    if (app && app.globalData.categories && app.globalData.categories.length) {
      this.setData({ categories: this.wrapCategories(app.globalData.categories) });
      return;
    }
    api.get('/wx/api/home/', null, { silent: true })
      .then((res) => {
        if (app) app.globalData.categories = res.categories || [];
        this.setData({ categories: this.wrapCategories(res.categories || []) });
      })
      .catch(() => { });
  },

  wrapCategories(list) {
    return list.map((c) => Object.assign({}, c, {
      labelKey: CAT_LABEL[c.key] || ('cat_' + c.key),
      icon: '/images/cat-' + c.key + '.png'
    }));
  },

  // 学校预填：优先全局/本地缓存的用户资料，缺失时静默拉取
  prefillSchool() {
    const app = getApp();
    const cached = (app && app.globalData.user) || api.getCachedUser();
    if (cached && cached.school) {
      this.applySchoolDefault(cached.school);
      return;
    }
    if (!api.isLogin()) return;
    api.get('/wx/api/user/me/', null, { silent: true })
      .then((res) => {
        const user = res && res.user;
        if (user && user.school && !this.data.form.school) {
          if (app) app.globalData.user = user;
          this.applySchoolDefault(user.school);
        }
      })
      .catch(() => { });
  },

  applySchoolDefault(school) {
    this.setData({
      schoolDefault: school,
      schoolHint: i18n.t('publish_school_default', { n: school }),
      'form.school': school
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ ['form.' + field]: e.detail.value });
  },

  pickCategory(e) {
    this.setData({ 'form.category': e.currentTarget.dataset.key });
  },

  pickTradeType(e) {
    this.setData({ 'form.trade_type': e.currentTarget.dataset.value });
  },

  toggleRepeat() {
    this.setData({ 'form.allow_repeat': !this.data.form.allow_repeat });
  },

  chooseImage() {
    const left = MAX_IMAGES - this.data.images.length;
    if (left <= 0) {
      wx.showToast({ title: i18n.t('publish_images_tip'), icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: left,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        // 与网站一致：单张不超过20MB，超出提示并跳过
        const okPaths = [];
        let seq = this.data.images.length;
        for (const f of res.tempFiles) {
          seq += 1;
          if (f.size > MAX_IMAGE_SIZE) {
            wx.showToast({ title: i18n.t('publish_err_img_too_big', { n: seq }), icon: 'none' });
            continue;
          }
          okPaths.push(f.tempFilePath);
          if (this.data.images.length + okPaths.length >= MAX_IMAGES) break;
        }
        this.uploadImages(okPaths);
      }
    });
  },

  uploadImages(paths) {
    if (!paths.length) return;
    wx.showLoading({ title: i18n.t('publish_uploading_images'), mask: true });
    // 单张失败不影响其余图片（服务端校验失败会自动 toast）
    const tasks = paths.map((p) =>
      api.upload('/wx/api/goods/upload-image/', p, 'image')
        .then((r) => ({ path: p, tmpId: r.tmp_id }))
        .catch(() => null)
    );
    Promise.all(tasks)
      .then((results) => {
        wx.hideLoading();
        const ok = results.filter((r) => r && r.tmpId !== undefined && r.tmpId !== null);
        if (!ok.length) return;
        this.setData({
          images: this.data.images.concat(ok.map((r) => r.path)),
          tmpIds: this.data.tmpIds.concat(ok.map((r) => r.tmpId))
        });
      })
      .catch(() => { wx.hideLoading(); });
  },

  removeImage(e) {
    const index = Number(e.currentTarget.dataset.index);
    const images = this.data.images.slice();
    const tmpIds = this.data.tmpIds.slice();
    images.splice(index, 1);
    tmpIds.splice(index, 1);
    this.setData({ images: images, tmpIds: tmpIds });
  },

  previewImage(e) {
    const index = Number(e.currentTarget.dataset.index);
    wx.previewImage({ current: this.data.images[index], urls: this.data.images });
  },

  // 校验顺序与提示与网站 handlePublish 一致：
  // 图片 -> 名称 -> 价格 -> 描述 -> 分类 -> 学校
  validate() {
    const f = this.data.form;
    if (!this.data.tmpIds.length) {
      wx.showToast({ title: i18n.t('publish_err_image'), icon: 'none' });
      return false;
    }
    if (!f.title.trim()) {
      wx.showToast({ title: i18n.t('publish_err_name'), icon: 'none' });
      return false;
    }
    if (!f.price.trim() || parseFloat(f.price) < 0) {
      wx.showToast({ title: i18n.t('publish_err_price'), icon: 'none' });
      return false;
    }
    if (!f.description.trim()) {
      wx.showToast({ title: i18n.t('publish_err_desc'), icon: 'none' });
      return false;
    }
    if (!f.category) {
      wx.showToast({ title: i18n.t('publish_err_cat'), icon: 'none' });
      return false;
    }
    if (!f.school.trim()) {
      wx.showToast({ title: i18n.t('publish_school_ph'), icon: 'none' });
      return false;
    }
    return true;
  },

  submit() {
    if (this.data.submitting) return;
    if (!this.validate()) return;
    const f = this.data.form;
    this.setData({ submitting: true });
    api.post('/wx/api/goods/publish/', {
      title: f.title.trim(),
      description: f.description.trim(),
      price: f.price.trim(),
      original_price: f.original_price.trim(),
      category: f.category,
      sub_category: f.sub_category.trim(),
      trade_type: f.trade_type,
      school: f.school.trim(),
      allow_repeat: f.allow_repeat,
      tmp_ids: this.data.tmpIds
    }, { loading: i18n.t('publish_publishing') })
      .then((res) => {
        this.setData({ submitting: false });
        if (res.success) {
          wx.showToast({ title: i18n.t('publish_success'), icon: 'success' });
          setTimeout(() => {
            wx.redirectTo({ url: '/pages/detail/detail?id=' + res.goods_id });
          }, 800);
        }
      })
      .catch(() => {
        // 业务错误提示已由 api.js 统一 toast
        this.setData({ submitting: false });
      });
  }
});
