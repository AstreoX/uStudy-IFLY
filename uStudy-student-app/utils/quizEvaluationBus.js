/**
 * Quiz Evaluation Event Bus
 *
 * Buffers pending evaluation results to handle the race condition where
 * the API response arrives before spaceChat's onShow registers its listener.
 * Also triggers system-level push notifications on completion (APP-PLUS only).
 */
const _pending = {}

export function setPendingEvaluation(quizId, data) {
	_pending[quizId] = data
	uni.$emit('quizEvaluationDone', { quizId, ...data })

	// 评估完成时发送系统级通知
	if (data.status === 'success' || data.status === 'already_attempted') {
		showQuizNotification(quizId, data)
	}
}

export function consumeAllPending() {
	const results = { ..._pending }
	Object.keys(_pending).forEach(k => delete _pending[k])
	return results
}

/**
 * 发送系统级本地推送通知（仅 APP-PLUS）
 */
function showQuizNotification(quizId, data) {
	// #ifdef APP-PLUS
	try {
		const body = data.status === 'success'
			? `得分 ${data.result?.score ?? '--'} / ${data.result?.total_score ?? '--'}，点击查看详情`
			: '该测验已作答，点击查看结果'
		const payload = JSON.stringify({ type: 'quiz_evaluation', quizId })
		plus.push.createMessage(body, payload, {
			title: '测试评估完成',
			cover: false,
			when: new Date(),
			sound: 'system',
		})
	} catch (e) {
		console.warn('[QuizEvalBus] Notification failed:', e?.message || e)
	}
	// #endif
}
