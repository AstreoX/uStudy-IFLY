<template>
  <view class="timeline-container" :class="themeClass">
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
            <!-- Related nodes & review tags -->
            <view v-if="item.last_completed_review_number || (item.related_node_labels && item.related_node_labels.length) || item.next_review_date" class="node-tags">
              <text v-if="item.last_completed_review_number" class="node-tag review-done-tag">
                第{{ item.last_completed_review_number }}轮已完成 · {{ formatCompletedAt(item.last_completed_at) }}
              </text>
              <text v-if="item.next_review_date" class="node-tag review-tag">
                复习第{{ item.next_review_number }}轮：{{ formatReviewDate(item.next_review_date) }}
              </text>
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
import { normalizeThemeMode } from '@/utils/themeMode'

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
    themeMode: {
      type: String,
      default: 'dark'
    },
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
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode)}`
    },

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
    },

    formatCompletedAt(datetimeStr) {
      if (!datetimeStr) return ''
      const d = new Date(datetimeStr)
      const month = d.getMonth() + 1
      const day = d.getDate()
      const h = d.getHours().toString().padStart(2, '0')
      const m = d.getMinutes().toString().padStart(2, '0')
      return `${month}月${day}日 ${h}:${m}`
    }
  }
}
</script>

<style scoped>
.timeline-container {
  --timeline-text-strong: rgba(255, 255, 255, 0.9);
  --timeline-text-primary: rgba(255, 255, 255, 0.85);
  --timeline-text-secondary: rgba(255, 255, 255, 0.45);
  --timeline-text-muted: rgba(255, 255, 255, 0.35);
  --timeline-line: rgba(255, 255, 255, 0.12);
  --timeline-node-bg: rgba(255, 255, 255, 0.08);
  --timeline-node-border: rgba(255, 255, 255, 0.12);
  --timeline-icon-filter: brightness(0) invert(1);
  --timeline-icon-opacity: 0.7;
  --timeline-tag-blue-text: rgba(0, 122, 255, 0.8);
  --timeline-tag-blue-bg: rgba(0, 122, 255, 0.1);
  --timeline-tag-blue-border: rgba(0, 122, 255, 0.2);
  --timeline-tag-orange-text: rgba(255, 149, 0, 0.9);
  --timeline-tag-orange-bg: rgba(255, 149, 0, 0.12);
  --timeline-tag-orange-border: rgba(255, 149, 0, 0.25);
  --timeline-tag-green-text: rgba(52, 199, 89, 0.95);
  --timeline-tag-green-bg: rgba(52, 199, 89, 0.14);
  --timeline-tag-green-border: rgba(52, 199, 89, 0.28);
  --timeline-suggestion-node-bg: rgba(0, 122, 255, 0.2);
  --timeline-suggestion-node-border: rgba(0, 122, 255, 0.35);
  --timeline-suggestion-card-bg: linear-gradient(135deg, rgba(0, 122, 255, 0.15) 0%, rgba(100, 100, 255, 0.08) 100%);
  --timeline-suggestion-card-border: rgba(0, 122, 255, 0.25);
  --timeline-suggestion-title: rgba(255, 255, 255, 0.9);
  --timeline-suggestion-reason: rgba(255, 255, 255, 0.45);
  width: 100%;
}

.timeline-container.theme-light {
  --timeline-text-strong: #1f1a16;
  --timeline-text-primary: rgba(31, 26, 22, 0.84);
  --timeline-text-secondary: rgba(31, 26, 22, 0.58);
  --timeline-text-muted: rgba(31, 26, 22, 0.4);
  --timeline-line: rgba(63, 53, 42, 0.12);
  --timeline-node-bg: rgba(255, 255, 255, 0.86);
  --timeline-node-border: rgba(63, 53, 42, 0.1);
  --timeline-icon-filter: brightness(0) saturate(100%);
  --timeline-icon-opacity: 0.72;
  --timeline-tag-blue-text: #2f6eea;
  --timeline-tag-blue-bg: rgba(47, 110, 234, 0.12);
  --timeline-tag-blue-border: rgba(47, 110, 234, 0.2);
  --timeline-tag-orange-text: #a86412;
  --timeline-tag-orange-bg: rgba(192, 122, 24, 0.12);
  --timeline-tag-orange-border: rgba(192, 122, 24, 0.2);
  --timeline-tag-green-text: #2f8f62;
  --timeline-tag-green-bg: rgba(47, 143, 98, 0.12);
  --timeline-tag-green-border: rgba(47, 143, 98, 0.2);
  --timeline-suggestion-node-bg: rgba(47, 110, 234, 0.14);
  --timeline-suggestion-node-border: rgba(47, 110, 234, 0.22);
  --timeline-suggestion-card-bg: linear-gradient(135deg, rgba(47, 110, 234, 0.12) 0%, rgba(126, 153, 216, 0.08) 100%);
  --timeline-suggestion-card-border: rgba(47, 110, 234, 0.18);
  --timeline-suggestion-title: #1f1a16;
  --timeline-suggestion-reason: rgba(31, 26, 22, 0.58);
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
  color: var(--timeline-text-secondary);
  white-space: nowrap;
}

.timeline-header-line {
  flex: 1;
  height: 1rpx;
  background: var(--timeline-line);
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
  color: var(--timeline-text-muted);
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
  background: var(--timeline-line);
}

/* Date group */
.date-group-header {
  margin-bottom: 16rpx;
  margin-top: 8rpx;
}

.date-group-label {
  font-size: 22rpx;
  font-weight: 600;
  color: var(--timeline-text-secondary);
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
  background: var(--timeline-node-bg);
  border: 1rpx solid var(--timeline-node-border);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.timeline-icon {
  width: 28rpx;
  height: 28rpx;
  filter: var(--timeline-icon-filter);
  opacity: var(--timeline-icon-opacity);
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
  color: var(--timeline-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.timeline-date {
  font-size: 22rpx;
  color: var(--timeline-text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.timeline-subtitle {
  font-size: 22rpx;
  color: var(--timeline-text-secondary);
  margin-top: 4rpx;
}

/* Summary */
.timeline-summary-row {
  margin-top: 8rpx;
}

.timeline-summary {
  font-size: 22rpx;
  color: var(--timeline-text-muted);
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
  color: var(--timeline-tag-blue-text);
  background: var(--timeline-tag-blue-bg);
  border: 1rpx solid var(--timeline-tag-blue-border);
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
}

.review-tag {
  color: var(--timeline-tag-orange-text);
  background: var(--timeline-tag-orange-bg);
  border-color: var(--timeline-tag-orange-border);
}

.review-done-tag {
  color: var(--timeline-tag-green-text);
  background: var(--timeline-tag-green-bg);
  border-color: var(--timeline-tag-green-border);
}

/* Suggestion card — highlighted */
.timeline-entry-suggestion {
  margin-bottom: 36rpx;
}

.timeline-node-suggestion {
  background: var(--timeline-suggestion-node-bg);
  border-color: var(--timeline-suggestion-node-border);
  top: 50%;
  transform: translateY(-50%);
}

.suggestion-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--timeline-suggestion-card-bg);
  border: 1rpx solid var(--timeline-suggestion-card-border);
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
}

.suggestion-title {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--timeline-suggestion-title);
}

.suggestion-reason {
  font-size: 22rpx;
  color: var(--timeline-suggestion-reason);
  margin-top: 6rpx;
}
</style>
