<template>
  <view class="quiz-panel">
    <view v-if="!spaceId" class="placeholder-wrap">
      <text class="placeholder-text">请先选择学习空间</text>
      <text class="placeholder-sub">选择左侧学习空间后可管理测试题</text>
    </view>

    <template v-else>
      <QuizListView
        v-if="viewMode === 'list'"
        :loading="quizzesLoading"
        :load-error="quizzesError"
        :quizzes="quizzes"
        @refresh="loadQuizzes"
        @open="handleOpenQuiz"
      />

      <QuizAnswerView
        v-else-if="viewMode === 'answer'"
        :quiz-title="quizTitle"
        :questions="quizQuestions"
        :loading="quizDetailLoading"
        :load-error="quizDetailError"
        :submitting="submittingAnswers"
        @back="backToList"
        @retry="retryLoadQuizDetail"
        @submit="handleSubmitAnswers"
      />

      <QuizResultView
        v-else
        :loading="resultLoading"
        :load-error="resultError"
        :result-data="resultData"
        @back="backToList"
        @retry="retryLoadQuizResult"
      />
    </template>

    <UToast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import QuizListView from './QuizListView.vue'
import QuizAnswerView from './QuizAnswerView.vue'
import QuizResultView from './QuizResultView.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import {
  getQuizAttempt,
  getQuizDetail,
  getQuizzesBySpace,
  submitQuiz
} from '@/api/space'
import {
  buildSubmitAnswersPayload,
  convertQuizDetail,
  isQuizAlreadyAttemptedError,
  mapEvaluationResult
} from '@/utils/quiz-adapter'

export default {
  name: 'QuizPanel',
  components: {
    QuizListView,
    QuizAnswerView,
    QuizResultView,
    UToast
  },
  props: {
    spaceId: {
      type: [String, Number],
      default: ''
    }
  },
  data() {
    return {
      viewMode: 'list',
      quizzesLoading: false,
      quizzesError: '',
      quizzes: [],

      activeQuiz: null,
      quizDetailLoading: false,
      quizDetailError: '',
      quizDetail: null,
      submittingAnswers: false,

      resultLoading: false,
      resultError: '',
      resultData: null,

      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },
  computed: {
    quizTitle() {
      if (this.quizDetail && this.quizDetail.title) return this.quizDetail.title
      if (this.activeQuiz && this.activeQuiz.title) return this.activeQuiz.title
      return ''
    },
    quizQuestions() {
      return this.quizDetail && Array.isArray(this.quizDetail.questions) ? this.quizDetail.questions : []
    }
  },
  watch: {
    spaceId: {
      immediate: true,
      handler() {
        this.resetState()
        if (this.spaceId) {
          this.loadQuizzes()
        }
      }
    }
  },
  methods: {
    showToast(message, type = 'info') {
      this.toast = {
        visible: true,
        message: typeof message === 'string' ? message : String(message || ''),
        type
      }
    },
    resetState() {
      this.viewMode = 'list'
      this.quizzesLoading = false
      this.quizzesError = ''
      this.quizzes = []

      this.activeQuiz = null
      this.quizDetailLoading = false
      this.quizDetailError = ''
      this.quizDetail = null
      this.submittingAnswers = false

      this.resultLoading = false
      this.resultError = ''
      this.resultData = null
    },
    normalizeErrorMessage(error, fallback) {
      if (!error) return fallback
      if (typeof error?.message === 'string') return error.message
      const detailMessage = error?.data?.detail?.message
      if (typeof detailMessage === 'string') return detailMessage
      return fallback
    },
    normalizeQuizList(response) {
      if (Array.isArray(response)) return response
      if (Array.isArray(response?.data)) return response.data
      return []
    },
    async loadQuizzes() {
      if (!this.spaceId) return

      try {
        this.quizzesLoading = true
        this.quizzesError = ''
        const response = await getQuizzesBySpace(this.spaceId)
        this.quizzes = this.normalizeQuizList(response)
      } catch (error) {
        this.quizzes = []
        this.quizzesError = this.normalizeErrorMessage(error, '加载失败，请检查网络后重试')
      } finally {
        this.quizzesLoading = false
      }
    },
    async handleOpenQuiz(quiz) {
      if (!quiz?.id) return

      this.activeQuiz = quiz
      if (quiz.has_attempt) {
        await this.loadQuizResult(quiz.id)
        return
      }
      await this.loadQuizDetail(quiz.id)
    },
    async loadQuizDetail(quizId) {
      this.viewMode = 'answer'
      this.quizDetailLoading = true
      this.quizDetailError = ''
      this.quizDetail = null

      try {
        const response = await getQuizDetail(quizId)
        this.quizDetail = convertQuizDetail(response)
      } catch (error) {
        this.quizDetailError = this.normalizeErrorMessage(error, '加载测试题失败')
      } finally {
        this.quizDetailLoading = false
      }
    },
    async loadQuizResult(quizId) {
      this.viewMode = 'result'
      this.resultLoading = true
      this.resultError = ''
      this.resultData = null

      try {
        const response = await getQuizAttempt(quizId)
        this.resultData = mapEvaluationResult(response)
      } catch (error) {
        this.resultError = this.normalizeErrorMessage(error, '加载评估结果失败')
      } finally {
        this.resultLoading = false
      }
    },
    async retryLoadQuizDetail() {
      const quizId = this.activeQuiz?.id
      if (!quizId) return
      await this.loadQuizDetail(quizId)
    },
    async retryLoadQuizResult() {
      const quizId = this.activeQuiz?.id
      if (!quizId) return
      await this.loadQuizResult(quizId)
    },
    async handleSubmitAnswers({ userAnswers }) {
      if (this.submittingAnswers) return
      if (!this.activeQuiz?.id || !this.quizDetail?.questions?.length) return

      try {
        this.submittingAnswers = true
        const payload = buildSubmitAnswersPayload(this.quizDetail.questions, userAnswers)
        const response = await submitQuiz(this.activeQuiz.id, payload)
        this.resultData = mapEvaluationResult(response)
        this.resultError = ''
        this.resultLoading = false
        this.viewMode = 'result'
        this.loadQuizzes()
      } catch (error) {
        if (isQuizAlreadyAttemptedError(error)) {
          this.showToast('该测验已作答，正在跳转到评估结果', 'info')
          await this.loadQuizResult(this.activeQuiz.id)
          return
        }
        this.showToast(this.normalizeErrorMessage(error, '提交失败，请重试'), 'error')
      } finally {
        this.submittingAnswers = false
      }
    },
    backToList() {
      this.viewMode = 'list'
      this.activeQuiz = null
      this.quizDetailLoading = false
      this.quizDetailError = ''
      this.quizDetail = null
      this.submittingAnswers = false
      this.resultLoading = false
      this.resultError = ''
      this.resultData = null
      this.loadQuizzes()
    }
  }
}
</script>

<style scoped>
.quiz-panel {
  width: 100%;
  height: 100%;
  position: relative;
}

.placeholder-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14rpx;
}

.placeholder-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.78);
}

.placeholder-sub {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.45);
}
</style>
