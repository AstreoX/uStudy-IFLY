const LOCAL_BASE_URL = 'http://localhost:8000'
const PRODUCTION_BASE_URL = 'https://api.ustudy.top'

function isProduction() {
  try {
    return process.env.NODE_ENV === 'production'
  } catch (error) {
    return false
  }
}

function resolveBaseUrl() {
  if (isProduction()) {
    // Production uses dedicated API domain.
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
