const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const { BASE_URL } = require('../../config');

// 后端分类 key -> i18n 字典 cat_* key（与 images/cat-*.png 对应）
const CAT_LABEL = {
  daily: 'cat_life',
  clothing: 'cat_clothes'
};

// 媒体地址兜底：后端正常返回绝对地址，若为相对路径则拼接 BASE_URL
function fixUrl(u) {
  if (!u) return '';
  return u.indexOf('http') === 0 ? u : BASE_URL + u;
}

Page({
  data: {
    keyword: '',
    category: '',
    tradeType: '',
    minPrice: '',
    maxPrice: '',
    school: '',
    sort: 'newest',
    categories: [],
    goods: [],
    count: 0,
    page: 1,
    numPages: 1,
    hasNext: false,
    hasPrevious: false,
    filterShow: false,
    // 抽屉内临时编辑值
    draftMinPrice: '',
    draftMaxPrice: '',
    draftSchool: ''
  },

  onLoad(options) {
    i18n.apply(this);
    const updates = {};
    if (options.keyword) updates.keyword = decodeURIComponent(options.keyword);
    if (options.category) updates.category = options.category;
    if (options.trade_type) updates.tradeType = options.trade_type;
    if (options.school) updates.school = decodeURIComponent(options.school);
    if (options.min_price) updates.minPrice = options.min_price;
    if (options.max_price) updates.maxPrice = options.max_price;
    if (options.sort) updates.sort = options.sort;
    if (Object.keys(updates).length) this.setData(updates);

    api.get('/wx/api/home/', null, { silent: true })
      .then((res) => {
        const categories = (res.categories || []).map((c) => {
          return Object.assign({}, c, { labelKey: CAT_LABEL[c.key] || ('cat_' + c.key) });
        });
        this.setData({ categories: categories });
      })
      .catch(() => {});
    this.loadGoods();
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('list_title') });
  },

  onPullDownRefresh() {
    this.setData({ page: 1 });
    this.loadGoods().then(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.hasNext) {
      this.setData({ page: this.data.page + 1 });
      this.loadGoods(true);
    }
  },

  loadGoods(append) {
    const d = this.data;
    const params = {
      keyword: d.keyword,
      category: d.category,
      trade_type: d.tradeType,
      min_price: d.minPrice,
      max_price: d.maxPrice,
      school: d.school,
      sort: d.sort,
      page: d.page
    };
    return api.get('/wx/api/goods/', params, { silent: true })
      .then((res) => {
        const goods = (res.goods || []).map((g) => Object.assign({}, g, { image: fixUrl(g.image) }));
        this.setData({
          goods: append ? d.goods.concat(goods) : goods,
          count: res.count || 0,
          numPages: res.num_pages || 1,
          page: res.page || 1,
          hasNext: res.has_next || false,
          hasPrevious: res.has_previous || false
        });
        if (!append) wx.pageScrollTo({ scrollTop: 0, duration: 200 });
      })
      .catch(() => { });
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  clearKeyword() {
    this.setData({ keyword: '', page: 1 });
    this.loadGoods();
  },

  doSearch() {
    this.setData({ page: 1 });
    this.loadGoods();
  },

  goPublish() {
    if (!api.isLogin()) {
      wx.showToast({ title: i18n.t('api_please_login'), icon: 'none' });
      setTimeout(() => wx.navigateTo({ url: '/pages/login/login' }), 600);
      return;
    }
    wx.navigateTo({ url: '/pages/publish/publish' });
  },

  onSort(e) {
    const sort = e.currentTarget.dataset.sort;
    if (sort === this.data.sort) return;
    this.setData({ sort: sort, page: 1 });
    this.loadGoods();
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.currentTarget.dataset.id });
  },

  prevPage() {
    if (!this.data.hasPrevious) return;
    this.setData({ page: this.data.page - 1 });
    this.loadGoods();
  },

  nextPage() {
    if (!this.data.hasNext) return;
    this.setData({ page: this.data.page + 1 });
    this.loadGoods();
  },

  // ===== 筛选抽屉 =====
  openFilter() {
    this.setData({
      filterShow: true,
      draftMinPrice: this.data.minPrice,
      draftMaxPrice: this.data.maxPrice,
      draftSchool: this.data.school
    });
  },

  closeFilter() {
    this.setData({ filterShow: false });
  },

  onPickCategory(e) {
    const key = e.currentTarget.dataset.category || '';
    this.setData({ category: key, filterShow: false, page: 1 });
    this.loadGoods();
  },

  onPickTrade(e) {
    const val = e.currentTarget.dataset.trade || '';
    this.setData({ tradeType: val, filterShow: false, page: 1 });
    this.loadGoods();
  },

  onMinPrice(e) {
    this.setData({ draftMinPrice: e.detail.value });
  },

  onMaxPrice(e) {
    this.setData({ draftMaxPrice: e.detail.value });
  },

  onSchoolInput(e) {
    this.setData({ draftSchool: e.detail.value.trim() });
  },

  resetFilter() {
    this.setData({
      category: '',
      tradeType: '',
      minPrice: '',
      maxPrice: '',
      school: '',
      draftMinPrice: '',
      draftMaxPrice: '',
      draftSchool: '',
      filterShow: false,
      page: 1
    });
    this.loadGoods();
  },

  applyFilter() {
    this.setData({
      minPrice: this.data.draftMinPrice,
      maxPrice: this.data.draftMaxPrice,
      school: this.data.draftSchool,
      filterShow: false,
      page: 1
    });
    this.loadGoods();
  }
});
