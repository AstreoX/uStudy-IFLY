export function syncThemeSystemUi(mode, options = {}) {
  const {
    lightStatusBarBackground = '#F3EDE3',
    darkStatusBarBackground = '#0A0A12'
  } = options

  const isLight = mode === 'light'

  // #ifdef APP-PLUS
  try {
    if (typeof plus !== 'undefined' && plus.navigator) {
      plus.navigator.setStatusBarStyle(isLight ? 'dark' : 'light')
      if (typeof plus.navigator.setStatusBarBackground === 'function') {
        plus.navigator.setStatusBarBackground(isLight ? lightStatusBarBackground : darkStatusBarBackground)
      }
    }
  } catch (_) {}
  // #endif
}
