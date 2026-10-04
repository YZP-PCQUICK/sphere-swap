const api = require('../../utils/api');
const i18n = require('../../utils/i18n');

// 以下长文本与网站 templates/goods/privacy.html、terms.html、support.html、
// advertise.html 逐字对齐（网站无英文版，多语言模式下法律/说明类文案保持中文原文）
const PRIVACY_INTRO = 'SWAP校园二手交易平台（以下简称“我们”）尊重并保护所有使用服务用户的个人隐私权。我们会按照本隐私政策来处理和保护您的个人信息。';
const PRIVACY_SECTIONS = [
  {
    h: '1. 我们收集的信息',
    ps: ['我们可能收集以下信息：'],
    ul: [
      '您提供的注册信息（如邮箱、学校、昵称、头像等）',
      '您发布商品的信息（如商品标题、描述、价格、图片等）',
      '您的交易记录和聊天沟通记录',
      '您的浏览、搜索和平台使用行为记录'
    ]
  },
  {
    h: '2. 我们如何使用信息',
    ps: [],
    ul: [
      '提供、维护和改进我们的平台服务',
      '处理您的商品发布、交易和沟通请求',
      '向您发送服务相关的必要通知和更新',
      '检测和防止欺诈、滥用行为，保障平台安全'
    ]
  },
  {
    h: '3. 信息共享与披露',
    ps: ['我们不会向第三方共享您的个人信息，除非获得您的明确同意，或为了完成您的交易需求，或遵守法律法规的要求。我们仅会在必要范围内向服务提供商共享信息，且要求其遵守严格的保密协议。'],
    ul: []
  },
  {
    h: '4. 您的权利与选择',
    ps: [],
    ul: [
      '您可以随时访问、更新或删除您的个人账号信息',
      '您可以撤回同意我们收集特定的个人信息',
      '您可以申请注销您的平台账号'
    ]
  },
  {
    h: '5. 信息安全',
    ps: ['我们采用行业标准的安全技术和流程来保护您的个人信息免受未授权访问、使用或披露。但请注意，任何互联网传输方式都无法保证100%的安全性。'],
    ul: []
  },
  {
    h: '6. 联系我们',
    ps: ['如果您对本隐私政策有任何疑问或建议，请通过平台官方渠道与我们联系。'],
    ul: []
  }
];

const TERMS_INTRO = '欢迎使用SWAP校园二手交易平台！请您仔细阅读本用户协议（以下简称“本协议”），使用本平台即表示您同意接受本协议的所有条款和条件。';
const TERMS_SECTIONS = [
  {
    h: '1. 服务内容',
    ps: ['SWAP校园二手交易平台为校园内的用户提供闲置物品交易的信息发布、交流和交易撮合服务，帮助用户实现闲置资源的高效流转。'],
    ul: []
  },
  {
    h: '2. 用户义务',
    ps: [],
    ul: [
      '您承诺提供的注册信息真实、准确、完整',
      '您发布的商品信息真实、合法，不包含违规、违法内容',
      '您遵守国家法律法规、校园管理规定和平台规则',
      '您自行承担通过本平台进行交易的所有责任，包括但不限于商品质量、交易安全等'
    ]
  },
  {
    h: '3. 交易规范',
    ps: [],
    ul: [
      '交易双方应遵循诚实信用原则，如实沟通商品信息和交易细节',
      '平台仅提供信息中介服务，不参与交易双方的实际交易行为，不对交易的商品质量、安全性或合法性负责',
      '禁止任何形式的欺诈、虚假交易、恶意竞价等行为'
    ]
  },
  {
    h: '4. 账号管理',
    ps: [],
    ul: [
      '您需要妥善保管您的账号和密码，对您账号下的所有活动负责',
      '您不得转让、出租或共享您的账号',
      '如发现账号异常，请立即通知平台并修改密码'
    ]
  },
  {
    h: '5. 协议修改',
    ps: ['我们有权随时修改本协议的条款，修改后的协议将在平台上公布并生效。您继续使用平台即表示您同意接受修改后的协议。'],
    ul: []
  },
  {
    h: '6. 服务终止',
    ps: [],
    ul: [
      '我们有权在您违反本协议时，终止您的平台服务访问权限',
      '您也可以随时申请注销您的平台账号',
      '协议终止后，您仍需承担终止前的交易责任和义务'
    ]
  },
  {
    h: '7. 免责声明',
    ps: ['平台对因不可抗力、黑客攻击、网络故障等不可预见、不可避免的因素导致的服务中断或信息泄露不承担责任。'],
    ul: []
  },
  {
    h: '8. 联系我们',
    ps: ['如果您对本用户协议有任何疑问或建议，请通过平台官方渠道与我们联系。'],
    ul: []
  }
];

Page({
  data: {
    // tab: about 关于 / privacy 隐私政策 / terms 用户协议 / support 支持我们 / ad 广告合作
    tab: 'about',
    tabs: [
      { key: 'about', labelKey: 'about_tab_about' },
      { key: 'privacy', labelKey: 'about_tab_privacy' },
      { key: 'terms', labelKey: 'about_tab_terms' },
      { key: 'support', labelKey: 'about_tab_support' },
      { key: 'ad', labelKey: 'about_tab_ad' }
    ],
    officialSite: 'https://www.pcquick.cn',
    officialSiteText: 'www.pcquick.cn',
    // 与网站 support.html 一致的赞赏码 / advertise.html 的开发者微信二维码
    rewardImg: api.BASE_URL + '/static/images/reward_code.png',
    adQrImg: api.BASE_URL + '/static/images/contact_wechat_qr.png',
    rewardImgError: false,
    adQrImgError: false,
    // 支持我们承诺（与网站 support.html 文案一致）
    supportPromise: [
      { pre: '· 本网站', strong: '不收取任何费用', post: '，无任何盈利行为，所有功能永久免费使用。' },
      { pre: '· 您的每一笔赞赏都将', strong: '仅用于服务器租赁和网站维护', post: '，帮助 SWAP 长久运转下去。' }
    ],
    privacy: { intro: PRIVACY_INTRO, sections: PRIVACY_SECTIONS },
    terms: { intro: TERMS_INTRO, sections: TERMS_SECTIONS }
  },

  onLoad() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('about_title') });
  },

  onShow() {
    i18n.apply(this);
    wx.setNavigationBarTitle({ title: i18n.t('about_title') });
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.key;
    if (tab === this.data.tab) return;
    this.setData({ tab: tab });
    wx.pageScrollTo({ scrollTop: 0, duration: 0 });
  },

  // 官网链接：小程序无法直接跳外网，复制地址（i18n about_link_copied）
  copyOfficialSite() {
    wx.setClipboardData({
      data: this.data.officialSite,
      success: () => {
        wx.showToast({ title: i18n.t('about_link_copied'), icon: 'none' });
      }
    });
  },

  onRewardImgError() {
    this.setData({ rewardImgError: true });
  },

  onAdQrImgError() {
    this.setData({ adQrImgError: true });
  }
});
