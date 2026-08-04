<template>
  <view v-if="visible" class="activation-modal-wrapper" @touchmove.stop.prevent>
    <!-- Overlay with blur -->
    <view
      class="activation-modal-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleOverlayClick"
    ></view>

    <!-- Modal Container -->
    <view class="activation-modal-container" :class="{ 'modal-show': animationVisible }">
      <!-- Glow effect -->
      <view class="modal-glow" :class="{ 'glow-success': showSuccess }"></view>

      <!-- Success State -->
      <view v-if="showSuccess" class="success-content">
        <!-- Success Icon with Animation -->
        <view class="success-icon-container">
          <!-- Ripple effects -->
          <view class="ripple ripple-1"></view>
          <view class="ripple ripple-2"></view>
          <view class="ripple ripple-3"></view>

          <!-- Main icon circle -->
          <view class="success-icon-circle">
            <!-- Checkmark SVG -->
            <view class="checkmark-container">
              <view class="checkmark-stem"></view>
              <view class="checkmark-kick"></view>
            </view>
          </view>

          <!-- Floating particles -->
          <view class="particle particle-1"></view>
          <view class="particle particle-2"></view>
          <view class="particle particle-3"></view>
          <view class="particle particle-4"></view>
          <view class="particle particle-5"></view>
          <view class="particle particle-6"></view>
        </view>

        <!-- Success Text -->
        <view class="success-text-container">
          <text class="success-title">激活成功</text>
          <text class="success-subtitle">{{ successSubtitle }}</text>
        </view>

        <!-- Benefits List -->
        <view class="benefits-container">
          <view class="benefit-item">
            <view class="benefit-icon">✓</view>
            <text class="benefit-text">无限创建学习空间</text>
          </view>
          <view class="benefit-item">
            <view class="benefit-icon">✓</view>
            <text class="benefit-text">无限每日对话次数</text>
          </view>
          <view class="benefit-item">
            <view class="benefit-icon">✓</view>
            <text class="benefit-text">更多 AI 模型可选</text>
          </view>
        </view>

        <!-- Continue Button -->
        <view class="success-btn" @click="handleSuccessClose">
          <text class="success-btn-text">开始使用</text>
        </view>
      </view>

      <!-- Input State -->
      <view v-else class="modal-content">
        <!-- Header with icon -->
        <view class="modal-header">
          <view class="alpha-badge">
            <text class="alpha-text">会员</text>
          </view>
        </view>

        <!-- Title -->
        <view class="modal-title">
          <text class="title-main">激活码验证</text>
          <text class="title-sub">输入激活码以开通订阅权益</text>
        </view>

        <!-- Input Field -->
        <view class="input-container">
          <input
            class="code-input"
            type="text"
            :value="inputCode"
            placeholder="请输入激活码"
            :maxlength="24"
            :focus="animationVisible && !loading && !showSuccess"
            :disabled="loading"
            placeholder-class="input-placeholder"
            @input="onInput"
          />
        </view>

        <!-- Error Message -->
        <view v-if="errorMessage" class="error-container">
          <text class="error-text">{{ errorMessage }}</text>
        </view>

        <!-- Buttons -->
        <view class="button-container" :class="{ 'single-action': mandatory }">
          <view
            v-if="!mandatory"
            class="btn btn-secondary"
            :class="{ 'btn-disabled': loading }"
            @click="handleCancel"
          >
            <text class="btn-text">稍后</text>
          </view>
          <view
            class="btn btn-primary"
            :class="{ 'btn-disabled': !isValid || loading }"
            @click="handleActivate"
          >
            <text v-if="loading" class="btn-text">验证中...</text>
            <text v-else class="btn-text">激活</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { activateCode } from '@/api/auth'
import { useUserStore } from '@/store/user'

export default {
  name: 'ActivationModal',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    mandatory: {
      type: Boolean,
      default: false
    }
  },

  data() {
    return {
      animationVisible: false,
      inputCode: '',
      errorMessage: '',
      loading: false,
      showSuccess: false,
      activatedTier: ''
    }
  },

  computed: {
    isValid() {
      const code = this.inputCode.replace(/[-\s]/g, '').trim()
      return code.length >= 10
    },
    successSubtitle() {
      const labels = {
        BASIC: 'Plus',
        PREMIUM: 'Ultra',
        ALPHA: 'Alpha 内测',
        ULTRA: 'Ultra'
      }
      const label = labels[this.activatedTier] || this.activatedTier || '会员'
      return `已开通 ${label} 权益`
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.inputCode = ''
          this.errorMessage = ''
          this.loading = false
          this.showSuccess = false
          this.activatedTier = ''
          this.$nextTick(() => {
            setTimeout(() => {
              this.animationVisible = true
            }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  methods: {
    onInput(e) {
      this.inputCode = e.detail?.value ?? e.target?.value ?? ''
      this.errorMessage = ''
    },

    handleOverlayClick() {
      // 成功状态下点击遮罩也可以关闭
      if (this.showSuccess) {
        this.handleSuccessClose()
      } else if (!this.loading && !this.mandatory) {
        this.handleCancel()
      }
    },

    handleCancel() {
      if (this.loading || this.mandatory) return
      this.close()
      this.$emit('cancel')
    },

    async handleActivate() {
      if (!this.isValid || this.loading) return

      this.loading = true
      this.errorMessage = ''

      try {
        const code = this.inputCode.trim()
        const response = await activateCode(code)

        if (response.success) {
          const userStore = useUserStore()
          userStore.updateSubscription(
            response.subscription_tier,
            response.subscription_expires_at
          )

          // 显示成功界面
          this.activatedTier = response.subscription_tier
          this.showSuccess = true
          this.$emit('success', response)
        }
      } catch (error) {
        const detail = error.data?.detail || error.message || '激活失败，请稍后重试'
        if (typeof detail === 'object') {
          this.errorMessage = detail.message || '激活失败'
        } else {
          this.errorMessage = detail
        }
      } finally {
        this.loading = false
      }
    },

    handleSuccessClose() {
      this.close()
    },

    close() {
      this.animationVisible = false
      setTimeout(() => {
        this.showSuccess = false
        this.$emit('close')
      }, 200)
    }
  }
}
</script>

<style scoped>
.activation-modal-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.activation-modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 300ms ease;
}

.activation-modal-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.75);
}

.activation-modal-container {
  position: relative;
  width: 600rpx;
  background: rgba(18, 18, 28, 0.85);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  overflow: hidden;
  transform: translateY(60rpx) scale(0.9);
  opacity: 0;
  transition: all 350ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.activation-modal-container.modal-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .activation-modal-container {
    background: rgba(18, 18, 28, 0.98);
  }
}

/* Glow effect */
.modal-glow {
  position: absolute;
  top: -100rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 400rpx;
  height: 200rpx;
  background: radial-gradient(ellipse, rgba(0, 136, 255, 0.25) 0%, transparent 70%);
  pointer-events: none;
  transition: all 500ms ease;
}

.modal-glow.glow-success {
  top: -150rpx;
  width: 600rpx;
  height: 300rpx;
  background: radial-gradient(ellipse, rgba(34, 197, 94, 0.35) 0%, rgba(0, 136, 255, 0.15) 50%, transparent 70%);
}

/* ==================== SUCCESS STATE ==================== */
.success-content {
  padding: 48rpx 40rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Success Icon Container */
.success-icon-container {
  position: relative;
  width: 180rpx;
  height: 180rpx;
  margin-bottom: 32rpx;
}

/* Ripple Effects */
.ripple {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2rpx solid rgba(34, 197, 94, 0.3);
  transform: translate(-50%, -50%) scale(0.5);
  opacity: 0;
}

.ripple-1 {
  animation: ripple 2s ease-out infinite;
}

.ripple-2 {
  animation: ripple 2s ease-out infinite 0.4s;
}

.ripple-3 {
  animation: ripple 2s ease-out infinite 0.8s;
}

@keyframes ripple {
  0% {
    transform: translate(-50%, -50%) scale(0.5);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2);
    opacity: 0;
  }
}

/* Main Success Circle */
.success-icon-circle {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120rpx;
  height: 120rpx;
  transform: translate(-50%, -50%);
  background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%);
  border-radius: 50%;
  box-shadow: 0 8rpx 32rpx rgba(34, 197, 94, 0.4);
  animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

@keyframes scaleIn {
  0% {
    transform: translate(-50%, -50%) scale(0);
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
  }
}

/* Checkmark */
.checkmark-container {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 50rpx;
  height: 30rpx;
  transform: translate(-50%, -50%) rotate(-45deg);
}

.checkmark-stem {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 6rpx;
  height: 0;
  background: #ffffff;
  border-radius: 3rpx;
  animation: checkmarkStem 0.2s ease-out 0.3s forwards;
}

.checkmark-kick {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 0;
  height: 6rpx;
  background: #ffffff;
  border-radius: 3rpx;
  animation: checkmarkKick 0.2s ease-out 0.5s forwards;
}

@keyframes checkmarkStem {
  0% {
    height: 0;
  }
  100% {
    height: 30rpx;
  }
}

@keyframes checkmarkKick {
  0% {
    width: 0;
  }
  100% {
    width: 50rpx;
  }
}

/* Floating Particles */
.particle {
  position: absolute;
  width: 12rpx;
  height: 12rpx;
  background: linear-gradient(135deg, #22C55E, #0088FF);
  border-radius: 50%;
  opacity: 0;
}

.particle-1 {
  top: 10%;
  left: 20%;
  animation: particleFloat 0.8s ease-out 0.4s forwards;
}

.particle-2 {
  top: 5%;
  right: 25%;
  animation: particleFloat 0.8s ease-out 0.5s forwards;
}

.particle-3 {
  top: 30%;
  left: 5%;
  animation: particleFloat 0.8s ease-out 0.6s forwards;
}

.particle-4 {
  top: 25%;
  right: 5%;
  animation: particleFloat 0.8s ease-out 0.55s forwards;
}

.particle-5 {
  bottom: 20%;
  left: 15%;
  animation: particleFloat 0.8s ease-out 0.65s forwards;
}

.particle-6 {
  bottom: 25%;
  right: 15%;
  animation: particleFloat 0.8s ease-out 0.7s forwards;
}

@keyframes particleFloat {
  0% {
    opacity: 0;
    transform: translateY(20rpx) scale(0);
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateY(-40rpx) scale(1.5);
  }
}

/* Success Text */
.success-text-container {
  text-align: center;
  margin-bottom: 32rpx;
  animation: fadeInUp 0.5s ease-out 0.3s both;
}

@keyframes fadeInUp {
  0% {
    opacity: 0;
    transform: translateY(20rpx);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.success-title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 12rpx;
}

.success-subtitle {
  display: block;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.6);
}

/* Benefits List */
.benefits-container {
  width: 100%;
  margin-bottom: 32rpx;
  animation: fadeInUp 0.5s ease-out 0.5s both;
}

.benefit-item {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 12rpx;
  margin-bottom: 12rpx;
}

.benefit-item:last-child {
  margin-bottom: 0;
}

.benefit-icon {
  width: 36rpx;
  height: 36rpx;
  background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20rpx;
  color: #ffffff;
  font-weight: bold;
  margin-right: 16rpx;
  flex-shrink: 0;
}

.benefit-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.85);
}

/* Success Button */
.success-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(34, 197, 94, 0.35);
  animation: fadeInUp 0.5s ease-out 0.7s both;
  transition: all 150ms ease;
}

.success-btn:active {
  transform: scale(0.98);
  box-shadow: 0 4rpx 16rpx rgba(34, 197, 94, 0.4);
}

.success-btn-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
}

/* ==================== INPUT STATE ==================== */
.modal-content {
  position: relative;
  padding: 48rpx 40rpx 40rpx;
}

/* Header */
.modal-header {
  display: flex;
  justify-content: center;
  margin-bottom: 32rpx;
}

.alpha-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12rpx 32rpx;
  background: linear-gradient(135deg, rgba(0, 136, 255, 0.25) 0%, rgba(0, 170, 255, 0.1) 100%);
  border: 1rpx solid rgba(0, 170, 255, 0.4);
  border-radius: 100rpx;
}

.alpha-text {
  font-size: 26rpx;
  font-weight: 600;
  color: #00AAFF;
  letter-spacing: 2rpx;
}

/* Title */
.modal-title {
  text-align: center;
  margin-bottom: 40rpx;
}

.title-main {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 12rpx;
}

.title-sub {
  display: block;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.5);
}

/* Input */
.input-container {
  margin-bottom: 24rpx;
}

.code-input {
  width: 100%;
  height: 100rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 16rpx;
  font-size: 34rpx;
  font-weight: 500;
  color: #ffffff;
  text-align: center;
  letter-spacing: 4rpx;
  box-sizing: border-box;
  transition: border-color 200ms ease, background 200ms ease;
}

.code-input:focus {
  border-color: rgba(0, 170, 255, 0.6);
  background: rgba(0, 136, 255, 0.08);
}

.code-input:disabled {
  opacity: 0.5;
}

.input-placeholder {
  color: rgba(255, 255, 255, 0.25);
  font-weight: 400;
  letter-spacing: 2rpx;
}

/* Error */
.error-container {
  margin-bottom: 16rpx;
  text-align: center;
}

.error-text {
  font-size: 26rpx;
  color: #F87171;
}

/* Buttons */
.button-container {
  display: flex;
  gap: 24rpx;
  margin-top: 32rpx;
}

.button-container.single-action {
  gap: 0;
}

.btn {
  flex: 1;
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
  transition: all 150ms ease;
}

.btn:active:not(.btn-disabled) {
  transform: scale(0.98);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.btn-secondary .btn-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 30rpx;
  font-weight: 500;
}

.btn-secondary:active:not(.btn-disabled) {
  background: rgba(255, 255, 255, 0.12);
}

.btn-primary {
  background: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  border: none;
  box-shadow: 0 8rpx 24rpx rgba(0, 136, 255, 0.3);
}

.btn-primary .btn-text {
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
}

.btn-primary:active:not(.btn-disabled) {
  box-shadow: 0 4rpx 16rpx rgba(0, 136, 255, 0.4);
}

.btn-primary.btn-disabled {
  background: rgba(0, 136, 255, 0.3);
  box-shadow: none;
}

.btn-primary.btn-disabled .btn-text {
  color: rgba(255, 255, 255, 0.5);
}

.btn-secondary.btn-disabled {
  opacity: 0.5;
}
</style>
