<template>
  <view class="subscription-page">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <view class="subscription-wrap">
      <view class="hero-card">
        <view class="hero-header">
          <text class="hero-title">选择适合你的订阅方案</text>
          <text class="hero-subtitle">从日常学习到顶尖模型能力，按你的节奏升级</text>
        </view>

        <view class="current-plan-row">
          <text class="current-plan-label">当前方案</text>
          <view :class="['tier-chip', `tier-chip-${normalizedTier.toLowerCase()}`]">
            <text class="tier-chip-text">{{ tierLabel }}</text>
          </view>
          <text v-if="user?.subscription_expires_at" class="current-plan-expire">
            到期：{{ formatTime(user.subscription_expires_at) }}
          </text>
          <text v-else class="current-plan-expire">长期可用</text>
        </view>
      </view>

      <view class="plans-grid">
        <view
          v-for="plan in plans"
          :key="plan.id"
          class="plan-card"
          :class="[
            `plan-card-${plan.id}`,
            { 'plan-card-current': isCurrentPlan(plan.id), 'plan-card-recommended': plan.recommended }
          ]"
        >
          <view class="plan-head">
            <view class="plan-name-row">
              <text class="plan-name">{{ plan.name }}</text>
              <view v-if="plan.recommended" class="plan-recommended">
                <text class="plan-recommended-text">推荐</text>
              </view>
            </view>
            <text class="plan-desc">{{ plan.desc }}</text>
          </view>

          <view v-if="plan.id === 'FREE'" class="price-block price-block-free">
            <text class="price-main">¥0</text>
            <text class="price-sub">永久免费</text>
          </view>

          <view v-else class="price-block">
            <view
              v-for="option in plan.pricing"
              :key="option.label"
              class="price-option"
              :class="{ 'price-option-highlight': option.highlight }"
            >
              <text class="price-option-label">{{ option.label }}</text>
              <text class="price-option-value">{{ option.price }}</text>
            </view>
          </view>

          <view class="benefits-list">
            <view v-for="benefit in plan.benefits" :key="benefit" class="benefit-item">
              <view class="benefit-dot"></view>
              <text class="benefit-text">{{ benefit }}</text>
            </view>
          </view>

          <button class="plan-action-btn" :class="`plan-action-btn-${plan.id.toLowerCase()}`">
            {{ isCurrentPlan(plan.id) ? '当前方案' : plan.buttonText }}
          </button>
        </view>
      </view>

      <view class="extras-row">
        <view class="redeem-card">
          <text class="redeem-title">已有兑换码？</text>
          <text class="redeem-subtitle">可直接输入激活码开通权益</text>
          <button class="redeem-btn" @tap="showActivationModal = true">输入激活码</button>
        </view>
        <view class="note-card">
          <text class="note-title">方案说明</text>
          <text class="note-item">1. 日对话上限按自然日重置。</text>
          <text class="note-item">2. 每个学习空间的知识库容量独立计算。</text>
          <text class="note-item">3. Ultra 可切换顶尖模型（Gemini 3 Pro / GPT5.2 / Grok）。</text>
        </view>
      </view>
    </view>

    <ActivationModal
      :visible="showActivationModal"
      :mandatory="false"
      @success="handleActivationSuccess"
      @cancel="showActivationModal = false"
      @close="showActivationModal = false"
    />
  </view>
</template>

<script>
import ActivationModal from '@/components/activation-modal/activation-modal.vue'
import { getMe } from '@/api/auth'
import { useUserStore } from '@/store/user'
import { getTokens } from '@/utils/storage'

export default {
  components: {
    ActivationModal
  },
  data() {
    return {
      user: null,
      showActivationModal: false,
      plans: [
        {
          id: 'FREE',
          name: 'Free',
          desc: '轻量体验，适合起步学习',
          benefits: [
            '最多创建 1 个学习空间',
            '每日 AI 对话上限 25 次',
            '模型限制：Gemini 3 Flash',
            '每个学习空间知识库上限 50MB'
          ],
          pricing: [],
          buttonText: '开始使用'
        },
        {
          id: 'PLUS',
          name: 'Plus',
          desc: '主力学习方案，覆盖一个学期',
          benefits: [
            '最多创建 3 个学习空间',
            '每日 AI 对话上限 100 次',
            '模型限制：Gemini 3 Flash',
            '每个学习空间知识库上限 100MB'
          ],
          pricing: [
            { label: '月付', price: '¥9.9 / 月' },
            { label: '4个月（学期包）', price: '¥30 / 4个月', highlight: true },
            { label: '年付', price: '¥110 / 年' }
          ],
          recommended: true,
          buttonText: '选择 Plus'
        },
        {
          id: 'ULTRA',
          name: 'Ultra',
          desc: '顶配能力，解锁多模型与更高上限',
          benefits: [
            '学习空间数量不限',
            '可切换 Gemini 3 Pro / GPT5.2 / Grok 等模型',
            '每个学习空间知识库上限 300MB',
            '更适合高频与重度学习场景'
          ],
          pricing: [
            { label: '月付', price: '¥29.9 / 月' },
            { label: '4个月（学期包）', price: '¥99 / 4个月', highlight: true },
            { label: '年付', price: '¥299 / 年' }
          ],
          buttonText: '选择 Ultra'
        }
      ]
    }
  },
  computed: {
    normalizedTier() {
      const tier = (this.user?.subscription_tier || 'FREE').toUpperCase()
      if (['FREE', 'PLUS', 'ULTRA', 'ALPHA'].includes(tier)) {
        return tier
      }
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
    async loadUser() {
      const tokens = getTokens()
      if (!tokens || !tokens.access_token) {
        uni.reLaunch({ url: '/pages/login/login' })
        return
      }

      try {
        const user = await getMe()
        this.user = user
        const userStore = useUserStore()
        userStore.setUser(user)
      } catch (error) {
        this.user = null
      }
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
    isCurrentPlan(planId) {
      if (this.normalizedTier === 'ALPHA') {
        return planId === 'ULTRA'
      }
      return this.normalizedTier === planId
    }
  }
}
</script>

<style scoped>
.subscription-page {
  min-height: 100vh;
  background: #0a0a12;
  position: relative;
  padding: 28px;
  box-sizing: border-box;
}

.aurora-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 980px;
  height: 980px;
  top: -25%;
  left: -10%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, rgba(59, 130, 246, 0.1) 45%, transparent 75%);
}

.aurora-blob-2 {
  width: 860px;
  height: 860px;
  bottom: -25%;
  right: -10%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(249, 115, 22, 0.22) 0%, rgba(249, 115, 22, 0.08) 45%, transparent 75%);
}

.aurora-blob-3 {
  width: 760px;
  height: 760px;
  top: 20%;
  left: 40%;
  filter: blur(80px);
  background: radial-gradient(circle, rgba(79, 70, 229, 0.2) 0%, rgba(79, 70, 229, 0.08) 45%, transparent 75%);
}

.subscription-wrap {
  max-width: 1180px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.hero-card {
  width: 100%;
  padding: 24px;
  border-radius: 20px;
  background: rgba(18, 18, 28, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  box-sizing: border-box;
}

.hero-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hero-title {
  font-size: 32px;
  line-height: 1.18;
  font-weight: 700;
  color: #fff;
  display: block;
}

.hero-subtitle {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.6);
  display: block;
}

.current-plan-row {
  margin-top: 20px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.current-plan-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.58);
}

.tier-chip {
  height: 26px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tier-chip-text {
  font-size: 12px;
  color: #ffffff;
  font-weight: 600;
}

.tier-chip-free {
  background: rgba(156, 163, 175, 0.2);
}

.tier-chip-plus {
  background: rgba(59, 130, 246, 0.2);
}

.tier-chip-ultra {
  background: rgba(139, 92, 246, 0.24);
}

.tier-chip-alpha {
  background: rgba(16, 185, 129, 0.2);
}

.current-plan-expire {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.plans-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.plan-card {
  border-radius: 18px;
  background: rgba(19, 20, 32, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 16px;
  min-height: 520px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
}

.plan-card-current {
  border-color: rgba(16, 185, 129, 0.45);
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.24) inset;
}

.plan-card-recommended::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 1px solid rgba(59, 130, 246, 0.32);
  pointer-events: none;
}

.plan-head {
  min-height: 80px;
}

.plan-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plan-name {
  font-size: 26px;
  line-height: 1.1;
  font-weight: 700;
  color: #ffffff;
}

.plan-recommended {
  height: 22px;
  border-radius: 999px;
  padding: 0 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.2);
}

.plan-recommended-text {
  font-size: 11px;
  color: #93c5fd;
}

.plan-desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.56);
}

.price-block {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.price-main {
  font-size: 36px;
  line-height: 1;
  color: #ffffff;
  font-weight: 700;
}

.price-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.price-option {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  padding: 10px 11px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.price-option-highlight {
  border-color: rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.1);
}

.price-option-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
}

.price-option-value {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}

.benefits-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.benefit-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.benefit-dot {
  width: 7px;
  height: 7px;
  margin-top: 6px;
  border-radius: 50%;
  background: #60a5fa;
  flex-shrink: 0;
}

.benefit-text {
  font-size: 13px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.8);
}

.plan-action-btn {
  margin-top: auto;
  height: 42px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.plan-action-btn::after {
  border: none;
}

.plan-action-btn-free {
  background: rgba(255, 255, 255, 0.12);
}

.plan-action-btn-plus {
  background: linear-gradient(135deg, #0f6fff 0%, #2563eb 100%);
}

.plan-action-btn-ultra {
  background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%);
}

.plan-card-current .plan-action-btn {
  background: rgba(16, 185, 129, 0.22);
  color: #6ee7b7;
}

.extras-row {
  margin-top: 14px;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 14px;
}

.redeem-card,
.note-card {
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  padding: 14px;
  box-sizing: border-box;
}

.redeem-title,
.note-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
}

.redeem-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.redeem-btn {
  margin-top: 12px;
  height: 38px;
  border-radius: 9px;
  border: none;
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
}

.redeem-btn::after {
  border: none;
}

.note-item {
  margin-top: 7px;
  display: block;
  font-size: 12px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.62);
}

@media (max-width: 1180px) {
  .plans-grid {
    grid-template-columns: 1fr;
  }

  .plan-card {
    min-height: auto;
  }

  .extras-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .subscription-page {
    padding: 16px;
  }

  .hero-title {
    font-size: 26px;
  }
}
</style>
