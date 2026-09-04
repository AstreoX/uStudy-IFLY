const LOCAL_BASE_URL = 'http://localhost:8000'
const PRODUCTION_BASE_URL = '' // H5 production uses the current origin

function resolveBaseUrl() {
  try {
    if (typeof window !== 'undefined' && window.location) {
      const host = window.location.hostname || 'localhost'
      if (host === 'ustudy.top' || host === 'www.ustudy.top') {
        return PRODUCTION_BASE_URL
      }
      return `http://${host}:8000`
    }
  } catch (error) {
    // ignore
  }

  return LOCAL_BASE_URL
}

const API_BASE_URL = resolveBaseUrl()
const TOKEN_KEY = 'ustudy_dev_tokens'
const USER_KEY = 'ustudy_dev_user'
const APP_SCHEME = 'ustudy'
const APP_DOWNLOAD_URL = ''
const MOBILE_WEB_BASE_URL = 'https://ustudy.top'

export default {
  API_BASE_URL,
  TOKEN_KEY,
  USER_KEY,
  APP_SCHEME,
  APP_DOWNLOAD_URL,
  MOBILE_WEB_BASE_URL
}
