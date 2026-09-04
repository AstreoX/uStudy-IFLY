import {
  buildDraftSavePayload,
  buildInitialUserAnswers,
  buildSubmitAnswersPayload,
  convertQuestion,
  difficultyLabel,
  formatAnswer,
  formatQuizDate
} from './quiz-adapter'

const GRADING_STATUSES = new Set(['submitted', 'pending', 'queued', 'grading', 'evaluating'])
const COMPLETED_STATUSES = new Set(['graded', 'provisional', 'reviewed', 'completed'])

function firstArray(...candidates) {
  return candidates.find(Array.isArray) || []
}

function finiteNumber(...values) {
  const value = values.find((item) => Number.isFinite(item))
  return Number.isFinite(value) ? value : null
}

function normalizeSubmissionStatus(source) {
  const raw = String(
    source?.submission_status ||
    source?.attempt_status ||
    source?.submission?.status ||
    ''
  ).toLowerCase()

  if (raw === 'draft' || raw === 'in_progress') return 'in_progress'
  if (GRADING_STATUSES.has(raw)) return 'evaluating'
  if (COMPLETED_STATUSES.has(raw)) return 'completed'
  if (raw === 'failed' || raw === 'grading_failed') return 'failed'
  if (raw === 'missed' || raw === 'expired') return 'missed'
  return ''
}

export function unwrapAssignmentList(response) {
  return firstArray(response, response?.items, response?.assignments, response?.data)
}

export function isAssignmentOverdue(assignment, now = Date.now()) {
  if (!assignment?.due_at || assignment?.attempt_status === 'completed') return false
  const dueTime = new Date(assignment.due_at).getTime()
  return Number.isFinite(dueTime) && dueTime <= now
}

export function isAssignmentUrgent(assignment, now = Date.now()) {
  if (!assignment?.due_at || assignment?.attempt_status === 'completed') return false
  const dueTime = new Date(assignment.due_at).getTime()
  if (!Number.isFinite(dueTime)) return false
  const remaining = dueTime - now
  return remaining > 0 && remaining <= 24 * 60 * 60 * 1000
}

export function normalizeAssignmentListItem(item) {
  const attemptStatus = normalizeSubmissionStatus(item)
  const dueAt = item?.effective_due_at || item?.effective_deadline || item?.due_at || item?.deadline || ''
  const score = finiteNumber(
    item?.final_score,
    item?.submission?.final_score,
    item?.provisional_score,
    item?.auto_score,
    item?.submission?.provisional_score,
    item?.submission?.auto_score
  )
  const totalScore = finiteNumber(item?.total_score, item?.max_score, item?.submission?.total_score)
  const hasAttempt = Boolean(
    item?.has_submission ||
    item?.has_attempt ||
    item?.submission ||
    attemptStatus
  )

  const normalized = {
    ...item,
    id: item?.id ? String(item.id) : '',
    item_kind: 'assignment',
    title: item?.title || '未命名作业',
    topic: item?.instructions || item?.description || item?.requirements || item?.topic || '当前课程空间',
    difficulty: item?.difficulty || '',
    total_questions: finiteNumber(item?.total_questions, item?.question_count) || 0,
    created_at: item?.published_at || item?.created_at || '',
    due_at: dueAt,
    assignment_status: item?.assignment_status || item?.status || 'published',
    attempt_status: attemptStatus,
    has_attempt: hasAttempt,
    draft_answer_count: finiteNumber(item?.draft_answer_count, item?.submission?.draft_answer_count) || 0,
    attempt_score: score,
    attempt_total_score: totalScore,
    score_label: finiteNumber(item?.final_score, item?.submission?.final_score) !== null ? '教师最终成绩' : 'AI 初评'
  }

  if ((!normalized.attempt_status || normalized.attempt_status === 'in_progress') && isAssignmentOverdue(normalized)) {
    normalized.attempt_status = 'missed'
  }
  if (!normalized.attempt_status && normalized.assignment_status === 'closed') normalized.attempt_status = 'missed'

  return normalized
}

export function sortAssignments(assignments) {
  const priority = (item) => {
    if (!item.attempt_status && isAssignmentUrgent(item)) return 0
    if (item.attempt_status === 'in_progress') return 1
    if (item.attempt_status === 'evaluating') return 2
    if (item.attempt_status === 'completed') return 3
    if (item.attempt_status === 'failed') return 4
    if (!item.attempt_status) return 5
    return 6
  }

  return [...assignments].sort((a, b) => {
    const priorityDelta = priority(a) - priority(b)
    if (priorityDelta) return priorityDelta
    const aTime = new Date(a.due_at || '9999-12-31').getTime()
    const bTime = new Date(b.due_at || '9999-12-31').getTime()
    return aTime - bTime
  })
}

export function convertAssignmentDetail(detail) {
  const rawQuestions = firstArray(detail?.questions, detail?.assignment?.questions)
  const questions = rawQuestions.map((question, index) => ({
    ...convertQuestion(question, index),
    points: finiteNumber(question?.points, question?.score, question?.max_score) || 0
  }))
  const submission = detail?.submission || {}
  const draftAnswers = firstArray(detail?.draft_answers, submission?.answers, submission?.draft_answers)

  return {
    id: detail?.id ? String(detail.id) : String(detail?.assignment?.id || ''),
    title: detail?.title || detail?.assignment?.title || '',
    description: detail?.description || detail?.instructions || detail?.requirements || detail?.assignment?.description || detail?.assignment?.instructions || '',
    difficulty: detail?.difficulty || detail?.assignment?.difficulty || '',
    dueAt: detail?.effective_due_at || detail?.effective_deadline || detail?.due_at || detail?.deadline || detail?.assignment?.effective_due_at || detail?.assignment?.due_at || '',
    status: detail?.assignment_status || detail?.status || detail?.assignment?.assignment_status || detail?.assignment?.status || 'published',
    totalQuestions: finiteNumber(detail?.total_questions, detail?.question_count) || rawQuestions.length,
    attemptStatus: normalizeSubmissionStatus(detail),
    currentQuestionIndex: finiteNumber(detail?.current_question_index, submission?.current_question_index) || 0,
    draftUpdatedAt: detail?.draft_updated_at || submission?.draft_updated_at || '',
    questions,
    draftUserAnswers: buildInitialUserAnswers(questions, draftAnswers)
  }
}

export function buildAssignmentSubmitPayload(questions, userAnswers) {
  return buildSubmitAnswersPayload(questions, userAnswers)
}

export function buildAssignmentDraftPayload(questions, userAnswers, currentQuestionIndex) {
  return buildDraftSavePayload(questions, userAnswers, currentQuestionIndex)
}

export function mapAssignmentSubmission(response) {
  const submission = response?.submission || response || {}
  const rawStatus = String(
    response?.submission_status ||
    submission?.submission_status ||
    submission?.status ||
    response?.grading_status ||
    ''
  ).toLowerCase()
  const status = normalizeSubmissionStatus({ submission_status: rawStatus }) || rawStatus || 'evaluating'
  const finalScore = finiteNumber(submission?.final_score, response?.final_score)
  const provisionalScore = finiteNumber(
    submission?.provisional_score,
    response?.provisional_score,
    submission?.auto_score,
    response?.auto_score,
    submission?.score,
    response?.score
  )
  const totalScore = finiteNumber(submission?.total_score, response?.total_score, submission?.max_score, response?.max_score) || 0
  const answersReleased = response?.answers_revealed === true || response?.answers_released === true || response?.can_view_answers === true || submission?.answers_revealed === true || submission?.answers_released === true
  const rawResults = firstArray(response?.question_results, submission?.question_results, response?.answers, submission?.answers)

  return {
    id: String(response?.assignment_id || submission?.assignment_id || response?.id || ''),
    itemKind: 'assignment',
    status,
    score: finalScore ?? provisionalScore ?? 0,
    totalScore,
    scoreLabel: finalScore !== null ? '教师最终成绩' : 'AI 初评',
    isFinal: finalScore !== null,
    answersReleased,
    answerReleaseText: answersReleased ? '标准答案已开放' : '标准答案将在截止后开放',
    teacherFeedback: response?.teacher_feedback || submission?.teacher_feedback || '',
    strengths: firstArray(response?.strengths, submission?.strengths),
    weaknesses: firstArray(response?.weaknesses, submission?.weaknesses),
    suggestions: firstArray(response?.suggestions, submission?.suggestions),
    questionResults: rawResults.map((item, index) => {
      const questionType = item?.question_type || item?.type || 'short_answer'
      const maxScore = finiteNumber(item?.max_score, item?.points) || 0
      const score = finiteNumber(item?.final_score, item?.auto_score, item?.score, item?.provisional_score)
      let itemStatus = item?.status
      if (!itemStatus && maxScore > 0 && score !== null) {
        itemStatus = score >= maxScore ? 'correct' : (score > 0 ? 'partial' : 'wrong')
      }
      return {
        id: String(item?.question_id || item?.id || `q-${index + 1}`),
        order: finiteNumber(item?.order_index, item?.order) || index + 1,
        questionType,
        title: item?.question_stem || item?.title || '',
        options: Array.isArray(item?.options) ? item.options : [],
        status: itemStatus || '-',
        score,
        maxScore,
        userAnswer: item?.user_answer || item?.answer || null,
        correctAnswer: answersReleased ? (item?.correct_answer || null) : null,
        aiEvaluation: item?.teacher_feedback || item?.ai_feedback || item?.ai_evaluation || item?.feedback || '',
        userAnswerDisplay: formatAnswer(questionType, item?.user_answer || item?.answer),
        correctAnswerDisplay: answersReleased ? formatAnswer(questionType, item?.correct_answer) : '',
        graderResult: item?.grader_result || item?.oj_result || null,
        publicConfig: item?.public_config || {},
        solution: answersReleased && questionType === 'code' ? (item?.correct_answer || null) : null
      }
    }),
    debugInfo: null
  }
}

export function isAssignmentLockedError(error) {
  const code = error?.data?.detail?.code || error?.code
  return error?.statusCode === 409 || [
    'ASSIGNMENT_ALREADY_SUBMITTED',
    'ASSIGNMENT_SUBMISSION_LOCKED',
    'ASSIGNMENT_DEADLINE_PASSED',
    'ASSIGNMENT_CLOSED',
    'SUBMISSION_LOCKED',
    'ALREADY_SUBMITTED'
  ].includes(code)
}

export { difficultyLabel, formatQuizDate }
