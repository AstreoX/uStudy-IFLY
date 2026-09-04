<template>
  <view class="widget-card">
    <!-- Header: title + month + divider -->
    <view class="timeline-header">
      <text class="timeline-title-label">学习动态</text>
      <text class="timeline-month">{{ monthLabel }}</text>
      <view class="timeline-header-line"></view>
    </view>

    <!-- Scrollable content -->
    <scroll-view
      scroll-y
      :show-scrollbar="false"
      class="timeline-scroll"
      :lower-threshold="80"
      @scrolltolower="handleScrollToLower"
    >
      <view class="timeline-body">
        <!-- Vertical line -->
        <view class="timeline-line"></view>

        <!-- AI Suggestion card -->
        <view v-if="suggestion" class="timeline-entry timeline-entry-suggestion">
          <view class="timeline-node timeline-node-suggestion">
            <svg class="timeline-svg-icon" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M176 232a8 8 0 0 1-8 8H88a8 8 0 0 1 0-16h80a8 8 0 0 1 8 8Zm40-128a87.55 87.55 0 0 1-33.64 69.21A16.24 16.24 0 0 0 176 186v6a16 16 0 0 1-16 16H96a16 16 0 0 1-16-16v-6a16 16 0 0 0-6.23-12.66A87.59 87.59 0 0 1 40 104.49C39.74 56.83 78.26 17.14 125.88 16A88 88 0 0 1 216 104Z" fill="currentColor"/>
            </svg>
          </view>
          <view class="suggestion-card">
            <text class="suggestion-title">{{ suggestion.title }}</text>
            <text class="suggestion-reason">{{ suggestion.reason }}</text>
          </view>
        </view>

        <!-- Loading -->
        <view v-if="loading" class="timeline-loading">
          <text class="loading-text">加载中...</text>
        </view>

        <!-- Empty -->
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
          >
            <view class="timeline-node">
              <svg class="timeline-svg-icon" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path :d="getIconPath(item.activity_type)" fill="currentColor"/>
              </svg>
            </view>
            <view class="timeline-content">
              <view class="timeline-main-row">
                <text class="timeline-title">{{ item.title }}</text>
                <text class="timeline-time">{{ formatTime(item.activity_time) }}</text>
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
              <!-- Tags: review status + node labels -->
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

        <view v-if="!loading && groupedItems.length && (loadingMore || !hasMore)" class="timeline-footer">
          <text class="timeline-footer-text">
            {{ loadingMore ? '正在加载更早的学习事项...' : '已经到底了' }}
          </text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { getActivityTimeline, getStudySuggestion } from '@/api/activity'

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
    const old = Object.keys(localStorage).filter(k => k.startsWith('suggestion_') && k !== currentKey)
    old.sort().reverse()
    old.slice(1).forEach(k => localStorage.removeItem(k))
  } catch (_) {}
}

const TIMELINE_CACHE_KEY = 'timeline_cache_v2'
const TIMELINE_CACHE_TTL = 5 * 60 * 1000
const TIMELINE_PAGE_SIZE = 20

// Inline SVG paths (Phosphor icons) replacing mobile image references
const ICON_PATHS = {
  // Books icon — 学习新知识
  '学习新知识': 'M231.65 194.55l-33.19-157.8a16 16 0 0 0-19-12.39l-46.81 10.06a16.08 16.08 0 0 0-12.3 19l33.19 157.8a16 16 0 0 0 19 12.39l46.81-10.06a16.08 16.08 0 0 0 12.3-19ZM136 192H40a16 16 0 0 1-16-16V48a16 16 0 0 1 16-16h96a16 16 0 0 1 16 16v128a16 16 0 0 1-16 16Z',
  // Clock counter-clockwise — 复习
  '复习': 'M136 80v43.47l36.12 21.67a8 8 0 0 1-8.24 13.72l-40-24A8 8 0 0 1 120 128V80a8 8 0 0 1 16 0Zm-8-48a99.38 99.38 0 0 0-70.76 29.34L32 36.28V96h59.72L63.27 67.56A84 84 0 1 1 44 128a8 8 0 0 0-16 0A100 100 0 1 0 128 32Z',
  // Pencil — 解题
  '解题': 'M227.31 73.37l-44.68-44.69a16 16 0 0 0-22.63 0L36.69 152A15.86 15.86 0 0 0 32 163.31V208a16 16 0 0 0 16 16h44.69a15.86 15.86 0 0 0 11.31-4.69L227.31 96a16 16 0 0 0 0-22.63Z',
  // Chat circle dots — 探讨
  '探讨': 'M128 24a104 104 0 0 0-91.82 152.88l-11.35 34.05a16 16 0 0 0 20.24 20.24l34.05-11.35A104 104 0 1 0 128 24Zm-20 128a12 12 0 1 1-12-12 12 12 0 0 1 12 12Zm32 0a12 12 0 1 1-12-12 12 12 0 0 1 12 12Zm32 0a12 12 0 1 1-12-12 12 12 0 0 1 12 12Z',
  // Exam — 测验
  '测验': 'M200 24H56a16 16 0 0 0-16 16v176a16 16 0 0 0 16 16h144a16 16 0 0 0 16-16V40a16 16 0 0 0-16-16Zm-40 152H96a8 8 0 0 1 0-16h64a8 8 0 0 1 0 16Zm0-32H96a8 8 0 0 1 0-16h64a8 8 0 0 1 0 16Zm0-32H96a8 8 0 0 1 0-16h64a8 8 0 0 1 0 16Z'
}

// Legacy English keys
ICON_PATHS.study = ICON_PATHS['学习新知识']
ICON_PATHS.review = ICON_PATHS['复习']
ICON_PATHS.exercise = ICON_PATHS['解题']
ICON_PATHS.exam = ICON_PATHS['测验']

const DEPTH_MAP = {
  '浅层浏览': '浅',
  '中等理解': '中',
  '深入掌握': '深'
}

export default {
  name: 'UpdatesWidget',

  data() {
    return {
      items: [],
      aiSuggestion: null,
      loading: true,
      loadingMore: false,
      page: 1,
      total: 0,
      hasMore: true,
      suggestionLoading: true,
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
      if (this.suggestionLoading && !this.aiSuggestion) {
        return {
          title: '正在思考建议...',
          reason: '正在分析你的学习情况'
        }
      }

      if (this.aiSuggestion) {
        return {
          title: this.aiSuggestion.title,
          reason: this.aiSuggestion.guidance
        }
      }

      if (this.items.length) {
        const reviewItem = this.items.find(i =>
          i.activity_type === '复习' || i.activity_type === 'review'
        )
        if (reviewItem) {
          return {
            title: `建议复习: ${reviewItem.subject_name || reviewItem.title}`,
            reason: '巩固已学内容，提升长期记忆'
          }
        }
        const first = this.items[0]
        return {
          title: `继续学习: ${first.subject_name || first.title}`,
          reason: '保持学习节奏，完成今日目标'
        }
      }

      return {
        title: '开始今天的学习吧',
        reason: '保持学习节奏，每天进步一点点'
      }
    }
  },

  mounted() {
    this.loadData()
  },

  methods: {
    async loadData() {
      const slotKey = _getSuggestionSlotKey()

      // 1. 先查本地缓存（命中则跳过对应 API 请求）
      let cachedTimeline = null
      let cachedSuggestion = null
      try {
        const rawTimeline = localStorage.getItem(TIMELINE_CACHE_KEY)
        if (rawTimeline) {
          const cached = JSON.parse(rawTimeline)
          if (Date.now() - cached.ts < TIMELINE_CACHE_TTL) cachedTimeline = cached
        }
      } catch (_) {}
      try {
        const rawSuggestion = localStorage.getItem(slotKey)
        if (rawSuggestion) cachedSuggestion = JSON.parse(rawSuggestion)
      } catch (_) {}

      if (cachedTimeline) {
        this.items = cachedTimeline.items || []
        this.page = cachedTimeline.page || 1
        this.total = cachedTimeline.total || this.items.length
        this.hasMore = typeof cachedTimeline.hasMore === 'boolean'
          ? cachedTimeline.hasMore
          : this.items.length < this.total
        this.loading = false
      }
      if (cachedSuggestion) {
        this.aiSuggestion = cachedSuggestion
        this.suggestionLoading = false
      }

      // 2. 未命中的部分并行请求 API
      const requests = []
      if (!cachedTimeline) requests.push(this.loadTimelinePage({ reset: true }))
      if (!cachedSuggestion) {
        requests.push(
          getStudySuggestion().then(r => {
            this.aiSuggestion = r
            try {
              localStorage.setItem(slotKey, JSON.stringify(r))
              _cleanOldSuggestionCache(slotKey)
            } catch (_) {}
            this.suggestionLoading = false
          })
        )
      }

      if (requests.length === 0) return

      await Promise.allSettled(requests)

      // 确保 loading 状态最终归位
      this.loading = false
      this.suggestionLoading = false
    },

    async loadTimelinePage({ reset = false } = {}) {
      if (!reset && (this.loading || this.loadingMore || !this.hasMore)) return

      if (reset) {
        this.loading = true
      } else {
        this.loadingMore = true
      }

      const nextPage = reset ? 1 : this.page + 1
      try {
        const result = await getActivityTimeline(nextPage, TIMELINE_PAGE_SIZE)
        const incomingItems = result.items || []
        const mergedItems = reset ? incomingItems : [...this.items, ...incomingItems]
        const total = typeof result.total === 'number' ? result.total : mergedItems.length

        this.items = mergedItems
        this.page = result.page || nextPage
        this.total = total
        this.hasMore = mergedItems.length < total

        try {
          localStorage.setItem(
            TIMELINE_CACHE_KEY,
            JSON.stringify({
              items: this.items,
              page: this.page,
              total: this.total,
              hasMore: this.hasMore,
              ts: Date.now()
            })
          )
        } catch (_) {}
      } catch (_) {
        if (reset) {
          this.items = []
          this.page = 1
          this.total = 0
          this.hasMore = false
        }
      } finally {
        this.loading = false
        this.loadingMore = false
      }
    },

    handleScrollToLower() {
      this.loadTimelinePage({ reset: false })
    },

    getIconPath(type) {
      return ICON_PATHS[type] || ICON_PATHS['学习新知识']
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
.widget-card {
  background: var(--color-widget-bg);
  border: 1px solid var(--color-widget-border);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  padding: 16px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

/* Header */
.timeline-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  flex-shrink: 0;
}

.timeline-title-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-widget-header);
  white-space: nowrap;
}

.timeline-month {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
}

.timeline-header-line {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.12);
}

/* Scroll area — hide scrollbar */
.timeline-scroll {
  flex: 1;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.timeline-scroll::-webkit-scrollbar {
  display: none;
}

/* Deep selector for uni-app scroll-view internal container */
.timeline-scroll :deep(.uni-scroll-view),
.timeline-scroll :deep(.uni-scroll-view::-webkit-scrollbar) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.timeline-scroll :deep(.uni-scroll-view::-webkit-scrollbar) {
  display: none;
  width: 0;
  height: 0;
}

/* Loading / Empty */
.timeline-loading,
.timeline-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
}

.loading-text,
.empty-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}

/* Timeline body */
.timeline-body {
  position: relative;
  padding-left: 34px;
}

.timeline-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 0 4px;
}

.timeline-footer-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}

.timeline-line {
  position: absolute;
  left: 11px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.12);
}

/* Date group */
.date-group-header {
  margin-bottom: 8px;
  margin-top: 4px;
}

.date-group-label {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.45);
}

/* Each entry */
.timeline-entry {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  margin-bottom: 16px;
  position: relative;
}

.timeline-entry:last-child {
  margin-bottom: 0;
}

/* Node circle with icon */
.timeline-node {
  position: absolute;
  left: -34px;
  top: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.timeline-svg-icon {
  width: 14px;
  height: 14px;
  color: rgba(255, 255, 255, 0.7);
}

/* Content area */
.timeline-content {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
}

.timeline-main-row {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
}

.timeline-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.timeline-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  flex-shrink: 0;
}

.timeline-subtitle {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 2px;
}

/* Summary */
.timeline-summary-row {
  margin-top: 4px;
  cursor: pointer;
}

.timeline-summary {
  font-size: 11px;
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
  gap: 4px;
  margin-top: 5px;
}

.node-tag {
  font-size: 10px;
  color: rgba(0, 122, 255, 0.8);
  background: rgba(0, 122, 255, 0.1);
  border: 1px solid rgba(0, 122, 255, 0.2);
  border-radius: 4px;
  padding: 2px 6px;
}

.review-tag {
  color: rgba(255, 149, 0, 0.9);
  background: rgba(255, 149, 0, 0.12);
  border-color: rgba(255, 149, 0, 0.25);
}

.review-done-tag {
  color: rgba(52, 199, 89, 0.95);
  background: rgba(52, 199, 89, 0.14);
  border-color: rgba(52, 199, 89, 0.28);
}

/* Suggestion card — highlighted */
.timeline-entry-suggestion {
  margin-bottom: 18px;
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
  border: 1px solid rgba(0, 122, 255, 0.25);
  border-radius: 8px;
  padding: 10px 12px;
}

.suggestion-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.suggestion-reason {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 3px;
}
</style>
