<template>
  <view class="register-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
      <view class="aurora-blob aurora-blob-5"></view>
    </view>

    <!-- Back Button (page-level, top-left) -->
    <view class="back-btn" @tap="handleBack">
      <text class="back-icon">&#x2190;</text>
    </view>

    <!-- Content Wrapper (max-width for web) -->
    <view class="content-wrapper">
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
          <text class="btn-text">{{ primaryButtonText }}</text>
        </button>

        <view class="login-link" @tap="handleGoLogin">
          <text class="login-text">已有账户？</text>
          <text class="login-text-highlight">登录</text>
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
import { sendCode, verifyCode, registerWithCode, getMe } from '@/api/auth'
import { setTokens } from '@/utils/storage'
import { useUserStore } from '@/store/user'

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
      isSubmitting: false,
      toastMessage: ''
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

    toggleTerms() {
      this.form.agreeTerms = !this.form.agreeTerms
      if (this.form.agreeTerms) {
        this.errors.terms = ''
      }
    },

    showToast(message) {
      this.toastMessage = message
      setTimeout(() => {
        this.toastMessage = ''
      }, 3000)
    },

    getErrorMessage(error, fallback) {
      const detail = error?.data?.detail
      if (typeof detail === 'string') {
        return detail
      }
      if (detail && typeof detail === 'object') {
        return detail.message || fallback
      }
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

    validateNickname() {
      if (!this.form.nickname) {
        this.errors.nickname = '请输入昵称'
        return false
      }
      if (this.form.nickname.length < 2) {
        this.errors.nickname = '昵称至少需要2个字符'
        return false
      }
      if (this.form.nickname.length > 50) {
        this.errors.nickname = '昵称不能超过50个字符'
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
        this.showToast('验证成功')
        this.step = 3
      } catch (error) {
        const message = this.getErrorMessage(error, '验证码无效')
        this.showToast(message)
      } finally {
        this.isSubmitting = false
      }
    },

    async handleRegister() {
      if (!this.verificationToken) {
        this.showToast('请先完成验证码验证')
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

        this.showToast('注册成功')

        setTimeout(() => {
          uni.reLaunch({
            url: '/pages/index/index'
          })
        }, 800)
      } catch (error) {
        const message = this.getErrorMessage(error, '注册失败，请重试')
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
.register-container {
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

/* Aurora Background — 5-blob website style (matches login page) */
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

/* Content Wrapper - vertically centered for web (matches login page) */
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

/* Terms Section */
.terms-section {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin-top: 16rpx;
  cursor: pointer;
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

.register-btn {
  background-color: #007AFF;
}

.register-btn.disabled {
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

/* Toast (matches login page) */
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
