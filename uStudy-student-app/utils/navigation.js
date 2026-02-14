/**
 * Navigation utility functions for uni-app
 * Provides consistent navigation behavior across all platforms
 */

/**
 * 统一返回导航函数
 * @param {Object} options - 配置选项
 * @param {number} options.delta - 返回层数 (默认: 1)
 * @param {string} options.fallbackUrl - 返回失败时的回退页面 (默认: '/pages/index/index')
 * @param {number} options.animationDuration - APP-PLUS 动画时长 (默认: 300)
 */
export function goBack(options = {}) {
  const {
    delta = 1,
    fallbackUrl = '/pages/index/index',
    animationDuration = 300
  } = options

  const handleFail = () => {
    uni.reLaunch({ url: fallbackUrl })
  }

  // #ifdef APP-PLUS
  uni.navigateBack({
    delta,
    animationType: 'slide-out-right',
    animationDuration,
    fail: handleFail
  })
  // #endif

  // #ifndef APP-PLUS
  uni.navigateBack({
    delta,
    fail: handleFail
  })
  // #endif
}
