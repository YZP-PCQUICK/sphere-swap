const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const { BASE_URL } = require('../../config');

// 媒体地址兜底：后端正常返回绝对地址，若为相对路径则拼接 BASE_URL
function fixUrl(u) {
  if (!u) return '';
  return u.indexOf('http') === 0 ? u : BASE_URL + u;
}

Page({
  data: {
    goods: [],
    isLogin: false
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('fav_title') });
    const isLogin = api.isLogin();
    this.setData({ isLogin: isLogin });
    if (isLogin) this.load();
    else this.setData({ goods: [] });
  },

  onPullDownRefresh() {
    if (api.isLogin()) {
      this.load().then(() => wx.stopPullDownRefresh());
    } else {
      wx.stopPullDownRefresh();
    }
  },

  load() {
    return api.get('/wx/api/user/favorites/', null, { silent: true })
      .then((res) => {
        const goods = (res.goods || []).map((g) => Object.assign({}, g, { image: fixUrl(g.image) }));
        this.setData({ goods: goods });
      })
      .catch(() => { });
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.currentTarget.dataset.id });
  },

  // 取消收藏（与网站 goods:toggle_favorite / wxapi goods_favorite 同一开关接口）
  unfavorite(e) {
    const id = e.currentTarget.dataset.id;
    const goods = this.data.goods;
    const target = goods.filter((g) => String(g.id) === String(id))[0];
    wx.showModal({
      title: i18n.t('fav_unfavorite'),
      content: target ? target.title : '',
      confirmText: i18n.t('confirm'),
      cancelText: i18n.t('cancel'),
      success: (res) => {
        if (!res.confirm) return;
        api.post('/wx/api/goods/favorite/', { goods_id: id })
          .then(() => {
            this.setData({
              goods: goods.filter((g) => String(g.id) !== String(id))
            });
            wx.showToast({ title: i18n.t('fav_removed'), icon: 'none' });
          })
          .catch(() => { });
      }
    });
  },

  goList() {
    wx.navigateTo({ url: '/pages/list/list' });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  }
});
