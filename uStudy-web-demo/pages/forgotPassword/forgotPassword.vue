<template>
  <view class="forgot-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
      <view class="aurora-blob aurora-blob-5"></view>
    </view>

    <!-- Back Button -->
    <view class="back-btn" @tap="handleBack">
      <text class="back-icon">&#x2190;</text>
    </view>

    <!-- Content Wrapper -->
    <view class="content-wrapper">
      <!-- Title Section -->
      <view class="title-section">
        <text class="title-main">找回密码</text>
        <text class="title-sub">{{ stepDescription }}</text>
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
            placeholder="请输入注册时使用的邮箱"
            :disabled="step > 1"
            @blur="validateEmail"
          />
          <text v-if="errors.email" class="error-message">{{ errors.email }}</text>
        </view>

        <!-- Code Input -->
        <view class="form-group" v-if="step >= 2">
          <text class="form-label">验证码</text>
          <input
            class="form-input"
            :class="{ error: errors.code }"
            type="text"
            v-model="form.code"
            placeholder="请输入6位验证码"
            :disabled="step > 2"
            @blur="validateCode"
          />
          <text v-if="errors.code" class="error-message">{{ errors.code }}</text>
        </view>

        <!-- Step 3: New Password -->
        <view v-if="step === 3">
          <view class="form-group">
            <text class="form-label">新密码</text>
            <view class="input-wrapper">
              <input
                class="form-input"
                :class="{ error: errors.password }"
                :type="showPassword ? 'text' : 'password'"
                v-model="form.password"
                placeholder="请输入新密码（至少8位，含大小写+数字）"
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
                placeholder="请再次输入新密码"
                @blur="validateConfirmPassword"
                @confirm="handlePrimaryAction"
              />
              <view class="toggle-password" @tap="toggleConfirmPassword">
                <text class="toggle-icon">{{ showConfirmPassword ? '🙈' : '👁️' }}</text>
              </view>
            </view>
            <text v-if="errors.confirmPassword" class="error-message">{{ errors.confirmPassword }}</text>
          </view>
        </view>
      </view>

      <!-- Buttons Section -->
      <view class="buttons-section">
        <button
          class="btn primary-btn"
          :class="{ disabled: isSubmitting }"
          :disabled="isSubmitting"
          @tap="handlePrimaryAction"
        >
          <text class="btn-text">{{ primaryButtonText }}</text>
        </button>

        <view class="login-link" @tap="handleGoLogin">
          <text class="login-text">想起密码了？</text>
          <text class="login-text-highlight">返回登录</text>
        </view>
      </view>

      <!-- Toast -->
      <view v-if="toastMessage" class="toast" @tap="toastMessage = ''">
        <text class="toast-text">{{ toastMessage }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { sendCode, verifyCode, resetPassword } from '@/api/auth'
import { clearAuth } from '@/utils/storage'
import { useUserStore } from '@/store/user'

export default {
  data() {
    return {
      step: 1,
      verificationToken: '',
      form: {
        email: '',
        code: '',
        password: '',
        confirmPassword: ''
      },
      errors: {
        email: '',
        code: '',
        password: '',
        confirmPassword: ''
      },
      showPassword: false,
      showConfirmPassword: false,
      isSubmitting: false,
      toastMessage: ''
    }
  },
  computed: {
    stepDescription() {
      if (this.step === 1) return '输入注册邮箱，我们将发送验证码'
      if (this.step === 2) return '请输入邮箱收到的6位验证码'
      return '设置你的新密码'
    },
    primaryButtonText() {
      if (this.step === 1) return this.isSubmitting ? '发送中...' : '发送验证码'
      if (this.step === 2) return this.isSubmitting ? '验证中...' : '验证验证码'
      return this.isSubmitting ? '重置中...' : '重置密码'
    }
  },
  methods: {
    handleBack() {
      uni.navigateTo({
        url: '/pages/login/login'
      })
    },

    togglePassword() {
      this.showPassword = !this.showPassword
    },

    toggleConfirmPassword() {
      this.showConfirmPassword = !this.showConfirmPassword
    },

    showToast(message) {
      this.toastMessage = message
      setTimeout(() => {
        this.toastMessage = ''
      }, 3000)
    },

    getErrorMessage(error, fallback) {
      const detail = error?.data?.detail
      if (typeof detail === 'string') return detail
      if (detail && typeof detail === 'object') return detail.message || fallback
      return error?.message || fallback
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

    validateCode() {
      if (!this.form.code) {
        this.errors.code = '请输入验证码'
        return false
      }
      if (this.form.code.length !== 6) {
        this.errors.code = '验证码需为6位数字'
        return false
      }
      this.errors.code = ''
      return true
    },

    validatePassword() {
      if (!this.form.password) {
        this.errors.password = '请输入新密码'
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
        this.errors.confirmPassword = '请确认新密码'
        return false
      }
      if (this.form.confirmPassword !== this.form.password) {
        this.errors.confirmPassword = '两次输入的密码不一致'
        return false
      }
      this.errors.confirmPassword = ''
      return true
    },

    async handlePrimaryAction() {
      if (this.step === 1) {
        await this.handleSendCode()
        return
      }
      if (this.step === 2) {
        await this.handleVerifyCode()
        return
      }
      await this.handleResetPassword()
    },

    async handleSendCode() {
      if (!this.validateEmail()) return

      this.isSubmitting = true
      try {
        await sendCode({
          email: this.form.email,
          purpose: 'password_reset'
        })
        this.showToast('验证码已发送')
        this.step = 2
      } catch (error) {
        const message = this.getErrorMessage(error, '发送失败，请重试')
        this.showToast(message)
      } finally {
        this.isSubmitting = false
      }
    },

    async handleVerifyCode() {
      if (!this.validateEmail() || !this.validateCode()) return

      this.isSubmitting = true
      try {
        const resp = await verifyCode({
          email: this.form.email,
          code: this.form.code,
          purpose: 'password_reset'
        })
        this.verificationToken = resp.verification_token
        this.showToast('验证成功')
        this.step = 3
      } catch (error) {
        const message = this.getErrorMessage(error, '验证码无效')
        this.showToast(message)
      } finally {
        this.isSubmitting = false
      }
    },

    async handleResetPassword() {
      if (!this.verificationToken) {
        this.showToast('请先完成验证码验证')
        this.step = 2
        return
      }

      const passwordValid = this.validatePassword()
      const confirmValid = this.validateConfirmPassword()
      if (!passwordValid || !confirmValid) return

      this.isSubmitting = true
      try {
        await resetPassword({
          email: this.form.email,
          verification_token: this.verificationToken,
          new_password: this.form.password
        })

        clearAuth()
        const userStore = useUserStore()
        userStore.clear()

        this.showToast('密码重置成功，请重新登录')

        setTimeout(() => {
          uni.reLaunch({
            url: '/pages/login/login'
          })
        }, 1500)
      } catch (error) {
        const message = this.getErrorMessage(error, '重置失败，请重试')
        this.showToast(message)
      } finally {
        this.isSubmitting = false
      }
    },

    handleGoLogin() {
      uni.navigateTo({
        url: '/pages/login/login'
      })
    }
  }
}
</script>

<style>
.forgot-container {
  width: 100%;
  min-height: 100vh;
  background:
    radial-gradient(ellipse 70% 50% at 75% 12%, rgba(249,115,22,0.08) 0%, transparent 65%),
    radial-gradient(ellipse 60% 45% at 25% 55%, rgba(59,130,246,0.06) 0%, transparent 65%),
    linear-gradient(160deg, #141828 0%, #1a2640 50%, #162035 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 1100px;
  height: 1100px;
  background: radial-gradient(circle, rgba(59,130,246,0.35) 0%, rgba(59,130,246,0.12) 40%, transparent 70%);
  top: -35%;
  left: 10%;
  filter: blur(80px);
  animation: aurora-drift-1 28s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(249,115,22,0.08) 40%, transparent 70%);
  top: -10%;
  right: -15%;
  filter: blur(60px);
  animation: aurora-drift-2 24s ease-in-out infinite;
}

.aurora-blob-3 {
  width: 900px;
  height: 900px;
  background: radial-gradient(circle, rgba(59,130,246,0.20) 0%, rgba(59,130,246,0.07) 40%, transparent 70%);
  top: 30%;
  left: -25%;
  filter: blur(80px);
  animation: aurora-drift-3 32s ease-in-out infinite;
}

.aurora-blob-4 {
  width: 800px;
  height: 800px;
  background: radial-gradient(circle, rgba(79,70,229,0.16) 0%, rgba(79,70,229,0.06) 40%, transparent 70%);
  bottom: -20%;
  left: 20%;
  filter: blur(90px);
  animation: aurora-drift-4 36s ease-in-out infinite;
}

.aurora-blob-5 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(249,115,22,0.18) 0%, rgba(249,115,22,0.06) 40%, transparent 70%);
  bottom: -10%;
  right: -10%;
  filter: blur(60px);
  animation: aurora-drift-5 26s ease-in-out infinite;
}

@keyframes aurora-drift-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, 30px) scale(1.05); }
  66% { transform: translate(-20px, 15px) scale(0.97); }
}

@keyframes aurora-drift-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-30px, 20px) scale(1.03); }
  66% { transform: translate(15px, -25px) scale(1.06); }
}

@keyframes aurora-drift-3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(35px, -20px) scale(1.04); }
}

@keyframes aurora-drift-4 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(25px, -15px) scale(1.03); }
  66% { transform: translate(-15px, 10px) scale(0.98); }
}

@keyframes aurora-drift-5 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-20px, -30px) scale(1.05); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
}

/* Content Wrapper */
.content-wrapper {
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40rpx 50rpx;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

/* Back Button */
.back-btn {
  position: fixed;
  top: 40rpx;
  left: 40rpx;
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
  cursor: pointer;
}

.back-icon {
  font-size: 40rpx;
  color: #FFFFFF;
}

/* Title Section */
.title-section {
  display: flex;
  flex-direction: column;
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
  width: 100%;
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
  cursor: pointer;
}

.toggle-icon {
  font-size: 32rpx;
}

.error-message {
  font-size: 24rpx;
  color: #EF4444;
  margin-top: 8rpx;
}

/* Buttons Section */
.buttons-section {
  margin-top: 48rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
  width: 100%;
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
  cursor: pointer;
}

.btn::after {
  border: none;
}

.btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

.primary-btn {
  background-color: #007AFF;
}

.primary-btn.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-text {
  font-size: 34rpx;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: 1rpx;
}

.login-link {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 20rpx;
  cursor: pointer;
}

.login-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.6);
}

.login-text-highlight {
  font-size: 28rpx;
  color: #007AFF;
  margin-left: 8rpx;
}

/* Toast */
.toast {
  position: fixed;
  top: 100rpx;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 16rpx;
  padding: 20rpx 40rpx;
  z-index: 100;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  cursor: pointer;
}

.toast-text {
  font-size: 28rpx;
  color: #FFFFFF;
  white-space: nowrap;
}
</style>
