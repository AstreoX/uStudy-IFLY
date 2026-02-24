// ========== 环境配置 ==========
// 切换这里来选择连接本地还是服务器
const USE_PRODUCTION = true  // true = 连接服务器, false = 连接本地
const LOCAL_BASE_URL = 'http://localhost:8000'
const PRODUCTION_BASE_URL = 'https://api.ustudy.top'
// ==============================

function resolveBaseUrl() {
  if (USE_PRODUCTION) {
    return PRODUCTION_BASE_URL
  }

  try {
    if (typeof window !== 'undefined' && window.location) {
      const host = window.location.hostname || 'localhost'
      return `http://${host}:8000`
    }
  } catch (error) {
    // ignore
  }

  return LOCAL_BASE_URL
}

const API_BASE_URL = resolveBaseUrl()
const TOKEN_KEY = 'ustudy_tokens'
const USER_KEY = 'ustudy_user'

export default {
  API_BASE_URL,
  TOKEN_KEY,
  USER_KEY
}
