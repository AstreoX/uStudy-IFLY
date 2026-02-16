<template>
	<view class="page-container">
		<!-- Aurora Background Layer -->
		<view class="aurora-bg">
			<view class="aurora-blob aurora-blob-1"></view>
			<view class="aurora-blob aurora-blob-2"></view>
			<view class="aurora-blob aurora-blob-3"></view>
			<view class="aurora-blob aurora-blob-4"></view>
		</view>

		<!-- 选择模式背景遮罩 -->
		<view
			class="selection-backdrop"
			:class="{ 'backdrop-active': isSelectionMode }"
			@click="exitSelectionMode"
		></view>

		<!-- 标题区域 -->
		<view class="header" :class="{ 'header-hidden': isSelectionMode }">
			<!-- 正常状态：显示当前学习主题 -->
			<template v-if="!isEmptyState">
				<view class="header-title">
					<text class="header-text-light">正在学习</text>
					<text class="header-text-highlight">「{{ currentTopic.name }}」</text>
				</view>
				<text class="header-subtitle">下一学习点已就绪</text>
			</template>

			<!-- 空状态：交错布局提示 -->
			<template v-else>
				<view class="header-title-empty">
					<text class="header-text-line1">还没有学习空间</text>
					<text class="header-text-line2">来试试创建一个吧</text>
				</view>
			</template>
		</view>

		<!-- 统一卡片容器 -->
		<view
			class="unified-cards-container"
			:class="{ 'selection-mode': isSelectionMode }"
			@touchstart="handleTouchStart"
			@touchmove="handleTouchMove"
			@touchend="handleTouchEnd"
		>
			<!-- 所有卡片统一渲染（使用 transform 控制位置） -->
			<view
				v-for="(card, index) in orderedTopics"
				:key="card.id"
				class="unified-card"
				:class="getUnifiedCardClass(card, index)"
				:style="getUnifiedCardStyle(card, index)"
				@click="handleCardClick(card, index)"
			>
				<!-- 真实学习空间卡片 -->
				<template v-if="card.cardType === 'space'">
					<!-- 删除按钮（仅选择模式显示，带淡入淡出动画） -->
					<view
						class="delete-btn"
						:class="{ 'delete-btn-visible': isSelectionMode && !isExitingSelection }"
						@click.stop="handleDeleteClick(card)"
					>
						<image class="delete-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
					</view>
					<!-- 卡片内容 -->
					<view class="card-header">
						<text class="card-title">{{ card.name }}</text>
						<view class="card-info-row">
							<text class="card-part">Part {{ card.currentPart }} / {{ card.totalParts }}</text>
							<text class="card-percentage">{{ card.progress }}%</text>
						</view>
					</view>

					<!-- 进度条 -->
					<view class="progress-bar">
						<view class="progress-fill progress-green" :style="{width: card.progress + '%'}"></view>
					</view>

					<!-- 知识树区域 -->
					<view class="knowledge-tree-container">
						<knowledge-tree-mini
							v-if="getGraphData(card.id)"
							:space-id="card.id"
							:nodes="getGraphData(card.id).nodes"
							:edges="getGraphData(card.id).edges"
							:canvas-width="treeCanvasWidth"
							:canvas-height="treeCanvasHeight"
						/>
						<view v-else class="knowledge-tree-loading">
							<text class="loading-text">加载中...</text>
						</view>
					</view>

					<!-- 箭头按钮（仅主卡片显示，带过渡效果） -->
					<view class="arrow-button" :class="{ 'arrow-hidden': index !== 0 || !showArrow }">
						<image class="arrow-icon" src="/static/icons/phosphor-icons/SVGs/fill/arrow-fat-right-fill.svg" mode="aspectFit"></image>
					</view>
				</template>

				<!-- 虚拟新建卡片 -->
				<template v-else-if="card.cardType === 'add'">
					<view class="add-card-inner" :class="{ 'add-card-main': index === 0 }">
						<text class="add-card-icon">+</text>
						<text class="add-card-text">{{ index === 0 ? '创建学习空间' : '添加学习空间' }}</text>
					</view>
				</template>
			</view>

			<!-- 选择模式下的新建按钮（仅4+空间时显示） -->
			<view
				v-if="isSelectionMode && spaceCount >= 4"
				class="unified-card add-card"
				:class="{ 'add-card-visible': isSelectionMode }"
				:style="getAddCardStyle()"
				@click="handleAddCard"
			>
				<view class="add-card-inner">
					<text class="add-card-icon">+</text>
					<text class="add-card-text">添加学习空间</text>
				</view>
			</view>
		</view>

		<!-- 删除确认弹窗 -->
		<u-modal
			:visible="showDeleteModal"
			title="删除学习空间"
			:content="deleteModalContent"
			confirm-text="删除"
			confirm-type="danger"
			@confirm="doDeleteSpace"
			@close="showDeleteModal = false"
		/>

		<!-- Toast 通知 -->
		<u-toast
			:visible="toast.visible"
			:message="toast.message"
			:type="toast.type"
			@close="toast.visible = false"
		/>

		<!-- 底部导航栏 -->
		<view class="bottom-nav" :class="{ 'nav-hidden': isSelectionMode }">
			<view class="nav-item">
				<view class="nav-icon">
					<image class="icon-img" src="/static/icons/phosphor-icons/SVGs/fill/cards-three-fill.svg" mode="aspectFit"></image>
				</view>
			</view>
			<view class="nav-item nav-item-active" @click="navigateToChat">
				<view class="nav-icon-wrapper">
					<image class="icon-img-active" src="/static/icons/phosphor-icons/SVGs/duotone/chat-centered-duotone.svg" mode="aspectFit"></image>
				</view>
			</view>
			<view class="nav-item" @click="navigateToAccount">
				<view class="nav-icon">
					<image class="icon-img" src="/static/icons/phosphor-icons/SVGs/duotone/user-circle-duotone.svg" mode="aspectFit"></image>
				</view>
			</view>
		</view>
		<!-- Alpha 激活码弹窗 -->
		<activation-modal
			:visible="showActivationModal"
			@success="onActivationSuccess"
			@cancel="onActivationCancel"
			@close="showActivationModal = false"
		/>

		<!-- 更新弹窗 -->
		<update-dialog
			:visible="updateStore.showUpdateDialog"
			:version-name="updateStore.manifest?.latestVersion?.versionName || ''"
			:file-size-mb="updateStore.manifest?.latestVersion?.fileSizeMB || 0"
			:is-forced="updateStore.isForced"
			:changelog="updateStore.changelogContent"
			:is-downloading="updateStore.isDownloading"
			:download-progress="updateStore.downloadProgress"
			:download-complete="updateStore.downloadComplete"
			:download-error="updateStore.downloadError"
			@skip="updateStore.skipThisVersion()"
			@later="updateStore.dismissUpdate()"
			@update="updateStore.downloadInBrowser()"
			@install="updateStore.installUpdate()"
			@browser="updateStore.fallbackToBrowser()"
		/>

		<!-- 公告弹窗 -->
		<announcement-dialog
			:visible="updateStore.showAnnouncementDialog"
			:title="updateStore.currentAnnouncement?.title || ''"
			:date="updateStore.currentAnnouncement?.date || ''"
			:type="updateStore.currentAnnouncement?.type || 'notice'"
			:body="updateStore.announcementContent"
			@close="onAnnouncementClose"
		/>

		<!-- 启动兜底遮罩：避免网络异常时出现纯黑屏 -->
		<view v-if="bootState !== 'ready'" class="boot-overlay">
			<view class="boot-panel">
				<template v-if="bootState === 'loading'">
					<text class="boot-title">正在加载首页...</text>
					<text class="boot-subtitle">请稍候</text>
				</template>
				<template v-else>
					<text class="boot-title">{{ bootErrorMessage || '加载失败，请重试' }}</text>
					<view class="boot-retry" @click="handleBootRetry">
						<text class="boot-retry-text">重试</text>
					</view>
				</template>
			</view>
		</view>
	</view>
</template>

<script>
	import { getMe } from '@/api/auth'
	import { getSpaces, getSpaceGraph, deleteSpace } from '@/api/space'
	import { getTokens, getCardOrder, setCardOrder, clearAuth } from '@/utils/storage'
	import { useUserStore } from '@/store/user'
	import { useUpdateStore } from '@/store/update'
	import KnowledgeTreeMini from '@/components/knowledge-tree-mini/knowledge-tree-mini.vue'
	import ActivationModal from '@/components/activation-modal/activation-modal.vue'
	import UpdateDialog from '@/components/update-dialog/update-dialog.vue'
	import AnnouncementDialog from '@/components/announcement-dialog/announcement-dialog.vue'
	import UModal from '@/components/u-modal/u-modal.vue'
	import UToast from '@/components/u-toast/u-toast.vue'

	export default {
		components: {
			KnowledgeTreeMini,
			ActivationModal,
			UpdateDialog,
			AnnouncementDialog,
			UModal,
			UToast
		},

		data() {
			return {
				// 所有学习主题（从后端加载）
				learningTopics: [],
				// 卡片顺序（栈结构，最近选择的在前）
				cardOrder: [],
				// 是否处于选择模式
				isSelectionMode: false,
				// 触摸相关
				touchStartY: 0,
				touchStartTime: 0,
				lastTouchY: 0,
				// 选择模式滚动偏移
				selectionScrollY: 0,
				// 位置计算（像素值，在 mounted 中初始化）
				screenHeight: 0,
				mainCardTop: 0,
				cardHeight: 0,
				selectionGap: 0,
				selectionTopPadding: 0,
				// 退出过渡状态
				isExitingSelection: false,
				exitingSelectedIndex: -1,
				// 过度拉动距离（顶部继续下拉）
				overPullDistance: 0,
				// 是否正在滚动（滚动时禁用动画）
				isScrolling: false,
				// 惯性滚动相关
				lastMoveTime: 0,
				velocity: 0,
				inertiaAnimationId: null,
				// 退出过渡时保持卡片内容可见
				keepContentVisible: false,
				// 控制箭头显示（用于确保过渡动画正常触发）
				showArrow: true,
				// 知识图谱缓存 { spaceId: { nodes, edges } }
				graphCache: {},
				// 画布尺寸
				treeCanvasWidth: 0,
				treeCanvasHeight: 0,
				// Alpha 激活码弹窗
				showActivationModal: false,
				// 删除学习空间
				showDeleteModal: false,
				deletingSpace: null,
				isDeleting: false,
				// Toast
				toast: { visible: false, message: '', type: 'info' },
				// 启动状态兜底
				bootState: 'loading',
				bootErrorMessage: '',
				bootTimeoutId: null
			}
		},

		async onShow() {
			await this.initializePage()
		},

		mounted() {
			this.calculateLayout()
		},

		computed: {
			updateStore() {
				return useUpdateStore()
			},

			// 真实学习空间数量
			spaceCount() {
				return this.learningTopics.length
			},

			// 是否在堆叠区域显示新建卡片（非选择模式，空间数<4）
			showAddCardInStack() {
				return this.spaceCount < 4
			},

			// 是否为空状态（0个空间）
			isEmptyState() {
				return this.spaceCount === 0
			},

			// 删除弹窗内容
			deleteModalContent() {
				if (!this.deletingSpace) return ''
				return `确定要删除「${this.deletingSpace.name}」吗？此操作不可恢复，所有学习记录、知识图谱和对话记录将被永久删除。`
			},

			// 当前主卡片数据（栈顶）
			currentTopic() {
				if (this.cardOrder.length === 0 || this.learningTopics.length === 0) {
					return { name: '无学习内容', progress: 0, currentPart: 0, totalParts: 0 }
				}
				const index = this.cardOrder[0]
				if (index < 0 || index >= this.learningTopics.length) {
					return { name: '无学习内容', progress: 0, currentPart: 0, totalParts: 0 }
				}
				return this.learningTopics[index]
			},

			// 按顺序排列的卡片列表（包含虚拟新建卡片）
			orderedTopics() {
				const realCards = this.cardOrder.map(index => ({
					...this.learningTopics[index],
					originalIndex: index,
					cardType: 'space'
				}))

				// 空间数<4时，在末尾插入虚拟新建卡片
				// 无论选择模式还是非选择模式都包含，以实现平滑过渡动画
				if (this.showAddCardInStack) {
					const addCard = {
						id: '__add_card__',
						name: '',
						cardType: 'add',
						originalIndex: -1
					}
					return [...realCards, addCard]
				}

				return realCards
			}
		},

		methods: {
			async initializePage() {
				this.calculateLayout()
				this.bootState = 'loading'
				this.bootErrorMessage = ''
				if (this.bootTimeoutId) {
					clearTimeout(this.bootTimeoutId)
				}
				this.bootTimeoutId = setTimeout(() => {
					if (this.bootState === 'loading') {
						this.setBootError('首页加载超时，请检查网络后重试')
					}
				}, 15000)

				try {
					const authed = await this.ensureAuth()
					if (!authed) return

					this.checkAlphaActivation()

					const loaded = await this.loadSpaces()
					if (!loaded) return

					this.bootState = 'ready'
				} catch (error) {
					this.setBootError('初始化失败，请重试', error)
				} finally {
					if (this.bootTimeoutId) {
						clearTimeout(this.bootTimeoutId)
						this.bootTimeoutId = null
					}
				}
			},

			setBootError(message, error) {
				if (error) {
					console.error(message, error)
				}
				this.bootErrorMessage = message
				this.bootState = 'error'
			},

			handleBootRetry() {
				this.initializePage()
			},

			// 计算各种位置的像素值
			calculateLayout() {
				const systemInfo = uni.getSystemInfoSync()
				const screenHeight = systemInfo.windowHeight
				const unitVh = screenHeight / 26

				this.screenHeight = screenHeight
				this.mainCardTop = unitVh * 11          // 主卡片 top 位置
				this.cardHeight = unitVh * 7            // 卡片高度
				this.selectionGap = uni.upx2px(30)      // 30rpx 转像素
				this.selectionTopPadding = uni.upx2px(100)  // 顶部间距
			},

			async ensureAuth() {
				const userStore = useUserStore()
				const tokens = getTokens()
				if (!tokens || !tokens.access_token) {
					clearAuth()
					userStore.clear()
					uni.reLaunch({
						url: '/pages/login/login'
					})
					return false
				}

				try {
					const user = await getMe()
					userStore.setUser(user)
					return true
				} catch (error) {
					console.error('Auth check failed:', error)
					clearAuth()
					userStore.clear()
					uni.reLaunch({
						url: '/pages/login/login'
					})
					return false
				}
			},

			// 检查用户是否需要激活 Alpha
			checkAlphaActivation() {
				const userStore = useUserStore()
				const tier = userStore.user?.subscription_tier
				// 非 ALPHA 用户显示激活弹窗
				if (tier !== 'ALPHA' && tier !== 'alpha') {
					this.showActivationModal = true
				}
			},

			// 激活成功回调
			onActivationSuccess(response) {
				this.showActivationModal = false
			},

			// 用户取消激活（稍后再说）
			onActivationCancel() {
				this.showActivationModal = false
			},

			// 公告关闭
			onAnnouncementClose({ dontShowAgain }) {
				this.updateStore.dismissAnnouncement(dontShowAgain)
			},

			// 从后端加载学习空间
			async loadSpaces() {
				try {
					const spaces = await getSpaces()

					// 转换后端格式为前端格式
					this.learningTopics = spaces.map(space => ({
						id: space.id,
						name: space.name,
						progress: 0,  // TODO: 从节点 mastery 计算
						currentPart: 1,
						totalParts: 10,  // TODO: 从节点数量计算
						color: this.hexToColorName(space.color)
					}))

					// 恢复持久化的卡片顺序（基于空间 ID）
					this.cardOrder = this.restoreCardOrder()

					// 计算画布尺寸并加载图谱数据
					this.calculateCanvasSize()
					this.loadAllGraphData(spaces)
					return true

				} catch (error) {
					this.setBootError('学习空间加载失败，请检查网络后重试', error)
					return false
				}
			},

			// 计算知识树画布尺寸
			calculateCanvasSize() {
				// 卡片尺寸：宽度为 10/12 屏幕宽度，高度为 7/26 屏幕高度
				// 知识树区域：宽度 90%，高度 4/7 卡片高度
				const systemInfo = uni.getSystemInfoSync()
				const cardWidth = systemInfo.windowWidth * (10 / 12)
				const cardHeight = systemInfo.windowHeight * (7 / 26)

				this.treeCanvasWidth = Math.floor(cardWidth * 0.9)
				this.treeCanvasHeight = Math.floor(cardHeight * (4 / 7))
			},

			// 并行加载所有空间的图谱数据
			async loadAllGraphData(spaces) {
				const loadPromises = spaces.map(space => this.loadGraphData(space.id))
				await Promise.allSettled(loadPromises)
			},

			// 加载单个空间的图谱数据
			async loadGraphData(spaceId) {
				try {
					const { nodes, edges } = await getSpaceGraph(spaceId)

					// 转换为本地格式
					const localNodes = nodes.map(n => ({
						id: n.id,
						label: n.label,
						mastery: n.mastery
					}))

					const localEdges = edges.map(e => ({
						from: e.from_node_id,
						to: e.to_node_id,
						type: e.type
					}))

					this.graphCache = {
						...this.graphCache,
						[spaceId]: {
						nodes: localNodes,
						edges: localEdges
						}
					}

					// 更新该空间的进度数据
					this.updateSpaceProgress(spaceId)
				} catch (error) {
					// 图谱加载失败，静默处理（显示空状态）
					console.error(`Failed to load graph for space ${spaceId}:`, error)
				}
			},

			// 获取空间的图谱数据
			getGraphData(spaceId) {
				return this.graphCache[spaceId] || null
			},

			// 计算空间的学习进度
			calculateSpaceProgress(spaceId) {
				const graphData = this.graphCache[spaceId]
				if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
					return { currentPart: 0, totalParts: 0, progress: 0 }
				}

				const nodes = graphData.nodes
				const totalParts = nodes.length
				const masteredNodes = nodes.filter(n => n.mastery != null && n.mastery >= 70)
				const currentPart = masteredNodes.length
				const progress = Math.round((currentPart / totalParts) * 100)

				return { currentPart, totalParts, progress }
			},

			// 更新空间的进度数据到卡片
			updateSpaceProgress(spaceId) {
				const { currentPart, totalParts, progress } = this.calculateSpaceProgress(spaceId)

				const topicIndex = this.learningTopics.findIndex(t => t.id === spaceId)
				if (topicIndex !== -1) {
					this.learningTopics[topicIndex].currentPart = currentPart
					this.learningTopics[topicIndex].totalParts = totalParts
					this.learningTopics[topicIndex].progress = progress
				}
			},

			// 十六进制颜色转颜色名称
			hexToColorName(hex) {
				const colorMap = {
					'#0F6FFF': 'blueGreen',
					'#A18CD1': 'purplePink',
					'#FA709A': 'pinkYellow',
					'#84FAB0': 'mintCyan',
					'#F43B37': 'redPurple'
				}
				// 不区分大小写匹配
				const upperHex = (hex || '').toUpperCase()
				for (const [key, value] of Object.entries(colorMap)) {
					if (key.toUpperCase() === upperHex) {
						return value
					}
				}
				return 'blueGreen'  // 默认颜色
			},

			// 恢复卡片顺序（ID -> 索引映射）
			restoreCardOrder() {
				const savedIds = getCardOrder()
				const currentIds = this.learningTopics.map(t => t.id)

				if (!savedIds || savedIds.length === 0) {
					// 无存储，使用默认顺序
					return currentIds.map((_, i) => i)
				}

				// 构建 ID -> 索引映射
				const idToIndex = new Map(currentIds.map((id, index) => [id, index]))

				// 1. 按存储顺序添加仍存在的空间
				const orderedIndices = []
				const addedIds = new Set()

				for (const id of savedIds) {
					if (idToIndex.has(id)) {
						orderedIndices.push(idToIndex.get(id))
						addedIds.add(id)
					}
				}

				// 2. 新空间追加到末尾（按原始顺序）
				for (let i = 0; i < currentIds.length; i++) {
					if (!addedIds.has(currentIds[i])) {
						orderedIndices.push(i)
					}
				}

				return orderedIndices
			},

			// 保存卡片顺序（索引 -> ID）
			saveCardOrder() {
				const orderedIds = this.cardOrder
					.map(index => this.learningTopics[index])
					.filter(topic => topic !== undefined)
					.map(topic => topic.id)
				setCardOrder(orderedIds)
			},

			// 获取卡片渐变样式（5种预设渐变色，统一角度）
			getCardGradient(color) {
				const gradients = {
					blueGreen: 'background: linear-gradient(to bottom right, #0F6FFF 0%, #B1DD8B 100%);',
					purplePink: 'background: linear-gradient(to bottom right, #A18CD1 0%, #FBC2EB 100%);',
					pinkYellow: 'background: linear-gradient(to bottom right, #FA709A 0%, #FEE140 100%);',
					mintCyan: 'background: linear-gradient(to bottom right, #84FAB0 0%, #38F9D7 100%);',
					redPurple: 'background: linear-gradient(to bottom right, #F43B37 0%, #453A94 100%);'
				}
				return gradients[color] || gradients.blueGreen
			},

			// 获取统一卡片的类名（简化版，主要用于控制内容显示）
			getUnifiedCardClass(card, index) {
				// 新建卡片特殊处理
				if (card.cardType === 'add') {
					if (this.isSelectionMode) {
						return 'selection-card add-card-selection'
					}
					if (index === 0) {
						// 主卡片位置（0空间场景）
						return 'main-card add-card-main-position'
					}
					// 堆叠位置
					return 'stacked-card add-card-stacked'
				}

				// 真实学习空间卡片
				if (this.isSelectionMode) {
					// 退出过渡期间，需要淡出标题的卡片：
					// - index > 1（后面的卡片）
					// - 不是被选中的卡片（被选中的卡片会变成新的主卡片）
					if (this.isExitingSelection && index > 1 && index !== this.exitingSelectedIndex) {
						return 'selection-card exiting-back'
					}
					return 'selection-card'
				}
				if (index === 0) {
					return 'main-card'
				} else if (index <= 3) {
					// 堆叠卡片：退出过渡期间保持内容可见
					const baseClass = this.keepContentVisible ? 'stacked-card keep-content' : 'stacked-card'
					// index=1 是最前面的堆叠卡片，index=2,3 是后面的（标题需要淡出）
					return index > 1 ? `${baseClass} back-stacked` : baseClass
				}
				return 'hidden-card'
			},

			// 获取统一卡片的样式（通过 transform 控制位置和缩放）
			getUnifiedCardStyle(card, index) {
				// 新建卡片使用专门的样式计算
				if (card.cardType === 'add') {
					return this.getAddCardStackedStyle(index)
				}

				const gradient = this.getCardGradient(card.color)

				// ========== 退出过渡状态 ==========
				if (this.isExitingSelection) {
					const selectedIdx = this.exitingSelectedIndex

					if (index === selectedIdx) {
						// 被选中的卡片：移动到主卡片位置
						// z-index 最高，确保在最上层
						return `${gradient} transform: translateY(0) scale(1); z-index: 200;`
					}

					// 计算该卡片在新顺序中的堆叠位置
					// 原 index=0 的卡片会变成 index=1（堆叠第一层）
					// 原 index < selectedIdx 的卡片，新 index = 原 index + 1
					// 原 index > selectedIdx 的卡片，新 index = 原 index
					let newIndex
					if (index === 0) {
						newIndex = 1  // 原主卡片变成堆叠第一层
					} else if (index < selectedIdx) {
						newIndex = index + 1
					} else {
						newIndex = index
					}

					// 计算目标位置（使用非选择模式的堆叠逻辑）
					const unitVh = this.screenHeight / 26

					// z-index：newIndex 越小越高
					const zIndex = 100 + (10 - newIndex)

					if (newIndex <= 3) {
						// 堆叠卡片
						const stackIndex = 4 - newIndex  // 1→3, 2→2, 3→1
						const scales = { 1: 0.8, 2: 0.9, 3: 1 }
						const offsets = { 1: -1.0, 2: -0.5, 3: 0 }

						const targetTop = unitVh * (21.5 + offsets[stackIndex])
						const offsetY = targetTop - this.mainCardTop

						return `${gradient} transform: translateY(${offsetY}px) scale(${scales[stackIndex]}); z-index: ${zIndex};`
					}

					// 隐藏的卡片
					const offsetY = this.screenHeight - this.mainCardTop
					return `${gradient} transform: translateY(${offsetY}px) scale(0.8); opacity: 0; z-index: ${zIndex};`
				}

				// ========== 选择模式 ==========
				if (this.isSelectionMode) {
					const baseZIndex = 100
					const zIndex = baseZIndex + (10 - index)

					const targetY = this.selectionTopPadding + index * (this.cardHeight + this.selectionGap)
					const offsetY = targetY - this.mainCardTop - this.selectionScrollY
					const delay = 0.02 * index

					// 滚动时禁用动画，否则启用
					const transition = this.isScrolling
						? 'transition: none;'
						: `transition-delay: ${delay}s;`

					return `${gradient} transform: translateY(${offsetY}px) scale(1); ${transition} z-index: ${zIndex};`
				}

				// ========== 非选择模式 ==========
				const baseZIndex = 10
				const zIndex = baseZIndex + (10 - index)

				if (index === 0) {
					// 主卡片：无偏移
					return `${gradient} transform: translateY(0) scale(1); z-index: ${zIndex};`
				} else if (index <= 3) {
					// 堆叠卡片
					const stackIndex = 4 - index  // 反转顺序：1→3, 2→2, 3→1
					const scales = { 1: 0.8, 2: 0.9, 3: 1 }
					const offsets = { 1: -1.0, 2: -0.5, 3: 0 }  // 相对于 21.5 行的偏移

					const unitVh = this.screenHeight / 26
					const targetTop = unitVh * (21.5 + offsets[stackIndex])
					const offsetY = targetTop - this.mainCardTop

					return `${gradient} transform: translateY(${offsetY}px) scale(${scales[stackIndex]}); z-index: ${zIndex};`
				}

				// 隐藏的卡片
				const offsetY = this.screenHeight - this.mainCardTop
				return `${gradient} transform: translateY(${offsetY}px) scale(0.8); opacity: 0; z-index: ${zIndex};`
			},

			// 获取添加卡片按钮样式（仅用于选择模式下的独立新建按钮，4+空间场景）
			getAddCardStyle() {
				// 使用真实空间数量计算位置
				const index = this.spaceCount
				const targetY = this.selectionTopPadding + index * (this.cardHeight + this.selectionGap)
				const offsetY = targetY - this.mainCardTop - this.selectionScrollY
				const delay = 0

				// 滚动时禁用动画，否则启用
				const transition = this.isScrolling
					? 'transition: none;'
					: `transition-delay: ${delay}s;`

				return `transform: translateY(${offsetY}px) scale(1); ${transition}`
			},

			// 获取新建卡片在堆叠区域的样式
			getAddCardStackedStyle(index) {
				const baseZIndex = 10
				const zIndex = baseZIndex + (10 - index)

				// 退出过渡状态：与真实卡片同步回到堆叠位置
				if (this.isExitingSelection) {
					if (index === 0) {
						return `transform: translateY(0) scale(1); z-index: ${zIndex};`
					}
					const unitVh = this.screenHeight / 26
					if (index <= 3) {
						const stackIndex = 4 - index
						const scales = { 1: 0.8, 2: 0.9, 3: 1 }
						const offsets = { 1: -1.0, 2: -0.5, 3: 0 }
						const targetTop = unitVh * (21.5 + offsets[stackIndex])
						const offsetY = targetTop - this.mainCardTop
						return `transform: translateY(${offsetY}px) scale(${scales[stackIndex]}); z-index: ${zIndex};`
					}
					const offsetY = this.screenHeight - this.mainCardTop
					return `transform: translateY(${offsetY}px) scale(0.8); opacity: 0; z-index: ${zIndex};`
				}

				// 选择模式：列表排列（与真实卡片相同逻辑）
				if (this.isSelectionMode) {
					const targetY = this.selectionTopPadding + index * (this.cardHeight + this.selectionGap)
					const offsetY = targetY - this.mainCardTop - this.selectionScrollY
					const delay = 0
					const transition = this.isScrolling
						? 'transition: none;'
						: `transition-delay: ${delay}s;`
					return `transform: translateY(${offsetY}px) scale(1); ${transition} z-index: ${zIndex};`
				}

				// 主卡片位置（0空间场景）
				if (index === 0) {
					return `transform: translateY(0) scale(1); z-index: ${zIndex};`
				}

				// 堆叠位置：应用与正常卡片相同的缩放
				const unitVh = this.screenHeight / 26
				if (index <= 3) {
					const stackIndex = 4 - index  // 1→3, 2→2, 3→1
					const scales = { 1: 0.8, 2: 0.9, 3: 1 }
					const offsets = { 1: -1.0, 2: -0.5, 3: 0 }

					const targetTop = unitVh * (21.5 + offsets[stackIndex])
					const offsetY = targetTop - this.mainCardTop

					return `transform: translateY(${offsetY}px) scale(${scales[stackIndex]}); z-index: ${zIndex};`
				}

				// 隐藏位置
				const offsetY = this.screenHeight - this.mainCardTop
				return `transform: translateY(${offsetY}px) scale(0.8); opacity: 0; z-index: ${zIndex};`
			},

			// 触摸开始
			handleTouchStart(e) {
				this.touchStartY = e.touches[0].clientY
				this.touchStartTime = Date.now()
				this.lastTouchY = e.touches[0].clientY
				// 选择模式下触摸开始，标记为正在滚动
				if (this.isSelectionMode) {
					this.isScrolling = true
					// 停止惯性动画
					if (this.inertiaAnimationId) {
						cancelAnimationFrame(this.inertiaAnimationId)
						this.inertiaAnimationId = null
					}
					this.velocity = 0
					this.lastMoveTime = Date.now()
				}
			},

			// 触摸移动
			handleTouchMove(e) {
				if (this.isSelectionMode) {
					const currentY = e.touches[0].clientY
					const currentTime = Date.now()
					const deltaY = this.lastTouchY - currentY  // 正值=向上滑，负值=向下滑
					const deltaTime = currentTime - this.lastMoveTime

					// 计算速度（像素/毫秒）
					if (deltaTime > 0) {
						this.velocity = deltaY / deltaTime
					}

					this.lastTouchY = currentY
					this.lastMoveTime = currentTime

					// 计算最大滚动距离
					// 当 spaceCount >= 4 时，需要额外算上独立的新建按钮
					const addCardCount = this.spaceCount >= 4 ? 1 : 0
					const totalHeight = (this.orderedTopics.length + addCardCount) * (this.cardHeight + this.selectionGap)
					const maxScroll = Math.max(0, totalHeight - this.screenHeight + this.selectionTopPadding * 2)

					// 尝试更新滚动位置
					const newScrollY = this.selectionScrollY + deltaY

					if (newScrollY < 0) {
						// 已在顶部，继续下拉 → 累积过度拉动距离
						this.overPullDistance = Math.min(150, this.overPullDistance - deltaY)
						this.selectionScrollY = 0
					} else {
						// 正常滚动范围内
						this.selectionScrollY = Math.min(maxScroll, newScrollY)
						this.overPullDistance = 0  // 重置过度拉动
					}
				}
			},

			// 触摸结束
			handleTouchEnd(e) {
				if (this.isSelectionMode) {
					// 检测过度拉动是否触发退出（阈值 50px）
					if (this.overPullDistance >= 50) {
						this.isScrolling = false
						this.exitSelectionMode()
						return
					}
					// 重置过度拉动距离
					this.overPullDistance = 0

					// 启动惯性滚动（速度阈值 0.1 px/ms）
					if (Math.abs(this.velocity) > 0.1) {
						this.startInertiaScroll()
					} else {
						this.isScrolling = false
					}
					return
				}

				// 非选择模式：向上滑动进入选择模式
				// 空状态下禁止进入选择模式（只有新建卡片，无需选择）
				if (this.isEmptyState) return

				const touchEndY = e.changedTouches[0].clientY
				const deltaY = this.touchStartY - touchEndY
				const deltaTime = Date.now() - this.touchStartTime

				if (deltaY > 50 || (deltaY > 20 && deltaTime < 200)) {
					this.enterSelectionMode()
				}
			},

			// 进入选择模式
			enterSelectionMode() {
				this.selectionScrollY = 0
				this.isSelectionMode = true
				this.showArrow = false  // 隐藏箭头
			},

			// 退出选择模式
			exitSelectionMode() {
				// 如果已在退出过渡中，不重复处理
				if (this.isExitingSelection) return

				// 开始退出过渡（模拟选中当前卡片）
				this.isExitingSelection = true
				this.exitingSelectedIndex = 0
				this.keepContentVisible = true

				// 第一阶段(400ms)：卡片位置动画完成，退出选择模式
				setTimeout(() => {
					this.isExitingSelection = false
					this.exitingSelectedIndex = -1
					this.isSelectionMode = false
					this.selectionScrollY = 0
					this.overPullDistance = 0
					// 显示箭头（下拉退出不涉及 cardOrder 变化，可以直接显示）
					this.showArrow = true
				}, 400)

				// 第二阶段(700ms)：导航栏遮挡后隐藏内容
				setTimeout(() => {
					this.keepContentVisible = false
				}, 700)
			},

			// 惯性滚动
			startInertiaScroll() {
				const friction = 0.95  // 摩擦系数（越小衰减越快）
				const minVelocity = 0.1  // 最小速度阈值

				const animate = () => {
					// 速度衰减
					this.velocity *= friction

					// 速度太小，停止动画
					if (Math.abs(this.velocity) < minVelocity) {
						this.velocity = 0
						this.isScrolling = false
						this.inertiaAnimationId = null
						return
					}

					// 更新滚动位置（velocity 单位是 px/ms，每帧约 16ms）
					const delta = this.velocity * 16

					// 计算边界
					// 当 spaceCount >= 4 时，需要额外算上独立的新建按钮
					const addCardCount = this.spaceCount >= 4 ? 1 : 0
					const totalHeight = (this.orderedTopics.length + addCardCount) * (this.cardHeight + this.selectionGap)
					const maxScroll = Math.max(0, totalHeight - this.screenHeight + this.selectionTopPadding * 2)

					const newScrollY = this.selectionScrollY + delta

					if (newScrollY < 0) {
						this.selectionScrollY = 0
						this.velocity = 0
						this.isScrolling = false
						this.inertiaAnimationId = null
						return
					} else if (newScrollY > maxScroll) {
						this.selectionScrollY = maxScroll
						this.velocity = 0
						this.isScrolling = false
						this.inertiaAnimationId = null
						return
					}

					this.selectionScrollY = newScrollY
					this.inertiaAnimationId = requestAnimationFrame(animate)
				}

				this.inertiaAnimationId = requestAnimationFrame(animate)
			},

			// 卡片点击处理
			handleCardClick(card, index) {
				// 新建卡片点击直接导航到创建页面
				if (card.cardType === 'add') {
					this.handleAddCard()
					return
				}

				if (!this.isSelectionMode) {
					if (index === 0) {
						// 点击主卡片：跳转到学习空间
						this.navigateToLearningSpace(this.currentTopic)
					} else if (index > 0 && index <= 3) {
						// 点击堆叠卡片：进入选择模式
						this.enterSelectionMode()
					}
					return
				}

				// 选择模式下：进入退出过渡状态
				this.exitingSelectedIndex = index
				this.isExitingSelection = true
				this.keepContentVisible = true  // 保持内容可见

				// 第一阶段(400ms)：卡片位置动画完成，退出选择模式，导航栏开始滑入
				setTimeout(() => {
					if (index !== 0) {
						const selectedCard = this.orderedTopics[index]
						// 只有真实空间卡片才参与顺序重排（新建卡片不参与）
						if (selectedCard.cardType === 'space') {
							this.cardOrder = [
								selectedCard.originalIndex,
								...this.cardOrder.filter(i => i !== selectedCard.originalIndex)
							]
							// 持久化保存
							this.saveCardOrder()
						}
					}
					// 清除退出过渡状态并退出选择模式
					this.isExitingSelection = false
					this.exitingSelectedIndex = -1
					this.isSelectionMode = false
					this.selectionScrollY = 0
					// 注意：keepContentVisible 保持 true，内容仍然可见

					// 等待 DOM 更新完成后再显示箭头，确保过渡动画正常触发
					this.$nextTick(() => {
						// 延迟一段时间，让浏览器完成 DOM 重排后再触发过渡
						setTimeout(() => {
							this.showArrow = true
						}, 50)
					})
				}, 400)

				// 第二阶段(700ms)：导航栏基本遮挡住，隐藏内容
				setTimeout(() => {
					this.keepContentVisible = false
				}, 700)
			},

			// 添加新卡片
			handleAddCard() {
				// 直接导航，不等待动画
				// #ifdef APP-PLUS
				uni.navigateTo({
					url: '/pages/createSpace/createSpace',
					animationType: 'slide-in-right',
					animationDuration: 300
				})
				// #endif

				// #ifndef APP-PLUS
				uni.navigateTo({
					url: '/pages/createSpace/createSpace'
				})
				// #endif
			},

			// 添加新学习空间（从 createSpace 页面回调）
			// 现在改为刷新数据，因为空间已在后端创建
			async addNewLearningSpace(newSpace) {
				await this.loadSpaces()
			},

			// 导航到快速对话页面
			navigateToChat() {
				// #ifdef APP-PLUS
				uni.navigateTo({
					url: '/pages/quickChat/quickChat',
					animationType: 'slide-in-right',
					animationDuration: 300
				})
				// #endif

				// #ifndef APP-PLUS
				uni.navigateTo({
					url: '/pages/quickChat/quickChat'
				})
				// #endif
			},

			// 导航到账户页面
			navigateToAccount() {
				// #ifdef APP-PLUS
				uni.navigateTo({
					url: '/pages/account/account',
					animationType: 'slide-in-right',
					animationDuration: 300
				})
				// #endif

				// #ifndef APP-PLUS
				uni.navigateTo({
					url: '/pages/account/account'
				})
				// #endif
			},

			// 导航到学习空间页面
			navigateToLearningSpace(topic) {
				const url = `/pages/learningSpace/learningSpace?id=${topic.id}&name=${encodeURIComponent(topic.name)}`

				// #ifdef APP-PLUS
				uni.navigateTo({
					url,
					animationType: 'slide-in-right',
					animationDuration: 300
				})
				// #endif

				// #ifndef APP-PLUS
				uni.navigateTo({ url })
				// #endif
			},

			// 点击删除按钮
			handleDeleteClick(card) {
				this.deletingSpace = { id: card.id, name: card.name }
				this.showDeleteModal = true
			},

			// 确认删除学习空间
			async doDeleteSpace() {
				if (this.isDeleting || !this.deletingSpace) return
				this.isDeleting = true

				try {
					await deleteSpace(this.deletingSpace.id)
					this.showDeleteModal = false
					this.showToast('学习空间已删除', 'success')

					// 刷新空间列表（保持选择模式）
					await this.loadSpaces()

					// 如果没有空间了，退出选择模式
					if (this.spaceCount === 0) {
						this.isSelectionMode = false
						this.showArrow = true
					}
				} catch (error) {
					this.showToast(error.message || '删除失败，请重试', 'error')
				} finally {
					this.isDeleting = false
					this.deletingSpace = null
				}
			},

			// 显示 Toast 通知
			showToast(message, type = 'info') {
				this.toast = { visible: true, message, type }
			}
		}
	}
</script>

<style>
	/* 全局盒模型 */
	view, text {
		box-sizing: border-box;
	}

	.page-container {
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		background-color: #0A0A12;
		overflow-x: hidden;
	}

	.boot-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 300;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(10, 10, 18, 0.92);
	}

	.boot-panel {
		width: 78%;
		max-width: 560rpx;
		padding: 40rpx 36rpx;
		border-radius: 24rpx;
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.16);
		-webkit-backdrop-filter: blur(16px);
		backdrop-filter: blur(16px);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 20rpx;
	}

	.boot-title {
		font-size: 30rpx;
		font-weight: 600;
		color: #ffffff;
		text-align: center;
	}

	.boot-subtitle {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.72);
	}

	.boot-retry {
		margin-top: 8rpx;
		padding: 12rpx 34rpx;
		border-radius: 999rpx;
		background: rgba(0, 136, 255, 0.85);
	}

	.boot-retry-text {
		font-size: 26rpx;
		font-weight: 600;
		color: #ffffff;
	}

	/* ========== Aurora Background ========== */
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

	/* 蓝色光斑 - 顺时针大范围流动 */
	.aurora-blob-1 {
		width: 800rpx;
		height: 800rpx;
		background: radial-gradient(circle, #0066FF 0%, transparent 70%);
		top: -200rpx;
		right: -200rpx;
		animation: aurora-flow-1 12s ease-in-out infinite;
	}

	/* 紫色光斑 - 逆时针流动 */
	.aurora-blob-2 {
		width: 700rpx;
		height: 700rpx;
		background: radial-gradient(circle, #8B5CF6 0%, transparent 70%);
		top: 20%;
		left: -200rpx;
		animation: aurora-flow-2 15s ease-in-out infinite;
	}

	/* 青色光斑 - 上下脉动 */
	.aurora-blob-3 {
		width: 600rpx;
		height: 600rpx;
		background: radial-gradient(circle, #00FFFF 0%, transparent 70%);
		bottom: 10%;
		right: -150rpx;
		animation: aurora-flow-3 10s ease-in-out infinite;
	}

	/* 粉色光斑 - 对角穿梭 */
	.aurora-blob-4 {
		width: 500rpx;
		height: 500rpx;
		background: radial-gradient(circle, #FF00FF 0%, transparent 70%);
		bottom: 30%;
		left: 30%;
		animation: aurora-flow-4 14s ease-in-out infinite;
	}

	/* 蓝色光斑动画 - 顺时针大范围流动 */
	@keyframes aurora-flow-1 {
		0%, 100% {
			transform: translate(0, 0) scale(1);
			opacity: 0.5;
		}
		25% {
			transform: translate(150rpx, 100rpx) scale(1.4);
			opacity: 0.7;
		}
		50% {
			transform: translate(100rpx, 200rpx) scale(1.2);
			opacity: 0.6;
		}
		75% {
			transform: translate(-50rpx, 100rpx) scale(1.5);
			opacity: 0.8;
		}
	}

	/* 紫色光斑动画 - 逆时针流动 */
	@keyframes aurora-flow-2 {
		0%, 100% {
			transform: translate(0, 0) scale(1);
			opacity: 0.4;
		}
		33% {
			transform: translate(200rpx, -100rpx) scale(1.3);
			opacity: 0.6;
		}
		66% {
			transform: translate(100rpx, 150rpx) scale(1.5);
			opacity: 0.7;
		}
	}

	/* 青色光斑动画 - 上下脉动 */
	@keyframes aurora-flow-3 {
		0%, 100% {
			transform: translate(0, 0) scale(1);
			opacity: 0.5;
		}
		50% {
			transform: translate(-100rpx, -150rpx) scale(1.6);
			opacity: 0.8;
		}
	}

	/* 粉色光斑动画 - 对角穿梭 */
	@keyframes aurora-flow-4 {
		0%, 100% {
			transform: translate(0, 0) scale(1);
			opacity: 0.25;
		}
		50% {
			transform: translate(-150rpx, -200rpx) scale(1.4);
			opacity: 0.5;
		}
	}

	/* 尊重用户减弱动画偏好 */
	@media (prefers-reduced-motion: reduce) {
		.aurora-blob {
			animation: none !important;
		}
	}

	/* ========== 背景遮罩 ========== */
	.selection-backdrop {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, 0.8);
		opacity: 0;
		pointer-events: none;
		z-index: 50;
		transition: opacity 0.35s ease;
	}

	.selection-backdrop.backdrop-active {
		opacity: 1;
		pointer-events: auto;
	}

	/* ========== 标题区域 ========== */
	.header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: calc(100vh / 26 * 10);
		padding: 0 40rpx;
		transition: all 0.35s ease;
		opacity: 1;
		transform: translateY(0);
		z-index: 40;
	}

	.header.header-hidden {
		opacity: 0;
		transform: translateY(-50rpx);
		pointer-events: none;
	}

	.header-title {
		position: absolute;
		top: calc(100vh / 26 * 6);
		left: 40rpx;
		transform: translateY(-50%);
		display: flex;
		justify-content: flex-start;
		align-items: baseline;
	}

	.header-text-light {
		font-size: 44rpx;
		font-weight: 600;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.header-text-highlight {
		font-size: 54rpx;
		font-weight: 600;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.header-subtitle {
		position: absolute;
		top: calc(100vh / 26 * 8);
		left: calc(100% / 12 * 5);
		height: calc(100vh / 26);
		display: flex;
		align-items: center;
		font-size: 44rpx;
		font-weight: 600;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	/* ========== 统一卡片容器 ========== */
	.unified-cards-container {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 55;
		touch-action: none;
	}

	.unified-cards-container.selection-mode,
	.unified-cards-container.swiping-mode {
		z-index: 100;
	}

	/* ========== 统一卡片基础样式 ========== */
	/* 所有卡片使用 fixed position，通过 transform 控制位置 */
	.unified-card {
		position: fixed;
		top: calc(100vh / 26 * 11);
		left: calc(100% / 12 * 1);
		width: calc(100% / 12 * 10);
		height: calc(100vh / 26 * 7);
		border-radius: 36rpx;
		padding: 20rpx 30rpx 30rpx;
		transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease;
		transform-origin: center top;
		pointer-events: auto;
		z-index: 60;
	}

	/* ========== 主卡片样式 ========== */
	.unified-card.main-card {
		z-index: 60;
	}

	/* ========== 堆叠卡片样式 ========== */
	.unified-card.stacked-card {
		border-radius: 36rpx 36rpx 0 0;
		z-index: 10;
	}

	/* ========== 选择模式卡片样式 ========== */
	.unified-card.selection-card {
		z-index: 101;
	}

	/* ========== 隐藏卡片样式 ========== */
	.unified-card.hidden-card {
		pointer-events: none;
		z-index: 1;
	}

	/* ========== 卡片内容样式 ========== */
	.card-header {
		display: flex;
		flex-direction: column;
	}

	.card-title {
		font-size: 40rpx;
		color: #000000;
		font-weight: 600;
		transition: opacity 0.15s ease;
	}

	.card-info-row {
		position: absolute;
		left: 30rpx;
		right: 30rpx;
		top: calc(100% / 7 * 1.35);
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	/* 堆叠卡片隐藏详细内容 - 使用 opacity 支持过渡 */
	.unified-card.stacked-card .card-info-row,
	.unified-card.stacked-card .progress-bar,
	.unified-card.stacked-card .knowledge-tree-container {
		opacity: 0;
		visibility: hidden;
		transition: opacity 0.15s ease, visibility 0.15s ease;
	}

	/* 退出过渡时保持内容可见（等待导航栏遮挡） */
	.unified-card.stacked-card.keep-content .card-info-row,
	.unified-card.stacked-card.keep-content .progress-bar,
	.unified-card.stacked-card.keep-content .knowledge-tree-container {
		opacity: 1;
		visibility: visible;
	}

	/* 后面两张堆叠卡片的标题淡出 */
	.unified-card.stacked-card.back-stacked .card-title,
	.unified-card.selection-card.exiting-back .card-title {
		opacity: 0;
	}

	.card-part {
		font-size: 20rpx;
		color: #333333;
	}

	.card-percentage {
		font-size: 20rpx;
		color: #ffffff;
		font-weight: 600;
	}

	/* 进度条 */
	.progress-bar {
		position: absolute;
		left: 30rpx;
		right: 30rpx;
		top: calc(100% / 7 * 2);
		display: flex;
		height: 10rpx;
		background-color: #D6D6D6;
		border-radius: 5rpx;
	}

	.progress-fill {
		height: 100%;
		transition: width 0.3s ease;
	}

	.progress-green {
		background-color: #7ACC71;
		border-radius: 5rpx;
	}

	/* 知识树容器 */
	.knowledge-tree-container {
		position: absolute;
		left: calc(100% / 20);
		width: calc(100% / 10 * 9);
		top: calc(100% / 7 * 2.5);
		height: calc(100% / 7 * 4);
		display: flex;
		justify-content: center;
		align-items: center;
		background-color: rgba(0, 0, 0, 0.85);
		border-radius: 24rpx;
		overflow: hidden;
	}

	.knowledge-tree-loading {
		display: flex;
		justify-content: center;
		align-items: center;
		width: 100%;
		height: 100%;
	}

	.loading-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.3);
	}

	/* 箭头按钮 */
	.arrow-button {
		position: absolute;
		top: calc(100% / 7 * 6);
		left: calc(100% / 10 * 9);
		transform: translate(-50%, -50%);
		display: flex;
		justify-content: center;
		align-items: center;
		opacity: 1;
		/* 过渡动画：淡入淡出 + 轻微位移 */
		transition: opacity 0.35s ease, transform 0.35s ease;
	}

	.arrow-button.arrow-hidden {
		opacity: 0;
		transform: translate(-50%, -50%) translateY(20rpx);
		pointer-events: none;
	}

	.arrow-icon {
		width: 48rpx;
		height: 48rpx;
		filter: brightness(0) invert(1);
	}

	/* ========== 添加卡片按钮 ========== */
	.add-card {
		opacity: 0;
		pointer-events: none;
		padding: 0;
		z-index: 100;
	}

	.add-card.add-card-visible {
		opacity: 1;
		pointer-events: auto;
	}

	.add-card-inner {
		border: 4rpx dashed rgba(255, 255, 255, 0.3);
		border-radius: 36rpx;
		height: calc(100vh / 26 * 7);
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
	}

	.add-card-icon {
		font-size: 72rpx;
		color: rgba(255, 255, 255, 0.4);
		line-height: 1;
		margin-bottom: 16rpx;
	}

	.add-card-text {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	/* ========== 空状态标题样式 ========== */
	.header-title-empty {
		position: absolute;
		top: calc(100vh / 26 * 5);
		left: 40rpx;
		right: 40rpx;
		display: flex;
		flex-direction: column;
		gap: 20rpx;
	}

	.header-text-line1 {
		font-size: 44rpx;
		font-weight: 600;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.header-text-line2 {
		font-size: 44rpx;
		font-weight: 600;
		text-align: right;
		padding-left: 30%;
		background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	/* ========== 新建卡片在堆叠位置的样式 ========== */
	.unified-card.add-card-stacked {
		padding: 0;
		border-radius: 36rpx 36rpx 0 0;
	}

	.unified-card.add-card-main-position {
		padding: 0;
	}

	.unified-card.add-card-selection {
		padding: 0;
	}

	/* 堆叠位置和主位置的新建卡片内框适配 */
	.add-card-stacked .add-card-inner,
	.add-card-main-position .add-card-inner,
	.add-card-selection .add-card-inner {
		height: 100%;
	}

	/* 主位置新建卡片样式增强（0空间场景） */
	.add-card-main.add-card-inner {
		border-color: rgba(255, 255, 255, 0.4);
	}

	.add-card-main .add-card-icon {
		font-size: 96rpx;
		color: rgba(255, 255, 255, 0.5);
	}

	.add-card-main .add-card-text {
		font-size: 32rpx;
		color: rgba(255, 255, 255, 0.5);
	}

	/* ========== 底部导航栏 ========== */
	.bottom-nav {
		position: fixed;
		top: calc(100vh / 26 * 23);
		bottom: 0;
		left: 0;
		right: 0;

		/* 上方圆角 */
		border-radius: 36rpx 36rpx 0 0;

		/* 毛玻璃：半透明背景 */
		background-color: rgba(48, 48, 58, 0.55);

		/* 毛玻璃模糊效果 */
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);

		/* 玻璃质感边缘：微光边框 */
		border-top: 1rpx solid rgba(255, 255, 255, 0.15);
		border-left: 1rpx solid rgba(255, 255, 255, 0.08);
		border-right: 1rpx solid rgba(255, 255, 255, 0.08);

		/* 上方阴影 + 内侧高光 */
		box-shadow:
			0 -4rpx 30rpx rgba(0, 0, 0, 0.3),
			inset 0 1rpx 0 rgba(255, 255, 255, 0.1);

		display: flex;
		justify-content: space-around;
		align-items: center;
		padding-bottom: env(safe-area-inset-bottom);
		z-index: 100;
		transition: all 0.35s ease;
	}

	.bottom-nav.nav-hidden {
		opacity: 0;
		transform: translateY(100rpx);
		pointer-events: none;
	}

	/* 不支持 backdrop-filter 时的降级方案 */
	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.bottom-nav {
			background-color: rgba(48, 48, 58, 0.92);
		}
	}

	.nav-item {
		display: flex;
		justify-content: center;
		align-items: center;
		width: 100rpx;
		height: 100rpx;
	}

	.nav-icon {
		width: 75rpx;
		height: 75rpx;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.icon-img {
		width: 75rpx;
		height: 75rpx;
		filter: brightness(0) invert(1);
	}

	.nav-item-active .nav-icon-wrapper {
		width: 140rpx;
		height: 140rpx;
		min-width: 140rpx;
		min-height: 140rpx;

		/* 原始蓝色背景 */
		background-color: #0088FF;

		/* 玻璃边缘光泽 */
		border: 1rpx solid rgba(255, 255, 255, 0.2);

		/* 外发光 + 内侧高光 */
		box-shadow:
			0 4rpx 24rpx rgba(0, 136, 255, 0.35),
			inset 0 1rpx 0 rgba(255, 255, 255, 0.15);

		border-radius: 50%;
		aspect-ratio: 1 / 1;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-shrink: 0;
	}

	.icon-img-active {
		width: 72rpx;
		height: 72rpx;
		filter: brightness(0) invert(1);
	}

	/* ========== 删除按钮 ========== */
	.delete-btn {
		position: absolute;
		top: 16rpx;
		right: 16rpx;
		width: 48rpx;
		height: 48rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		opacity: 0;
		transform: scale(0.7);
		pointer-events: none;
		transition: opacity 0.3s ease, transform 0.3s ease;
		z-index: 10;
	}

	.delete-btn.delete-btn-visible {
		opacity: 1;
		transform: scale(1);
		pointer-events: auto;
	}

	.delete-btn:active {
		transform: scale(0.85);
	}

	.delete-icon {
		width: 40rpx;
		height: 40rpx;
		filter: brightness(0) saturate(100%) invert(28%) sepia(93%) saturate(5765%) hue-rotate(351deg) brightness(97%) contrast(93%);
	}

</style>
