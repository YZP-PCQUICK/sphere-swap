const i18n = require('../../utils/i18n');
const settingsStore = require('../../utils/settings');

Component({
  data: {
    enabled: false,
    expanded: false,
    t: {}
  },

  lifetimes: {
    attached() {
      this.setData({
        enabled: settingsStore.getQuickNav(),
        t: i18n.dictFor()
      });
    }
  },

  pageLifetimes: {
    // 页面每次显示时同步开关状态与语言文案
    show() {
      this.setData({
        enabled: settingsStore.getQuickNav(),
        t: i18n.dictFor()
      });
    }
  },

  methods: {
    // 语言切换后由页面调用，刷新文案
    refresh() {
      this.setData({ t: i18n.dictFor() });
    },

    toggle() {
      this.setData({ expanded: !this.data.expanded });
    },

    goHome() {
      this.setData({ expanded: false });
      wx.switchTab({ url: '/pages/index/index' });
    },

    goList() {
      this.setData({ expanded: false });
      wx.navigateTo({ url: '/pages/list/list' });
    },

    goPublish() {
      this.setData({ expanded: false });
      if (!getApp().globalData.user) {
        wx.showToast({ title: i18n.t('api_please_login'), icon: 'none' });
        return;
      }
      wx.navigateTo({ url: '/pages/publish/publish' });
    }
  }
});
