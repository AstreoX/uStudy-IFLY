<template>
  <view class="login-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
    </view>

    <!-- Welcome Section -->
    <view class="welcome-section">
      <view class="welcome-line">
        <text class="welcome-hi">Hi!</text>
        <text class="welcome-text">欢迎来到</text>
      </view>
      <view class="logo">
        <text class="logo-u">u</text><text class="logo-study">Study</text>
      </view>
    </view>

    <!-- Buttons Section -->
    <view class="buttons-section">
      <!-- Apple ID Button -->
      <button class="btn apple-btn" @tap="handleAppleLogin">
        <image class="apple-icon" src="/static/icons/apple-logo.svg" mode="aspectFit" />
        <text class="btn-text">使用 Apple ID 继续</text>
      </button>

      <!-- Login Button -->
      <button class="btn login-btn" @tap="handleEmailLogin">
        <text class="btn-text login-text">登录</text>
      </button>

      <!-- Register Button -->
      <button class="btn register-btn" @tap="handleRegister">
        <text class="btn-text register-text">注册</text>
      </button>
    </view>
  </view>
</template>

<script>
import { appleLogin, getMe } from '@/api/auth'
import { getTokens, setTokens, clearAuth } from '@/utils/storage'
import { useUserStore } from '@/store/user'

export default {
  data() {
    return {}
  },
  async onShow() {
    const tokens = getTokens()
    if (tokens && tokens.access_token) {
      try {
        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)
        uni.reLaunch({
          url: '/pages/index/index'
        })
      } catch (error) {
        console.error('Token validation failed on login page:', error)
        clearAuth()
        const userStore = useUserStore()
        userStore.clear()
      }
    }
  },
  methods: {
    async handleAppleLogin() {
      // #ifdef APP-PLUS
      const systemInfo = uni.getSystemInfoSync()
      if (systemInfo.platform !== 'ios') {
        uni.showToast({
          title: 'Apple 登录仅支持 iOS',
          icon: 'none'
        })
        return
      }

      try {
        uni.showLoading({ title: '登录中...' })
        const loginResult = await new Promise((resolve, reject) => {
          uni.login({
            provider: 'apple',
            success: resolve,
            fail: reject
          })
        })

        const authResult = loginResult.authResult || {}
        const idToken =
          authResult.identityToken ||
          authResult.id_token ||
          authResult.token

        if (!idToken) {
          throw new Error('Apple 登录凭证缺失')
        }

        const tokenResp = await appleLogin(idToken)
        setTokens({
          access_token: tokenResp.access_token,
          refresh_token: tokenResp.refresh_token
        })

        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)

        uni.reLaunch({
          url: '/pages/index/index'
        })
      } catch (error) {
        console.error('Apple login failed:', error)
        const detail = error?.data?.detail
        const message =
          (detail && typeof detail === 'object' ? detail.message : detail) ||
          'Apple 登录失败'
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        uni.hideLoading()
      }
      // #endif

      // #ifndef APP-PLUS
      uni.showToast({
        title: 'Apple 登录仅支持 iOS App',
        icon: 'none'
      })
      // #endif
    },
    handleEmailLogin() {
      uni.navigateTo({
        url: '/pages/emailLogin/emailLogin'
      })
    },
    handleRegister() {
      uni.navigateTo({
        url: '/pages/register/register'
      })
    }
  }
}
</script>

<style>
.login-container {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A12;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 0 50rpx;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}

/* Aurora Background */
.aurora-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120rpx);
  will-change: transform, opacity;
}

/* 蓝色光斑 - 顺时针大范围流动 */
.aurora-blob-1 {
  width: 800rpx;
  height: 800rpx;
  background: radial-gradient(circle, #0066FF 0%, transparent 70%);
  top: -200rpx;
  right: -200rpx;
  animation: aurora-flow-1 12s ease-in-out infinite;
}

/* 紫色光斑 - 逆时针流动 */
.aurora-blob-2 {
  width: 700rpx;
  height: 700rpx;
  background: radial-gradient(circle, #8B5CF6 0%, transparent 70%);
  top: 20%;
  left: -200rpx;
  animation: aurora-flow-2 15s ease-in-out infinite;
}

/* 青色光斑 - 上下脉动 */
.aurora-blob-3 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, #00FFFF 0%, transparent 70%);
  bottom: 10%;
  right: -150rpx;
  animation: aurora-flow-3 10s ease-in-out infinite;
}

/* 粉色光斑 - 对角穿梭 */
.aurora-blob-4 {
  width: 500rpx;
  height: 500rpx;
  background: radial-gradient(circle, #FF00FF 0%, transparent 70%);
  bottom: 30%;
  left: 30%;
  animation: aurora-flow-4 14s ease-in-out infinite;
}

/* 蓝色光斑动画 - 顺时针大范围流动 */
@keyframes aurora-flow-1 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.5;
  }
  25% {
    transform: translate(150rpx, 100rpx) scale(1.4);
    opacity: 0.7;
  }
  50% {
    transform: translate(100rpx, 200rpx) scale(1.2);
    opacity: 0.6;
  }
  75% {
    transform: translate(-50rpx, 100rpx) scale(1.5);
    opacity: 0.8;
  }
}

/* 紫色光斑动画 - 逆时针流动 */
@keyframes aurora-flow-2 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.4;
  }
  33% {
    transform: translate(200rpx, -100rpx) scale(1.3);
    opacity: 0.6;
  }
  66% {
    transform: translate(100rpx, 150rpx) scale(1.5);
    opacity: 0.7;
  }
}

/* 青色光斑动画 - 上下脉动 */
@keyframes aurora-flow-3 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.5;
  }
  50% {
    transform: translate(-100rpx, -150rpx) scale(1.6);
    opacity: 0.8;
  }
}

/* 粉色光斑动画 - 对角穿梭 */
@keyframes aurora-flow-4 {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.25;
  }
  50% {
    transform: translate(-150rpx, -200rpx) scale(1.4);
    opacity: 0.5;
  }
}

/* Welcome Section */
.welcome-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  width: 100%;
  padding-left: 20rpx;
  position: relative;
  z-index: 1;
}

.welcome-line {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  margin-bottom: 10rpx;
}

.welcome-hi {
  font-size: 80rpx;
  font-weight: 800;
  color: #FFFFFF;
  margin-right: 20rpx;
  letter-spacing: -2rpx;
}

.welcome-text {
  font-size: 60rpx;
  font-weight: 400;
  color: #FFFFFF;
  letter-spacing: 2rpx;
}

.logo {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  margin-top: 20rpx;
  padding-left: 220rpx;
}

.logo-u {
  font-size: 110rpx;
  font-weight: 600;
  color: #3B82F6;
}

.logo-study {
  font-size: 110rpx;
  font-weight: 700;
  color: #FFFFFF;
}

/* Buttons Section */
.buttons-section {
  width: 100%;
  padding-bottom: 100rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
  position: relative;
  z-index: 1;
}

.btn {
  width: 100%;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition: opacity 0.2s ease, transform 0.15s ease;
}

.btn::after {
  border: none;
}

.btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

/* Apple Button - Glassmorphism */
.apple-btn {
  background-color: #007AFF;
  border: 1rpx solid rgba(255, 255, 255, 0.3);
}

.apple-icon {
  width: 52rpx;
  height: 52rpx;
  margin-right: 18rpx;
  filter: brightness(0) invert(1);
}

/* Login Button - Glassmorphism */
.login-btn {
  background-color: #FFFFFF;
  border: 1rpx solid rgba(255, 255, 255, 0.4);
}

.login-text {
  color: #000000 !important;
  font-weight: 600;
}

/* Register Button - Glassmorphism */
.register-btn {
  background-color: #1C1C1E;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
}

.btn-text {
  font-size: 34rpx;
  font-weight: 500;
  color: #FFFFFF;
  letter-spacing: 1rpx;
}

.register-text {
  color: rgba(255, 255, 255, 0.8);
}
</style>
