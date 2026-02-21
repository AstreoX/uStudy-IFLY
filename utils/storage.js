import config from '@/config'

const { TOKEN_KEY, USER_KEY } = config

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
