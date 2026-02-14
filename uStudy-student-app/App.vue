<script>
	import { useUserStore } from '@/store/user'

	export default {
		onLaunch: function() {
			useUserStore()
			console.log('App Launch')
		},
		onShow: function() {
			console.log('App Show')
		},
		onHide: function() {
			console.log('App Hide')
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
