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
    goodsId: null,
    goods: null,
    isFavorited: false,
    isMine: false,
    isLogin: false,
    sellerOther: [],
    currentImg: 0,
    loaded: false,
    favLoading: false
  },

  onLoad(options) {
    i18n.apply(this);
    this.setData({
      goodsId: options.id,
      isLogin: api.isLogin()
    });
    this.loadDetail();
  },

  onShow() {
    i18n.apply(this);
    // 登录态可能变化（从登录页返回）
    const login = api.isLogin();
    if (login !== this.data.isLogin) {
      this.setData({ isLogin: login });
      if (login && this.data.goodsId) this.loadDetail();
    }
  },

  loadDetail() {
    const headers = this.data.isLogin ? {} : { silent: true, noAuthJump: true };
    return api.get('/wx/api/goods/' + this.data.goodsId + '/', null, headers)
      .then((res) => {
        const goods = res.goods;
        goods.images = (goods.images || []).map(fixUrl);
        if (goods.seller && goods.seller.avatar) {
          goods.seller.avatar = fixUrl(goods.seller.avatar);
        }
        const sellerOther = (res.seller_other || []).map((g) => Object.assign({}, g, { image: fixUrl(g.image) }));
        wx.setNavigationBarTitle({ title: goods.title });
        this.setData({
          goods: goods,
          isFavorited: res.is_favorited,
          isMine: res.is_mine,
          sellerOther: sellerOther,
          loaded: true
        });
      })
      .catch(() => {
        this.setData({ loaded: true });
        wx.showToast({ title: i18n.t('detail_not_found'), icon: 'none' });
        setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) }), 1200);
      });
  },

  onSwiperChange(e) {
    this.setData({ currentImg: e.detail.current });
  },

  selectImage(e) {
    this.setData({ currentImg: Number(e.currentTarget.dataset.index) });
  },

  previewImage(e) {
    const index = Number(e.currentTarget.dataset.index);
    const urls = this.data.goods.images;
    wx.previewImage({ current: urls[index], urls: urls });
  },

  toggleFavorite() {
    if (this.data.favLoading) return;
    if (!api.requireLogin(i18n.t('detail_login_fav'))) return;
    this.setData({ favLoading: true });
    api.post('/wx/api/goods/favorite/', { goods_id: this.data.goodsId })
      .then((res) => {
        this.setData({
          isFavorited: res.is_favorited,
          favLoading: false
        });
        wx.showToast({
          title: res.is_favorited ? i18n.t('fav_added') : i18n.t('fav_removed'),
          icon: 'none'
        });
      })
      .catch(() => {
        this.setData({ favLoading: false });
      });
  },

  startChat() {
    api.post('/wx/api/chat/start/', { goods_id: this.data.goodsId }, { loading: i18n.t('detail_starting_chat') })
      .then((res) => {
        if (res.success && res.conv_id) {
          wx.navigateTo({ url: '/pages/chat/chat?id=' + res.conv_id });
        } else {
          wx.showToast({ title: res.msg || i18n.t('detail_chat_fail'), icon: 'none' });
        }
      })
      .catch(() => {});
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  goMyGoods() {
    wx.navigateTo({ url: '/pages/transactions/transactions?tab=goods' });
  },

  goDetail(e) {
    wx.redirectTo({ url: '/pages/detail/detail?id=' + e.currentTarget.dataset.id });
  },

  onShareAppMessage() {
    const g = this.data.goods;
    return {
      title: g ? g.title : i18n.t('share_default_title'),
      path: '/pages/detail/detail?id=' + this.data.goodsId,
      imageUrl: g && g.images && g.images.length ? g.images[0] : ''
    };
  }
});
