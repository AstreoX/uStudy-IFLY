<script>
	import { useUserStore } from '@/store/user'
	import { useUpdateStore } from '@/store/update'
	import { startTracking, stopTracking } from '@/utils/appUsageTracker'
	import { stopBackgroundMonitor } from '@/utils/backgroundChatMonitor'
	import { navigateToTarget, resolveAppLaunchTarget, resolveNotificationTarget, savePendingNavigation } from '@/utils/deepLink'
	import config from '@/config'

	export default {
		onLaunch: function(options) {
			// #ifdef APP-PLUS
			this.clearCacheOnVersionChange()
			this.setupSplashTimeout()
			this.setupPushListener()
			this.setupIntentListener()
			this.requestNotificationPermission()
			this.handleExternalLaunch(options, { replace: true, delayMs: 140 })
			// #endif

			useUserStore()

			// #ifdef APP-PLUS
			setTimeout(() => {
				const updateStore = useUpdateStore()
				updateStore.checkForUpdates()
			}, 2000)
			// #endif
		},
		onShow: function(options) {
			startTracking()
			// #ifdef APP-PLUS
			this.handleExternalLaunch(options, { replace: true, delayMs: 60 })
			// #endif
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

						const target = resolveNotificationTarget(data)
						if (!target) return

						stopBackgroundMonitor()
						navigateToTarget(target)
					} catch (e) {
						// Push click handler error — ignore
					}
				}, false)
			},
			setupIntentListener() {
				if (typeof document === 'undefined') return
				document.addEventListener('newintent', () => {
					this.handleExternalLaunch(null, { replace: true, force: true, delayMs: 60 })
				}, false)
			},
			handleExternalLaunch(options, navOptions = {}) {
				try {
					const target = resolveAppLaunchTarget({
						launchOptions: options || {},
						launcher: this.getRuntimeLauncher(),
						runtimeArguments: this.getRuntimeArguments(),
						force: navOptions.force
					})
					if (!target) return
					if (target.url.includes('/pages/test/test') || target.url.includes('/pages/testResult/testResult')) {
						savePendingNavigation({ ...target, openType: 'reLaunch' })
					}
					navigateToTarget(target, {
						replace: navOptions.replace,
						delayMs: navOptions.delayMs
					})
				} catch (_) {}
			},
			getRuntimeLauncher() {
				try {
					return typeof plus !== 'undefined' && plus.runtime
						? plus.runtime.launcher || ''
						: ''
				} catch (_) {
					return ''
				}
			},
			getRuntimeArguments() {
				try {
					return typeof plus !== 'undefined' && plus.runtime
						? plus.runtime.arguments || ''
						: ''
				} catch (_) {
					return ''
				}
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
			async requestNotificationPermission() {
				try {
					const { ensureNotificationPermission } = await import('@/utils/permission')
					await ensureNotificationPermission()
				} catch (e) {
					console.warn('[App] Notification permission check failed:', e)
				}
			}
		}
	}
</script>

<style>
	@import './styles/light-theme-pages.css';

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
