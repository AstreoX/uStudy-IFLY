<template>
  <view class="login-container">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
      <view class="aurora-blob aurora-blob-4"></view>
      <view class="aurora-blob aurora-blob-5"></view>
    </view>

    <!-- Content Wrapper (max-width for web) -->
    <view class="content-wrapper">
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

      <!-- Form Section -->
      <view class="form-section">
        <!-- Experiment Account Input -->
        <view class="form-group">
          <text class="form-label">账号或邮箱</text>
          <input
            class="form-input"
            :class="{ error: errors.identifier }"
            type="text"
            v-model="form.identifier"
            placeholder="请输入实验账号或注册邮箱"
            autocomplete="username"
            @blur="validateIdentifier"
          />
          <text v-if="errors.identifier" class="error-message">{{ errors.identifier }}</text>
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
              autocomplete="current-password"
              @blur="validatePassword"
              @confirm="handleLogin"
            />
            <view class="toggle-password" @tap="togglePassword">
              <text class="toggle-icon">{{ showPassword ? '🙈' : '👁️' }}</text>
            </view>
          </view>
          <view class="password-row">
            <text v-if="errors.password" class="error-message">{{ errors.password }}</text>
            <view class="forgot-password" @tap="handleForgotPassword">
              <text class="forgot-text">忘记密码？</text>
            </view>
          </view>
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
          <text class="btn-text">{{ isSubmitting ? '登录中...' : '登 录' }}</text>
        </button>

        <view v-if="exampleLoginEnabled" class="example-login-section">
          <text class="example-login-label">示例账户</text>
          <view class="example-login-buttons">
            <button
              class="example-login-btn teacher-example-btn"
              :class="{ disabled: isSubmitting }"
              :disabled="isSubmitting"
              @tap="loginAsExample('teacher')"
            >
              <text class="example-login-btn-text">登录教师示例账户</text>
            </button>
            <button
              class="example-login-btn student-example-btn"
              :class="{ disabled: isSubmitting }"
              :disabled="isSubmitting"
              @tap="loginAsExample('student')"
            >
              <text class="example-login-btn-text">登录学生示例账户</text>
            </button>
          </view>
        </view>

        <view class="register-link" @tap="handleGoRegister">
          <text class="register-text">没有账户？</text>
          <text class="register-text-highlight">邮箱注册</text>
        </view>
      </view>

      <!-- Error Toast -->
      <view v-if="toastMessage" class="toast" @tap="toastMessage = ''">
        <text class="toast-text">{{ toastMessage }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { login, getMe } from '@/api/auth'
import { getTokens, setTokens, clearAuth } from '@/utils/storage'
import { useUserStore } from '@/store/user'
import { openDefaultSpace } from '@/utils/default-space'

const EXAMPLE_ACCOUNTS = Object.freeze({
  teacher: Object.freeze({
    identifier: 'noreply+local-smoke-1787638979@uverse.cc',
    password: 'Aa1!2P28o19d1NlxH9c5'
  }),
  student: Object.freeze({
    identifier: 'example@experiment.invalid',
    password: 'Student@123'
  })
})
// This package is the dedicated experiment frontend; the shortcuts are enabled
// on its deployed host as well as local development hosts.
const EXAMPLE_LOGIN_ENABLED = true

export default {
  computed: {
    exampleLoginEnabled() {
      return EXAMPLE_LOGIN_ENABLED
    }
  },
  data() {
    return {
      form: {
        identifier: '',
        password: ''
      },
      errors: {
        identifier: '',
        password: ''
      },
      showPassword: false,
      isSubmitting: false,
      toastMessage: '',
      redirectUrl: ''
    }
  },
  onLoad(options) {
    let candidate = ''
    try {
      candidate = decodeURIComponent(String(options?.redirect || ''))
    } catch (_) {
      candidate = ''
    }
    if (candidate.startsWith('/pages/') && !candidate.startsWith('/pages/login/')) {
      this.redirectUrl = candidate
    }
  },
  async onShow() {
    const tokens = getTokens()
    if (tokens && tokens.access_token) {
      try {
        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)
        if (this.redirectUrl) {
          uni.reLaunch({ url: this.redirectUrl })
        } else {
          await openDefaultSpace()
        }
      } catch (error) {
        clearAuth()
        const userStore = useUserStore()
        userStore.clear()
      }
    }
  },
  methods: {
    togglePassword() {
      this.showPassword = !this.showPassword
    },

    validateIdentifier() {
      const identifier = this.form.identifier.trim()
      if (!identifier) {
        this.errors.identifier = '请输入账号或邮箱'
        return false
      }
      if (identifier.length > 255) {
        this.errors.identifier = '账号格式不正确'
        return false
      }
      this.form.identifier = identifier
      this.errors.identifier = ''
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
      const identifierValid = this.validateIdentifier()
      const passwordValid = this.validatePassword()
      return identifierValid && passwordValid
    },

    loginAsExample(role) {
      if (this.isSubmitting) {
        return
      }

      const account = EXAMPLE_ACCOUNTS[role]
      if (!account) {
        return
      }

      this.form.identifier = account.identifier
      this.form.password = account.password
      this.errors.identifier = ''
      this.errors.password = ''
      this.handleLogin()
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

    async handleLogin() {
      if (!this.validateForm()) {
        return
      }

      this.isSubmitting = true

      try {
        const tokenResp = await login({
          identifier: this.form.identifier,
          password: this.form.password
        })

        setTokens({
          access_token: tokenResp.access_token,
          refresh_token: tokenResp.refresh_token
        })

        const user = await getMe()
        const userStore = useUserStore()
        userStore.setUser(user)

        this.showToast('登录成功')

        if (this.redirectUrl) {
          setTimeout(() => uni.reLaunch({ url: this.redirectUrl }), 800)
        } else {
          await openDefaultSpace()
        }
      } catch (error) {
        const message = this.getErrorMessage(error, '登录失败，请重试')
        this.showToast(message)
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

/* Aurora Background — 5-blob website style */
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

/* Blob 1: Large blue, top-center */
.aurora-blob-1 {
  width: 1100px;
  height: 1100px;
  background: radial-gradient(circle, rgba(59,130,246,0.35) 0%, rgba(59,130,246,0.12) 40%, transparent 70%);
  top: -35%;
  left: 10%;
  filter: blur(80px);
  animation: aurora-drift-1 28s ease-in-out infinite;
}

/* Blob 2: Orange, upper-right */
.aurora-blob-2 {
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(249,115,22,0.08) 40%, transparent 70%);
  top: -10%;
  right: -15%;
  filter: blur(60px);
  animation: aurora-drift-2 24s ease-in-out infinite;
}

/* Blob 3: Blue, mid-left */
.aurora-blob-3 {
  width: 900px;
  height: 900px;
  background: radial-gradient(circle, rgba(59,130,246,0.20) 0%, rgba(59,130,246,0.07) 40%, transparent 70%);
  top: 30%;
  left: -25%;
  filter: blur(80px);
  animation: aurora-drift-3 32s ease-in-out infinite;
}

/* Blob 4: Indigo, bottom-center */
.aurora-blob-4 {
  width: 800px;
  height: 800px;
  background: radial-gradient(circle, rgba(79,70,229,0.16) 0%, rgba(79,70,229,0.06) 40%, transparent 70%);
  bottom: -20%;
  left: 20%;
  filter: blur(90px);
  animation: aurora-drift-4 36s ease-in-out infinite;
}

/* Blob 5: Orange, bottom-right */
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

/* Content Wrapper - vertically centered for web */
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

/* Welcome Section */
.welcome-section {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  width: 100%;
  padding-left: 20rpx;
  padding-top: 0;
  padding-bottom: 60rpx;
}

.welcome-line {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  margin-bottom: 10rpx;
}

.welcome-hi {
  font-size: 72rpx;
  font-weight: 800;
  color: #FFFFFF;
  margin-right: 20rpx;
  letter-spacing: -2rpx;
}

.welcome-text {
  font-size: 52rpx;
  font-weight: 400;
  color: #FFFFFF;
  letter-spacing: 2rpx;
}

.logo {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  margin-top: 20rpx;
  padding-left: 180rpx;
}

.logo-u {
  font-size: 96rpx;
  font-weight: 600;
  color: #3B82F6;
}

.logo-study {
  font-size: 96rpx;
  font-weight: 700;
  color: #FFFFFF;
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

.password-row {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  margin-top: 8rpx;
}

.error-message {
  font-size: 24rpx;
  color: #EF4444;
}

.password-error {
  margin-top: 8rpx;
}

.experiment-hint {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
}

/* Forgot Password */
.forgot-password {
  margin-left: auto;
  cursor: pointer;
}

.forgot-text {
  font-size: 26rpx;
  color: #007AFF;
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

.login-btn {
  background-color: #007AFF;
}

.login-btn.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.example-login-section {
  width: 100%;
  margin-top: 8rpx;
}

.example-login-label {
  display: block;
  margin-bottom: 14rpx;
  color: rgba(255, 255, 255, 0.48);
  font-size: 24rpx;
  text-align: center;
}

.example-login-buttons {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  width: 100%;
}

.example-login-btn {
  flex: 1;
  min-width: 0;
  height: 72rpx;
  padding: 0 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.16);
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s ease, transform 0.15s ease, background-color 0.2s ease;
  cursor: pointer;
  box-sizing: border-box;
}

.example-login-btn::after {
  border: none;
}

.example-login-btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

.example-login-btn.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.teacher-example-btn {
  background-color: rgba(249, 115, 22, 0.18);
  border-color: rgba(249, 115, 22, 0.35);
}

.student-example-btn {
  background-color: rgba(0, 122, 255, 0.18);
  border-color: rgba(0, 122, 255, 0.35);
}

.example-login-btn-text {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.9);
  font-size: 25rpx;
  line-height: 1.2;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-text {
  font-size: 34rpx;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: 2rpx;
}

.register-link {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 20rpx;
  cursor: pointer;
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
