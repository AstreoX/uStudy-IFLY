<template>
  <view class="login-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Back Button -->
    <view class="back-btn" @tap="handleBack">
      <text class="back-icon">&#x2190;</text>
    </view>

    <!-- Content Area -->
    <view class="content-area">
      <!-- Title Section -->
      <view class="title-section">
        <text class="title-main">欢迎回来</text>
        <text class="title-sub">登录您的 uStudy 账户</text>
      </view>

      <!-- Form Section -->
      <view class="form-section">
        <!-- Email Input -->
        <view class="form-group">
          <text class="form-label">邮箱</text>
          <input
            class="form-input"
            :class="{ error: errors.email }"
            type="text"
            v-model="form.email"
            placeholder="请输入邮箱地址"
            @blur="validateEmail"
          />
          <text v-if="errors.email" class="error-message">{{ errors.email }}</text>
        </view>

        <!-- Password Input -->
        <view class="form-group">
          <text class="form-label">密码</text>
          <view class="input-wrapper">
            <input
              class="form-input"
              :class="{ error: errors.password }"
              :type="showPassword ? 'text' : 'password'"
              v-model="form.password"
              placeholder="请输入密码"
              @blur="validatePassword"
            />
            <view class="toggle-password" @tap="togglePassword">
              <text class="toggle-icon">{{ showPassword ? '🙈' : '👁️' }}</text>
            </view>
          </view>
          <text v-if="errors.password" class="error-message">{{ errors.password }}</text>
        </view>

        <!-- Forgot Password Link -->
        <view class="forgot-password" @tap="handleForgotPassword">
          <text class="forgot-text">忘记密码？</text>
        </view>
      </view>

      <!-- Buttons Section -->
      <view class="buttons-section">
        <button
          class="btn login-btn"
          :class="{ disabled: isSubmitting }"
          :disabled="isSubmitting"
          @tap="handleLogin"
        >
          <text class="btn-text">{{ isSubmitting ? '登录中...' : '登录' }}</text>
        </button>

        <view class="register-link" @tap="handleGoRegister">
          <text class="register-text">没有账户？</text>
          <text class="register-text-highlight">注册</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getMe, login } from '@/api/auth'
import { setTokens } from '@/utils/storage'
import { useUserStore } from '@/store/user'

export default {
  data() {
    return {
      form: {
        email: '',
        password: ''
      },
      errors: {
        email: '',
        password: ''
      },
      showPassword: false,
      isSubmitting: false
    }
  },
  methods: {
    handleBack() {
      uni.navigateBack()
    },

    togglePassword() {
      this.showPassword = !this.showPassword
    },

    validateEmail() {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!this.form.email) {
        this.errors.email = '请输入邮箱地址'
        return false
      }
      if (!emailRegex.test(this.form.email)) {
        this.errors.email = '请输入有效的邮箱地址'
        return false
      }
      this.errors.email = ''
      return true
    },

    validatePassword() {
      if (!this.form.password) {
        this.errors.password = '请输入密码'
        return false
      }
      this.errors.password = ''
      return true
    },

    validateForm() {
      const emailValid = this.validateEmail()
      const passwordValid = this.validatePassword()
      return emailValid && passwordValid
    },

    getErrorMessage(error, fallback) {
      const detail = error?.data?.detail
      if (typeof detail === 'string') {
        return detail
      }
      if (detail && typeof detail === 'object') {
        return detail.message || fallback
      }
      return fallback
    },

    async handleLogin() {
      if (!this.validateForm()) {
        return
      }

      this.isSubmitting = true

      try {
        const tokenResp = await login({
          email: this.form.email,
          password: this.form.password
        })

        setTokens({
          access_token: tokenResp.access_token,
          refresh_token: tokenResp.refresh_token
        })

        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)

        uni.showToast({
          title: '登录成功',
          icon: 'success'
        })

        setTimeout(() => {
          uni.reLaunch({
            url: '/pages/index/index'
          })
        }, 800)
      } catch (error) {
        console.error('Login failed:', error)
        const message = this.getErrorMessage(error, '登录失败，请重试')
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        this.isSubmitting = false
      }
    },

    handleForgotPassword() {
      uni.navigateTo({
        url: '/pages/forgotPassword/forgotPassword'
      })
    },

    handleGoRegister() {
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

/* Back Button */
.back-btn {
  position: absolute;
  top: 100rpx;
  left: 30rpx;
  width: 80rpx;
  height: 80rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 50%;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.back-icon {
  font-size: 40rpx;
  color: #FFFFFF;
}

/* Content Area */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-top: 200rpx;
  position: relative;
  z-index: 1;
}

/* Title Section */
.title-section {
  margin-bottom: 60rpx;
}

.title-main {
  font-size: 64rpx;
  font-weight: 700;
  color: #FFFFFF;
  display: block;
  margin-bottom: 16rpx;
}

.title-sub {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.6);
  display: block;
}

/* Form Section */
.form-section {
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 12rpx;
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.form-input {
  width: 100%;
  height: 100rpx;
  padding: 0 32rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  color: #FFFFFF;
  font-size: 32rpx;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition: border-color 0.2s ease, background 0.2s ease;
  box-sizing: border-box;
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.form-input:focus {
  border-color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.12);
}

.form-input.error {
  border-color: #EF4444;
}

.toggle-password {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  padding: 10rpx;
}

.toggle-icon {
  font-size: 32rpx;
}

.error-message {
  font-size: 24rpx;
  color: #EF4444;
  margin-top: 8rpx;
}

/* Forgot Password */
.forgot-password {
  display: flex;
  justify-content: flex-end;
  margin-top: 8rpx;
}

.forgot-text {
  font-size: 26rpx;
  color: #007AFF;
}

/* Buttons Section */
.buttons-section {
  margin-top: auto;
  padding-bottom: 100rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
}

.btn {
  width: 100%;
  height: 96rpx;
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  transition: opacity 0.2s ease, transform 0.15s ease;
}

.btn::after {
  border: none;
}

.btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

.login-btn {
  background-color: #007AFF;
}

.login-btn.disabled {
  opacity: 0.6;
}

.btn-text {
  font-size: 34rpx;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: 1rpx;
}

.register-link {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 20rpx;
}

.register-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.6);
}

.register-text-highlight {
  font-size: 28rpx;
  color: #007AFF;
  margin-left: 8rpx;
}
</style>
