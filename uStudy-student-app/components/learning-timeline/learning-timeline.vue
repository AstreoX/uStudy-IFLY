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

      <!-- Suggested action card (always visible) -->
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

      <!-- Loading state -->
      <view v-if="loading" class="timeline-loading">
        <text class="loading-text">加载中...</text>
      </view>

      <!-- Empty state -->
      <view v-else-if="!groupedItems.length" class="timeline-empty">
        <text class="empty-text">暂无学习动态</text>
      </view>

      <!-- Date groups -->
      <template v-else v-for="(group, gi) in groupedItems" :key="gi">
        <view class="date-group-header">
          <text class="date-group-label">{{ group.label }}</text>
        </view>

        <view
          v-for="(item, index) in group.items"
          :key="item.id || index"
          class="timeline-entry"
          @click="onItemTap(item)"
        >
          <view class="timeline-node">
            <image
              class="timeline-icon"
              :src="getIcon(item.activity_type)"
              mode="aspectFit"
            ></image>
          </view>
          <view class="timeline-content">
            <view class="timeline-main-row">
              <text class="timeline-title">{{ item.title }}</text>
              <text class="timeline-date">{{ formatTime(item.activity_time) }}</text>
            </view>
            <text class="timeline-subtitle">{{ getSubtitle(item) }}</text>
            <!-- Summary (expandable) -->
            <view
              v-if="item.summary"
              class="timeline-summary-row"
              @click.stop="toggleSummary(item)"
            >
              <text
                class="timeline-summary"
                :class="{ 'summary-expanded': expandedIds[item.id] }"
              >{{ item.summary }}</text>
            </view>
            <!-- Related nodes & review tag -->
            <view v-if="(item.related_node_labels && item.related_node_labels.length) || item.next_review_date" class="node-tags">
              <text v-if="item.next_review_date" class="node-tag review-tag">建议复习：{{ formatReviewDate(item.next_review_date) }}</text>
              <text
                v-for="(label, li) in (item.related_node_labels || []).slice(0, 3)"
                :key="li"
                class="node-tag"
              >{{ label }}</text>
            </view>
          </view>
        </view>
      </template>
    </view>
    </scroll-view>

  </view>
</template>

<script>
const ICON_MAP = {
  '学习新知识': '/static/icons/phosphor-icons/SVGs/regular/books.svg',
  '复习': '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
  '解题': '/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg',
  '探讨': '/static/icons/phosphor-icons/SVGs/regular/chat-circle-dots.svg',
  '测验': '/static/icons/phosphor-icons/SVGs/regular/exam.svg',
  // Legacy keys
  study: '/static/icons/phosphor-icons/SVGs/regular/books.svg',
  review: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
  exercise: '/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg',
  exam: '/static/icons/phosphor-icons/SVGs/regular/exam.svg'
}

const DEPTH_MAP = {
  '浅层浏览': '浅',
  '中等理解': '中',
  '深入掌握': '深'
}

export default {
  name: 'LearningTimeline',

  props: {
    items: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    },
    aiSuggestion: {
      type: Object,
      default: null
    },
    suggestionLoading: {
      type: Boolean,
      default: false
    }
  },

  data() {
    return {
      expandedIds: {}
    }
  },

  computed: {
    monthLabel() {
      const now = new Date()
      return `${now.getMonth() + 1}月 ${now.getFullYear()}`
    },

    groupedItems() {
      if (!this.items.length) return []

      const groups = {}
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const yesterday = new Date(today)
      yesterday.setDate(yesterday.getDate() - 1)

      for (const item of this.items) {
        const d = new Date(item.activity_date || item.activity_time)
        d.setHours(0, 0, 0, 0)

        let label
        const key = d.toISOString().slice(0, 10)
        if (d.getTime() === today.getTime()) {
          label = '今天'
        } else if (d.getTime() === yesterday.getTime()) {
          label = '昨天'
        } else {
          label = `${d.getMonth() + 1}月${d.getDate()}日`
        }

        if (!groups[key]) {
          groups[key] = { label, items: [], sortKey: d.getTime() }
        }
        groups[key].items.push(item)
      }

      return Object.values(groups).sort((a, b) => b.sortKey - a.sortKey)
    },

    suggestion() {
      // Loading state while AI suggestion is being fetched
      if (this.suggestionLoading && !this.aiSuggestion) {
        return {
          title: '正在思考建议...',
          reason: '正在分析你的学习情况',
          item: null
        }
      }

      // Prefer AI suggestion when available
      if (this.aiSuggestion) {
        const matchingItem = this.items.find(i =>
          i.subject_name === this.aiSuggestion.subject ||
          i.title === this.aiSuggestion.subject
        )
        return {
          title: this.aiSuggestion.title,
          reason: this.aiSuggestion.guidance,
          item: matchingItem || null
        }
      }

      // Heuristic fallback: derive from real data
      if (this.items.length) {
        const reviewItem = this.items.find(i =>
          i.activity_type === '复习' || i.activity_type === 'review'
        )
        if (reviewItem) {
          return {
            title: `建议复习: ${reviewItem.subject_name || reviewItem.title}`,
            reason: '巩固已学内容，提升长期记忆',
            item: reviewItem
          }
        }
        const first = this.items[0]
        return {
          title: `继续学习: ${first.subject_name || first.title}`,
          reason: '保持学习节奏，完成今日目标',
          item: first
        }
      }

      // No data at all
      return {
        title: '开始今天的学习吧',
        reason: '保持学习节奏，每天进步一点点',
        item: null
      }
    }
  },

  methods: {
    getIcon(type) {
      return ICON_MAP[type] || ICON_MAP['学习新知识']
    },

    getSubtitle(item) {
      const parts = []
      if (item.activity_type) parts.push(item.activity_type)
      if (item.subject_name) parts.push(item.subject_name)
      if (item.study_depth && DEPTH_MAP[item.study_depth]) {
        parts.push(DEPTH_MAP[item.study_depth])
      }
      return parts.join(' · ') || '学习'
    },

    formatTime(timeStr) {
      if (!timeStr) return ''
      const d = new Date(timeStr)
      const h = d.getHours().toString().padStart(2, '0')
      const m = d.getMinutes().toString().padStart(2, '0')
      return `${h}:${m}`
    },

    toggleSummary(item) {
      this.expandedIds = {
        ...this.expandedIds,
        [item.id]: !this.expandedIds[item.id]
      }
    },

    onSuggestionTap() {
      if (this.suggestion) {
        this.$emit('suggestion-tap', this.suggestion.item)
      }
    },

    onItemTap(item) {
      this.$emit('item-tap', item)
    },

    formatReviewDate(dateStr) {
      if (!dateStr) return ''
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}月${d.getDate()}日`
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
  height: 1040rpx;
}

/* Loading / Empty */
.timeline-loading,
.timeline-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200rpx;
}

.loading-text,
.empty-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.35);
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

/* Date group */
.date-group-header {
  margin-bottom: 16rpx;
  margin-top: 8rpx;
}

.date-group-label {
  font-size: 22rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.45);
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

/* Summary */
.timeline-summary-row {
  margin-top: 8rpx;
}

.timeline-summary {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.summary-expanded {
  white-space: normal;
  overflow: visible;
}

/* Node tags */
.node-tags {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 10rpx;
}

.node-tag {
  font-size: 20rpx;
  color: rgba(0, 122, 255, 0.8);
  background: rgba(0, 122, 255, 0.1);
  border: 1rpx solid rgba(0, 122, 255, 0.2);
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
}

.review-tag {
  color: rgba(255, 149, 0, 0.9);
  background: rgba(255, 149, 0, 0.12);
  border-color: rgba(255, 149, 0, 0.25);
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
