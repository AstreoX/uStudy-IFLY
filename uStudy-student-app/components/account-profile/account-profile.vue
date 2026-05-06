<template>
  <view class="account-profile" :class="themeClass">
    <!-- Top Bar -->
    <view class="top-bar">
      <text class="top-bar-title">我的</text>
    </view>

    <!-- Scrollable Content -->
    <scroll-view
      class="content-scroll"
      scroll-y
      :style="{ height: scrollHeight + 'px' }"
    >
      <!-- Profile Card -->
      <view class="profile-card glass-card" @click="navigateToSettings">
        <view class="avatar-container">
          <view class="avatar" :style="avatarStyle">
            <image
              v-if="user && user.avatar_url"
              class="avatar-image"
              :src="fullAvatarUrl"
              mode="aspectFill"
            ></image>
            <text v-else class="avatar-text">{{ userInitial }}</text>
          </view>
          <view class="avatar-edit-badge">
            <text class="edit-badge-icon">+</text>
          </view>
        </view>
        <view class="profile-info">
          <view class="nickname-row">
            <text class="nickname">{{ user ? (user.nickname || '用户') : '用户' }}</text>
            <view class="subscription-badge" :class="subscriptionClass">
              <text class="badge-text">{{ subscriptionLabel }}</text>
            </view>
          </view>
          <view class="stats-row">
            <view class="stat-item">
              <text class="stat-value">{{ spaceCount }}</text>
              <text class="stat-label">学习空间</text>
            </view>
            <view class="stat-divider"></view>
            <view class="stat-item">
              <text class="stat-value">{{ studiedNodeCount }}</text>
              <text class="stat-label">已学节点</text>
            </view>
          </view>
        </view>
        <view class="settings-btn">
          <image
            class="settings-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/gear.svg"
            mode="aspectFit"
          ></image>
        </view>
      </view>

      <!-- Wallet Card -->
      <view class="wallet-card glass-card">
        <view class="wallet-main">
          <view>
            <text class="wallet-label">账户余额</text>
            <text class="wallet-balance">{{ walletBalanceText }}</text>
          </view>
          <view class="wallet-recharge-btn" @click="navigateToSubscription">
            <text class="wallet-recharge-text">充值</text>
          </view>
        </view>
        <view class="wallet-stats">
          <view class="wallet-stat">
            <text class="wallet-stat-value">{{ walletAvailableText }}</text>
            <text class="wallet-stat-label">可用额度</text>
          </view>
          <view class="wallet-stat-divider"></view>
          <view class="wallet-stat">
            <text class="wallet-stat-value">{{ walletSpentText }}</text>
            <text class="wallet-stat-label">累计消耗</text>
          </view>
          <view class="wallet-stat-divider"></view>
          <view class="wallet-stat">
            <text class="wallet-stat-value">{{ walletMonthGrantText }}</text>
            <text class="wallet-stat-label">本月赠送</text>
          </view>
        </view>
      </view>

      <!-- Invite Card -->
      <view class="invite-card glass-card">
        <view class="invite-main">
          <view>
            <text class="invite-title">邀请好友</text>
            <text class="invite-subtitle">好友注册后，你们各得 ¥1</text>
          </view>
          <view class="invite-copy-btn" @click="copyInviteLink">
            <text class="invite-copy-text">{{ inviteStore?.loading ? '...' : '复制' }}</text>
          </view>
        </view>
        <view class="invite-code-row">
          <text class="invite-code-label">邀请码</text>
          <text class="invite-code-value">{{ inviteCode || '加载中' }}</text>
        </view>
        <view class="invite-stats">
          <view class="invite-stat">
            <text class="invite-stat-value">{{ inviteTotal }}</text>
            <text class="invite-stat-label">已邀请</text>
          </view>
          <view class="invite-stat-divider"></view>
          <view class="invite-stat">
            <text class="invite-stat-value">{{ inviteRewardText }}</text>
            <text class="invite-stat-label">累计奖励</text>
          </view>
        </view>
      </view>

      <!-- Combined Analytics Card -->
      <view class="analytics-card glass-card">
        <view class="analytics-row">
          <view class="analytics-left">
            <learning-radar
              :theme-mode="themeMode"
              :current-values="radarCurrentValues"
              :last-week-values="radarLastWeekValues"
              @dimension-click="onDimensionClick"
            />
          </view>
          <view class="analytics-right">
            <view class="detail-grid">
              <view class="detail-row">
                <view class="detail-cell">
                  <text class="detail-value">{{ studyDays }}</text>
                  <text class="detail-label">学习天数</text>
                </view>
                <view class="detail-cell">
                  <text class="detail-value">{{ avgMastery }}</text>
                  <text class="detail-label">平均掌握分</text>
                </view>
              </view>
              <view class="detail-row">
                <view class="detail-cell">
                  <text class="detail-value">{{ formattedStudyHours }}</text>
                  <text class="detail-label">总学时</text>
                </view>
                <view class="detail-cell">
                  <text class="detail-value">{{ nodeCoverage }}%</text>
                  <text class="detail-label">节点覆盖率</text>
                </view>
              </view>
            </view>
          </view>
        </view>

        <!-- Learning activity timeline -->
        <view class="timeline-section">
          <view class="section-title-row">
            <text class="section-title">学习动态</text>
            <text v-if="dueReviewCount > 0" class="due-review-badge">{{ dueReviewCount }}个待复习</text>
          </view>
          <learning-timeline
            :theme-mode="themeMode"
            :items="recentItems"
            :loading="timelineLoading"
            :has-more="timelineHasMore"
            :loading-more="timelineLoadingMore"
            :ai-suggestion="aiSuggestion"
            :suggestion-loading="suggestionLoading"
            @load-more="loadMoreActivityTimeline"
          />
        </view>
      </view>

      <!-- Activation Code Section -->
      <view class="activation-card glass-card">
        <view class="activation-input-row">
          <view class="activation-input-wrapper">
            <image
              class="activation-key-icon"
              src="/static/icons/lucide/key-round.svg"
              mode="aspectFit"
            ></image>
            <input
              class="activation-input"
              type="text"
              v-model="activationCode"
              placeholder="输入激活码开通会员"
              :maxlength="20"
              :disabled="activating"
              placeholder-class="activation-placeholder"
            />
          </view>
          <view
            class="activation-btn"
            :class="{ 'activation-btn-disabled': !activationCode.trim() || activating }"
            @click="handleActivate"
          >
            <text class="activation-btn-text">{{ activating ? '...' : '激活' }}</text>
          </view>
        </view>
        <text v-if="activationError" class="activation-error">{{ activationError }}</text>
      </view>

      <!-- Bottom spacer for nav bar clearance -->
      <view class="bottom-spacer"></view>
    </scroll-view>

    <!-- Continuity detail drawer -->
    <continuity-drawer
      :theme-mode="themeMode"
      :visible="continuityDrawerVisible"
      @close="continuityDrawerVisible = false"
    />
  </view>
</template>

<script>
import { useUserStore } from '@/store/user'
import { useWalletStore } from '@/store/wallet'
import { useInviteStore } from '@/store/invite'
import config from '@/config'
import { activateCode } from '@/api/auth'
import { getSpaces, getSpaceGraph } from '@/api/space'
import { getActivityTimeline, getStudySuggestion } from '@/api/activity'
import { getDueReviews } from '@/api/review'
import { getProfileStats, getContinuityScore, getFocusScore, getDepthScore, getComprehensionScore, getKnowledgeStructureScore, getReviewScore } from '@/api/assessment'
import { saveRadarSnapshot, getLastWeekSnapshot } from '@/utils/radar-snapshot'
import LearningRadar from '@/components/learning-radar/learning-radar.vue'
import LearningTimeline from '@/components/learning-timeline/learning-timeline.vue'
import ContinuityDrawer from '@/components/continuity-drawer/continuity-drawer.vue'
import { normalizeThemeMode } from '@/utils/themeMode'

// ── 学习建议时间槽缓存（UTC+8）──
// 更新时间点：08:00 / 12:00 / 18:00 / 21:00
function _getCSTComponents() {
  const now = new Date()
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000
  const cstMs = utcMs + 8 * 3600 * 1000
  const d = new Date(cstMs)
  return {
    year: d.getUTCFullYear(),
    month: d.getUTCMonth() + 1,
    day: d.getUTCDate(),
    hour: d.getUTCHours(),
    cstMs
  }
}

function _getSuggestionSlotKey() {
  const { year, month, day, hour, cstMs } = _getCSTComponents()
  const dateStr = `${year}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`
  const slots = [8, 12, 18, 21]
  let slot = null
  for (const s of slots) { if (hour >= s) slot = s }
  if (slot === null) {
    const yd = new Date(cstMs - 86400000)
    const yStr = `${yd.getUTCFullYear()}${String(yd.getUTCMonth() + 1).padStart(2, '0')}${String(yd.getUTCDate()).padStart(2, '0')}`
    return `suggestion_${yStr}_21`
  }
  return `suggestion_${dateStr}_${String(slot).padStart(2, '0')}`
}

function _cleanOldSuggestionCache(currentKey) {
  try {
    const info = uni.getStorageInfoSync()
    const old = (info.keys || []).filter(k => k.startsWith('suggestion_') && k !== currentKey)
    old.sort().reverse()
    old.slice(1).forEach(k => uni.removeStorageSync(k))
  } catch (_) {}
}

const TIMELINE_CACHE_KEY = 'timeline_cache_v2'
const TIMELINE_CACHE_TTL = 5 * 60 * 1000
const TIMELINE_PAGE_SIZE = 20

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #0F6FFF 0%, #B1DD8B 100%)',
  'linear-gradient(135deg, #A18CD1 0%, #FBC2EB 100%)',
  'linear-gradient(135deg, #FA709A 0%, #FEE140 100%)',
  'linear-gradient(135deg, #84FAB0 0%, #38F9D7 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
]

export default {
  name: 'AccountProfile',

  props: {
    themeMode: {
      type: String,
      default: 'dark'
    }
  },

  components: {
    LearningRadar,
    LearningTimeline,
    ContinuityDrawer
  },

  created() {
    this.userStore = useUserStore()
    this.walletStore = useWalletStore()
    this.inviteStore = useInviteStore()
  },

  data() {
    return {
      scrollHeight: 0,
      spaceCount: 0,
      studiedNodeCount: 0,
      continuityDrawerVisible: false,
      radarCurrentValues: [0, 0, 0, 0, 0, 0],
      radarLastWeekValues: null,
      studyDays: 0,
      totalStudyHours: 0,
      avgMastery: 0,
      nodeCoverage: 0,
      recentItems: [],
      timelineLoading: false,
      timelineLoadingMore: false,
      timelinePage: 1,
      timelineTotal: 0,
      timelineHasMore: true,
      dueReviewCount: 0,
      aiSuggestion: null,
      suggestionLoading: false,
      activationCode: '',
      activating: false,
      activationError: ''
    }
  },

  computed: {
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode)}`
    },

    user() {
      return this.userStore.user
    },

    userInitial() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      return nickname.charAt(0).toUpperCase()
    },

    avatarGradient() {
      const nickname = this.user?.nickname || this.user?.email || 'U'
      const index = nickname.charCodeAt(0) % AVATAR_GRADIENTS.length
      return AVATAR_GRADIENTS[index]
    },

    fullAvatarUrl() {
      if (!this.user?.avatar_url) return ''
      if (this.user.avatar_url.startsWith('http')) {
        return this.user.avatar_url
      }
      return `${config.API_BASE_URL}${this.user.avatar_url}`
    },

    avatarStyle() {
      if (this.user?.avatar_url) {
        return {}
      }
      return { background: this.avatarGradient }
    },

    subscriptionClass() {
      const tier = this.user?.subscription_tier || 'FREE'
      return `badge-${tier.toLowerCase()}`
    },

    subscriptionLabel() {
      const tier = this.user?.subscription_tier || 'FREE'
      const labels = {
        FREE: 'Free',
        BASIC: 'Plus',
        PREMIUM: 'Ultra',
        ALPHA: 'Alpha',
        ULTRA: 'Ultra'
      }
      return labels[tier] || tier
    },

    formattedStudyHours() {
      const h = this.totalStudyHours
      if (h <= 0) return '0h'
      if (h < 1) return `${h}h`
      return `${Math.round(h)}h`
    },

    walletStatus() {
      return this.walletStore?.status || null
    },

    walletBalanceText() {
      return this.formatWalletMoney(this.walletStatus?.balance_cents || 0)
    },

    walletAvailableText() {
      return this.formatWalletMoney(this.walletStatus?.available_cents || 0)
    },

    walletSpentText() {
      return this.formatWalletMoney(this.walletStatus?.total_spent_cents || 0)
    },

    walletMonthGrantText() {
      return this.formatWalletMoney(this.walletStatus?.current_month_granted_cents || 0)
    },

    inviteInfo() {
      return this.inviteStore?.info || null
    },

    inviteCode() {
      return this.inviteInfo?.code || ''
    },

    inviteUrl() {
      return this.inviteInfo?.invite_url || ''
    },

    inviteTotal() {
      return this.inviteInfo?.total_invites || 0
    },

    inviteRewardText() {
      return this.formatWalletMoney(this.inviteInfo?.total_reward_cents || 0)
    }
  },

  mounted() {
    this.calculateScrollHeight()
    this.radarLastWeekValues = getLastWeekSnapshot()
    this.loadStats()
    this.loadProfileStats()
    this.refreshTimelineSection()
    this.loadRadarScoresAndSnapshot()
    this.refreshWallet()
    this.refreshInvite()
  },

  methods: {
    formatWalletMoney(cents) {
      return `¥${((cents || 0) / 100).toFixed(2)}`
    },

    async refreshWallet() {
      try {
        await this.walletStore.refresh()
      } catch (_e) {}
    },

    async refreshInvite() {
      try {
        await this.inviteStore.refresh()
      } catch (_e) {}
    },

    async copyInviteLink() {
      if (!this.inviteUrl) {
        await this.refreshInvite()
      }
      const link = this.inviteUrl
      if (!link) {
        uni.showToast({ title: '邀请链接生成失败', icon: 'none' })
        return
      }
      uni.setClipboardData({
        data: link,
        success: () => {
          uni.showToast({ title: '邀请链接已复制', icon: 'none' })
        },
        fail: () => {
          uni.showToast({ title: '复制失败，请稍后重试', icon: 'none' })
        }
      })
    },

    async handleActivate() {
      const code = this.activationCode.trim()
      if (!code || this.activating) return

      this.activating = true
      this.activationError = ''

      try {
        const response = await activateCode(code)
        if (response.success) {
          this.userStore.updateSubscription(
            response.subscription_tier,
            response.subscription_expires_at
          )
          this.activationCode = ''
          uni.showToast({
            title: response.message || '激活成功',
            icon: 'none'
          })
        }
      } catch (error) {
        const detail = error.data?.detail || error.message || '激活失败，请稍后重试'
        if (typeof detail === 'object') {
          this.activationError = detail.message || '激活失败'
        } else {
          this.activationError = detail
        }
      } finally {
        this.activating = false
      }
    },

    calculateScrollHeight() {
      const systemInfo = uni.getSystemInfoSync()
      // Top bar height ~ 3.5/26 vh, nav bar ~ 3/26 vh
      const topBarHeight = systemInfo.windowHeight * (3.5 / 26)
      const navBarHeight = systemInfo.windowHeight * (3 / 26)
      this.scrollHeight = systemInfo.windowHeight - topBarHeight - navBarHeight
    },

    async loadProfileStats() {
      try {
        const result = await getProfileStats()
        this.studyDays = result.study_days || 0
        this.totalStudyHours = result.total_study_hours || 0
        this.avgMastery = result.avg_mastery || 0
        this.nodeCoverage = result.node_coverage_percent || 0
      } catch (_e) {
        // Keep default values
      }
    },

    async refreshTimelineSection() {
      await Promise.allSettled([
        this.loadActivityTimeline({ reset: true }),
        this.loadDueReviews(),
        this.loadStudySuggestion()
      ])
    },

    async loadActivityTimeline({ reset = false, useCache = true } = {}) {
      if (!reset && (this.timelineLoading || this.timelineLoadingMore || !this.timelineHasMore)) return

      if (reset) {
        // 优先恢复最近一次分页状态，避免每次回到“我的”都只能看到第一页。
        try {
          const raw = uni.getStorageSync(TIMELINE_CACHE_KEY)
          if (raw && useCache) {
            const cached = JSON.parse(raw)
            if (Date.now() - cached.ts < TIMELINE_CACHE_TTL) {
              this.recentItems = cached.items || []
              this.timelinePage = cached.page || 1
              this.timelineTotal = cached.total || this.recentItems.length
              this.timelineHasMore = typeof cached.hasMore === 'boolean'
                ? cached.hasMore
                : this.recentItems.length < this.timelineTotal
              this.timelineLoading = false
              return
            }
          }
        } catch (_) {}
      }

      if (reset) {
        this.timelineLoading = true
      } else {
        this.timelineLoadingMore = true
      }

      const nextPage = reset ? 1 : this.timelinePage + 1
      try {
        const result = await getActivityTimeline(nextPage, TIMELINE_PAGE_SIZE)
        const incomingItems = result.items || []
        const mergedItems = reset ? incomingItems : [...this.recentItems, ...incomingItems]
        const total = typeof result.total === 'number' ? result.total : mergedItems.length

        this.recentItems = mergedItems
        this.timelinePage = result.page || nextPage
        this.timelineTotal = total
        this.timelineHasMore = mergedItems.length < total

        uni.setStorageSync(
          TIMELINE_CACHE_KEY,
          JSON.stringify({
            items: this.recentItems,
            page: this.timelinePage,
            total: this.timelineTotal,
            hasMore: this.timelineHasMore,
            ts: Date.now()
          })
        )
      } catch (_e) {
        if (reset) {
          this.recentItems = []
          this.timelinePage = 1
          this.timelineTotal = 0
          this.timelineHasMore = false
        }
      } finally {
        this.timelineLoading = false
        this.timelineLoadingMore = false
      }
    },

    async loadMoreActivityTimeline() {
      await this.loadActivityTimeline({ reset: false, useCache: false })
    },

    async loadDueReviews() {
      try {
        const result = await getDueReviews(1)
        this.dueReviewCount = result.total || 0
      } catch (_e) {
        // Silently fail
        this.dueReviewCount = 0
      }
    },

    async loadStudySuggestion() {
      const key = _getSuggestionSlotKey()
      // 1. 先查本地时间槽缓存
      try {
        const cached = uni.getStorageSync(key)
        if (cached) {
          this.aiSuggestion = JSON.parse(cached)
          this.suggestionLoading = false
          return
        }
      } catch (_) {}
      // 2. 无缓存则请求 API
      this.suggestionLoading = true
      try {
        const result = await getStudySuggestion()
        this.aiSuggestion = result
        uni.setStorageSync(key, JSON.stringify(result))
        _cleanOldSuggestionCache(key)
      } catch (_e) {
        // Silently fail — timeline falls back to heuristic
      } finally {
        this.suggestionLoading = false
      }
    },

    async loadStats() {
      try {
        const spaces = await getSpaces()
        this.spaceCount = Array.isArray(spaces) ? spaces.length : 0

        let totalStudied = 0
        const graphPromises = (spaces || []).map(s =>
          getSpaceGraph(s.id).catch(() => null)
        )
        const graphs = await Promise.all(graphPromises)
        for (const graph of graphs) {
          if (graph && Array.isArray(graph.nodes)) {
            totalStudied += graph.nodes.filter(
              n => n.mastery != null && n.mastery >= 70
            ).length
          }
        }
        this.studiedNodeCount = totalStudied
      } catch (e) {
        // Silently fail — show 0/0
      }
    },

    async loadRadarScoresAndSnapshot() {
      await Promise.allSettled([
        this.loadContinuityScore(),
        this.loadFocusScore(),
        this.loadDepthScore(),
        this.loadComprehensionScore(),
        this.loadKnowledgeStructureScore(),
        this.loadReviewScore()
      ])
      saveRadarSnapshot(this.radarCurrentValues)
    },

    updateRadarValue(index, value) {
      const updated = [...this.radarCurrentValues]
      updated[index] = value
      this.radarCurrentValues = updated
    },

    async loadContinuityScore() {
      try {
        const result = await getContinuityScore()
        this.updateRadarValue(0, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    async loadFocusScore() {
      try {
        const result = await getFocusScore(0)
        this.updateRadarValue(1, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    async loadDepthScore() {
      try {
        const result = await getDepthScore(0)
        this.updateRadarValue(2, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    async loadComprehensionScore() {
      try {
        const result = await getComprehensionScore()
        this.updateRadarValue(3, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    async loadKnowledgeStructureScore() {
      try {
        const result = await getKnowledgeStructureScore()
        this.updateRadarValue(4, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    async loadReviewScore() {
      try {
        const result = await getReviewScore()
        this.updateRadarValue(5, Math.round(result.score))
      } catch (_e) {
        // Keep default value
      }
    },

    onDimensionClick({ index, label }) {
      if (label === '连续性') {
        this.continuityDrawerVisible = true
      }
    },

    navigateToSettings() {
      // #ifdef APP-PLUS
      uni.navigateTo({
        url: '/pages/account/account',
        animationType: 'slide-in-right',
        animationDuration: 300
      })
      // #endif

      // #ifndef APP-PLUS
      uni.navigateTo({
        url: '/pages/account/account'
      })
      // #endif
    },

    navigateToSubscription() {
      uni.navigateTo({ url: '/pages/subscription/subscription' })
    }
  }
}
</script>

<style scoped>
.account-profile {
  --account-topbar-title: #ffffff;
  --account-settings-btn-bg: rgba(255, 255, 255, 0.08);
  --account-settings-btn-border: rgba(255, 255, 255, 0.12);
  --account-surface: rgba(255, 255, 255, 0.08);
  --account-surface-strong: rgba(255, 255, 255, 0.1);
  --account-surface-fallback: rgba(80, 80, 95, 0.65);
  --account-surface-input: rgba(255, 255, 255, 0.06);
  --account-border: rgba(255, 255, 255, 0.15);
  --account-border-soft: rgba(255, 255, 255, 0.12);
  --account-divider: rgba(255, 255, 255, 0.06);
  --account-text-primary: #ffffff;
  --account-text-secondary: rgba(255, 255, 255, 0.85);
  --account-text-muted: rgba(255, 255, 255, 0.45);
  --account-text-faint: rgba(255, 255, 255, 0.25);
  --account-icon-filter: brightness(0) invert(1);
  --account-icon-opacity: 0.6;
  --account-shadow: rgba(0, 0, 0, 0.3);
  --account-shadow-soft: rgba(0, 0, 0, 0.18);
  --account-avatar-edit-bg: rgba(0, 122, 255, 0.9);
  --account-avatar-edit-border: #0A0A12;
  --account-badge-free-bg: rgba(255, 255, 255, 0.1);
  --account-badge-free-text: rgba(255, 255, 255, 0.6);
  --account-badge-basic-bg: rgba(0, 122, 255, 0.2);
  --account-badge-basic-text: #007AFF;
  --account-badge-premium-bg: rgba(147, 51, 234, 0.2);
  --account-badge-premium-text: #A855F7;
  --account-badge-alpha-bg: rgba(255, 255, 255, 0.1);
  --account-badge-alpha-text: rgba(255, 255, 255, 0.6);
  --account-badge-ultra-bg: rgba(147, 51, 234, 0.2);
  --account-badge-ultra-text: #A855F7;
  --account-review-badge-bg: rgba(255, 149, 0, 0.12);
  --account-review-badge-text: rgba(255, 149, 0, 0.9);
  --account-activation-bg: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  --account-activation-disabled-bg: rgba(0, 136, 255, 0.3);
  --account-activation-text: #ffffff;
  --account-placeholder: rgba(255, 255, 255, 0.25);
  --account-error: #F87171;
  --account-avatar-text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.2);
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 2;
}

.account-profile.theme-light {
  --account-topbar-title: #1f1a16;
  --account-settings-btn-bg: rgba(255, 255, 255, 0.82);
  --account-settings-btn-border: rgba(63, 53, 42, 0.1);
  --account-surface: rgba(255, 255, 255, 0.84);
  --account-surface-strong: rgba(255, 255, 255, 0.92);
  --account-surface-fallback: rgba(255, 249, 241, 0.96);
  --account-surface-input: rgba(255, 249, 241, 0.96);
  --account-border: rgba(63, 53, 42, 0.12);
  --account-border-soft: rgba(63, 53, 42, 0.1);
  --account-divider: rgba(63, 53, 42, 0.08);
  --account-text-primary: #1f1a16;
  --account-text-secondary: rgba(31, 26, 22, 0.82);
  --account-text-muted: rgba(31, 26, 22, 0.58);
  --account-text-faint: rgba(31, 26, 22, 0.38);
  --account-icon-filter: brightness(0) saturate(100%);
  --account-icon-opacity: 0.72;
  --account-shadow: rgba(118, 101, 80, 0.16);
  --account-shadow-soft: rgba(118, 101, 80, 0.12);
  --account-avatar-edit-bg: #2F6EEA;
  --account-avatar-edit-border: #F3EDE3;
  --account-badge-free-bg: rgba(63, 53, 42, 0.08);
  --account-badge-free-text: rgba(63, 53, 42, 0.72);
  --account-badge-basic-bg: rgba(47, 110, 234, 0.14);
  --account-badge-basic-text: #2F6EEA;
  --account-badge-premium-bg: rgba(124, 58, 237, 0.14);
  --account-badge-premium-text: #7C3AED;
  --account-badge-alpha-bg: rgba(63, 53, 42, 0.08);
  --account-badge-alpha-text: rgba(63, 53, 42, 0.72);
  --account-badge-ultra-bg: rgba(124, 58, 237, 0.14);
  --account-badge-ultra-text: #7C3AED;
  --account-review-badge-bg: rgba(192, 122, 24, 0.12);
  --account-review-badge-text: #A86412;
  --account-activation-bg: linear-gradient(135deg, #2F6EEA 0%, #1F56C6 100%);
  --account-activation-disabled-bg: rgba(47, 110, 234, 0.24);
  --account-activation-text: #ffffff;
  --account-placeholder: rgba(31, 26, 22, 0.35);
  --account-error: #D14F4F;
  --account-avatar-text-shadow: 0 2rpx 8rpx rgba(118, 101, 80, 0.12);
}

/* Top Bar */
.top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 90;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.top-bar-title {
  font-size: 40rpx;
  font-weight: 700;
  color: var(--account-topbar-title);
}

.settings-btn {
  flex-shrink: 0;
  width: 64rpx;
  height: 64rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: var(--account-settings-btn-bg);
  border: 1rpx solid var(--account-settings-btn-border);
}

.settings-icon {
  width: 44rpx;
  height: 44rpx;
  opacity: var(--account-icon-opacity);
  filter: var(--account-icon-filter);
}

/* Scrollable Content */
.content-scroll {
  margin-top: calc(100vh * 3.5 / 26);
  overflow-x: hidden;
}

/* Glassmorphism card */
.glass-card {
  background: var(--account-surface);
  border: 1rpx solid var(--account-border);
  border-radius: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  margin-bottom: 24rpx;
  margin-left: calc(100vw / 24);
  margin-right: calc(100vw / 24);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .glass-card {
    background: var(--account-surface-fallback);
  }
}

/* Profile Card */
.profile-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 28rpx 30rpx;
  gap: 52rpx;
}

.avatar-container {
  position: relative;
  flex-shrink: 0;
}

.avatar {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 8rpx 32rpx var(--account-shadow);
  overflow: hidden;
}

.avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.avatar-text {
  font-size: 48rpx;
  font-weight: 700;
  color: var(--account-text-primary);
  text-shadow: var(--account-avatar-text-shadow);
}

.avatar-edit-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 40rpx;
  height: 40rpx;
  background: var(--account-avatar-edit-bg);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3rpx solid var(--account-avatar-edit-border);
  box-shadow: 0 2rpx 8rpx var(--account-shadow);
}

.edit-badge-icon {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--account-activation-text);
  line-height: 1;
}

.profile-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.wallet-card {
  padding: 28rpx 30rpx;
}

.wallet-main {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 24rpx;
}

.wallet-label {
  display: block;
  font-size: 24rpx;
  color: var(--account-text-muted);
  margin-bottom: 8rpx;
}

.wallet-balance {
  display: block;
  font-size: 48rpx;
  font-weight: 700;
  color: var(--account-text-primary);
}

.wallet-recharge-btn {
  flex-shrink: 0;
  min-width: 116rpx;
  height: 64rpx;
  border-radius: 32rpx;
  background: var(--account-activation-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 28rpx;
}

.wallet-recharge-text {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--account-activation-text);
}

.wallet-stats {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  border-top: 1rpx solid var(--account-divider);
  padding-top: 22rpx;
}

.wallet-stat {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.wallet-stat-value {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--account-text-secondary);
}

.wallet-stat-label {
  font-size: 22rpx;
  color: var(--account-text-muted);
}

.wallet-stat-divider {
  width: 1rpx;
  background: var(--account-divider);
  margin: 0 22rpx;
}

.invite-card {
  padding: 28rpx 30rpx;
}

.invite-main {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 20rpx;
}

.invite-title {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: var(--account-text-primary);
  margin-bottom: 6rpx;
}

.invite-subtitle {
  display: block;
  font-size: 24rpx;
  color: var(--account-text-muted);
}

.invite-copy-btn {
  flex-shrink: 0;
  min-width: 112rpx;
  height: 64rpx;
  border-radius: 32rpx;
  background: var(--account-activation-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 28rpx;
}

.invite-copy-text {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--account-activation-text);
}

.invite-code-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 18rpx 0;
  border-top: 1rpx solid var(--account-divider);
  border-bottom: 1rpx solid var(--account-divider);
}

.invite-code-label {
  font-size: 24rpx;
  color: var(--account-text-muted);
}

.invite-code-value {
  font-size: 30rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
  color: var(--account-text-primary);
}

.invite-stats {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  padding-top: 20rpx;
}

.invite-stat {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.invite-stat-value {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--account-text-secondary);
}

.invite-stat-label {
  font-size: 22rpx;
  color: var(--account-text-muted);
}

.invite-stat-divider {
  width: 1rpx;
  background: var(--account-divider);
  margin: 0 22rpx;
}

.nickname-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
}

.nickname {
  font-size: 36rpx;
  font-weight: 600;
  color: var(--account-text-primary);
}

.subscription-badge {
  padding: 8rpx 24rpx;
  border-radius: 20rpx;
}

.badge-free {
  background: var(--account-badge-free-bg);
}

.badge-free .badge-text {
  color: var(--account-badge-free-text);
}

.badge-basic {
  background: var(--account-badge-basic-bg);
}

.badge-basic .badge-text {
  color: var(--account-badge-basic-text);
}

.badge-premium {
  background: var(--account-badge-premium-bg);
}

.badge-premium .badge-text {
  color: var(--account-badge-premium-text);
}

.badge-alpha {
  background: var(--account-badge-alpha-bg);
}

.badge-alpha .badge-text {
  color: var(--account-badge-alpha-text);
}

.badge-ultra {
  background: var(--account-badge-ultra-bg);
}

.badge-ultra .badge-text {
  color: var(--account-badge-ultra-text);
}

.badge-text {
  font-size: 24rpx;
  font-weight: 500;
}

/* Stats Row */
.stats-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20rpx;
}

.stat-item {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 6rpx;
}

.stat-value {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--account-text-secondary);
}

.stat-label {
  font-size: 22rpx;
  color: var(--account-text-muted);
}

.stat-divider {
  width: 2rpx;
  height: 24rpx;
  background: var(--account-border);
}

/* Analytics Card */
.analytics-card {
  padding: 28rpx 24rpx;
}

.analytics-row {
  display: flex;
  flex-direction: row;
  align-items: center;
}

.analytics-left {
  flex-shrink: 0;
}

.analytics-right {
  flex: 1;
  min-width: 0;
}

.detail-grid {
  display: flex;
  flex-direction: column;
}

.detail-row {
  display: flex;
  flex-direction: row;
}

.detail-row + .detail-row {
  border-top: 1rpx solid var(--account-divider);
}

.detail-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20rpx 0;
}

.detail-cell + .detail-cell {
  border-left: 1rpx solid var(--account-divider);
}

.detail-value {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--account-text-primary);
}

.detail-label {
  font-size: 20rpx;
  color: var(--account-text-muted);
  margin-top: 4rpx;
}

.section-title-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--account-text-secondary);
}

.due-review-badge {
  font-size: 22rpx;
  font-weight: 500;
  color: var(--account-review-badge-text);
  background: var(--account-review-badge-bg);
  padding: 4rpx 16rpx;
  border-radius: 12rpx;
}

/* Timeline section */
.timeline-section {
  margin-top: 24rpx;
}

/* Activation Code Card */
.activation-card {
  padding: 20rpx 24rpx;
}

.activation-input-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
}

.activation-input-wrapper {
  flex: 1;
  height: 76rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  background: var(--account-surface-input);
  border: 1rpx solid var(--account-border-soft);
  border-radius: 16rpx;
  padding: 0 20rpx;
  gap: 14rpx;
}

.activation-key-icon {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  opacity: var(--account-icon-opacity);
  filter: var(--account-icon-filter);
}

.activation-input {
  flex: 1;
  height: 76rpx;
  font-size: 28rpx;
  color: var(--account-text-primary);
  letter-spacing: 2rpx;
}

.activation-placeholder {
  color: var(--account-placeholder);
}

.activation-btn {
  height: 76rpx;
  padding: 0 36rpx;
  background: var(--account-activation-bg);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activation-btn-disabled {
  background: var(--account-activation-disabled-bg);
}

.activation-btn-text {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--account-activation-text);
}

.activation-error {
  font-size: 24rpx;
  color: var(--account-error);
  margin-top: 12rpx;
  padding-left: 4rpx;
}

/* Bottom spacer */
.bottom-spacer {
  height: calc(100vh / 26 * 4 + env(safe-area-inset-bottom, 0px));
}
</style>
