<template>
  <view class="test-page">
    <!-- 顶部导航栏 -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">测试题</text>
      <view class="nav-right" :class="{ 'nav-right-active': canSubmit }" @click="handleSubmit">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/bold/arrow-up-bold.svg" mode="aspectFit"></image>
      </view>
    </view>

    <!-- 加载状态 -->
    <view v-if="isLoading" class="loading-container">
      <text class="loading-text">正在加载测试题...</text>
    </view>

    <!-- 加载失败 -->
    <view v-else-if="loadError" class="error-container">
      <text class="error-text">{{ loadError }}</text>
      <view class="retry-btn" @click="loadQuizData(quizId)">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- 正常内容 -->
    <template v-else>
      <!-- 答题进度条 -->
      <view class="progress-section">
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: progressPercent + '%' }"></view>
        </view>
        <text class="progress-text">{{ answeredCount }}/{{ questions.length }}</text>
      </view>

      <!-- 题目滚动区域 -->
      <scroll-view
      class="question-container"
      scroll-y
      @touchstart="handleTouchStart"
      @touchend="handleTouchEnd"
    >
      <!-- 动画包装器 -->
      <view
        class="question-card-wrapper"
        :class="slideAnimationClass"
      >
      <!-- 单选题 -->
      <view class="question-card" v-if="currentQuestion.type === 'single'">
        <view class="question-header">
          <view class="question-type-tag question-type-single">单选题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="options-list">
          <view
            v-for="(option, idx) in currentQuestion.options"
            :key="idx"
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === idx }"
            @click="selectSingleAnswer(idx)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === idx }">
              <view v-if="userAnswers[currentQuestion.id] === idx" class="radio-inner"></view>
            </view>
            <text class="option-text">{{ optionLabels[idx] }}. {{ option }}</text>
          </view>
        </view>
      </view>

      <!-- 多选题 -->
      <view class="question-card" v-else-if="currentQuestion.type === 'multiple'">
        <view class="question-header">
          <view class="question-type-tag question-type-multiple">多选题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="options-list">
          <view
            v-for="(option, idx) in currentQuestion.options"
            :key="idx"
            class="option-item"
            :class="{ 'option-item-selected': isMultipleSelected(idx) }"
            @click="toggleMultipleAnswer(idx)"
          >
            <view class="option-checkbox" :class="{ 'option-checkbox-checked': isMultipleSelected(idx) }">
              <image v-if="isMultipleSelected(idx)" class="checkbox-icon" src="/static/icons/phosphor-icons/SVGs/bold/check.svg" mode="aspectFit"></image>
            </view>
            <text class="option-text">{{ optionLabels[idx] }}. {{ option }}</text>
          </view>
        </view>
      </view>

      <!-- 判断题 -->
      <view class="question-card" v-else-if="currentQuestion.type === 'truefalse'">
        <view class="question-header">
          <view class="question-type-tag question-type-truefalse">判断题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="options-list">
          <view
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === true }"
            @click="selectTrueFalseAnswer(true)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === true }">
              <view v-if="userAnswers[currentQuestion.id] === true" class="radio-inner"></view>
            </view>
            <text class="option-text">A. 正确</text>
          </view>
          <view
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === false }"
            @click="selectTrueFalseAnswer(false)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === false }">
              <view v-if="userAnswers[currentQuestion.id] === false" class="radio-inner"></view>
            </view>
            <text class="option-text">B. 错误</text>
          </view>
        </view>
      </view>

      <!-- 简答题 -->
      <view class="question-card" v-else-if="currentQuestion.type === 'shortanswer'">
        <view class="question-header">
          <view class="question-type-tag question-type-shortanswer">简答题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="answer-textarea-wrapper">
          <textarea
            class="answer-textarea"
            v-model="userAnswers[currentQuestion.id]"
            placeholder="请输入你的答案..."
            placeholder-class="textarea-placeholder"
            :maxlength="1000"
          ></textarea>
          <text class="textarea-counter">{{ (userAnswers[currentQuestion.id] || '').length }}/1000</text>
        </view>
      </view>
      </view>
      </scroll-view>

      <!-- 底部导航 -->
      <view class="bottom-nav">
        <view
          class="nav-btn prev-btn"
          :class="{ 'nav-btn-disabled': currentIndex === 0 }"
          @click="prevQuestion"
        >
          <image class="nav-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
          <text class="nav-btn-text">上一题</text>
        </view>
        <scroll-view
          class="question-dots"
          ref="questionDots"
          scroll-x
          :scroll-left="dotsScrollLeft"
          scroll-with-animation
          :show-scrollbar="false"
        >
          <view class="question-dots-inner">
            <view
              v-for="(q, idx) in questions"
              :key="q.id"
              class="dot"
              :class="{
                'dot-current': idx === currentIndex,
                'dot-answered': hasAnswer(q.id) && idx !== currentIndex
              }"
              @click="jumpToQuestion(idx)"
            ></view>
          </view>
        </scroll-view>
        <view
          class="nav-btn next-btn"
          :class="{ 'nav-btn-disabled': currentIndex === questions.length - 1 }"
          @click="nextQuestion"
        >
          <text class="nav-btn-text">下一题</text>
          <image class="nav-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import { getQuizDetail, submitQuiz } from '@/api/space'

export default {
  data() {
    return {
      msgId: null,
      quizId: null,
      isLoading: true,
      loadError: null,
      currentIndex: 0,
      userAnswers: {},
      optionLabels: ['A', 'B', 'C', 'D', 'E', 'F'],
      touchStartX: 0,
      touchStartY: 0,
      // 动画状态
      slideDirection: 'none',  // 'left' | 'right' | 'none'
      isAnimating: false,
      // dots 滚动位置（用于小程序）
      dotsScrollLeft: 0,
      // 默认模拟数据（当没有 quizId 时使用）
      questions: [
        {
          id: 1,
          type: 'single',
          title: '以下哪个是 JavaScript 的基本数据类型？',
          options: ['Array', 'Object', 'String', 'Function'],
          answer: 2
        },
        {
          id: 2,
          type: 'multiple',
          title: '以下哪些是 CSS 选择器？（多选）',
          options: ['.class', '#id', '@media', ':hover'],
          answer: [0, 1, 3]
        },
        {
          id: 3,
          type: 'truefalse',
          title: 'HTML 是一种编程语言。',
          answer: false
        },
        {
          id: 4,
          type: 'shortanswer',
          title: '简述什么是响应式设计？',
          answer: null
        }
      ]
    }
  },

  computed: {
    currentQuestion() {
      return this.questions[this.currentIndex]
    },
    answeredCount() {
      return this.questions.filter(q => this.hasAnswer(q.id)).length
    },
    progressPercent() {
      return (this.answeredCount / this.questions.length) * 100
    },
    canSubmit() {
      return this.answeredCount === this.questions.length
    },
    slideAnimationClass() {
      if (this.slideDirection === 'none') return ''
      if (this.slideDirection === 'left') {
        return this.isAnimating ? 'slide-out-left' : 'slide-in-from-right'
      }
      return this.isAnimating ? 'slide-out-right' : 'slide-in-from-left'
    }
  },

  onLoad(options) {
    if (options.quizId) {
      this.quizId = options.quizId
      this.loadQuizData(options.quizId)
    } else if (options.msgId) {
      // 兼容模拟模式
      this.msgId = options.msgId
      this.isLoading = false
    } else {
      this.isLoading = false
    }
  },

  methods: {
    /**
     * 从后端加载测试数据
     * @param {string} quizId - 测试 ID
     */
    async loadQuizData(quizId) {
      try {
        this.isLoading = true
        this.loadError = null

        const response = await getQuizDetail(quizId)

        // 转换后端数据格式到前端格式
        this.questions = response.questions.map((q, index) => {
          return this.convertQuestion(q, index)
        })

        this.isLoading = false
      } catch (error) {
        this.loadError = error.message || '加载失败'
        this.isLoading = false

        uni.showToast({
          title: '加载测试数据失败',
          icon: 'none'
        })
      }
    },

    /**
     * 转换后端题目格式到前端格式
     * @param {Object} backendQuestion - 后端题目数据
     * @param {number} index - 题目索引
     * @returns {Object} 前端题目数据
     */
    convertQuestion(backendQuestion, index) {
      const typeMap = {
        'single_choice': 'single',
        'multiple_choice': 'multiple',
        'true_false': 'truefalse',
        'short_answer': 'shortanswer'
      }

      const frontendType = typeMap[backendQuestion.question_type] || 'single'
      const correctAnswer = backendQuestion.correct_answer

      // 提取正确答案
      let answer = null
      if (frontendType === 'single') {
        answer = correctAnswer.index
      } else if (frontendType === 'multiple') {
        answer = correctAnswer.indices || []
      } else if (frontendType === 'truefalse') {
        answer = correctAnswer.value
      } else if (frontendType === 'shortanswer') {
        answer = correctAnswer.reference || null
      }

      return {
        id: backendQuestion.id || (index + 1),
        type: frontendType,
        title: backendQuestion.question_stem,
        options: backendQuestion.options || [],
        answer: answer
      }
    },

    goBack() {
      uni.navigateBack({
        delta: 1
      })
    },

    handleTouchStart(e) {
      this.touchStartX = e.touches[0].clientX
      this.touchStartY = e.touches[0].clientY
    },

    handleTouchEnd(e) {
      const touchEndX = e.changedTouches[0].clientX
      const touchEndY = e.changedTouches[0].clientY
      const deltaX = touchEndX - this.touchStartX
      const deltaY = touchEndY - this.touchStartY

      // 水平滑动距离大于垂直滑动，且超过阈值
      if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
        if (deltaX < 0) {
          this.nextQuestion()  // 左滑 → 下一题
        } else {
          this.prevQuestion()  // 右滑 → 上一题
        }
      }
    },

    hasAnswer(questionId) {
      const answer = this.userAnswers[questionId]
      if (answer === undefined || answer === null) return false
      if (Array.isArray(answer)) return answer.length > 0
      if (typeof answer === 'string') return answer.trim().length > 0
      return true
    },

    selectSingleAnswer(idx) {
      this.userAnswers = {
        ...this.userAnswers,
        [this.currentQuestion.id]: idx
      }
    },

    isMultipleSelected(idx) {
      const answers = this.userAnswers[this.currentQuestion.id]
      return Array.isArray(answers) && answers.includes(idx)
    },

    toggleMultipleAnswer(idx) {
      const currentAnswers = this.userAnswers[this.currentQuestion.id] || []
      const newAnswers = currentAnswers.includes(idx)
        ? currentAnswers.filter(i => i !== idx)
        : [...currentAnswers, idx]

      this.userAnswers = {
        ...this.userAnswers,
        [this.currentQuestion.id]: newAnswers
      }
    },

    selectTrueFalseAnswer(value) {
      this.userAnswers = {
        ...this.userAnswers,
        [this.currentQuestion.id]: value
      }
    },

    /**
     * 带动画切换到指定题目
     * @param {number} newIndex - 目标题目索引
     * @param {string} direction - 动画方向 'left' | 'right'
     */
    async animateToQuestion(newIndex, direction) {
      // 边界检查
      if (newIndex < 0 || newIndex >= this.questions.length) return
      // 相同题目或正在动画中
      if (newIndex === this.currentIndex || this.isAnimating) return

      // 1. 设置退出动画状态
      this.slideDirection = direction
      this.isAnimating = true

      // 2. 等待退出动画完成
      await new Promise(resolve => setTimeout(resolve, 280))

      // 3. 更新索引，切换到进入动画
      this.currentIndex = newIndex
      this.isAnimating = false

      // 4. 等待进入动画完成后重置状态
      await new Promise(resolve => setTimeout(resolve, 280))
      this.slideDirection = 'none'

      // 5. 滚动 dots 容器使当前圆点居中
      this.$nextTick(() => {
        this.scrollDotsToCenter(newIndex)
      })
    },

    /**
     * 滚动 dots 容器使指定索引的圆点居中显示
     * @param {number} index - 目标圆点索引
     */
    scrollDotsToCenter(index) {
      // 使用 uni.createSelectorQuery 获取尺寸信息
      const query = uni.createSelectorQuery().in(this)
      query.select('.question-dots').boundingClientRect()
      query.selectAll('.dot').boundingClientRect()
      query.exec((res) => {
        if (!res || !res[0] || !res[1]) return

        const containerRect = res[0]
        const dotRects = res[1]
        if (!dotRects[index]) return

        const dot = dotRects[index]
        const containerWidth = containerRect.width

        // 计算圆点相对于容器的偏移位置
        // 通过累加前面所有圆点的宽度和间距来计算
        const dotWidth = 16  // rpx，普通圆点宽度
        const currentDotWidth = 32  // rpx，当前圆点宽度
        const gap = 12  // rpx 间距
        const padding = 8  // rpx 内边距

        // 计算当前圆点的左侧偏移（单位 rpx）
        let offsetRpx = padding
        for (let i = 0; i < index; i++) {
          offsetRpx += dotWidth + gap
        }

        // 将 rpx 转换为 px
        const systemInfo = uni.getSystemInfoSync()
        const ratio = systemInfo.screenWidth / 750
        const offsetPx = offsetRpx * ratio
        const currentDotWidthPx = (index === this.currentIndex ? currentDotWidth : dotWidth) * ratio

        // 计算滚动位置，使当前圆点居中
        const scrollLeft = offsetPx - (containerWidth / 2) + (currentDotWidthPx / 2)

        // 设置滚动位置
        this.dotsScrollLeft = Math.max(0, scrollLeft)
      })
    },

    prevQuestion() {
      if (this.currentIndex > 0) {
        this.animateToQuestion(this.currentIndex - 1, 'right')
      }
    },

    nextQuestion() {
      if (this.currentIndex < this.questions.length - 1) {
        this.animateToQuestion(this.currentIndex + 1, 'left')
      }
    },

    jumpToQuestion(idx) {
      if (idx === this.currentIndex) return
      const direction = idx > this.currentIndex ? 'left' : 'right'
      this.animateToQuestion(idx, direction)
    },

    handleSubmit() {
      if (!this.canSubmit) {
        uni.showToast({
          title: '请完成所有题目',
          icon: 'none'
        })
        return
      }

      this.submitAnswers()
    },

    async submitAnswers() {
      // 如果有 quizId，调用后端 API 进行评估
      if (this.quizId) {
        await this.submitToBackend()
        return
      }

      // 模拟模式：本地计算得分
      let correctCount = 0
      let totalAutoGrade = 0

      this.questions.forEach(q => {
        if (q.type === 'shortanswer') return

        totalAutoGrade++
        const userAnswer = this.userAnswers[q.id]

        if (q.type === 'single' || q.type === 'truefalse') {
          if (userAnswer === q.answer) correctCount++
        } else if (q.type === 'multiple') {
          const correct = q.answer.sort().join(',')
          const user = (userAnswer || []).sort().join(',')
          if (correct === user) correctCount++
        }
      })

      const score = Math.round((correctCount / totalAutoGrade) * 100)

      uni.showModal({
        title: '测试完成',
        content: `你的得分：${score}分\n（${correctCount}/${totalAutoGrade} 题正确）`,
        showCancel: false,
        success: () => {
          this.goBack()
        }
      })
    },

    /**
     * 提交答卷到后端进行评估
     */
    async submitToBackend() {
      try {
        uni.showLoading({
          title: '正在评估...',
          mask: true
        })

        // 构建提交数据，转换为后端格式
        const answers = this.questions.map(q => {
          const userAnswer = this.userAnswers[q.id]
          let answer = null

          if (q.type === 'single') {
            // 单选题: { index: number }
            answer = userAnswer !== undefined ? { index: userAnswer } : null
          } else if (q.type === 'multiple') {
            // 多选题: { indices: number[] }
            answer = Array.isArray(userAnswer) && userAnswer.length > 0
              ? { indices: userAnswer }
              : null
          } else if (q.type === 'truefalse') {
            // 判断题: { value: boolean }
            answer = userAnswer !== undefined ? { value: userAnswer } : null
          } else if (q.type === 'shortanswer') {
            // 简答题: { text: string }
            answer = userAnswer ? { text: userAnswer } : null
          }

          return {
            question_id: q.id,
            answer: answer
          }
        })

        const response = await submitQuiz(this.quizId, { answers })

        uni.hideLoading()

        // 将评估结果存入全局缓存，传递给结果页
        uni.setStorageSync('quizEvaluationResult', response)

        // 跳转到结果页
        uni.redirectTo({
          url: `/pages/testResult/testResult?quizId=${this.quizId}`
        })
      } catch (error) {
        uni.hideLoading()

        // 处理 409 冲突错误（已作答过）
        if (error.statusCode === 409 || error.code === 'QUIZ_ALREADY_ATTEMPTED') {
          uni.showModal({
            title: '提示',
            content: '该测验已经作答过，将为您跳转到评估结果页面',
            showCancel: false,
            success: () => {
              uni.redirectTo({
                url: `/pages/testResult/testResult?quizId=${this.quizId}&fromList=true`
              })
            }
          })
          return
        }

        uni.showToast({
          title: error.message || '提交失败，请重试',
          icon: 'none'
        })
      }
    }
  }
}
</script>

<style>
.test-page {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: rgb(10, 10, 10);
  overflow-x: hidden;
}

/* ========== 加载和错误状态 ========== */
.loading-container,
.error-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 88rpx);
}

.loading-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.6);
}

.error-text {
  font-size: 30rpx;
  color: #ef4444;
  margin-bottom: 32rpx;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(0, 136, 255, 0.2);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
  border-radius: 40rpx;
}

.retry-btn-text {
  font-size: 28rpx;
  color: #0088FF;
}

/* ========== 导航栏 ========== */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
  background: linear-gradient(to bottom, rgba(10, 10, 10, 0.95) 0%, transparent 100%);
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
  color: #ffffff;
}

.nav-right {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.15);
  transition: all 0.2s ease;
}

.nav-right-active {
  background-color: #0088FF;
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

/* ========== 进度条 ========== */
.progress-section {
  position: fixed;
  top: calc(100vh * 1.5 / 26 + 88rpx);
  left: 0;
  right: 0;
  z-index: 99;
  padding: 16rpx calc(100vw / 24);
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: linear-gradient(to bottom, rgba(10, 10, 10, 0.9) 0%, transparent 100%);
}

.progress-bar {
  flex: 1;
  height: 8rpx;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4rpx;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: rgb(134, 208, 125);
  border-radius: 4rpx;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.6);
  min-width: 60rpx;
  text-align: right;
}

/* ========== 题目容器 ========== */
.question-container {
  flex: 1;
  padding: calc(100vh * 1.5 / 26 + 140rpx) calc(100vw / 24) 180rpx;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* ========== 题目卡片 ========== */
.question-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-sizing: border-box;
  overflow: hidden;
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.question-type-tag {
  font-size: 22rpx;
  font-weight: 500;
  padding: 8rpx 16rpx;
  border-radius: 8rpx;
}

.question-type-single {
  background: rgba(0, 136, 255, 0.2);
  color: #0088FF;
}

.question-type-multiple {
  background: rgba(139, 92, 246, 0.2);
  color: #8B5CF6;
}

.question-type-truefalse {
  background: rgba(16, 185, 129, 0.2);
  color: #10B981;
}

.question-type-shortanswer {
  background: rgba(245, 158, 11, 0.2);
  color: #F59E0B;
}

.question-number {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
}

.question-title {
  font-size: 32rpx;
  font-weight: 500;
  color: #ffffff;
  line-height: 1.6;
  margin-bottom: 48rpx;
}

/* ========== 选项列表 ========== */
.options-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 28rpx 32rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  transition: all 0.2s ease;
}

.option-item-selected {
  background: rgba(0, 136, 255, 0.15);
  border-color: rgba(0, 136, 255, 0.4);
}

/* ========== 单选按钮 ========== */
.option-radio {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(255, 255, 255, 0.3);
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.option-radio-selected {
  border-color: #0088FF;
}

.radio-inner {
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  background: #0088FF;
}

/* ========== 多选框 ========== */
.option-checkbox {
  width: 40rpx;
  height: 40rpx;
  border-radius: 10rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.3);
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.option-checkbox-checked {
  background: #0088FF;
  border-color: transparent;
}

.checkbox-icon {
  width: 24rpx;
  height: 24rpx;
  filter: brightness(0) invert(1);
}

.option-text {
  flex: 1;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.5;
}


/* ========== 简答题 ========== */
.answer-textarea-wrapper {
  position: relative;
}

.answer-textarea {
  width: 100%;
  min-height: 240rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  padding: 24rpx;
  font-size: 28rpx;
  color: #ffffff;
  line-height: 1.6;
  box-sizing: border-box;
}

.textarea-placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.textarea-counter {
  position: absolute;
  right: 24rpx;
  bottom: 16rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.3);
}

/* ========== 底部导航 ========== */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding: 20rpx calc(100vw / 24) calc(20rpx + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(to top, rgba(10, 10, 10, 0.98) 0%, rgba(10, 10, 10, 0.9) 70%, transparent 100%);
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 20rpx 28rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 40rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.nav-btn-disabled {
  opacity: 0.4;
}

.nav-btn-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
}

.nav-btn-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
}

/* ========== 题目指示点 ========== */
.question-dots {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  padding: 8rpx 0;
}

.question-dots-inner {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 0 8rpx;
}

/* 隐藏滚动条 */
.question-dots::-webkit-scrollbar {
  display: none;
}

.dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.dot-current {
  width: 32rpx;
  border-radius: 8rpx;
  background: #0088FF;
}

.dot-answered {
  background: rgba(0, 136, 255, 0.5);
}

/* ========== 卡片切换动画 ========== */
.question-card-wrapper {
  will-change: transform, opacity;
}

/* 退出动画 - 向左滑出 */
.slide-out-left {
  transform: translateX(-30%);
  opacity: 0;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 退出动画 - 向右滑出 */
.slide-out-right {
  transform: translateX(30%);
  opacity: 0;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 进入动画 - 从右侧滑入 */
.slide-in-from-right {
  animation: slideInFromRight 0.28s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

/* 进入动画 - 从左侧滑入 */
.slide-in-from-left {
  animation: slideInFromLeft 0.28s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes slideInFromRight {
  0% {
    transform: translateX(30%);
    opacity: 0;
  }
  100% {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideInFromLeft {
  0% {
    transform: translateX(-30%);
    opacity: 0;
  }
  100% {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
