const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const { BASE_URL } = require('../../config');

// 后端分类 key -> i18n 字典 cat_* key（与 images/cat-*.png 对应）
const CAT_LABEL = {
  daily: 'cat_life',
  clothing: 'cat_clothes',
  snack: 'cat_snack'
};

// 媒体地址兜底：后端正常返回绝对地址，若为相对路径则拼接 BASE_URL
function fixUrl(u) {
  if (!u) return '';
  return u.indexOf('http') === 0 ? u : BASE_URL + u;
}

Page({
  data: {
    keyword: '',
    categories: [],
    goods: [],
    ads: [],
    loading: true
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 });
      this.getTabBar().refresh();
    }
    i18n.apply(this);
    this.loadData();
  },

  onPullDownRefresh() {
    this.loadData().then(() => wx.stopPullDownRefresh());
  },

  loadData() {
    this.loadAds();
    return api.get('/wx/api/home/', null, { silent: true })
      .then((res) => {
        const categories = (res.categories || []).map((c) => {
          return Object.assign({}, c, { labelKey: CAT_LABEL[c.key] || ('cat_' + c.key) });
        });
        const goods = (res.goods || []).map((g) => Object.assign({}, g, { image: fixUrl(g.image) }));
        this.setData({
          categories: categories,
          goods: goods,
          loading: false
        });
      })
      .catch(() => {
        this.setData({ loading: false });
      });
  },

  // 首页广告轮播（网站对应 /goods/api/ads/today/ 的当日广告，16:9 轮播、自动切换、点击跳转）
  // TODO: 后端缺少接口 —— wxapi 未提供广告接口，拿到接口后在此请求并把 {id,image,link} 存入 ads 即可
  loadAds() {
    this.setData({ ads: [] });
  },

  onAdTap(e) {
    const link = e.currentTarget.dataset.link;
    if (!link) return;
    // 小程序无法直接 window.open，复制链接引导用户打开
    wx.setClipboardData({
      data: link,
      success: () => wx.showToast({ title: '链接已复制', icon: 'none' })
    });
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  doSearch() {
    const kw = (this.data.keyword || '').trim();
    wx.navigateTo({
      url: '/pages/list/list' + (kw ? '?keyword=' + encodeURIComponent(kw) : '')
    });
  },

  goAllGoods() {
    wx.navigateTo({ url: '/pages/list/list' });
  },

  goCategory(e) {
    const key = e.currentTarget.dataset.key;
    wx.navigateTo({ url: '/pages/list/list?category=' + key });
  },

  goPublish() {
    if (!api.isLogin()) {
      wx.showToast({ title: i18n.t('api_please_login'), icon: 'none' });
      setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 600);
      return;
    }
    wx.navigateTo({ url: '/pages/publish/publish' });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
  }
});
