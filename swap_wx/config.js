// SWAP 小程序全局配置
// 后端地址（Django 服务，与网站共用同一后端和数据库）
// 本地开发：微信开发者工具需勾选「详情 -> 本地设置 -> 不校验合法域名...」
// 线上发布：改为 https 域名并在微信公众平台配置 request/uploadFile/downloadFile 合法域名
const BASE_URL = 'https://swap.pcquick.cn';

module.exports = {
  BASE_URL,
  // 微信订阅消息模板 ID（在微信公众平台「订阅消息」中申请后填入）
  // 示例: ['tmplId1', 'tmplId2']；为空数组时设置页开关仅保存状态，不弹授权
  SUBSCRIBE_TMPL_IDS: []
};
