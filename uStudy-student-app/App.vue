<script>
	import { useUserStore } from '@/store/user'
	import { useUpdateStore } from '@/store/update'
	import { startTracking, stopTracking } from '@/utils/appUsageTracker'
	import { stopBackgroundMonitor } from '@/utils/backgroundChatMonitor'
	import config from '@/config'

	export default {
		onLaunch: function() {
			// #ifdef APP-PLUS
			this.clearCacheOnVersionChange()
			this.setupSplashTimeout()
			this.setupPushListener()
			this.requestNotificationPermission()
			// #endif

			useUserStore()

			// #ifdef APP-PLUS
			setTimeout(() => {
				const updateStore = useUpdateStore()
				updateStore.checkForUpdates()
			}, 2000)
			// #endif
		},
		onShow: function() {
			startTracking()
		},
		onHide: function() {
			stopTracking()
		},
		methods: {
			setupPushListener() {
				plus.push.addEventListener('click', (msg) => {
					try {
						const data = typeof msg.payload === 'string'
							? JSON.parse(msg.payload)
							: msg.payload
						if (!data) return

						// 测试评估完成通知 → 跳转结果页
						if (data.type === 'quiz_evaluation' && data.quizId) {
							uni.navigateTo({
								url: `/pages/testResult/testResult?quizId=${data.quizId}&fromList=true`
							})
							return
						}

						if (!data.conversationId) return

						stopBackgroundMonitor()

						if (data.chatMode === 'quick_chat') {
							uni.navigateTo({
								url: `/pages/quickChat/quickChat?conversationId=${data.conversationId}`
							})
						} else {
							const query = [
								`conversationId=${data.conversationId}`,
								data.spaceId ? `spaceId=${data.spaceId}` : '',
								data.spaceTitle ? `spaceTitle=${encodeURIComponent(data.spaceTitle)}` : '',
							].filter(Boolean).join('&')
							uni.navigateTo({
								url: `/pages/spaceChat/spaceChat?${query}`
							})
						}
					} catch (e) {
						// Push click handler error — ignore
					}
				}, false)
			},
			clearCacheOnVersionChange() {
				try {
					const versionKey = '__app_cached_version_code__'
					const currentVersion = String(config.APP_VERSION_CODE)
					const lastVersion = uni.getStorageSync(versionKey)

					if (lastVersion && lastVersion !== currentVersion) {
						// 版本变更：清除 WebView 缓存（不影响 localStorage/Storage）
						if (typeof plus !== 'undefined' && plus.navigator) {
							plus.navigator.clearCache()
						}
					}

					// 无论是否清除缓存，都更新记录的版本号
					uni.setStorageSync(versionKey, currentVersion)
				} catch (error) {
					// 缓存清理失败不阻塞启动
				}
			},
			setupSplashTimeout() {
				// 安全网：5 秒后如果 splash 仍未关闭，强制关闭
				try {
					setTimeout(() => {
						if (typeof plus !== 'undefined' && plus.navigator) {
							plus.navigator.closeSplashscreen()
						}
					}, 5000)
				} catch (error) {}
			},
			requestNotificationPermission() {
				try {
					if (plus.os.name !== 'Android') return
					const Build = plus.android.importClass('android.os.Build')
					if (Build.VERSION.SDK_INT < 33) return
					const main = plus.android.runtimeMainActivity()
					const ContextCompat = plus.android.importClass('androidx.core.content.ContextCompat')
					const PERMISSION = 'android.permission.POST_NOTIFICATIONS'
					const granted = ContextCompat.checkSelfPermission(main, PERMISSION)
					if (granted === 0) return
					plus.android.requestPermissions(
						[PERMISSION],
						(result) => {
							const ok = result && result.granted && result.granted.length > 0
							console.log('[App] POST_NOTIFICATIONS permission:', ok ? 'granted' : 'denied')
						},
						(err) => {
							console.warn('[App] Notification permission request failed:', err)
						}
					)
				} catch (e) {
					console.warn('[App] Notification permission check failed:', e)
				}
			}
		}
	}
</script>

<style>
	/* 全局样式 */
	page {
		background-color: #0a0a12;
		min-height: 100vh;
	}

	/* 全局 CSS 变量 */
	:root {
		--color-bg: #0a0a12;
		--color-text-primary: #ffffff;
		--color-text-secondary: #9ca3af;
		--color-progress-green: #22c55e;
		--color-progress-blue: #3b82f6;
		--color-nav-bg: #1a1a1a;
		--color-nav-active: #2563eb;
	}
</style>
