<template>
  <view class="quiz-answer-view">
    <view class="answer-toolbar">
      <view class="toolbar-btn" @tap="$emit('back')">
        <text class="toolbar-btn-text">返回</text>
      </view>
      <text class="toolbar-title">{{ quizTitle || '测试题' }}</text>
      <view
        class="toolbar-btn toolbar-submit-btn"
        :class="{ 'toolbar-submit-btn-active': canSubmit && !submitting }"
        @tap="handleSubmit"
      >
        <text class="toolbar-btn-text">{{ submitting ? '提交中...' : '提交' }}</text>
      </view>
    </view>

    <view v-if="loading" class="state-wrap">
      <text class="state-text">正在加载测试题...</text>
    </view>

    <view v-else-if="loadError" class="state-wrap">
      <text class="state-text state-error">{{ loadError }}</text>
      <view class="retry-btn" @tap="$emit('retry')">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <view v-else-if="questions.length === 0" class="state-wrap">
      <text class="state-text">测试题为空</text>
      <view class="retry-btn" @tap="$emit('back')">
        <text class="retry-btn-text">返回列表</text>
      </view>
    </view>

    <template v-else>
      <view class="progress-wrap">
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: `${progressPercent}%` }"></view>
        </view>
        <text class="progress-text">{{ answeredCount }}/{{ questions.length }}</text>
      </view>

      <view class="question-wrap">
        <view class="question-header">
          <view class="question-type-tag" :class="`question-type-${currentQuestion.type}`">
            <text class="question-type-tag-text">{{ questionTypeLabel(currentQuestion.type) }}</text>
          </view>
          <text class="question-order">第 {{ currentIndex + 1 }} 题</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>

        <view v-if="currentQuestion.type === 'single'" class="options-list">
          <view
            v-for="(option, idx) in currentQuestion.options"
            :key="idx"
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === idx }"
            @tap="selectSingleAnswer(idx)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === idx }">
              <view v-if="userAnswers[currentQuestion.id] === idx" class="option-radio-inner"></view>
            </view>
            <text class="option-text">{{ optionLabel(idx) }}. {{ option }}</text>
          </view>
        </view>

        <view v-else-if="currentQuestion.type === 'multiple'" class="options-list">
          <view
            v-for="(option, idx) in currentQuestion.options"
            :key="idx"
            class="option-item"
            :class="{ 'option-item-selected': isMultipleSelected(idx) }"
            @tap="toggleMultipleAnswer(idx)"
          >
            <view class="option-checkbox" :class="{ 'option-checkbox-selected': isMultipleSelected(idx) }">
              <text v-if="isMultipleSelected(idx)" class="option-checkmark">✓</text>
            </view>
            <text class="option-text">{{ optionLabel(idx) }}. {{ option }}</text>
          </view>
        </view>

        <view v-else-if="currentQuestion.type === 'truefalse'" class="options-list">
          <view
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === true }"
            @tap="selectTrueFalseAnswer(true)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === true }">
              <view v-if="userAnswers[currentQuestion.id] === true" class="option-radio-inner"></view>
            </view>
            <text class="option-text">A. 正确</text>
          </view>
          <view
            class="option-item"
            :class="{ 'option-item-selected': userAnswers[currentQuestion.id] === false }"
            @tap="selectTrueFalseAnswer(false)"
          >
            <view class="option-radio" :class="{ 'option-radio-selected': userAnswers[currentQuestion.id] === false }">
              <view v-if="userAnswers[currentQuestion.id] === false" class="option-radio-inner"></view>
            </view>
            <text class="option-text">B. 错误</text>
          </view>
        </view>

        <view v-else class="short-answer-wrap">
          <textarea
            class="short-answer-textarea"
            :value="shortAnswerValue"
            placeholder="请输入你的答案..."
            placeholder-class="short-answer-placeholder"
            maxlength="1000"
            @input="onShortAnswerInput"
          ></textarea>
          <text class="short-answer-counter">{{ shortAnswerLength }}/1000</text>
        </view>
      </view>

      <view class="bottom-nav">
        <view
          class="nav-btn"
          :class="{ 'nav-btn-disabled': currentIndex === 0 }"
          @tap="prevQuestion"
        >
          <text class="nav-btn-text">上一题</text>
        </view>

        <scroll-view class="dots-scroll" scroll-x :show-scrollbar="false">
          <view class="dots-inner">
            <view
              v-for="(q, idx) in questions"
              :key="q.id"
              class="dot"
              :class="{
                'dot-current': idx === currentIndex,
                'dot-answered': hasAnswer(q.id) && idx !== currentIndex
              }"
              @tap="jumpToQuestion(idx)"
            ></view>
          </view>
        </scroll-view>

        <view
          class="nav-btn"
          :class="{ 'nav-btn-disabled': currentIndex === questions.length - 1 }"
          @tap="nextQuestion"
        >
          <text class="nav-btn-text">下一题</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
const OPTION_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

export default {
  name: 'QuizAnswerView',
  props: {
    quizTitle: {
      type: String,
      default: ''
    },
    questions: {
      type: Array,
      default: () => []
    },
    loading: {
      type: Boolean,
      default: false
    },
    loadError: {
      type: String,
      default: ''
    },
    submitting: {
      type: Boolean,
      default: false
    }
  },
  emits: ['back', 'retry', 'submit'],
  data() {
    return {
      currentIndex: 0,
      userAnswers: {}
    }
  },
  computed: {
    currentQuestion() {
      return this.questions[this.currentIndex] || {}
    },
    answeredCount() {
      return this.questions.filter((q) => this.hasAnswer(q.id)).length
    },
    progressPercent() {
      if (!this.questions.length) return 0
      return (this.answeredCount / this.questions.length) * 100
    },
    canSubmit() {
      return this.questions.length > 0 && this.answeredCount === this.questions.length
    },
    shortAnswerValue() {
      const qid = this.currentQuestion?.id
      if (!qid) return ''
      return this.userAnswers[qid] || ''
    },
    shortAnswerLength() {
      return this.shortAnswerValue.length
    }
  },
  watch: {
    questions: {
      immediate: true,
      handler() {
        this.currentIndex = 0
        this.userAnswers = {}
      }
    }
  },
  methods: {
    optionLabel(index) {
      return OPTION_LABELS[index] || String(index + 1)
    },
    questionTypeLabel(type) {
      const labels = {
        single: '单选题',
        multiple: '多选题',
        truefalse: '判断题',
        shortanswer: '简答题'
      }
      return labels[type] || '题目'
    },
    hasAnswer(questionId) {
      const answer = this.userAnswers[questionId]
      if (answer === undefined || answer === null) return false
      if (Array.isArray(answer)) return answer.length > 0
      if (typeof answer === 'string') return answer.trim().length > 0
      return true
    },
    updateAnswer(questionId, value) {
      this.userAnswers = {
        ...this.userAnswers,
        [questionId]: value
      }
    },
    selectSingleAnswer(index) {
      this.updateAnswer(this.currentQuestion.id, index)
    },
    isMultipleSelected(index) {
      const answer = this.userAnswers[this.currentQuestion.id]
      return Array.isArray(answer) && answer.includes(index)
    },
    toggleMultipleAnswer(index) {
      const current = this.userAnswers[this.currentQuestion.id]
      const currentAnswers = Array.isArray(current) ? current : []
      const nextAnswers = currentAnswers.includes(index)
        ? currentAnswers.filter((item) => item !== index)
        : [...currentAnswers, index]
      this.updateAnswer(this.currentQuestion.id, nextAnswers)
    },
    selectTrueFalseAnswer(value) {
      this.updateAnswer(this.currentQuestion.id, value)
    },
    onShortAnswerInput(event) {
      const value = event?.detail?.value || ''
      this.updateAnswer(this.currentQuestion.id, value)
    },
    prevQuestion() {
      if (this.currentIndex <= 0) return
      this.currentIndex = this.currentIndex - 1
    },
    nextQuestion() {
      if (this.currentIndex >= this.questions.length - 1) return
      this.currentIndex = this.currentIndex + 1
    },
    jumpToQuestion(index) {
      if (index < 0 || index >= this.questions.length) return
      this.currentIndex = index
    },
    handleSubmit() {
      if (this.submitting) return
      if (!this.canSubmit) {
        uni.showToast({ title: '请完成所有题目', icon: 'none' })
        return
      }
      this.$emit('submit', { userAnswers: this.userAnswers })
    }
  }
}
</script>

<style scoped>
.quiz-answer-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24rpx;
  box-sizing: border-box;
}

.answer-toolbar {
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.toolbar-title {
  min-width: 0;
  flex: 1;
  font-size: 28rpx;
  color: #ffffff;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toolbar-btn {
  flex-shrink: 0;
  height: 58rpx;
  min-width: 108rpx;
  border-radius: 999rpx;
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
}

.toolbar-submit-btn {
  border-color: rgba(96, 165, 250, 0.34);
  background: rgba(96, 165, 250, 0.14);
}

.toolbar-submit-btn-active {
  background: rgba(59, 130, 246, 0.86);
}

.toolbar-btn-text {
  font-size: 24rpx;
  color: #ffffff;
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

.progress-wrap {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 18rpx;
}

.progress-bar {
  flex: 1;
  height: 12rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
}

.progress-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.66);
}

.question-wrap {
  flex: 1;
  min-height: 0;
  border-radius: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(20, 20, 35, 0.88);
  padding: 24rpx;
  box-sizing: border-box;
  overflow-y: auto;
  /* Custom scrollbar */
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
}

.question-wrap::-webkit-scrollbar {
  width: 6px;
}

.question-wrap::-webkit-scrollbar-track {
  background: transparent;
}

.question-wrap::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

.question-wrap::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10rpx;
}

.question-type-tag {
  padding: 8rpx 16rpx;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  background: rgba(96, 165, 250, 0.2);
}

.question-type-tag-text {
  font-size: 22rpx;
  font-weight: 500;
  color: #60a5fa;
}

.question-type-single {
  background: rgba(0, 136, 255, 0.2);
}

.question-type-single .question-type-tag-text {
  color: #0088FF;
}

.question-type-multiple {
  background: rgba(139, 92, 246, 0.2);
}

.question-type-multiple .question-type-tag-text {
  color: #8B5CF6;
}

.question-type-truefalse {
  background: rgba(16, 185, 129, 0.2);
}

.question-type-truefalse .question-type-tag-text {
  color: #10B981;
}

.question-type-shortanswer {
  background: rgba(245, 158, 11, 0.2);
}

.question-type-shortanswer .question-type-tag-text {
  color: #F59E0B;
}

.question-order {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.6);
}

.question-title {
  display: block;
  margin-top: 16rpx;
  font-size: 30rpx;
  line-height: 1.5;
  color: #ffffff;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 18rpx;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-height: 72rpx;
  border-radius: 14rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  padding: 14rpx 16rpx;
  box-sizing: border-box;
}

.option-item-selected {
  border-color: rgba(96, 165, 250, 0.58);
  background: rgba(96, 165, 250, 0.16);
}

.option-radio,
.option-checkbox {
  width: 34rpx;
  height: 34rpx;
  flex-shrink: 0;
  border-radius: 50%;
  border: 2rpx solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.option-checkbox {
  border-radius: 8rpx;
}

.option-radio-selected,
.option-checkbox-selected {
  border-color: #60a5fa;
  background: rgba(59, 130, 246, 0.72);
}

.option-radio-inner {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: #ffffff;
}

.option-checkmark {
  font-size: 20rpx;
  color: #ffffff;
  line-height: 1;
}

.option-text {
  min-width: 0;
  flex: 1;
  font-size: 24rpx;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.92);
}

.short-answer-wrap {
  margin-top: 18rpx;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.short-answer-textarea {
  width: 100%;
  min-height: 300rpx;
  max-height: 100%;
  border-radius: 14rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  padding: 16rpx;
  box-sizing: border-box;
  color: #ffffff;
  font-size: 24rpx;
  line-height: 1.5;
  resize: none;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
}

.short-answer-textarea::-webkit-scrollbar {
  width: 6px;
}

.short-answer-textarea::-webkit-scrollbar-track {
  background: transparent;
}

.short-answer-textarea::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

.short-answer-textarea::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

.short-answer-placeholder {
  color: rgba(255, 255, 255, 0.36);
}

.short-answer-counter {
  display: block;
  margin-top: 8rpx;
  text-align: right;
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.45);
}

.bottom-nav {
  height: 72rpx;
  margin-top: 16rpx;
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.nav-btn {
  flex-shrink: 0;
  min-width: 104rpx;
  height: 56rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
}

.nav-btn-disabled {
  opacity: 0.4;
}

.nav-btn-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.86);
}

.dots-scroll {
  flex: 1;
  min-width: 0;
}

.dots-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 0 4rpx;
}

.dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
}

.dot-current {
  width: 18rpx;
  height: 18rpx;
  background: #60a5fa;
}

.dot-answered {
  background: #86efac;
}
</style>
