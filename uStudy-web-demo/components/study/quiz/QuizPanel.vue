<template>
  <view class="quiz-panel">
    <view v-if="!spaceId" class="placeholder-wrap">
      <text class="placeholder-text">请先选择学习空间</text>
      <text class="placeholder-sub">选择左侧学习空间后可查看测试题</text>
    </view>

    <template v-else>
      <QuizListView
        v-if="viewMode === 'list'"
        :loading="quizzesLoading"
        :load-error="quizzesError"
        :quizzes="quizzes"
        :assignments="assignments"
        @refresh="loadQuizzes"
        @open="handleOpenItem"
      />

      <QuizAnswerView
        v-else-if="viewMode === 'answer'"
        :quiz-title="itemTitle"
        :item-kind="activeItemKind"
        :item-id="activeItem?.id || ''"
        :due-at="itemDetail?.dueAt || activeItem?.due_at || ''"
        :questions="itemQuestions"
        :loading="itemDetailLoading"
        :load-error="itemDetailError"
        :submitting="submittingAnswers"
        :initial-answers="itemInitialAnswers"
        :initial-question-index="itemInitialQuestionIndex"
        :initial-state-key="itemInitialStateKey"
        :draft-saving="draftSaving"
        :draft-save-error="draftSaveError"
        :draft-saved-at="draftSavedAt"
        @back="handleAnswerBack"
        @retry="retryLoadItemDetail"
        @state-change="handleAnswerStateChange"
        @submit="handleSubmitAnswers"
      />

      <QuizResultView
        v-else
        :loading="resultLoading"
        :load-error="resultError"
        :result-data="resultData"
        :item-kind="activeItemKind"
        @back="backToList"
        @retry="retryLoadItemResult"
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
  saveQuizDraft,
  submitQuizAsync
} from '@/api/space'
import {
  getAssignmentDetail,
  getAssignmentSubmission,
  getAssignmentsBySpace,
  saveAssignmentDraft,
  submitAssignment
} from '@/api/assignments'
import {
  buildDraftSavePayload,
  buildSubmitAnswersPayload,
  convertQuizDetail,
  isQuizAlreadyAttemptedError,
  mapEvaluationResult
} from '@/utils/quiz-adapter'
import {
  buildAssignmentDraftPayload,
  buildAssignmentSubmitPayload,
  convertAssignmentDetail,
  isAssignmentLockedError,
  mapAssignmentSubmission,
  normalizeAssignmentListItem,
  sortAssignments,
  unwrapAssignmentList
} from '@/utils/assignment-adapter'

export default {
  name: 'QuizPanel',
  components: { QuizListView, QuizAnswerView, QuizResultView, UToast },
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
      assignments: [],
      activeItem: null,
      itemDetailLoading: false,
      itemDetailError: '',
      itemDetail: null,
      itemInitialStateKey: '',
      submittingAnswers: false,
      answerDraftState: null,
      draftSaving: false,
      draftSaveError: '',
      draftSavedAt: '',
      draftSaveTimer: null,
      draftSaveRequestId: 0,
      resultLoading: false,
      resultError: '',
      resultData: null,
      resultPollTimer: null,
      resultPollAttempts: 0,
      toast: { visible: false, message: '', type: 'info' }
    }
  },
  computed: {
    activeItemKind() {
      return this.activeItem?.item_kind === 'assignment' ? 'assignment' : 'quiz'
    },
    itemTitle() {
      return this.itemDetail?.title || this.activeItem?.title || ''
    },
    itemQuestions() {
      return Array.isArray(this.itemDetail?.questions) ? this.itemDetail.questions : []
    },
    itemInitialAnswers() {
      return this.itemDetail?.draftUserAnswers || {}
    },
    itemInitialQuestionIndex() {
      return Number.isFinite(this.itemDetail?.currentQuestionIndex) ? this.itemDetail.currentQuestionIndex : 0
    }
  },
  watch: {
    spaceId: {
      immediate: true,
      handler() {
        this.resetState()
        if (this.spaceId) this.loadQuizzes()
      }
    }
  },
  beforeUnmount() {
    this.clearDraftSaveTimer()
    this.clearResultPollTimer()
  },
  methods: {
    showToast(message, type = 'info') {
      this.toast = { visible: true, message: String(message || ''), type }
    },
    normalizeErrorMessage(error, fallback) {
      const detail = error?.data?.detail
      if (typeof detail === 'string') return detail
      if (typeof detail?.message === 'string') return detail.message
      if (typeof error?.message === 'string') return error.message
      return fallback
    },
    normalizeQuizList(response) {
      if (Array.isArray(response)) return response
      if (Array.isArray(response?.data)) return response.data
      return []
    },
    resetState() {
      this.clearDraftSaveTimer()
      this.clearResultPollTimer()
      this.viewMode = 'list'
      this.quizzesLoading = false
      this.quizzesError = ''
      this.quizzes = []
      this.assignments = []
      this.resetActiveState()
    },
    resetActiveState() {
      this.activeItem = null
      this.itemDetailLoading = false
      this.itemDetailError = ''
      this.itemDetail = null
      this.itemInitialStateKey = ''
      this.submittingAnswers = false
      this.answerDraftState = null
      this.draftSaving = false
      this.draftSaveError = ''
      this.draftSavedAt = ''
      this.draftSaveRequestId = 0
      this.resultLoading = false
      this.resultError = ''
      this.resultData = null
      this.resultPollAttempts = 0
    },
    clearDraftSaveTimer() {
      if (!this.draftSaveTimer) return
      clearTimeout(this.draftSaveTimer)
      this.draftSaveTimer = null
    },
    clearResultPollTimer() {
      if (!this.resultPollTimer) return
      clearTimeout(this.resultPollTimer)
      this.resultPollTimer = null
    },
    cloneDraftState(state) {
      if (!state) return null
      return {
        currentQuestionIndex: Number.isFinite(state.currentQuestionIndex) ? state.currentQuestionIndex : 0,
        userAnswers: JSON.parse(JSON.stringify(state.userAnswers || {}))
      }
    },
    countAnsweredAnswers(userAnswers) {
      return Object.values(userAnswers || {}).filter((answer) => {
        if (answer === undefined || answer === null) return false
        if (Array.isArray(answer)) return answer.length > 0
        if (typeof answer === 'string') return answer.trim().length > 0
        if (typeof answer === 'object' && typeof answer.source === 'string') return answer.source.trim().length > 0
        return true
      }).length
    },
    shouldPersistDraft(state) {
      if (!state) return false
      const hasDraft = this.itemDetail?.attemptStatus === 'in_progress' || this.activeItem?.attempt_status === 'in_progress'
      return hasDraft || this.countAnsweredAnswers(state.userAnswers) > 0 || state.currentQuestionIndex > 0
    },
    updateLocalDraftMeta(draftState, draftUpdatedAt) {
      const answeredCount = this.countAnsweredAnswers(draftState?.userAnswers)
      if (this.itemDetail) {
        this.itemDetail = {
          ...this.itemDetail,
          attemptStatus: 'in_progress',
          currentQuestionIndex: draftState?.currentQuestionIndex || 0,
          draftUpdatedAt: draftUpdatedAt || this.itemDetail.draftUpdatedAt
        }
      }
      if (this.activeItem) {
        this.activeItem = {
          ...this.activeItem,
          has_attempt: true,
          attempt_status: 'in_progress',
          draft_answer_count: answeredCount,
          draft_updated_at: draftUpdatedAt || this.activeItem.draft_updated_at
        }
      }
      const update = (item) => String(item.id) === String(this.activeItem?.id)
        ? {
          ...item,
          has_attempt: true,
          attempt_status: 'in_progress',
          draft_answer_count: answeredCount,
          draft_updated_at: draftUpdatedAt || item.draft_updated_at
        }
        : item
      if (this.activeItemKind === 'assignment') this.assignments = this.assignments.map(update)
      else this.quizzes = this.quizzes.map(update)
    },
    async persistDraft(state, { silent = true, force = false } = {}) {
      if (!this.activeItem?.id || !this.itemQuestions.length) return true
      const snapshot = this.cloneDraftState(state || this.answerDraftState)
      if (!snapshot || (!force && !this.shouldPersistDraft(snapshot))) return true
      const requestId = ++this.draftSaveRequestId
      this.draftSaving = true
      this.draftSaveError = ''
      try {
        const isAssignment = this.activeItemKind === 'assignment'
        const payload = isAssignment
          ? buildAssignmentDraftPayload(this.itemQuestions, snapshot.userAnswers, snapshot.currentQuestionIndex)
          : buildDraftSavePayload(this.itemQuestions, snapshot.userAnswers, snapshot.currentQuestionIndex)
        const response = isAssignment
          ? await saveAssignmentDraft(this.activeItem.id, payload)
          : await saveQuizDraft(this.activeItem.id, payload)
        if (requestId !== this.draftSaveRequestId) return true
        const savedAt = response?.draft_updated_at || new Date().toISOString()
        this.draftSavedAt = savedAt
        this.updateLocalDraftMeta(snapshot, savedAt)
        return true
      } catch (error) {
        if (this.activeItemKind === 'quiz' && isQuizAlreadyAttemptedError(error)) return true
        if (this.activeItemKind === 'assignment' && isAssignmentLockedError(error)) return true
        if (requestId !== this.draftSaveRequestId) return false
        this.draftSaveError = this.normalizeErrorMessage(error, '暂存失败，请稍后重试')
        if (!silent) this.showToast(this.draftSaveError, 'error')
        return false
      } finally {
        if (requestId === this.draftSaveRequestId) this.draftSaving = false
      }
    },
    scheduleDraftSave(state) {
      const snapshot = this.cloneDraftState(state)
      if (!snapshot || !this.shouldPersistDraft(snapshot)) return
      if (this.draftSaveTimer) return
      this.draftSaveTimer = setTimeout(() => {
        this.draftSaveTimer = null
        this.persistDraft(this.answerDraftState, { silent: true }).finally(() => {
          if (this.viewMode === 'answer' && this.shouldPersistDraft(this.answerDraftState)) {
            this.scheduleDraftSave(this.answerDraftState)
          }
        })
      }, 30000)
    },
    handleAnswerStateChange(state) {
      this.answerDraftState = this.cloneDraftState(state)
      if (state?.reason !== 'init') {
        this.draftSaveError = ''
        this.scheduleDraftSave(state)
      }
    },
    async loadQuizzes() {
      if (!this.spaceId) return
      this.quizzesLoading = true
      this.quizzesError = ''
      try {
        const [quizResult, assignmentResult] = await Promise.allSettled([
          getQuizzesBySpace(this.spaceId),
          getAssignmentsBySpace(this.spaceId)
        ])
        this.quizzes = quizResult.status === 'fulfilled'
          ? this.normalizeQuizList(quizResult.value).map((quiz) => ({ ...quiz, item_kind: 'quiz' }))
          : []
        this.assignments = assignmentResult.status === 'fulfilled'
          ? sortAssignments(unwrapAssignmentList(assignmentResult.value).map(normalizeAssignmentListItem))
          : []
        if (quizResult.status === 'rejected' && assignmentResult.status === 'rejected') {
          throw quizResult.reason || assignmentResult.reason
        }
        if (quizResult.status === 'rejected') this.showToast('自主测试暂时加载失败，教师作业仍可使用', 'info')
        if (assignmentResult.status === 'rejected') this.showToast('教师作业暂时加载失败，自主测试仍可使用', 'info')
      } catch (error) {
        this.quizzes = []
        this.assignments = []
        this.quizzesError = this.normalizeErrorMessage(error, '加载失败，请检查网络后重试')
      } finally {
        this.quizzesLoading = false
      }
    },
    async handleOpenItem(item) {
      if (!item?.id) return
      if (item.item_kind === 'assignment') await this.handleOpenAssignment(item)
      else await this.handleOpenQuiz(item)
    },
    async handleOpenQuiz(quiz) {
      const attemptStatus = quiz.attempt_status
      if (attemptStatus === 'pending' || attemptStatus === 'evaluating') {
        this.showToast('该测验正在评估中，请稍后查看结果', 'info')
        return
      }
      this.activeItem = { ...quiz, item_kind: 'quiz' }
      if (attemptStatus === 'in_progress' || !quiz.has_attempt) await this.loadItemDetail(quiz.id)
      else await this.loadItemResult(quiz.id)
    },
    async handleOpenAssignment(assignment) {
      this.activeItem = { ...assignment, item_kind: 'assignment' }
      if (assignment.attempt_status === 'missed') {
        this.showToast('该作业已截止，且未提交答卷', 'info')
        return
      }
      if (['evaluating', 'failed', 'completed'].includes(assignment.attempt_status)) await this.loadItemResult(assignment.id)
      else await this.loadItemDetail(assignment.id)
    },
    async loadItemDetail(itemId) {
      this.viewMode = 'answer'
      this.itemDetailLoading = true
      this.itemDetailError = ''
      this.itemDetail = null
      this.itemInitialStateKey = ''
      this.answerDraftState = null
      this.draftSaveError = ''
      this.draftSavedAt = ''
      this.clearDraftSaveTimer()
      this.clearResultPollTimer()
      try {
        const isAssignment = this.activeItemKind === 'assignment'
        const response = isAssignment ? await getAssignmentDetail(itemId) : await getQuizDetail(itemId)
        const detail = isAssignment ? convertAssignmentDetail(response) : convertQuizDetail(response)
        this.itemDetail = detail
        this.answerDraftState = this.cloneDraftState({
          currentQuestionIndex: detail.currentQuestionIndex,
          userAnswers: detail.draftUserAnswers
        })
        this.draftSavedAt = detail.draftUpdatedAt || ''
        this.itemInitialStateKey = `${this.activeItemKind}:${detail.id || itemId}:${detail.attemptStatus || 'new'}:${detail.draftUpdatedAt || 'fresh'}`
      } catch (error) {
        this.itemDetailError = this.normalizeErrorMessage(error, this.activeItemKind === 'assignment' ? '加载教师作业失败' : '加载测试题失败')
      } finally {
        this.itemDetailLoading = false
      }
    },
    async loadItemResult(itemId, { background = false } = {}) {
      const isAssignment = this.activeItemKind === 'assignment'
      this.viewMode = 'result'
      if (!background) {
        this.resultLoading = true
        this.resultError = ''
        this.resultData = null
        this.resultPollAttempts = 0
        this.clearResultPollTimer()
      }
      try {
        const response = isAssignment ? await getAssignmentSubmission(itemId) : await getQuizAttempt(itemId)
        this.resultData = isAssignment ? mapAssignmentSubmission(response) : mapEvaluationResult(response)
        this.resultError = ''
        if (isAssignment && this.resultData.status === 'evaluating') {
          this.resultPollAttempts += 1
          this.scheduleAssignmentResultPoll(itemId)
        } else {
          this.clearResultPollTimer()
          if (background && isAssignment && this.resultData.status === 'completed') {
            this.showToast('AI 初评已完成', 'success')
            this.loadQuizzes()
          }
        }
      } catch (error) {
        if (!background) {
          this.resultError = this.normalizeErrorMessage(error, isAssignment ? '加载作业结果失败' : '加载评估结果失败')
        } else if (isAssignment) {
          this.resultPollAttempts += 1
          this.scheduleAssignmentResultPoll(itemId, 5000)
        }
      } finally {
        if (!background) this.resultLoading = false
      }
    },
    scheduleAssignmentResultPoll(assignmentId, delay = 3000) {
      this.clearResultPollTimer()
      this.resultPollTimer = setTimeout(() => {
        this.resultPollTimer = null
        if (this.viewMode === 'result' && this.activeItemKind === 'assignment') {
          this.loadItemResult(assignmentId, { background: true })
        }
      }, delay)
    },
    retryLoadItemDetail() {
      if (this.activeItem?.id) this.loadItemDetail(this.activeItem.id)
    },
    retryLoadItemResult() {
      if (this.activeItem?.id) this.loadItemResult(this.activeItem.id)
    },
    async handleAnswerBack() {
      this.clearDraftSaveTimer()
      if (this.shouldPersistDraft(this.answerDraftState)) {
        const saved = await this.persistDraft(this.answerDraftState, { silent: false, force: true })
        if (!saved) return
      }
      this.backToList()
    },
    async handleSubmitAnswers({ userAnswers }) {
      if (this.submittingAnswers || !this.activeItem?.id || !this.itemQuestions.length) return
      this.clearDraftSaveTimer()
      this.submittingAnswers = true
      try {
        const isAssignment = this.activeItemKind === 'assignment'
        const payload = isAssignment
          ? buildAssignmentSubmitPayload(this.itemQuestions, userAnswers)
          : buildSubmitAnswersPayload(this.itemQuestions, userAnswers)
        if (isAssignment) {
          await submitAssignment(this.activeItem.id, payload)
          this.showToast('作业已提交，AI 正在初评', 'success')
          await this.loadItemResult(this.activeItem.id)
        } else {
          await submitQuizAsync(this.activeItem.id, payload)
          this.showToast('提交成功，AI 正在后台评估', 'success')
          await this.loadQuizzes()
          this.backToList()
        }
      } catch (error) {
        if (this.activeItemKind === 'assignment' && isAssignmentLockedError(error)) {
          const code = error?.data?.detail?.code || error?.code
          if (code === 'ASSIGNMENT_DEADLINE_PASSED' || code === 'ASSIGNMENT_CLOSED') {
            this.showToast('作业已截止，无法继续提交', 'error')
            this.backToList()
          } else {
            this.showToast('作业已提交，正在查看批改进度', 'info')
            await this.loadItemResult(this.activeItem.id)
          }
          return
        }
        const code = error?.data?.detail?.code || error?.code
        if (code === 'QUIZ_ATTEMPT_LOCKED') {
          this.showToast('该测验已进入评估队列，请返回列表查看状态', 'info')
          await this.loadQuizzes()
          this.backToList()
          return
        }
        if (isQuizAlreadyAttemptedError(error)) {
          this.showToast('该测验已作答，正在跳转到评估结果', 'info')
          await this.loadItemResult(this.activeItem.id)
          return
        }
        this.showToast(this.normalizeErrorMessage(error, '提交失败，请重试'), 'error')
      } finally {
        this.submittingAnswers = false
      }
    },
    navigateToQuizResult(quizId) {
      if (!quizId) return
      this.activeItem = { id: quizId, item_kind: 'quiz' }
      this.loadItemResult(quizId)
    },
    navigateToAssignmentResult(assignmentId) {
      if (!assignmentId) return
      this.activeItem = { id: assignmentId, item_kind: 'assignment' }
      this.loadItemResult(assignmentId)
    },
    backToList() {
      this.clearDraftSaveTimer()
      this.clearResultPollTimer()
      this.viewMode = 'list'
      this.resetActiveState()
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
