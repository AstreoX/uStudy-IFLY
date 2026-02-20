/**
 * 后台 AI 回复监控服务
 *
 * App 级别的单例服务，当用户在 AI 流式回复过程中切屏或退出对话时，
 * 启动轮询检查 AI 是否已完成回复，完成后发送系统级通知。
 */
import { request } from '@/utils/request'

// 全局状态
let pollingTimer = null
let maxTimer = null
let activeMonitor = null

const POLL_INTERVAL = 5000   // 每 5 秒检查一次
const MAX_POLL_TIME = 120000 // 最多轮询 2 分钟

/**
 * 开始后台监控 AI 回复
 * @param {Object} options
 * @param {string} options.conversationId
 * @param {number} options.userMessageTimestamp - Date.now() 时间戳
 * @param {string} options.chatMode - 'space_chat' | 'quick_chat'
 * @param {string} [options.spaceId] - 学习空间ID（space_chat 模式）
 * @param {string} [options.spaceTitle] - 空间标题
 */
export function startBackgroundMonitor(options) {
	console.log('[BackgroundMonitor] Starting monitor for conversation:', options.conversationId,
		'chatMode:', options.chatMode, 'timestamp:', options.userMessageTimestamp)
	stopBackgroundMonitor()

	activeMonitor = { ...options }
	const afterTs = options.userMessageTimestamp / 1000  // 转 Unix seconds

	pollingTimer = setInterval(async () => {
		try {
			const result = await request({
				url: `/api/conversations/${options.conversationId}/reply-status`,
				method: 'GET',
				data: { after: afterTs },
			})
			console.log('[BackgroundMonitor] Poll result:', result.has_reply, 'preview:', result.preview?.substring(0, 30))
			if (result.has_reply) {
				showSystemNotification(options, result.preview)
				stopBackgroundMonitor()
			}
		} catch (err) {
			console.warn('[BackgroundMonitor] Poll failed:', err?.message || err)
		}
	}, POLL_INTERVAL)

	// 2 分钟后自动停止（省电）
	maxTimer = setTimeout(() => stopBackgroundMonitor(), MAX_POLL_TIME)
}

/**
 * 停止后台监控
 */
export function stopBackgroundMonitor() {
	if (pollingTimer) {
		clearInterval(pollingTimer)
		pollingTimer = null
	}
	if (maxTimer) {
		clearTimeout(maxTimer)
		maxTimer = null
	}
	activeMonitor = null
}

/**
 * 获取当前活跃的监控信息
 */
export function getActiveMonitor() {
	return activeMonitor
}

/**
 * 发送系统级通知
 */
function showSystemNotification(options, preview) {
	// #ifdef APP-PLUS
	const permitted = isNotificationPermitted()
	console.log('[BackgroundMonitor] Attempting notification, permitted:', permitted, 'preview:', preview?.substring(0, 30))
	if (!permitted) {
		console.warn('[BackgroundMonitor] POST_NOTIFICATIONS not granted, notification will be silent')
	}
	try {
		const payload = JSON.stringify({
			conversationId: options.conversationId,
			chatMode: options.chatMode,
			spaceId: options.spaceId || '',
			spaceTitle: options.spaceTitle || '',
		})
		plus.push.createMessage(
			preview || 'AI 已完成回复',
			payload,
			{
				title: 'uStudy',
				cover: false,
				when: new Date(),
				sound: 'system',
			}
		)
		console.log('[BackgroundMonitor] Notification created successfully')
	} catch (e) {
		console.warn('[BackgroundMonitor] Notification failed:', e?.message || e)
	}
	// #endif
}

/**
 * 检查通知权限状态（不请求，权限请求已移至 App.vue onLaunch）
 */
function isNotificationPermitted() {
	// #ifdef APP-PLUS
	try {
		if (plus.os.name !== 'Android') return true
		const Build = plus.android.importClass('android.os.Build')
		if (Build.VERSION.SDK_INT < 33) return true
		const main = plus.android.runtimeMainActivity()
		const ContextCompat = plus.android.importClass('androidx.core.content.ContextCompat')
		const PERMISSION = 'android.permission.POST_NOTIFICATIONS'
		return ContextCompat.checkSelfPermission(main, PERMISSION) === 0
	} catch (e) {
		console.warn('[BackgroundMonitor] Permission check failed:', e?.message || e)
		return true
	}
	// #endif
	// #ifndef APP-PLUS
	return false
	// #endif
}
