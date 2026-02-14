<template>
  <view class="register-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
    </view>

    <!-- Back Button -->
    <view class="back-btn" @tap="handleBack">
      <text class="back-icon">&#x2190;</text>
    </view>

    <!-- Content Area -->
    <view class="content-area">
      <!-- Title Section -->
      <view class="title-section">
        <text class="title-main">创建账户</text>
        <text class="title-sub">加入 uStudy，开启学习之旅</text>
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
            @blur="validateCode"
          />
          <text v-if="errors.code" class="error-message">{{ errors.code }}</text>
        </view>

        <!-- Step 3 Inputs -->
        <view v-if="step === 3">
          <!-- Nickname Input -->
          <view class="form-group">
            <text class="form-label">昵称</text>
            <input
              class="form-input"
              :class="{ error: errors.nickname }"
              type="text"
              v-model="form.nickname"
              placeholder="请输入昵称"
              @blur="validateNickname"
            />
            <text v-if="errors.nickname" class="error-message">{{ errors.nickname }}</text>
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
              placeholder="请输入密码（至少8位，含大小写+数字）"
              @blur="validatePassword"
            />
            <view class="toggle-password" @tap="togglePassword">
              <text class="toggle-icon">{{ showPassword ? '🙈' : '👁️' }}</text>
            </view>
          </view>
          <text v-if="errors.password" class="error-message">{{ errors.password }}</text>
        </view>

        <!-- Confirm Password Input -->
        <view class="form-group">
          <text class="form-label">确认密码</text>
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

        <!-- Terms Checkbox -->
        <view class="terms-section" @tap="toggleTerms">
          <view class="checkbox" :class="{ checked: form.agreeTerms }">
            <text v-if="form.agreeTerms" class="check-icon">✓</text>
          </view>
          <text class="terms-text">我同意 <text class="terms-link">服务条款</text> 和 <text class="terms-link">隐私政策</text></text>
        </view>
        <text v-if="errors.terms" class="error-message terms-error">{{ errors.terms }}</text>
        </view>
      </view>

      <!-- Buttons Section -->
      <view class="buttons-section">
        <button
          class="btn register-btn"
          :class="{ disabled: isSubmitting }"
          :disabled="isSubmitting"
          @tap="handlePrimaryAction"
        >
          <text class="btn-text">
            {{ primaryButtonText }}
          </text>
        </button>

        <view class="login-link" @tap="handleGoLogin">
          <text class="login-text">已有账户？</text>
          <text class="login-text-highlight">登录</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getMe, registerWithCode, sendCode, verifyCode } from '@/api/auth'
import { setTokens } from '@/utils/storage'
import { useUserStore } from '@/store/user'
import { goBack } from '@/utils/navigation'

export default {
  data() {
    return {
      step: 1,
      verificationToken: '',
      form: {
        email: '',
        code: '',
        nickname: '',
        password: '',
        confirmPassword: '',
        agreeTerms: false
      },
      errors: {
        email: '',
        code: '',
        nickname: '',
        password: '',
        confirmPassword: '',
        terms: ''
      },
      showPassword: false,
      showConfirmPassword: false,
      isSubmitting: false
    }
  },
  computed: {
    primaryButtonText() {
      if (this.step === 1) {
        return this.isSubmitting ? '发送中...' : '发送验证码'
      }
      if (this.step === 2) {
        return this.isSubmitting ? '验证中...' : '验证验证码'
      }
      return this.isSubmitting ? '注册中...' : '注册'
    }
  },
  methods: {
    handleBack() {
      goBack({ fallbackUrl: '/pages/login/login' })
    },

    togglePassword() {
      this.showPassword = !this.showPassword
    },

    toggleConfirmPassword() {
      this.showConfirmPassword = !this.showConfirmPassword
    },

    toggleTerms() {
      this.form.agreeTerms = !this.form.agreeTerms
      if (this.form.agreeTerms) {
        this.errors.terms = ''
      }
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

    validateNickname() {
      if (!this.form.nickname) {
        this.errors.nickname = '请输入昵称'
        return false
      }
      if (this.form.nickname.length > 100) {
        this.errors.nickname = '昵称不能超过100个字符'
        return false
      }
      this.errors.nickname = ''
      return true
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

    validateTerms() {
      if (!this.form.agreeTerms) {
        this.errors.terms = '请同意服务条款'
        return false
      }
      this.errors.terms = ''
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
      await this.handleRegister()
    },

    async handleSendCode() {
      if (!this.validateEmail()) {
        return
      }

      this.isSubmitting = true
      try {
        await sendCode({
          email: this.form.email,
          purpose: 'registration'
        })
        uni.showToast({
          title: '验证码已发送',
          icon: 'success'
        })
        this.step = 2
      } catch (error) {
        console.error('Send code failed:', error)
        const message = this.getErrorMessage(error, '发送失败，请重试')
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        this.isSubmitting = false
      }
    },

    async handleVerifyCode() {
      if (!this.validateEmail() || !this.validateCode()) {
        return
      }

      this.isSubmitting = true
      try {
        const resp = await verifyCode({
          email: this.form.email,
          code: this.form.code,
          purpose: 'registration'
        })
        this.verificationToken = resp.verification_token
        uni.showToast({
          title: '验证成功',
          icon: 'success'
        })
        this.step = 3
      } catch (error) {
        console.error('Verify code failed:', error)
        const message = this.getErrorMessage(error, '验证码无效')
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        this.isSubmitting = false
      }
    },

    async handleRegister() {
      if (!this.verificationToken) {
        uni.showToast({
          title: '请先完成验证码验证',
          icon: 'none'
        })
        this.step = 2
        return
      }

      const nicknameValid = this.validateNickname()
      const passwordValid = this.validatePassword()
      const confirmValid = this.validateConfirmPassword()
      const termsValid = this.validateTerms()
      if (!nicknameValid || !passwordValid || !confirmValid || !termsValid) {
        return
      }

      this.isSubmitting = true
      try {
        const tokenResp = await registerWithCode({
          email: this.form.email,
          verification_token: this.verificationToken,
          password: this.form.password,
          nickname: this.form.nickname
        })

        setTokens({
          access_token: tokenResp.access_token,
          refresh_token: tokenResp.refresh_token
        })

        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)

        uni.showToast({
          title: '注册成功',
          icon: 'success'
        })

        setTimeout(() => {
          uni.reLaunch({
            url: '/pages/index/index'
          })
        }, 800)
      } catch (error) {
        console.error('Registration failed:', error)
        const message = this.getErrorMessage(error, '注册失败，请重试')
        uni.showToast({
          title: message,
          icon: 'none'
        })
      } finally {
        this.isSubmitting = false
      }
    },

    handleGoLogin() {
      uni.navigateBack()
    }
  }
}
</script>

<style>
.register-container {
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

/* Aurora Background - 复用登录页样式 */
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

/* Terms Section */
.terms-section {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin-top: 16rpx;
}

.checkbox {
  width: 40rpx;
  height: 40rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.4);
  border-radius: 8rpx;
  margin-right: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.checkbox.checked {
  background: #007AFF;
  border-color: #007AFF;
}

.check-icon {
  color: #FFFFFF;
  font-size: 24rpx;
  font-weight: bold;
}

.terms-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.6);
}

.terms-link {
  color: #007AFF;
}

.terms-error {
  margin-left: 56rpx;
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

.register-btn {
  background-color: #007AFF;
}

.register-btn.disabled {
  opacity: 0.6;
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
</style>
