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
