<template>
  <view class="leaderboard-page" :class="pageThemeClass">
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">排行榜</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <view v-if="loading" class="state-container">
      <view class="loading-spinner"></view>
      <text class="state-title">正在加载排行...</text>
      <text class="state-sub">稍等一下，正在汇总协作空间学习数据</text>
    </view>

    <view v-else-if="loadError" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="state-title">{{ loadError }}</text>
      <view class="state-btn" @click="loadLeaderboard">
        <text class="state-btn-text">重试</text>
      </view>
    </view>

    <view v-else-if="entries.length === 0" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/fill/trophy-fill.svg" mode="aspectFit"></image>
      <text class="state-title">暂无排行数据</text>
      <text class="state-sub">成员开始学习、测验和记录笔记后会出现在这里</text>
    </view>

    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="content-body">
        <view class="hero-card">
          <view class="hero-header">
            <view>
              <text class="hero-kicker">Collaborative Space</text>
              <text class="hero-title">{{ spaceName || '当前学习空间' }}</text>
            </view>
            <view class="hero-badge">
              <text class="hero-badge-text">{{ entries.length }} 人</text>
            </view>
          </view>
          <text class="hero-desc">综合分 = 掌握度 50% + 测验 30% + 活跃度 20%</text>
        </view>

        <view v-if="topThree.length > 0" class="podium-card">
          <view class="podium-row">
            <view
              v-for="entry in topThree"
              :key="entry.user_id"
              class="podium-item"
              :class="`podium-rank-${entry.rank}`"
            >
              <view class="podium-rank-chip">
                <text class="podium-rank-text">#{{ entry.rank }}</text>
              </view>
              <view class="podium-avatar" :style="{ borderColor: entry.color || '#5B8CFF' }">
                <text class="podium-avatar-text">{{ getInitial(entry.nickname) }}</text>
              </view>
              <text class="podium-name">{{ entry.nickname || '未命名成员' }}</text>
              <text class="podium-score">{{ formatScore(entry.composite_score) }}</text>
            </view>
          </view>
        </view>

        <view class="leaderboard-card">
          <view class="section-header">
            <text class="section-title">完整榜单</text>
            <text class="section-sub">高亮显示你自己的排名</text>
          </view>

          <view
            v-for="entry in entries"
            :key="entry.user_id"
            class="rank-row"
            :class="{ 'rank-row-self': isSelf(entry) }"
          >
            <view class="rank-main">
              <view class="rank-left">
                <view class="rank-badge">
                  <text class="rank-badge-text">{{ rankDisplay(entry.rank) }}</text>
                </view>
                <view class="rank-avatar" :style="{ borderColor: entry.color || '#5B8CFF' }">
                  <text class="rank-avatar-text">{{ getInitial(entry.nickname) }}</text>
                </view>
                <view class="rank-user">
                  <view class="rank-name-row">
                    <text class="rank-name">{{ entry.nickname || '未命名成员' }}</text>
                    <text v-if="entry.role === 'owner'" class="role-badge">管理员</text>
                    <text v-else-if="isSelf(entry)" class="self-badge">我</text>
                  </view>
                  <text class="rank-score">综合分 {{ formatScore(entry.composite_score) }}</text>
                </view>
              </view>
            </view>

            <view class="metrics-grid">
              <view class="metric-card">
                <view class="metric-head">
                  <text class="metric-label">掌握度</text>
                  <text class="metric-value">{{ formatPercent(entry.avg_mastery) }}</text>
                </view>
                <view class="metric-track">
                  <view class="metric-fill metric-fill-mastery" :style="{ width: percentWidth(entry.avg_mastery) }"></view>
                </view>
                <text class="metric-foot">掌握 {{ entry.mastered_nodes || 0 }}/{{ entry.total_nodes || 0 }}</text>
              </view>

              <view class="metric-card">
                <view class="metric-head">
                  <text class="metric-label">测验</text>
                  <text class="metric-value">{{ formatPercent(entry.avg_quiz_score) }}</text>
                </view>
                <view class="metric-track">
                  <view class="metric-fill metric-fill-quiz" :style="{ width: percentWidth(entry.avg_quiz_score) }"></view>
                </view>
                <text class="metric-foot">{{ entry.quiz_count || 0 }} 次作答</text>
              </view>

              <view class="metric-card metric-card-small">
                <text class="metric-label">笔记</text>
                <text class="metric-value metric-value-large">{{ entry.notes_count || 0 }}</text>
                <text class="metric-foot">近阶段累计</text>
              </view>

              <view class="metric-card metric-card-small">
                <text class="metric-label">活跃度</text>
                <text class="metric-value metric-value-large">{{ entry.activity_count || 0 }}</text>
                <text class="metric-foot">最近 30 天</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { getSpaceLeaderboard } from '@/api/space'
import { useUserStore } from '@/store/user'
import { goBack } from '@/utils/navigation'
import homeThemePageMixin from '@/mixins/homeThemePageMixin'

export default {
  mixins: [homeThemePageMixin],
  data() {
    return {
      spaceId: '',
      spaceName: '',
      entries: [],
      loading: true,
      loadError: '',
      currentUserId: null
    }
  },

  computed: {
    topThree() {
      return this.entries.slice(0, 3)
    }
  },

  onLoad(options) {
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    const userStore = useUserStore()
    this.currentUserId = userStore.user?.id || null
    this.loadLeaderboard()
  },

  onShow() {
    this.restoreThemeMode({ darkStatusBarBackground: '#0A0A12' })
    if (this.spaceId && !this.loading) {
      this.loadLeaderboard()
    }
  },

  methods: {
    goBack() {
      goBack()
    },

    async loadLeaderboard() {
      if (!this.spaceId) {
        this.entries = []
        this.loading = false
        return
      }

      this.loading = true
      this.loadError = ''

      try {
        const result = await getSpaceLeaderboard(this.spaceId)
        this.entries = result?.data || result || []
      } catch (error) {
        this.entries = []
        this.loadError = error.message || '加载排行榜失败'
      } finally {
        this.loading = false
      }
    },

    isSelf(entry) {
      return String(entry?.user_id || '') === String(this.currentUserId || '')
    },

    getInitial(name) {
      return (name || '?').slice(0, 1).toUpperCase()
    },

    rankDisplay(rank) {
      if (rank === 1) return '#1'
      if (rank === 2) return '#2'
      if (rank === 3) return '#3'
      return `#${rank}`
    },

    formatPercent(value) {
      const num = Number(value || 0)
      return `${Math.max(0, Math.min(100, Math.round(num * 10) / 10))}%`
    },

    formatScore(value) {
      const num = Number(value || 0)
      return Number.isInteger(num) ? String(num) : num.toFixed(1)
    },

    percentWidth(value) {
      const num = Number(value || 0)
      return `${Math.max(0, Math.min(100, num))}%`
    }
  }
}
</script>

<style scoped>
.leaderboard-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(91, 140, 255, 0.22), transparent 42%),
    radial-gradient(circle at top right, rgba(56, 249, 215, 0.18), transparent 35%),
    linear-gradient(180deg, #0a0a12 0%, #11111b 48%, #0d0f17 100%);
  color: #ffffff;
}

.nav-bar {
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

.nav-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: -70rpx;
  z-index: -1;
  background: linear-gradient(
    to bottom,
    rgba(10, 10, 10, 0.6) 0%,
    rgba(10, 10, 10, 0.45) 50%,
    rgba(10, 10, 10, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(10, 10, 10, 0.95) 0%,
      rgba(10, 10, 10, 0.8) 50%,
      rgba(10, 10, 10, 0) 100%
    );
  }
}

.nav-left,
.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
}

.nav-left {
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

.state-container {
  min-height: 100vh;
  padding: calc(100vh * 5 / 26) calc(100vw / 12) calc(100vh * 2 / 26);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.loading-spinner {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(255, 255, 255, 0.15);
  border-top-color: #5b8cff;
  animation: spin 0.8s linear infinite;
}

.state-icon {
  width: 88rpx;
  height: 88rpx;
  margin-bottom: 28rpx;
  opacity: 0.86;
  filter: brightness(0) invert(1);
}

.state-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
}

.state-sub {
  margin-top: 16rpx;
  font-size: 26rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.56);
}

.state-btn {
  margin-top: 32rpx;
  padding: 0 36rpx;
  height: 84rpx;
  border-radius: 42rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.8) 0%, rgba(56, 249, 215, 0.52) 100%);
  box-shadow: 0 10rpx 32rpx rgba(91, 140, 255, 0.22);
}

.state-btn-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.content-scroll {
  min-height: 100vh;
}

.content-body {
  padding:
    calc(100vh * 4.5 / 26)
    calc(100vw / 24)
    calc(env(safe-area-inset-bottom) + 40rpx);
}

.hero-card,
.podium-card,
.leaderboard-card {
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.18);
}

.hero-card {
  padding: 32rpx;
}

.hero-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
}

.hero-kicker {
  display: block;
  font-size: 22rpx;
  letter-spacing: 2rpx;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.42);
}

.hero-title {
  display: block;
  margin-top: 10rpx;
  font-size: 38rpx;
  font-weight: 700;
  line-height: 1.3;
  color: #ffffff;
}

.hero-badge {
  min-width: 108rpx;
  height: 60rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(91, 140, 255, 0.16);
  border: 1rpx solid rgba(91, 140, 255, 0.24);
}

.hero-badge-text {
  font-size: 24rpx;
  color: #b8cbff;
}

.hero-desc {
  margin-top: 20rpx;
  font-size: 25rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.58);
}

.podium-card {
  margin-top: 24rpx;
  padding: 28rpx 24rpx;
}

.podium-row {
  display: flex;
  gap: 18rpx;
}

.podium-item {
  flex: 1;
  padding: 26rpx 18rpx 22rpx;
  border-radius: 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(255, 255, 255, 0.05);
}

.podium-rank-1 {
  background: linear-gradient(180deg, rgba(255, 215, 0, 0.14) 0%, rgba(255, 255, 255, 0.05) 100%);
}

.podium-rank-2 {
  background: linear-gradient(180deg, rgba(192, 192, 192, 0.14) 0%, rgba(255, 255, 255, 0.05) 100%);
}

.podium-rank-3 {
  background: linear-gradient(180deg, rgba(205, 127, 50, 0.14) 0%, rgba(255, 255, 255, 0.05) 100%);
}

.podium-rank-chip {
  min-width: 72rpx;
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
}

.podium-rank-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.82);
}

.podium-avatar,
.rank-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 4rpx solid rgba(91, 140, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.podium-avatar {
  width: 108rpx;
  height: 108rpx;
}

.rank-avatar {
  width: 82rpx;
  height: 82rpx;
  flex-shrink: 0;
}

.podium-avatar-text,
.rank-avatar-text {
  font-weight: 700;
  color: #ffffff;
}

.podium-avatar-text {
  font-size: 38rpx;
}

.rank-avatar-text {
  font-size: 30rpx;
}

.podium-name {
  margin-top: 18rpx;
  max-width: 100%;
  font-size: 26rpx;
  font-weight: 600;
  color: #ffffff;
  text-align: center;
}

.podium-score {
  margin-top: 8rpx;
  font-size: 30rpx;
  font-weight: 700;
  color: #9fe8d5;
}

.leaderboard-card {
  margin-top: 24rpx;
  padding: 28rpx 24rpx 20rpx;
}

.section-header {
  margin-bottom: 20rpx;
}

.section-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.section-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.46);
}

.rank-row {
  padding: 24rpx;
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.04);
}

.rank-row + .rank-row {
  margin-top: 18rpx;
}

.rank-row-self {
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.18) 0%, rgba(56, 249, 215, 0.08) 100%);
  border: 1rpx solid rgba(91, 140, 255, 0.18);
}

.rank-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.rank-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.rank-badge {
  width: 84rpx;
  height: 84rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.rank-badge-text {
  font-size: 24rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.86);
}

.rank-user {
  flex: 1;
  min-width: 0;
}

.rank-name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.rank-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.role-badge,
.self-badge {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
}

.role-badge {
  color: #ffd56a;
  background: rgba(255, 213, 106, 0.12);
}

.self-badge {
  color: #99d4ff;
  background: rgba(91, 140, 255, 0.14);
}

.rank-score {
  margin-top: 10rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.56);
}

.metrics-grid {
  margin-top: 22rpx;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx;
}

.metric-card {
  padding: 18rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.05);
}

.metric-card-small {
  min-height: 144rpx;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.metric-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.5);
}

.metric-value {
  font-size: 24rpx;
  font-weight: 600;
  color: #ffffff;
}

.metric-value-large {
  font-size: 40rpx;
}

.metric-track {
  margin-top: 16rpx;
  height: 12rpx;
  border-radius: 999rpx;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}

.metric-fill {
  height: 100%;
  border-radius: 999rpx;
}

.metric-fill-mastery {
  background: linear-gradient(90deg, #4f8cff 0%, #78c6ff 100%);
}

.metric-fill-quiz {
  background: linear-gradient(90deg, #5ae39f 0%, #d8ff8c 100%);
}

.metric-foot {
  display: block;
  margin-top: 12rpx;
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.4);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ========== 浅色主题覆盖：仅调整颜色，不改布局 ========== */
.leaderboard-page.theme-light {
  background:
    radial-gradient(circle at top left, rgba(47, 110, 234, 0.14), transparent 40%),
    radial-gradient(circle at top right, rgba(245, 187, 115, 0.12), transparent 34%),
    linear-gradient(180deg, #F7F1E8 0%, #F3EDE3 48%, #EFE6DA 100%);
  color: #1F1A16;
}

.leaderboard-page.theme-light .nav-bar::before {
  background: linear-gradient(
    to bottom,
    rgba(243, 237, 227, 0.94) 0%,
    rgba(243, 237, 227, 0.72) 52%,
    rgba(243, 237, 227, 0) 100%
  );
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .leaderboard-page.theme-light .nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(243, 237, 227, 0.96) 0%,
      rgba(243, 237, 227, 0.82) 52%,
      rgba(243, 237, 227, 0) 100%
    );
  }
}

.leaderboard-page.theme-light .nav-left {
  background-color: rgba(255, 255, 255, 0.82);
  border-color: rgba(63, 53, 42, 0.1);
  outline-color: rgba(255, 255, 255, 0.72);
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.68),
    0 10rpx 24rpx rgba(118, 101, 80, 0.12);
}

.leaderboard-page.theme-light .nav-icon,
.leaderboard-page.theme-light .state-icon {
  filter: brightness(0) saturate(100%);
}

.leaderboard-page.theme-light .nav-title,
.leaderboard-page.theme-light .state-title {
  color: #1F1A16;
}

.leaderboard-page.theme-light .hero-card,
.leaderboard-page.theme-light .podium-card,
.leaderboard-page.theme-light .leaderboard-card {
  background: rgba(255, 251, 245, 0.92);
  border-color: rgba(79, 66, 51, 0.12);
  box-shadow: 0 20rpx 56rpx rgba(118, 101, 80, 0.12);
}

.leaderboard-page.theme-light .rank-row {
  background: rgba(255, 255, 255, 0.78);
}

.leaderboard-page.theme-light .rank-row-self {
  background: linear-gradient(135deg, rgba(47, 110, 234, 0.12) 0%, rgba(47, 157, 112, 0.08) 100%);
  border: 1rpx solid rgba(47, 110, 234, 0.16);
}

.leaderboard-page.theme-light .metric-card {
  background: rgba(255, 255, 255, 0.8);
}

.leaderboard-page.theme-light .podium-item {
  background: rgba(255, 255, 255, 0.68);
}

.leaderboard-page.theme-light .podium-rank-1 {
  background: linear-gradient(180deg, rgba(255, 215, 0, 0.18) 0%, rgba(255, 255, 255, 0.7) 100%);
}

.leaderboard-page.theme-light .podium-rank-2 {
  background: linear-gradient(180deg, rgba(192, 192, 192, 0.2) 0%, rgba(255, 255, 255, 0.7) 100%);
}

.leaderboard-page.theme-light .podium-rank-3 {
  background: linear-gradient(180deg, rgba(205, 127, 50, 0.22) 0%, rgba(255, 255, 255, 0.7) 100%);
}

.leaderboard-page.theme-light .hero-kicker,
.leaderboard-page.theme-light .podium-rank-text,
.leaderboard-page.theme-light .rank-badge-text,
.leaderboard-page.theme-light .metric-label,
.leaderboard-page.theme-light .metric-foot {
  color: rgba(31, 26, 22, 0.52);
}

.leaderboard-page.theme-light .hero-title,
.leaderboard-page.theme-light .podium-name,
.leaderboard-page.theme-light .section-title,
.leaderboard-page.theme-light .rank-name,
.leaderboard-page.theme-light .metric-value,
.leaderboard-page.theme-light .podium-avatar-text,
.leaderboard-page.theme-light .rank-avatar-text {
  color: #1F1A16;
}

.leaderboard-page.theme-light .state-sub,
.leaderboard-page.theme-light .hero-desc,
.leaderboard-page.theme-light .section-sub,
.leaderboard-page.theme-light .rank-score {
  color: rgba(31, 26, 22, 0.58);
}

.leaderboard-page.theme-light .hero-badge {
  background: rgba(47, 110, 234, 0.1);
  border-color: rgba(47, 110, 234, 0.18);
}

.leaderboard-page.theme-light .hero-badge-text,
.leaderboard-page.theme-light .self-badge {
  color: #2F6EEA;
}

.leaderboard-page.theme-light .role-badge {
  color: #B78321;
  background: rgba(255, 213, 106, 0.16);
}

.leaderboard-page.theme-light .self-badge {
  background: rgba(47, 110, 234, 0.12);
}

.leaderboard-page.theme-light .podium-score {
  color: #2F9D70;
}

.leaderboard-page.theme-light .podium-rank-chip,
.leaderboard-page.theme-light .rank-badge,
.leaderboard-page.theme-light .podium-avatar,
.leaderboard-page.theme-light .rank-avatar {
  background: rgba(255, 255, 255, 0.74);
}

.leaderboard-page.theme-light .metric-track {
  background: rgba(79, 66, 51, 0.08);
}

.leaderboard-page.theme-light .loading-spinner {
  border-color: rgba(63, 53, 42, 0.14);
  border-top-color: #2F6EEA;
}

.leaderboard-page.theme-light .state-btn {
  background: linear-gradient(135deg, #2F6EEA 0%, #5B95FF 100%);
  box-shadow: 0 10rpx 28rpx rgba(47, 110, 234, 0.18);
}
</style>
