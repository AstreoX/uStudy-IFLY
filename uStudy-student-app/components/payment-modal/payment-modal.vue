<template>
  <view v-if="visible" class="pm-overlay" @tap.self="handleClose">
    <view class="pm-container" :class="[themeClass, { 'pm-submitted': showSubmitted }]">
      <!-- Close button -->
      <view class="pm-close" @tap="handleClose">
        <text class="pm-close-icon">×</text>
      </view>

      <!-- State 1: Confirm & Pay -->
      <template v-if="!showSubmitted && !showQrCode">
        <view class="pm-header">
          <text class="pm-title">确认订单</text>
        </view>

        <view class="pm-plan-info">
          <view class="pm-plan-row">
            <text class="pm-plan-label">方案</text>
            <text class="pm-plan-value">{{ planDisplayName }}</text>
          </view>
          <view class="pm-plan-row" v-if="!isCreditPack">
            <text class="pm-plan-label">周期</text>
            <text class="pm-plan-value">{{ cycleDisplayName }}</text>
          </view>
          <view class="pm-divider"></view>
          <view class="pm-plan-row pm-plan-row-total">
            <text class="pm-plan-label">合计</text>
            <text class="pm-plan-price">{{ priceDisplay }}</text>
          </view>
        </view>

        <button
          class="pm-pay-btn"
          :class="{ 'pm-pay-btn-loading': loading }"
          :disabled="loading"
          @tap="handlePay"
        >
          <text v-if="loading" class="pm-loading-text">正在创建订单...</text>
          <text v-else class="pm-pay-text">去支付</text>
        </button>

        <text v-if="errorMsg" class="pm-error">{{ errorMsg }}</text>
      </template>

      <!-- State 2: Show QR Code -->
      <template v-if="showQrCode && !showSubmitted">
        <view class="pm-header">
          <text class="pm-title">扫码支付</text>
        </view>

        <!-- Payment method tabs -->
        <view class="pm-tabs">
          <view
            class="pm-tab"
            :class="{ 'pm-tab-active': payMethod === 'alipay' }"
            @tap="payMethod = 'alipay'"
          >
            <text class="pm-tab-text">支付宝</text>
          </view>
          <view
            class="pm-tab"
            :class="{ 'pm-tab-active': payMethod === 'wechat' }"
            @tap="payMethod = 'wechat'"
          >
            <text class="pm-tab-text">微信支付</text>
          </view>
        </view>

        <!-- QR Code -->
        <view class="pm-qr-section">
          <image class="pm-qr-img" :src="qrCodeSrc" mode="aspectFit" />
        </view>

        <!-- Amount -->
        <view class="pm-amount-section">
          <text class="pm-amount-label">请支付</text>
          <text class="pm-amount-value">{{ orderAmount }}</text>
        </view>

        <text class="pm-hint">请使用{{ payMethod === 'alipay' ? '支付宝' : '微信' }}扫描上方二维码完成支付</text>

        <!-- Save QR to album -->
        <button class="pm-save-btn" :disabled="saving" @tap="handleSaveQr">
          <text class="pm-save-text">{{ saving ? '保存中...' : '保存收款码到相册' }}</text>
        </button>

        <!-- Confirm button -->
        <button class="pm-confirm-btn" :disabled="submitting" @tap="handleConfirmPaid">
          <text class="pm-confirm-text">{{ submitting ? '提交中...' : '我已支付' }}</text>
        </button>

        <text v-if="errorMsg" class="pm-error">{{ errorMsg }}</text>
      </template>

      <!-- State 3: Submitted -->
      <template v-if="showSubmitted">
        <view class="pm-submitted-content">
          <view class="pm-submitted-icon-wrap">
            <text class="pm-submitted-icon">✉</text>
          </view>
          <text class="pm-submitted-title">已提交</text>
          <text class="pm-submitted-desc">
            已通知管理员，审核结果将通过邮件通知您
          </text>
          <button class="pm-done-btn" @tap="handleDone">
            <text class="pm-done-text">知道了</text>
          </button>
        </view>
      </template>
    </view>
  </view>
</template>

<script>
import { createOrder, notifyPaid } from '@/api/payment'
import { ensureAlbumWritePermission, isPermissionDenied, guideToSettings } from '@/utils/permission'
import config from '@/config'
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

const API_BASE_URL = config.API_BASE_URL

const TIER_MAP = {
  PLUS: 'BASIC',
  ULTRA: 'PREMIUM'
}

const CYCLE_LABELS = {
  monthly: '月付',
  semester: '学期包（4个月）',
  yearly: '年付'
}

export default {
  props: {
    visible: { type: Boolean, default: false },
    plan: { type: Object, default: null },
    billingCycle: { type: String, default: 'semester' },
    themeMode: { type: String, default: '' }
  },
  emits: ['close', 'success'],
  data() {
    return {
      internalThemeMode: 'dark',
      loading: false,
      showSubmitted: false,
      showQrCode: false,
      submitting: false,
      saving: false,
      errorMsg: '',
      orderId: null,
      orderAmount: '',
      payMethod: 'alipay',
      qrCodes: { alipay: {}, wechat: {} }
    }
  },
  computed: {
    backendTier() {
      if (!this.plan) return ''
      return TIER_MAP[this.plan.id] || this.plan.id
    },
    planDisplayName() {
      return this.plan?.name || this.plan?.product_code || ''
    },
    isCreditPack() {
      return this.plan?.product_type === 'credit_pack'
    },
    cycleDisplayName() {
      return CYCLE_LABELS[this.billingCycle] || this.billingCycle
    },
    priceDisplay() {
      if (!this.plan) return ''
      if (this.plan.amount_display) return this.plan.amount_display
      const pricing = this.plan.pricing?.[this.billingCycle]
      return pricing ? `${pricing.main}` : ''
    },
    qrCodeSrc() {
      const urls = this.qrCodes?.[this.payMethod]
      if (!urls?.display) return ''
      return urls.display.startsWith('http') ? urls.display : `${API_BASE_URL}${urls.display}`
    },
    saveQrCodeSrc() {
      const urls = this.qrCodes?.[this.payMethod]
      const path = urls?.save || urls?.display
      if (!path) return ''
      return path.startsWith('http') ? path : `${API_BASE_URL}${path}`
    },
    resolvedThemeMode() {
      return this.themeMode ? normalizeThemeMode(this.themeMode) : this.internalThemeMode
    },
    themeClass() {
      return this.resolvedThemeMode === 'light' ? 'theme-light' : 'theme-dark'
    }
  },
  watch: {
    visible(val) {
      if (!val) {
        this.reset()
      } else {
        this.refreshThemeMode()
      }
    }
  },
  created() {
    this.refreshThemeMode()
  },
  methods: {
    refreshThemeMode() {
      this.internalThemeMode = getStoredThemeMode('dark')
    },

    reset() {
      this.loading = false
      this.showSubmitted = false
      this.showQrCode = false
      this.submitting = false
      this.saving = false
      this.errorMsg = ''
      this.orderId = null
      this.orderAmount = ''
      this.payMethod = 'alipay'
      this.qrCodes = { alipay: {}, wechat: {} }
    },
    handleClose() {
      this.$emit('close')
    },
    async handlePay() {
      if (this.loading) return
      this.loading = true
      this.errorMsg = ''

      try {
        const resp = await createOrder({
          product_type: this.isCreditPack ? 'credit_pack' : 'subscription',
          product_code: this.isCreditPack ? this.plan.product_code : null,
          tier: this.isCreditPack ? null : this.backendTier,
          billing_cycle: this.isCreditPack ? null : this.billingCycle
        })

        this.orderId = resp.order_id
        this.orderAmount = resp.amount_display
        this.qrCodes = resp.qr_codes || { alipay: {}, wechat: {} }
        this.showQrCode = true
      } catch (err) {
        this.errorMsg = err?.message || err?.detail || '创建订单失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    async handleConfirmPaid() {
      if (this.submitting) return
      this.submitting = true
      this.errorMsg = ''

      try {
        await notifyPaid(this.orderId)
      } catch {
        // 通知失败不阻塞
      }

      this.showSubmitted = true
      this.showQrCode = false
      this.submitting = false
    },
    async handleSaveQr() {
      if (this.saving) return
      this.saving = true

      try {
        const permitted = await ensureAlbumWritePermission()
        if (!permitted) return

        const imgInfo = await new Promise((resolve, reject) => {
          uni.getImageInfo({ src: this.saveQrCodeSrc, success: resolve, fail: reject })
        })

        await new Promise((resolve, reject) => {
          uni.saveImageToPhotosAlbum({ filePath: imgInfo.path, success: resolve, fail: reject })
        })

        uni.showToast({ title: '已保存到相册', icon: 'success' })
      } catch (err) {
        if (isPermissionDenied(err)) {
          guideToSettings('需要相册权限', '请在设置中允许访问相册，以便保存收款码')
        } else {
          console.error('Save QR failed:', err?.errMsg || '')
          uni.showToast({ title: '保存失败，请重试', icon: 'none' })
        }
      } finally {
        this.saving = false
      }
    },
    handleDone() {
      this.$emit('close')
    }
  }
}
</script>

<style scoped>
.pm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8rpx);
  -webkit-backdrop-filter: blur(8rpx);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.pm-container {
  position: relative;
  width: 620rpx;
  border-radius: 32rpx;
  background: rgba(22, 25, 42, 0.96);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 48rpx 40rpx;
  box-shadow: 0 48rpx 128rpx rgba(0, 0, 0, 0.4);
}

.pm-container.theme-light {
  background: rgba(255, 250, 244, 0.96);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 28rpx 80rpx rgba(118, 101, 80, 0.18);
}

.pm-close {
  position: absolute;
  top: 24rpx;
  right: 24rpx;
  width: 52rpx;
  height: 52rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  z-index: 1;
}

.pm-close:active {
  background: rgba(255, 255, 255, 0.16);
}

.pm-close-icon {
  font-size: 36rpx;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1;
}

.theme-light .pm-close {
  background: rgba(63, 53, 42, 0.06);
}

.theme-light .pm-close:active {
  background: rgba(63, 53, 42, 0.1);
}

.theme-light .pm-close-icon {
  color: rgba(31, 26, 22, 0.56);
}

.pm-header {
  margin-bottom: 32rpx;
}

.pm-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #fff;
}

.theme-light .pm-title {
  color: #1F1A16;
}

.pm-plan-info {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 24rpx;
  padding: 28rpx;
  margin-bottom: 32rpx;
}

.theme-light .pm-plan-info {
  background: rgba(255, 255, 255, 0.78);
  border-color: rgba(63, 53, 42, 0.08);
}

.pm-plan-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10rpx 0;
}

.pm-plan-label {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
}

.theme-light .pm-plan-label {
  color: rgba(31, 26, 22, 0.52);
}

.pm-plan-value {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.88);
  font-weight: 500;
}

.theme-light .pm-plan-value {
  color: rgba(31, 26, 22, 0.84);
}

.pm-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.06);
  margin: 14rpx 0;
}

.theme-light .pm-divider {
  background: rgba(63, 53, 42, 0.08);
}

.pm-plan-row-total {
  padding-top: 14rpx;
}

.pm-plan-price {
  font-size: 40rpx;
  font-weight: 800;
  color: #60a5fa;
}

.pm-pay-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 20rpx;
  border: none;
  background: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-pay-btn::after {
  border: none;
}

.pm-pay-btn:active {
  opacity: 0.85;
}

.pm-pay-btn-loading {
  opacity: 0.7;
}

.pm-pay-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #fff;
}

.pm-loading-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.8);
}

/* Tabs */
.pm-tabs {
  display: flex;
  gap: 16rpx;
  margin-bottom: 28rpx;
}

.pm-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  height: 72rpx;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.theme-light .pm-tab {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(63, 53, 42, 0.08);
}

.pm-tab:active {
  opacity: 0.8;
}

.pm-tab-active {
  background: rgba(22, 119, 255, 0.12);
  border-color: rgba(22, 119, 255, 0.4);
}

.pm-tab-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.theme-light .pm-tab-text {
  color: rgba(31, 26, 22, 0.62);
}

.pm-tab-active .pm-tab-text {
  color: #60a5fa;
}

/* QR Code */
.pm-qr-section {
  display: flex;
  justify-content: center;
  padding: 20rpx 0;
}

.pm-qr-img {
  width: 360rpx;
  height: 360rpx;
  border-radius: 20rpx;
  background: #fff;
}

/* Amount */
.pm-amount-section {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 12rpx;
  margin: 12rpx 0 6rpx;
}

.pm-amount-label {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.5);
}

.theme-light .pm-amount-label {
  color: rgba(31, 26, 22, 0.52);
}

.pm-amount-value {
  font-size: 52rpx;
  font-weight: 800;
  color: #f59e0b;
}

.pm-hint {
  display: block;
  text-align: center;
  margin-top: 6rpx;
  margin-bottom: 28rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.35);
}

.theme-light .pm-hint {
  color: rgba(31, 26, 22, 0.48);
}

.pm-save-btn {
  width: 100%;
  height: 72rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16rpx;
}

.theme-light .pm-save-btn {
  border-color: rgba(63, 53, 42, 0.1);
  background: rgba(255, 255, 255, 0.76);
}

.pm-save-btn::after {
  border: none;
}

.pm-save-btn:active {
  opacity: 0.7;
}

.pm-save-text {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
}

.theme-light .pm-save-text {
  color: rgba(31, 26, 22, 0.62);
}

.pm-confirm-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 20rpx;
  border: none;
  background: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-confirm-btn::after {
  border: none;
}

.pm-confirm-btn:active {
  opacity: 0.85;
}

.pm-confirm-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #fff;
}

.pm-error {
  display: block;
  text-align: center;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #f87171;
}

.theme-light .pm-submitted-icon-wrap {
  background: rgba(47, 110, 234, 0.12);
}

/* Submitted State */
.pm-submitted-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28rpx 0;
  gap: 20rpx;
}

.pm-submitted-icon-wrap {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  background: rgba(96, 165, 250, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-submitted-icon {
  font-size: 48rpx;
  color: #60a5fa;
}

.pm-submitted-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #fff;
}

.theme-light .pm-submitted-title {
  color: #1F1A16;
}

.pm-submitted-desc {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.55);
  text-align: center;
  line-height: 1.6;
}

.theme-light .pm-submitted-desc {
  color: rgba(31, 26, 22, 0.54);
}

.pm-done-btn {
  margin-top: 12rpx;
  width: 100%;
  height: 80rpx;
  border-radius: 20rpx;
  border: none;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-done-btn::after {
  border: none;
}

.pm-done-btn:active {
  opacity: 0.85;
}

.pm-done-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #fff;
}
</style>
