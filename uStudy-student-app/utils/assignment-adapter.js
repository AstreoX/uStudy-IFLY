const QUESTION_TYPE_MAP = {
  single_choice: 'single',
  multiple_choice: 'multiple',
  true_false: 'truefalse',
  short_answer: 'shortanswer',
  code: 'code'
}

const GRADING_STATUSES = new Set(['submitted', 'pending', 'queued', 'grading', 'evaluating'])
const COMPLETED_STATUSES = new Set(['graded', 'provisional', 'reviewed', 'completed'])

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function finiteNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback
}

export function normalizeAssignmentStatus(value) {
  const raw = String(value || '').toLowerCase()
  if (raw === 'draft' || raw === 'in_progress') return 'in_progress'
  if (GRADING_STATUSES.has(raw)) return 'evaluating'
  if (COMPLETED_STATUSES.has(raw)) return 'completed'
  if (raw === 'missed' || raw === 'expired' || raw === 'closed') return 'missed'
  if (raw === 'failed' || raw === 'grading_failed') return 'failed'
  return ''
}

export function isAssignmentOverdue(assignment, now = Date.now()) {
  if (!assignment?.due_at || assignment?.attempt_status === 'completed') return false
  const dueTime = new Date(assignment.due_at).getTime()
  return Number.isFinite(dueTime) && dueTime <= now
}

export function normalizeAssignmentListItem(item = {}) {
  let attemptStatus = normalizeAssignmentStatus(item.submission_status || item.attempt_status)
  const dueAt = item.effective_due_at || item.due_at || ''
  if ((attemptStatus === 'in_progress' || !attemptStatus) && (item.answers_revealed || item.assignment_status === 'closed' || isAssignmentOverdue({ due_at: dueAt }))) {
    attemptStatus = 'missed'
  }
  return {
    ...item,
    id: String(item.id || ''),
    item_kind: 'assignment',
    title: item.title || '未命名教师测验',
    instructions: item.instructions || '',
    difficulty: item.difficulty || 'medium',
    total_questions: finiteNumber(item.total_questions),
    total_score: finiteNumber(item.total_score),
    created_at: item.published_at || item.created_at || '',
    due_at: dueAt,
    attempt_status: attemptStatus,
    draft_answer_count: finiteNumber(item.draft_answer_count),
    attempt_score: Number.isFinite(item.final_score) ? item.final_score : item.provisional_score,
    attempt_total_score: finiteNumber(item.total_score),
    score_label: Number.isFinite(item.final_score) ? '教师最终成绩' : 'AI 初评'
  }
}

export function sortAssignments(assignments) {
  const priority = { in_progress: 0, '': 1, evaluating: 2, completed: 3, failed: 4, missed: 5 }
  return [...asArray(assignments)].sort((left, right) => {
    const statusDelta = (priority[left.attempt_status] ?? 9) - (priority[right.attempt_status] ?? 9)
    if (statusDelta) return statusDelta
    return new Date(left.due_at || '9999-12-31').getTime() - new Date(right.due_at || '9999-12-31').getTime()
  })
}

export function convertAssignmentQuestion(question = {}, index = 0) {
  const backendType = question.question_type || 'single_choice'
  return {
    id: String(question.id || `q-${index + 1}`),
    type: QUESTION_TYPE_MAP[backendType] || 'single',
    backendType,
    title: question.question_stem || '',
    options: asArray(question.options),
    order: finiteNumber(question.order_index, index) + 1,
    maxScore: finiteNumber(question.max_score),
    // APP deliberately does not render OJ config, samples, code, or run data.
    isOj: backendType === 'code'
  }
}

export function buildInitialAssignmentAnswers(questions, draftAnswers) {
  const draftMap = new Map(asArray(draftAnswers).map(item => [String(item?.question_id || ''), item?.answer ?? null]))
  return asArray(questions).reduce((answers, question) => {
    const raw = draftMap.get(question.id)
    if (raw == null || question.isOj) return answers
    if (question.type === 'single' && Number.isFinite(raw.index)) answers[question.id] = raw.index
    if (question.type === 'multiple' && Array.isArray(raw.indices)) answers[question.id] = raw.indices
    if (question.type === 'truefalse' && typeof raw.value === 'boolean') answers[question.id] = raw.value
    if (question.type === 'shortanswer' && typeof raw.text === 'string' && raw.text.trim()) answers[question.id] = raw.text
    return answers
  }, {})
}

export function convertAssignmentDetail(detail = {}) {
  const questions = asArray(detail.questions).map(convertAssignmentQuestion)
  return {
    id: String(detail.id || ''),
    title: detail.title || '教师测验',
    instructions: detail.instructions || '',
    dueAt: detail.effective_due_at || detail.due_at || '',
    status: detail.assignment_status || 'published',
    attemptStatus: normalizeAssignmentStatus(detail.submission_status),
    answersRevealed: detail.answers_revealed === true,
    currentQuestionIndex: finiteNumber(detail.current_question_index),
    questions,
    userAnswers: buildInitialAssignmentAnswers(questions, detail.draft_answers),
    // Keep the raw OJ answer opaque. It is never rendered, but preserves a web
    // draft if the student updates non-OJ answers in the app.
    rawDraftAnswers: asArray(detail.draft_answers)
  }
}

function answerForQuestion(question, userAnswers) {
  const value = userAnswers?.[question.id]
  if (question.type === 'single') return Number.isFinite(value) ? { index: value } : null
  if (question.type === 'multiple') return Array.isArray(value) && value.length ? { indices: value } : null
  if (question.type === 'truefalse') return typeof value === 'boolean' ? { value } : null
  if (question.type === 'shortanswer') {
    const text = typeof value === 'string' ? value.trim() : ''
    return text ? { text } : null
  }
  return null
}

export function buildAssignmentDraftPayload(detail, userAnswers, currentQuestionIndex) {
  const visibleAnswers = asArray(detail?.questions)
    .filter(question => !question.isOj)
    .map(question => ({ question_id: question.id, answer: answerForQuestion(question, userAnswers) }))
  const preservedOjAnswers = asArray(detail?.rawDraftAnswers)
    .filter(item => asArray(detail?.questions).some(question => question.id === String(item?.question_id || '') && question.isOj))
  return {
    answers: [...visibleAnswers, ...preservedOjAnswers],
    current_question_index: Number.isFinite(currentQuestionIndex) ? currentQuestionIndex : 0
  }
}

export function buildAssignmentSubmitPayload(detail, userAnswers) {
  return {
    answers: asArray(detail?.questions)
      .filter(question => !question.isOj)
      .map(question => ({ question_id: question.id, answer: answerForQuestion(question, userAnswers) }))
  }
}

export function assignmentHasOj(detail) {
  return asArray(detail?.questions).some(question => question.isOj)
}

export function mapAssignmentSubmission(result = {}) {
  const score = Number.isFinite(result.final_score) ? result.final_score : (result.provisional_score || 0)
  return {
    score,
    total_score: finiteNumber(result.total_score),
    quiz_title: result.title || '教师测验结果',
    strengths: [],
    weaknesses: [],
    suggestions: result.teacher_feedback ? [result.teacher_feedback] : [],
    question_results: asArray(result.question_results).map((item, index) => ({
      id: item.id || item.question_id || `q-${index + 1}`,
      order: finiteNumber(item.order_index, index) + 1,
      question_type: item.question_type,
      title: item.question_stem || '',
      options: asArray(item.options),
      status: item.status,
      score: Number.isFinite(item.final_score) ? item.final_score : (item.auto_score || 0),
      max_score: finiteNumber(item.max_score),
      user_answer: item.question_type === 'code' ? null : item.user_answer,
      correct_answer: item.question_type === 'code' ? null : item.correct_answer,
      ai_evaluation: item.question_type === 'code' ? '编程题请前往网页端查看评测详情。' : (item.feedback || '')
    }))
  }
}
