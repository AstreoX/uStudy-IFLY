<script>
	export default {
		onLaunch: function() {
		},
		onShow: function() {
		},
		onHide: function() {
		}
	}
</script>

<style>
	:root {
		--color-bg: #181825;
		--color-surface: #2a2a3c;
		--color-primary: #007AFF;
		--color-blue: #3B82F6;
		--color-text: #FFFFFF;
		--color-text-secondary: rgba(255, 255, 255, 0.6);
		--color-border: rgba(255, 255, 255, 0.15);
		--color-error: #EF4444;
		--color-widget-bg: rgba(255, 255, 255, 0.06);
		--color-widget-border: rgba(255, 255, 255, 0.10);
		--color-widget-header: rgba(255, 255, 255, 0.9);
		--color-accent-blue: #3B82F6;
		--color-accent-orange: #F97316;
		--color-accent-indigo: #4F46E5;
	}

	page {
		background-color: #181825;
		color: #FFFFFF;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
		min-height: 100vh;
	}

	/* #ifdef H5 */
	/* Keep every native and uni-app scroll area consistent with the study chat. */
	* {
		scrollbar-width: thin;
		scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
	}

	*::-webkit-scrollbar {
		width: 6px;
		height: 6px;
	}

	*::-webkit-scrollbar-track,
	*::-webkit-scrollbar-corner {
		background: transparent;
	}

	*::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
	}

	*::-webkit-scrollbar-thumb:hover {
		background: rgba(255, 255, 255, 0.2);
	}

	*::-webkit-scrollbar-button {
		display: none;
		width: 0;
		height: 0;
	}
	/* #endif */
</style>
