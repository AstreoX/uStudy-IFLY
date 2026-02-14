<template>
	<view class="learning-space-page">
		<!-- 开发网格 -->
		<view class="dev-grid" v-if="showDevGrid">
			<view class="grid-row" v-for="row in 26" :key="'row-'+row">
				<view
					class="grid-cell"
					:class="{'grid-origin': row === 1 && col === 1}"
					v-for="col in 12"
					:key="'col-'+col"
				></view>
			</view>
		</view>

		<!-- 顶部导航栏 -->
		<view class="space-nav-bar">
			<view class="nav-left" @click="goBack">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
			</view>
			<text class="nav-title">{{ spaceTitle }}</text>
			<view class="nav-right" @click="openSettings">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/sliders-horizontal.svg" mode="aspectFit"></image>
			</view>
		</view>

		<!-- 小地图 -->
		<view class="minimap-container" @touchstart="onMinimapTouchStart" @touchmove="onMinimapTouchMove">
			<canvas
				canvas-id="minimapCanvas"
				id="minimapCanvas"
				class="minimap-canvas"
			></canvas>
		</view>

		<!-- 知识图谱画布 -->
		<view
			class="graph-container"
			ref="graphContainer"
			@touchstart="onGraphTouchStart"
			@touchmove.prevent="onGraphTouchMove"
			@touchend="onGraphTouchEnd"
		>
			<canvas
				canvas-id="graphCanvas"
				id="graphCanvas"
				class="graph-canvas"
			></canvas>
		</view>

		<!-- 节点信息弹窗 -->
		<view
			v-if="selectedNode"
			class="node-popup"
			:style="{
				left: nodePopupPosition.x + 'px',
				top: nodePopupPosition.y + 'px'
			}"
		>
			<view class="node-popup-content">
				<!-- 左侧：节点名称 -->
				<text class="node-popup-name">{{ selectedNode.label }}</text>

				<!-- 右侧：圆环进度条 或 锁图标 -->
				<view class="mastery-ring-container">
					<!-- 已掌握节点：显示圆环进度条 -->
					<view
						v-if="selectedNode.mastery != null"
						class="mastery-ring"
						:style="{ background: masteryRingGradient }"
					>
						<view class="mastery-ring-inner">
							<text class="mastery-ring-text">{{ selectedNode.mastery }}</text>
						</view>
					</view>

					<!-- 未掌握节点：显示锁图标 -->
					<image
						v-else
						class="mastery-lock-icon"
						src="/static/icons/phosphor-icons/SVGs/fill/lock-key-fill.svg"
						mode="aspectFit"
					></image>
				</view>
			</view>
		</view>

		<!-- 操作按钮 -->
		<view class="action-buttons">
			<view class="action-btn" :class="{ 'action-btn-active': isPathHighlightOn }" @click="togglePathHighlight">
				<image class="action-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/path.svg" mode="aspectFit"></image>
			</view>
			<view class="action-btn" @click="handleAddFile">
				<image class="action-btn-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit"></image>
			</view>
		</view>

		<!-- 添加文件弹窗 -->
		<view v-if="showAddFilePopup" class="add-file-popup-wrapper" @click="closeAddFilePopup">
			<view
				class="add-file-popup"
				:class="{ 'popup-show': addFilePopupVisible }"
				@click.stop
			>
				<view class="popup-option" @click="handleAddDocument">
					<image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
					<text class="popup-option-text">添加文档</text>
				</view>
				<view class="popup-divider"></view>
				<view class="popup-option" @click="handleAddLink">
					<image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit" />
					<text class="popup-option-text">添加链接</text>
				</view>
				<!-- 小箭头指向按钮 -->
				<view class="popup-arrow"></view>
			</view>
		</view>

		<!-- 添加链接对话框 -->
		<view
			v-if="showLinkDialog"
			class="link-dialog-overlay"
			:class="{ 'overlay-show': linkDialogVisible }"
			@click="closeLinkDialog"
		>
			<view
				class="link-dialog"
				:class="{ 'dialog-show': linkDialogVisible }"
				@click.stop
			>
				<text class="link-dialog-title">添加链接</text>

				<view class="link-dialog-content">
					<view class="link-input-group">
						<text class="link-input-label">标题</text>
						<input
							class="link-input"
							v-model="linkTitle"
							placeholder="输入链接标题"
							placeholder-class="link-input-placeholder"
							maxlength="255"
						/>
					</view>

					<view class="link-input-group">
						<text class="link-input-label">网址</text>
						<input
							class="link-input"
							v-model="linkUrl"
							placeholder="https://example.com"
							placeholder-class="link-input-placeholder"
							type="url"
						/>
					</view>
				</view>

				<view class="link-dialog-actions">
					<view class="link-btn link-btn-cancel" @click="closeLinkDialog">
						<text class="link-btn-text">取消</text>
					</view>
					<view
						class="link-btn link-btn-confirm"
						:class="{ 'link-btn-disabled': isAddingLink }"
						@click="submitLink"
					>
						<text class="link-btn-text">{{ isAddingLink ? '添加中...' : '添加' }}</text>
					</view>
				</view>
			</view>
		</view>

		<!-- 上传进度遮罩 -->
		<view v-if="isUploading" class="upload-overlay">
			<view class="upload-content">
				<view class="upload-spinner"></view>
				<text class="upload-text">上传中 {{ uploadProgress }}%</text>
			</view>
		</view>

		<!-- 加载遮罩 -->
		<view v-if="isLoading" class="loading-overlay">
			<view class="loading-content">
				<!-- 多节点轨道加载器 -->
				<view class="loading-spinner-enhanced">
					<view class="loading-center-glow"></view>
					<view class="loading-dot loading-dot-1"></view>
					<view class="loading-dot loading-dot-2"></view>
					<view class="loading-dot loading-dot-3"></view>
				</view>
				<text class="loading-text">{{ loadingText }}</text>
				<!-- 不确定性进度条 -->
				<view class="loading-progress-bar">
					<view class="loading-progress-fill"></view>
				</view>
			</view>
		</view>

		<!-- 图谱加载失败提示 -->
		<view v-if="graphLoadFailed && !isLoading" class="graph-failed-overlay">
			<view class="failed-content">
				<image
					class="failed-icon"
					src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg"
					mode="aspectFit"
				/>
				<text class="failed-title">知识图谱生成失败</text>
				<text class="failed-message">{{ failedMessage }}</text>
				<view
					class="regenerate-btn"
					:class="{ 'regenerate-btn-disabled': regenerateAttempts >= 3 }"
					@click="regenerateKnowledgeGraph"
				>
					<text class="regenerate-btn-text">
						{{ regenerateAttempts >= 3 ? '稍后再试' : '重新生成' }}
					</text>
				</view>
				<text v-if="regenerateAttempts > 0 && regenerateAttempts < 3" class="retry-hint">
					已重试 {{ regenerateAttempts }}/3 次
				</text>
			</view>
		</view>

		<!-- 底部输入栏 -->
			<view class="input-bar" :style="{ bottom: keyboardHeight > 0 ? keyboardHeight + 'px' : '' }">
				<view class="input-bar-inner">
					<!-- 待发送附件预览区域 -->
					<view v-if="pendingAttachments.length > 0 || uploadingFiles.length > 0" class="pending-attachments-area">
						<!-- 已上传待发送的附件 -->
						<view v-for="att in pendingAttachments" :key="att.id" class="attachment-preview-item">
							<view v-if="att.attachment_type === 'image'" class="attachment-image-preview">
								<image :src="att.thumbnail_url || att.file_url" class="attachment-thumbnail" mode="aspectFill"></image>
								<view class="attachment-remove-btn" @click.stop="removePendingAttachment(att.id)">
									<image class="remove-icon" src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit"></image>
								</view>
							</view>
							<view v-else class="attachment-file-preview">
								<image class="file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit"></image>
								<view class="attachment-file-meta">
									<text class="file-name">{{ att.original_filename }}</text>
									<text class="file-size">{{ formatAttachmentFileSize(att.file_size) }}</text>
								</view>
								<view class="attachment-remove-btn" @click.stop="removePendingAttachment(att.id)">
									<image class="remove-icon" src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit"></image>
								</view>
							</view>
						</view>

						<!-- 上传中的文件 -->
						<view v-for="file in uploadingFiles" :key="file.id" class="attachment-uploading-item">
							<view class="uploading-content">
								<image class="file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit"></image>
								<view class="uploading-info">
									<text class="file-name">{{ file.name }}</text>
									<progress v-if="!file.error" :percent="file.progress" class="upload-progress" stroke-width="2" activeColor="#3B82F6" backgroundColor="#E5E7EB" />
									<text v-if="file.error" class="upload-error">{{ file.error }}</text>
								</view>
							</view>
						</view>
					</view>

					<view
						class="input-field-wrapper"
						:class="{ 'input-field-wrapper-expanded': textareaLineCount > 1 }"
					>
					<view class="input-action" @click="handlePlusClick">
						<image class="input-action-icon" src="/static/icons/phosphor-icons/SVGs/regular/plus.svg" mode="aspectFit"></image>
					</view>

					<textarea
						ref="textareaRef"
						class="input-field"
						v-model="inputText"
						placeholder="有问题，尽管问"
						placeholder-class="input-placeholder"
						:maxlength="-1"
						:adjust-position="false"
						confirm-type="send"
						:style="{ height: textareaHeight, overflowY: textareaOverflow }"
						@input="onTextareaInput"
						@linechange="onTextareaLineChange"
						@confirm="sendMessage"
						@focus="onInputFocus"
						@blur="onInputBlur"
					/>

					<view class="input-action send-btn-wrapper" @click="sendMessage">
						<image
							class="input-action-icon send-action-icon"
							:class="{ 'send-btn-disabled': !canSend }"
							src="/static/icons/phosphor-icons/SVGs Flat/fill/arrow-circle-up-fill.svg"
							mode="aspectFit"
						></image>
					</view>
				</view>
			</view>

			<view class="input-safe-area"></view>
		</view>

		<!-- +号弹窗 -->
		<view v-if="showPlusPopup" class="plus-popup-wrapper" @click="closePlusPopup">
			<view class="plus-popup" :class="{ 'popup-show': plusPopupVisible }" @click.stop>
				<view class="popup-option" @click="handleSelectFile">
					<image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
					<text class="popup-option-text">添加文件</text>
				</view>
				<view class="popup-divider"></view>
				<view class="popup-option" @click="handleSelectImage">
					<image class="popup-option-icon" src="/static/icons/phosphor-icons/SVGs/regular/image.svg" mode="aspectFit" />
					<text class="popup-option-text">添加图片</text>
				</view>
				<view class="popup-arrow"></view>
			</view>
		</view>

		<!-- 图片来源选择弹窗 -->
		<image-source-picker
			:visible="showImageSourcePicker"
			@camera="handleCameraSelect"
			@album="handleAlbumSelect"
			@close="showImageSourcePicker = false"
		/>
	</view>
</template>

<script>
	import { getSpaceGraph, getTaskStatus, generateKnowledgeGraph, addSpaceLink, uploadSpaceDocument } from '@/api/space'
	import { uploadAttachment, deleteAttachment, formatFileSize } from '@/api/attachment'
	import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
	import ImageSourcePicker from '@/components/image-source-picker/image-source-picker.vue'

	// 掌握度颜色渐变端点 (0-100 分段插值，避免中间棕色)
	const MASTERY_COLOR_START = { r: 255, g: 50, b: 66 }   // #FF3242 (mastery=0, 珊瑚红)
	const MASTERY_COLOR_MID = { r: 255, g: 217, b: 61 }    // #FFD93D (mastery=50, 浅黄色)
	const MASTERY_COLOR_END = { r: 73, g: 255, b: 170 }    // #49FFAA (mastery=100, 薄荷绿)
	const UNMASTERED_NODE_COLOR = '#9CA3AF'
	const UNMASTERED_NODE_GLOW = 'rgba(156, 163, 175, 0.50)'
	const UNMASTERED_NODE_OUTLINE = 'rgba(226, 232, 240, 0.26)'
	const KNOWLEDGE_EDGE_COLOR = 'rgba(245, 248, 255, 0.42)'
	const KNOWLEDGE_EDGE_WIDTH = 1.8

	/**
	 * 根据掌握度 (0-100) 计算分段渐变颜色
	 * 0-50: 珊瑚红 → 浅黄色
	 * 50-100: 浅黄色 → 薄荷绿
	 * @param {number} mastery - 掌握度 0-100
	 * @returns {string} - Hex 颜色值
	 */
	function getMasteryColor(mastery) {
		if (mastery == null || mastery < 0) mastery = 0
		if (mastery > 100) mastery = 100

		let r, g, b

		if (mastery <= 50) {
			// 0-50: 珊瑚红 → 浅黄色
			const t = mastery / 50
			r = Math.round(MASTERY_COLOR_START.r + (MASTERY_COLOR_MID.r - MASTERY_COLOR_START.r) * t)
			g = Math.round(MASTERY_COLOR_START.g + (MASTERY_COLOR_MID.g - MASTERY_COLOR_START.g) * t)
			b = Math.round(MASTERY_COLOR_START.b + (MASTERY_COLOR_MID.b - MASTERY_COLOR_START.b) * t)
		} else {
			// 50-100: 浅黄色 → 薄荷绿
			const t = (mastery - 50) / 50
			r = Math.round(MASTERY_COLOR_MID.r + (MASTERY_COLOR_END.r - MASTERY_COLOR_MID.r) * t)
			g = Math.round(MASTERY_COLOR_MID.g + (MASTERY_COLOR_END.g - MASTERY_COLOR_MID.g) * t)
			b = Math.round(MASTERY_COLOR_MID.b + (MASTERY_COLOR_END.b - MASTERY_COLOR_MID.b) * t)
		}

		return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
	}

	/**
	 * 根据掌握度计算分段渐变发光颜色
	 * 0-50: 珊瑚红 → 浅黄色
	 * 50-100: 浅黄色 → 薄荷绿
	 * @param {number} mastery - 掌握度 0-100
	 * @param {number} opacity - 透明度 0-1，默认 0.5
	 * @returns {string} - RGBA 颜色值
	 */
	function getMasteryGlowColor(mastery, opacity = 0.5) {
		if (mastery == null || mastery < 0) mastery = 0
		if (mastery > 100) mastery = 100

		let r, g, b

		if (mastery <= 50) {
			// 0-50: 珊瑚红 → 浅黄色
			const t = mastery / 50
			r = Math.round(MASTERY_COLOR_START.r + (MASTERY_COLOR_MID.r - MASTERY_COLOR_START.r) * t)
			g = Math.round(MASTERY_COLOR_START.g + (MASTERY_COLOR_MID.g - MASTERY_COLOR_START.g) * t)
			b = Math.round(MASTERY_COLOR_START.b + (MASTERY_COLOR_MID.b - MASTERY_COLOR_START.b) * t)
		} else {
			// 50-100: 浅黄色 → 薄荷绿
			const t = (mastery - 50) / 50
			r = Math.round(MASTERY_COLOR_MID.r + (MASTERY_COLOR_END.r - MASTERY_COLOR_MID.r) * t)
			g = Math.round(MASTERY_COLOR_MID.g + (MASTERY_COLOR_END.g - MASTERY_COLOR_MID.g) * t)
			b = Math.round(MASTERY_COLOR_MID.b + (MASTERY_COLOR_END.b - MASTERY_COLOR_MID.b) * t)
		}

		return `rgba(${r}, ${g}, ${b}, ${opacity})`
	}

	// 同心圆布局配置
	const LAYOUT_CONFIG = {
		baseRadius: 120,      // 第一层距中心距离
		levelSpacing: 100     // 每层之间的间距
	}

	// 生成测试数据 (约50个节点)
	function generateMockData() {
		const nodes = []
		const edges = []
		let nodeId = 1

		// 根节点
		nodes.push({
			id: nodeId++,
			label: 'Root',
			level: 0,
			mastery: 100,  // 完全掌握
			collapsed: false,
			x: 0, y: 0, vx: 0, vy: 0
		})

		// 一级节点 (4个)
		const level1Count = 4
		for (let i = 0; i < level1Count; i++) {
			const masteryValues = [100, 60, null, 40]  // null 表示未掌握
			nodes.push({
				id: nodeId,
				label: `Topic ${nodeId}`,
				level: 1,
				mastery: masteryValues[i % 4],
				parent: 1,
				collapsed: false,
				x: 0, y: 0, vx: 0, vy: 0
			})
			edges.push({ from: 1, to: nodeId })
			nodeId++
		}

		// 二级节点 (每个一级下3-5个，共约15个)
		const level1Nodes = nodes.filter(n => n.level === 1)
		level1Nodes.forEach((parent, idx) => {
			const childCount = 3 + (idx % 3) // 3-5个子节点
			for (let i = 0; i < childCount; i++) {
				nodes.push({
					id: nodeId,
					label: `Topic ${nodeId}`,
					level: 2,
					mastery: Math.random() < 0.2 ? null : Math.floor(Math.random() * 101),  // 20% 概率为 null（未掌握）
					parent: parent.id,
					collapsed: false,
					x: 0, y: 0, vx: 0, vy: 0
				})
				edges.push({ from: parent.id, to: nodeId })
				nodeId++
			}
		})

		// 三级节点 (每个二级下2-3个，共约35个)
		const level2Nodes = nodes.filter(n => n.level === 2)
		level2Nodes.forEach((parent, idx) => {
			const childCount = 2 + (idx % 2) // 2-3个子节点
			for (let i = 0; i < childCount; i++) {
				nodes.push({
					id: nodeId,
					label: `Topic ${nodeId}`,
					level: 3,
					mastery: Math.random() < 0.2 ? null : Math.floor(Math.random() * 101),  // 20% 概率为 null（未掌握）
					parent: parent.id,
					collapsed: false,
					x: 0, y: 0, vx: 0, vy: 0
				})
				edges.push({ from: parent.id, to: nodeId })
				nodeId++
			}
		})

		return { nodes, edges }
	}

	export default {
		components: {
			ImageSourcePicker
		},
		data() {
			return {
				showDevGrid: false,
				spaceId: null,
				// 首次加载标志，避免 onShow 与 mounted 重复加载
				isFirstLoad: true,
				// +号弹窗状态
				showPlusPopup: false,
				plusPopupVisible: false,
				showImageSourcePicker: false,
				spaceTitle: '学习空间',
				inputText: '',
				textareaHeight: 'auto',
				textareaOverflow: 'hidden',
				textareaMaxLines: 4, // 输入框可撑高的最大行数
				textareaLineCount: 1, // 记录 linechange 上报的真实行数（用于非 H5 兜底）
				keyboardHeight: 0,

				// 加载状态
				isLoading: false,
				loadingText: '正在生成知识图谱...',
				taskId: null,

				// 图谱加载失败状态
				graphLoadFailed: false,
				failedMessage: '',
				regenerateAttempts: 0,
				lastRegenerateTime: 0,

				// 知识图谱数据
				nodes: [],
				edges: [],

				// 显示进阶边开关
				showAdvancedEdges: true,

				// 画布变换状态
				scale: 1,
				offsetX: 0,
				offsetY: 0,
				canvasWidth: 0,
				canvasHeight: 0,

				// 小地图尺寸
				minimapWidth: 120,
				minimapHeight: 100,

				// 触摸状态
				lastTouchX: 0,
				lastTouchY: 0,
				lastPinchDistance: 0,
				lastTapTime: 0,
				lastTapX: 0,
				lastTapY: 0,
				isTouching: false,
				isPinching: false,

				// 选中的节点
				selectedNodeId: null,

				// 学习路径高亮
				isPathHighlightOn: false,
				// 学习路径（从后端加载的 LEARNING_PATH 类型边）
				learningPath: [],

				// 画布上下文
				graphCtx: null,
				minimapCtx: null,

				// 性能优化
				renderPending: false,
				minimapPending: false,
				nodeMap: new Map(),
				visibleNodesCache: null,
				childCountCache: new Map(),
				edgeBuckets: {
					treeEdges: [],
					advancedEdges: [],
					pathEdges: [],
					nonPathEdges: []
				},
				learningPathSet: new Set(),
				isInteracting: false,
				interactionEndTimer: null,
				interactionEndDelayMs: 120,
				minimapIntervalMs: 120,
				lastMinimapRenderAt: 0,

				// 单击延迟处理（解决双击时误触发单击的问题）
				tapTimer: null,
				pendingTapX: 0,
				pendingTapY: 0,
				dragDistance: 0,  // 累计拖拽距离，用于区分点击和拖拽

				// 组件销毁标志（防止异步回调在组件销毁后执行）
				isDestroyed: false,
				// initCanvas 重试定时器（用于清理）
				initCanvasTimer: null,

				// 添加文件弹窗状态
				showAddFilePopup: false,
				addFilePopupVisible: false,

				// 添加链接对话框状态
				showLinkDialog: false,
				linkDialogVisible: false,
				linkTitle: '',
				linkUrl: '',
				isAddingLink: false,

				// 上传状态
				isUploading: false,
				uploadProgress: 0,
				pendingAttachments: [],
				uploadingFiles: [],

				// 静默刷新标志，防止并发刷新
				isRefreshing: false,

				// 动画状态管理
				animationState: {
					isAnimating: false,
					startTime: 0,
					duration: 800,
					nodeAppearDelay: 30,
					edgeAppearDelay: 400,
					currentProgress: 0
				},
				nodeAnimationStates: new Map(),
				prefersReducedMotion: false,
				nodeInteractionScale: null  // 节点交互缩放状态 { nodeId, scale }
			}
		},

		computed: {
			// 获取选中节点数据
			selectedNode() {
				if (!this.selectedNodeId) return null
				return this.nodeMap.get(this.selectedNodeId)
			},

			// 计算弹窗位置（屏幕坐标）
			nodePopupPosition() {
				if (!this.selectedNode) return { x: 0, y: 0 }
				const screenX = this.selectedNode.x * this.scale + this.offsetX
				const screenY = this.selectedNode.y * this.scale + this.offsetY
				const radius = this.selectedNode.level === 0 ? 18 : (this.selectedNode.level === 1 ? 14 : 11)
				return {
					x: screenX,
					y: screenY + (radius + 20) * this.scale  // 节点下方
				}
			},

			// 圆环进度条渐变背景
			masteryRingGradient() {
				if (!this.selectedNode) return ''
				const mastery = this.selectedNode.mastery || 0
				const color = getMasteryColor(mastery)
				// conic-gradient 实现圆环进度
				const angle = (mastery / 100) * 360
				return `conic-gradient(${color} 0deg, ${color} ${angle}deg, rgba(255, 255, 255, 0.1) ${angle}deg, rgba(255, 255, 255, 0.1) 360deg)`
			},

			canSend() {
				return this.inputText.trim().length > 0 || this.pendingAttachments.length > 0
			}
		},

		async onLoad(options) {
			if (options.id) {
				this.spaceId = options.id
			}
			if (options.name) {
				this.spaceTitle = decodeURIComponent(options.name)
			}
			if (options.taskId) {
				this.taskId = options.taskId
			}

			// 监听学习路径更新事件
			uni.$on('learningPathUpdated', this.handleLearningPathUpdated)
		},

		async mounted() {
			try {
				// 检测用户无障碍偏好
				// #ifdef H5
				if (typeof window !== 'undefined' && window.matchMedia) {
					this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
				}
				// #endif

				// 如果有 taskId，等待任务完成
				if (this.taskId) {
					this.isLoading = true
					this.loadingText = '正在生成知识图谱...'
					await this.waitForTask(this.taskId)

					// 等待3秒，确保数据库事务commit完成
					this.loadingText = '知识图谱生成中，请稍候...'
					await new Promise(resolve => setTimeout(resolve, 3000))

					// 任务完成后清除 taskId，允许后续 onShow 刷新
					this.taskId = null
				}

				// 从后端加载图谱数据
				if (this.spaceId) {
					this.isLoading = true
					this.loadingText = '正在加载知识图谱...'
					await this.loadGraphData(0)
				} else {
					// 没有 spaceId 时使用 mock 数据（开发用）
					const mockData = generateMockData()
					this.nodes = mockData.nodes
					this.edges = mockData.edges
				}

				this.isLoading = false
			} catch (err) {
				this.isLoading = false
				this.graphLoadFailed = true
				// 用户友好的错误消息
				if (err.message?.includes('timeout') || err.message?.includes('超时')) {
					this.failedMessage = '请求超时，请检查网络后重试'
				} else if (err.message?.includes('Network') || err.message?.includes('网络')) {
					this.failedMessage = '网络连接失败，请检查网络'
				} else {
					this.failedMessage = '加载失败，请重试'
				}
			}

			this.initCanvas()

			// 存储回调引用以便清理
			this.keyboardCallback = (res) => {
				this.keyboardHeight = res.height
			}
			uni.onKeyboardHeightChange(this.keyboardCallback)

			// #ifdef H5
			// H5 平台添加滚轮缩放支持
			this.$nextTick(() => {
				const graphContainer = document.querySelector('.graph-container')
				if (graphContainer) {
					graphContainer.addEventListener('wheel', this.onGraphWheel, { passive: false })
				}
				this.adjustTextareaHeight()
			})
			// #endif

			// #ifndef H5
			this.$nextTick(() => {
				this.adjustTextareaHeight()
			})
			// #endif

			// 标记首次加载完成，后续 onShow 才会触发刷新
			this.isFirstLoad = false
		},

		onShow() {
			// 首次加载由 mounted 处理，跳过
			if (this.isFirstLoad) return

			// 页面已销毁，跳过
			if (this.isDestroyed) return

			// 正在执行任务（生成知识图谱），跳过
			if (this.taskId) return

			// 没有 spaceId，跳过
			if (!this.spaceId) return

			// 静默刷新图谱数据
			this.refreshGraphData()
		},

		beforeDestroy() {
			// 移除学习路径更新事件监听
			uni.$off('learningPathUpdated', this.handleLearningPathUpdated)

			// 设置销毁标志，阻止异步回调执行
			this.isDestroyed = true

			// 停止动画循环并清理动画状态
			this.animationState.isAnimating = false
			this.nodeAnimationStates.clear()
			this.nodeInteractionScale = null

			// #ifdef H5
			// 清理滚轮事件监听
			const graphContainer = document.querySelector('.graph-container')
			if (graphContainer) {
				graphContainer.removeEventListener('wheel', this.onGraphWheel)
			}
			// #endif

			// 清理键盘高度监听
			if (this.keyboardCallback) {
				uni.offKeyboardHeightChange(this.keyboardCallback)
				this.keyboardCallback = null
			}
			// 清理画布上下文
			this.graphCtx = null
			this.minimapCtx = null

			// 清理单击延迟定时器
			if (this.tapTimer) {
				clearTimeout(this.tapTimer)
				this.tapTimer = null
			}

			// 清理 initCanvas 重试定时器
			if (this.initCanvasTimer) {
				clearTimeout(this.initCanvasTimer)
				this.initCanvasTimer = null
			}

			// 清理交互结束定时器
			if (this.interactionEndTimer) {
				clearTimeout(this.interactionEndTimer)
				this.interactionEndTimer = null
			}
		},

		watch: {
			inputText() {
				this.$nextTick(() => {
					this.adjustTextareaHeight()
				})
			}
		},

		methods: {
			onTextareaInput() {
				this.$nextTick(() => {
					this.adjustTextareaHeight()
					if (typeof requestAnimationFrame === 'function') {
						requestAnimationFrame(() => {
							this.adjustTextareaHeight()
						})
					} else {
						setTimeout(() => {
							this.adjustTextareaHeight()
						}, 0)
					}
				})
			},

			onTextareaLineChange(e) {
				const detail = e && e.detail ? e.detail : {}
				const lineCount = Number(detail.lineCount)
				if (!lineCount || Number.isNaN(lineCount)) {
					this.adjustTextareaHeight()
					return
				}

				const lineH = uni.upx2px(40)
				const padV = uni.upx2px(44)
				const maxLines = Math.max(1, Number(this.textareaMaxLines) || 4)
				const normalizedLineCount = Math.max(1, lineCount)
				this.textareaLineCount = normalizedLineCount
				const visibleLines = Math.min(maxLines, normalizedLineCount)
				this.textareaHeight = lineH * visibleLines + padV + 'px'
				this.textareaOverflow = normalizedLineCount > maxLines ? 'auto' : 'hidden'
			},

			adjustTextareaHeight() {
				const lineH = uni.upx2px(40) // 约等于 28rpx * 1.4
				const padV = uni.upx2px(44)  // 上下总 padding: 22rpx + 22rpx
				const minH = lineH + padV
				const maxLines = Math.max(1, Number(this.textareaMaxLines) || 4)
				const maxH = lineH * maxLines + padV
				const text = this.inputText || ''
				if (!text) {
					this.textareaLineCount = 1
				}
				let contentH = 0
				let measuredLines = 0

				const ref = this.$refs.textareaRef
				const el = ref && ref.$el
					? (ref.$el.querySelector('textarea') || ref.$el)
					: ref

				// H5: 通过真实 scrollHeight 计算，可覆盖“自动换行”场景
				// #ifdef H5
				if (el && typeof el.scrollHeight === 'number') {
					const prevHeight = el.style.height
					el.style.height = 'auto'
					contentH = el.scrollHeight || 0
					el.style.height = prevHeight || ''
					if (contentH > 0) {
						// 添加 2px 容差，避免因亚像素渲染导致单行被误判为两行
						const tolerance = 2
						measuredLines = Math.max(1, Math.ceil(Math.max(0, contentH - padV - tolerance) / lineH))
					}
				}
				// #endif

				// 非 H5 或无法获取 scrollHeight 时，优先用 linechange 的真实行数兜底
				if (!contentH) {
					const explicitLineCount = Math.max(1, text.split('\n').length)
					const cachedLineCount = Math.max(1, Number(this.textareaLineCount) || 1)
					const lineCount = text ? Math.max(explicitLineCount, cachedLineCount) : 1
					contentH = lineH * lineCount + padV
				} else {
					// H5 下也避免被误判回退：使用“历史行数、显式换行、测量行数”三者最大值
					const explicitLineCount = Math.max(1, text.split('\n').length)
					const cachedLineCount = Math.max(1, Number(this.textareaLineCount) || 1)
					const lineCount = text ? Math.max(explicitLineCount, cachedLineCount, measuredLines || 1) : 1
					this.textareaLineCount = lineCount
					contentH = lineH * lineCount + padV
				}

				const nextH = Math.min(maxH, Math.max(minH, contentH))
				this.textareaHeight = nextH + 'px'
				if (contentH > maxH) {
					this.textareaOverflow = 'auto'
				} else {
					this.textareaOverflow = 'hidden'
				}
			},

			// ========== 数据加载方法 ==========
			async waitForTask(taskId) {
				const maxAttempts = 150 // 最多等待 5 分钟（每 2 秒一次）
				for (let i = 0; i < maxAttempts; i++) {
					const task = await getTaskStatus(taskId)

					if (task.status === 'done') {
						return task
					} else if (task.status === 'failed') {
						throw new Error(task.error_message || '知识图谱生成失败')
					}

					// 更新加载进度提示
					this.loadingText = `正在生成知识图谱... (${i + 1}/${maxAttempts})`

					// 等待 2 秒后重试
					await new Promise(resolve => setTimeout(resolve, 2000))
				}

				throw new Error('知识图谱生成超时，请稍后重试')
			},

			async loadGraphData(retryAttempt = 0) {
				const MAX_RETRIES = 8
				const RETRY_DELAYS = [1000, 2000, 3000, 4000, 5000, 5000, 5000, 5000]

				try {
					const { nodes, edges } = await getSpaceGraph(this.spaceId)

					// 检测空图谱情况 + 重试逻辑
					if (!nodes || nodes.length === 0) {
						if (retryAttempt < MAX_RETRIES) {
							// 更新加载提示文案，显示重试次数
							this.loadingText = `正在加载知识图谱... (尝试 ${retryAttempt + 1}/${MAX_RETRIES})`

							// 等待后重试
							await new Promise(resolve => setTimeout(resolve, RETRY_DELAYS[retryAttempt]))
							return await this.loadGraphData(retryAttempt + 1)
						} else {
							// 真正失败：8次重试后仍为空
							this.graphLoadFailed = true
							this.failedMessage = '知识图谱尚未生成，请稍后重试'
							return
						}
					}

					// 从 KNOWLEDGE_TREE 边构建层级关系
					const treeEdges = edges.filter(e => e.type === 'knowledge_tree')
					const parentMap = new Map()
					const childrenMap = new Map()

					treeEdges.forEach(e => {
						parentMap.set(e.to_node_id, e.from_node_id)
						if (!childrenMap.has(e.from_node_id)) {
							childrenMap.set(e.from_node_id, [])
						}
						childrenMap.get(e.from_node_id).push(e.to_node_id)
					})

					// BFS 计算层级
					const roots = nodes.filter(n => !parentMap.has(n.id))
					const levels = new Map()
					const queue = roots.map(r => ({ id: r.id, level: 0 }))

					while (queue.length > 0) {
						const { id, level } = queue.shift()
						levels.set(id, level)
						const children = childrenMap.get(id) || []
						children.forEach(cid => queue.push({ id: cid, level: level + 1 }))
					}

					// 转换为本地节点格式
					this.nodes = nodes.map(n => ({
						id: n.id,
						label: n.label,
						level: levels.get(n.id) || 0,
						mastery: n.mastery,
						parent: parentMap.get(n.id) || null,
						collapsed: false,
						x: 0, y: 0, vx: 0, vy: 0
					}))

					// 转换为本地边格式
					this.edges = edges.map(e => ({
						from: e.from_node_id,
						to: e.to_node_id,
						type: e.type
					}))

					// 构建学习路径（从 LEARNING_PATH 类型的边）
					const pathEdges = edges.filter(e => e.type === 'learning_path')
					if (pathEdges.length > 0) {
						// 从路径边构建有序节点列表
						const pathNodeSet = new Set()
						pathEdges.forEach(e => {
							pathNodeSet.add(e.from_node_id)
							pathNodeSet.add(e.to_node_id)
						})
						this.learningPath = Array.from(pathNodeSet)
					} else {
						// 重置学习路径
						this.learningPath = []
					}

					// 预构建渲染缓存（边桶、路径集合、节点样式）
					this.rebuildRenderCaches({ refreshVisible: false, refreshChildCount: false })
				} catch (err) {
					// 网络错误重试（仅针对服务器错误或网络断开）
					if (retryAttempt < MAX_RETRIES) {
						this.loadingText = `正在重试加载... (尝试 ${retryAttempt + 1}/${MAX_RETRIES})`
						await new Promise(resolve => setTimeout(resolve, RETRY_DELAYS[retryAttempt]))
						return await this.loadGraphData(retryAttempt + 1)
					}
					// 超过重试次数,抛出原始错误
					throw err
				}
			},

			/**
			 * 静默刷新图谱数据（用于 onShow 时刷新，不显示 loading）
			 */
			async refreshGraphData() {
				// 防止并发刷新
				if (this.isRefreshing) return
				this.isRefreshing = true

				try {
					const { nodes, edges } = await getSpaceGraph(this.spaceId)

					// 数据为空则跳过
					if (!nodes || nodes.length === 0) return

					// 从 KNOWLEDGE_TREE 边构建层级关系
					const treeEdges = edges.filter(e => e.type === 'knowledge_tree')
					const parentMap = new Map()
					const childrenMap = new Map()

					treeEdges.forEach(e => {
						parentMap.set(e.to_node_id, e.from_node_id)
						if (!childrenMap.has(e.from_node_id)) {
							childrenMap.set(e.from_node_id, [])
						}
						childrenMap.get(e.from_node_id).push(e.to_node_id)
					})

					// BFS 计算层级
					const roots = nodes.filter(n => !parentMap.has(n.id))
					const levels = new Map()
					const queue = roots.map(r => ({ id: r.id, level: 0 }))

					while (queue.length > 0) {
						const { id, level } = queue.shift()
						levels.set(id, level)
						const children = childrenMap.get(id) || []
						children.forEach(cid => queue.push({ id: cid, level: level + 1 }))
					}

					// 转换为本地节点格式
					this.nodes = nodes.map(n => ({
						id: n.id,
						label: n.label,
						level: levels.get(n.id) || 0,
						mastery: n.mastery,
						parent: parentMap.get(n.id) || null,
						collapsed: false,
						x: 0, y: 0, vx: 0, vy: 0
					}))

					// 转换为本地边格式
					this.edges = edges.map(e => ({
						from: e.from_node_id,
						to: e.to_node_id,
						type: e.type
					}))

					// 构建学习路径（从 LEARNING_PATH 类型的边）
					const pathEdges = edges.filter(e => e.type === 'learning_path')
					if (pathEdges.length > 0) {
						// 从路径边构建有序节点列表
						const pathNodeSet = new Set()
						pathEdges.forEach(e => {
							pathNodeSet.add(e.from_node_id)
							pathNodeSet.add(e.to_node_id)
						})
						this.learningPath = Array.from(pathNodeSet)
					} else {
						this.learningPath = []
					}

					// 重新计算布局（处理新增/变更的节点）
					this.initializeLayout()

					// 重建渲染缓存
					this.rebuildRenderCaches()

					// 重新绘制图谱
					this.isInteracting = false
					if (this.interactionEndTimer) {
						clearTimeout(this.interactionEndTimer)
						this.interactionEndTimer = null
					}
					this.drawGraph()
					this.drawMinimap()
				} catch (err) {
					// 静默刷新失败，不显示错误，保留现有数据
					// #ifdef DEBUG
					// console.warn('静默刷新图谱失败:', err)
					// #endif
				} finally {
					this.isRefreshing = false
				}
			},

			/**
			 * 处理学习路径更新事件
			 * 由 spaceChat 页面在 generate_learning_path 工具完成时触发
			 */
			async handleLearningPathUpdated() {
				// 强制刷新，绕过 isRefreshing 标志
				this.isRefreshing = false
				try {
					await this.refreshGraphData()
				} catch (err) {
					console.error('刷新图谱数据失败:', err)
				}
			},

			async regenerateKnowledgeGraph() {
				// 验证 spaceId
				if (!this.spaceId) {
					uni.showToast({ title: '无效的学习空间', icon: 'none' })
					return
				}

				// 速率限制：最少间隔 5 秒
				const now = Date.now()
				if (now - this.lastRegenerateTime < 5000) {
					uni.showToast({ title: '请稍后再试', icon: 'none' })
					return
				}

				// 最大重试次数限制
				if (this.regenerateAttempts >= 3) {
					uni.showToast({
						title: '重试次数已达上限，请稍后再试',
						icon: 'none',
						duration: 3000
					})
					return
				}

				this.regenerateAttempts++
				this.lastRegenerateTime = now

				try {
					this.graphLoadFailed = false
					this.isLoading = true
					this.loadingText = '正在重新生成知识图谱...'

					// 使用空间名称作为 topic 重新生成
					const taskRes = await generateKnowledgeGraph(this.spaceId, {
						topic: this.spaceTitle
					})

					// 等待任务完成
					await this.waitForTask(taskRes.task_id)

					// 等待3秒，确保数据库事务commit完成
					this.loadingText = '知识图谱生成中，请稍候...'
					await new Promise(resolve => setTimeout(resolve, 3000))

					// 重新加载图谱数据（显式重置重试计数）
					await this.loadGraphData(0)

					this.isLoading = false
					// 成功后重置重试计数
					this.regenerateAttempts = 0
				} catch (err) {
					this.isLoading = false
					this.graphLoadFailed = true
					// 用户友好的错误消息
					if (err.message?.includes('timeout') || err.message?.includes('超时')) {
						this.failedMessage = '请求超时，请检查网络后重试'
					} else if (err.message?.includes('Network') || err.message?.includes('网络')) {
						this.failedMessage = '网络连接失败，请检查网络'
					} else {
						this.failedMessage = '生成失败，请重试'
					}
				}
			},

			// ========== 导航方法 ==========
			goBack() {
				// #ifdef APP-PLUS
				uni.navigateBack({
					delta: 1,
					animationType: 'slide-out-right',
					animationDuration: 300,
					fail: () => {
						// 如果返回失败（没有上一页），跳转到首页
						uni.reLaunch({ url: '/pages/index/index' })
					}
				})
				// #endif

				// #ifndef APP-PLUS
				uni.navigateBack({
					delta: 1,
					fail: () => {
						// 如果返回失败（没有上一页），跳转到首页
						uni.reLaunch({ url: '/pages/index/index' })
					}
				})
				// #endif
			},

			openSettings() {
				uni.navigateTo({
					url: `/pages/spaceSettings/spaceSettings?id=${this.spaceId}&name=${encodeURIComponent(this.spaceTitle)}`
				})
			},

			// ========== 输入栏方法 ==========
			handlePlusClick() {
				this.showPlusPopup = true
				this.$nextTick(() => {
					setTimeout(() => {
						this.plusPopupVisible = true
					}, 10)
				})
			},

			closePlusPopup() {
				this.plusPopupVisible = false
				setTimeout(() => {
					this.showPlusPopup = false
				}, 250)
			},

			async handleSelectFile() {
				this.closePlusPopup()
				const remainingSlots = 9 - this.pendingAttachments.length - this.uploadingFiles.length
				if (remainingSlots <= 0) {
					uni.showToast({ title: '最多只能添加9个附件', icon: 'none' })
					return
				}

				// #ifdef H5
				const input = document.createElement('input')
				input.type = 'file'
				input.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt'
				input.multiple = true
				input.onchange = async (e) => {
					const files = Array.from(e.target.files || []).slice(0, remainingSlots)
					for (const file of files) {
						const tempUrl = URL.createObjectURL(file)
						await this.uploadFile(tempUrl, file.name)
					}
				}
				input.click()
				// #endif

				// #ifndef H5
				try {
					const files = await chooseLocalFiles({
						count: remainingSlots,
						extension: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
					})
					for (const file of files) {
						if (!file.path) continue
						await this.uploadFile(file.path, file.name)
					}
				} catch (err) {
					if (!isPickerCancel(err)) {
						const errMsg = getPickerErrorMessage(err)
						console.error('[LearningSpace] 选择文件失败:', errMsg, err)
						uni.showToast({ title: '选择文件失败', icon: 'none' })
					}
				}
				// #endif
			},

			async handleSelectImage() {
				this.closePlusPopup()
				const remainingSlots = 9 - this.pendingAttachments.length - this.uploadingFiles.length
				if (remainingSlots <= 0) {
					uni.showToast({ title: '最多只能添加9个附件', icon: 'none' })
					return
				}

				this.showImageSourcePicker = true
			},

			handleCameraSelect() {
				this.showImageSourcePicker = false
				uni.chooseImage({
					count: 1,
					sizeType: ['original', 'compressed'],
					sourceType: ['camera'],
					success: async (res) => {
						for (const filePath of res.tempFilePaths) {
							await this.uploadFile(filePath, `image_${Date.now()}.jpg`)
						}
					},
					fail: (err) => {
						if (err.errMsg !== 'chooseImage:fail cancel') {
							uni.showToast({ title: '拍照失败', icon: 'none' })
						}
					}
				})
			},

			handleAlbumSelect() {
				this.showImageSourcePicker = false
				const remainingSlots = 9 - this.pendingAttachments.length - this.uploadingFiles.length
				uni.chooseImage({
					count: remainingSlots,
					sizeType: ['original', 'compressed'],
					sourceType: ['album'],
					success: async (res) => {
						for (const filePath of res.tempFilePaths) {
							await this.uploadFile(filePath, `image_${Date.now()}.jpg`)
						}
					},
					fail: (err) => {
						if (err.errMsg !== 'chooseImage:fail cancel') {
							uni.showToast({ title: '选择图片失败', icon: 'none' })
						}
					}
				})
			},

			handleMicClick() {
				uni.showToast({ title: '语音输入（待实现）', icon: 'none' })
			},

			async uploadFile(filePath, filename) {
				const uploadId = `upload_${Date.now()}_${Math.random()}`

				this.uploadingFiles.push({
					id: uploadId,
					name: filename,
					progress: 0,
					error: null
				})

				try {
					const attachment = await uploadAttachment(filePath, (progress) => {
						const file = this.uploadingFiles.find(f => f.id === uploadId)
						if (file) {
							file.progress = progress
						}
					})

					this.pendingAttachments.push(attachment)
					const index = this.uploadingFiles.findIndex(f => f.id === uploadId)
					if (index !== -1) {
						this.uploadingFiles.splice(index, 1)
					}
				} catch (err) {
					const file = this.uploadingFiles.find(f => f.id === uploadId)
					if (file) {
						file.error = err.message || '上传失败'
					}
					uni.showToast({ title: err.message || '上传失败', icon: 'none' })
					setTimeout(() => {
						const index = this.uploadingFiles.findIndex(f => f.id === uploadId)
						if (index !== -1) {
							this.uploadingFiles.splice(index, 1)
						}
					}, 1500)
				}
			},

			async removePendingAttachment(attachmentId) {
				try {
					const index = this.pendingAttachments.findIndex(att => att.id === attachmentId)
					if (index !== -1) {
						this.pendingAttachments.splice(index, 1)
					}
					await deleteAttachment(attachmentId)
				} catch (err) {
					uni.showToast({ title: err.message || '删除失败', icon: 'none' })
				}
			},

			formatAttachmentFileSize(bytes) {
				if (!bytes) return ''
				return formatFileSize(bytes)
			},

			sendMessage() {
				const text = this.inputText.trim()
				if (!text && this.pendingAttachments.length === 0) return
				if (this.uploadingFiles.length > 0) {
					uni.showToast({ title: '请等待附件上传完成', icon: 'none' })
					return
				}

				const attachments = [...this.pendingAttachments]
				const attachmentIds = attachments.map(att => att.id).filter(Boolean)

				let initialAttachmentKey = ''
				if (attachments.length > 0) {
					initialAttachmentKey = `ls_init_att_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
					uni.setStorageSync(initialAttachmentKey, JSON.stringify(attachments))
				}

				// 导航到学习空间对话页面，传递空间信息和初始消息
				const queryParts = [
					`id=${this.spaceId}`,
					`name=${encodeURIComponent(this.spaceTitle)}`
				]
				if (text) {
					queryParts.push(`initialMessage=${encodeURIComponent(text)}`)
				}
				if (attachmentIds.length > 0) {
					queryParts.push(`initialAttachmentIds=${encodeURIComponent(attachmentIds.join(','))}`)
				}
				if (initialAttachmentKey) {
					queryParts.push(`initialAttachmentKey=${encodeURIComponent(initialAttachmentKey)}`)
				}
				const url = `/pages/spaceChat/spaceChat?${queryParts.join('&')}`
				this.inputText = ''
				this.pendingAttachments = []

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

			onInputFocus() {
				// 输入框聚焦，等待用户输入后发送
			},

			onInputBlur() {
				// 输入框失焦
			},

			// ========== 操作按钮方法 ==========
			togglePathHighlight() {
				this.isPathHighlightOn = !this.isPathHighlightOn
				this.isInteracting = false
				if (this.interactionEndTimer) {
					clearTimeout(this.interactionEndTimer)
					this.interactionEndTimer = null
				}
				this.drawGraph()
				this.drawMinimap()
				uni.showToast({
					title: this.isPathHighlightOn ? '学习路径已开启' : '学习路径已关闭',
					icon: 'none'
				})
			},

			handleAddFile() {
				this.showAddFilePopup = true
				this.$nextTick(() => {
					setTimeout(() => {
						this.addFilePopupVisible = true
					}, 10)
				})
			},

			closeAddFilePopup() {
				this.addFilePopupVisible = false
				setTimeout(() => {
					this.showAddFilePopup = false
				}, 250)
			},

			async handleAddDocument() {
				this.closeAddFilePopup()
				const allowedExtensions = ['pdf', 'doc', 'docx', 'txt']

				// #ifdef H5
				// H5 平台使用 HTML input 选择文件
				const input = document.createElement('input')
				input.type = 'file'
				input.accept = '.pdf,.doc,.docx,.txt'
				input.onchange = async (e) => {
					const file = e.target.files[0]
					if (!file) return

					// 先检查文件扩展名
					const ext = file.name.split('.').pop()?.toLowerCase()
					if (!ext || !allowedExtensions.includes(ext)) {
						uni.showToast({ title: `仅支持 ${allowedExtensions.join(', ')} 格式`, icon: 'none' })
						return
					}

					// 检查文件大小 (10MB)
					if (file.size > 10 * 1024 * 1024) {
						uni.showToast({ title: '文件大小不能超过10MB', icon: 'none' })
						return
					}

					this.isUploading = true
					this.uploadProgress = 0

					try {
						await this.uploadFileH5(file)
						uni.showToast({ title: '文档上传成功', icon: 'success' })
					} catch (err) {
						uni.showToast({ title: err.message || '上传失败', icon: 'none' })
					} finally {
						this.isUploading = false
						this.uploadProgress = 0
					}
				}
				input.click()
				// #endif

				// #ifdef APP-PLUS || MP-WEIXIN
				// APP 和小程序使用 uni.chooseFile 或 uni.chooseMessageFile
				try {
					const files = await chooseLocalFiles({
						count: 1,
						extension: allowedExtensions
					})
					if (!files.length) return

					const file = files[0]
					const filename = String(file.name || file.path || '')
					const ext = filename.split('.').pop()?.toLowerCase()
					if (!ext || !allowedExtensions.includes(ext)) {
						uni.showToast({ title: `仅支持 ${allowedExtensions.join(', ')} 格式`, icon: 'none' })
						return
					}

					// 检查文件大小 (10MB)
					if ((file.size || 0) > 10 * 1024 * 1024) {
						uni.showToast({ title: '文件大小不能超过10MB', icon: 'none' })
						return
					}

					if (!file.path) {
						uni.showToast({ title: '未获取到文件路径', icon: 'none' })
						return
					}

					this.isUploading = true
					this.uploadProgress = 0

					try {
						await uploadSpaceDocument(this.spaceId, file.path, (progress) => {
							this.uploadProgress = progress.progress
						})
						uni.showToast({ title: '文档上传成功', icon: 'success' })
					} catch (err) {
						uni.showToast({ title: err.message || '上传失败', icon: 'none' })
					} finally {
						this.isUploading = false
						this.uploadProgress = 0
					}
				} catch (err) {
					if (!isPickerCancel(err)) {
						const errMsg = getPickerErrorMessage(err)
						console.error('[LearningSpace] 选择文件失败:', errMsg, err)
						uni.showToast({ title: `选择文件失败${errMsg ? `: ${errMsg}` : ''}`, icon: 'none' })
					}
				}
				// #endif
			},

			// #ifdef H5
			// H5 平台使用 XMLHttpRequest 上传文件，确保文件名正确传递
			async uploadFileH5(file) {
				const { getTokens } = await import('@/utils/storage')
				const config = (await import('@/config')).default
				const tokens = getTokens()

				return new Promise((resolve, reject) => {
					const formData = new FormData()
					formData.append('file', file, file.name)

					const xhr = new XMLHttpRequest()
					xhr.open('POST', `${config.API_BASE_URL}/api/spaces/${this.spaceId}/documents/upload`)

					if (tokens?.access_token) {
						xhr.setRequestHeader('Authorization', `Bearer ${tokens.access_token}`)
					}

					xhr.upload.onprogress = (e) => {
						if (e.lengthComputable) {
							this.uploadProgress = Math.round((e.loaded / e.total) * 100)
						}
					}

					xhr.onload = () => {
						if (xhr.status >= 200 && xhr.status < 300) {
							try {
								resolve(JSON.parse(xhr.responseText))
							} catch (e) {
								reject(new Error('响应解析失败'))
							}
						} else {
							try {
								const errorData = JSON.parse(xhr.responseText)
								reject(new Error(errorData.detail || '上传失败'))
							} catch (e) {
								reject(new Error(`上传失败: ${xhr.status}`))
							}
						}
					}

					xhr.onerror = () => reject(new Error('网络错误'))
					xhr.send(formData)
				})
			},
			// #endif

			handleAddLink() {
				this.closeAddFilePopup()
				// 显示链接输入对话框
				this.showLinkDialog = true
				this.$nextTick(() => {
					setTimeout(() => {
						this.linkDialogVisible = true
					}, 10)
				})
			},

			closeLinkDialog() {
				this.linkDialogVisible = false
				setTimeout(() => {
					this.showLinkDialog = false
					this.linkTitle = ''
					this.linkUrl = ''
				}, 250)
			},

			async submitLink() {
				const title = this.linkTitle.trim()
				const url = this.linkUrl.trim()

				if (!title) {
					uni.showToast({ title: '请输入链接标题', icon: 'none' })
					return
				}

				if (!url) {
					uni.showToast({ title: '请输入链接地址', icon: 'none' })
					return
				}

				// URL 格式验证
				const urlPattern = /^https?:\/\/[^\s/$.?#].[^\s]*$/i
				if (!urlPattern.test(url)) {
					uni.showToast({ title: '请输入有效的网址', icon: 'none' })
					return
				}

				this.isAddingLink = true

				try {
					await addSpaceLink(this.spaceId, { title, url })
					uni.showToast({ title: '链接添加成功', icon: 'success' })
					this.closeLinkDialog()
				} catch (err) {
					uni.showToast({ title: err.message || '添加失败', icon: 'none' })
				} finally {
					this.isAddingLink = false
				}
			},

			// ========== 画布初始化 ==========
			initCanvas(retryCount = 0) {
				// 组件已销毁，不再执行
				if (this.isDestroyed) return

				const maxRetries = 5
				const query = uni.createSelectorQuery().in(this)

				// 同时查询主画布和小地图容器尺寸
				query.select('.graph-container').boundingClientRect()
				query.select('.minimap-container').boundingClientRect()
				query.exec((results) => {
					// 组件已销毁，不再执行
					if (this.isDestroyed) return

					const graphRect = results[0]
					const minimapRect = results[1]

					if (!graphRect || !graphRect.width || !graphRect.height) {
						if (retryCount < maxRetries) {
							// 保存定时器引用以便清理
							this.initCanvasTimer = setTimeout(() => this.initCanvas(retryCount + 1), 100)
						} else {
							uni.showToast({ title: '画布初始化失败', icon: 'none' })
						}
						return
					}

					this.canvasWidth = graphRect.width
					this.canvasHeight = graphRect.height

					// 动态设置小地图尺寸（匹配容器实际大小）
					if (minimapRect && minimapRect.width && minimapRect.height) {
						this.minimapWidth = minimapRect.width
						this.minimapHeight = minimapRect.height
					}

					// 初始化同心圆布局
					this.initializeLayout()

					// 构建性能优化缓存
					this.rebuildRenderCaches()

					// 设置初始偏移，使图谱居中
					const bounds = this.getGraphBounds()
					const centerX = (bounds.minX + bounds.maxX) / 2
					const centerY = (bounds.minY + bounds.maxY) / 2
					this.offsetX = this.canvasWidth / 2 - centerX
					this.offsetY = this.canvasHeight / 2 - centerY

					this.$nextTick(() => {
						this.graphCtx = uni.createCanvasContext('graphCanvas', this)
						this.minimapCtx = uni.createCanvasContext('minimapCanvas', this)

						// 触发渲染动画（如果启用）
						this.animateGraphAppearance()
						this.drawMinimap()
					})
				})
			},

			// ========== 图谱渲染动画 ==========
			/**
			 * 主动画入口：触发知识图谱渐进式出现动画
			 */
			animateGraphAppearance() {
				// 如果用户启用了减少动画，直接渲染
				if (this.prefersReducedMotion) {
					this.drawGraph()
					return
				}

				// 如果没有节点，直接渲染
				if (!this.nodes || this.nodes.length === 0) {
					this.drawGraph()
					return
				}

				// 大图谱降级策略（100+ 节点）
				if (this.nodes.length >= 100) {
					// 使用简单的整体淡入动画（300ms）
					this.animationState.isAnimating = true
					this.animationState.startTime = Date.now()
					this.animationState.duration = 300
					this.animationState.currentProgress = 0

					const simpleFadeIn = () => {
						if (!this.animationState.isAnimating) return

						const elapsed = Date.now() - this.animationState.startTime
						const progress = Math.min(elapsed / this.animationState.duration, 1)
						this.animationState.currentProgress = progress

						// 整体淡入（仅渲染树边 + 内圆节点）
						if (this.graphCtx) {
							this.drawGraphSimpleFade(progress)
						}

						if (progress < 1) {
							requestAnimationFrame(simpleFadeIn)
						} else {
							this.animationState.isAnimating = false
							this.drawGraph()
						}
					}

					requestAnimationFrame(simpleFadeIn)
					return
				}

				// 准备节点动画状态
				this.prepareNodeAnimations()

				// 启动动画循环
				this.animationState.isAnimating = true
				this.animationState.startTime = Date.now()
				this.animationState.currentProgress = 0

				this.runGraphAnimation()
			},

			/**
			 * 准备节点动画状态（按层级分配延迟）
			 */
			prepareNodeAnimations() {
				this.nodeAnimationStates.clear()

				const { nodeAppearDelay } = this.animationState

				// 按层级分组
				const levelGroups = new Map()
				this.nodes.forEach(node => {
					const level = node.level || 0
					if (!levelGroups.has(level)) {
						levelGroups.set(level, [])
					}
					levelGroups.get(level).push(node)
				})

				// 计算每个节点的出现延迟
				let currentDelay = 0
				const sortedLevels = Array.from(levelGroups.keys()).sort((a, b) => a - b)

				sortedLevels.forEach(level => {
					const nodesInLevel = levelGroups.get(level)
					nodesInLevel.forEach(node => {
						this.nodeAnimationStates.set(node.id, {
							delay: currentDelay,
							opacity: 0,
							scale: 0.3
						})
						currentDelay += nodeAppearDelay
					})
				})
			},

			/**
			 * 动画循环（RAF）
			 */
			runGraphAnimation() {
				if (!this.animationState.isAnimating) return

				const now = Date.now()
				const elapsed = now - this.animationState.startTime
				const progress = Math.min(elapsed / this.animationState.duration, 1)
				this.animationState.currentProgress = progress

				// 更新节点动画状态
				const currentTime = elapsed
				this.nodeAnimationStates.forEach((state, nodeId) => {
					const nodeProgress = Math.max(0, Math.min((currentTime - state.delay) / 300, 1))

					// ease-out-cubic: 1 - (1-t)³
					const eased = 1 - Math.pow(1 - nodeProgress, 3)

					state.opacity = eased
					state.scale = 0.3 + (0.7 * eased)
				})

				// 绘制带动画状态的图谱
				this.drawGraphAnimated()

				// 继续动画或结束
				if (progress < 1) {
					requestAnimationFrame(() => this.runGraphAnimation())
				} else {
					this.animationState.isAnimating = false
					this.nodeAnimationStates.clear()
					this.drawGraph()
				}
				},

				isKnowledgeTreeEdge(edge) {
					return edge.type === 'knowledge_tree' || !edge.type
				},

				getNodeBaseRadius(node) {
					if (!node) return 8
					if (node.baseRadius != null) return node.baseRadius
					if (node.level === 0) return 18
					if (node.level === 1) return 14
					if (node.level === 2) return 11
					return 8
				},

				getAnimatedNodeFillColor(node) {
					return node.mastery == null ? UNMASTERED_NODE_COLOR : getMasteryColor(node.mastery)
				},

				drawAnimatedTreeEdges(ctx, visibleNodes, edgeOpacity = 1) {
					if (edgeOpacity <= 0) return

					const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
					ctx.save()
					ctx.globalAlpha = edgeOpacity

					const treeEdges = (this.edgeBuckets && this.edgeBuckets.treeEdges) || []
					treeEdges.forEach(edge => {
						if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) return

						const fromNode = this.nodeMap.get(edge.from)
						const toNode = this.nodeMap.get(edge.to)
						if (!fromNode || !toNode) return

						const startX = fromNode.x * this.scale + this.offsetX
						const startY = fromNode.y * this.scale + this.offsetY
						const endX = toNode.x * this.scale + this.offsetX
						const endY = toNode.y * this.scale + this.offsetY

						ctx.beginPath()
						ctx.moveTo(startX, startY)
						ctx.lineTo(endX, endY)
						ctx.setStrokeStyle(KNOWLEDGE_EDGE_COLOR)
						ctx.setLineWidth(KNOWLEDGE_EDGE_WIDTH)
						ctx.setLineDash([])
						ctx.stroke()
					})

					ctx.restore()
				},

				drawAnimatedInnerNode(ctx, node, opacity = 1, animScale = 1) {
					if (opacity <= 0) return

					const x = node.x * this.scale + this.offsetX
					const y = node.y * this.scale + this.offsetY
					const radius = this.getNodeBaseRadius(node) * this.scale

					ctx.save()
					ctx.globalAlpha = opacity
					ctx.translate(x, y)
					ctx.scale(animScale, animScale)
					ctx.translate(-x, -y)

					ctx.beginPath()
					ctx.arc(x, y, radius, 0, 2 * Math.PI)
					ctx.setFillStyle(this.getAnimatedNodeFillColor(node))
					ctx.fill()

					// 与静态图一致：标签在节点下方
					ctx.setFillStyle('#E2E8F0')
					ctx.setFontSize(11 * this.scale)
					ctx.setTextAlign('center')
					ctx.setTextBaseline('top')
					ctx.fillText(node.label, x, y + radius + 6 * this.scale)

					ctx.restore()
				},

				drawGraphSimpleFade(progress) {
					if (!this.graphCtx) return

					const ctx = this.graphCtx
					const visibleNodes = this.getVisibleNodes()

					ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)
					this.drawAnimatedTreeEdges(ctx, visibleNodes, progress)

					visibleNodes.forEach(node => {
						this.drawAnimatedInnerNode(ctx, node, progress, 1)
					})

					// #ifndef H5
					ctx.draw()
					// #endif
				},

				/**
				 * 带动画状态的绘制方法
				 */
				drawGraphAnimated() {
					if (!this.graphCtx) return

					const ctx = this.graphCtx
					const visibleNodes = this.getVisibleNodes()
					const { edgeAppearDelay, duration } = this.animationState
					const currentTime = Date.now() - this.animationState.startTime

					// 清空画布
					ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)

					// 阶段 1：绘制边线（延迟淡入）
					if (currentTime >= edgeAppearDelay) {
						const edgeProgress = Math.min((currentTime - edgeAppearDelay) / (duration - edgeAppearDelay), 1)
						this.drawAnimatedTreeEdges(ctx, visibleNodes, edgeProgress)
					}

					// 阶段 2：绘制节点（按动画状态）
					visibleNodes.forEach(node => {
						const animState = this.nodeAnimationStates.get(node.id)
						if (!animState || animState.opacity <= 0) return

						this.drawAnimatedInnerNode(ctx, node, animState.opacity, animState.scale)
					})

					// #ifndef H5
					ctx.draw()
					// #endif
				},

			/**
			 * 节点点击弹跳动画
			 */
			animateNodeBounce(node) {
				// 如果用户启用了减少动画，跳过
				if (this.prefersReducedMotion) return

				const startTime = Date.now()
				const duration = 200

				const animate = () => {
					const elapsed = Date.now() - startTime
					const progress = Math.min(elapsed / duration, 1)

					// 弹性缓动：0 -> 0.5 放大，0.5 -> 1 缩小
					let scale
					if (progress < 0.5) {
						scale = 1.0 + 0.3 * (progress * 2)
					} else {
						scale = 1.3 - 0.3 * ((progress - 0.5) * 2)
					}

					this.nodeInteractionScale = { nodeId: node.id, scale }
					this.requestRender()

					if (progress < 1) {
						requestAnimationFrame(animate)
					} else {
						this.nodeInteractionScale = null
						this.requestRender()
					}
				}

				animate()
			},

			// ========== 同心圆布局算法 ==========
			// 计算子树大小（包含自身）
			getSubtreeSize(nodeId) {
				const children = this.nodes.filter(n => n.parent === nodeId)
				if (children.length === 0) return 1
				return 1 + children.reduce((sum, c) => sum + this.getSubtreeSize(c.id), 0)
			},

			// 初始化布局（确定性，只调用一次）
			initializeLayout() {
				const root = this.nodes.find(n => n.level === 0)
				if (!root) return

				// 根节点在圆心
				root.x = 0
				root.y = 0

				// 从根节点开始，分配整个圆周 (0 到 2π)
				this.layoutSubtree(root, 0, Math.PI * 2)
			},

			// 递归布局子树
			layoutSubtree(parent, angleStart, angleEnd) {
				const children = this.nodes.filter(n => n.parent === parent.id)
				if (children.length === 0) return

				// 计算每个子节点的子树大小
				const subtreeSizes = children.map(c => this.getSubtreeSize(c.id))
				const totalSize = subtreeSizes.reduce((a, b) => a + b, 0)

				// 子节点到圆心的距离（同心圆半径）
				const radius = LAYOUT_CONFIG.baseRadius + parent.level * LAYOUT_CONFIG.levelSpacing

				// 分配角度
				let currentAngle = angleStart
				children.forEach((child, i) => {
					// 根据子树大小分配角度范围
					const angleRange = (subtreeSizes[i] / totalSize) * (angleEnd - angleStart)
					const childAngle = currentAngle + angleRange / 2  // 子节点在范围中心

					// 计算位置
					child.x = Math.cos(childAngle) * radius
					child.y = Math.sin(childAngle) * radius

					// 递归布局该子节点的子树
					this.layoutSubtree(child, currentAngle, currentAngle + angleRange)

					currentAngle += angleRange
				})
			},

			// ========== 性能优化方法 ==========
			// 渲染节流 - 确保每帧最多绘制一次
			requestRender() {
				if (this.renderPending) return
				this.renderPending = true
				requestAnimationFrame(() => {
					this.renderPending = false
					this.drawGraph()
				})
			},

			// 小地图渲染节流（交互期降频）
			requestMinimapRender(force = false) {
				const now = Date.now()
				if (!force && this.isInteracting && (now - this.lastMinimapRenderAt < this.minimapIntervalMs)) {
					return
				}
				if (this.minimapPending) return
				this.minimapPending = true
				requestAnimationFrame(() => {
					this.minimapPending = false
					const frameNow = Date.now()
					if (!force && this.isInteracting && (frameNow - this.lastMinimapRenderAt < this.minimapIntervalMs)) {
						return
					}
					this.drawMinimap()
				})
			},

			markInteractionStart() {
				if (this.interactionEndTimer) {
					clearTimeout(this.interactionEndTimer)
					this.interactionEndTimer = null
				}
				if (!this.isInteracting) {
					this.isInteracting = true
					this.requestRender()
				}
			},

			scheduleInteractionEnd() {
				if (this.interactionEndTimer) {
					clearTimeout(this.interactionEndTimer)
				}
				this.interactionEndTimer = setTimeout(() => {
					this.interactionEndTimer = null
					if (!this.isInteracting) return
					this.isInteracting = false
					this.requestRender()
					this.requestMinimapRender(true)
				}, this.interactionEndDelayMs)
			},

			rebuildRenderCaches(options = {}) {
				const {
					refreshVisible = true,
					refreshChildCount = true
				} = options

				this.buildNodeIndex()
				this.buildEdgeBuckets()
				this.buildLearningPathSet()
				this.buildNodeStyleCache()
				if (refreshChildCount) {
					this.buildChildCountCache()
				}
				if (refreshVisible) {
					this.updateVisibleNodesCache()
				}
			},

			// 构建节点索引 Map
			buildNodeIndex() {
				this.nodeMap = new Map()
				this.nodes.forEach(n => this.nodeMap.set(n.id, n))
			},

			buildEdgeBuckets() {
				const buckets = {
					treeEdges: [],
					advancedEdges: [],
					pathEdges: [],
					nonPathEdges: []
				}
				this.edges.forEach(edge => {
					if (this.isKnowledgeTreeEdge(edge)) {
						buckets.treeEdges.push(edge)
					}
					if (edge.type === 'advanced') {
						buckets.advancedEdges.push(edge)
					}
					if (edge.type === 'learning_path') {
						buckets.pathEdges.push(edge)
					} else {
						buckets.nonPathEdges.push(edge)
					}
				})
				this.edgeBuckets = buckets
			},

			buildLearningPathSet() {
				this.learningPathSet = new Set(this.learningPath)
			},

			buildNodeStyleCache() {
				this.nodes.forEach(node => this.updateNodeStyleCache(node))
			},

			updateNodeStyleCache(node) {
				if (!node) return
				node.baseRadius = this.getNodeBaseRadius(node)
				if (node.mastery == null) {
					node.fillColor = UNMASTERED_NODE_COLOR
					node.glowColor = UNMASTERED_NODE_GLOW
					node.outlineColor = UNMASTERED_NODE_OUTLINE
					return
				}
				node.fillColor = getMasteryColor(node.mastery)
				node.glowColor = getMasteryGlowColor(node.mastery, 0.5)
				node.outlineColor = getMasteryGlowColor(node.mastery, 0.2)
			},

			// 构建子节点数量缓存
			buildChildCountCache() {
				this.childCountCache = new Map()
				this.nodes.forEach(n => {
					this.childCountCache.set(n.id, this.computeChildCount(n.id))
				})
			},

			// 计算子节点数量（内部方法）
			computeChildCount(nodeId) {
				let count = 0
				const countChildren = (parentId) => {
					this.nodes.forEach(n => {
						if (n.parent === parentId) {
							count++
							countChildren(n.id)
						}
					})
				}
				countChildren(nodeId)
				return count
			},

			// 更新可见节点缓存
			updateVisibleNodesCache() {
				this.visibleNodesCache = this.nodes.filter(node => {
					let parent = this.findParentNode(node)
					while (parent) {
						if (parent.collapsed) return false
						parent = this.findParentNode(parent)
					}
					return true
				})
			},

			// ========== 绘制知识图谱 ==========
			drawGraph() {
				if (!this.graphCtx) return

				const ctx = this.graphCtx
				const visibleNodes = this.getVisibleNodes()
				const interactionMode = this.isInteracting

				// 清空画布
				ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)

				// 设置变换
				ctx.save()
				ctx.translate(this.offsetX, this.offsetY)
				ctx.scale(this.scale, this.scale)

				// 绘制边（先绘制，这样节点会覆盖在上面）
				this.drawEdges(ctx, visibleNodes, { interactionMode })

				// 绘制节点
				visibleNodes.forEach(node => {
					// 检查是否有交互缩放动画
					if (this.nodeInteractionScale && this.nodeInteractionScale.nodeId === node.id) {
						ctx.save()
						ctx.translate(node.x, node.y)
						ctx.scale(this.nodeInteractionScale.scale, this.nodeInteractionScale.scale)
						ctx.translate(-node.x, -node.y)
						this.drawNode(ctx, node, { interactionMode })
						ctx.restore()
					} else {
						this.drawNode(ctx, node, { interactionMode })
					}
				})

				ctx.restore()
				ctx.draw()
			},

			drawEdges(ctx, visibleNodes, options = {}) {
				const interactionMode = Boolean(options.interactionMode)
				const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
				const buckets = this.edgeBuckets || {
					treeEdges: [],
					advancedEdges: [],
					pathEdges: []
				}

				// 路径高亮时，非路径边变暗
				if (this.isPathHighlightOn) {
					ctx.setGlobalAlpha(0.15)
				}

				// 1. 绘制知识树边（灰色实线 - 树形骨架）
				buckets.treeEdges.forEach(edge => {
					if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) return

					const fromNode = this.nodeMap.get(edge.from)
					const toNode = this.nodeMap.get(edge.to)

					if (!fromNode || !toNode) return

					ctx.beginPath()
					ctx.moveTo(fromNode.x, fromNode.y)
					ctx.lineTo(toNode.x, toNode.y)
					ctx.setStrokeStyle(KNOWLEDGE_EDGE_COLOR)
					ctx.setLineWidth(KNOWLEDGE_EDGE_WIDTH)
					ctx.setLineDash([])
					ctx.stroke()
				})

				// 2. 绘制进阶边（紫色虚线 - 跨分支关联）
				if (!interactionMode && this.showAdvancedEdges) {
					buckets.advancedEdges.forEach(edge => {
						if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) return

						const fromNode = this.nodeMap.get(edge.from)
						const toNode = this.nodeMap.get(edge.to)

						if (!fromNode || !toNode) return

						ctx.beginPath()
						ctx.moveTo(fromNode.x, fromNode.y)
						ctx.lineTo(toNode.x, toNode.y)
						ctx.setStrokeStyle('rgba(139, 92, 246, 0.5)')
						ctx.setLineWidth(1.5)
						ctx.setLineDash([5, 5])
						ctx.stroke()
						ctx.setLineDash([])
					})
				}

				// 恢复透明度后再绘制路径边
				if (this.isPathHighlightOn) {
					ctx.setGlobalAlpha(1.0)
				}

				// 3. 绘制学习路径边（蓝色实线 + 中间箭头）
				if (!interactionMode && this.isPathHighlightOn) {
					buckets.pathEdges.forEach(edge => {
						if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) return

						const fromNode = this.nodeMap.get(edge.from)
						const toNode = this.nodeMap.get(edge.to)

						if (!fromNode || !toNode) return

						this.drawPathEdge(ctx, fromNode.x, fromNode.y, toNode.x, toNode.y)
					})
				}
			},

			// 绘制学习路径边（蓝色实线 + 中间箭头）
			drawPathEdge(ctx, x1, y1, x2, y2) {
				const color = '#0088FF'
				const lineWidth = 3

				// 绘制实线
				ctx.beginPath()
				ctx.setStrokeStyle(color)
				ctx.setLineWidth(lineWidth)
				ctx.moveTo(x1, y1)
				ctx.lineTo(x2, y2)
				ctx.stroke()

				// 在中点绘制箭头
				const midX = (x1 + x2) / 2
				const midY = (y1 + y2) / 2
				const angle = Math.atan2(y2 - y1, x2 - x1)
				const arrowSize = 8

				// 绘制三角形箭头
				ctx.beginPath()
				ctx.setFillStyle(color)
				// 箭头尖端（指向目标方向）
				ctx.moveTo(
					midX + arrowSize * Math.cos(angle),
					midY + arrowSize * Math.sin(angle)
				)
				// 箭头左翼
				ctx.lineTo(
					midX + arrowSize * Math.cos(angle + 2.5),
					midY + arrowSize * Math.sin(angle + 2.5)
				)
				// 箭头右翼
				ctx.lineTo(
					midX + arrowSize * Math.cos(angle - 2.5),
					midY + arrowSize * Math.sin(angle - 2.5)
				)
				ctx.closePath()
				ctx.fill()
			},

			drawNode(ctx, node, options = {}) {
				const interactionMode = Boolean(options.interactionMode)
				const radius = this.getNodeBaseRadius(node)
				const isSelected = this.selectedNodeId === node.id
				const isOnPath = this.isPathHighlightOn && this.learningPathSet.has(node.id)

				// 路径高亮时，非路径节点变暗（选中节点始终清晰）
				const isDimmed = this.isPathHighlightOn && !isOnPath && !isSelected
				if (isDimmed) {
					ctx.setGlobalAlpha(0.25)
				}

				const fillColor = node.fillColor || (node.mastery == null ? UNMASTERED_NODE_COLOR : getMasteryColor(node.mastery))

				if (interactionMode) {
					// 交互期走轻量渲染：仅主圆，不绘制阴影和外轮廓
					ctx.setShadow(0, 0, 0, 'transparent')
					ctx.beginPath()
					ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
					ctx.setFillStyle(fillColor)
					ctx.fill()
				} else {
					const glowColor = node.glowColor || (node.mastery == null ? UNMASTERED_NODE_GLOW : getMasteryGlowColor(node.mastery, 0.5))
					const outlineColor = node.outlineColor || (node.mastery == null ? UNMASTERED_NODE_OUTLINE : getMasteryGlowColor(node.mastery, 0.2))

					// 绘制发光效果 (阴影)
					ctx.setShadow(0, 0, 18, glowColor)

					// 绘制半透明轮廓
					ctx.beginPath()
					ctx.arc(node.x, node.y, radius + 4, 0, Math.PI * 2)
					ctx.setFillStyle(outlineColor)
					ctx.fill()

					// 绘制主圆圈
					ctx.beginPath()
					ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
					ctx.setFillStyle(fillColor)
					ctx.fill()

					// 关闭阴影
					ctx.setShadow(0, 0, 0, 'transparent')
				}

				// 选中节点：白色描边轮廓（加粗）
				if (isSelected) {
					ctx.beginPath()
					ctx.arc(node.x, node.y, radius + 6, 0, Math.PI * 2)
					ctx.setStrokeStyle('#FFFFFF')
					ctx.setLineWidth(3)
					ctx.stroke()
				}

				// 路径节点：蓝色描边（非选中时）
				if (isOnPath && !isSelected) {
					ctx.beginPath()
					ctx.arc(node.x, node.y, radius + 5, 0, Math.PI * 2)
					ctx.setStrokeStyle('#0088FF')
					ctx.setLineWidth(2)
					ctx.stroke()
				}

				// 交互期仅保留选中节点文字，静止期显示全部
				if (!interactionMode || isSelected) {
					ctx.setFillStyle('#E2E8F0')
					ctx.setFontSize(11)
					ctx.setTextAlign('center')
					ctx.setTextBaseline('top')
					ctx.fillText(node.label, node.x, node.y + radius + 6)
				}

				// 如果折叠了，显示子节点数量角标
				if (node.collapsed) {
					const childCount = this.getChildCount(node.id)
					if (childCount > 0) {
						this.drawBadge(ctx, node.x + radius - 2, node.y - radius + 2, childCount)
					}
				}

				// 恢复透明度
				if (isDimmed) {
					ctx.setGlobalAlpha(1.0)
				}
			},

			drawBadge(ctx, x, y, count) {
				const badgeRadius = 8
				const badgeColor = '#818CF8'

				// 关闭阴影绘制角标
				ctx.setShadow(0, 0, 0, 'transparent')

				// 绘制角标背景
				ctx.beginPath()
				ctx.arc(x, y, badgeRadius, 0, Math.PI * 2)
				ctx.setFillStyle(badgeColor)
				ctx.fill()

				// 绘制数字
				ctx.setFillStyle('#FFFFFF')
				ctx.setFontSize(9)
				ctx.setTextAlign('center')
				ctx.setTextBaseline('middle')
				ctx.fillText(count.toString(), x, y)
			},

			// ========== 绘制小地图 ==========
			drawMinimap() {
				if (!this.minimapCtx) return

				const ctx = this.minimapCtx
				const allNodes = this.nodes
				const buckets = this.edgeBuckets || {
					nonPathEdges: [],
					pathEdges: []
				}

				// 清空小地图（不绘制背景，容器已有背景）
				ctx.clearRect(0, 0, this.minimapWidth, this.minimapHeight)

				// 计算图谱边界
				const bounds = this.getGraphBounds()
				const graphWidth = bounds.maxX - bounds.minX
				const graphHeight = bounds.maxY - bounds.minY

				// 使用 10% padding（动态，而非固定 100px）
				const padding = Math.max(graphWidth, graphHeight) * 0.1
				const totalWidth = graphWidth + padding * 2
				const totalHeight = graphHeight + padding * 2

				// 计算小地图缩放比例（移除 0.85 系数，充分利用空间）
				const scaleX = this.minimapWidth / totalWidth
				const scaleY = this.minimapHeight / totalHeight
				const minimapScale = Math.min(scaleX, scaleY)

				// 小地图中心偏移
				const centerX = this.minimapWidth / 2
				const centerY = this.minimapHeight / 2
				const graphCenterX = (bounds.minX + bounds.maxX) / 2
				const graphCenterY = (bounds.minY + bounds.maxY) / 2

				// 路径高亮时，非路径边变暗
				if (this.isPathHighlightOn) {
					ctx.setGlobalAlpha(0.15)
				}

				// 绘制边（使用 nodeMap 优化 O(1) 查找）- 只绘制非路径边
				buckets.nonPathEdges.forEach(edge => {
					const fromNode = this.nodeMap.get(edge.from)
					const toNode = this.nodeMap.get(edge.to)
					if (!fromNode || !toNode) return

					const x1 = centerX + (fromNode.x - graphCenterX) * minimapScale
					const y1 = centerY + (fromNode.y - graphCenterY) * minimapScale
					const x2 = centerX + (toNode.x - graphCenterX) * minimapScale
					const y2 = centerY + (toNode.y - graphCenterY) * minimapScale

					ctx.beginPath()
					ctx.moveTo(x1, y1)
					ctx.lineTo(x2, y2)
					ctx.setStrokeStyle('rgba(255, 255, 255, 0.2)')
					ctx.setLineWidth(0.5)
					ctx.stroke()
				})

				// 恢复透明度绘制路径边
				if (this.isPathHighlightOn) {
					ctx.setGlobalAlpha(1.0)

					// 绘制学习路径边（蓝色）
					buckets.pathEdges.forEach(edge => {
						const fromNode = this.nodeMap.get(edge.from)
						const toNode = this.nodeMap.get(edge.to)
						if (!fromNode || !toNode) return

						const x1 = centerX + (fromNode.x - graphCenterX) * minimapScale
						const y1 = centerY + (fromNode.y - graphCenterY) * minimapScale
						const x2 = centerX + (toNode.x - graphCenterX) * minimapScale
						const y2 = centerY + (toNode.y - graphCenterY) * minimapScale

						ctx.beginPath()
						ctx.moveTo(x1, y1)
						ctx.lineTo(x2, y2)
						ctx.setStrokeStyle('#0088FF')
						ctx.setLineWidth(1)
						ctx.stroke()
					})
				}

				// 绘制节点（小圆点）
				allNodes.forEach(node => {
					const x = centerX + (node.x - graphCenterX) * minimapScale
					const y = centerY + (node.y - graphCenterY) * minimapScale
					const isOnPath = this.isPathHighlightOn && this.learningPathSet.has(node.id)
					const isDimmed = this.isPathHighlightOn && !isOnPath

					// 路径高亮时，非路径节点变暗
					if (isDimmed) {
						ctx.setGlobalAlpha(0.25)
					}

					// 小地图使用统一灰色：根节点稍亮，其他节点较暗
					// 路径上的节点使用蓝色
					const dotColor = isOnPath ? '#0088FF' : (node.level === 0 ? '#9CA3AF' : '#6B7280')
					const dotRadius = node.level === 0 ? 3 : (node.level === 1 ? 2.5 : 2)

					ctx.beginPath()
					ctx.arc(x, y, dotRadius, 0, Math.PI * 2)
					ctx.setFillStyle(dotColor)
					ctx.fill()

					// 恢复透明度
					if (isDimmed) {
						ctx.setGlobalAlpha(1.0)
					}
				})

				// 绘制视口指示器
				const viewportWidth = (this.canvasWidth / this.scale) * minimapScale
				const viewportHeight = (this.canvasHeight / this.scale) * minimapScale
				const viewportCenterX = centerX - ((this.offsetX - this.canvasWidth / 2) / this.scale + graphCenterX) * minimapScale
				const viewportCenterY = centerY - ((this.offsetY - this.canvasHeight / 2) / this.scale + graphCenterY) * minimapScale

				// 绘制圆角矩形视口
				const vx = viewportCenterX - viewportWidth / 2
				const vy = viewportCenterY - viewportHeight / 2
				const vr = 4 // 圆角半径

				ctx.beginPath()
				ctx.moveTo(vx + vr, vy)
				ctx.lineTo(vx + viewportWidth - vr, vy)
				ctx.arcTo(vx + viewportWidth, vy, vx + viewportWidth, vy + vr, vr)
				ctx.lineTo(vx + viewportWidth, vy + viewportHeight - vr)
				ctx.arcTo(vx + viewportWidth, vy + viewportHeight, vx + viewportWidth - vr, vy + viewportHeight, vr)
				ctx.lineTo(vx + vr, vy + viewportHeight)
				ctx.arcTo(vx, vy + viewportHeight, vx, vy + viewportHeight - vr, vr)
				ctx.lineTo(vx, vy + vr)
				ctx.arcTo(vx, vy, vx + vr, vy, vr)
				ctx.closePath()

				ctx.setStrokeStyle('#FFFFFF')
				ctx.setLineWidth(1.5)
				ctx.stroke()

				this.lastMinimapRenderAt = Date.now()
				ctx.draw()
			},

			getGraphBounds() {
				if (this.nodes.length === 0) {
					return { minX: 0, maxX: 100, minY: 0, maxY: 100 }
				}

				let minX = Infinity, maxX = -Infinity
				let minY = Infinity, maxY = -Infinity

				this.nodes.forEach(node => {
					minX = Math.min(minX, node.x)
					maxX = Math.max(maxX, node.x)
					minY = Math.min(minY, node.y)
					maxY = Math.max(maxY, node.y)
				})

				if (maxX - minX < 1) { maxX = minX + 100 }
				if (maxY - minY < 1) { maxY = minY + 100 }

				return { minX, maxX, minY, maxY }
			},

			// ========== 可见节点计算 ==========
			getVisibleNodes() {
				// 使用缓存（拖动时不重复计算）
				if (this.visibleNodesCache) {
					return this.visibleNodesCache
				}
				// 缓存未初始化时计算
				this.updateVisibleNodesCache()
				return this.visibleNodesCache
			},

			findParentNode(node) {
				if (!node.parent) return null
				return this.nodeMap.get(node.parent)
			},

			getChildCount(nodeId) {
				// 使用缓存
				return this.childCountCache.get(nodeId) || 0
			},

			// ========== 主画布触摸事件 ==========
			onGraphTouchStart(e) {
				this.markInteractionStart()

				// 清除待处理的点击定时器，防止状态混乱
				if (this.tapTimer) {
					clearTimeout(this.tapTimer)
					this.tapTimer = null
				}

				if (e.touches.length === 1) {
					this.isTouching = true
					this.isPinching = false
					this.dragDistance = 0  // 重置拖拽距离
					this.lastTouchX = e.touches[0].clientX
					this.lastTouchY = e.touches[0].clientY
				} else if (e.touches.length === 2) {
					this.isPinching = true
					this.lastPinchDistance = this.getPinchDistance(e.touches)
				}
			},

			onGraphTouchMove(e) {
				if (this.isPinching && e.touches.length === 2) {
					this.markInteractionStart()
					const distance = this.getPinchDistance(e.touches)
					// 避免除零
					if (this.lastPinchDistance > 0) {
						const delta = distance / this.lastPinchDistance
						this.scale = Math.max(0.3, Math.min(3, this.scale * delta))
					}
					this.lastPinchDistance = distance

					this.requestRender()
					this.requestMinimapRender()
				} else if (this.isTouching && e.touches.length === 1) {
					this.markInteractionStart()
					const deltaX = e.touches[0].clientX - this.lastTouchX
					const deltaY = e.touches[0].clientY - this.lastTouchY

					// 累计拖拽距离，用于区分点击和拖拽
					this.dragDistance += Math.abs(deltaX) + Math.abs(deltaY)

					this.offsetX += deltaX
					this.offsetY += deltaY

					this.lastTouchX = e.touches[0].clientX
					this.lastTouchY = e.touches[0].clientY

					this.requestRender()
					this.requestMinimapRender()
				}
			},

			onGraphTouchEnd(e) {
				const touch = e.changedTouches?.[0]
				if (!touch) {
					this.isTouching = false
					this.isPinching = false
					this.scheduleInteractionEnd()
					return
				}

				const now = Date.now()
				const x = touch.clientX
				const y = touch.clientY

				// 双击检测：300ms 内在相近位置
				const isDoubleTap = now - this.lastTapTime < 300 &&
					Math.abs(x - this.lastTapX) < 30 &&
					Math.abs(y - this.lastTapY) < 30

				// 拖拽距离阈值：超过此值视为拖拽而非点击
				const TAP_THRESHOLD = 10

				if (isDoubleTap) {
					// 取消待处理的单击，只执行双击操作
					if (this.tapTimer) {
						clearTimeout(this.tapTimer)
						this.tapTimer = null
					}
					this.handleDoubleTap(x, y)
				} else if (!this.isPinching && this.isTouching && this.dragDistance < TAP_THRESHOLD) {
					// 延迟单击，等待可能的双击（只有拖拽距离小于阈值才视为点击）
					this.pendingTapX = x
					this.pendingTapY = y

					if (this.tapTimer) {
						clearTimeout(this.tapTimer)
					}
					this.tapTimer = setTimeout(() => {
						this.handleTap(this.pendingTapX, this.pendingTapY)
						this.tapTimer = null
					}, 150)
				}

				// 更新上次点击记录
				this.lastTapTime = now
				this.lastTapX = x
				this.lastTapY = y

				this.isTouching = false
				this.isPinching = false
				this.scheduleInteractionEnd()
			},

			getPinchDistance(touches) {
				const dx = touches[0].clientX - touches[1].clientX
				const dy = touches[0].clientY - touches[1].clientY
				return Math.sqrt(dx * dx + dy * dy)
			},

			// ========== H5 滚轮缩放 ==========
			onGraphWheel(e) {
				e.preventDefault()
				this.markInteractionStart()

				// 缩放灵敏度
				const zoomSensitivity = 0.001
				const delta = -e.deltaY * zoomSensitivity

				// 计算新缩放比例
				const newScale = Math.max(0.3, Math.min(3, this.scale * (1 + delta)))

				// 以鼠标位置为中心进行缩放
				const rect = e.currentTarget.getBoundingClientRect()
				const mouseX = e.clientX - rect.left
				const mouseY = e.clientY - rect.top

				// 计算缩放前后的偏移调整（使鼠标位置保持不变）
				const scaleRatio = newScale / this.scale
				this.offsetX = mouseX - (mouseX - this.offsetX) * scaleRatio
				this.offsetY = mouseY - (mouseY - this.offsetY) * scaleRatio

				this.scale = newScale

				this.requestRender()
				this.requestMinimapRender()
				this.scheduleInteractionEnd()
			},

			handleTap(screenX, screenY) {
				const node = this.findNodeAtPosition(screenX, screenY)
				if (node) {
					// 点击已选中的节点，收回详情卡片（toggle）
					if (this.selectedNodeId === node.id) {
						this.selectedNodeId = null
					} else {
						this.selectedNodeId = node.id
						// 触发节点弹跳动画
						this.animateNodeBounce(node)
					}
					this.requestRender()
				} else {
					// 点击空白区域，关闭弹窗
					this.selectedNodeId = null
					this.requestRender()
				}
			},

			// 打开节点操作菜单
			openNodeOptions() {
				const node = this.selectedNode
				if (!node) return

				uni.showActionSheet({
					itemList: ['查看详情', '标记为已掌握', '添加笔记', '删除节点'],
					success: (res) => {
						switch (res.tapIndex) {
							case 0:
								// 查看详情
								console.log('查看详情:', node.label)
								break
							case 1:
								// 标记为已掌握
								this.updateNodeMastery(node.id, 100)
								break
							case 2:
								// 添加笔记
								console.log('添加笔记:', node.label)
								break
							case 3:
								// 删除节点
								console.log('删除节点:', node.label)
								break
						}
					}
				})
			},

			// 更新节点掌握度
			updateNodeMastery(nodeId, mastery) {
				const nodeIndex = this.nodes.findIndex(n => n.id === nodeId)
				if (nodeIndex !== -1) {
					this.nodes[nodeIndex].mastery = mastery
					this.updateNodeStyleCache(this.nodes[nodeIndex])
					this.requestRender()
					uni.showToast({
						title: '已标记为已掌握',
						icon: 'success'
					})
				}
			},

			handleDoubleTap(screenX, screenY) {
				const node = this.findNodeAtPosition(screenX, screenY)
				if (node) {
					const childCount = this.getChildCount(node.id)
					if (childCount > 0) {
						const nodeIndex = this.nodes.findIndex(n => n.id === node.id)
						if (nodeIndex !== -1) {
							const newCollapsed = !this.nodes[nodeIndex].collapsed
							this.nodes[nodeIndex].collapsed = newCollapsed

							// 不需要重新计算位置！位置在初始化时已确定
							// 只改变 collapsed 状态，控制可见性

							// 折叠/展开后更新可见节点缓存
							this.updateVisibleNodesCache()

							this.isInteracting = false
							if (this.interactionEndTimer) {
								clearTimeout(this.interactionEndTimer)
								this.interactionEndTimer = null
							}
							this.drawGraph()
							this.drawMinimap()
						}
					}
				}
			},

			findNodeAtPosition(screenX, screenY) {
				const graphX = (screenX - this.offsetX) / this.scale
				const graphY = (screenY - this.offsetY) / this.scale

				const visibleNodes = this.getVisibleNodes()
				for (const node of visibleNodes) {
					const radius = this.getNodeBaseRadius(node)
					// 增大点击区域
					const hitRadius = radius + 15

					const dx = graphX - node.x
					const dy = graphY - node.y
					if (dx * dx + dy * dy <= hitRadius * hitRadius) {
						return node
					}
				}
				return null
			},

			// ========== 小地图触摸事件 ==========
			onMinimapTouchStart(e) {
				this.markInteractionStart()
				this.navigateFromMinimap(e.touches[0])
			},

			onMinimapTouchMove(e) {
				this.markInteractionStart()
				this.navigateFromMinimap(e.touches[0])
			},

			navigateFromMinimap(touch) {
				const bounds = this.getGraphBounds()
				const graphWidth = bounds.maxX - bounds.minX + 100
				const graphHeight = bounds.maxY - bounds.minY + 100

				const scaleX = this.minimapWidth / graphWidth
				const scaleY = this.minimapHeight / graphHeight
				const minimapScale = Math.min(scaleX, scaleY) * 0.85

				const graphCenterX = (bounds.minX + bounds.maxX) / 2
				const graphCenterY = (bounds.minY + bounds.maxY) / 2

				const targetX = graphCenterX + (touch.x - this.minimapWidth / 2) / minimapScale
				const targetY = graphCenterY + (touch.y - this.minimapHeight / 2) / minimapScale

				this.offsetX = this.canvasWidth / 2 - targetX * this.scale
				this.offsetY = this.canvasHeight / 2 - targetY * this.scale

				this.requestRender()
				this.requestMinimapRender()
				this.scheduleInteractionEnd()
			}
		}
	}
</script>

<style>
	@import '/static/styles/dev-grid.css';

	view, text {
		box-sizing: border-box;
	}

	/* 页面容器 */
	.learning-space-page {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: rgb(10, 10, 10);
		overflow: hidden;
	}

	/* 顶部导航栏 - 磨砂玻璃效果 */
	.space-nav-bar {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 100;
		padding-top: calc(100vh * 1.5 / 26);
		padding-bottom: calc(100vh * 0.5 / 26);
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: calc(100vw / 24);
		padding-right: calc(100vw / 24);
	}

	/* 磨砂玻璃背景层 - 使用伪元素实现渐变过渡 */
	.space-nav-bar::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: -70rpx;
		z-index: -1;
		background: linear-gradient(
			to bottom,
			rgba(10, 10, 10, 0.6) 0%,
			rgba(10, 10, 10, 0.45) 50%,
			rgba(10, 10, 10, 0) 100%
		);
		-webkit-backdrop-filter: blur(24px) saturate(150%);
		backdrop-filter: blur(24px) saturate(150%);
		-webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
		mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
	}

	/* 不支持 backdrop-filter 的降级方案 */
	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.space-nav-bar::before {
			background: linear-gradient(
				to bottom,
				rgba(10, 10, 10, 0.95) 0%,
				rgba(10, 10, 10, 0.8) 50%,
				rgba(10, 10, 10, 0) 100%
			);
		}
	}

	.nav-left {
		width: 72rpx;
		height: 72rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 50%;
		background-color: rgba(255, 255, 255, 0.06);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		outline: 1rpx solid rgba(255, 255, 255, 0.04);
		outline-offset: 1rpx;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
			0 2rpx 12rpx rgba(0, 0, 0, 0.25);
		transition: all 0.2s ease;
		color: #ffffff;
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.nav-left {
			background: rgba(80, 80, 95, 0.65);
		}
	}

	.nav-right {
		width: 80rpx;
		height: 80rpx;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.nav-icon {
		width: 48rpx;
		height: 48rpx;
		filter: brightness(0) invert(1);
	}

	.nav-title {
		font-size: 34rpx;
		font-weight: 600;
		color: #ffffff;
	}

	/* 小地图容器 */
	.minimap-container {
		position: fixed;
		top: calc(100vh * 3.5 / 26);
		left: calc(100vw / 24);
		z-index: 90;
		width: 240rpx;
		height: 200rpx;
		background-color: rgba(255, 255, 255, 0.04);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 16rpx;
		overflow: hidden;
	}

	.minimap-canvas {
		width: 100%;
		height: 100%;
	}

	/* 知识图谱容器 */
	.graph-container {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1;
	}

	.graph-canvas {
		width: 100%;
		height: 100%;
	}

	/* 操作按钮 */
	.action-buttons {
		position: fixed;
		bottom: calc(100vh * 3 / 26);
		left: 0;
		right: 0;
		z-index: 100;
		display: flex;
		justify-content: space-between;
		padding: 0 calc(100vw / 24);
	}

	.action-btn {
		width: 108rpx;
		height: 108rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 50%;
		background-color: rgba(255, 255, 255, 0.06);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		outline: 1rpx solid rgba(255, 255, 255, 0.04);
		outline-offset: 1rpx;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
			0 2rpx 12rpx rgba(0, 0, 0, 0.25);
		transition: all 0.2s ease;
	}

	.action-btn-active {
		background-color: rgba(0, 136, 255, 0.75);
		border: 1rpx solid rgba(255, 255, 255, 0.2);
		outline: 1rpx solid rgba(0, 136, 255, 0.3);
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.15),
			0 0 20rpx rgba(0, 136, 255, 0.4),
			0 2rpx 12rpx rgba(0, 0, 0, 0.25);
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.action-btn {
			background: rgba(80, 80, 95, 0.65);
		}
	}

	.action-btn-icon {
		width: 66rpx;
		height: 66rpx;
		filter: brightness(0) invert(1);
	}

	/* 底部输入栏 - 透明悬浮 */
	.input-bar {
		position: fixed;
		left: calc(100vw / 24);
		right: calc(100vw / 24);
		bottom: calc(100vh * 0.5 / 26);
		z-index: 100;
		padding: 16rpx 0;
		box-sizing: border-box;
		transition: bottom 0.25s ease;
	}

	.input-bar-inner {
		display: flex;
		flex-direction: column;
		width: 100%;
		align-items: stretch;
		gap: 12rpx;
	}

	.input-action {
		width: 86rpx;
		height: 86rpx;
		flex-shrink: 0;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.input-action-icon {
		width: 52rpx;
		height: 52rpx;
		filter: brightness(0) invert(1);
	}

	.send-btn-wrapper .send-action-icon {
		width: 80rpx !important;
		height: 80rpx !important;
		transform: scale(1.0);
		transform-origin: center center;
		display: block;
	}

	.send-btn-disabled {
		opacity: 0.3;
	}

	.input-field-wrapper {
		flex: none;
		width: 100%;
		max-width: 100%;
		min-width: 0;
		min-height: 86rpx;
		background-color: rgba(255, 255, 255, 0.06);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border-radius: 999rpx;
		display: flex;
		align-items: center;
		overflow: hidden;
		padding: 0 8rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		outline: 1rpx solid rgba(255, 255, 255, 0.04);
		outline-offset: 1rpx;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
			0 2rpx 12rpx rgba(0, 0, 0, 0.25);
	}

	.input-field-wrapper-expanded {
		align-items: flex-end;
		border-radius: 36rpx;
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.input-field-wrapper {
			background-color: rgba(80, 80, 95, 0.65);
		}
	}

	.input-field {
		flex: 1 1 0;
		width: 0;
		min-width: 0;
		max-width: 100%;
		font-size: 28rpx;
		color: #ffffff;
		min-height: 40rpx;
		line-height: 1.4;
		padding: 22rpx 0;
		box-sizing: border-box;
		resize: none;
		overflow-y: hidden;
	}

	.input-placeholder {
		color: #9ca3af;
		font-size: 28rpx;
	}

	.input-safe-area {
		height: env(safe-area-inset-bottom);
	}

	/* ========== 待发送附件预览 ========== */
	.pending-attachments-area {
		display: flex;
		flex-wrap: wrap;
		gap: 12rpx;
		padding: 8rpx 0;
		background-color: transparent;
		max-height: 360rpx;
		overflow-y: auto;
		width: 100%;
	}

	.attachment-preview-item {
		position: relative;
	}

	.attachment-image-preview {
		position: relative;
		width: 140rpx;
		height: 140rpx;
		border-radius: 12rpx;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
	}

	.attachment-thumbnail {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.attachment-file-preview {
		position: relative;
		display: flex;
		align-items: center;
		gap: 12rpx;
		padding: 14rpx 18rpx;
		border-radius: 12rpx;
		max-width: 520rpx;
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
	}

	.attachment-file-preview .file-icon {
		width: 30rpx;
		height: 30rpx;
		flex-shrink: 0;
		filter: brightness(0) invert(1);
		opacity: 0.8;
	}

	.attachment-file-meta {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
	}

	.attachment-file-meta .file-name {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.92);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.attachment-file-meta .file-size {
		font-size: 20rpx;
		color: rgba(255, 255, 255, 0.6);
	}

	.attachment-remove-btn {
		position: absolute;
		top: 4rpx;
		right: 4rpx;
		width: 40rpx;
		height: 40rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		background-color: rgba(0, 0, 0, 0.75);
		border-radius: 50%;
		z-index: 10;
	}

	.remove-icon {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(1);
	}

	.attachment-uploading-item {
		width: 140rpx;
		height: 140rpx;
		border-radius: 12rpx;
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		padding: 14rpx;
	}

	.uploading-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8rpx;
		width: 100%;
	}

	.uploading-content .file-icon {
		width: 42rpx;
		height: 42rpx;
		filter: brightness(0) invert(1);
		opacity: 0.9;
	}

	.uploading-info {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8rpx;
		width: 100%;
	}

	.uploading-info .file-name {
		font-size: 20rpx;
		color: #ffffff;
		text-align: center;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
	}

	.upload-progress {
		width: 100%;
		position: absolute;
		bottom: 8rpx;
		left: 8rpx;
		right: 8rpx;
	}

	.upload-error {
		font-size: 20rpx;
		color: #FEE2E2;
		text-align: center;
	}

	/* 节点信息弹窗 */
	.node-popup {
		position: fixed;
		z-index: 200;
		transform: translateX(-50%);
		pointer-events: auto;
	}

	.node-popup-content {
		display: flex;
		align-items: center;
		gap: 16rpx;
		padding: 16rpx 20rpx;
		background-color: rgba(255, 255, 255, 0.04);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 16rpx;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.06),
			0 4rpx 20rpx rgba(0, 0, 0, 0.2);
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.node-popup-content {
			background: rgba(20, 20, 30, 0.85);
		}
	}

	.node-popup-name {
		font-size: 26rpx;
		font-weight: 500;
		color: #FFFFFF;
		flex: 1;
	}

	/* 圆环进度条容器 */
	.mastery-ring-container {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* 圆环进度条 */
	.mastery-ring {
		width: 48rpx;
		height: 48rpx;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* 圆环内圈（遮罩） */
	.mastery-ring-inner {
		width: 36rpx;
		height: 36rpx;
		border-radius: 50%;
		background-color: rgba(10, 10, 18, 0.9);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* 百分比文字 */
	.mastery-ring-text {
		font-size: 16rpx;
		font-weight: 600;
		color: #FFFFFF;
	}

	/* 锁图标样式 */
	.mastery-lock-icon {
		width: 36rpx;
		height: 36rpx;
		filter: brightness(0) invert(1); /* SVG 转白色 */
	}

	/* 加载遮罩 */
	.loading-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1000;
		background-color: rgba(10, 10, 18, 0.9);
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.loading-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 24rpx;
	}

	/* 多节点轨道加载器 */
	.loading-spinner-enhanced {
		position: relative;
		width: 120rpx;
		height: 120rpx;
	}

	/* 中心脉冲光晕 */
	.loading-center-glow {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 32rpx;
		height: 32rpx;
		margin: -16rpx 0 0 -16rpx;
		background: radial-gradient(circle, rgba(64, 224, 208, 0.8), rgba(64, 224, 208, 0.2));
		border-radius: 50%;
		animation: centerPulse 2s ease-in-out infinite;
	}

	/* 轨道节点 */
	.loading-dot {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 16rpx;
		height: 16rpx;
		margin: -8rpx 0 0 -8rpx;
		background: #0088FF;
		border-radius: 50%;
		box-shadow: 0 0 16rpx rgba(0, 136, 255, 0.6);
	}

	.loading-dot-1 {
		animation: orbitRotate 2s linear infinite;
	}

	.loading-dot-2 {
		animation: orbitRotate 2s linear infinite 0.66s;
	}

	.loading-dot-3 {
		animation: orbitRotate 2s linear infinite 1.33s;
	}

	/* 中心脉冲动画 */
	@keyframes centerPulse {
		0%, 100% {
			transform: scale(1);
			opacity: 1;
		}
		50% {
			transform: scale(1.5);
			opacity: 0.6;
		}
	}

	/* 轨道旋转动画 */
	@keyframes orbitRotate {
		0% {
			transform: rotate(0deg) translateX(48rpx) rotate(0deg);
		}
		100% {
			transform: rotate(360deg) translateX(48rpx) rotate(-360deg);
		}
	}

	.loading-text {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.7);
	}

	/* 不确定性进度条 */
	.loading-progress-bar {
		width: 400rpx;
		height: 6rpx;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3rpx;
		overflow: hidden;
		margin-top: 16rpx;
	}

	.loading-progress-fill {
		height: 100%;
		background: linear-gradient(90deg,
			transparent 0%,
			rgba(0, 136, 255, 0.8) 50%,
			transparent 100%
		);
		animation: progressIndeterminate 1.5s ease-in-out infinite;
	}

	@keyframes progressIndeterminate {
		0% {
			transform: translateX(-100%);
		}
		100% {
			transform: translateX(400rpx);
		}
	}

	/* 图谱加载失败样式 */
	.graph-failed-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(10, 10, 18, 0.9);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.failed-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 40rpx;
	}

	.failed-icon {
		width: 80rpx;
		height: 80rpx;
		margin-bottom: 24rpx;
		opacity: 0.8;
		filter: brightness(0) invert(1);
	}

	.failed-title {
		font-size: 36rpx;
		font-weight: 600;
		color: #fff;
		margin-bottom: 12rpx;
	}

	.failed-message {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.7);
		margin-bottom: 40rpx;
		text-align: center;
	}

	.regenerate-btn {
		padding: 20rpx 60rpx;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		border-radius: 40rpx;
	}

	.regenerate-btn-text {
		font-size: 32rpx;
		font-weight: 500;
		color: #fff;
	}

	.regenerate-btn-disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	.retry-hint {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.5);
		margin-top: 16rpx;
	}

	/* 添加文件弹窗 */
	.add-file-popup-wrapper {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 200;
	}

	.add-file-popup {
		position: fixed;
		right: calc(100vw / 24);
		bottom: calc(100vh * 3 / 26 + 120rpx);
		min-width: 280rpx;
		background: rgba(30, 30, 45, 0.95);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		border-radius: 20rpx;
		box-shadow:
			0 12rpx 40rpx rgba(0, 0, 0, 0.4),
			0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
		overflow: hidden;
		transform: translateY(20rpx) scale(0.9);
		opacity: 0;
		transition: all 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	.add-file-popup.popup-show {
		transform: translateY(0) scale(1);
		opacity: 1;
	}

	.popup-option {
		display: flex;
		align-items: center;
		padding: 28rpx 32rpx;
		transition: background 150ms ease;
	}

	.popup-option:active {
		background: rgba(255, 255, 255, 0.08);
	}

	.popup-option-icon {
		width: 44rpx;
		height: 44rpx;
		margin-right: 24rpx;
		filter: brightness(0) invert(1);
		opacity: 0.85;
	}

	.popup-option-text {
		font-size: 30rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
	}

	.popup-divider {
		height: 1rpx;
		background: rgba(255, 255, 255, 0.1);
		margin: 0 24rpx;
	}

	.popup-arrow {
		position: absolute;
		right: 36rpx;
		bottom: -16rpx;
		width: 0;
		height: 0;
		border-left: 16rpx solid transparent;
		border-right: 16rpx solid transparent;
		border-top: 16rpx solid rgba(30, 30, 45, 0.95);
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.add-file-popup {
			background: rgba(40, 40, 55, 0.98);
		}
	}

	/* 添加链接对话框 - 与 u-modal 风格一致 */
	.link-dialog-overlay {
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

	.link-dialog-overlay.overlay-show {
		background: rgba(0, 0, 0, 0.6);
	}

	.link-dialog {
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
		transform: translateY(40rpx) scale(0.95);
		opacity: 0;
		transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	.link-dialog.dialog-show {
		transform: translateY(0) scale(1);
		opacity: 1;
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.link-dialog {
			background: rgba(30, 30, 45, 0.98);
		}
	}

	.link-dialog-title {
		padding: 40rpx 40rpx 0;
		font-size: 36rpx;
		font-weight: 600;
		color: #ffffff;
		text-align: center;
		display: block;
	}

	.link-dialog-content {
		padding: 32rpx 40rpx 40rpx;
	}

	.link-input-group {
		margin-bottom: 24rpx;
	}

	.link-input-group:last-child {
		margin-bottom: 0;
	}

	.link-input-label {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.7);
		margin-bottom: 12rpx;
		display: block;
	}

	.link-input {
		width: 100%;
		height: 80rpx;
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 12rpx;
		padding: 0 24rpx;
		font-size: 30rpx;
		color: #ffffff;
		box-sizing: border-box;
	}

	.link-input-placeholder {
		color: rgba(255, 255, 255, 0.35);
	}

	.link-dialog-actions {
		display: flex;
		border-top: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.link-btn {
		flex: 1;
		height: 100rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		transition: background 150ms ease;
	}

	.link-btn:active {
		background: rgba(255, 255, 255, 0.08);
	}

	.link-btn-cancel {
		border-right: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.link-btn-cancel .link-btn-text {
		color: rgba(255, 255, 255, 0.7);
	}

	.link-btn-confirm .link-btn-text {
		color: #00AAFF;
	}

	.link-btn-disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	.link-btn-text {
		font-size: 32rpx;
		font-weight: 500;
	}

	/* 上传进度遮罩 */
	.upload-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1000;
		background-color: rgba(10, 10, 18, 0.9);
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.upload-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 24rpx;
	}

	.upload-spinner {
		width: 80rpx;
		height: 80rpx;
		border: 4rpx solid rgba(255, 255, 255, 0.1);
		border-top-color: #0088FF;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	.upload-text {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.7);
	}

	/* +号弹窗 */
	.plus-popup-wrapper {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 200;
	}

	.plus-popup {
		position: fixed;
		left: calc(100vw / 24);
		bottom: calc(100vh * 1.5 / 26 + 100rpx);
		min-width: 280rpx;
		background: rgba(30, 30, 45, 0.95);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		border-radius: 20rpx;
		box-shadow:
			0 12rpx 40rpx rgba(0, 0, 0, 0.4),
			0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
		overflow: hidden;
		transform: translateY(20rpx) scale(0.9);
		opacity: 0;
		transition: all 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	.plus-popup.popup-show {
		transform: translateY(0) scale(1);
		opacity: 1;
	}

	.popup-option {
		display: flex;
		align-items: center;
		padding: 28rpx 32rpx;
		transition: background 150ms ease;
	}

	.popup-option:active {
		background: rgba(255, 255, 255, 0.08);
	}

	.popup-option-icon {
		width: 44rpx;
		height: 44rpx;
		margin-right: 24rpx;
		filter: brightness(0) invert(1);
		opacity: 0.85;
	}

	.popup-option-text {
		font-size: 30rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
	}

	.popup-divider {
		height: 1rpx;
		background: rgba(255, 255, 255, 0.1);
		margin: 0 24rpx;
	}

	.popup-arrow {
		position: absolute;
		left: 36rpx;
		bottom: -16rpx;
		width: 0;
		height: 0;
		border-left: 16rpx solid transparent;
		border-right: 16rpx solid transparent;
		border-top: 16rpx solid rgba(30, 30, 45, 0.95);
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.plus-popup {
			background: rgba(40, 40, 55, 0.98);
		}
	}
</style>
