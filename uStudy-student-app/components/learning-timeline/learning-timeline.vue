<template>
  <view class="timeline-container">
    <!-- Month header -->
    <view class="timeline-header">
      <text class="timeline-month">{{ monthLabel }}</text>
      <view class="timeline-header-line"></view>
    </view>

    <!-- Timeline body -->
    <scroll-view scroll-y class="timeline-scroll">
    <view class="timeline-body">
      <!-- Vertical line -->
      <view class="timeline-line"></view>

      <!-- Suggested action card -->
      <view
        v-if="suggestion"
        class="timeline-entry timeline-entry-suggestion"
        @click="onSuggestionTap"
      >
        <view class="timeline-node timeline-node-suggestion">
          <image
            class="timeline-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/lightbulb.svg"
            mode="aspectFit"
          ></image>
        </view>
        <view class="suggestion-card">
          <text class="suggestion-title">{{ suggestion.title }}</text>
          <text class="suggestion-reason">{{ suggestion.reason }}</text>
        </view>
      </view>

      <!-- Each event -->
      <view
        v-for="(item, index) in items"
        :key="index"
        class="timeline-entry"
      >
        <view class="timeline-node">
          <image
            class="timeline-icon"
            :src="getIcon(item.type)"
            mode="aspectFit"
          ></image>
        </view>
        <view class="timeline-content">
          <view class="timeline-main-row">
            <text class="timeline-title">{{ item.name }}</text>
            <text class="timeline-date">{{ item.time }}</text>
          </view>
          <text class="timeline-subtitle">{{ getSubtitle(item) }}</text>
        </view>
      </view>
    </view>
    </scroll-view>
  </view>
</template>

<script>
const ICON_MAP = {
  study: '/static/icons/phosphor-icons/SVGs/regular/books.svg',
  review: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
  exercise: '/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg',
  exam: '/static/icons/phosphor-icons/SVGs/regular/exam.svg'
}

const LABEL_MAP = {
  study: '学习',
  review: '复习',
  exercise: '练习',
  exam: '考试'
}

export default {
  name: 'LearningTimeline',

  props: {
    items: {
      type: Array,
      default: () => []
    }
  },

  computed: {
    monthLabel() {
      const now = new Date()
      return `${now.getMonth() + 1}月 ${now.getFullYear()}`
    },

    suggestion() {
      if (!this.items.length) return null

      const reviewItem = this.items.find(i => i.type === 'review')
      if (reviewItem) {
        const subject = this.extractSubject(reviewItem.name)
        return {
          title: `建议复习: ${subject}`,
          reason: '巩固已学内容，提升长期记忆',
          item: reviewItem
        }
      }

      const studyItem = this.items[0]
      const subject = this.extractSubject(studyItem.name)
      return {
        title: `继续学习: ${subject}`,
        reason: '保持学习节奏，完成今日目标',
        item: studyItem
      }
    }
  },

  methods: {
    getIcon(type) {
      return ICON_MAP[type] || ICON_MAP.study
    },

    getSubtitle(item) {
      const typeLabel = LABEL_MAP[item.type] || '学习'
      const subject = item.subject || this.extractSubject(item.name)
      return `${typeLabel} · ${subject}`
    },

    extractSubject(name) {
      if (!name) return ''
      const dashIndex = name.indexOf(' - ')
      return dashIndex > 0 ? name.substring(0, dashIndex) : name
    },

    onSuggestionTap() {
      if (this.suggestion) {
        this.$emit('suggestion-tap', this.suggestion.item)
      }
    }
  }
}
</script>

<style scoped>
.timeline-container {
  width: 100%;
}

/* Month header */
.timeline-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 28rpx;
}

.timeline-month {
  font-size: 24rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
}

.timeline-header-line {
  flex: 1;
  height: 1rpx;
  background: rgba(255, 255, 255, 0.12);
}

.timeline-scroll {
  height: 520rpx;
}

/* Timeline body */
.timeline-body {
  position: relative;
  padding-left: 68rpx;
}

.timeline-line {
  position: absolute;
  left: 23rpx;
  top: 0;
  bottom: 0;
  width: 2rpx;
  background: rgba(255, 255, 255, 0.12);
}

/* Each entry */
.timeline-entry {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  margin-bottom: 32rpx;
  position: relative;
}

.timeline-entry:last-child {
  margin-bottom: 0;
}

/* Node circle with icon */
.timeline-node {
  position: absolute;
  left: -68rpx;
  top: 0;
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.timeline-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.7;
}

/* Content area */
.timeline-content {
  flex: 1;
  min-width: 0;
  padding-top: 4rpx;
}

.timeline-main-row {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  justify-content: space-between;
  gap: 12rpx;
}

.timeline-title {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.timeline-date {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  flex-shrink: 0;
}

.timeline-subtitle {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 4rpx;
}

/* Suggestion card — highlighted */
.timeline-entry-suggestion {
  margin-bottom: 36rpx;
}

.timeline-node-suggestion {
  background: rgba(0, 122, 255, 0.2);
  border-color: rgba(0, 122, 255, 0.35);
  top: 50%;
  transform: translateY(-50%);
}

.suggestion-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, rgba(0, 122, 255, 0.15) 0%, rgba(100, 100, 255, 0.08) 100%);
  border: 1rpx solid rgba(0, 122, 255, 0.25);
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
}

.suggestion-title {
  font-size: 26rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.suggestion-reason {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 6rpx;
}
</style>
