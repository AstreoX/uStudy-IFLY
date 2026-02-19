// ========== 环境配置 ==========
// 切换这里来选择连接本地还是服务器
const USE_PRODUCTION = false  // true = 连接服务器, false = 连接本地

const LOCAL_BASE_URL = 'http://localhost:8000'
const PRODUCTION_BASE_URL = 'http://121.199.164.168:8000'
// ==============================

const DEFAULT_BASE_URL = USE_PRODUCTION ? PRODUCTION_BASE_URL : LOCAL_BASE_URL

function resolveBaseUrl() {
  // 如果使用生产环境，直接返回服务器地址
  if (USE_PRODUCTION) {
    return PRODUCTION_BASE_URL
  }

  // #ifdef H5
  try {
    if (typeof window !== 'undefined' && window.location) {
      const host = window.location.hostname || 'localhost'
      return `http://${host}:8000`
    }
  } catch (error) {
    // ignore and use default
  }
  // #endif

  try {
    const info = uni.getSystemInfoSync()
    const platform = (info.platform || '').toLowerCase()
    if (platform === 'android') {
      return 'http://10.0.2.2:8000'
    }
    if (platform === 'ios') {
      return 'http://localhost:8000'
    }
  } catch (error) {
    // ignore and use default
  }
  return DEFAULT_BASE_URL
}

const API_BASE_URL = resolveBaseUrl()
const TOKEN_KEY = 'ustudy_tokens'
const USER_KEY = 'ustudy_user'
const CARD_ORDER_KEY = 'ustudy_card_order'
const APP_VERSION_NAME = '1.2.5'
const APP_VERSION_CODE = 125
const GITEE_RAW_BASE = 'https://gitee.com/Gskyer/u-study-release/raw/master'
const UPDATE_STORAGE_KEY = 'ustudy_update_prefs'
const ANNOUNCEMENT_STORAGE_KEY = 'ustudy_announcement_prefs'

export default {
  API_BASE_URL,
  TOKEN_KEY,
  USER_KEY,
  CARD_ORDER_KEY,
  APP_VERSION_NAME,
  APP_VERSION_CODE,
  GITEE_RAW_BASE,
  UPDATE_STORAGE_KEY,
  ANNOUNCEMENT_STORAGE_KEY
}
