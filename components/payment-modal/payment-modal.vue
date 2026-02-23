<template>
  <view v-if="visible" class="pm-overlay" @tap.self="handleClose">
    <view class="pm-container" :class="{ 'pm-success': showSuccess }">
      <!-- Close button -->
      <view class="pm-close" @tap="handleClose">
        <text class="pm-close-icon">×</text>
      </view>

      <!-- State 1: Confirm & Pay -->
      <template v-if="!showSuccess && !showQrCode">
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
      <template v-if="showQrCode && !showSuccess">
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
          <image
            v-if="payMethod === 'alipay'"
            class="pm-qr-img"
            src="/static/payment/alipay-qr.png"
            mode="aspectFit"
          />
          <image
            v-else
            class="pm-qr-img"
            src="/static/payment/wechat-qr.png"
            mode="aspectFit"
          />
        </view>

        <!-- Amount -->
        <view class="pm-amount-section">
          <text class="pm-amount-label">请支付</text>
          <text class="pm-amount-value">{{ orderAmount }}</text>
        </view>

        <text class="pm-hint">请使用{{ payMethod === 'alipay' ? '支付宝' : '微信' }}扫描上方二维码完成支付</text>

        <!-- Confirm button -->
        <button class="pm-confirm-btn" @tap="handleConfirmPaid">
          <text class="pm-confirm-text">{{ polling ? '等待管理员确认中...' : '我已支付' }}</text>
        </button>

        <text v-if="polling" class="pm-waiting-hint">
          管理员收到通知后会尽快确认，请稍候
        </text>

        <text v-if="errorMsg" class="pm-error">{{ errorMsg }}</text>
      </template>

      <!-- State 3: Success -->
      <template v-if="showSuccess">
        <view class="pm-success-content">
          <view class="pm-success-icon-wrap">
            <text class="pm-success-check">✓</text>
          </view>
          <text class="pm-success-title">订阅成功</text>
          <text class="pm-success-desc">
            已开通 {{ planDisplayName }}，有效期至 {{ expiryDisplay }}
          </text>
          <button class="pm-done-btn" @tap="handleDone">开始使用</button>
        </view>
      </template>
    </view>
  </view>
</template>

<script>
import { createOrder, getOrderStatus } from '@/api/payment'
import { getMe } from '@/api/auth'
import { useUserStore } from '@/store/user'

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
      showSuccess: false,
      showQrCode: false,
      polling: false,
      errorMsg: '',
      orderId: null,
      orderAmount: '',
      pollTimer: null,
      pollCount: 0,
      successData: null,
      payMethod: 'alipay'
    }
  },
  computed: {
    backendTier() {
      if (!this.plan) return ''
      return TIER_MAP[this.plan.id] || this.plan.id
    },
    planDisplayName() {
      if (this.successData) return TIER_LABELS[this.successData.target_tier] || this.successData.target_tier
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
    expiryDisplay() {
      if (!this.successData?.subscription_expires_at) return ''
      const d = new Date(this.successData.subscription_expires_at)
      if (Number.isNaN(d.getTime())) return ''
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd}`
    }
  },
  watch: {
    visible(val) {
      if (!val) {
        this.reset()
      }
    }
  },
  beforeUnmount() {
    this.stopPolling()
  },
  methods: {
    reset() {
      this.loading = false
      this.showSuccess = false
      this.showQrCode = false
      this.polling = false
      this.errorMsg = ''
      this.orderId = null
      this.orderAmount = ''
      this.successData = null
      this.pollCount = 0
      this.payMethod = 'alipay'
      this.stopPolling()
    },
    handleClose() {
      this.stopPolling()
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
    handleConfirmPaid() {
      if (this.polling) return
      this.polling = true
      this.errorMsg = ''
      this.startPolling()
    },
    startPolling() {
      this.pollCount = 0
      this.stopPolling()
      this.pollTimer = setInterval(() => {
        this.pollOrderStatus()
      }, 3000)
    },
    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    async pollOrderStatus() {
      if (!this.orderId) return
      this.pollCount++

      // Stop after 10 minutes
      if (this.pollCount > 200) {
        this.stopPolling()
        this.polling = false
        this.errorMsg = '等待确认超时，请联系管理员'
        return
      }

      try {
        const order = await getOrderStatus(this.orderId)

        if (order.status === 'paid') {
          this.stopPolling()
          this.polling = false
          const user = await getMe()
          const userStore = useUserStore()
          userStore.setUser(user)

          this.successData = {
            ...order,
            subscription_expires_at: user.subscription_expires_at
          }
          this.showSuccess = true
          this.showQrCode = false
          this.$emit('success', {
            subscription_tier: user.subscription_tier,
            subscription_expires_at: user.subscription_expires_at
          })
        } else if (order.status === 'expired' || order.status === 'cancelled') {
          this.stopPolling()
          this.polling = false
          this.errorMsg = '订单已过期，请重新下单'
        }
      } catch {
        // Ignore polling errors silently
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

.pm-waiting-hint {
  display: block;
  text-align: center;
  margin-top: 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.pm-error {
  display: block;
  text-align: center;
  margin-top: 10px;
  font-size: 12px;
  color: #f87171;
}

/* Success State */
.pm-success-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  gap: 12px;
}

.pm-success-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(16, 185, 129, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-success-check {
  font-size: 28px;
  font-weight: 700;
  color: #10b981;
}

.pm-success-title {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.pm-success-desc {
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
