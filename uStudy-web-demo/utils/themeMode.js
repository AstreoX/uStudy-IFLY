export const HOME_THEME_STORAGE_KEY = 'home_theme_mode'

export function normalizeThemeMode(mode) {
  return mode === 'light' ? 'light' : 'dark'
}

export function getStoredThemeMode(defaultMode = 'dark') {
  const fallback = normalizeThemeMode(defaultMode)
  try {
    return normalizeThemeMode(uni.getStorageSync(HOME_THEME_STORAGE_KEY) || fallback)
  } catch (_) {
    return fallback
  }
}

export function persistThemeMode(mode) {
  const normalizedMode = normalizeThemeMode(mode)
  try {
    uni.setStorageSync(HOME_THEME_STORAGE_KEY, normalizedMode)
  } catch (_) {}
  return normalizedMode
}
