import { request } from '@/utils/request'
import config from '@/config'
import { getTokens } from '@/utils/storage'

const API_ROOT = '/api/teacher/spaces'

function valueOf(source, ...keys) {
  for (const key of keys) {
    if (source && source[key] !== undefined && source[key] !== null) return source[key]
  }
  return undefined
}

function unwrapList(payload, keys = ['items']) {
  if (Array.isArray(payload)) return payload
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

export function normalizeQuestion(question = {}, index = 0) {
  const type = valueOf(question, 'question_type', 'type') || 'single_choice'
  const correctAnswer = valueOf(question, 'correct_answer', 'answer', 'reference_answer') ?? {}
  let editableAnswer = correctAnswer
  if (correctAnswer && typeof correctAnswer === 'object' && !Array.isArray(correctAnswer)) {
    if (type === 'single_choice') editableAnswer = correctAnswer.index === undefined ? '' : String.fromCharCode(65 + Number(correctAnswer.index))
    else if (type === 'multiple_choice') editableAnswer = (correctAnswer.indices || []).map(item => String.fromCharCode(65 + Number(item))).join(',')
    else if (type === 'true_false') editableAnswer = correctAnswer.value === true ? '正确' : correctAnswer.value === false ? '错误' : ''
    else if (type === 'short_answer') editableAnswer = correctAnswer.reference || correctAnswer.text || ''
    else if (type === 'code') editableAnswer = correctAnswer.explanation || correctAnswer.reference || ''
  }
  return {
    ...question,
    id: String(valueOf(question, 'id', 'question_id') || `new-${index}`),
    question_type: type,
    prompt: valueOf(question, 'prompt', 'question_stem', 'content', 'question') || '',
    options: Array.isArray(question.options) ? question.options : [],
    answer: editableAnswer,
    correct_answer: correctAnswer,
    rubric: valueOf(question, 'rubric', 'scoring_rubric') || '',
    points: Number(valueOf(question, 'points', 'max_score', 'score') || 0),
    order_index: Number(valueOf(question, 'order_index', 'order', 'position') ?? index),
    grader_type: valueOf(question, 'grader_type') || (type === 'short_answer' ? 'ai' : type === 'code' ? 'oj' : 'rule'),
    grader_config: valueOf(question, 'grader_config') || {},
    public_config: valueOf(question, 'public_config') || {},
    reference_solution: correctAnswer?.reference_solution || valueOf(question, 'reference_solution') || null,
    oj_validation_status: valueOf(question, 'oj_validation_status', 'validation_status') || question?.grader_config?.validation_status || 'unvalidated'
  }
}

export function normalizeAssignment(assignment = {}) {
  const questions = unwrapList(assignment, ['questions']).map(normalizeQuestion)
  return {
    ...assignment,
    id: String(valueOf(assignment, 'id', 'assignment_id') || ''),
    title: valueOf(assignment, 'title', 'name') || '未命名作业',
    instructions: valueOf(assignment, 'instructions', 'requirements', 'description') || '',
    difficulty: valueOf(assignment, 'difficulty') || 'medium',
    status: valueOf(assignment, 'status') || 'draft',
    version: Number(valueOf(assignment, 'version') || 1),
    deadline: valueOf(assignment, 'deadline', 'due_at') || '',
    published_at: valueOf(assignment, 'published_at') || '',
    created_at: valueOf(assignment, 'created_at') || '',
    updated_at: valueOf(assignment, 'updated_at') || '',
    question_count: Number(valueOf(assignment, 'question_count', 'total_questions') ?? questions.length),
    total_points: Number(valueOf(assignment, 'total_points', 'total_score', 'max_score') ?? questions.reduce((sum, item) => sum + item.points, 0)),
    recipient_count: Number(valueOf(assignment, 'recipient_count', 'students_total') || 0),
    submitted_count: Number(valueOf(assignment, 'submitted_count', 'submissions_count') || 0),
    graded_count: Number(valueOf(assignment, 'graded_count') || 0),
    review_required_count: Number(valueOf(assignment, 'review_required_count') || 0),
    questions
  }
}

export function normalizeSubmission(submission = {}) {
  return {
    ...submission,
    id: String(valueOf(submission, 'id', 'submission_id') || ''),
    student_id: String(valueOf(submission, 'student_id', 'user_id') || ''),
    student_name: valueOf(submission, 'student_name', 'nickname', 'username') || '学生',
    student_identifier: valueOf(submission, 'student_identifier', 'email', 'username') || '',
    status: valueOf(submission, 'status', 'submission_status', 'grading_status') || 'not_submitted',
    submitted_at: valueOf(submission, 'submitted_at') || '',
    effective_deadline: valueOf(submission, 'effective_deadline', 'effective_due_at', 'due_at', 'deadline') || '',
    provisional_score: valueOf(submission, 'provisional_score'),
    final_score: valueOf(submission, 'final_score'),
    review_required: Boolean(valueOf(submission, 'review_required')),
    teacher_comment: valueOf(submission, 'teacher_comment', 'teacher_feedback', 'comment') || '',
    answers: unwrapList(submission, ['answers', 'question_results', 'items'])
  }
}

export async function listTeacherAssignments(spaceId) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/assignments`, method: 'GET' })
  return unwrapList(payload, ['assignments', 'items']).map(normalizeAssignment)
}

export async function generateTeacherAssignment(spaceId, data) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/generate`, method: 'POST', data })
}

export function getAssignmentJob(spaceId, jobId) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/jobs/${jobId}`, method: 'GET' })
}

export function retryAssignmentQuestion(spaceId, jobId, questionIndex) {
  return request({
    url: `${API_ROOT}/${spaceId}/assignments/jobs/${jobId}/questions/${questionIndex}/retry`,
    method: 'POST'
  })
}

export async function getTeacherAssignment(spaceId, assignmentId) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}`, method: 'GET' })
  return normalizeAssignment(payload?.assignment || payload)
}

export async function updateTeacherAssignment(spaceId, assignmentId, data) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}`, method: 'PATCH', data })
  return normalizeAssignment(payload?.assignment || payload)
}

export function deleteTeacherAssignment(spaceId, assignmentId) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}`, method: 'DELETE' })
}

export function publishTeacherAssignment(spaceId, assignmentId) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/publish`, method: 'POST' })
}

export function closeTeacherAssignment(spaceId, assignmentId) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/close`, method: 'POST' })
}

export async function listAssignmentSubmissions(spaceId, assignmentId) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/submissions`, method: 'GET' })
  return {
    ...payload,
    submissions: unwrapList(payload, ['submissions', 'items', 'recipients']).map(normalizeSubmission)
  }
}

export async function getAssignmentSubmission(spaceId, submissionId) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/assignments/submissions/${submissionId}`, method: 'GET' })
  return normalizeSubmission(payload?.submission || payload)
}

export function reviewAssignmentSubmission(spaceId, submissionId, data) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/submissions/${submissionId}/review`, method: 'PATCH', data })
}

export function regradeAssignmentSubmission(spaceId, submissionId) {
  return request({ url: `${API_ROOT}/${spaceId}/assignments/submissions/${submissionId}/regrade`, method: 'POST' })
}

export function extendAssignmentDeadline(spaceId, assignmentId, studentId, deadline) {
  return request({
    url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/recipients/${studentId}/deadline`,
    method: 'PATCH',
    data: { due_at: deadline }
  })
}


export function getOjProblem(spaceId, assignmentId, questionId) {
  return request({
    url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/questions/${questionId}/oj-problem`,
    method: 'GET'
  })
}

export function updateOjProblem(spaceId, assignmentId, questionId, data) {
  return request({
    url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/questions/${questionId}/oj-problem`,
    method: 'PUT',
    data,
    timeout: 30000
  })
}

export function validateOjProblem(spaceId, assignmentId, questionId) {
  return request({
    url: `${API_ROOT}/${spaceId}/assignments/${assignmentId}/questions/${questionId}/oj-problem/validate`,
    method: 'POST',
    timeout: 30000
  })
}

export function importOjProblemZip(spaceId, assignmentId, questionId, filePath) {
  const tokens = getTokens()
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${config.API_BASE_URL || ''}${API_ROOT}/${spaceId}/assignments/${assignmentId}/questions/${questionId}/oj-problem/import`,
      filePath,
      name: 'file',
      header: tokens?.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {},
      timeout: 60000,
      success: (response) => {
        let payload = response.data
        try { payload = typeof response.data === 'string' ? JSON.parse(response.data) : response.data } catch (_) {}
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(payload)
        else reject({ statusCode: response.statusCode, data: payload, message: payload?.detail?.message || payload?.detail || payload?.message || '测试数据导入失败' })
      },
      fail: (error) => reject({ statusCode: 0, data: error, message: error?.errMsg || '测试数据上传失败' })
    })
  })
}
