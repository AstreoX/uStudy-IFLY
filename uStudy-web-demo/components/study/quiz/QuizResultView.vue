<template>
  <view class="quiz-result-view">
    <view class="result-toolbar">
      <view class="toolbar-btn" @tap="$emit('back')">
        <text class="toolbar-btn-text">返回列表</text>
      </view>
      <text class="toolbar-title">测试结果</text>
      <view class="toolbar-placeholder"></view>
    </view>

    <view v-if="loading" class="state-wrap">
      <text class="state-text">正在加载评估结果...</text>
    </view>

    <view v-else-if="loadError" class="state-wrap">
      <text class="state-text state-error">{{ loadError }}</text>
      <view class="retry-btn" @tap="$emit('retry')">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <scroll-view v-else class="result-scroll" scroll-y>
      <view class="score-card">
        <view class="score-ring-wrap">
          <svg class="score-ring" viewBox="0 0 120 120">
            <circle
              cx="60"
              cy="60"
              r="52"
              fill="none"
              stroke="rgba(255, 255, 255, 0.1)"
              stroke-width="8"
            />
            <circle
              cx="60"
              cy="60"
              r="52"
              fill="none"
              stroke="#0088FF"
              stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="circumference"
              :stroke-dashoffset="progressOffset"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <view class="score-center">
            <image class="trophy-icon" src="/static/icons/phosphor/regular/trophy-fill.svg" mode="aspectFit"></image>
            <text class="score-main">{{ safeResult.score }}/{{ safeResult.totalScore }}分</text>
          </view>
        </view>
      </view>

      <view class="analysis-row">
        <view class="analysis-card strength-card">
          <view class="card-header">
            <image class="card-header-icon strength-icon" src="/static/icons/phosphor/regular/thumbs-up.svg" mode="aspectFit"></image>
            <text class="analysis-title">优点分析</text>
          </view>
          <view v-if="safeResult.strengths.length > 0" class="analysis-list">
            <text
              v-for="(item, index) in safeResult.strengths"
              :key="`s-${index}`"
              class="analysis-item"
            >• {{ item }}</text>
          </view>
          <text v-else class="analysis-empty">暂无</text>
        </view>

        <view class="analysis-card weakness-card">
          <view class="card-header">
            <image class="card-header-icon weakness-icon" src="/static/icons/phosphor/regular/warning-circle.svg" mode="aspectFit"></image>
            <text class="analysis-title">缺点分析</text>
          </view>
          <view v-if="safeResult.weaknesses.length > 0" class="analysis-list">
            <text
              v-for="(item, index) in safeResult.weaknesses"
              :key="`w-${index}`"
              class="analysis-item"
            >• {{ item }}</text>
          </view>
          <text v-else class="analysis-empty">暂无</text>
        </view>
      </view>

      <view class="suggest-card">
        <view class="card-header">
          <image class="card-header-icon suggest-icon" src="/static/icons/phosphor/regular/lightbulb.svg" mode="aspectFit"></image>
          <text class="analysis-title">提升建议</text>
        </view>
        <view v-if="safeResult.suggestions.length > 0" class="analysis-list">
          <view
            v-for="(item, index) in safeResult.suggestions"
            :key="`sg-${index}`"
            class="suggestion-item"
          >
            <text class="suggestion-number">{{ index + 1 }}.</text>
            <text class="analysis-item">{{ item }}</text>
          </view>
        </view>
        <text v-else class="analysis-empty">暂无</text>
      </view>

      <view class="questions-card">
        <view class="card-header">
          <image class="card-header-icon" src="/static/icons/phosphor/regular/list-checks.svg" mode="aspectFit"></image>
          <text class="analysis-title">逐题评估</text>
        </view>
        <view v-if="safeResult.questionResults.length === 0" class="analysis-empty-wrap">
          <text class="analysis-empty">暂无评估详情</text>
        </view>
        <view
          v-for="item in safeResult.questionResults"
          :key="item.id"
          class="question-item"
        >
          <view class="question-main" @tap="toggleExpanded(item.id)">
            <view class="question-main-left">
              <text class="question-order">Q{{ item.order }}</text>
              <text class="question-title">{{ item.title }}</text>
            </view>
            <view class="question-main-right">
              <text class="question-score">{{ item.score }}/{{ item.maxScore }}</text>
              <text class="question-status" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</text>
            </view>
          </view>

          <view v-if="isExpanded(item.id)" class="question-expanded">
            <view v-if="item.options && item.options.length" class="expanded-section">
              <text class="expanded-label">选项</text>
              <view class="options-list">
                <text
                  v-for="(opt, idx) in item.options"
                  :key="idx"
                  class="option-item"
                >{{ optionLabel(idx) }}. {{ opt }}</text>
              </view>
            </view>
            <view class="expanded-section">
              <text class="expanded-label">你的答案</text>
              <text class="expanded-text">{{ item.userAnswerDisplay || '（未作答）' }}</text>
            </view>
            <view class="expanded-section">
              <text class="expanded-label">标准答案</text>
              <text class="expanded-text">{{ item.correctAnswerDisplay || '（未作答）' }}</text>
            </view>
            <view v-if="item.aiEvaluation" class="expanded-section">
              <text class="expanded-label">AI 评语</text>
              <text class="expanded-text">{{ item.aiEvaluation }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="safeResult.debugInfo" class="debug-card">
        <text class="analysis-title">调试信息</text>
        <text class="debug-line">模型: {{ safeResult.debugInfo.model_name || '-' }}</text>
        <text class="debug-line">总耗时: {{ formatDuration(safeResult.debugInfo.total_duration_ms) }}</text>
      </view>
    </scroll-view>
  </view>
</template>

<script>
const OPTION_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

export default {
  name: 'QuizResultView',
  props: {
    loading: {
      type: Boolean,
      default: false
    },
    loadError: {
      type: String,
      default: ''
    },
    resultData: {
      type: Object,
      default: null
    }
  },
  emits: ['back', 'retry'],
  data() {
    return {
      expandedIds: {}
    }
  },
  computed: {
    safeResult() {
      const source = this.resultData || {}
      return {
        score: source.score || 0,
        totalScore: source.totalScore || 0,
        strengths: Array.isArray(source.strengths) ? source.strengths : [],
        weaknesses: Array.isArray(source.weaknesses) ? source.weaknesses : [],
        suggestions: Array.isArray(source.suggestions) ? source.suggestions : [],
        questionResults: Array.isArray(source.questionResults) ? source.questionResults : [],
        debugInfo: source.debugInfo || null
      }
    },
    circumference() {
      return 326.7
    },
    progressPercent() {
      if (!this.safeResult.totalScore) return 0
      const value = this.safeResult.score / this.safeResult.totalScore
      return Math.max(0, Math.min(1, value))
    },
    progressOffset() {
      return this.circumference * (1 - this.progressPercent)
    }
  },
  watch: {
    resultData: {
      immediate: true,
      handler() {
        const nextExpanded = {}
        const list = Array.isArray(this.resultData?.questionResults) ? this.resultData.questionResults : []
        list.forEach((item, idx) => {
          if (idx < 1) nextExpanded[item.id] = true
        })
        this.expandedIds = nextExpanded
      }
    }
  },
  methods: {
    optionLabel(index) {
      return OPTION_LABELS[index] || String(index + 1)
    },
    statusLabel(status) {
      if (status === 'correct') return '正确'
      if (status === 'wrong') return '错误'
      if (status === 'partial') return '部分'
      return '-'
    },
    statusClass(status) {
      if (status === 'correct') return 'question-status-correct'
      if (status === 'wrong') return 'question-status-wrong'
      if (status === 'partial') return 'question-status-partial'
      return ''
    },
    toggleExpanded(id) {
      this.expandedIds = {
        ...this.expandedIds,
        [id]: !this.expandedIds[id]
      }
    },
    isExpanded(id) {
      return !!this.expandedIds[id]
    },
    formatDuration(durationMs) {
      const value = Number(durationMs) || 0
      return `${(value / 1000).toFixed(1)}s`
    }
  }
}
</script>

<style scoped>
.quiz-result-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24rpx;
  box-sizing: border-box;
}

.result-toolbar {
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.toolbar-btn {
  flex-shrink: 0;
  height: 58rpx;
  min-width: 120rpx;
  border-radius: 999rpx;
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
}

.toolbar-btn-text {
  font-size: 24rpx;
  color: #ffffff;
}

.toolbar-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.toolbar-placeholder {
  width: 120rpx;
}

.state-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
}

.state-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
}

.state-error {
  color: #fca5a5;
}

.retry-btn {
  height: 64rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(96, 165, 250, 0.4);
  background: rgba(96, 165, 250, 0.16);
}

.retry-btn-text {
  font-size: 24rpx;
  color: #93c5fd;
}

.result-scroll {
  flex: 1;
  min-height: 0;
}

/* Custom Scrollbar — matches dark glassmorphic theme */
.result-scroll :deep(.uni-scroll-view)::-webkit-scrollbar {
  width: 6px;
}

.result-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-track {
  background: transparent;
}

.result-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.result-scroll :deep(.uni-scroll-view)::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Firefox */
.result-scroll :deep(.uni-scroll-view) {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.score-card,
.analysis-card,
.suggest-card,
.questions-card,
.debug-card {
  border-radius: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(20, 20, 35, 0.88);
}

.score-card {
  padding: 22rpx;
  margin-bottom: 16rpx;
  display: flex;
  justify-content: center;
}

.score-ring-wrap {
  position: relative;
  width: 260rpx;
  height: 260rpx;
}

.score-ring {
  width: 100%;
  height: 100%;
}

.score-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
}

.trophy-icon {
  width: 72rpx;
  height: 72rpx;
  filter: brightness(0) saturate(100%) invert(74%) sepia(46%) saturate(959%) hue-rotate(354deg) brightness(101%) contrast(96%);
}

.score-main {
  font-size: 36rpx;
  color: #ffffff;
  font-weight: 700;
}

.analysis-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.analysis-card {
  padding: 20rpx;
  border-width: 2rpx;
}

.strength-card {
  border-color: rgba(134, 239, 172, 0.4);
}

.weakness-card {
  border-color: rgba(239, 68, 68, 0.4);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}

.card-header-icon {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(1);
}

.strength-icon {
  filter: brightness(0) saturate(100%) invert(85%) sepia(25%) saturate(556%) hue-rotate(85deg) brightness(96%) contrast(92%);
}

.weakness-icon {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
}

.suggest-icon {
  filter: brightness(0) saturate(100%) invert(69%) sepia(67%) saturate(634%) hue-rotate(356deg) brightness(102%) contrast(93%);
}

.analysis-title {
  font-size: 26rpx;
  color: #ffffff;
  font-weight: 600;
}

.analysis-list {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.analysis-item {
  font-size: 23rpx;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.84);
}

.analysis-empty-wrap {
  padding: 14rpx 0;
}

.analysis-empty {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.5);
}

.suggest-card {
  margin-bottom: 12rpx;
  padding: 20rpx;
  border-color: rgba(245, 158, 11, 0.4);
  border-width: 2rpx;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 6rpx;
}

.suggestion-number {
  font-size: 23rpx;
  color: rgba(245, 158, 11, 0.9);
  font-weight: 500;
  line-height: 1.45;
  flex-shrink: 0;
}

.questions-card {
  margin-bottom: 12rpx;
  padding: 20rpx;
}

.question-item {
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.question-item:first-of-type {
  border-top: none;
}

.question-main {
  min-height: 86rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.question-main-left {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.question-order {
  flex-shrink: 0;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.55);
}

.question-title {
  min-width: 0;
  flex: 1;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.question-main-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.question-score {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.question-status {
  font-size: 20rpx;
  font-weight: 500;
  padding: 6rpx 14rpx;
  border-radius: 8rpx;
}

.question-status-correct {
  color: #10B981;
  background: rgba(16, 185, 129, 0.2);
}

.question-status-wrong {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.2);
}

.question-status-partial {
  color: #F59E0B;
  background: rgba(245, 158, 11, 0.2);
}

.question-expanded {
  padding: 0 0 14rpx;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.expanded-section {
  border-radius: 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  padding: 12rpx 14rpx;
}

.expanded-label {
  display: block;
  font-size: 21rpx;
  color: rgba(255, 255, 255, 0.58);
  margin-bottom: 6rpx;
}

.expanded-text {
  font-size: 22rpx;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.88);
  white-space: pre-wrap;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.option-item {
  font-size: 22rpx;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.86);
}

.debug-card {
  padding: 18rpx;
}

.debug-line {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.72);
}

@media (max-width: 900px) {
  .analysis-row {
    grid-template-columns: 1fr;
  }
}
</style>
