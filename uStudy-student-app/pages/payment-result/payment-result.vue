<template>
  <view class="payment-result-page">
    <view class="result-panel">
      <text class="result-title">{{ title }}</text>
      <text class="result-desc">{{ description }}</text>
      <text v-if="orderStatus" class="result-status">订单状态：{{ orderStatus }}</text>
      <button class="result-button" @tap="goSubscription">
        <text class="result-button-text">返回会员中心</text>
      </button>
    </view>
  </view>
</template>

<script>
import { getPaymentOrder } from '@/api/payment'

const FINAL_STATUSES = ['paid', 'expired', 'rejected', 'cancelled']

export default {
  data() {
    return {
      orderId: '',
      orderStatus: '',
      title: '支付结果确认中',
      description: '请稍候，系统正在确认支付宝异步通知',
      pollingTimer: null,
      pollCount: 0
    }
  },
  onLoad(options = {}) {
    this.orderId = options.order_id || ''
    if (!this.orderId) {
      try {
        this.orderId = uni.getStorageSync('pending_payment_order_id') || ''
      } catch {
        this.orderId = ''
      }
    }
    if (!this.orderId) {
      this.title = '无法确认订单'
      this.description = '请返回会员中心查看订单状态'
      return
    }
    this.pollOrderStatus()
  },
  onUnload() {
    this.clearPolling()
  },
  methods: {
    async pollOrderStatus() {
      this.clearPolling()
      await this.refreshOrderStatus()
      if (!FINAL_STATUSES.includes(this.orderStatus)) {
        this.pollingTimer = setInterval(this.refreshOrderStatus, 3000)
      }
    },
    async refreshOrderStatus() {
      if (!this.orderId) return
      this.pollCount += 1
      try {
        const order = await getPaymentOrder(this.orderId)
        this.orderStatus = order.status
        this.applyStatus(order.status)
        if (FINAL_STATUSES.includes(order.status) || this.pollCount >= 20) {
          this.clearPolling()
          if (FINAL_STATUSES.includes(order.status)) {
            this.clearPendingOrderStorage()
          }
          if (!FINAL_STATUSES.includes(order.status)) {
            this.title = '支付确认中'
            this.description = '订单仍在处理中，请稍后返回会员中心查看状态'
          }
        }
      } catch {
        this.title = '暂时无法查询订单'
        this.description = '请稍后返回会员中心查看订单状态'
        this.clearPolling()
      }
    },
    applyStatus(status) {
      if (status === 'paid') {
        this.title = '支付成功'
        this.description = '订单已确认，会员或余额权益将以后台订单状态为准'
      } else if (status === 'pending') {
        this.title = '支付结果确认中'
        this.description = '请稍候，系统正在确认支付宝异步通知'
      } else if (['expired', 'rejected', 'cancelled'].includes(status)) {
        this.title = '支付未完成'
        this.description = '订单未完成或已失效，请返回会员中心重新发起'
      }
    },
    clearPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },
    clearPendingOrderStorage() {
      try {
        uni.removeStorageSync('pending_payment_order_id')
        uni.removeStorageSync('pending_payment_out_trade_no')
      } catch {
        // Best-effort cleanup only.
      }
    },
    goSubscription() {
      uni.redirectTo({
        url: '/pages/subscription/subscription',
        fail: () => {
          uni.navigateBack()
        }
      })
    }
  }
}
</script>

<style scoped>
.payment-result-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx;
  background: linear-gradient(160deg, #0A0A12 0%, #101827 48%, #18221f 100%);
}

.result-panel {
  width: 100%;
  max-width: 640rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  padding: 44rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.result-title {
  font-size: 40rpx;
  font-weight: 800;
  color: #fff;
}

.result-desc,
.result-status {
  font-size: 28rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.68);
}

.result-button {
  margin-top: 12rpx;
  height: 88rpx;
  border-radius: 18rpx;
  background: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-button::after {
  border: none;
}

.result-button-text {
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
}
</style>
