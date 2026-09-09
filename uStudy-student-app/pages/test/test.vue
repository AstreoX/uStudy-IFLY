<template>
  <view class="test-page" :class="pageThemeClass">
    <!-- 顶部导航栏 -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">{{ isAssignment ? (assignmentTitle || '教师测验') : '测试题' }}</text>
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
      <view class="retry-btn" @click="reloadContent">
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
      @touchstart="handleQuestionTouchStart"
      @touchend="handleQuestionTouchEnd"
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

      <!-- OJ 编程题：APP 仅展示题干，不能查看或编辑代码。 -->
      <view class="question-card oj-question-card" v-else-if="currentQuestion.type === 'code'">
        <view class="question-header">
          <view class="question-type-tag question-type-code">编程题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="option-item option-item-selected oj-web-hint">
          <text class="option-text oj-web-hint-text">请前往网页端作答</text>
        </view>
      </view>

      <!-- 简答题 -->
      <view class="question-card" v-else-if="currentQuestion.type === 'shortanswer'">
        <view class="question-header">
          <view class="question-type-tag question-type-shortanswer">简答题</view>
          <text class="question-number">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
        <view class="answer-textarea-wrapper" @click.stop @touchstart.stop @touchend.stop @mousedown.stop>
          <textarea
            class="answer-textarea"
            v-model="userAnswers[currentQuestion.id]"
            placeholder="请输入你的答案..."
            placeholder-class="textarea-placeholder"
            :maxlength="1000"
            @click.stop
            @touchstart.stop
            @touchend.stop
            @mousedown.stop
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
          <view class="question-dots-center">
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

    <!-- 提交成功浮层 -->
    <view v-if="showSubmitSuccess" class="submit-overlay" @touchmove.stop.prevent>
      <view class="submit-overlay-bg" :class="{ 'overlay-bg-show': submitOverlayAnimated }"></view>
      <view class="submit-overlay-card" :class="{ 'overlay-card-show': submitOverlayAnimated }">
        <view class="submit-success-icon-wrap">
          <image class="submit-success-icon" src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg" mode="aspectFit" />
        </view>
        <text class="submit-success-title">提交成功</text>
        <text class="submit-success-desc">答卷已提交，AI 正在后台评估中，完成后会通知你</text>
        <view class="submit-success-btn" @click="handleSuccessConfirm">
          <text class="submit-success-btn-text">返回</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getQuizDetail, submitQuiz } from '@/api/space'
import { getAssignmentDetail, saveAssignmentDraft, submitAssignment } from '@/api/assignments'
import { assignmentHasOj, buildAssignmentDraftPayload, buildAssignmentSubmitPayload, convertAssignmentDetail } from '@/utils/assignment-adapter'
import { setPendingEvaluation } from '@/utils/quizEvaluationBus'
import { setQuizEvaluationResult } from '@/utils/storage'
import { clearPendingNavigationIfMatches } from '@/utils/deepLink'
import { goBack as safeGoBack } from '@/utils/navigation'
import homeThemePageMixin from '@/mixins/homeThemePageMixin'

export default {
  mixins: [homeThemePageMixin],
  data() {
    return {
      msgId: null,
      quizId: null,
      assignmentId: null,
      itemKind: 'quiz',
      assignmentTitle: '',
      assignmentDueAt: '',
      assignmentDetail: null,
      isLoading: true,
      showSubmitSuccess: false,
      submitOverlayAnimated: false,
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
      return this.questions.length > 0 && this.answeredCount === this.questions.length && !this.assignmentOverdue && !this.hasOjQuestion
    },
    isAssignment() {
      return this.itemKind === 'assignment'
    },
    hasOjQuestion() {
      return this.isAssignment && assignmentHasOj(this.assignmentDetail)
    },
    assignmentOverdue() {
      if (!this.isAssignment || !this.assignmentDueAt) return false
      const dueTime = new Date(this.assignmentDueAt).getTime()
      return Number.isFinite(dueTime) && dueTime <= Date.now()
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
    this.restoreThemeMode({ darkStatusBarBackground: '#1D1E20' })
    if (options.itemKind === 'assignment' && options.assignmentId) {
      this.itemKind = 'assignment'
      this.assignmentId = options.assignmentId
      this.loadAssignmentData(options.assignmentId)
    } else if (options.quizId) {
      this.quizId = options.quizId
      clearPendingNavigationIfMatches(`/pages/test/test?quizId=${encodeURIComponent(options.quizId)}`)
      this.loadQuizData(options.quizId)
    } else if (options.msgId) {
      // 兼容模拟模式
      this.msgId = options.msgId
      this.isLoading = false
    } else {
      this.isLoading = false
    }
  },

  onShow() {
    this.restoreThemeMode({ darkStatusBarBackground: '#1D1E20' })
  },

  methods: {
    handleQuestionTouchStart(e) {
      if (this.currentQuestion && this.currentQuestion.type === 'shortanswer') return
      this.handleTouchStart(e)
    },

    handleQuestionTouchEnd(e) {
      if (this.currentQuestion && this.currentQuestion.type === 'shortanswer') return
      this.handleTouchEnd(e)
    },

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
        'short_answer': 'shortanswer',
        'code': 'code'
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

    async goBack() {
      if (this.isAssignment) await this.saveAssignmentDraftIfNeeded()
      safeGoBack({
        fallbackUrl: '/pages/index/index'
      })
    },

    async loadAssignmentData(assignmentId) {
      try {
        this.isLoading = true
        this.loadError = null
        const response = await getAssignmentDetail(assignmentId)
        const detail = convertAssignmentDetail(response)
        this.assignmentDetail = detail
        this.assignmentTitle = detail.title
        this.assignmentDueAt = detail.dueAt
        this.currentIndex = Math.min(Math.max(detail.currentQuestionIndex || 0, 0), Math.max(detail.questions.length - 1, 0))
        this.questions = detail.questions
        this.userAnswers = detail.userAnswers
      } catch (error) {
        this.loadError = error.message || '加载教师测验失败'
        uni.showToast({ title: '加载教师测验失败', icon: 'none' })
      } finally {
        this.isLoading = false
      }
    },

    reloadContent() {
      if (this.isAssignment) this.loadAssignmentData(this.assignmentId)
      else this.loadQuizData(this.quizId)
    },

    handleSuccessConfirm() {
      this.submitOverlayAnimated = false
      setTimeout(() => {
        this.showSubmitSuccess = false
        safeGoBack({
          fallbackUrl: '/pages/index/index'
        })
      }, 200)
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
      const query = uni.createSelectorQuery().in(this)
      query.select('.question-dots').boundingClientRect()
      query.select('.question-dots-inner').boundingClientRect()
      query.selectAll('.dot').boundingClientRect()
      query.exec((res) => {
        if (!res || !res[0] || !res[1] || !res[2]) return

        const containerRect = res[0]
        const innerRect = res[1]
        const dotRects = res[2]
        if (!dotRects[index]) return

        // 如果内容未超出容器，无需滚动（圆点已居中显示）
        if (innerRect.width <= containerRect.width) {
          this.dotsScrollLeft = 0
          return
        }

        // 计算使当前圆点居中的滚动位置
        const currentDot = dotRects[index]
        const dotCenter = currentDot.left - innerRect.left + currentDot.width / 2
        const scrollLeft = dotCenter - containerRect.width / 2

        // 限制滚动范围
        const maxScroll = innerRect.width - containerRect.width
        this.dotsScrollLeft = Math.max(0, Math.min(scrollLeft, maxScroll))
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
      if (this.isAssignment && this.hasOjQuestion) {
        uni.showToast({ title: '编程题请前往网页端作答并提交', icon: 'none' })
        return
      }
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
      if (this.isAssignment) {
        try {
          await submitAssignment(this.assignmentId, buildAssignmentSubmitPayload(this.assignmentDetail, this.userAnswers))
          this.showSubmitSuccess = true
          this.$nextTick(() => {
            setTimeout(() => { this.submitOverlayAnimated = true }, 10)
          })
        } catch (error) {
          uni.showToast({ title: error.message || '提交失败，请重试', icon: 'none' })
        }
        return
      }
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
    submitToBackend() {
      // 构建提交数据，转换为后端格式
      const answers = this.questions.map(q => {
        const userAnswer = this.userAnswers[q.id]
        let answer = null

        if (q.type === 'single') {
          answer = userAnswer !== undefined ? { index: userAnswer } : null
        } else if (q.type === 'multiple') {
          answer = Array.isArray(userAnswer) && userAnswer.length > 0
            ? { indices: userAnswer }
            : null
        } else if (q.type === 'truefalse') {
          answer = userAnswer !== undefined ? { value: userAnswer } : null
        } else if (q.type === 'shortanswer') {
          answer = userAnswer ? { text: userAnswer } : null
        }

        return {
          question_id: q.id,
          answer: answer
        }
      })

      const quizId = this.quizId

      // 立即通知 spaceChat 进入评估中状态（卡片变为不可点击）
      setPendingEvaluation(quizId, { status: 'evaluating' })

      // Fire-and-forget: submit in background
      submitQuiz(quizId, { answers })
        .then(response => {
          setQuizEvaluationResult(response)
          setPendingEvaluation(quizId, { status: 'success', result: response })
        })
        .catch(error => {
          if (error.statusCode === 409 || error.code === 'QUIZ_ALREADY_ATTEMPTED') {
            setPendingEvaluation(quizId, { status: 'already_attempted' })
          } else {
            setPendingEvaluation(quizId, { status: 'error', error: error.message || '评估失败，请重试' })
          }
        })

      // 显示自定义成功浮层
      this.showSubmitSuccess = true
      this.$nextTick(() => {
        setTimeout(() => { this.submitOverlayAnimated = true }, 10)
      })
    },

    async saveAssignmentDraftIfNeeded() {
      if (!this.assignmentId || !this.assignmentDetail || this.assignmentOverdue) return
      try {
        await saveAssignmentDraft(
          this.assignmentId,
          buildAssignmentDraftPayload(this.assignmentDetail, this.userAnswers, this.currentIndex)
        )
      } catch (error) {
        // Do not trap the student on this page when a temporary network error occurs.
        uni.showToast({ title: error.message || '草稿暂存失败', icon: 'none' })
      }
    }
  }
}
</script>

<style scoped>
.test-page {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: rgb(24, 24, 24);
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

.question-type-code {
  background: rgba(0, 136, 255, 0.2);
  color: #0088FF;
}

.oj-web-hint {
  justify-content: center;
  text-align: center;
}

.oj-web-hint-text { flex: none; }

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
  z-index: 2;
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
  position: relative;
  z-index: 2;
  pointer-events: auto;
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
  pointer-events: none;
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

.question-dots-center {
  display: inline-flex;
  min-width: 100%;
  justify-content: center;
  box-sizing: border-box;
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

/* ========== 提交成功浮层 ========== */
.submit-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.submit-overlay-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 250ms ease;
}

.submit-overlay-bg.overlay-bg-show {
  background: rgba(0, 0, 0, 0.55);
}

.submit-overlay-card {
  position: relative;
  width: 560rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56rpx 48rpx 40rpx;
  background: rgba(28, 28, 38, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 28rpx;
  box-shadow:
    0 20rpx 60rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.04) inset;
  transform: translateY(40rpx) scale(0.95);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.submit-overlay-card.overlay-card-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.submit-success-icon-wrap {
  width: 96rpx;
  height: 96rpx;
  margin-bottom: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(76, 175, 80, 0.12);
}

.submit-success-icon {
  width: 56rpx;
  height: 56rpx;
  filter: invert(56%) sepia(43%) saturate(580%) hue-rotate(87deg) brightness(96%) contrast(88%);
}

.submit-success-title {
  font-size: 36rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 16rpx;
}

.submit-success-desc {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.55);
  text-align: center;
  line-height: 1.6;
  margin-bottom: 40rpx;
}

.submit-success-btn {
  width: 100%;
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(74, 108, 247, 0.15);
  border: 1rpx solid rgba(74, 108, 247, 0.3);
  border-radius: 18rpx;
  transition: all 0.15s ease;
}

.submit-success-btn:active {
  transform: scale(0.97);
  background: rgba(74, 108, 247, 0.25);
}

.submit-success-btn-text {
  font-size: 32rpx;
  font-weight: 500;
  color: rgba(74, 108, 247, 1);
}

/* ========== 浅色主题覆盖：仅调整颜色，不改布局 ========== */
.test-page.theme-light {
  background-color: #F3EDE3;
}

.test-page.theme-light .nav-bar {
  background: linear-gradient(
    to bottom,
    rgba(243, 237, 227, 0.95) 0%,
    rgba(243, 237, 227, 0.72) 44%,
    rgba(243, 237, 227, 0) 100%
  );
}

.test-page.theme-light .progress-section {
  background: linear-gradient(
    to bottom,
    rgba(243, 237, 227, 0.92) 0%,
    rgba(243, 237, 227, 0.58) 48%,
    rgba(243, 237, 227, 0) 100%
  );
}

.test-page.theme-light .question-container {
  background: linear-gradient(
    180deg,
    rgba(243, 237, 227, 0.98) 0%,
    rgba(243, 237, 227, 0.98) 100%
  );
}

.test-page.theme-light .bottom-nav {
  background: linear-gradient(
    to top,
    rgba(243, 237, 227, 0.98) 0%,
    rgba(243, 237, 227, 0.94) 74%,
    rgba(243, 237, 227, 0) 100%
  );
}

.test-page.theme-light .nav-left,
.test-page.theme-light .nav-right,
.test-page.theme-light .nav-btn {
  background-color: rgba(255, 255, 255, 0.84);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 12rpx 28rpx rgba(118, 101, 80, 0.1);
}

.test-page.theme-light .question-card,
.test-page.theme-light .option-item {
  background: #FFFAF4;
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 14rpx 32rpx rgba(118, 101, 80, 0.08);
}

.test-page.theme-light .answer-textarea {
  background: rgba(255, 255, 255, 0.88);
  border-color: rgba(63, 53, 42, 0.12);
}

.test-page.theme-light .progress-bar {
  background: rgba(63, 53, 42, 0.08);
}

.test-page.theme-light .progress-fill {
  background: #2F9D70;
}

.test-page.theme-light .nav-title,
.test-page.theme-light .question-title,
.test-page.theme-light .option-text,
.test-page.theme-light .nav-btn-text,
.test-page.theme-light .submit-success-title {
  color: #1F1A16;
}

.test-page.theme-light .loading-text,
.test-page.theme-light .progress-text,
.test-page.theme-light .question-number,
.test-page.theme-light .textarea-counter,
.test-page.theme-light .submit-success-desc {
  color: rgba(31, 26, 22, 0.62);
}

.test-page.theme-light .textarea-placeholder {
  color: rgba(31, 26, 22, 0.42);
}

.test-page.theme-light .nav-icon,
.test-page.theme-light .nav-btn-icon {
  filter: brightness(0) saturate(100%);
}

.test-page.theme-light .nav-right-active,
.test-page.theme-light .option-radio-selected,
.test-page.theme-light .option-checkbox-checked,
.test-page.theme-light .dot-current,
.test-page.theme-light .submit-success-btn {
  background: #2F6EEA;
  border-color: #2F6EEA;
}

.test-page.theme-light .radio-inner {
  background: #FFFFFF;
}

.test-page.theme-light .option-item-selected {
  background: rgba(47, 110, 234, 0.12);
  border-color: rgba(47, 110, 234, 0.22);
}

.test-page.theme-light .option-radio,
.test-page.theme-light .option-checkbox {
  border-color: rgba(63, 53, 42, 0.18);
}

.test-page.theme-light .question-type-single,
.test-page.theme-light .question-type-code {
  background: rgba(47, 110, 234, 0.12);
  color: #2F6EEA;
}

.test-page.theme-light .question-type-multiple {
  background: rgba(126, 94, 219, 0.12);
  color: #6D57BF;
}

.test-page.theme-light .question-type-truefalse {
  background: rgba(47, 157, 112, 0.12);
  color: #2F9D70;
}

.test-page.theme-light .question-type-shortanswer {
  background: rgba(214, 147, 46, 0.12);
  color: #BA7F1F;
}

.test-page.theme-light .dot {
  background: rgba(63, 53, 42, 0.18);
}

.test-page.theme-light .dot-answered {
  background: rgba(47, 110, 234, 0.48);
}

.test-page.theme-light .submit-overlay-bg.overlay-bg-show {
  background: rgba(74, 59, 45, 0.18);
}

.test-page.theme-light .submit-overlay-card {
  background: #FFFAF4;
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 20rpx 54rpx rgba(118, 101, 80, 0.14);
}

.test-page.theme-light .submit-success-btn-text {
  color: #FFFFFF;
}
</style>
