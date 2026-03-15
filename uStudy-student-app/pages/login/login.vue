<template>
  <view class="login-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
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
      <!-- Login Button -->
      <button class="btn login-btn" @tap="handleEmailLogin">
        <text class="btn-text">登录</text>
      </button>

      <!-- Register Button -->
      <button class="btn register-btn" @tap="handleRegister">
        <text class="btn-text register-text">注册</text>
      </button>
    </view>
  </view>
</template>

<script>
import { getMe } from '@/api/auth'
import { getTokens, clearAuth } from '@/utils/storage'
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

/* Aurora Background (Blue-Orange) */
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

/* 蓝色光晕 - 左上 */
.aurora-blob-1 {
  width: 900rpx;
  height: 900rpx;
  background: radial-gradient(circle, #1A6AFF 0%, rgba(26, 106, 255, 0.3) 40%, transparent 70%);
  top: -250rpx;
  left: -200rpx;
  animation: aurora-blue 14s ease-in-out infinite;
}

/* 橙色光晕 - 右下 */
.aurora-blob-2 {
  width: 850rpx;
  height: 850rpx;
  background: radial-gradient(circle, #FF6A1A 0%, rgba(255, 106, 26, 0.3) 40%, transparent 70%);
  bottom: -200rpx;
  right: -200rpx;
  animation: aurora-orange 16s ease-in-out infinite;
}

/* 过渡融合 - 中部 */
.aurora-blob-3 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, #FF9F45 0%, rgba(255, 159, 69, 0.15) 40%, transparent 70%);
  top: 40%;
  left: 25%;
  animation: aurora-blend 18s ease-in-out infinite;
}

@keyframes aurora-blue {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.55; }
  33% { transform: translate(60rpx, 80rpx) scale(1.15); opacity: 0.7; }
  66% { transform: translate(-30rpx, 40rpx) scale(1.05); opacity: 0.6; }
}

@keyframes aurora-orange {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
  33% { transform: translate(-70rpx, -60rpx) scale(1.1); opacity: 0.65; }
  66% { transform: translate(40rpx, -80rpx) scale(1.2); opacity: 0.55; }
}

@keyframes aurora-blend {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.2; }
  50% { transform: translate(50rpx, -40rpx) scale(1.3); opacity: 0.35; }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
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

/* Login Button - Blue (previously Apple style) */
.login-btn {
  background-color: #007AFF;
  border: 1rpx solid rgba(255, 255, 255, 0.3);
}

/* Register Button - White (previously Login style) */
.register-btn {
  background-color: #FFFFFF;
  border: 1rpx solid rgba(255, 255, 255, 0.4);
}

.register-text {
  color: #000000 !important;
  font-weight: 600;
}

.btn-text {
  font-size: 34rpx;
  font-weight: 500;
  color: #FFFFFF;
  letter-spacing: 1rpx;
}
</style>
