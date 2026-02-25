<template>
  <view v-if="visible" class="pm-overlay" @tap.self="handleClose">
    <view class="pm-container" :class="{ 'pm-submitted': showSubmitted }">
      <!-- Close button -->
      <view class="pm-close" @tap="handleClose">
        <text class="pm-close-icon">×</text>
      </view>

      <!-- State 1: Confirm & Pay -->
      <template v-if="!showSubmitted && !showQrCode">
        <view class="pm-header">
          <text class="pm-title">确认订阅</text>
        </view>

        <view class="pm-plan-info">
          <view class="pm-plan-row">
            <text class="pm-plan-label">方案</text>
            <text class="pm-plan-value">{{ planDisplayName }}</text>
          </view>
          <view class="pm-plan-row">
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
            <image class="pm-tab-icon" src="/static/icons/alipay.svg" mode="aspectFit" />
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
          <button class="pm-done-btn" @tap="handleDone">知道了</button>
        </view>
      </template>
    </view>
  </view>
</template>

<script>
import { createOrder, notifyPaid } from '@/api/payment'

const TIER_MAP = {
  PLUS: 'BASIC',
  ULTRA: 'PREMIUM'
}

const TIER_LABELS = {
  BASIC: 'Plus',
  PREMIUM: 'Ultra'
}

const CYCLE_LABELS = {
  monthly: '月付',
  semester: '学期包（4个月）',
  yearly: '年付'
}

const QR_CODE_MAP = {
  PLUS_monthly: { cycle: 'month', plan: 'plus', price: '12-9' },
  PLUS_semester: { cycle: '4-month', plan: 'plus', price: '38' },
  PLUS_yearly: { cycle: 'year', plan: 'plus', price: '92' },
  ULTRA_monthly: { cycle: 'month', plan: 'ultra', price: '36-9' },
  ULTRA_semester: { cycle: '4-month', plan: 'ultra', price: '108' },
  ULTRA_yearly: { cycle: 'year', plan: 'ultra', price: '268' },
}

export default {
  props: {
    visible: { type: Boolean, default: false },
    plan: { type: Object, default: null },
    billingCycle: { type: String, default: 'semester' }
  },
  emits: ['close', 'success'],
  data() {
    return {
      loading: false,
      showSubmitted: false,
      showQrCode: false,
      submitting: false,
      errorMsg: '',
      orderId: null,
      orderAmount: '',
      payMethod: 'alipay'
    }
  },
  computed: {
    backendTier() {
      if (!this.plan) return ''
      return TIER_MAP[this.plan.id] || this.plan.id
    },
    planDisplayName() {
      return this.plan?.name || ''
    },
    cycleDisplayName() {
      return CYCLE_LABELS[this.billingCycle] || this.billingCycle
    },
    priceDisplay() {
      if (!this.plan) return ''
      const pricing = this.plan.pricing?.[this.billingCycle]
      return pricing ? `${pricing.main}` : ''
    },
    qrCodeSrc() {
      const key = `${this.plan?.id}_${this.billingCycle}`
      const entry = QR_CODE_MAP[key]
      if (!entry) return '/static/payment/alipay-qr.png'
      const method = this.payMethod === 'alipay' ? 'alipay' : 'wechat'
      return `/static/payment/${method}-qr-${entry.cycle}-${entry.plan}(${entry.price}).png`
    }
  },
  watch: {
    visible(val) {
      if (!val) {
        this.reset()
      }
    }
  },
  methods: {
    reset() {
      this.loading = false
      this.showSubmitted = false
      this.showQrCode = false
      this.submitting = false
      this.errorMsg = ''
      this.orderId = null
      this.orderAmount = ''
      this.payMethod = 'alipay'
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
          tier: this.backendTier,
          billing_cycle: this.billingCycle
        })

        this.orderId = resp.order_id
        this.orderAmount = resp.amount_display
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
    handleDone() {
      this.$emit('close')
    }
  }
}
</script>

<style scoped>
.pm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.pm-container {
  position: relative;
  width: 400px;
  max-width: 90vw;
  border-radius: 20px;
  background: rgba(22, 25, 42, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 28px 24px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
}

.pm-close {
  position: absolute;
  top: 12px;
  right: 14px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.2s;
}

.pm-close:hover {
  background: rgba(255, 255, 255, 0.08);
}

.pm-close-icon {
  font-size: 20px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
}

.pm-header {
  margin-bottom: 20px;
}

.pm-title {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.pm-plan-info {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 20px;
}

.pm-plan-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.pm-plan-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.pm-plan-value {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.88);
  font-weight: 500;
}

.pm-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 8px 0;
}

.pm-plan-row-total {
  padding-top: 8px;
}

.pm-plan-price {
  font-size: 22px;
  font-weight: 800;
  color: #60a5fa;
}

.pm-pay-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  border: none;
  background: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pm-pay-btn::after {
  border: none;
}

.pm-pay-btn:hover {
  background: #0f6ae8;
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.3);
}

.pm-pay-btn-loading {
  opacity: 0.7;
  cursor: not-allowed;
}

.pm-pay-text {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.pm-loading-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

/* Tabs */
.pm-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.pm-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: all 0.2s;
}

.pm-tab-active {
  background: rgba(22, 119, 255, 0.12);
  border-color: rgba(22, 119, 255, 0.4);
}

.pm-tab-icon {
  width: 18px;
  height: 18px;
}

.pm-tab-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.pm-tab-active .pm-tab-text {
  color: #60a5fa;
}

/* QR Code */
.pm-qr-section {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

.pm-qr-img {
  width: 200px;
  height: 200px;
  border-radius: 12px;
  background: #fff;
}

/* Amount */
.pm-amount-section {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 8px;
  margin: 8px 0 4px;
}

.pm-amount-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.pm-amount-value {
  font-size: 28px;
  font-weight: 800;
  color: #f59e0b;
}

.pm-hint {
  display: block;
  text-align: center;
  margin-top: 4px;
  margin-bottom: 16px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}

.pm-confirm-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  border: none;
  background: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pm-confirm-btn::after {
  border: none;
}

.pm-confirm-btn:hover {
  background: #059669;
}

.pm-confirm-text {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.pm-error {
  display: block;
  text-align: center;
  margin-top: 10px;
  font-size: 12px;
  color: #f87171;
}

/* Submitted State */
.pm-submitted-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  gap: 12px;
}

.pm-submitted-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(96, 165, 250, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-submitted-icon {
  font-size: 28px;
  color: #60a5fa;
}

.pm-submitted-title {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.pm-submitted-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  text-align: center;
  line-height: 1.6;
}

.pm-done-btn {
  margin-top: 8px;
  width: 100%;
  height: 44px;
  border-radius: 11px;
  border: none;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pm-done-btn::after {
  border: none;
}

.pm-done-btn:hover {
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
}
</style>
