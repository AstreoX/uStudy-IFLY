<template>
  <view class="login-container" :class="pageThemeClass">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
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
import homeThemePageMixin from '@/mixins/homeThemePageMixin'

export default {
  mixins: [homeThemePageMixin],
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
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
    this.email = decodeURIComponent(options.email || '')
    this.token = decodeURIComponent(options.token || '')
  },
  onShow() {
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
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

<style scoped>
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

.login-container.theme-light {
  background:
    radial-gradient(circle at top left, rgba(47, 110, 234, 0.12), transparent 36%),
    radial-gradient(circle at bottom right, rgba(230, 126, 34, 0.1), transparent 32%),
    linear-gradient(180deg, #F7F1E8 0%, #F3EDE3 48%, #EFE6DA 100%);
}

.login-container.theme-light .aurora-bg .aurora-blob-1 {
  background: radial-gradient(circle, rgba(47, 110, 234, 0.46) 0%, rgba(47, 110, 234, 0.14) 42%, transparent 72%);
}

.login-container.theme-light .aurora-bg .aurora-blob-2 {
  background: radial-gradient(circle, rgba(228, 123, 40, 0.34) 0%, rgba(228, 123, 40, 0.12) 42%, transparent 72%);
}

.login-container.theme-light .aurora-bg .aurora-blob-3 {
  background: radial-gradient(circle, rgba(226, 167, 73, 0.18) 0%, rgba(226, 167, 73, 0.06) 42%, transparent 72%);
}

.login-container.theme-light .back-btn {
  background: rgba(255, 250, 244, 0.84);
  border: 1rpx solid rgba(63, 53, 42, 0.1);
  box-shadow: 0 14rpx 36rpx rgba(118, 101, 80, 0.14);
}

.login-container.theme-light .back-icon {
  color: #1F1A16;
}

.login-container.theme-light .title-main {
  color: #1F1A16;
}

.login-container.theme-light .title-sub,
.login-container.theme-light .form-label {
  color: rgba(31, 26, 22, 0.62);
}

.login-container.theme-light .form-input {
  background: rgba(255, 250, 244, 0.86);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 18rpx 48rpx rgba(118, 101, 80, 0.12);
  color: #1F1A16;
}

.login-container.theme-light .form-input::placeholder {
  color: rgba(31, 26, 22, 0.36);
}

.login-container.theme-light .form-input:focus {
  border-color: rgba(47, 110, 234, 0.26);
  background: rgba(255, 255, 255, 0.9);
}

.login-container.theme-light .toggle-icon {
  color: #2F6EEA;
}

.login-container.theme-light .btn.login-btn {
  background: linear-gradient(135deg, #2F6EEA 0%, #4C86F0 100%);
  border-color: transparent;
  box-shadow: 0 14rpx 34rpx rgba(47, 110, 234, 0.18);
}
</style>
