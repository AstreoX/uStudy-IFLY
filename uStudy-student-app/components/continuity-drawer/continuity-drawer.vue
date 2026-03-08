<template>
  <view v-if="visible" class="drawer-wrapper" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="drawer-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="close"
    />

    <!-- Drawer Container -->
    <view class="drawer-container" :class="{ 'drawer-show': animationVisible }">
      <!-- Handle bar -->
      <view class="drawer-handle">
        <view class="handle-bar" />
      </view>

      <!-- Score Section -->
      <view class="score-section">
        <text class="score-value" :style="{ color: scoreColor }">{{ displayScore }}</text>
        <text class="score-label">连续性分数</text>
        <text class="score-desc">{{ scoreDescription }}</text>
      </view>

      <!-- Stats Grid -->
      <view class="stats-grid">
        <view class="stats-cell">
          <text class="stats-value">{{ scoreData.current_streak }}</text>
          <text class="stats-label">连续天数</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-cell">
          <text class="stats-value">{{ scoreData.cumulative_active_days }}</text>
          <text class="stats-label">累计学习天</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-cell">
          <text class="stats-value">{{ scoreData.effective_gap_days }}</text>
          <text class="stats-label">中断天数</text>
        </view>
      </view>

      <!-- Recovery Progress -->
      <view v-if="showRecovery" class="recovery-section">
        <view class="recovery-bar-bg">
          <view class="recovery-bar-fill" :style="{ width: recoveryPercent + '%' }" />
        </view>
        <text class="recovery-text">
          再坚持 {{ recoveryDaysLeft }} 天，中断记录将被清零
        </text>
      </view>

      <!-- Calendar -->
      <view class="calendar-section">
        <text class="section-title">学习日历</text>
        <activity-calendar :records="calendarRecords" :months="6" />
      </view>
    </view>
  </view>
</template>

<script>
import { getContinuityScore, getContinuityCalendar } from '@/api/assessment'
import ActivityCalendar from '@/components/activity-calendar/activity-calendar.vue'

export default {
  name: 'ContinuityDrawer',

  components: { ActivityCalendar },

  props: {
    visible: {
      type: Boolean,
      default: false
    }
  },

  data() {
    return {
      animationVisible: false,
      scoreData: {
        score: 0,
        cumulative_active_days: 0,
        effective_gap_days: 0,
        current_streak: 0,
        last_gap: 0,
        reset_threshold: 4
      },
      calendarRecords: [],
      loading: false,
      loadGeneration: 0
    }
  },

  computed: {
    displayScore() {
      return Math.round(this.scoreData.score)
    },

    scoreColor() {
      const s = this.scoreData.score
      if (s >= 80) return '#34D399'
      if (s >= 60) return '#FBBF24'
      if (s >= 40) return '#FB923C'
      return '#EF4444'
    },

    scoreDescription() {
      const s = this.scoreData.score
      if (s >= 80) return '学习习惯非常稳定'
      if (s >= 60) return '保持不错，继续加油'
      if (s >= 40) return '有些波动，尝试更规律地学习'
      if (s > 0) return '需要提升学习连续性'
      return '开始你的学习之旅吧'
    },

    showRecovery() {
      const d = this.scoreData
      return d.effective_gap_days > 0 && d.current_streak > 0 && d.current_streak < d.reset_threshold
    },

    recoveryDaysLeft() {
      return this.scoreData.reset_threshold - this.scoreData.current_streak
    },

    recoveryPercent() {
      return Math.round((this.scoreData.current_streak / this.scoreData.reset_threshold) * 100)
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(val) {
        if (val) {
          this.loadData()
          this.$nextTick(() => {
            setTimeout(() => {
              this.animationVisible = true
            }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  methods: {
    formatDate(date) {
      const y = date.getFullYear()
      const m = String(date.getMonth() + 1).padStart(2, '0')
      const d = String(date.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    },

    close() {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close')
      }, 300)
    },

    async loadData() {
      this.loadGeneration++
      const gen = this.loadGeneration
      this.loading = true
      try {
        const [score, calendar] = await Promise.all([
          getContinuityScore(),
          getContinuityCalendar(6)
        ])
        if (gen !== this.loadGeneration) return
        this.scoreData = score
        this.calendarRecords = calendar.records || []
      } catch (_e) {
        // Show defaults on error
      } finally {
        if (gen === this.loadGeneration) {
          this.loading = false
        }
      }
    }
  }
}
</script>

<style scoped>
.drawer-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.drawer-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 200ms ease;
}

.drawer-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.drawer-container {
  position: relative;
  background: rgba(20, 20, 30, 0.95);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border-top-left-radius: 32rpx;
  border-top-right-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-bottom: none;
  padding: 16rpx 32rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom) + 100vh / 26 * 3);
  max-height: 80vh;
  overflow-y: auto;
  transform: translateY(100%);
  transition: transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .drawer-container {
    background: rgba(20, 20, 30, 0.98);
  }
}

.drawer-container.drawer-show {
  transform: translateY(0);
}

/* Handle */
.drawer-handle {
  display: flex;
  justify-content: center;
  padding: 12rpx 0;
}

.handle-bar {
  width: 72rpx;
  height: 8rpx;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4rpx;
}

/* Score Section */
.score-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16rpx 0 20rpx;
}

.score-value {
  font-size: 80rpx;
  font-weight: 800;
  line-height: 1;
}

.score-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 8rpx;
}

.score-desc {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 12rpx;
}

/* Stats Grid */
.stats-grid {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-around;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 20rpx;
  padding: 24rpx 0;
  margin-bottom: 20rpx;
}

.stats-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stats-value {
  font-size: 36rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.stats-label {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 6rpx;
}

.stats-divider {
  width: 1rpx;
  height: 48rpx;
  background: rgba(255, 255, 255, 0.1);
}

/* Recovery */
.recovery-section {
  margin-bottom: 20rpx;
}

.recovery-bar-bg {
  height: 12rpx;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6rpx;
  overflow: hidden;
}

.recovery-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #34D399, #10B981);
  border-radius: 6rpx;
  transition: width 300ms ease;
}

.recovery-text {
  font-size: 22rpx;
  color: rgba(52, 211, 153, 0.8);
  margin-top: 8rpx;
  text-align: center;
  display: block;
}

/* Calendar */
.calendar-section {
  margin-top: 8rpx;
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 16rpx;
  display: block;
}
</style>
