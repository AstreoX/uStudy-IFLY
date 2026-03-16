<template>
  <view class="account-profile">
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

      <!-- Combined Analytics Card -->
      <view class="analytics-card glass-card">
        <view class="analytics-row">
          <view class="analytics-left">
            <learning-radar
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
            :items="recentItems"
            :loading="timelineLoading"
            :ai-suggestion="aiSuggestion"
            :suggestion-loading="suggestionLoading"
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
      :visible="continuityDrawerVisible"
      @close="continuityDrawerVisible = false"
    />
  </view>
</template>

<script>
import { useUserStore } from '@/store/user'
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

const TIMELINE_CACHE_KEY = 'timeline_cache_v1'
const TIMELINE_CACHE_TTL = 5 * 60 * 1000

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #0F6FFF 0%, #B1DD8B 100%)',
  'linear-gradient(135deg, #A18CD1 0%, #FBC2EB 100%)',
  'linear-gradient(135deg, #FA709A 0%, #FEE140 100%)',
  'linear-gradient(135deg, #84FAB0 0%, #38F9D7 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
]

export default {
  name: 'AccountProfile',

  components: {
    LearningRadar,
    LearningTimeline,
    ContinuityDrawer
  },

  created() {
    this.userStore = useUserStore()
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
      dueReviewCount: 0,
      aiSuggestion: null,
      suggestionLoading: false,
      activationCode: '',
      activating: false,
      activationError: ''
    }
  },

  computed: {
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
    }
  },

  mounted() {
    this.calculateScrollHeight()
    this.radarLastWeekValues = getLastWeekSnapshot()
    this.loadStats()
    this.loadProfileStats()
    this.refreshTimelineSection()
    this.loadRadarScoresAndSnapshot()
  },

  methods: {
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
        this.loadActivityTimeline(),
        this.loadDueReviews(),
        this.loadStudySuggestion()
      ])
    },

    async loadActivityTimeline() {
      // 1. 先查本地缓存（5分钟TTL）
      try {
        const raw = uni.getStorageSync(TIMELINE_CACHE_KEY)
        if (raw) {
          const { data, ts } = JSON.parse(raw)
          if (Date.now() - ts < TIMELINE_CACHE_TTL) {
            this.recentItems = data
            this.timelineLoading = false
            return
          }
        }
      } catch (_) {}
      // 2. 无缓存或已过期，请求 API
      this.timelineLoading = true
      try {
        const result = await getActivityTimeline(1, 20)
        this.recentItems = result.items || []
        uni.setStorageSync(TIMELINE_CACHE_KEY, JSON.stringify({ data: this.recentItems, ts: Date.now() }))
      } catch (_e) {
        this.recentItems = []
      } finally {
        this.timelineLoading = false
      }
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
    }
  }
}
</script>

<style scoped>
.account-profile {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 2;
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
  color: #ffffff;
}

.settings-btn {
  flex-shrink: 0;
  width: 64rpx;
  height: 64rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.settings-icon {
  width: 44rpx;
  height: 44rpx;
  opacity: 0.6;
  filter: brightness(0) invert(1);
}

/* Scrollable Content */
.content-scroll {
  margin-top: calc(100vh * 3.5 / 26);
  overflow-x: hidden;
}

/* Glassmorphism card */
.glass-card {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  margin-bottom: 24rpx;
  margin-left: calc(100vw / 24);
  margin-right: calc(100vw / 24);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .glass-card {
    background: rgba(80, 80, 95, 0.65);
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
  box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.3);
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
  color: #ffffff;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.2);
}

.avatar-edit-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 40rpx;
  height: 40rpx;
  background: rgba(0, 122, 255, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3rpx solid #0A0A12;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
}

.edit-badge-icon {
  font-size: 26rpx;
  font-weight: 600;
  color: #ffffff;
  line-height: 1;
}

.profile-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
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
  color: #ffffff;
}

.subscription-badge {
  padding: 8rpx 24rpx;
  border-radius: 20rpx;
}

.badge-free {
  background: rgba(255, 255, 255, 0.1);
}

.badge-free .badge-text {
  color: rgba(255, 255, 255, 0.6);
}

.badge-basic {
  background: rgba(0, 122, 255, 0.2);
}

.badge-basic .badge-text {
  color: #007AFF;
}

.badge-premium {
  background: rgba(147, 51, 234, 0.2);
}

.badge-premium .badge-text {
  color: #A855F7;
}

.badge-alpha {
  background: rgba(255, 255, 255, 0.1);
}

.badge-alpha .badge-text {
  color: rgba(255, 255, 255, 0.6);
}

.badge-ultra {
  background: rgba(147, 51, 234, 0.2);
}

.badge-ultra .badge-text {
  color: #A855F7;
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
  color: rgba(255, 255, 255, 0.85);
}

.stat-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.stat-divider {
  width: 2rpx;
  height: 24rpx;
  background: rgba(255, 255, 255, 0.15);
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
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
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
  border-left: 1rpx solid rgba(255, 255, 255, 0.06);
}

.detail-value {
  font-size: 28rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.detail-label {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.45);
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
  color: rgba(255, 255, 255, 0.8);
}

.due-review-badge {
  font-size: 22rpx;
  font-weight: 500;
  color: rgba(255, 149, 0, 0.9);
  background: rgba(255, 149, 0, 0.12);
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
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 16rpx;
  padding: 0 20rpx;
  gap: 14rpx;
}

.activation-key-icon {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  opacity: 0.4;
  filter: brightness(0) invert(1);
}

.activation-input {
  flex: 1;
  height: 76rpx;
  font-size: 28rpx;
  color: #ffffff;
  letter-spacing: 2rpx;
}

.activation-placeholder {
  color: rgba(255, 255, 255, 0.25);
}

.activation-btn {
  height: 76rpx;
  padding: 0 36rpx;
  background: linear-gradient(135deg, #0088FF 0%, #0066DD 100%);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activation-btn-disabled {
  background: rgba(0, 136, 255, 0.3);
}

.activation-btn-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.activation-error {
  font-size: 24rpx;
  color: #F87171;
  margin-top: 12rpx;
  padding-left: 4rpx;
}

/* Bottom spacer */
.bottom-spacer {
  height: calc(100vh / 26 * 4 + env(safe-area-inset-bottom, 0px));
}
</style>
