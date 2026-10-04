const api = require('../utils/api');
const i18n = require('../utils/i18n');

Component({
  data: {
    selected: 0,
    badge: 0,
    tabs: [
      { key: 'home', path: '/pages/index/index', icon: '/images/tab-home.png', activeIcon: '/images/tab-home-active.png', label: '首页' },
      { key: 'chats', path: '/pages/chats/chats', icon: '/images/tab-msg.png', activeIcon: '/images/tab-msg-active.png', label: '消息' },
      { key: 'profile', path: '/pages/profile/profile', icon: '/images/tab-me.png', activeIcon: '/images/tab-me-active.png', label: '我的' }
    ]
  },

  lifetimes: {
    attached() {
      this.refresh();
    }
  },

  pageLifetimes: {
    show() {
      this.refresh();
    }
  },

  methods: {
    // 刷新文案与角标（页面 onShow 时触发）
    refresh() {
      const t = i18n.dictFor();
      const tabs = this.data.tabs.map(item => Object.assign({}, item, {
        label: t['tab_' + item.key] || item.label
      }));
      this.setData({ tabs });
      this.fetchBadge();
    },

    // 外部（app.refreshChatBadge）直接更新角标
    updateBadge(n) {
      this.setData({ badge: n || 0 });
    },

    fetchBadge() {
      if (!api.getToken()) {
        this.setData({ badge: 0 });
        return;
      }
      api.get('/wx/api/chats/', null, { silent: true }).then(res => {
        if (res && res.success) {
          this.setData({ badge: res.unread_total || 0 });
        }
      }).catch(() => {});
    },

    switchTab(e) {
      const { path, index } = e.currentTarget.dataset;
      if (this.data.selected === index) return;
      wx.switchTab({ url: path });
    }
  }
});
