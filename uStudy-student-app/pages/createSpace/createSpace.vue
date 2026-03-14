<template>
	<page-meta :page-style="createSpacePageStyle"></page-meta>
	<view class="page-container">
		<!-- Aurora Background Layer -->
		<view class="aurora-bg">
			<view class="aurora-blob aurora-blob-1"></view>
			<view class="aurora-blob aurora-blob-2"></view>
			<view class="aurora-blob aurora-blob-3"></view>
		</view>

		<!-- 主内容区域 -->
		<view class="main-content">
			<!-- 居中标题 -->
			<text class="page-title">新建学习空间</text>

			<!-- 胶囊形输入框 -->
			<view class="input-wrapper">
				<input
					class="topic-input"
					type="text"
					v-model="topicName"
					placeholder="输入你想学习的内容..."
					placeholder-class="input-placeholder"
					:placeholder-style="placeholderStyle"
					:focus="inputFocused"
					@focus="inputFocused = true"
					@blur="inputFocused = false"
				/>
			</view>

			<!-- 偏好选项区域 -->
			<view class="preferences-section">
				<view class="preferences-content">
					<!-- 自定义偏好输入框 -->
					<view class="custom-preference-wrapper">
						<input
							class="custom-preference-input"
							type="text"
							v-model="customPreference"
							placeholder="自定义学习偏好（可选）"
							placeholder-class="input-placeholder"
							:placeholder-style="placeholderStyle"
							@focus="handlePreferenceFocus"
						/>
					</view>

					<!-- 横向滚动偏好标签（点击偏好输入框后显示） -->
					<scroll-view
						v-if="showPreferenceTags"
						class="preferences-scroll-container"
						scroll-x
						:scroll-left="scrollLeft"
						@touchstart="handleScrollTouchStart"
						@touchend="handleScrollTouchEnd"
						@touchcancel="handleScrollTouchCancel"
						@scroll="handleScroll"
					>
						<view class="preferences-tags">
							<view
								v-for="option in displayPreferenceOptions"
								:key="option.uniqueKey"
								class="preference-tag"
								:class="{ 'preference-tag-selected': selectedPreferences.includes(option.id) }"
								@click="togglePreference(option.id)"
							>
								<text class="tag-emoji">{{ option.emoji }}</text>
								<text class="tag-text">{{ option.label }}</text>
							</view>
						</view>
					</scroll-view>
				</view>
			</view>

			<!-- 分享码导入区域 -->
			<view class="import-section">
				<view class="import-divider">
					<view class="import-divider-line"></view>
					<text class="import-divider-text">或</text>
					<view class="import-divider-line"></view>
				</view>
				<view class="import-text-btn" @click="showImportModal = true">
					<text class="import-text-btn-label">通过分享码导入</text>
				</view>
			</view>
		</view>

		<!-- 底部按钮 -->
		<view class="bottom-action">
			<view
				class="create-btn"
				:class="{ 'create-btn-disabled': !canCreate }"
				@click="handleCreate"
			>
				<text class="create-btn-text">开始学习</text>
			</view>
		</view>

		<!-- 分享码导入弹窗 -->
		<view
			v-if="showImportModal"
			class="import-modal-overlay"
			:class="{ 'overlay-show': showImportModal }"
			@click="closeImportModal"
		>
			<view class="import-modal-card" @click.stop>
				<text class="import-modal-title">导入学习空间</text>
				<view class="import-modal-input-wrapper">
					<input
						class="import-modal-input"
						v-model="importCode"
						placeholder="输入分享码，如 A1B2-C3D4"
						placeholder-class="input-placeholder"
						:placeholder-style="placeholderStyle"
						maxlength="9"
					/>
				</view>
				<view class="import-modal-actions">
					<view class="import-modal-btn import-modal-btn-cancel" @click="closeImportModal">
						<text class="import-modal-btn-text">取消</text>
					</view>
					<view
						class="import-modal-btn import-modal-btn-confirm"
						:class="{ 'import-modal-btn-disabled': isImporting || !importCode.trim() }"
						@click="handleImport"
					>
						<text class="import-modal-btn-text">{{ isImporting ? '导入中...' : '导入' }}</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	import { createSpace, generateKnowledgeGraph, importSpaceByCode } from '@/api/space'

	const ENABLE_AUTO_SCROLL = true
	const DEBUG_LOOP_SCROLL = false
	const AUTO_SPEED_PX_PER_SEC = 24
	const AUTO_TICK_MS = 16
	const RESUME_DELAY_MS = 1200

	export default {
		data() {
			return {
				topicName: '',
				customPreference: '',
				selectedPreferences: [],
				inputFocused: false,
				isCreating: false,
				preferenceOptions: [
					{ id: 'university', label: '大学课程', emoji: '🎓' },
					{ id: 'quick', label: '快速掌握', emoji: '⚡' },
					{ id: 'solid', label: '扎实学习', emoji: '📚' },
					{ id: 'hobby', label: '业余自学', emoji: '🎨' },
					{ id: 'exam', label: '应对考试', emoji: '📝' },
					{ id: 'work', label: '职场技能', emoji: '💼' },
					{ id: 'research', label: '学术研究', emoji: '🔬' },
					{ id: 'practice', label: '实践项目', emoji: '🛠️' }
				],
				showPreferenceTags: false,
				scrollLeft: 0,
				loopUnitWidth: 0,
				loopMin: 0,
				loopMax: 0,
				currentScrollLeft: 0,
				autoTickTimer: null,
				resumeTimer: null,
				isInteracting: false,
				isRepositioning: false,
				lastTickTs: 0,

				// 分享码导入
				showImportModal: false,
				importCode: '',
				isImporting: false,
			}
		},

		computed: {
			canCreate() {
				return this.topicName.trim().length > 0 && !this.isCreating
			},
			createSpacePageStyle() {
				return 'height: 100vh; overflow: hidden; overscroll-behavior: none; background-color: #0A0A12;'
			},
			placeholderStyle() {
				return 'color: rgba(255, 255, 255, 0.45);'
			},
			// 复制一份标签列表实现无缝循环
			displayPreferenceOptions() {
				return [
					...this.preferenceOptions.map((opt, idx) => ({
						...opt,
						uniqueKey: `first-${opt.id}-${idx}`
					})),
					...this.preferenceOptions.map((opt, idx) => ({
						...opt,
						uniqueKey: `middle-${opt.id}-${idx}`
					})),
					...this.preferenceOptions.map((opt, idx) => ({
						...opt,
						uniqueKey: `last-${opt.id}-${idx}`
					}))
				]
			}
		},

		onReady() {
			this.inputFocused = true
		},

		onShow() {
			if (!this.showPreferenceTags) return
			if (this.loopUnitWidth > 0) {
				this.startAutoScroll()
				return
			}
			this.$nextTick(() => {
				this.initializeLoopScroll()
			})
		},

		onHide() {
			this.teardownLoopScroll()
		},

		onUnload() {
			this.teardownLoopScroll()
		},

		beforeDestroy() {
			this.teardownLoopScroll()
		},

		methods: {
			logLoop(...args) {
				if (!DEBUG_LOOP_SCROLL) return
				console.log('[createSpace][loop-scroll]', ...args)
			},

			togglePreference(id) {
				if (this.selectedPreferences.includes(id)) {
					this.selectedPreferences = this.selectedPreferences.filter(p => p !== id)
				} else {
					this.selectedPreferences = [...this.selectedPreferences, id]
				}
			},

			handlePreferenceFocus() {
				if (!this.showPreferenceTags) {
					this.showPreferenceTags = true
					this.$nextTick(() => {
						this.initializeLoopScroll()
					})
					return
				}

				if (this.loopUnitWidth > 0) {
					this.startAutoScroll()
				} else {
					this.$nextTick(() => {
						this.initializeLoopScroll()
					})
				}
			},

			measureTagsWidth() {
				return new Promise((resolve) => {
					const query = uni.createSelectorQuery().in(this)
					query.select('.preferences-tags').boundingClientRect(rect => {
						if (!rect || !Number.isFinite(rect.width) || rect.width <= 0) {
							resolve(0)
							return
						}
						resolve(rect.width)
					}).exec()
				})
			},

			async initializeLoopScroll() {
				const fullWidth = await this.measureTagsWidth()
				if (!Number.isFinite(fullWidth) || fullWidth <= 0) {
					this.logLoop('measure failed, keep manual scroll only')
					this.stopAutoScroll()
					return
				}

				const unitWidth = fullWidth / 3
				if (!Number.isFinite(unitWidth) || unitWidth <= 0) {
					this.logLoop('unit width invalid, keep manual scroll only', fullWidth)
					this.stopAutoScroll()
					return
				}

				this.loopUnitWidth = unitWidth
				this.loopMin = 0
				this.loopMax = unitWidth * 2

				this.scrollLeft = unitWidth
				this.currentScrollLeft = unitWidth
				this.lastTickTs = Date.now()
				this.isRepositioning = true
				this.logLoop('init loop', {
					fullWidth,
					unitWidth,
					loopMin: this.loopMin,
					loopMax: this.loopMax
				})

				this.startAutoScroll()
			},

			normalizeIfNeeded(rawLeft, source = '') {
				if (this.loopUnitWidth <= 0) {
					return { left: rawLeft, normalized: false }
				}

				let nextLeft = rawLeft
				let normalized = false

				const lowerBound = -this.loopUnitWidth
				const upperBound = this.loopMax + this.loopUnitWidth
				if (!Number.isFinite(nextLeft) || nextLeft < lowerBound || nextLeft > upperBound) {
					nextLeft = this.loopUnitWidth
					normalized = true
					this.logLoop('abnormal reset', { source, rawLeft, nextLeft })
				}

				while (nextLeft >= this.loopMax) {
					nextLeft -= this.loopUnitWidth
					normalized = true
				}

				while (nextLeft <= this.loopMin) {
					nextLeft += this.loopUnitWidth
					normalized = true
				}

				return { left: nextLeft, normalized }
			},

			applyScrollLeft(nextLeft) {
				this.scrollLeft = nextLeft
				this.currentScrollLeft = nextLeft
			},

			startAutoScroll() {
				if (!ENABLE_AUTO_SCROLL) return
				if (this.autoTickTimer) return
				if (!this.showPreferenceTags) return
				if (this.loopUnitWidth <= 0) return

				this.lastTickTs = Date.now()
				this.autoTickTimer = setInterval(() => {
					if (this.isRepositioning) {
						this.isRepositioning = false
						this.lastTickTs = Date.now()
						return
					}

					if (this.isInteracting) {
						this.lastTickTs = Date.now()
						return
					}

					const now = Date.now()
					const dt = Math.min((now - this.lastTickTs) / 1000, 0.05)
					this.lastTickTs = now

					if (!Number.isFinite(dt) || dt <= 0) return

					const baseLeft = Number.isFinite(this.currentScrollLeft) ? this.currentScrollLeft : this.loopUnitWidth
					const rawLeft = baseLeft + AUTO_SPEED_PX_PER_SEC * dt
					const { left, normalized } = this.normalizeIfNeeded(rawLeft, 'auto')
					if (normalized) {
						this.isRepositioning = true
						this.logLoop('normalize(auto)', { rawLeft, normalizedLeft: left })
					}
					this.applyScrollLeft(left)
				}, AUTO_TICK_MS)
				this.logLoop('auto timer started')
			},

			handleScroll(e) {
				const nextLeft = Number(e && e.detail ? e.detail.scrollLeft : NaN)
				if (!Number.isFinite(nextLeft)) return

				if (this.isRepositioning) {
					this.currentScrollLeft = nextLeft
					this.isRepositioning = false
					return
				}

				const { left, normalized } = this.normalizeIfNeeded(nextLeft, 'scroll')
				this.currentScrollLeft = left
				if (normalized) {
					this.isRepositioning = true
					this.scrollLeft = left
					this.logLoop('normalize(scroll)', { rawLeft: nextLeft, normalizedLeft: left })
				}
			},

			stopAutoScroll() {
				if (this.autoTickTimer) {
					clearInterval(this.autoTickTimer)
					this.autoTickTimer = null
					this.logLoop('auto timer stopped')
				}
			},

			handleScrollTouchStart() {
				this.isInteracting = true
				this.clearResumeTimer()
				this.logLoop('touchstart')
			},

			handleScrollTouchEnd() {
				this.scheduleAutoResume('touchend')
			},

			handleScrollTouchCancel() {
				this.scheduleAutoResume('touchcancel')
			},

			clearResumeTimer() {
				if (this.resumeTimer) {
					clearTimeout(this.resumeTimer)
					this.resumeTimer = null
				}
			},

			scheduleAutoResume(source) {
				this.clearResumeTimer()
				this.resumeTimer = setTimeout(() => {
					this.isInteracting = false
					this.lastTickTs = Date.now()
					this.resumeTimer = null
					this.logLoop('interaction resume', source)
				}, RESUME_DELAY_MS)
				this.logLoop('schedule resume', source)
			},

			teardownLoopScroll() {
				this.stopAutoScroll()
				this.clearResumeTimer()
				this.isInteracting = false
				this.isRepositioning = false
				this.lastTickTs = 0
			},

			closeImportModal() {
				this.showImportModal = false
				this.importCode = ''
			},

			async handleImport() {
				const code = this.importCode.trim().replace(/-/g, '')
				if (!code || this.isImporting) return
				this.isImporting = true
				try {
					const res = await importSpaceByCode(code)
					this.closeImportModal()
					if (res.is_collaborative) {
						// Joined a collaborative space — navigate to it
						uni.showToast({ title: '已加入协作空间', icon: 'success' })
						setTimeout(() => {
							uni.redirectTo({
								url: `/pages/learningSpace/learningSpace?id=${res.id}&name=${encodeURIComponent(res.name)}`
							})
						}, 500)
					} else {
						uni.redirectTo({
							url: `/pages/learningSpace/learningSpace?id=${res.id}&name=${encodeURIComponent(res.name)}`
						})
					}
				} catch (err) {
					const errMsg = err?.data?.detail || err?.data?.message || '导入失败，请检查分享码'
					uni.showToast({ title: errMsg, icon: 'none' })
				} finally {
					this.isImporting = false
				}
			},

			async handleCreate() {
				if (!this.canCreate || this.isCreating) return

				const colorOptions = ['blueGreen', 'purplePink', 'pinkYellow', 'mintCyan', 'redPurple']
				const randomColor = colorOptions[Math.floor(Math.random() * colorOptions.length)]

				// 颜色名称到十六进制映射
				const colorMap = {
					'blueGreen': '#0F6FFF',
					'purplePink': '#8B5CF6',
					'pinkYellow': '#F97316',
					'mintCyan': '#10B981',
					'redPurple': '#EF4444'
				}

				// 合并选中的预设偏好和自定义偏好
				const preferenceLabels = this.selectedPreferences.map(id => {
					const opt = this.preferenceOptions.find(o => o.id === id)
					return opt ? opt.label : null
				}).filter(Boolean)

				if (this.customPreference.trim()) {
					preferenceLabels.push(this.customPreference.trim())
				}

				this.isCreating = true
				let spaceRes = null

				// 第一步：创建学习空间
				// 构建 learning_preferences 对象
				const learningPreferences = {
					preset_preferences: this.selectedPreferences,
					custom_preference: this.customPreference.trim() || null
				}
				const hasPreferences =
					learningPreferences.preset_preferences.length > 0 ||
					learningPreferences.custom_preference !== null

				try {
					spaceRes = await createSpace({
						name: this.topicName.trim(),
						color: colorMap[randomColor],
						...(hasPreferences && { learning_preferences: learningPreferences })
					})
				} catch (err) {
					const errData = err?.data || {}
					const errCode = errData?.detail?.code || errData?.code
					if (errCode === 'SPACE_COUNT_QUOTA_EXCEEDED') {
						uni.showModal({
							title: '空间数量已达上限',
							content: errData.detail?.message || errData.message || '升级订阅以创建更多学习空间',
							confirmText: '去升级',
							cancelText: '知道了',
							success: (res) => {
								if (res.confirm) {
									uni.navigateTo({ url: '/pages/account/account' })
								}
							}
						})
					} else {
						const errorMsg = errData?.detail?.message || errData?.message || '创建失败，请重试'
						uni.showToast({ title: errorMsg, icon: 'none' })
					}
					this.isCreating = false
					return
				}

				// 第二步：触发知识图谱生成
				try {
					const taskRes = await generateKnowledgeGraph(spaceRes.id, {
						topic: this.topicName.trim(),
						user_preference: preferenceLabels.length > 0 ? preferenceLabels.join('、') : null
					})

					// 成功：跳转到学习空间页面（带 taskId）
					uni.redirectTo({
						url: `/pages/learningSpace/learningSpace?id=${spaceRes.id}&name=${encodeURIComponent(this.topicName.trim())}&taskId=${taskRes.task_id}`
					})
				} catch (err) {
					console.error('知识图谱生成失败:', err)
					// 空间已创建，仍然跳转但不带 taskId
					uni.redirectTo({
						url: `/pages/learningSpace/learningSpace?id=${spaceRes.id}&name=${encodeURIComponent(this.topicName.trim())}`
					})
				} finally {
					this.isCreating = false
				}
			}
		}
	}
</script>

<style>
	view, text {
		box-sizing: border-box;
	}

	.page-container {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: #0A0A12;
		overflow: hidden;
	}

	/* ========== Aurora Background (Blue-Orange) ========== */
	.aurora-bg {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		overflow: hidden;
		z-index: 1;
		pointer-events: none;
	}

	.aurora-blob {
		position: absolute;
		border-radius: 50%;
		filter: blur(120rpx);
		will-change: transform, opacity;
	}

	/* 蓝色光晕 - 左上 */
	.aurora-blob-1 {
		width: 900rpx;
		height: 900rpx;
		background: radial-gradient(circle, #1A6AFF 0%, rgba(26, 106, 255, 0.3) 40%, transparent 70%);
		top: -250rpx;
		left: -200rpx;
		animation: aurora-blue 14s ease-in-out infinite;
	}

	/* 橙色光晕 - 右下 */
	.aurora-blob-2 {
		width: 850rpx;
		height: 850rpx;
		background: radial-gradient(circle, #FF6A1A 0%, rgba(255, 106, 26, 0.3) 40%, transparent 70%);
		bottom: -200rpx;
		right: -200rpx;
		animation: aurora-orange 16s ease-in-out infinite;
	}

	/* 过渡融合 - 中部 */
	.aurora-blob-3 {
		width: 600rpx;
		height: 600rpx;
		background: radial-gradient(circle, #FF9F45 0%, rgba(255, 159, 69, 0.15) 40%, transparent 70%);
		top: 40%;
		left: 25%;
		animation: aurora-blend 18s ease-in-out infinite;
	}

	@keyframes aurora-blue {
		0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.55; }
		33% { transform: translate(60rpx, 80rpx) scale(1.15); opacity: 0.7; }
		66% { transform: translate(-30rpx, 40rpx) scale(1.05); opacity: 0.6; }
	}

	@keyframes aurora-orange {
		0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
		33% { transform: translate(-70rpx, -60rpx) scale(1.1); opacity: 0.65; }
		66% { transform: translate(40rpx, -80rpx) scale(1.2); opacity: 0.55; }
	}

	@keyframes aurora-blend {
		0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.2; }
		50% { transform: translate(50rpx, -40rpx) scale(1.3); opacity: 0.35; }
	}

	/* 尊重用户减弱动画偏好 */
	@media (prefers-reduced-motion: reduce) {
		.aurora-blob {
			animation: none !important;
		}
	}

	/* ========== 主内容区域 ========== */
	.main-content {
		position: relative;
		z-index: 10;
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 0 40rpx;
		padding-top: 20vh;
	}

	/* ========== 居中标题 ========== */
	.page-title {
		font-size: 44rpx;
		font-weight: 600;
		color: #ffffff;
		margin-bottom: 48rpx;
		text-align: center;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	/* ========== 胶囊形输入框 ========== */
	.input-wrapper {
		width: 80%;
		background: rgba(255, 255, 255, 0.08);
		border: 4rpx solid rgba(255, 255, 255, 0.20);
		border-radius: 100rpx;
		padding: 28rpx 40rpx;
		-webkit-backdrop-filter: blur(10px);
		backdrop-filter: blur(10px);
		margin-bottom: 32rpx;
	}

	.topic-input {
		width: 100%;
		font-size: 30rpx;
		color: #ffffff;
		background-color: transparent;
		text-align: center;
	}

	.input-placeholder {
		color: rgba(255, 255, 255, 0.45);
	}

	/* ========== 偏好选项区域 ========== */
	.preferences-section {
		width: 100%;
	}

	.preferences-content {
		padding-top: 8rpx;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	/* ========== 自定义偏好输入框（与主题输入框统一大小） ========== */
	.custom-preference-wrapper {
		width: 80%;
		background: rgba(255, 255, 255, 0.06);
		border: 4rpx solid rgba(255, 255, 255, 0.15);
		border-radius: 100rpx;
		padding: 28rpx 40rpx;
		margin-bottom: 24rpx;
	}

	.custom-preference-input {
		width: 100%;
		font-size: 30rpx;
		color: #ffffff;
		background-color: transparent;
		text-align: center;
	}

	/* ========== 偏好标签滚动区域 ========== */
	.preferences-scroll-container {
		width: 100%;
		white-space: nowrap;
		touch-action: pan-x;
	}

	.preferences-tags {
		display: inline-flex;
		gap: 12rpx;
		padding: 0 20rpx 16rpx;
	}

	/* ========== 偏好标签（圆角矩形+emoji） ========== */
	.preference-tag {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 6rpx;
		padding: 12rpx 20rpx;
		border-radius: 16rpx;
		background: rgba(255, 255, 255, 0.08);
		border: 4rpx solid rgba(255, 255, 255, 0.15);
		transition: all 0.2s ease;
	}

	.preference-tag-selected {
		background: rgba(0, 136, 255, 0.25);
		border-color: rgba(255, 255, 255, 0.35);
		box-shadow: 0 0 12rpx rgba(0, 136, 255, 0.3);
	}

	.tag-emoji {
		font-size: 24rpx;
	}

	.tag-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.8);
		white-space: nowrap;
	}

	.preference-tag-selected .tag-text {
		color: #ffffff;
	}

	/* ========== 分享码导入区域 ========== */
	.import-section {
		display: flex;
		flex-direction: column;
		align-items: center;
		margin-top: 16rpx;
		padding-bottom: 200rpx;
	}

	.import-divider {
		display: flex;
		align-items: center;
		width: 60%;
		margin-bottom: 20rpx;
	}

	.import-divider-line {
		flex: 1;
		height: 1rpx;
		background: rgba(255, 255, 255, 0.15);
	}

	.import-divider-text {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.4);
		padding: 0 24rpx;
	}

	.import-text-btn {
		padding: 12rpx 32rpx;
	}

	.import-text-btn-label {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.55);
		text-decoration: underline;
		text-underline-offset: 4rpx;
	}

	/* ========== 分享码导入弹窗 ========== */
	.import-modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 300;
		background: rgba(0, 0, 0, 0);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 200ms ease;
	}

	.import-modal-overlay.overlay-show {
		background: rgba(0, 0, 0, 0.6);
	}

	.import-modal-card {
		width: 560rpx;
		background: rgba(20, 20, 30, 0.92);
		-webkit-backdrop-filter: blur(24px) saturate(180%);
		backdrop-filter: blur(24px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		border-radius: 24rpx;
		box-shadow:
			0 16rpx 48rpx rgba(0, 0, 0, 0.5),
			0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
		overflow: hidden;
		padding: 40rpx;
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.import-modal-card {
			background: rgba(30, 30, 45, 0.98);
		}
	}

	.import-modal-title {
		font-size: 36rpx;
		font-weight: 600;
		color: #ffffff;
		text-align: center;
		display: block;
		margin-bottom: 32rpx;
	}

	.import-modal-input-wrapper {
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		border-radius: 16rpx;
		padding: 24rpx 28rpx;
		margin-bottom: 32rpx;
	}

	.import-modal-input {
		width: 100%;
		font-size: 34rpx;
		color: #ffffff;
		background-color: transparent;
		text-align: center;
		letter-spacing: 4rpx;
		font-family: 'Courier New', Courier, monospace;
	}

	.import-modal-actions {
		display: flex;
		gap: 20rpx;
	}

	.import-modal-btn {
		flex: 1;
		height: 84rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 42rpx;
		transition: all 0.2s ease;
	}

	.import-modal-btn-cancel {
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
	}

	.import-modal-btn-confirm {
		background: linear-gradient(135deg, rgba(0, 136, 255, 0.6) 0%, rgba(139, 92, 246, 0.5) 100%);
		border: 2rpx solid rgba(255, 255, 255, 0.2);
		box-shadow: 0 8rpx 32rpx rgba(0, 136, 255, 0.3);
	}

	.import-modal-btn-disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	.import-modal-btn-text {
		font-size: 30rpx;
		font-weight: 500;
		color: #ffffff;
	}

	/* ========== 底部按钮 ========== */
	.bottom-action {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 24rpx 40rpx calc(24rpx + env(safe-area-inset-bottom));
		z-index: 100;
		background: linear-gradient(to top, rgba(10, 10, 18, 0.95) 0%, transparent 100%);
	}

	.create-btn {
		width: 100%;
		height: 96rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		background: linear-gradient(135deg,
			rgba(0, 136, 255, 0.6) 0%,
			rgba(139, 92, 246, 0.5) 100%
		);
		border: 2rpx solid rgba(255, 255, 255, 0.2);
		border-radius: 48rpx;
		-webkit-backdrop-filter: blur(20px);
		backdrop-filter: blur(20px);
		transition: all 0.2s ease;
		box-shadow:
			0 8rpx 32rpx rgba(0, 136, 255, 0.3),
			inset 0 1rpx 0 rgba(255, 255, 255, 0.2);
	}

	.create-btn-disabled {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.1);
		box-shadow: none;
	}

	.create-btn-text {
		font-size: 30rpx;
		font-weight: 600;
		color: #ffffff;
	}

	.create-btn-disabled .create-btn-text {
		color: rgba(255, 255, 255, 0.4);
	}
</style>
