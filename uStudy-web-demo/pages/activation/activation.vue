<template>
  <view class="subscription-page">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @select-space="handleSelectSpace"
      @create-space="handleCreateSpace"
    />

    <view class="subscription-main">
      <scroll-view class="subscription-scroll" scroll-y>
        <view class="subscription-content">
          <!-- Hero Section -->
          <view class="hero-section anim-fade-in" style="animation-delay: 0s">
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
          <view class="billing-switch anim-fade-in" style="animation-delay: 0.06s">
            <view
              v-for="cycle in billingCycles"
              :key="cycle.id"
              class="billing-item"
              :class="{ 'billing-item-active': billingCycle === cycle.id }"
              @tap="switchBillingCycle(cycle.id)"
            >
              <text class="billing-label">{{ cycle.label }}</text>
              <text v-if="cycle.tag" class="billing-tag">{{ cycle.tag }}</text>
            </view>
          </view>

          <!-- Social Proof -->
          <view class="social-proof anim-fade-in" style="animation-delay: 0.08s">
            <text class="social-proof-text">已有 </text>
            <text class="social-proof-count">2,000+</text>
            <text class="social-proof-text"> 学习者选择付费方案</text>
          </view>

          <!-- Plan Cards Grid -->
          <view class="plans-grid">
            <view
              v-for="(plan, index) in plans"
              :key="plan.id"
              class="plan-card anim-fade-in"
              :style="{ animationDelay: `${0.1 + index * 0.08}s` }"
              :class="[
                `plan-card-${plan.id.toLowerCase()}`,
                { 'plan-card-current': isCurrentPlan(plan.id), 'plan-card-recommended': plan.recommended }
              ]"
            >
              <!-- Recommended ribbon banner -->
              <view v-if="plan.recommended" class="plan-ribbon">
                <text class="plan-ribbon-text">最受欢迎</text>
              </view>
              <!-- Recommended glow accent -->
              <view v-if="plan.recommended" class="plan-glow"></view>
              <!-- Ultra shimmer accent -->
              <view v-if="plan.id === 'ULTRA'" class="plan-shimmer"></view>

              <view class="plan-top-row">
                <text class="plan-name">{{ plan.name }}</text>
                <view class="plan-badges">
                  <view v-if="isCurrentPlan(plan.id)" class="plan-badge plan-badge-current">
                    <text class="plan-badge-text">当前</text>
                  </view>
                </view>
              </view>

              <text class="plan-desc">{{ plan.desc }}</text>

              <view class="plan-price-wrap" :key="billingCycle">
                <text v-if="getDisplayedPrice(plan).monthlyUnitPrice" class="plan-price-strikethrough">{{ getDisplayedPrice(plan).monthlyUnitPrice }}</text>
                <text :class="['plan-price-main', `plan-price-main-${plan.id.toLowerCase()}`]">{{ getDisplayedPrice(plan).main }}</text>
                <text class="plan-price-suffix">{{ getDisplayedPrice(plan).suffix }}</text>
              </view>
              <text class="plan-price-label">{{ getDisplayedPrice(plan).label }}</text>
              <text v-if="getDisplayedPrice(plan).hint" class="plan-price-hint">{{ getDisplayedPrice(plan).hint }}</text>

              <view class="plan-divider"></view>

              <view class="feature-list">
                <view v-for="feature in plan.features" :key="feature" class="feature-item">
                  <view :class="['feature-icon', `feature-icon-${plan.id.toLowerCase()}`]">
                    <text class="feature-check">✓</text>
                  </view>
                  <text class="feature-text">{{ feature }}</text>
                </view>
                <template v-if="plan.limitations">
                  <view v-for="limit in plan.limitations" :key="limit" class="feature-item feature-item-limit">
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
                {{ isCurrentPlan(plan.id) ? '当前方案' : plan.buttonText }}
              </button>

            </view>
          </view>

          <!-- Comparison Table -->
          <view class="compare-card anim-fade-in" style="animation-delay: 0.36s">
            <text class="compare-title">核心权益对比</text>
            <view class="compare-table-wrap">
              <view class="compare-table">
                <view class="compare-row compare-head">
                  <text class="compare-cell compare-metric">权益项</text>
                  <text class="compare-cell compare-head-free">Free</text>
                  <text class="compare-cell compare-head-plus compare-col-plus">Plus</text>
                  <text class="compare-cell compare-head-ultra">Ultra</text>
                </view>
                <view v-for="(row, idx) in compareRows" :key="row.metric" class="compare-row" :class="{ 'compare-row-alt': idx % 2 === 1 }">
                  <text class="compare-cell compare-metric">{{ row.metric }}</text>
                  <text class="compare-cell compare-val-free">{{ row.free }}</text>
                  <text class="compare-cell compare-val-plus compare-col-plus">{{ row.plus }}</text>
                  <text class="compare-cell compare-val-ultra">{{ row.ultra }}</text>
                </view>
              </view>
            </view>
          </view>

          <!-- Redeem Section -->
          <view class="redeem-section anim-fade-in" style="animation-delay: 0.42s">
            <image class="redeem-icon" src="/static/icons/phosphor/regular/key.svg" mode="aspectFit" />
            <view class="redeem-text">
              <text class="redeem-title">已有兑换码？</text>
              <text class="redeem-subtitle">输入激活码直接开通订阅权益。</text>
            </view>
            <button class="redeem-btn" @tap="showActivationModal = true">输入激活码</button>
          </view>
        </view>
      </scroll-view>
    </view>

    <ActivationModal
      :visible="showActivationModal"
      :mandatory="false"
      @success="handleActivationSuccess"
      @cancel="showActivationModal = false"
      @close="showActivationModal = false"
    />

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
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import ActivationModal from '@/components/activation-modal/activation-modal.vue'
import PaymentModal from '@/components/payment-modal/payment-modal.vue'
import { getMe } from '@/api/auth'
import { getOrderStatus } from '@/api/payment'
import { useUserStore } from '@/store/user'
import { getTokens } from '@/utils/storage'

export default {
  components: {
    HomeSidebar,
    ActivationModal,
    PaymentModal
  },
  data() {
    return {
      sidebarCollapsed: false,
      user: null,
      showActivationModal: false,
      showPaymentModal: false,
      selectedPlan: null,
      billingCycle: 'semester',
      billingCycles: [
        { id: 'monthly', label: '月付' },
        { id: 'semester', label: '学期包（4个月）', tag: '省 25%' },
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
            '模型：Grok 4 Fast',
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
            '模型：Grok 4 Fast + Kimi K2.5',
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
            '全部模型：Grok 4 Fast / Kimi K2.5 / Gemini-3.1-pro',
            '每个学习空间知识库上限 500MB',
            '单文件上传上限 100MB',
            '优先客服 + 新功能抢先体验'
          ]
        }
      ],
      compareRows: [
        { metric: '学习空间数量', free: '1', plus: '5', ultra: '不限' },
        { metric: '每日 AI 对话', free: '20 次', plus: '150 次', ultra: '不限' },
        { metric: '模型能力', free: 'Grok 4 Fast', plus: 'Grok + Kimi', ultra: 'Grok / Kimi / Gemini' },
        { metric: '单空间知识库', free: '30MB', plus: '200MB', ultra: '500MB' },
        { metric: '单文件上传', free: '10MB', plus: '50MB', ultra: '100MB' },
        { metric: '优先客服', free: '—', plus: '✓', ultra: '✓' },
        { metric: '新功能抢先体验', free: '—', plus: '—', ultra: '✓' }
      ],
      faqItems: [
        { q: '可以随时升级或降级吗？', a: '可以。升级立即生效，按剩余时长折算差价；降级在当前周期结束后生效。', open: false },
        { q: '支持哪些支付方式？', a: '支持微信支付、支付宝，以及激活码兑换。', open: false },
        { q: '对话次数和存储配额如何重置？', a: '每日对话次数在自然日 00:00 重置。知识库存储按学习空间独立计算，不会定期清零。', open: false },
        { q: '不满意可以退款吗？', a: '开通后 7 天内可无理由退款，超过 7 天按已使用天数折算退还剩余金额。', open: false }
      ],
      notes: [
        '对话次数按自然日重置。',
        '每个学习空间的知识库存储独立计算。',
        'Ultra 支持 Grok 4 Fast / Kimi K2.5 / Gemini-3.1-pro 全部模型。'
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
    this.checkAlipayReturn()
  },
  methods: {
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
      } catch (error) {
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
    handleActivationSuccess(response) {
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
      this.showActivationModal = false
      uni.showToast({
        title: '激活成功',
        icon: 'none'
      })
    },
    formatTime(value) {
      if (!value) return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      const yyyy = date.getFullYear()
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      const dd = String(date.getDate()).padStart(2, '0')
      const hh = String(date.getHours()).padStart(2, '0')
      const min = String(date.getMinutes()).padStart(2, '0')
      return `${yyyy}-${mm}-${dd} ${hh}:${min}`
    },
    switchBillingCycle(cycleId) {
      this.billingCycle = cycleId
    },
    toggleFaq(index) {
      this.faqItems = this.faqItems.map((item, i) => ({
        ...item,
        open: i === index ? !item.open : item.open
      }))
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
    async checkAlipayReturn() {
      // #ifdef H5
      const params = new URLSearchParams(window.location.search)
      const outTradeNo = params.get('out_trade_no')
      if (!outTradeNo) return

      // Clean URL params without reloading
      const cleanUrl = window.location.pathname + window.location.hash
      window.history.replaceState({}, '', cleanUrl)

      // Refresh user data to get updated subscription
      try {
        const user = await getMe()
        this.user = user
        useUserStore().setUser(user)

        if (user.subscription_tier !== 'FREE') {
          uni.showToast({ title: '订阅已激活', icon: 'none' })
        }
      } catch {
        // Silently ignore
      }
      // #endif
    },
    handleSelectSpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${spaceId}` })
    },
    handleCreateSpace() {
      uni.navigateTo({ url: '/pages/createSpace/createSpace' })
    }
  }
}
</script>

<style scoped>
/* ============================
   Entrance Animation
   ============================ */
@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.anim-fade-in {
  opacity: 0;
  animation: fadeSlideIn 0.5s cubic-bezier(0.23, 1, 0.32, 1) forwards;
}

/* ============================
   Page Layout
   ============================ */
.subscription-page {
  display: flex;
  flex-direction: row;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: var(--color-bg);
}

.aurora-bg {
  position: fixed;
  inset: 0;
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
  width: 1180px;
  height: 1180px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.28) 0%, rgba(59, 130, 246, 0.08) 46%, transparent 75%);
  top: -30%;
  left: -10%;
  filter: blur(90px);
  animation: auroraFloat1 18s ease-in-out infinite alternate;
}

.aurora-blob-2 {
  width: 920px;
  height: 920px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.18) 0%, rgba(139, 92, 246, 0.06) 46%, transparent 75%);
  top: 8%;
  right: -12%;
  filter: blur(75px);
  animation: auroraFloat2 22s ease-in-out infinite alternate;
}

.aurora-blob-3 {
  width: 980px;
  height: 980px;
  background: radial-gradient(circle, rgba(79, 70, 229, 0.18) 0%, rgba(79, 70, 229, 0.06) 46%, transparent 75%);
  bottom: -20%;
  left: 18%;
  filter: blur(85px);
  animation: auroraFloat3 20s ease-in-out infinite alternate;
}

@keyframes auroraFloat1 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(40px, 30px) scale(1.05); }
}
@keyframes auroraFloat2 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-30px, 20px) scale(1.03); }
}
@keyframes auroraFloat3 {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(20px, -25px) scale(1.04); }
}

.subscription-main {
  flex: 1;
  min-width: 0;
  z-index: 1;
}

.subscription-scroll {
  width: 100%;
  height: 100vh;
  box-sizing: border-box;
}

.subscription-content {
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 24px 40px;
  box-sizing: border-box;
}

/* ============================
   Hero Section (Open Layout)
   ============================ */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 48px 0 20px;
  gap: 12px;
}

.hero-eyebrow {
  font-size: 11px;
  color: rgba(147, 197, 253, 0.85);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600;
}

.hero-title {
  font-size: 42px;
  line-height: 1.1;
  color: #fff;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: 15px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.5);
  max-width: 460px;
}

.hero-current-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.hero-current-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.38);
  font-weight: 500;
}

.hero-current-expiry {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.32);
}

.tier-chip {
  height: 28px;
  padding: 0 14px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: flex-start;
  transition: transform 0.2s ease;
}

.tier-chip-text {
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.03em;
}

.tier-chip-free {
  background: rgba(156, 163, 175, 0.18);
  border: 1px solid rgba(156, 163, 175, 0.15);
}

.tier-chip-plus {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.25);
}

.tier-chip-ultra {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(79, 70, 229, 0.2));
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.tier-chip-alpha {
  background: rgba(16, 185, 129, 0.18);
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.current-expiry {
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.45);
}

/* ============================
   Billing Cycle Switch
   ============================ */
.billing-switch {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  padding: 5px;
  display: flex;
  gap: 4px;
}

.billing-item {
  flex: 1;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.22s cubic-bezier(0.23, 1, 0.32, 1);
  border: 1px solid transparent;
  position: relative;
}

.billing-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.billing-item-active {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.12);
}

.billing-item-active:hover {
  background: rgba(59, 130, 246, 0.2);
}

.billing-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
  font-weight: 500;
}

.billing-item-active .billing-label {
  color: rgba(255, 255, 255, 0.95);
}

.billing-tag {
  font-size: 10px;
  color: #60a5fa;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.12);
  padding: 2px 7px;
  border-radius: 6px;
}

/* ============================
   Plan Cards Grid
   ============================ */
.plans-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.plan-card {
  position: relative;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(18, 21, 38, 0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 20px;
  min-height: 420px;
  display: flex;
  flex-direction: column;
  transition: transform 0.28s cubic-bezier(0.23, 1, 0.32, 1), border-color 0.28s ease, box-shadow 0.28s ease;
  overflow: hidden;
}

.plan-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.14);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}

.plan-card-recommended {
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.2) inset, 0 8px 32px rgba(59, 130, 246, 0.08);
  transform: scale(1.03);
  z-index: 2;
  padding-top: 52px;
}

.plan-card-recommended::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 19px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.5), rgba(37, 99, 235, 0.2), rgba(59, 130, 246, 0.5));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.plan-card-recommended:hover {
  border-color: rgba(59, 130, 246, 0.5);
  transform: scale(1.03) translateY(-4px);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.3) inset, 0 16px 48px rgba(59, 130, 246, 0.12);
}

.plan-card-ultra {
  border-color: rgba(139, 92, 246, 0.2);
}

.plan-card-ultra:hover {
  border-color: rgba(139, 92, 246, 0.4);
  box-shadow: 0 16px 48px rgba(139, 92, 246, 0.1);
}

.plan-card-current {
  border-color: rgba(16, 185, 129, 0.35);
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.15) inset;
}

/* Plan card glow accents */
.plan-glow {
  position: absolute;
  top: -60px;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  height: 120px;
  background: radial-gradient(ellipse, rgba(59, 130, 246, 0.2) 0%, transparent 70%);
  pointer-events: none;
}

.plan-shimmer {
  position: absolute;
  top: -60px;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  height: 120px;
  background: radial-gradient(ellipse, rgba(139, 92, 246, 0.18) 0%, rgba(79, 70, 229, 0.08) 50%, transparent 70%);
  pointer-events: none;
}

.plan-top-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  position: relative;
  z-index: 1;
}

.plan-name {
  font-size: 26px;
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

.plan-badges {
  display: flex;
  gap: 6px;
}

.plan-badge {
  height: 22px;
  border-radius: 999px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.plan-badge-text {
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.03em;
}

.plan-badge-current {
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.plan-desc {
  margin-top: 8px;
  min-height: 38px;
  font-size: 13px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.5);
  position: relative;
  z-index: 1;
}

/* ============================
   Plan Pricing
   ============================ */
.plan-price-wrap {
  margin-top: 14px;
  display: flex;
  align-items: flex-end;
  gap: 4px;
  position: relative;
  z-index: 1;
  animation: pricePop 0.35s cubic-bezier(0.23, 1, 0.32, 1);
}

.plan-price-main {
  font-size: 40px;
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
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 5px;
  font-weight: 500;
}

.plan-price-label {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  position: relative;
  z-index: 1;
}

.plan-price-hint {
  margin-top: 3px;
  font-size: 12px;
  color: #60a5fa;
  font-weight: 500;
  position: relative;
  z-index: 1;
}

.plan-card-ultra .plan-price-hint {
  color: #a78bfa;
}

.plan-divider {
  margin: 16px 0 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  position: relative;
  z-index: 1;
}

/* ============================
   Feature List
   ============================ */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.feature-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.feature-icon {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
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
  font-size: 11px;
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

.feature-text {
  font-size: 13px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.75);
}

/* ============================
   Plan Buttons
   ============================ */
.plan-btn {
  margin-top: auto;
  width: 60%;
  height: 44px;
  padding: 0 20px;
  align-self: center;
  border-radius: 11px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  line-height: 44px;
  text-align: center;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.22s ease;
  position: relative;
  z-index: 1;
}

.plan-btn::after {
  border: none;
}

.plan-btn-free {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.plan-btn-free:hover {
  background: rgba(255, 255, 255, 0.12);
}

.plan-btn-plus {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.25);
}

.plan-btn-plus:hover {
  box-shadow: 0 6px 24px rgba(37, 99, 235, 0.35);
  transform: translateY(-1px);
}

.plan-btn-ultra {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  box-shadow: 0 4px 16px rgba(124, 58, 237, 0.25);
}

.plan-btn-ultra:hover {
  box-shadow: 0 6px 24px rgba(124, 58, 237, 0.35);
  transform: translateY(-1px);
}

.plan-btn-current {
  background: rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
  cursor: default;
  box-shadow: none;
}

.plan-btn-current:hover {
  box-shadow: none;
  transform: none;
}

/* ============================
   Comparison Table
   ============================ */
.compare-card {
  margin-top: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  padding: 18px;
}

.compare-title {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.92);
  font-weight: 700;
  letter-spacing: -0.01em;
}

.compare-table-wrap {
  margin-top: 12px;
  overflow-x: auto;
}

.compare-table {
  min-width: 720px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.compare-row {
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 1fr;
}

.compare-head {
  background: rgba(255, 255, 255, 0.04);
}

.compare-row:not(.compare-head) {
  background: rgba(255, 255, 255, 0.015);
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.compare-row-alt {
  background: rgba(255, 255, 255, 0.025) !important;
}

.compare-cell {
  min-height: 46px;
  padding: 11px 14px;
  box-sizing: border-box;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.72);
  display: flex;
  align-items: center;
}

.compare-metric {
  color: rgba(255, 255, 255, 0.88);
  font-weight: 600;
  font-size: 13px;
}

.compare-head-free,
.compare-head-plus,
.compare-head-ultra {
  font-weight: 700;
  font-size: 13px;
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

.compare-val-ultra {
  color: rgba(167, 139, 250, 0.85);
  font-weight: 500;
}

.compare-val-plus {
  color: rgba(96, 165, 250, 0.85);
  font-weight: 500;
}

.compare-val-free {
  color: rgba(255, 255, 255, 0.55);
}

/* ============================
   Redeem Section
   ============================ */
.redeem-section {
  margin-top: 16px;
  padding: 20px 24px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.redeem-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.redeem-icon {
  width: 28px;
  height: 28px;
  opacity: 0.6;
  flex-shrink: 0;
}


.redeem-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.88);
  font-weight: 600;
}

.redeem-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.42);
  line-height: 1.5;
}

.redeem-btn {
  height: 36px;
  padding: 0 20px;
  border-radius: 9px;
  border: 1px solid rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.1);
  color: #60a5fa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  line-height: 36px;
}

.redeem-btn:hover {
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(59, 130, 246, 0.35);
}

.redeem-btn::after {
  border: none;
}

/* ============================
   Social Proof
   ============================ */
.social-proof {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 10px 0;
}

.social-proof-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.social-proof-count {
  font-size: 13px;
  color: #60a5fa;
  font-weight: 700;
}

/* ============================
   Plan Ribbon (Recommended)
   ============================ */
.plan-ribbon {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 17px 17px 0 0;
  z-index: 3;
}

.plan-ribbon-text {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.06em;
}

/* ============================
   Strikethrough Price
   ============================ */
.plan-price-strikethrough {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.35);
  text-decoration: line-through;
  margin-right: 8px;
  margin-bottom: 5px;
  font-weight: 500;
}

/* ============================
   Price Pop Animation
   ============================ */
@keyframes pricePop {
  0% { transform: scale(0.92); opacity: 0.6; }
  60% { transform: scale(1.04); }
  100% { transform: scale(1); opacity: 1; }
}

/* ============================
   Guarantee Badge
   ============================ */
.guarantee-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin-top: 10px;
  position: relative;
  z-index: 1;
}

.guarantee-icon {
  font-size: 13px;
  line-height: 1;
}

.guarantee-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.38);
  font-weight: 500;
}

/* ============================
   Button Shimmer on Hover
   ============================ */
.plan-btn-plus,
.plan-btn-ultra {
  overflow: hidden;
}

.plan-btn-plus::before,
.plan-btn-ultra::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.12), transparent);
  transition: left 0.5s ease;
  z-index: 1;
}

.plan-btn-plus:hover::before,
.plan-btn-ultra:hover::before {
  left: 100%;
}

/* ============================
   Card Hover Glow
   ============================ */
.plan-card-free:hover {
  box-shadow: 0 12px 40px rgba(156, 163, 175, 0.1);
}

.plan-card-plus:not(.plan-card-recommended):hover {
  box-shadow: 0 16px 48px rgba(59, 130, 246, 0.15);
}

.plan-card-ultra:not(.plan-card-recommended):hover {
  box-shadow: 0 16px 48px rgba(139, 92, 246, 0.15);
}

/* ============================
   Comparison Table Column Highlight
   ============================ */
.compare-col-plus {
  background: rgba(59, 130, 246, 0.04);
}

/* ============================
   Feature Limitations (Free)
   ============================ */
.feature-icon-limit {
  background: rgba(239, 68, 68, 0.1);
}

.feature-cross {
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  color: rgba(239, 68, 68, 0.5);
}

.feature-text-limit {
  color: rgba(255, 255, 255, 0.4);
}

/* ============================
   FAQ Accordion
   ============================ */
.faq-card {
  margin-top: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.025);
  padding: 18px;
}

.faq-title {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.92);
  font-weight: 700;
  letter-spacing: -0.01em;
}

.faq-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
}

.faq-item {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.faq-item:first-child {
  border-top: none;
}

.faq-question {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  cursor: pointer;
  gap: 12px;
}

.faq-q-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.82);
  font-weight: 600;
  line-height: 1.5;
}

.faq-chevron {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 300;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.faq-answer {
  padding: 0 0 14px;
}

.faq-a-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.52);
  line-height: 1.65;
}

/* ============================
   Reduced Motion
   ============================ */
@media (prefers-reduced-motion: reduce) {
  .aurora-blob {
    animation: none !important;
  }
  .anim-fade-in {
    opacity: 1 !important;
    animation: none !important;
  }
  .plan-card {
    transition: none !important;
  }
  .plan-price-wrap {
    animation: none !important;
  }
}

/* ============================
   Responsive
   ============================ */
@media (max-width: 1180px) {
  .plans-grid {
    grid-template-columns: 1fr;
    max-width: 420px;
    margin-left: auto;
    margin-right: auto;
  }

  .plan-card {
    min-height: auto;
  }

  .plan-card-recommended {
    transform: scale(1);
  }

  .plan-card-recommended:hover {
    transform: translateY(-4px);
  }

}

@media (max-width: 720px) {
  .subscription-content {
    padding: 16px 14px 32px;
  }

  .hero-section {
    padding: 28px 0 14px;
  }

  .hero-title {
    font-size: 28px;
  }

  .hero-current-strip {
    flex-wrap: wrap;
    justify-content: center;
  }

  .billing-switch {
    flex-direction: column;
  }

  .billing-item {
    justify-content: flex-start;
    padding: 0 14px;
  }

  .plan-card {
    padding: 18px 16px;
  }

  .compare-card {
    padding: 14px;
  }

  .redeem-section {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }
}
</style>

<style>
/* Thin dark scrollbar for this page (matches home page style) */
uni-page-body,
uni-page-body > uni-view,
.subscription-page,
.subscription-page * {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

uni-page-body::-webkit-scrollbar,
uni-page-body > uni-view::-webkit-scrollbar,
.subscription-page ::-webkit-scrollbar {
  width: 6px;
}

uni-page-body::-webkit-scrollbar-track,
uni-page-body > uni-view::-webkit-scrollbar-track,
.subscription-page ::-webkit-scrollbar-track {
  background: transparent;
}

uni-page-body::-webkit-scrollbar-thumb,
uni-page-body > uni-view::-webkit-scrollbar-thumb,
.subscription-page ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

uni-page-body::-webkit-scrollbar-thumb:hover,
uni-page-body > uni-view::-webkit-scrollbar-thumb:hover,
.subscription-page ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
