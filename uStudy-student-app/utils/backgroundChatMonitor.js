/**
 * 后台 AI 回复监控服务
 *
 * App 级别的单例服务，当用户在 AI 流式回复过程中切屏或退出对话时，
 * 启动轮询检查 AI 是否已完成回复，完成后发送系统级通知。
 *
 * 优化策略：
 * - 使用 Redis streaming-status API（更快）
 * - 智能轮询间隔：前 30 秒每 3 秒，之后每 8 秒
 * - 最长轮询 5 分钟
 * - Redis 缓存过期时回退到数据库查询
 */
import { getStreamingStatus, checkReplyStatus } from '@/api/chat'

// 轮询配置
const FAST_POLL_INTERVAL = 3000   // 前 30 秒：每 3 秒
const SLOW_POLL_INTERVAL = 8000   // 之后：每 8 秒
const FAST_POLL_DURATION = 30000  // 30 秒后切换到慢速
const MAX_POLL_TIME = 300000      // 最多轮询 5 分钟

// 全局状态
let pollingTimer = null
let maxTimer = null
let activeMonitor = null
let startTime = 0

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
	startTime = Date.now()

	// 开始智能轮询
	scheduleNextPoll()

	// 5 分钟后自动停止（省电）
	maxTimer = setTimeout(() => {
		console.log('[BackgroundMonitor] Max poll time reached, stopping')
		stopBackgroundMonitor()
	}, MAX_POLL_TIME)
}

/**
 * 调度下一次轮询（智能间隔）
 */
function scheduleNextPoll() {
	if (!activeMonitor) return

	const elapsed = Date.now() - startTime
	const interval = elapsed < FAST_POLL_DURATION ? FAST_POLL_INTERVAL : SLOW_POLL_INTERVAL

	pollingTimer = setTimeout(async () => {
		await doPoll()
		if (activeMonitor) {
			scheduleNextPoll()
		}
	}, interval)
}

/**
 * 执行一次轮询检查
 */
async function doPoll() {
	if (!activeMonitor) return
	const { conversationId, userMessageTimestamp } = activeMonitor

	try {
		// 优先使用 Redis streaming-status（更快）
		const status = await getStreamingStatus(conversationId)

		// AI 已完成：is_streaming=false 且有内容
		if (status.partial_content && !status.is_streaming) {
			const preview = status.partial_content.substring(0, 50)
			console.log('[BackgroundMonitor] AI completed (Redis), preview:', preview)
			showSystemNotification(activeMonitor, preview)
			stopBackgroundMonitor()
			return
		}

		// 仍在生成，继续轮询
		if (status.is_streaming) {
			console.log('[BackgroundMonitor] Still streaming, continue polling')
			return
		}

		// Redis 缓存可能已过期（返回空），回退到数据库查询
		const afterTs = userMessageTimestamp / 1000
		const reply = await checkReplyStatus(conversationId, afterTs)
		console.log('[BackgroundMonitor] Fallback to DB, has_reply:', reply.has_reply)
		if (reply.has_reply) {
			showSystemNotification(activeMonitor, reply.preview)
			stopBackgroundMonitor()
		}
	} catch (err) {
		console.warn('[BackgroundMonitor] Poll failed:', err?.message || err)
	}
}

/**
 * 停止后台监控
 */
export function stopBackgroundMonitor() {
	if (pollingTimer) {
		clearTimeout(pollingTimer)
		pollingTimer = null
	}
	if (maxTimer) {
		clearTimeout(maxTimer)
		maxTimer = null
	}
	activeMonitor = null
	startTime = 0
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
