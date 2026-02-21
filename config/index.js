const USE_PRODUCTION = true
const LOCAL_BASE_URL = 'http://localhost:8000'
const PRODUCTION_BASE_URL = 'http://121.199.164.168:8000'

const DEFAULT_BASE_URL = USE_PRODUCTION ? PRODUCTION_BASE_URL : LOCAL_BASE_URL

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
  return DEFAULT_BASE_URL
}

const API_BASE_URL = resolveBaseUrl()
const TOKEN_KEY = 'ustudy_tokens'
const USER_KEY = 'ustudy_user'

export default {
  API_BASE_URL,
  TOKEN_KEY,
  USER_KEY
}
