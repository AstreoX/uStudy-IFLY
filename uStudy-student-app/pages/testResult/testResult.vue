<template>
  <view class="test-result-page" :class="pageThemeClass">
    <!-- Background -->
    <view class="page-bg">
      <view class="bg-mesh"></view>
      <view class="bg-glow bg-glow-blue"></view>
      <view class="bg-glow bg-glow-violet"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-back" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <view class="nav-copy">
        <text class="nav-title">{{ navTitle }}</text>
        <text class="nav-subtitle">{{ navSubtitle }}</text>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <!-- Loading -->
    <view v-if="loading" class="state-container">
      <text class="state-text">正在加载评估结果...</text>
    </view>

    <!-- Content -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="content-body">

        <!-- Score Section -->
        <view class="score-section">
          <view class="score-ring-container">
            <!-- #ifdef APP-PLUS -->
            <canvas
              canvas-id="scoreRingCanvas"
              class="score-ring-canvas"
              :style="{ width: ringCanvasSizePx + 'px', height: ringCanvasSizePx + 'px' }"
            ></canvas>
            <!-- #endif -->
            <!-- #ifndef APP-PLUS -->
            <svg class="score-ring" viewBox="0 0 120 120">
              <circle
                cx="60" cy="60" r="52"
                fill="none"
                :stroke="trackColor"
                stroke-width="8"
              />
              <circle
                cx="60" cy="60" r="52"
                fill="none"
                :stroke="ringColor"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="circumference"
                :stroke-dashoffset="progressOffset"
                transform="rotate(-90 60 60)"
              />
            </svg>
            <!-- #endif -->
            <view class="score-content">
              <image class="trophy-icon" src="/static/icons/phosphor-icons/SVGs/fill/trophy-fill.svg" mode="aspectFit"></image>
              <view class="score-number-row">
                <text class="score-number">{{ scorePercent }}</text>
                <text class="score-unit">分</text>
              </view>
              <text class="score-detail">正确 {{ correctCount }}/{{ questionResults.length }} 题</text>
            </view>
          </view>
        </view>

        <!-- Analysis Cards Row -->
        <view class="analysis-row">
          <!-- Strengths Card -->
          <view class="analysis-card strength-card">
            <view class="card-header">
              <image class="card-icon" src="/static/icons/lucide/thumbs-up.svg" mode="aspectFit"></image>
              <text class="card-label strength-label">优势</text>
            </view>
            <view class="card-body">
              <view v-for="(item, index) in strengths" :key="'s-' + index" class="analysis-item">
                <text class="bullet">•</text>
                <text class="item-text">{{ item }}</text>
              </view>
            </view>
          </view>

          <!-- Weaknesses Card -->
          <view class="analysis-card weakness-card">
            <view class="card-header">
              <image class="card-icon" src="/static/icons/lucide/thumbs-down.svg" mode="aspectFit"></image>
              <text class="card-label weakness-label">待改进</text>
            </view>
            <view class="card-body">
              <view v-for="(item, index) in weaknesses" :key="'w-' + index" class="analysis-item">
                <text class="bullet">•</text>
                <text class="item-text">{{ item }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Suggestion Card -->
        <view class="suggestion-card">
          <view class="card-header">
            <image class="card-icon suggestion-icon" src="/static/icons/phosphor-icons/SVGs/regular/lightbulb.svg" mode="aspectFit"></image>
            <text class="card-label suggestion-label">提升建议</text>
          </view>
          <view class="card-body">
            <view v-for="(item, index) in suggestions" :key="'sg-' + index" class="suggestion-item">
              <text class="item-text">{{ item }}</text>
            </view>
          </view>
        </view>

        <!-- Questions Section -->
        <view class="questions-section">
          <text class="section-caption">答题详情</text>

          <view
            v-for="(item, index) in questionResults"
            :key="'q-' + item.id"
            class="question-card"
            :class="{ 'question-card-expanded': item.expanded }"
            @click="toggleQuestionExpand(index)"
          >
            <view class="question-main">
              <!-- Score Badge -->
              <view class="q-score-badge" :class="questionStatusClass(item)">
                <text class="q-score-badge-text">{{ item.score }}</text>
              </view>

              <!-- Question Info -->
              <view class="question-info">
                <text class="question-title">{{ item.order }}. {{ item.title }}</text>
              </view>

              <!-- Status Icon -->
              <view class="question-status">
                <image
                  v-if="item.status === 'correct'"
                  class="status-icon"
                  src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg"
                  mode="aspectFit"
                ></image>
                <image
                  v-else-if="item.status === 'wrong'"
                  class="status-icon status-icon-wrong"
                  src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
                  mode="aspectFit"
                ></image>
                <image
                  v-else-if="item.status === 'partial'"
                  class="status-icon status-icon-partial"
                  src="/static/icons/phosphor-icons/SVGs/fill/warning-circle-fill.svg"
                  mode="aspectFit"
                ></image>
              </view>
            </view>

            <!-- Expanded Content -->
            <view v-if="item.expanded" class="question-expand">
              <!-- Question & Options -->
              <view class="expand-section question-content-box">
                <view v-if="item.options && item.options.length" class="options-list">
                  <view
                    v-for="(opt, optIndex) in item.options"
                    :key="optIndex"
                    class="option-item"
                    :class="optionHighlightClass(item, optIndex)"
                  >
                    <text class="option-label">{{ getOptionLabel(optIndex) }}</text>
                    <text class="option-text">{{ opt }}</text>
                    <text v-if="isUserAnswerOption(item, optIndex)" class="option-tag">你的答案</text>
                  </view>
                </view>
              </view>

              <!-- Answers Row (non-short-answer) -->
              <view v-if="item.questionType !== 'short_answer'" class="expand-section answers-row">
                <view class="answer-item">
                  <text class="expand-label">你的答案</text>
                  <text class="expand-value user-answer">{{ item.userAnswerDisplay || '（未作答）' }}</text>
                </view>
                <view class="answer-item">
                  <text class="expand-label">标准答案</text>
                  <text class="expand-value correct-answer">{{ item.correctAnswerDisplay }}</text>
                </view>
              </view>

              <!-- Short answer answers -->
              <template v-else>
                <view class="expand-section">
                  <text class="expand-label">你的答案</text>
                  <text class="expand-value user-answer">{{ item.userAnswerDisplay || '（未作答）' }}</text>
                </view>
                <view class="expand-section">
                  <text class="expand-label">标准答案</text>
                  <text class="expand-value correct-answer">{{ item.correctAnswerDisplay }}</text>
                </view>
              </template>

              <!-- AI Evaluation (short answer only) -->
              <view v-if="item.questionType === 'short_answer' && item.aiEvaluation" class="expand-section ai-evaluation">
                <text class="expand-label">AI 评语</text>
                <rich-text class="expand-value ai-text" :nodes="parseMarkdown(item.aiEvaluation)"></rich-text>
              </view>

              <!-- Collapse Hint -->
              <view class="expand-hint">
                <image
                  class="expand-icon"
                  src="/static/icons/phosphor-icons/SVGs/regular/caret-up.svg"
                  mode="aspectFit"
                ></image>
              </view>
            </view>
          </view>
        </view>

      </view>
    </scroll-view>
  </view>
</template>

<script>
import { getQuizAttempt } from '@/api/space'
import { getQuizEvaluationResult, removeQuizEvaluationResult } from '@/utils/storage'
import { clearPendingNavigationIfMatches } from '@/utils/deepLink'
import { goBack as safeGoBack } from '@/utils/navigation'
import homeThemePageMixin from '@/mixins/homeThemePageMixin'

export default {
  mixins: [homeThemePageMixin],
  data() {
    return {
      quizId: null,
      quizTitle: '',
      fromList: false,
      score: 0,
      totalScore: 0,
      circumference: 326.7,
      strengths: [],
      weaknesses: [],
      suggestions: [],
      questionResults: [],
      loading: true,
      scoreRingDrawTimer: null
    }
  },

  computed: {
    ringCanvasSizePx() {
      return uni.upx2px(320)
    },
    scorePercent() {
      if (this.totalScore <= 0) return 0
      const pct = Math.round(this.score / this.totalScore * 100)
      return Number.isNaN(pct) ? 0 : Math.max(0, Math.min(100, pct))
    },
    progressPercent() {
      if (this.totalScore <= 0) return 0
      const percent = this.score / this.totalScore
      if (Number.isNaN(percent)) return 0
      return Math.max(0, Math.min(1, percent))
    },
    progressOffset() {
      return this.circumference * (1 - this.progressPercent)
    },
    ringColor() {
      const pct = this.scorePercent
      if (pct >= 80) return '#F5A623'
      if (pct >= 60) return '#3b82f6'
      if (pct >= 40) return '#f59e0b'
      return '#ef4444'
    },
    trackColor() {
      return this.isLightTheme ? 'rgba(63, 53, 42, 0.12)' : 'rgba(255, 255, 255, 0.08)'
    },
    correctCount() {
      return this.questionResults.filter(q => q.status === 'correct').length
    },
    navTitle() {
      return this.quizTitle || '测试结果'
    },
    navSubtitle() {
      if (this.loading) return ''
      return `${this.questionResults.length} 道题 · 正确 ${this.correctCount} 题`
    }
  },

  watch: {
    loading(val) {
      if (!val) {
        this.scheduleDrawScoreRing()
      }
    },
    score() {
      if (!this.loading) {
        this.scheduleDrawScoreRing()
      }
    },
    totalScore() {
      if (!this.loading) {
        this.scheduleDrawScoreRing()
      }
    }
  },

  onLoad(options) {
    this.restoreThemeMode({ darkStatusBarBackground: '#1D1E20' })
    if (options.quizId) {
      this.quizId = options.quizId
      clearPendingNavigationIfMatches(`/pages/testResult/testResult?quizId=${encodeURIComponent(options.quizId)}&fromList=true`)
    }
    if (options.quizTitle) {
      this.quizTitle = decodeURIComponent(options.quizTitle)
    }
    this.fromList = options.fromList === 'true'
    this.loadEvaluationResult()
  },

  onReady() {
    if (!this.loading) {
      this.scheduleDrawScoreRing()
    }
  },

  onShow() {
    this.restoreThemeMode({ darkStatusBarBackground: '#1D1E20' })
    if (!this.loading) {
      this.scheduleDrawScoreRing()
    }
  },

  onHide() {
    if (this.scoreRingDrawTimer) {
      clearTimeout(this.scoreRingDrawTimer)
      this.scoreRingDrawTimer = null
    }
  },

  onUnload() {
    if (this.scoreRingDrawTimer) {
      clearTimeout(this.scoreRingDrawTimer)
      this.scoreRingDrawTimer = null
    }
  },

  methods: {
    async loadEvaluationResult() {
      try {
        if (this.fromList && this.quizId) {
          await this.loadFromApi()
          return
        }

        const result = getQuizEvaluationResult()

        if (result) {
          this.populateResult(result)
          removeQuizEvaluationResult()
        } else {
          this.loadMockData()
        }

        this.loading = false
      } catch (error) {
        this.loadMockData()
        this.loading = false
      }
    },

    async loadFromApi() {
      try {
        const result = await getQuizAttempt(this.quizId)
        this.populateResult(result)
        this.loading = false
      } catch (error) {
        uni.showToast({
          title: error.message || '加载失败',
          icon: 'none'
        })
        this.loadMockData()
        this.loading = false
      }
    },

    populateResult(result) {
      this.score = result.score || 0
      this.totalScore = result.total_score || 0
      this.strengths = result.strengths || []
      this.weaknesses = result.weaknesses || []
      this.suggestions = result.suggestions || []
      if (result.quiz_title) {
        this.quizTitle = result.quiz_title
      }
      this.questionResults = (result.question_results || []).map(qr => ({
        id: qr.id,
        order: qr.order,
        questionType: qr.question_type,
        title: qr.title,
        options: qr.options,
        status: qr.status,
        score: qr.score,
        maxScore: qr.max_score,
        userAnswer: qr.user_answer,
        correctAnswer: qr.correct_answer,
        aiEvaluation: qr.ai_evaluation,
        expanded: false,
        userAnswerDisplay: this.formatAnswer(qr.question_type, qr.user_answer),
        correctAnswerDisplay: this.formatAnswer(qr.question_type, qr.correct_answer)
      }))
    },

    loadMockData() {
      this.quizTitle = '监督学习基础测验'
      this.score = 85
      this.totalScore = 100
      this.strengths = [
        '基础数据类型掌握扎实',
        'CSS 选择器理解准确',
        '判断题答题正确率高'
      ]
      this.weaknesses = [
        'HTML 标记语言概念模糊',
        '响应式设计理解不够深入'
      ]
      this.suggestions = [
        '建议复习 HTML 的定义和与编程语言的区别',
        '深入学习响应式设计的核心概念',
        '多做实践练习，加深对 CSS 布局的理解'
      ]
      this.questionResults = [
        { id: '1', order: 1, questionType: 'single_choice', title: '以下哪个是 JavaScript 的基本数据类型？', status: 'correct', score: 2, maxScore: 2, expanded: false },
        { id: '2', order: 2, questionType: 'multiple_choice', title: '以下哪些是 CSS 选择器？', status: 'partial', score: 2, maxScore: 4, expanded: false },
        { id: '3', order: 3, questionType: 'true_false', title: 'HTML 是一种编程语言。', status: 'wrong', score: 0, maxScore: 2, expanded: false },
        { id: '4', order: 4, questionType: 'short_answer', title: '简述什么是响应式设计？', status: 'partial', score: 7, maxScore: 10, aiEvaluation: '答案基本正确，涵盖了响应式设计的核心概念，但对媒体查询的描述不够详细。', expanded: false, userAnswerDisplay: '响应式设计是一种网页设计方法，可以让网页在不同设备上都能良好显示。', correctAnswerDisplay: '响应式设计是一种网页设计方法，通过使用弹性布局、媒体查询等技术，使网页能够自动适应不同尺寸的屏幕。' }
      ]
    },

    getOptionLabel(index) {
      return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][index] || String(index + 1)
    },

    formatAnswer(questionType, answer) {
      if (!answer) return '（未作答）'

      if (questionType === 'single_choice') {
        const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        const index = answer.index
        return index !== undefined && index < labels.length ? labels[index] : String(index)
      }

      if (questionType === 'multiple_choice') {
        const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        const indices = answer.indices || []
        return indices.map(i => labels[i] || String(i)).join('、') || '（未选择）'
      }

      if (questionType === 'true_false') {
        return answer.value === true ? '正确' : answer.value === false ? '错误' : '（未作答）'
      }

      if (questionType === 'short_answer') {
        return answer.text || answer.reference || '（未作答）'
      }

      return JSON.stringify(answer)
    },

    questionStatusClass(item) {
      if (item.status === 'correct') return 'q-badge-correct'
      if (item.status === 'wrong') return 'q-badge-wrong'
      return 'q-badge-partial'
    },

    optionHighlightClass(item, optIndex) {
      const isCorrect = this.isCorrectOption(item, optIndex)
      const isUser = this.isUserAnswerOption(item, optIndex)
      if (isCorrect && isUser) return 'option-correct'
      if (isCorrect) return 'option-correct'
      if (isUser && !isCorrect) return 'option-wrong'
      return ''
    },

    isCorrectOption(item, optIndex) {
      if (!item.correctAnswer) return false
      if (item.questionType === 'single_choice') {
        return item.correctAnswer.index === optIndex
      }
      if (item.questionType === 'multiple_choice') {
        return (item.correctAnswer.indices || []).includes(optIndex)
      }
      return false
    },

    isUserAnswerOption(item, optIndex) {
      if (!item.userAnswer) return false
      if (item.questionType === 'single_choice') {
        return item.userAnswer.index === optIndex
      }
      if (item.questionType === 'multiple_choice') {
        return (item.userAnswer.indices || []).includes(optIndex)
      }
      return false
    },

    toggleQuestionExpand(index) {
      this.questionResults = this.questionResults.map((q, i) => {
        if (i === index) {
          return { ...q, expanded: !q.expanded }
        }
        return q
      })
    },

    parseMarkdown(text) {
      if (!text) return ''
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, `<strong style="color:${this.isLightTheme ? '#2F6EEA' : 'rgba(139,92,246,1)'};font-weight:600;">$1</strong>`)
        .replace(/\*([^*]+)\*/g, '<em style="font-style:italic;">$1</em>')
        .replace(/`([^`]+)`/g, `<code style="background:${this.isLightTheme ? 'rgba(47,110,234,0.12)' : 'rgba(139,92,246,0.2)'};padding:2px 6px;border-radius:4px;color:${this.isLightTheme ? '#1F1A16' : '#FFFFFF'};">$1</code>`)
        .replace(/\n/g, '<br/>')
    },

    scheduleDrawScoreRing() {
      // #ifdef APP-PLUS
      this.$nextTick(() => {
        if (this.loading) return
        if (this.scoreRingDrawTimer) {
          clearTimeout(this.scoreRingDrawTimer)
        }
        this.scoreRingDrawTimer = setTimeout(() => {
          this.drawScoreRingCanvas()
          this.scoreRingDrawTimer = null
        }, 16)
      })
      // #endif
    },

    drawScoreRingCanvas() {
      // #ifdef APP-PLUS
      const size = this.ringCanvasSizePx
      const lineWidth = uni.upx2px(21)
      const center = size / 2
      const radius = Math.max(0, center - lineWidth / 2)
      const startAngle = -Math.PI / 2
      const endAngle = startAngle + Math.PI * 2 * this.progressPercent

      const ctx = uni.createCanvasContext('scoreRingCanvas', this)
      ctx.clearRect(0, 0, size, size)

      // Background track
      ctx.setStrokeStyle(this.trackColor)
      ctx.setLineWidth(lineWidth)
      ctx.setLineCap('round')
      ctx.beginPath()
      ctx.arc(center, center, radius, 0, Math.PI * 2, false)
      ctx.stroke()

      // Progress arc
      if (this.progressPercent > 0) {
        ctx.setStrokeStyle(this.ringColor)
        ctx.beginPath()
        ctx.arc(center, center, radius, startAngle, endAngle, false)
        ctx.stroke()
      }

      ctx.draw()
      // #endif
    },

    goBack() {
      safeGoBack({
        fallbackUrl: '/pages/index/index'
      })
    }
  }
}
</script>

<style>
.test-result-page {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: rgb(29, 30, 32);
  overflow-x: hidden;
}

/* ========== Background ========== */
.page-bg {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  pointer-events: none;
}

.bg-mesh {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background:
    radial-gradient(circle at 82% 14%, rgba(74, 108, 247, 0.07) 0%, rgba(74, 108, 247, 0) 32%),
    radial-gradient(circle at 12% 100%, rgba(99, 102, 241, 0.04) 0%, rgba(99, 102, 241, 0) 36%);
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(130rpx);
  opacity: 0.2;
}

.bg-glow-blue {
  top: 120rpx;
  right: -90rpx;
  width: 320rpx;
  height: 320rpx;
  background: rgba(74, 108, 247, 0.10);
}

.bg-glow-violet {
  bottom: 180rpx;
  left: -90rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(123, 97, 255, 0.07);
}

/* ========== Navigation Bar ========== */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: calc(100vh * 0.5 / 26);
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
    rgba(29, 30, 32, 0.56) 0%,
    rgba(29, 30, 32, 0.4) 50%,
    rgba(29, 30, 32, 0) 100%
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
      rgba(29, 30, 32, 0.82) 0%,
      rgba(29, 30, 32, 0.66) 50%,
      rgba(29, 30, 32, 0) 100%
    );
  }
}

.nav-back {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-back {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-back:active {
  background: rgba(255, 255, 255, 0.10);
}

.nav-spacer {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
}

.nav-copy {
  flex: 1;
  min-width: 0;
  margin-left: 16rpx;
  margin-right: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 4rpx;
}

.test-result-page .nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.nav-subtitle {
  max-width: 100%;
  font-size: 22rpx;
  line-height: 1.25;
  color: rgba(248, 248, 248, 0.52);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== States ========== */
.state-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
}

.state-text {
  font-size: 28rpx;
  color: #7C8598;
}

/* ========== Content Scroll ========== */
.content-scroll {
  flex: 1;
  padding-top: calc(100vh * 1.5 / 26 + 100rpx);
  box-sizing: border-box;
}

.content-body {
  padding: 0 calc(100vw / 24) 80rpx;
}

/* ========== Score Section ========== */
.score-section {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32rpx 0 40rpx;
}

.score-ring-container {
  position: relative;
  width: 320rpx;
  height: 320rpx;
  display: flex;
  justify-content: center;
  align-items: center;
}

.score-ring {
  position: absolute;
  width: 100%;
  height: 100%;
}

.score-ring-canvas {
  position: absolute;
  width: 100%;
  height: 100%;
}

.score-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
}

.trophy-icon {
  width: 64rpx;
  height: 64rpx;
  filter: brightness(0) saturate(100%) invert(74%) sepia(46%) saturate(959%) hue-rotate(354deg) brightness(101%) contrast(96%);
}

.score-number-row {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.score-number {
  font-size: 56rpx;
  font-weight: 700;
  color: rgb(248, 248, 248);
  line-height: 1;
}

.score-unit {
  font-size: 28rpx;
  font-weight: 500;
  color: rgba(248, 248, 248, 0.6);
}

.score-detail {
  font-size: 24rpx;
  color: #7C8598;
  margin-top: 4rpx;
}

/* ========== Analysis Cards Row ========== */
.analysis-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.analysis-card {
  flex: 1;
  border-radius: 28rpx;
  padding: 24rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.strength-card {
  border-color: rgba(74, 222, 128, 0.25);
}

.weakness-card {
  border-color: rgba(251, 191, 36, 0.25);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 16rpx;
}

.card-icon {
  width: 32rpx;
  height: 32rpx;
}

.strength-card .card-icon {
  filter: brightness(0) saturate(100%) invert(70%) sepia(52%) saturate(396%) hue-rotate(85deg) brightness(94%) contrast(88%);
}

.weakness-card .card-icon {
  filter: brightness(0) saturate(100%) invert(76%) sepia(60%) saturate(608%) hue-rotate(348deg) brightness(100%) contrast(97%);
}

.card-label {
  font-size: 26rpx;
  font-weight: 600;
}

.strength-label {
  color: rgba(74, 222, 128, 0.9);
}

.weakness-label {
  color: rgba(251, 191, 36, 0.9);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.analysis-item {
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
}

.bullet {
  font-size: 22rpx;
  color: #7C8598;
  line-height: 1.6;
}

.item-text {
  flex: 1;
  font-size: 22rpx;
  color: rgba(248, 248, 248, 0.72);
  line-height: 1.6;
}

/* ========== Suggestion Card ========== */
.suggestion-card {
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 28rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(99, 102, 241, 0.25);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.suggestion-icon {
  filter: brightness(0) saturate(100%) invert(52%) sepia(72%) saturate(2236%) hue-rotate(218deg) brightness(97%) contrast(95%) !important;
}

.suggestion-label {
  color: rgba(99, 102, 241, 0.9);
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
  padding-left: 4rpx;
}

/* ========== Questions Section ========== */
.questions-section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.section-caption {
  font-size: 26rpx;
  font-weight: 600;
  color: #7C8598;
  margin-bottom: 4rpx;
}

.question-card {
  display: flex;
  flex-direction: column;
  padding: 24rpx 28rpx;
  border-radius: 36rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.question-card-expanded {
  background: rgb(38, 38, 38);
}

.question-main {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

/* Question Score Badge */
.q-score-badge {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
}

.q-badge-correct {
  background: rgba(74, 222, 128, 0.12);
  border: 2rpx solid rgba(74, 222, 128, 0.3);
}

.q-badge-wrong {
  background: rgba(239, 68, 68, 0.12);
  border: 2rpx solid rgba(239, 68, 68, 0.3);
}

.q-badge-partial {
  background: rgba(251, 191, 36, 0.12);
  border: 2rpx solid rgba(251, 191, 36, 0.3);
}

.q-score-badge-text {
  font-size: 28rpx;
  font-weight: 700;
}

.q-badge-correct .q-score-badge-text {
  color: rgba(74, 222, 128, 0.9);
}

.q-badge-wrong .q-score-badge-text {
  color: rgba(239, 68, 68, 0.9);
}

.q-badge-partial .q-score-badge-text {
  color: rgba(251, 191, 36, 0.9);
}

.question-info {
  flex: 1;
  min-width: 0;
}

.question-title {
  font-size: 26rpx;
  color: rgb(248, 248, 248);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.question-status {
  flex-shrink: 0;
}

.status-icon {
  width: 40rpx;
  height: 40rpx;
  filter: brightness(0) saturate(100%) invert(70%) sepia(52%) saturate(396%) hue-rotate(85deg) brightness(94%) contrast(88%);
}

.status-icon-wrong {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
}

.status-icon-partial {
  filter: brightness(0) saturate(100%) invert(76%) sepia(60%) saturate(608%) hue-rotate(348deg) brightness(100%) contrast(97%);
}

/* ========== Expanded Content ========== */
.question-expand {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.expand-section {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.question-content-box {
  background: rgb(41, 41, 41);
  padding: 16rpx 20rpx;
  border-radius: 20rpx;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.03);
}

.option-correct {
  background: rgba(74, 222, 128, 0.08);
  border: 1rpx solid rgba(74, 222, 128, 0.2);
}

.option-wrong {
  background: rgba(239, 68, 68, 0.08);
  border: 1rpx solid rgba(239, 68, 68, 0.2);
}

.option-label {
  width: 40rpx;
  height: 40rpx;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 24rpx;
  font-weight: 600;
  color: #7C8598;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 50%;
}

.option-correct .option-label {
  color: rgba(74, 222, 128, 0.9);
  background: rgba(74, 222, 128, 0.15);
}

.option-wrong .option-label {
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.15);
}

.option-text {
  flex: 1;
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.8);
  line-height: 1.5;
}

.option-tag {
  font-size: 20rpx;
  color: rgba(74, 222, 128, 0.9);
  background: rgba(74, 222, 128, 0.1);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  flex-shrink: 0;
}

.option-wrong .option-tag {
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.1);
}

.answers-row {
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-start;
}

.answer-item {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 8rpx;
}

.expand-label {
  font-size: 22rpx;
  color: #7C8598;
  font-weight: 500;
}

.expand-value {
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.8);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.expand-value.user-answer {
  color: rgba(99, 102, 241, 0.9);
}

.expand-value.correct-answer {
  color: rgba(74, 222, 128, 0.9);
}

.ai-evaluation {
  background: rgba(139, 92, 246, 0.08);
  padding: 16rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(139, 92, 246, 0.2);
}

.ai-text {
  color: rgba(139, 92, 246, 0.9);
}

.expand-hint {
  display: flex;
  justify-content: center;
  margin-top: 8rpx;
}

.expand-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
}
</style>
