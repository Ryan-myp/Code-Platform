/**
 * 国际化语言包
 * 支持：zh-CN（默认）、en-US
 */

export const locales = {
  'zh-CN': {
    'app.name': '智能研发平台',
    'common.loading': '加载中...',
    'common.error': '出错了',
    'common.success': '操作成功',
    'auth.login': '登录',
    'auth.register': '注册',
    'nav.home': '首页',
    'nav.tasks': '任务管理',
  },
  'en-US': {
    'app.name': 'Smart R&D Platform',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.success': 'Success',
    'auth.login': 'Login',
    'auth.register': 'Register',
    'nav.home': 'Home',
    'nav.tasks': 'Tasks',
  },
}

export function t(key, lang = 'zh-CN') {
  return locales[lang]?.[key] || key
}

export function getLanguages() {
  return [
    { code: 'zh-CN', name: '简体中文' },
    { code: 'en-US', name: 'English' },
  ]
}
