const QUESTION_TYPE_MAP = {
  single_choice: 'single',
  multiple_choice: 'multiple',
  true_false: 'truefalse',
  short_answer: 'shortanswer'
}

const OPTION_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

export function convertQuestion(backendQuestion, index = 0) {
  const frontendType = QUESTION_TYPE_MAP[backendQuestion?.question_type] || 'single'
  const correctAnswer = backendQuestion?.correct_answer || {}

  let answer = null
  if (frontendType === 'single') {
    answer = typeof correctAnswer.index === 'number' ? correctAnswer.index : null
  } else if (frontendType === 'multiple') {
    answer = Array.isArray(correctAnswer.indices) ? correctAnswer.indices : []
  } else if (frontendType === 'truefalse') {
    answer = typeof correctAnswer.value === 'boolean' ? correctAnswer.value : null
  } else if (frontendType === 'shortanswer') {
    answer = correctAnswer.reference || null
  }

  return {
    id: String(backendQuestion?.id || `q-${index + 1}`),
    type: frontendType,
    backendType: backendQuestion?.question_type || 'single_choice',
    order: Number.isFinite(backendQuestion?.order_index) ? backendQuestion.order_index : index + 1,
    title: backendQuestion?.question_stem || '',
    options: Array.isArray(backendQuestion?.options) ? backendQuestion.options : [],
    answer
  }
}

export function convertQuizDetail(quizDetail) {
  const rawQuestions = Array.isArray(quizDetail?.questions) ? quizDetail.questions : []
  return {
    id: quizDetail?.id ? String(quizDetail.id) : '',
    title: quizDetail?.title || '',
    topic: quizDetail?.topic || '',
    difficulty: quizDetail?.difficulty || '',
    totalQuestions: Number.isFinite(quizDetail?.total_questions) ? quizDetail.total_questions : rawQuestions.length,
    questions: rawQuestions.map((q, index) => convertQuestion(q, index))
  }
}

export function buildSubmitAnswersPayload(questions, userAnswers) {
  const safeQuestions = Array.isArray(questions) ? questions : []
  const safeUserAnswers = userAnswers || {}

  const answers = safeQuestions.map((question) => {
    const userAnswer = safeUserAnswers[question.id]
    let answer = null

    if (question.type === 'single') {
      answer = typeof userAnswer === 'number' ? { index: userAnswer } : null
    } else if (question.type === 'multiple') {
      answer = Array.isArray(userAnswer) && userAnswer.length > 0 ? { indices: userAnswer } : null
    } else if (question.type === 'truefalse') {
      answer = typeof userAnswer === 'boolean' ? { value: userAnswer } : null
    } else if (question.type === 'shortanswer') {
      const text = typeof userAnswer === 'string' ? userAnswer.trim() : ''
      answer = text ? { text } : null
    }

    return {
      question_id: question.id,
      answer
    }
  })

  return { answers }
}

export function formatAnswer(questionType, answer) {
  if (!answer) return '（未作答）'

  if (questionType === 'single_choice') {
    const index = answer.index
    return Number.isFinite(index) ? (OPTION_LABELS[index] || String(index + 1)) : '（未作答）'
  }

  if (questionType === 'multiple_choice') {
    const indices = Array.isArray(answer.indices) ? answer.indices : []
    if (!indices.length) return '（未选择）'
    return indices.map((idx) => OPTION_LABELS[idx] || String(idx + 1)).join('、')
  }

  if (questionType === 'true_false') {
    if (answer.value === true) return '正确'
    if (answer.value === false) return '错误'
    return '（未作答）'
  }

  if (questionType === 'short_answer') {
    return answer.text || answer.reference || '（未作答）'
  }

  try {
    return JSON.stringify(answer)
  } catch (error) {
    return String(answer)
  }
}

export function mapEvaluationResult(result) {
  const questionResults = Array.isArray(result?.question_results)
    ? result.question_results.map((item) => ({
      id: String(item.id),
      order: item.order,
      questionType: item.question_type,
      title: item.title,
      options: Array.isArray(item.options) ? item.options : [],
      status: item.status,
      score: item.score,
      maxScore: item.max_score,
      userAnswer: item.user_answer,
      correctAnswer: item.correct_answer,
      aiEvaluation: item.ai_evaluation,
      userAnswerDisplay: formatAnswer(item.question_type, item.user_answer),
      correctAnswerDisplay: formatAnswer(item.question_type, item.correct_answer)
    }))
    : []

  return {
    id: String(result?.quiz_id || result?.id || ''),
    score: Number.isFinite(result?.score) ? result.score : 0,
    totalScore: Number.isFinite(result?.total_score) ? result.total_score : 0,
    strengths: Array.isArray(result?.strengths) ? result.strengths : [],
    weaknesses: Array.isArray(result?.weaknesses) ? result.weaknesses : [],
    suggestions: Array.isArray(result?.suggestions) ? result.suggestions : [],
    questionResults,
    debugInfo: result?.debug_info || null,
    status: result?.status || 'completed'
  }
}

export function difficultyLabel(level) {
  const map = { easy: '简单', medium: '中等', hard: '困难' }
  return map[level] || level || '-'
}

export function formatQuizDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'

  const month = date.getMonth() + 1
  const day = date.getDate()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${month}月${day}日 ${hours}:${minutes}`
}

export function isQuizAlreadyAttemptedError(error) {
  if (!error) return false

  if (error.statusCode === 409 || error.code === 'QUIZ_ALREADY_ATTEMPTED') {
    return true
  }

  const detailCode = error?.data?.detail?.code
  return detailCode === 'QUIZ_ALREADY_ATTEMPTED'
}
