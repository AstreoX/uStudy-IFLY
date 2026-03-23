import config from '@/config'

const { TOKEN_KEY, USER_KEY, CARD_ORDER_KEY } = config

export function getTokens() {
  try {
    const data = uni.getStorageSync(TOKEN_KEY)
    return data ? JSON.parse(data) : null
  } catch (error) {
    return null
  }
}

export function setTokens(tokens) {
  uni.setStorageSync(TOKEN_KEY, JSON.stringify(tokens))
}

export function removeTokens() {
  uni.removeStorageSync(TOKEN_KEY)
}

export function getUser() {
  try {
    const data = uni.getStorageSync(USER_KEY)
    return data ? JSON.parse(data) : null
  } catch (error) {
    return null
  }
}

export function setUser(user) {
  uni.setStorageSync(USER_KEY, JSON.stringify(user))
}

export function removeUser() {
  uni.removeStorageSync(USER_KEY)
}

export function clearAuth() {
  removeTokens()
  removeUser()
}

export function getCardOrder() {
  try {
    const data = uni.getStorageSync(CARD_ORDER_KEY)
    if (!data) return null
    const parsed = JSON.parse(data)
    return Array.isArray(parsed) ? parsed : null
  } catch (error) {
    return null
  }
}

export function setCardOrder(spaceIds) {
  try {
    uni.setStorageSync(CARD_ORDER_KEY, JSON.stringify(spaceIds))
  } catch (error) {
    // Storage write failed - app can continue without persistence
  }
}

export function clearCardOrder() {
  uni.removeStorageSync(CARD_ORDER_KEY)
}

// ========== Update Preferences ==========
const UPDATE_PREFS_KEY = config.UPDATE_STORAGE_KEY

export function getUpdatePrefs() {
  try {
    const data = uni.getStorageSync(UPDATE_PREFS_KEY)
    return data ? JSON.parse(data) : { skippedVersionCode: 0, lastCheckTime: 0 }
  } catch (error) {
    return { skippedVersionCode: 0, lastCheckTime: 0 }
  }
}

export function setUpdatePrefs(prefs) {
  try {
    uni.setStorageSync(UPDATE_PREFS_KEY, JSON.stringify(prefs))
  } catch (error) {
    // Storage write failed
  }
}

// ========== Announcement Preferences ==========
const ANNOUNCEMENT_PREFS_KEY = config.ANNOUNCEMENT_STORAGE_KEY

export function getAnnouncementPrefs() {
  try {
    const currentVersion = config.APP_VERSION_CODE
    const data = uni.getStorageSync(ANNOUNCEMENT_PREFS_KEY)
    const prefs = data ? JSON.parse(data) : { dismissedIds: [], versionCode: 0 }

    // 版本更新时重置 dismissedIds，确保用户能看到新版本公告
    if (prefs.versionCode < currentVersion) {
      const newPrefs = { dismissedIds: [], versionCode: currentVersion }
      setAnnouncementPrefs(newPrefs)
      return newPrefs
    }
    return prefs
  } catch (error) {
    return { dismissedIds: [], versionCode: config.APP_VERSION_CODE }
  }
}

export function setAnnouncementPrefs(prefs) {
  try {
    uni.setStorageSync(ANNOUNCEMENT_PREFS_KEY, JSON.stringify(prefs))
  } catch (error) {
    // Storage write failed
  }
}

// ========== Selected Model ==========
const SELECTED_MODEL_KEY = config.SELECTED_MODEL_KEY

export function getSelectedModelId() {
  return uni.getStorageSync(SELECTED_MODEL_KEY) || null
}

export function setSelectedModelId(id) {
  if (id) {
    uni.setStorageSync(SELECTED_MODEL_KEY, id)
  } else {
    uni.removeStorageSync(SELECTED_MODEL_KEY)
  }
}

// ========== Thinking Mode ==========
const THINKING_MODE_KEY = config.THINKING_MODE_KEY

export function getThinkingMode() {
  const val = uni.getStorageSync(THINKING_MODE_KEY)
  // 未设置过 → 默认开启
  if (val === '') return true
  return val === 'true'
}

export function setThinkingMode(enabled) {
  uni.setStorageSync(THINKING_MODE_KEY, enabled ? 'true' : 'false')
}

// ========== Quiz Evaluation Result ==========
const QUIZ_EVAL_KEY = config.QUIZ_EVALUATION_KEY

export function getQuizEvaluationResult() {
  try {
    const data = uni.getStorageSync(QUIZ_EVAL_KEY)
    return data || null
  } catch (error) {
    return null
  }
}

export function setQuizEvaluationResult(result) {
  uni.setStorageSync(QUIZ_EVAL_KEY, result)
}

export function removeQuizEvaluationResult() {
  uni.removeStorageSync(QUIZ_EVAL_KEY)
}
