const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

Page({
  data: {
    tab: 'goods',
    status: 'on_sale',
    tradeStatus: 'trading',
    goodsList: [],
    trades: []
  },

  onLoad(options) {
    i18n.apply(this);
    // 与网站一致：tab=goods 我发布的 / tab=trade 我的交易
    if (options.tab === 'trade') {
      this.setData({ tab: 'trade' });
    }
    wx.setNavigationBarTitle({ title: i18n.t('trans_title') });
    this.load();
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('trans_title') });
    if (api.isLogin()) this.load();
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh());
  },

  load() {
    if (!api.requireLogin()) return Promise.resolve();
    if (this.data.tab === 'goods') {
      return api.get('/wx/api/user/goods/', { status: this.data.status }, { silent: true })
        .then((res) => {
          // 与网站 meta 一致：分类名 · 浏览 N · 收藏 N
          const goodsList = (res.goods || []).map((g) => {
            g.status_name = this.goodsStatusName(g.status);
            g.meta = [
              g.category_name,
              i18n.t('trans_views_n', { n: g.views }),
              i18n.t('trans_favs_n', { n: g.favorites })
            ].join(' · ');
            return g;
          });
          this.setData({ goodsList: goodsList });
        })
        .catch(() => { });
    }
    return api.get('/wx/api/user/trades/', { status: this.data.tradeStatus }, { silent: true })
      .then((res) => {
        const trades = (res.conversations || []).map((c) => {
          // 后端 status_name 为中文，按语言映射（无对应 key 时保留后端文案）
          const statusKey = 'chat_status_' + c.status;
          const statusLabel = i18n.t(statusKey);
          if (statusLabel !== statusKey) c.status_name = statusLabel;
          // 与网站 meta 一致：卖家：xxx | 更新时间
          const peerName = (c.peer && (c.peer.nickname || c.peer.email)) || '';
          c.seller_meta = i18n.t('trans_seller_meta', { name: peerName }) +
            (c.last_message_at ? ' | ' + c.last_message_at : '');
          return c;
        });
        this.setData({ trades: trades });
      })
      .catch(() => { });
  },

  // 商品状态徽章文案（在售/已售出/已下架，与网站 get_status_display 一致）
  goodsStatusName(status) {
    const keyMap = { on_sale: 'trans_on_sale', sold: 'trans_sold', offline: 'trans_off' };
    const key = keyMap[status];
    return key ? i18n.t(key) : status;
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    if (tab === this.data.tab) return;
    this.setData({ tab: tab });
    this.load();
  },

  switchStatus(e) {
    const status = e.currentTarget.dataset.status;
    if (status === this.data.status) return;
    this.setData({ status: status });
    this.load();
  },

  switchTradeStatus(e) {
    const status = e.currentTarget.dataset.status;
    if (status === this.data.tradeStatus) return;
    this.setData({ tradeStatus: status });
    this.load();
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.currentTarget.dataset.id });
  },

  goChat(e) {
    wx.navigateTo({ url: '/pages/chat/chat?id=' + e.currentTarget.dataset.id });
  },

  // 商品状态切换（下架/标记售出/重新上架），确认文案与网站一致
  updateStatus(e) {
    const id = e.currentTarget.dataset.id;
    const status = e.currentTarget.dataset.status;
    const texts = {
      offline: i18n.t('trans_confirm_offline'),
      sold: i18n.t('trans_confirm_sold'),
      on_sale: i18n.t('trans_confirm_relist')
    };
    wx.showModal({
      title: i18n.t('trans_tip_title'),
      content: texts[status],
      confirmText: i18n.t('ok'),
      cancelText: i18n.t('cancel'),
      confirmColor: '#4A90E2',
      success: (res) => {
        if (!res.confirm) return;
        api.post('/wx/api/goods/status/', { goods_id: id, status: status })
          .then((r) => {
            if (r.success) {
              wx.showToast({ title: i18n.t('success'), icon: 'success' });
              this.load();
            }
          })
          .catch(() => { });
      }
    });
  },

  // 切换重复售卖（网站为复选框 onchange）
  toggleRepeat(e) {
    const id = e.currentTarget.dataset.id;
    const allow = e.currentTarget.dataset.allow === 'true' || e.currentTarget.dataset.allow === true;
    api.post('/wx/api/goods/toggle-repeat/', { goods_id: id, allow_repeat: allow })
      .then((r) => {
        if (r.success) {
          wx.showToast({
            title: allow ? i18n.t('trans_repeat_on_ok') : i18n.t('trans_repeat_off_ok'),
            icon: 'success'
          });
          this.load();
        }
      })
      .catch(() => { });
  },

  // 取消交易（仅 trading/confirmed 状态可取消，与网站一致）
  cancelTrade(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: i18n.t('chat_cancel_trade'),
      content: i18n.t('chat_cancel_confirm_text'),
      confirmText: i18n.t('chat_cancel_trade'),
      cancelText: i18n.t('trans_think_again'),
      confirmColor: '#F5222D',
      success: (res) => {
        if (!res.confirm) return;
        api.post('/wx/api/chat/cancel/', { conversation_id: id })
          .then((r) => {
            if (r.success) {
              wx.showToast({ title: i18n.t('chat_cancelled_tip'), icon: 'success' });
              this.load();
            }
          })
          .catch(() => { });
      }
    });
  }
});
