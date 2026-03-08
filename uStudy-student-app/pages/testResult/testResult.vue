<template>
  <view class="test-result-page">
    <!-- 顶部导航栏 -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">测试结果</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- 加载状态 -->
    <view v-if="loading" class="loading-container">
      <text class="loading-text">正在加载评估结果...</text>
    </view>

    <!-- 主内容区域 -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <!-- 圆环进度和分数 -->
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
            <!-- 背景轨道 -->
            <circle
              cx="60"
              cy="60"
              r="52"
              fill="none"
              stroke="rgba(255, 255, 255, 0.1)"
              stroke-width="8"
            />
            <!-- 进度圆弧 -->
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
          <!-- #endif -->
          <view class="score-content">
            <image class="trophy-icon" src="/static/icons/phosphor-icons/SVGs/fill/trophy-fill.svg" mode="aspectFit"></image>
            <text class="score-text">{{ score }}/{{ totalScore }}分</text>
          </view>
        </view>
      </view>

      <!-- 优点和缺点卡片 -->
      <view class="analysis-row">
        <!-- 优点卡片 -->
        <view class="analysis-card strength-card">
          <view class="card-header">
            <image class="card-icon" src="/static/icons/phosphor-icons/SVGs/regular/thumbs-up.svg" mode="aspectFit"></image>
            <text class="card-title">优点分析</text>
          </view>
          <view class="card-content">
            <view v-for="(item, index) in strengths" :key="'s-' + index" class="analysis-item">
              <text class="bullet">•</text>
              <text class="item-text">{{ item }}</text>
            </view>
          </view>
        </view>

        <!-- 缺点卡片 -->
        <view class="analysis-card weakness-card">
          <view class="card-header">
            <image class="card-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
            <text class="card-title">缺点分析</text>
          </view>
          <view class="card-content">
            <view v-for="(item, index) in weaknesses" :key="'w-' + index" class="analysis-item">
              <text class="bullet">•</text>
              <text class="item-text">{{ item }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 提升建议卡片 -->
      <view class="suggestion-card">
        <view class="card-header">
          <image class="card-icon suggestion-icon" src="/static/icons/phosphor-icons/SVGs/regular/lightbulb.svg" mode="aspectFit"></image>
          <text class="card-title">提升建议</text>
        </view>
        <view class="card-content">
          <view v-for="(item, index) in suggestions" :key="'sg-' + index" class="suggestion-item">
            <text class="suggestion-number">{{ index + 1 }}.</text>
            <text class="item-text">{{ item }}</text>
          </view>
        </view>
      </view>

      <!-- 逐题评估卡片 -->
      <view class="questions-card">
        <view class="card-header">
          <text class="card-title">逐题评估</text>
        </view>
        <view class="questions-list">
          <view
            v-for="(item, index) in questionResults"
            :key="'q-' + item.id"
            class="question-item question-item-expandable"
            :class="{ 'question-item-expanded': item.expanded }"
            @click="toggleQuestionExpand(index)"
          >
            <view class="question-main">
              <view class="question-info">
                <text class="question-label">Q{{ item.order }}:</text>
                <text class="question-title">{{ item.title }}</text>
              </view>
              <view class="question-right">
                <text class="question-score">{{ item.score }}/{{ item.maxScore }}</text>
                <view class="question-status">
                  <image
                    v-if="item.status === 'correct'"
                    class="status-icon correct"
                    src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg"
                    mode="aspectFit"
                  ></image>
                  <image
                    v-else-if="item.status === 'wrong'"
                    class="status-icon incorrect"
                    src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
                    mode="aspectFit"
                  ></image>
                  <image
                    v-else-if="item.status === 'partial'"
                    class="status-icon partial"
                    src="/static/icons/phosphor-icons/SVGs/fill/warning-circle-fill.svg"
                    mode="aspectFit"
                  ></image>
                </view>
              </view>
            </view>
            <!-- 展开内容 - 所有题型都可展开 -->
            <view v-if="item.expanded" class="question-expand">
              <!-- 题干和选项 -->
              <view class="expand-section question-content-section">
                <text class="expand-text question-title">{{ item.title }}</text>
                <view v-if="item.options && item.options.length" class="options-list">
                  <view v-for="(opt, optIndex) in item.options" :key="optIndex" class="option-item">
                    <text class="option-label">{{ getOptionLabel(optIndex) }}.</text>
                    <text class="option-text">{{ opt }}</text>
                  </view>
                </view>
              </view>
              <!-- 你的答案 & 标准答案 - 非简答题一行左右分布 -->
              <view v-if="item.questionType !== 'short_answer'" class="expand-section answers-row">
                <view class="answer-item">
                  <text class="expand-label">你的答案：</text>
                  <text class="expand-text user-answer">{{ item.userAnswerDisplay || '（未作答）' }}</text>
                </view>
                <view class="answer-item">
                  <text class="expand-label">标准答案：</text>
                  <text class="expand-text correct-answer">{{ item.correctAnswerDisplay }}</text>
                </view>
              </view>
              <!-- 简答题答案 - 上下排布 -->
              <template v-else>
                <view class="expand-section">
                  <text class="expand-label">你的答案：</text>
                  <text class="expand-text user-answer">{{ item.userAnswerDisplay || '（未作答）' }}</text>
                </view>
                <view class="expand-section">
                  <text class="expand-label">标准答案：</text>
                  <text class="expand-text correct-answer">{{ item.correctAnswerDisplay }}</text>
                </view>
              </template>
              <!-- AI 评语 - 仅简答题显示 -->
              <view v-if="item.questionType === 'short_answer' && item.aiEvaluation" class="expand-section ai-evaluation">
                <text class="expand-label">AI 评语：</text>
                <rich-text class="expand-text ai-text" :nodes="parseMarkdown(item.aiEvaluation)"></rich-text>
              </view>
            </view>
            <!-- 收起按钮 - 仅展开时显示 -->
            <view v-if="item.expanded" class="expand-hint">
              <image
                class="expand-icon expand-icon-rotated"
                src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
                mode="aspectFit"
              ></image>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

  </view>
</template>

<script>
import { getQuizAttempt } from '@/api/space'

export default {
  data() {
    return {
      quizId: null,
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
    progressPercent() {
      if (this.totalScore <= 0) return 0
      const percent = this.score / this.totalScore
      if (Number.isNaN(percent)) return 0
      return Math.max(0, Math.min(1, percent))
    },
    progressOffset() {
      return this.circumference * (1 - this.progressPercent)
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
    if (options.quizId) {
      this.quizId = options.quizId
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
    /**
     * 加载评估结果
     */
    async loadEvaluationResult() {
      try {
        if (this.fromList && this.quizId) {
          await this.loadFromApi()
          return
        }

        // 从全局缓存读取评估结果
        const result = uni.getStorageSync('quizEvaluationResult')

        if (result) {
          this.populateResult(result)
          // 清除缓存
          uni.removeStorageSync('quizEvaluationResult')
        } else {
          // 没有数据，使用默认模拟数据
          this.loadMockData()
        }

        this.loading = false
      } catch (error) {
        this.loadMockData()
        this.loading = false
      }
    },

    /**
     * 从 API 加载作答记录
     */
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

    /**
     * 填充评估结果数据
     */
    populateResult(result) {
      this.score = result.score || 0
      this.totalScore = result.total_score || 0
      this.strengths = result.strengths || []
      this.weaknesses = result.weaknesses || []
      this.suggestions = result.suggestions || []
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

    /**
     * 加载模拟数据（用于开发测试）
     */
    loadMockData() {
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

    /**
     * 获取选项标签（A、B、C、D...）
     */
    getOptionLabel(index) {
      return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'][index] || String(index + 1)
    },

    /**
     * 格式化答案显示
     */
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

    /**
     * 切换题目展开状态（所有题型都可展开）
     */
    toggleQuestionExpand(index) {
      this.questionResults = this.questionResults.map((q, i) => {
        if (i === index) {
          return { ...q, expanded: !q.expanded }
        }
        return q
      })
    },

    /**
     * 解析简单的 Markdown 格式
     */
    parseMarkdown(text) {
      if (!text) return ''
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, '<strong style="color:rgba(139,92,246,1);font-weight:600;">$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em style="font-style:italic;">$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(139,92,246,0.2);padding:2px 6px;border-radius:4px;">$1</code>')
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

      // 背景轨道
      ctx.setStrokeStyle('rgba(255, 255, 255, 0.1)')
      ctx.setLineWidth(lineWidth)
      ctx.setLineCap('round')
      ctx.beginPath()
      ctx.arc(center, center, radius, 0, Math.PI * 2, false)
      ctx.stroke()

      // 进度圆弧
      if (this.progressPercent > 0) {
        ctx.setStrokeStyle('#0088FF')
        ctx.beginPath()
        ctx.arc(center, center, radius, startAngle, endAngle, false)
        ctx.stroke()
      }

      ctx.draw()
      // #endif
    },

    goBack() {
      uni.navigateBack({
        delta: 1
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
  background-color: #0A0A0A;
  overflow-x: hidden;
}

/* ========== 加载状态 ========== */
.loading-container {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 88rpx);
}

.loading-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.6);
}

/* ========== 导航栏 ========== */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

/* 磨砂玻璃背景层 - 渐变过渡 */
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

/* 不支持 backdrop-filter 的降级方案 */
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

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
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

/* ========== 内容滚动区域 ========== */
.content-scroll {
  flex: 1;
  padding: calc(100vh * 1.5 / 26 + 100rpx) calc(100vw / 24) 60rpx;
  box-sizing: border-box;
}

/* ========== 分数区域 ========== */
.score-section {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40rpx 0 48rpx;
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
  gap: 12rpx;
}

.trophy-icon {
  width: 80rpx;
  height: 80rpx;
  filter: brightness(0) saturate(100%) invert(74%) sepia(46%) saturate(959%) hue-rotate(354deg) brightness(101%) contrast(96%);
}

.score-text {
  font-size: 40rpx;
  font-weight: 700;
  color: #ffffff;
}

/* ========== 分析卡片行 ========== */
.analysis-row {
  display: flex;
  gap: 20rpx;
  margin-bottom: 24rpx;
}

.analysis-card {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 24rpx;
  padding: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border: 2rpx solid;
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
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.card-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
}

.strength-card .card-icon {
  filter: brightness(0) saturate(100%) invert(85%) sepia(25%) saturate(556%) hue-rotate(85deg) brightness(96%) contrast(92%);
}

.weakness-card .card-icon {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
}

.card-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #ffffff;
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.analysis-item {
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
}

.bullet {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.6;
}

.item-text {
  flex: 1;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.6;
}

/* ========== 建议卡片 ========== */
.suggestion-card {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border: 2rpx solid rgba(245, 158, 11, 0.4);
}

.suggestion-icon {
  filter: brightness(0) saturate(100%) invert(69%) sepia(67%) saturate(634%) hue-rotate(356deg) brightness(102%) contrast(93%) !important;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
}

.suggestion-number {
  font-size: 24rpx;
  color: rgba(245, 158, 11, 0.9);
  font-weight: 500;
  line-height: 1.6;
}

/* ========== 逐题评估卡片 ========== */
.questions-card {
  background: rgba(255, 255, 255, 0.04);
  border-radius: 24rpx;
  padding: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.questions-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.question-item {
  display: flex;
  flex-direction: column;
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s ease;
}

.question-item-expandable {
  cursor: pointer;
}

.question-item-expanded {
  background: rgba(255, 255, 255, 0.06);
}

.question-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.question-info {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
  min-width: 0;
}

.question-label {
  font-size: 24rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  flex-shrink: 0;
}

.question-title {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-right {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex-shrink: 0;
  margin-left: 16rpx;
}

.question-score {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.question-status {
  flex-shrink: 0;
}

.status-icon {
  width: 40rpx;
  height: 40rpx;
}

.status-icon.correct {
  filter: brightness(0) saturate(100%) invert(85%) sepia(25%) saturate(556%) hue-rotate(85deg) brightness(96%) contrast(92%);
}

.status-icon.incorrect {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
}

.status-icon.partial {
  filter: brightness(0) saturate(100%) invert(69%) sepia(67%) saturate(634%) hue-rotate(356deg) brightness(102%) contrast(93%);
}

/* ========== 简答题展开内容 ========== */
.question-expand {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.expand-section {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
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
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
}

.expand-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.expand-text.user-answer {
  color: rgba(0, 136, 255, 0.9);
}

.expand-text.correct-answer {
  color: rgba(134, 239, 172, 0.9);
}

.question-content-section {
  background: rgba(255, 255, 255, 0.03);
  padding: 12rpx 16rpx;
  border-radius: 8rpx;
}

.question-content-section .question-title {
  display: block;
  margin-bottom: 12rpx;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 8rpx;
}

.option-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
  flex-shrink: 0;
}

.option-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
}

.ai-evaluation {
  background: rgba(139, 92, 246, 0.1);
  padding: 16rpx;
  border-radius: 12rpx;
  border: 1rpx solid rgba(139, 92, 246, 0.3);
}

.ai-text {
  color: rgba(139, 92, 246, 0.9);
}

/* ========== 展开提示 ========== */
.expand-hint {
  display: flex;
  justify-content: center;
  margin-top: 12rpx;
}

.expand-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
  transition: transform 0.3s ease;
}

.expand-icon-rotated {
  transform: rotate(180deg);
}


</style>
