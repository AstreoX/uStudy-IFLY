<template>
  <view class="subscription-page">
    <!-- Aurora Background Layer -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="sub-nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">订阅管理</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Scroll Content -->
    <scroll-view class="sub-scroll" scroll-y>
      <view class="sub-content">

        <!-- Hero Section -->
        <view class="hero-section">
          <text class="hero-eyebrow">uStudy Subscription</text>
          <text class="hero-title">选择你的学习引擎</text>
          <view class="hero-current-strip">
            <text class="hero-current-label">当前方案</text>
            <view :class="['tier-chip', `tier-chip-${normalizedTier.toLowerCase()}`]">
              <text class="tier-chip-text">{{ tierLabel }}</text>
            </view>
            <text v-if="user?.subscription_expires_at" class="hero-current-expiry">
              · {{ formatTime(user.subscription_expires_at) }} 到期
            </text>
          </view>
        </view>

        <!-- Billing Cycle Switch -->
        <view class="billing-switch">
          <view
            v-for="cycle in billingCycles"
            :key="cycle.id"
            class="billing-item"
            :class="{ 'billing-item-active': billingCycle === cycle.id }"
            @tap="billingCycle = cycle.id"
          >
            <text class="billing-label">{{ cycle.label }}</text>
            <text v-if="cycle.tag" class="billing-tag">{{ cycle.tag }}</text>
          </view>
        </view>

        <!-- Plan Cards -->
        <view class="plans-list">
          <view
            v-for="plan in plans"
            :key="plan.id"
            class="plan-card"
            :class="[
              `plan-card-${plan.id.toLowerCase()}`,
              { 'plan-card-current': isCurrentPlan(plan.id), 'plan-card-recommended': plan.recommended }
            ]"
          >
            <!-- Recommended ribbon -->
            <view v-if="plan.recommended" class="plan-ribbon">
              <text class="plan-ribbon-text">最受欢迎</text>
            </view>

            <view class="plan-top-row">
              <text class="plan-name">{{ plan.name }}</text>
              <view v-if="isCurrentPlan(plan.id)" class="plan-badge-current">
                <text class="plan-badge-text">当前</text>
              </view>
            </view>

            <text class="plan-desc">{{ plan.desc }}</text>

            <view class="plan-price-wrap" :key="billingCycle">
              <text v-if="getDisplayedPrice(plan).monthlyUnitPrice" class="plan-price-strikethrough">{{ getDisplayedPrice(plan).monthlyUnitPrice }}</text>
              <text :class="['plan-price-main', `plan-price-main-${plan.id.toLowerCase()}`]">{{ getDisplayedPrice(plan).main }}</text>
              <text class="plan-price-suffix">{{ getDisplayedPrice(plan).suffix }}</text>
            </view>
            <text class="plan-price-label">{{ getDisplayedPrice(plan).label }}</text>
            <text v-if="getDisplayedPrice(plan).hint" class="plan-price-hint" :class="{ 'plan-price-hint-ultra': plan.id === 'ULTRA' }">{{ getDisplayedPrice(plan).hint }}</text>

            <view class="plan-divider"></view>

            <view class="feature-list">
              <view v-for="feature in plan.features" :key="feature" class="feature-item">
                <view :class="['feature-icon', `feature-icon-${plan.id.toLowerCase()}`]">
                  <text class="feature-check">✓</text>
                </view>
                <text class="feature-text">{{ feature }}</text>
              </view>
              <template v-if="plan.limitations">
                <view v-for="limit in plan.limitations" :key="limit" class="feature-item">
                  <view class="feature-icon feature-icon-limit">
                    <text class="feature-cross">✕</text>
                  </view>
                  <text class="feature-text feature-text-limit">{{ limit }}</text>
                </view>
              </template>
            </view>

            <button
              class="plan-btn"
              :class="[`plan-btn-${plan.id.toLowerCase()}`, { 'plan-btn-current': isCurrentPlan(plan.id) }]"
              :disabled="isCurrentPlan(plan.id) || plan.id === 'FREE'"
              @tap="handleSelectPlan(plan)"
            >
              <text class="plan-btn-text" :class="{ 'plan-btn-text-current': isCurrentPlan(plan.id) }">
                {{ isCurrentPlan(plan.id) ? '当前方案' : plan.buttonText }}
              </text>
            </button>
          </view>
        </view>

        <!-- Comparison Table -->
        <view class="compare-card">
          <text class="compare-title">核心权益对比</text>
          <scroll-view class="compare-table-wrap" scroll-x>
            <view class="compare-table">
              <view class="compare-row compare-head">
                <text class="compare-cell compare-metric">权益项</text>
                <text class="compare-cell compare-head-free">Free</text>
                <text class="compare-cell compare-head-plus">Plus</text>
                <text class="compare-cell compare-head-ultra">Ultra</text>
              </view>
              <view
                v-for="(row, idx) in compareRows"
                :key="row.metric"
                class="compare-row"
                :class="{ 'compare-row-alt': idx % 2 === 1 }"
              >
                <text class="compare-cell compare-metric">{{ row.metric }}</text>
                <text class="compare-cell compare-val-free">{{ row.free }}</text>
                <text class="compare-cell compare-val-plus">{{ row.plus }}</text>
                <text class="compare-cell compare-val-ultra">{{ row.ultra }}</text>
              </view>
            </view>
          </scroll-view>
        </view>

      </view>
    </scroll-view>

    <!-- Payment Modal -->
    <PaymentModal
      :visible="showPaymentModal"
      :plan="selectedPlan"
      :billing-cycle="billingCycle"
      @close="showPaymentModal = false"
      @success="handlePaymentSuccess"
    />
  </view>
</template>

<script>
import PaymentModal from '@/components/payment-modal/payment-modal.vue'
import { getMe } from '@/api/auth'
import { useUserStore } from '@/store/user'
import { getTokens } from '@/utils/storage'
import { goBack } from '@/utils/navigation'

export default {
  components: {
    PaymentModal
  },
  data() {
    return {
      user: null,
      showPaymentModal: false,
      selectedPlan: null,
      billingCycle: 'semester',
      billingCycles: [
        { id: 'monthly', label: '月付' },
        { id: 'semester', label: '学期包', tag: '省 25%' },
        { id: 'yearly', label: '年付', tag: '省 40%' }
      ],
      plans: [
        {
          id: 'FREE',
          name: 'Free',
          desc: '轻量体验，适合刚开始使用',
          buttonText: '开始使用',
          pricing: {
            monthly: { main: '¥0', suffix: '', label: '永久免费' },
            semester: { main: '¥0', suffix: '', label: '永久免费' },
            yearly: { main: '¥0', suffix: '', label: '永久免费' }
          },
          features: [
            '最多创建 1 个学习空间',
            '每日 AI 对话上限 20 次',
            '模型：Qwen 3.5',
            '每个学习空间知识库上限 30MB',
            '单文件上传上限 10MB'
          ],
          limitations: [
            '不支持高级模型',
            '无优先客服支持'
          ]
        },
        {
          id: 'PLUS',
          name: 'Plus',
          desc: '主力学习方案，覆盖日常学习全场景',
          buttonText: '选择 Plus',
          recommended: true,
          pricing: {
            monthly: { main: '¥12.9', suffix: '/月', label: '月付' },
            semester: { main: '¥38', suffix: '/4个月', label: '学期包（4个月）', hint: '折合 ¥9.5/月', monthlyUnitPrice: '¥12.9/月' },
            yearly: { main: '¥92', suffix: '/年', label: '年付', hint: '折合 ¥7.7/月', monthlyUnitPrice: '¥12.9/月' }
          },
          features: [
            '最多创建 5 个学习空间',
            '每日 AI 对话上限 150 次',
            '模型：Qwen 3.5 + Kimi K2.5',
            '每个学习空间知识库上限 200MB',
            '单文件上传上限 50MB',
            '优先客服响应'
          ]
        },
        {
          id: 'ULTRA',
          name: 'Ultra',
          desc: '顶尖模型 + 无限额度，为重度学习者打造',
          buttonText: '选择 Ultra',
          pricing: {
            monthly: { main: '¥36.9', suffix: '/月', label: '月付' },
            semester: { main: '¥108', suffix: '/4个月', label: '学期包（4个月）', hint: '折合 ¥27/月', monthlyUnitPrice: '¥36.9/月' },
            yearly: { main: '¥268', suffix: '/年', label: '年付', hint: '折合 ¥22.3/月', monthlyUnitPrice: '¥36.9/月' }
          },
          features: [
            '学习空间数量不限',
            '每日 AI 对话不限',
            '全部模型：Qwen 3.5 / Kimi K2.5 / Gemini-3.1-pro',
            '每个学习空间知识库上限 500MB',
            '单文件上传上限 100MB',
            '优先客服 + 新功能抢先体验'
          ]
        }
      ],
      compareRows: [
        { metric: '学习空间数量', free: '1', plus: '5', ultra: '不限' },
        { metric: '每日 AI 对话', free: '20 次', plus: '150 次', ultra: '不限' },
        { metric: '模型能力', free: 'Qwen 3.5', plus: 'Qwen 3.5 + Kimi', ultra: 'Qwen 3.5 / Kimi / Gemini' },
        { metric: '单空间知识库', free: '30MB', plus: '200MB', ultra: '500MB' },
        { metric: '单文件上传', free: '10MB', plus: '50MB', ultra: '100MB' },
        { metric: '优先客服', free: '—', plus: '✓', ultra: '✓' },
        { metric: '新功能抢先体验', free: '—', plus: '—', ultra: '✓' }
      ]
    }
  },
  computed: {
    normalizedTier() {
      const tier = (this.user?.subscription_tier || 'FREE').toUpperCase()
      if (['FREE', 'PLUS', 'ULTRA', 'ALPHA'].includes(tier)) return tier
      if (tier === 'BASIC') return 'PLUS'
      if (tier === 'PREMIUM') return 'ULTRA'
      return 'FREE'
    },
    tierLabel() {
      const labels = {
        FREE: 'Free',
        PLUS: 'Plus',
        ULTRA: 'Ultra',
        ALPHA: 'Alpha'
      }
      return labels[this.normalizedTier] || 'Free'
    }
  },
  onShow() {
    this.loadUser()
  },
  methods: {
    goBack() {
      goBack()
    },
    async loadUser() {
      const tokens = getTokens()
      if (!tokens || !tokens.access_token) {
        uni.reLaunch({ url: '/pages/login/login' })
        return
      }

      try {
        const user = await getMe()
        this.user = user
        useUserStore().setUser(user)
      } catch {
        this.user = null
      }
    },
    getDisplayedPrice(plan) {
      if (!plan || !plan.pricing) {
        return { main: '', suffix: '', label: '' }
      }
      return plan.pricing[this.billingCycle] || plan.pricing.monthly || { main: '', suffix: '', label: '' }
    },
    isCurrentPlan(planId) {
      if (this.normalizedTier === 'ALPHA') return planId === 'ULTRA'
      return this.normalizedTier === planId
    },
    handleSelectPlan(plan) {
      if (this.isCurrentPlan(plan.id) || plan.id === 'FREE') return
      this.selectedPlan = plan
      this.showPaymentModal = true
    },
    handlePaymentSuccess(response) {
      const userStore = useUserStore()
      userStore.updateSubscription(
        response.subscription_tier,
        response.subscription_expires_at
      )
      this.user = {
        ...(this.user || {}),
        subscription_tier: response.subscription_tier,
        subscription_expires_at: response.subscription_expires_at
      }
    },
    formatTime(value) {
      if (!value) return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      const yyyy = date.getFullYear()
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      const dd = String(date.getDate()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd}`
    }
  }
}
</script>

<style>
.subscription-page {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A12;
  position: relative;
  overflow: hidden;
}

/* Aurora Background */
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
  width: 900rpx;
  height: 900rpx;
  background: radial-gradient(circle, #1A6AFF 0%, rgba(26, 106, 255, 0.3) 40%, transparent 70%);
  top: -250rpx;
  left: -200rpx;
  animation: aurora-blue 14s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 850rpx;
  height: 850rpx;
  background: radial-gradient(circle, #FF6A1A 0%, rgba(255, 106, 26, 0.3) 40%, transparent 70%);
  bottom: -200rpx;
  right: -200rpx;
  animation: aurora-orange 16s ease-in-out infinite;
}

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

/* Navigation Bar - 磨砂玻璃效果 */
.sub-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: calc(100vh * 0.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

/* 磨砂玻璃背景层 - 渐变过渡 */
.sub-nav-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: -70rpx;
  z-index: -1;
  background: linear-gradient(
    to bottom,
    rgba(10, 10, 18, 0.6) 0%,
    rgba(10, 10, 18, 0.45) 50%,
    rgba(10, 10, 18, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
}

/* 不支持 backdrop-filter 的降级方案 */
@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .sub-nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(10, 10, 18, 0.95) 0%,
      rgba(10, 10, 18, 0.8) 50%,
      rgba(10, 10, 18, 0) 100%
    );
  }
}

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-left {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

/* Scroll Content */
.sub-scroll {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100vh;
}

.sub-content {
  padding-top: calc(100vh * 3.5 / 26);
  padding-bottom: calc(60rpx + env(safe-area-inset-bottom));
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

/* Hero Section */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40rpx 0 24rpx;
  gap: 16rpx;
}

.hero-eyebrow {
  font-size: 22rpx;
  color: rgba(147, 197, 253, 0.85);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600;
}

.hero-title {
  font-size: 56rpx;
  line-height: 1.1;
  color: #fff;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hero-current-strip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 8rpx;
  flex-wrap: wrap;
  justify-content: center;
}

.hero-current-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.38);
  font-weight: 500;
}

.hero-current-expiry {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.32);
}

.tier-chip {
  height: 48rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tier-chip-text {
  font-size: 24rpx;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.03em;
}

.tier-chip-free {
  background: rgba(156, 163, 175, 0.18);
  border: 1rpx solid rgba(156, 163, 175, 0.15);
}

.tier-chip-plus {
  background: rgba(59, 130, 246, 0.2);
  border: 1rpx solid rgba(59, 130, 246, 0.25);
}

.tier-chip-ultra {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(79, 70, 229, 0.2));
  border: 1rpx solid rgba(139, 92, 246, 0.3);
}

.tier-chip-alpha {
  background: rgba(16, 185, 129, 0.18);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
}

/* Billing Cycle Switch */
.billing-switch {
  margin-top: 24rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  padding: 8rpx;
  display: flex;
  gap: 8rpx;
}

.billing-item {
  flex: 1;
  height: 80rpx;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  border: 1rpx solid transparent;
}

.billing-item:active {
  opacity: 0.8;
}

.billing-item-active {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 4rpx 24rpx rgba(59, 130, 246, 0.12);
}

.billing-label {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.78);
  font-weight: 500;
}

.billing-item-active .billing-label {
  color: rgba(255, 255, 255, 0.95);
}

.billing-tag {
  font-size: 20rpx;
  color: #60a5fa;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.12);
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

/* Plan Cards */
.plans-list {
  margin-top: 32rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.plan-card {
  position: relative;
  border-radius: 28rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(18, 21, 38, 0.78);
  backdrop-filter: blur(24rpx);
  -webkit-backdrop-filter: blur(24rpx);
  padding: 36rpx 32rpx;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .plan-card {
    background: rgba(18, 21, 38, 0.92);
  }
}

.plan-card-recommended {
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 0 0 1rpx rgba(59, 130, 246, 0.2) inset, 0 16rpx 64rpx rgba(59, 130, 246, 0.08);
  padding-top: 72rpx;
}

.plan-card-ultra {
  border-color: rgba(139, 92, 246, 0.2);
}

.plan-card-current {
  border-color: rgba(16, 185, 129, 0.35);
  box-shadow: 0 0 0 1rpx rgba(16, 185, 129, 0.15) inset;
}

/* Ribbon */
.plan-ribbon {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 52rpx;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 27rpx 27rpx 0 0;
  z-index: 3;
}

.plan-ribbon-text {
  font-size: 22rpx;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.06em;
}

.plan-top-row {
  display: flex;
  justify-content: space-between;
  gap: 12rpx;
  align-items: flex-start;
}

.plan-name {
  font-size: 44rpx;
  line-height: 1.15;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.01em;
}

.plan-card-ultra .plan-name {
  color: #a78bfa;
  background: linear-gradient(135deg, #c084fc, #818cf8, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.plan-badge-current {
  height: 40rpx;
  border-radius: 999rpx;
  padding: 0 16rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 185, 129, 0.2);
  border: 1rpx solid rgba(16, 185, 129, 0.2);
}

.plan-badge-text {
  font-size: 20rpx;
  font-weight: 600;
  color: #6ee7b7;
  letter-spacing: 0.03em;
}

.plan-desc {
  margin-top: 12rpx;
  font-size: 26rpx;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.5);
}

/* Pricing */
.plan-price-wrap {
  margin-top: 24rpx;
  display: flex;
  align-items: flex-end;
  gap: 8rpx;
}

.plan-price-main {
  font-size: 64rpx;
  line-height: 1;
  color: #fff;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.plan-price-main-plus {
  color: #60a5fa;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.plan-price-main-ultra {
  color: #a78bfa;
  background: linear-gradient(135deg, #c084fc, #8b5cf6, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.plan-price-suffix {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 8rpx;
  font-weight: 500;
}

.plan-price-strikethrough {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.35);
  text-decoration: line-through;
  margin-right: 12rpx;
  margin-bottom: 8rpx;
  font-weight: 500;
}

.plan-price-label {
  margin-top: 6rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
}

.plan-price-hint {
  margin-top: 4rpx;
  font-size: 24rpx;
  color: #60a5fa;
  font-weight: 500;
}

.plan-price-hint-ultra {
  color: #a78bfa;
}

.plan-divider {
  margin: 28rpx 0 20rpx;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
}

/* Feature List */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.feature-item {
  display: flex;
  gap: 16rpx;
  align-items: flex-start;
}

.feature-icon {
  width: 36rpx;
  height: 36rpx;
  border-radius: 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2rpx;
}

.feature-icon-free {
  background: rgba(156, 163, 175, 0.15);
}

.feature-icon-plus {
  background: rgba(59, 130, 246, 0.15);
}

.feature-icon-ultra {
  background: rgba(139, 92, 246, 0.15);
}

.feature-check {
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1;
}

.feature-icon-free .feature-check {
  color: rgba(156, 163, 175, 0.7);
}

.feature-icon-plus .feature-check {
  color: #60a5fa;
}

.feature-icon-ultra .feature-check {
  color: #a78bfa;
}

.feature-icon-limit {
  background: rgba(239, 68, 68, 0.1);
}

.feature-cross {
  font-size: 20rpx;
  font-weight: 700;
  line-height: 1;
  color: rgba(239, 68, 68, 0.5);
}

.feature-text {
  font-size: 26rpx;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.75);
}

.feature-text-limit {
  color: rgba(255, 255, 255, 0.4);
}

/* Plan Buttons */
.plan-btn {
  margin-top: 32rpx;
  width: 100%;
  height: 84rpx;
  border-radius: 20rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.plan-btn::after {
  border: none;
}

.plan-btn:active {
  opacity: 0.85;
  transform: scale(0.98);
}

.plan-btn-free {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.plan-btn-free[disabled] {
  opacity: 1;
}

.plan-btn-free .plan-btn-text {
  color: #5a5a6e;
  font-weight: 600;
}

.plan-btn-plus {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  box-shadow: 0 8rpx 32rpx rgba(37, 99, 235, 0.25);
}

.plan-btn-ultra {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  box-shadow: 0 8rpx 32rpx rgba(124, 58, 237, 0.25);
}

.plan-btn-current {
  background: rgba(16, 185, 129, 0.15);
  box-shadow: none;
}

.plan-btn-current:active {
  opacity: 1;
  transform: none;
}

.plan-btn-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #fff;
}

.plan-btn-text-current {
  color: #4a9a7a;
}

/* Comparison Table */
.compare-card {
  margin-top: 40rpx;
  border-radius: 28rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  padding: 32rpx;
}

.compare-title {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.92);
  font-weight: 700;
  letter-spacing: -0.01em;
}

.compare-table-wrap {
  margin-top: 20rpx;
  width: 100%;
}

.compare-table {
  min-width: 640rpx;
  border-radius: 20rpx;
  overflow: hidden;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.compare-row {
  display: flex;
}

.compare-head {
  background: rgba(255, 255, 255, 0.04);
}

.compare-row:not(.compare-head) {
  background: rgba(255, 255, 255, 0.015);
  border-top: 1rpx solid rgba(255, 255, 255, 0.04);
}

.compare-row-alt {
  background: rgba(255, 255, 255, 0.025) !important;
}

.compare-cell {
  flex: 1;
  min-height: 80rpx;
  padding: 18rpx 16rpx;
  box-sizing: border-box;
  font-size: 22rpx;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.72);
  display: flex;
  align-items: center;
}

.compare-metric {
  flex: 1.3;
  color: rgba(255, 255, 255, 0.88);
  font-weight: 600;
  font-size: 24rpx;
}

.compare-head-free,
.compare-head-plus,
.compare-head-ultra {
  font-weight: 700;
  font-size: 24rpx;
}

.compare-head-free {
  color: rgba(156, 163, 175, 0.85);
}

.compare-head-plus {
  color: #60a5fa;
}

.compare-head-ultra {
  color: #a78bfa;
}

.compare-val-free {
  color: rgba(255, 255, 255, 0.55);
}

.compare-val-plus {
  color: rgba(96, 165, 250, 0.85);
  font-weight: 500;
}

.compare-val-ultra {
  color: rgba(167, 139, 250, 0.85);
  font-weight: 500;
}
</style>
