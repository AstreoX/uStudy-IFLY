<template>
  <view class="login-container">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
    </view>

    <view class="back-btn" @tap="handleBack">
      <text class="back-icon">&#x2190;</text>
    </view>

    <view class="content-area">
      <view class="title-section">
        <text class="title-main">重置密码</text>
        <text class="title-sub">设置新的账户密码</text>
      </view>

      <view class="form-section">
        <view class="form-group">
          <text class="form-label">新密码</text>
          <view class="input-wrapper">
            <input
              class="form-input"
              :class="{ error: errors.password }"
              :type="showPassword ? 'text' : 'password'"
              v-model="form.password"
              placeholder="至少8位，含大小写+数字"
              @blur="validatePassword"
            />
            <view class="toggle-password" @tap="togglePassword">
              <text class="toggle-icon">{{ showPassword ? '🙈' : '👁️' }}</text>
            </view>
          </view>
          <text v-if="errors.password" class="error-message">{{ errors.password }}</text>
        </view>

        <view class="form-group">
          <text class="form-label">确认新密码</text>
          <view class="input-wrapper">
            <input
              class="form-input"
              :class="{ error: errors.confirmPassword }"
              :type="showConfirmPassword ? 'text' : 'password'"
              v-model="form.confirmPassword"
              placeholder="请再次输入密码"
              @blur="validateConfirmPassword"
            />
            <view class="toggle-password" @tap="toggleConfirmPassword">
              <text class="toggle-icon">{{ showConfirmPassword ? '🙈' : '👁️' }}</text>
            </view>
          </view>
          <text v-if="errors.confirmPassword" class="error-message">{{ errors.confirmPassword }}</text>
        </view>
      </view>

      <view class="buttons-section">
        <button
          class="btn login-btn"
          :class="{ disabled: isSubmitting }"
          :disabled="isSubmitting"
          @tap="handleReset"
        >
          <text class="btn-text">{{ isSubmitting ? '提交中...' : '重置密码' }}</text>
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { resetPassword } from '@/api/auth'
import { useUserStore } from '@/store/user'

export default {
  data() {
    return {
      email: '',
      token: '',
      form: {
        password: '',
        confirmPassword: ''
      },
      errors: {
        password: '',
        confirmPassword: ''
      },
      showPassword: false,
      showConfirmPassword: false,
      isSubmitting: false
    }
  },
  onLoad(options) {
    this.email = decodeURIComponent(options.email || '')
    this.token = decodeURIComponent(options.token || '')
  },
  methods: {
    handleBack() {
      uni.navigateBack()
    },

    togglePassword() {
      this.showPassword = !this.showPassword
    },

    toggleConfirmPassword() {
      this.showConfirmPassword = !this.showConfirmPassword
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

    validatePassword() {
      if (!this.form.password) {
        this.errors.password = '请输入密码'
        return false
      }
      if (this.form.password.length < 8) {
        this.errors.password = '密码至少需要8个字符'
        return false
      }
      if (!/[A-Z]/.test(this.form.password)) {
        this.errors.password = '密码需包含大写字母'
        return false
      }
      if (!/[a-z]/.test(this.form.password)) {
        this.errors.password = '密码需包含小写字母'
        return false
      }
      if (!/[0-9]/.test(this.form.password)) {
        this.errors.password = '密码需包含数字'
        return false
      }
      this.errors.password = ''
      return true
    },

    validateConfirmPassword() {
      if (!this.form.confirmPassword) {
        this.errors.confirmPassword = '请确认密码'
        return false
      }
      if (this.form.confirmPassword !== this.form.password) {
        this.errors.confirmPassword = '两次输入的密码不一致'
        return false
      }
      this.errors.confirmPassword = ''
      return true
    },

    async handleReset() {
      if (!this.token || !this.email) {
        uni.showToast({
          title: '链接无效，请重新获取验证码',
          icon: 'none'
        })
        return
      }

      const passwordValid = this.validatePassword()
      const confirmValid = this.validateConfirmPassword()
      if (!passwordValid || !confirmValid) {
        return
      }

      this.isSubmitting = true
      try {
        await resetPassword({
          email: this.email,
          verification_token: this.token,
          new_password: this.form.password
        })
        const userStore = useUserStore()
        userStore.clear()
        uni.showToast({
          title: '密码已重置',
          icon: 'success'
        })
        setTimeout(() => {
          uni.reLaunch({
            url: '/pages/login/login'
          })
        }, 800)
      } catch (error) {
        console.error('Reset password failed:', error)
        const message = this.getErrorMessage(error, '重置失败，请重试')
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        this.isSubmitting = false
      }
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

.aurora-blob-1 {
  width: 800rpx;
  height: 800rpx;
  background: radial-gradient(circle, #0066FF 0%, transparent 70%);
  top: -200rpx;
  right: -200rpx;
  animation: aurora-flow-1 12s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 700rpx;
  height: 700rpx;
  background: radial-gradient(circle, #8B5CF6 0%, transparent 70%);
  top: 20%;
  left: -200rpx;
  animation: aurora-flow-2 15s ease-in-out infinite;
}

.aurora-blob-3 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, #00FFFF 0%, transparent 70%);
  bottom: 10%;
  right: -150rpx;
  animation: aurora-flow-3 10s ease-in-out infinite;
}

.aurora-blob-4 {
  width: 500rpx;
  height: 500rpx;
  background: radial-gradient(circle, #FF00FF 0%, transparent 70%);
  bottom: 30%;
  left: 30%;
  animation: aurora-flow-4 14s ease-in-out infinite;
}

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

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-top: 200rpx;
  position: relative;
  z-index: 1;
}

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
</style>
