<template>
  <view class="quiz-result-view">
    <view class="result-toolbar">
      <view class="toolbar-btn" @tap="$emit('back')">
        <text class="toolbar-btn-text">返回列表</text>
      </view>
      <text class="toolbar-title">{{ itemKind === 'assignment' ? '作业结果' : '测试结果' }}</text>
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
      <view v-if="isResultPending || isResultFailed" class="assignment-result-state" :class="{ 'assignment-result-state-failed': isResultFailed }">
        <view v-if="isResultPending" class="grading-spinner">
          <view class="grading-spinner-dot" />
        </view>
        <text class="assignment-result-state-title">{{ isResultFailed ? '批改暂时失败' : 'AI 正在初评' }}</text>
        <text class="assignment-result-state-sub">
          {{ isResultFailed ? '已完成的客观题结果会保留，请稍后重试或等待教师处理。' : '客观题将自动计分，简答题正在生成个性化反馈。页面会自动刷新。' }}
        </text>
        <view v-if="isResultFailed" class="retry-btn result-retry-btn" @tap="$emit('retry')">
          <text class="retry-btn-text">重新加载</text>
        </view>
      </view>

      <template v-if="(!isResultPending && !isResultFailed) || safeResult.questionResults.length">
      <view v-if="itemKind === 'assignment'" class="assignment-result-meta">
        <view class="assignment-score-label">
          <view class="assignment-score-dot" />
          <text class="assignment-score-label-text">{{ safeResult.scoreLabel }}</text>
        </view>
        <text class="answer-release-text" :class="{ 'answer-release-open': safeResult.answersReleased }">{{ safeResult.answerReleaseText }}</text>
      </view>
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
              :stroke="itemKind === 'assignment' ? '#8b5cf6' : '#0088FF'"
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

      <view v-if="itemKind === 'assignment' && safeResult.teacherFeedback" class="teacher-feedback-card">
        <text class="teacher-feedback-label">教师评语</text>
        <text class="teacher-feedback-text">{{ safeResult.teacherFeedback }}</text>
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
              <text class="question-score">{{ displayQuestionScore(item) }}</text>
              <text class="question-status" :class="statusClass(questionStatus(item))">{{ statusLabel(questionStatus(item)) }}</text>
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
            <view v-if="item.questionType === 'code'" class="oj-result-panel">
              <view class="oj-verdict-line">
                <view class="oj-verdict-dot" :class="`oj-${normalizeVerdict(item.graderResult?.verdict || item.status)}`"></view>
                <strong>{{ verdictLabel(item.graderResult?.verdict || item.status) }}</strong>
                <text v-if="item.graderResult?.time_ms !== undefined">{{ item.graderResult.time_ms }} ms</text>
                <text v-if="item.graderResult?.memory_kb !== undefined">{{ formatMemory(item.graderResult.memory_kb) }}</text>
              </view>
              <view v-if="ojGroups(item).length" class="oj-groups">
                <view v-for="(group, groupIndex) in ojGroups(item)" :key="group.id || group.name || groupIndex" class="oj-group-row">
                  <view><strong>{{ group.name || `测试组 ${groupIndex + 1}` }}</strong><text>{{ verdictLabel(group.verdict || group.status) }}</text></view>
                  <view><text>{{ group.time_ms !== undefined ? `${group.time_ms} ms` : '' }}</text><text>{{ group.memory_kb !== undefined ? formatMemory(group.memory_kb) : '' }}</text><strong>{{ group.score ?? 0 }}/{{ group.max_score ?? group.maxScore ?? 0 }}</strong></view>
                </view>
              </view>
              <pre v-if="item.graderResult?.compile_output" class="oj-console">{{ item.graderResult.compile_output }}</pre>
              <view class="expanded-section code-section">
                <text class="expanded-label">提交代码 · {{ languageLabel(item.userAnswer?.language) }}</text>
                <pre class="oj-source">{{ item.userAnswer?.source || '（未作答）' }}</pre>
              </view>
              <view v-if="safeResult.answersReleased && item.solution" class="expanded-section code-section solution-section">
                <text class="expanded-label">题解与参考代码</text>
                <text v-if="item.solution.explanation || item.solution.reference" class="expanded-text solution-text">{{ item.solution.explanation || item.solution.reference }}</text>
                <pre v-if="referenceSource(item.solution)" class="oj-source">{{ referenceSource(item.solution) }}</pre>
              </view>
            </view>
            <view v-else class="expanded-section">
              <text class="expanded-label">你的答案</text>
              <text class="expanded-text">{{ item.userAnswerDisplay || '（未作答）' }}</text>
            </view>
            <view v-if="item.questionType !== 'code' && (itemKind !== 'assignment' || safeResult.answersReleased)" class="expanded-section">
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
      </template>
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
    },
    itemKind: {
      type: String,
      default: 'quiz'
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
        debugInfo: source.debugInfo || null,
        status: source.status || 'completed',
        scoreLabel: source.scoreLabel || 'AI 初评',
        answersReleased: source.answersReleased === true,
        answerReleaseText: source.answerReleaseText || '标准答案将在截止后开放',
        teacherFeedback: source.teacherFeedback || ''
      }
    },
    isResultPending() {
      return this.itemKind === 'assignment' && ['submitted', 'pending', 'queued', 'grading', 'evaluating'].includes(this.safeResult.status)
    },
    isResultFailed() {
      return this.itemKind === 'assignment' && ['failed', 'grading_failed'].includes(this.safeResult.status)
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
      if (status === 'failed') return '待重试'
      if (this.normalizeVerdict(status) === 'accepted') return '通过'
      if (['wrong_answer', 'compile_error', 'runtime_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'output_limit_exceeded', 'dangerous_syscall'].includes(this.normalizeVerdict(status))) return this.verdictLabel(status)
      return '-'
    },
    statusClass(status) {
      if (status === 'correct') return 'question-status-correct'
      if (status === 'wrong') return 'question-status-wrong'
      if (status === 'partial') return 'question-status-partial'
      if (status === 'failed') return 'question-status-failed'
      if (this.normalizeVerdict(status) === 'accepted') return 'question-status-correct'
      if (['wrong_answer', 'compile_error', 'runtime_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'output_limit_exceeded', 'dangerous_syscall'].includes(this.normalizeVerdict(status))) return 'question-status-wrong'
      return ''
    },
    questionStatus(item) {
      return item?.questionType === 'code' ? (item?.graderResult?.verdict || item?.status) : item?.status
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
    },
    displayQuestionScore(item) {
      if (!Number.isFinite(item?.score)) return `待批改/${item?.maxScore || 0}`
      return `${item.score}/${item.maxScore}`
    },
    normalizeVerdict(value) {
      const raw = String(value || '').toLowerCase().replace(/\s+/g, '_')
      return { ac: 'accepted', wa: 'wrong_answer', ce: 'compile_error', re: 'runtime_error', tle: 'time_limit_exceeded', mle: 'memory_limit_exceeded', ole: 'output_limit_exceeded', correct: 'accepted', wrong: 'wrong_answer' }[raw] || raw
    },
    verdictLabel(value) {
      const normalized = this.normalizeVerdict(value)
      return { accepted: '通过', wrong_answer: '答案错误', compile_error: '编译错误', runtime_error: '运行错误', time_limit_exceeded: '超出时间限制', memory_limit_exceeded: '超出内存限制', output_limit_exceeded: '输出超限', dangerous_syscall: '危险调用', system_error: '判题服务异常', failed: '待重试' }[normalized] || value || '待判定'
    },
    ojGroups(item) {
      const result = item?.graderResult || {}
      return Array.isArray(result.groups) ? result.groups : (Array.isArray(result.test_groups) ? result.test_groups : [])
    },
    languageLabel(language) { return language === 'cpp20' ? 'GNU C++20' : 'Python 3.11' },
    formatMemory(kb) { return Number(kb) >= 1024 ? `${(Number(kb) / 1024).toFixed(1)} MB` : `${Number(kb)} KB` },
    referenceSource(solution) {
      if (!solution || typeof solution !== 'object') return ''
      return solution.source || solution.reference_code || solution.code || solution.reference_solution?.source || ''
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

.assignment-result-state {
  min-height: 440rpx;
  padding: 48rpx 36rpx;
  border-radius: 20rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: linear-gradient(145deg, rgba(76, 29, 149, 0.24), rgba(20, 20, 35, 0.9) 64%);
  border: 1rpx solid rgba(196, 181, 253, 0.2);
}

.assignment-result-state-failed {
  background: linear-gradient(145deg, rgba(127, 29, 29, 0.2), rgba(20, 20, 35, 0.9) 64%);
  border-color: rgba(252, 165, 165, 0.2);
}

.grading-spinner {
  width: 78rpx;
  height: 78rpx;
  margin-bottom: 24rpx;
  border-radius: 50%;
  border: 5rpx solid rgba(196, 181, 253, 0.18);
  border-top-color: #a78bfa;
  animation: gradingSpin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.grading-spinner-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: #c4b5fd;
  box-shadow: 0 0 16rpx rgba(196, 181, 253, 0.78);
}

@keyframes gradingSpin {
  to { transform: rotate(360deg); }
}

.assignment-result-state-title {
  font-size: 30rpx;
  color: #ffffff;
  font-weight: 600;
}

.assignment-result-state-sub {
  max-width: 560rpx;
  margin-top: 12rpx;
  font-size: 22rpx;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.58);
}

.result-retry-btn {
  margin-top: 24rpx;
}

.assignment-result-meta {
  min-height: 58rpx;
  margin-bottom: 14rpx;
  padding: 0 18rpx;
  border-radius: 14rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  background: rgba(124, 58, 237, 0.1);
  border: 1rpx solid rgba(196, 181, 253, 0.18);
}

.assignment-score-label {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.assignment-score-dot {
  width: 9rpx;
  height: 9rpx;
  border-radius: 50%;
  background: #a78bfa;
  box-shadow: 0 0 10rpx rgba(167, 139, 250, 0.7);
}

.assignment-score-label-text {
  font-size: 21rpx;
  color: #ddd6fe;
  font-weight: 600;
}

.answer-release-text {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.5);
}

.answer-release-open {
  color: #86efac;
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

.teacher-feedback-card {
  margin-bottom: 16rpx;
  padding: 18rpx 20rpx;
  border-radius: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  background: rgba(124, 58, 237, 0.1);
  border: 1rpx solid rgba(196, 181, 253, 0.2);
}

.teacher-feedback-label {
  font-size: 21rpx;
  color: #c4b5fd;
  font-weight: 600;
}

.teacher-feedback-text {
  font-size: 23rpx;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.86);
  white-space: pre-wrap;
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

.question-status-failed {
  color: #c4b5fd;
  background: rgba(139, 92, 246, 0.18);
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

.oj-result-panel { display: flex; flex-direction: column; gap: 10rpx; }
.oj-verdict-line { min-height: 54rpx; display: flex; align-items: center; gap: 12rpx; padding: 0 2rpx; border-bottom: 1rpx solid rgba(255,255,255,.08); }
.oj-verdict-line strong { color: rgba(255,255,255,.88); font-size: 22rpx; }.oj-verdict-line text { color: rgba(148,163,184,.65); font-size: 18rpx; }
.oj-verdict-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: #fb7185; }.oj-accepted { background: #34d399; }.oj-system_error { background: #f59e0b; }
.oj-groups { border-top: 1rpx solid rgba(148,163,184,.09); }.oj-group-row { min-height: 58rpx; display: flex; align-items: center; justify-content: space-between; gap: 16rpx; border-bottom: 1rpx solid rgba(148,163,184,.08); }
.oj-group-row > view { display: flex; align-items: center; gap: 12rpx; }.oj-group-row strong { color: #cbd5e1; font-size: 20rpx; }.oj-group-row text { color: #64748b; font-size: 17rpx; }
.code-section { padding: 0; overflow: hidden; border-radius: 8rpx; background: #0d0e16; }.code-section .expanded-label { margin: 0; padding: 12rpx 14rpx; border-bottom: 1rpx solid rgba(148,163,184,.09); }
.oj-source,.oj-console { margin: 0; padding: 16rpx; color: #c9ced9; font: 19rpx/1.65 "SFMono-Regular",Consolas,"Liberation Mono",monospace; white-space: pre-wrap; word-break: break-word; overflow-x: auto; background: #0d0e16; }
.oj-console { color: #fda4af; border-left: 2rpx solid rgba(251,113,133,.55); }.solution-section { border-color: rgba(139,92,246,.22); }.solution-text { display: block; padding: 14rpx; border-bottom: 1rpx solid rgba(148,163,184,.08); }

@media (max-width: 900px) {
  .analysis-row {
    grid-template-columns: 1fr;
  }
}
</style>
