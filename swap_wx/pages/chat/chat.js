const api = require('../../utils/api');
const i18n = require('../../utils/i18n');
const settingsStore = require('../../utils/settings');

Page({
  data: {
    convId: null,
    loaded: false,
    peerName: '',
    peerSub: '',         // 头部副标题：昵称（卖家/买家），与网站 peer_name 一致
    goods: {},
    messages: [],
    inputText: '',
    canChat: false,
    loadFailed: false,
    loadError: '',
    loadFailedText: '',
    scanPayText: '',
    tradeMode: 'none',   // none / trading / confirmed / completed / cancelled / sold
    myConfirmed: false,
    otherConfirmed: false,
    isBuyer: true,
    sellerHasQrcode: false,
    qrcodeUrl: '',
    goodsSold: false,
    scrollInto: ''
  },

  onLoad(options) {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('chat_title') });
    this.convId = options.id;
    this.storageKey = 'swap_chat_' + this.convId;
    this.lastServerId = 0;
    this._idx = 0;
    this._loginJumped = false;
    // 登录守卫（与网站 @login_required 一致）
    if (!api.requireLogin()) {
      this._needLogin = true;
      return;
    }
    this._init();
  },

  _init() {
    this._needLogin = false;
    this.loadLocal();
    this.loadMeta();
    this.poll();
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('chat_title') });
    // 登录页返回后补初始化
    if (this._needLogin && api.isLogin()) this._init();
    if (this._needLogin) return;
    this._stopTimer();
    // 与网站一致：聊天室 2 秒轮询新消息（网站 setInterval(poll, 2000)）
    this._timer = setInterval(() => this.poll(), 2000);
  },

  onHide() {
    this._stopTimer();
  },

  onUnload() {
    this._stopTimer();
  },

  _stopTimer() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  // 从本地缓存恢复历史（保留最近200条，与网站 localStorage 一致）
  loadLocal() {
    this.messages = [];
    try {
      const raw = wx.getStorageSync(this.storageKey);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          this.messages = arr;
          let maxId = 0;
          arr.forEach((m) => {
            if (m.id && m.id > maxId) maxId = m.id;
          });
          this.lastServerId = maxId;
        }
      }
    } catch (e) {
      this.messages = [];
    }
  },

  saveLocal() {
    try {
      wx.setStorageSync(this.storageKey, JSON.stringify(this.messages.slice(-200)));
    } catch (e) { }
  },

  // 获取会话基础信息（对方昵称/角色），复用会话列表接口
  // TODO: 后端缺少接口：wxapi 无「单个会话详情」接口，只能从 /wx/api/chats/ 列表中查找
  loadMeta() {
    api.get('/wx/api/chats/', null, { silent: true, noAuthJump: true })
      .then((res) => {
        const conv = (res.conversations || []).find((c) => String(c.id) === String(this.convId));
        if (conv) {
          const role = conv.is_buyer ? i18n.t('chat_role_seller') : i18n.t('chat_role_buyer');
          this.setData({
            peerName: conv.peer.nickname,
            peerSub: i18n.t('chat_peer_role', { name: conv.peer.nickname, role: role }),
            isBuyer: conv.is_buyer
          });
        }
      })
      .catch(() => { });
  },

  render() {
    const messages = (this.messages || []).map((m) => {
      this._idx += 1;
      const item = Object.assign({}, m);
      item.idx = this._idx;
      // 系统提示（后端以【系统】开头的文本，与网站 msg-sys 展示一致）
      if (m.type === 'text' && m.content && m.content.indexOf('【系统】') === 0) {
        item.is_sys = true;
      }
      return item;
    });
    const lastIdx = messages.length ? messages[messages.length - 1].idx : 0;
    this.setData({
      messages: messages,
      // 新消息到达后滚动到底部（scroll-view scroll-into-view）
      scrollInto: lastIdx ? 'msg-' + lastIdx : ''
    });
    this.saveLocal();
    // TODO: 后端缺少接口：wxapi /wx/api/chat/messages/ 未返回 my_read_max_id
    //（网站端以此渲染自己消息的「已读/未读」回执），待后端补充后再展示已读回执
  },

  upsertMessages(newMsgs) {
    if (!newMsgs || !newMsgs.length) return;
    const ids = {};
    this.messages.forEach((m) => { ids[m.id] = true; });
    let changed = false;
    let hasIncoming = false;
    newMsgs.forEach((m) => {
      if (m.id && !ids[m.id]) {
        this.messages.push(m);
        ids[m.id] = true;
        changed = true;
        if (!m.is_me) hasIncoming = true;
        if (m.id > this.lastServerId) this.lastServerId = m.id;
      }
    });
    if (changed) {
      // 收到对方新消息时按设置振动提醒
      if (hasIncoming && settingsStore.getNotifyLocal()) {
        wx.vibrateShort({ type: 'light', fail: () => { } });
        // 同步 tabBar 未读角标（当前会话已在轮询中标记已读）
        const app = getApp();
        if (app && typeof app.refreshChatBadge === 'function') {
          app.refreshChatBadge();
        }
      }
      this.render();
    }
  },

  poll() {
    if (this._receiving) return;
    this._receiving = true;
    api.get('/wx/api/chat/messages/', {
      conversation_id: this.convId,
      after_id: this.lastServerId
    }, { silent: true, noAuthJump: true })
      .then((res) => {
        this._receiving = false;
        if (!res.success) {
          this.setData({
            loadFailed: true,
            loadError: i18n.t('chat_resp_error'),
            loadFailedText: i18n.t('load_failed_tap', { reason: i18n.t('chat_resp_error') }),
            canChat: false
          });
          return;
        }

        const goods = res.goods || {};
        const goodsSold = goods.status === 'sold' && !goods.allow_repeat;
        const status = res.status;

        let tradeMode = 'trading';
        if (status === 'completed') tradeMode = 'completed';
        else if (status === 'cancelled') tradeMode = 'cancelled';
        else if (goodsSold && status !== 'confirmed') tradeMode = 'sold';
        else if (status === 'confirmed') tradeMode = 'confirmed';

        this.upsertMessages(res.messages || []);
        this.setData({
          loaded: true,
          loadFailed: false,
          goods: goods,
          sellerHasQrcode: !!res.seller_has_qrcode,
          qrcodeUrl: res.qrcode_url || '',
          goodsSold: goodsSold,
          myConfirmed: !!res.my_confirmed,
          otherConfirmed: !!res.other_confirmed,
          tradeMode: tradeMode,
          canChat: tradeMode === 'trading',
          scanPayText: goods.price !== undefined && goods.price !== null && goods.price !== ''
            ? i18n.t('chat_scan_pay', { n: goods.price })
            : ''
        });
      })
      .catch((err) => {
        this._receiving = false;
        const body = err && err.data ? err.data : (err || {});
        // 令牌失效：引导重新登录（只跳一次，避免轮询反复压栈）
        if (err && err.statusCode === 401 && !this._loginJumped) {
          this._loginJumped = true;
          api.clearToken();
          const app = getApp();
          if (app) app.clearUser();
          wx.navigateTo({ url: '/pages/login/login' });
          return;
        }
        const reason = (err && err.statusCode) ? ('HTTP ' + err.statusCode + (body.msg ? '：' + body.msg : ''))
          : ((err && err.errMsg) ? i18n.t('chat_net_error') : i18n.t('chat_unknown_error'));
        this.setData({
          loaded: true,
          loadFailed: true,
          loadError: reason,
          loadFailedText: i18n.t('load_failed_tap', { reason: reason }),
          canChat: false
        });
      });
  },

  onInputText(e) {
    this.setData({ inputText: e.detail.value });
  },

  // 发送文字（chat/send 为 form-urlencoded，用 api.postForm）
  sendText() {
    const content = (this.data.inputText || '').trim();
    if (!content || !this.data.canChat) return;
    this.setData({ inputText: '' });
    api.postForm('/wx/api/chat/send/', {
      conversation_id: this.convId,
      type: 'text',
      content: content
    }, { silent: true })
      .then((res) => {
        if (res.success && res.msg) {
          this.upsertMessages([res.msg]);
        }
      })
      .catch((err) => {
        // 发送失败恢复输入内容；含敏感词被拦截（blocked）时展示后端 msg
        this.setData({ inputText: content });
        const body = err && err.data ? err.data : (err || {});
        if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
      });
  },

  chooseImage() {
    if (!this.data.canChat) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath;
        this.sendFile('image', path);
      }
    });
  },

  chooseVideo() {
    if (!this.data.canChat) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      maxDuration: 60,
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath;
        this.sendFile('video', path);
      }
    });
  },

  // 发送图片/视频（multipart，与网站 sendFile 一致）
  sendFile(type, path) {
    wx.showLoading({ title: i18n.t('chat_sending'), mask: true });
    api.upload('/wx/api/chat/send/', path, 'file', {
      conversation_id: this.convId,
      type: type
    }, { silent: true })
      .then((res) => {
        wx.hideLoading();
        if (res.success && res.msg) {
          this.upsertMessages([res.msg]);
        }
      })
      .catch((err) => {
        wx.hideLoading();
        const body = err && err.data ? err.data : (err || {});
        if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
      });
  },

  // 图片查看大图（对应网站 zoomImg）
  previewMsgImage(e) {
    wx.previewImage({ current: e.currentTarget.dataset.url, urls: [e.currentTarget.dataset.url] });
  },

  previewQrcode() {
    wx.previewImage({ current: this.data.qrcodeUrl, urls: [this.data.qrcodeUrl] });
  },

  // 确认交易（双方确认后进入 confirmed，与网站 api_confirm 同流程）
  confirmTrade() {
    api.post('/wx/api/chat/confirm/', { conversation_id: this.convId }, { silent: true })
      .then((res) => {
        if (res.success) {
          wx.showToast({ title: i18n.t('chat_confirmed_ok'), icon: 'success' });
          this.poll();
        } else {
          wx.showToast({ title: res.msg || i18n.t('chat_op_failed'), icon: 'none' });
        }
      })
      .catch((err) => {
        const body = err && err.data ? err.data : (err || {});
        if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
      });
  },

  // 买家确认收货（交易完成，服务器聊天记录被清除，与网站 api_complete 同流程）
  completeTrade() {
    this.showConfirm(i18n.t('chat_confirm_buy'), i18n.t('chat_confirm_buy_text'), () => {
      api.post('/wx/api/chat/complete/', { conversation_id: this.convId }, { silent: true })
        .then((res) => {
          if (res.success) {
            wx.showToast({ title: i18n.t('chat_completed_ok'), icon: 'success' });
            this.poll();
          } else {
            wx.showToast({ title: res.msg || i18n.t('chat_op_failed'), icon: 'none' });
          }
        })
        .catch((err) => {
          const body = err && err.data ? err.data : (err || {});
          if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
        });
    });
  },

  // 买家取消交易（与网站 api_cancel 同流程）
  cancelTrade() {
    this.showConfirm(i18n.t('chat_cancel_trade'), i18n.t('chat_cancel_confirm_text'), () => {
      api.post('/wx/api/chat/cancel/', { conversation_id: this.convId }, { silent: true })
        .then((res) => {
          if (res.success) {
            wx.showToast({ title: i18n.t('chat_cancelled_tip'), icon: 'success' });
            this.poll();
          } else {
            wx.showToast({ title: res.msg || i18n.t('chat_op_failed'), icon: 'none' });
          }
        })
        .catch((err) => {
          const body = err && err.data ? err.data : (err || {});
          if (body.msg) wx.showToast({ title: body.msg, icon: 'none' });
        });
    });
  },

  // 自定义确认弹窗（对应网站 showConfirm）
  showConfirm(title, text, onOk) {
    wx.showModal({
      title: title,
      content: text,
      confirmText: i18n.t('ok'),
      cancelText: i18n.t('cancel'),
      confirmColor: '#4A90E2',
      success: (res) => {
        if (res.confirm && onOk) onOk();
      }
    });
  },

  // 进入商品详情（对应网站「查看商品」按钮 / goodsDetailUrl）
  goGoods() {
    if (!this.data.goods || !this.data.goods.id) return;
    wx.navigateTo({ url: '/pages/detail/detail?id=' + this.data.goods.id });
  }
});
