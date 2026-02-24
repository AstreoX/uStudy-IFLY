<template>
	<view class="chat-page">
		<!-- 顶部导航栏 -->
		<view class="chat-nav-bar">
			<view class="nav-left" @click="goBack">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
			</view>
			<text class="nav-title">快速对话</text>
			<view class="nav-right" @click="openSettings">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/sliders-horizontal.svg" mode="aspectFit"></image>
			</view>
		</view>

		<!-- 消息区域 -->
		<scroll-view
			class="message-area"
			scroll-y
			:scroll-top="scrollTopValue"
			:scroll-with-animation="true"
			@scroll="onScroll"
			@scrolltoupper="onScrollToTop"
		>
			<view class="message-top-spacer"></view>

			<view
				v-for="(msg, index) in messages"
				:key="msg.id"
				:id="'msg-' + msg.id"
				class="message-row"
				:class="msg.role === 'user' ? 'message-row-right' : 'message-row-left'"
			>
				<!-- 用户消息：图片在气泡外上方 -->
				<template v-if="msg.role === 'user'">
					<!-- 图片附件容器（独立于气泡外） -->
					<view
						v-if="msg.attachments && msg.attachments.length > 0"
						class="message-attachments-wrapper"
					>
						<view class="message-attachments">
							<view
								v-for="att in msg.attachments"
								:key="att.id"
								class="message-attachment-item"
							>
								<image
									v-if="att.attachment_type === 'image'"
									:src="att.thumbnail_url || att.file_url"
									mode="aspectFill"
									class="message-image"
									@click="previewMessageImage(att.file_url, msg)"
								></image>
							</view>
						</view>
					</view>

					<!-- 气泡行：左侧放重试按钮 -->
					<view class="user-bubble-row">
						<view v-if="msg.isFailed" class="msg-retry-btn" @click="resendMessage(msg)">
							<image class="msg-retry-icon" src="/static/icons/phosphor-icons/SVGs Flat/fill/arrows-clockwise-fill.svg" mode="aspectFit" />
						</view>
						<view v-if="msg.content && msg.content.trim()" class="message-bubble bubble-user">
							<text class="message-text">{{ msg.content }}</text>
						</view>
					</view>
				</template>

				<!-- AI消息：保持原有结构 -->
				<template v-else>
					<view class="message-bubble bubble-ai">

						<!-- AI消息：按片段顺序渲染 -->
						<template v-for="(seg, segIdx) in getMessageSegments(msg)">
						<!-- 文本片段（Markdown渲染） -->
						<markdown-render
							v-if="seg.type === 'text' && seg.content && seg.content.trim()"
							:key="'text-' + segIdx"
							:content="seg.content"
						/>

						<!-- 记忆类工具：行内波浪文字 -->
						<view
							v-else-if="seg.type === 'tool' && isMemoryTool(seg.toolCall.tool)"
							:key="'memory-tool-' + segIdx"
							class="memory-tool-inline"
							:class="{
								'memory-tool-active': seg.toolCall.status === 'running' || memoryToolDelayedDone[seg.toolCall.id],
								'memory-tool-done': seg.toolCall.status === 'done' && !memoryToolDelayedDone[seg.toolCall.id]
							}"
						>
							<text class="memory-tool-text">{{ getMemoryToolText(seg.toolCall.tool) }}</text>
						</view>

						<!-- 非记忆类工具：原有卡片样式 -->
						<view
							v-else-if="seg.type === 'tool'"
							:key="'tool-' + segIdx"
							class="tool-call-card"
							:class="{
								'tool-call-running': seg.toolCall.status === 'running',
								'tool-call-pending': seg.toolCall.status === 'pending_confirmation',
								'tool-call-success': seg.toolCall.status === 'done' && seg.toolCall.success,
								'tool-call-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
							}"
						>
							<view class="tool-call-header">
								<image
									class="tool-call-icon"
									:src="getToolIcon(seg.toolCall.tool)"
									mode="aspectFit"
								></image>
								<text class="tool-call-name">{{ seg.toolCall.display_name || getToolDisplayName(seg.toolCall.tool) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
								<image
									v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="tool-call-status-icon"
									src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg"
									mode="aspectFit"
								></image>
								<image
									v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="tool-call-status-icon tool-call-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
									mode="aspectFit"
								></image>
							</view>

							<!-- 确认按钮区域 -->
							<view v-if="seg.toolCall.status === 'pending_confirmation'" class="tool-confirm-actions">
								<view class="tool-confirm-info">
									<text class="tool-confirm-text">{{ getConfirmationText(seg.toolCall) }}</text>
								</view>
								<view class="tool-confirm-buttons">
									<view class="tool-btn tool-btn-cancel" @click="handleToolReject(msg.id, seg.toolCall)">
										<text class="tool-btn-text">取消</text>
									</view>
									<view class="tool-btn tool-btn-confirm" @click="handleToolConfirm(msg.id, seg.toolCall)">
										<text class="tool-btn-text">确认</text>
									</view>
								</view>
							</view>

							<!-- 执行结果 -->
							<view v-if="seg.toolCall.status === 'done' && seg.toolCall.message" class="tool-call-result">
								<text class="tool-call-result-text">{{ seg.toolCall.message }}</text>
							</view>

							<!-- 查看学习空间工具结果 -->
							<view v-if="seg.toolCall.tool === 'view_learning_spaces' && seg.toolCall.status === 'done' && seg.toolCall.result && seg.toolCall.result.spaces" class="tool-spaces-list">
								<view
									v-for="space in seg.toolCall.result.spaces"
									:key="space.id"
									class="tool-space-item"
									@click="handleSpaceClick(space)"
								>
									<view class="tool-space-color" :style="{ backgroundColor: space.color }"></view>
									<text class="tool-space-name">{{ space.name }}</text>
									<image class="tool-space-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
								</view>
							</view>
						</view>
					</template>

					<!-- 等待输出加载动画 -->
					<view v-if="msg.isStreaming && msg.isWaitingOutput" class="typing-indicator">
						<view class="typing-dot"></view>
						<view class="typing-dot"></view>
						<view class="typing-dot"></view>
					</view>

				</view>

				<!-- AI 消息操作图标 (流式输出完成后显示) -->
				<view v-if="msg.role === 'ai' && !msg.isStreaming" class="ai-msg-actions">
					<image
						class="ai-msg-action-icon"
						src="/static/icons/phosphor-icons/SVGs/regular/copy.svg"
						mode="aspectFit"
						@click="copyMessage(msg)"
					></image>
					<image
						class="ai-msg-action-icon"
						src="/static/icons/phosphor-icons/SVGs/regular/flag.svg"
						mode="aspectFit"
						@click="openFeedbackModal(msg)"
					></image>
				</view>
			</template>
		</view>

		<view class="message-bottom-spacer" :style="keyboardHeight > 0 ? { height: 'calc(100vh * 6 / 26 + ' + keyboardHeight + 'px)' } : {}"></view>
		</scroll-view>


		<!-- 底部输入栏 -->
		<view class="input-bar" :style="{ bottom: keyboardHeight > 0 ? keyboardHeight + 'px' : '' }">
			<!-- 模型选择下拉菜单（向上弹出） -->
			<view v-if="showModelMenu" class="model-menu-backdrop" @click="showModelMenu = false"></view>
			<view v-if="showModelMenu" class="model-menu">
				<view
					v-for="m in availableModels"
					:key="m.id"
					class="model-menu-item"
					:class="{ 'model-menu-item-active': m.id === selectedModelId }"
					@click="selectModel(m.id)"
				>
					<view class="model-menu-item-info">
						<text class="model-menu-item-name">{{ m.display_name }}</text>
						<text class="model-menu-item-desc">{{ m.description }}</text>
					</view>
					<svg v-if="m.id === selectedModelId" viewBox="0 0 256 256" class="model-menu-check">
						<polyline points="40 144 96 200 216 80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
					</svg>
				</view>
			</view>

			<!-- 模型选择器（输入框上方） -->
			<view v-if="availableModels.length > 0" class="model-bar">
				<view class="model-selector-btn" @click="toggleModelMenu">
					<svg viewBox="0 0 256 256" class="model-selector-icon">
						<rect width="256" height="256" fill="none"/>
						<line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
						<line x1="40" y1="64" x2="216" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
						<line x1="40" y1="192" x2="216" y2="192" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
						<circle cx="104" cy="64" r="12" fill="currentColor"/>
						<circle cx="168" cy="128" r="12" fill="currentColor"/>
						<circle cx="88" cy="192" r="12" fill="currentColor"/>
					</svg>
					<text class="model-selector-label">{{ selectedModelName }}</text>
					<svg viewBox="0 0 256 256" class="model-selector-chevron">
						<polyline points="208 96 128 176 48 96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
					</svg>
				</view>
			</view>

			<view class="input-bar-inner">
				<!-- 待发送附件预览区域 -->
				<view v-if="pendingAttachments.length > 0 || uploadingFiles.length > 0" class="pending-attachments-area">
					<!-- 已上传待发送的附件 -->
					<view v-for="att in pendingAttachments" :key="att.id" class="attachment-preview-item">
						<view v-if="att.attachment_type === 'image'" class="attachment-image-preview">
							<image :src="att.thumbnail_url || att.file_url" class="attachment-thumbnail" mode="aspectFill"></image>
							<view class="attachment-remove-btn" @click.stop="removeAttachment(att.id)">
								<image class="remove-icon" src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit"></image>
							</view>
						</view>
						<view v-else class="attachment-file-preview">
							<image class="file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit"></image>
							<text class="file-name">{{ att.original_filename }}</text>
							<view class="attachment-remove-btn" @click.stop="removeAttachment(att.id)">
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

					<view class="input-action send-btn-wrapper" @click="handleRightButtonClick">
						<!-- AI正在回复 → 停止按钮 -->
						<view v-if="isAiStreaming" class="stop-btn">
							<view class="stop-btn-inner"></view>
						</view>
						<!-- 可发送 / 禁用状态 → 发送按钮 -->
						<image
							v-else
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
			<view
				class="plus-popup"
				:class="{ 'popup-show': plusPopupVisible }"
				@click.stop
			>
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

		<!-- 问题反馈弹窗 -->
		<u-input-modal
			:visible="showFeedbackModal"
			title="问题反馈"
			placeholder="请描述您遇到的问题..."
			:maxLength="500"
			:minLength="1"
			@confirm="handleFeedbackSubmit"
			@close="closeFeedbackModal"
		/>

		<!-- 图片来源选择弹窗 -->
		<image-source-picker
			:visible="showImageSourcePicker"
			@camera="handleCameraSelect"
			@album="handleAlbumSelect"
			@close="showImageSourcePicker = false"
		/>

		<!-- SSE Renderjs 组件 (仅 Android App) -->
		<!-- #ifdef APP-PLUS -->
		<sse-renderjs
			ref="sseRenderjs"
			@sse-events="onRenderjsSseEvents"
			@sse-complete="onRenderjsSseComplete"
			@sse-error="onRenderjsSseError"
		/>
		<!-- #endif -->
	</view>
</template>

<script>
	import { createQuickChatConversation, sendQuickChatMessage, confirmToolExecution, getConversation, submitFeedback, getModels } from '@/api/chat'
	import { uploadAttachment, deleteAttachment, formatFileSize } from '@/api/attachment'
	import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
	import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
	import ImageSourcePicker from '@/components/image-source-picker/image-source-picker.vue'
	import { goBack } from '@/utils/navigation'
	import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
	import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError } from '@/utils/sse'
	import { savePendingMessage, getPendingMessages, removePendingMessage, savePendingMessagesFromArray, clearPendingMessages } from '@/utils/messageDraft'
	import { startBackgroundMonitor, stopBackgroundMonitor, getActiveMonitor } from '@/utils/backgroundChatMonitor'
	// #ifdef APP-PLUS
	import SseRenderjs from '@/components/sse-renderjs/sse-renderjs.vue'
	// #endif

	// 工具名称映射
	const TOOL_DISPLAY_NAMES = {
		view_learning_spaces: '查看学习空间',
		rebind_to_learning_space: '绑定到学习空间',
		create_learning_space: '创建学习空间'
	}

	// 工具图标映射
	const TOOL_ICONS = {
		view_learning_spaces: '/static/icons/phosphor-icons/SVGs/regular/eye.svg',
		rebind_to_learning_space: '/static/icons/phosphor-icons/SVGs/regular/link.svg',
		create_learning_space: '/static/icons/phosphor-icons/SVGs/regular/plus-circle.svg'
	}

	// 记忆类工具集合（使用行内波浪文字而非卡片）
	const MEMORY_TOOLS = new Set([
		'write_to_long_term_memory',
		'delete_from_long_term_memory',
		'write_to_space_memory',
		'delete_from_space_memory'
	])

	// 记忆工具显示文字
	const MEMORY_TOOL_TEXT = {
		write_to_long_term_memory: '正在更新长期记忆…',
		delete_from_long_term_memory: '正在删除长期记忆…',
		write_to_space_memory: '正在更新学习空间偏好…',
		delete_from_space_memory: '正在删除学习空间偏好…'
	}

	export default {
		components: {
			MarkdownRender,
			UInputModal,
			ImageSourcePicker,
			// #ifdef APP-PLUS
			SseRenderjs,
			// #endif
		},
		data() {
			return {
				chatId: '',
				conversationId: null,
				messages: [],
				inputText: '',
				textareaHeight: 'auto',
				textareaOverflow: 'hidden',
				textareaMaxLines: 4, // 输入框可撑高的最大行数
				textareaLineCount: 1, // 记录 linechange 上报的真实行数（用于非 H5 兜底）
				keyboardHeight: 0,
				nextId: 1,
				cancelSSE: null,
				isLoadingHistory: false,

				// 滚动控制
				scrollTopValue: 0,
				isAutoScrollEnabled: true,
				lastScrollTop: 0,
				isUserScrolling: false,
				scrollTimer: null,

				// AI 流式生成监听
				aiStreamingMsgId: null,
				lastMsgHeight: 0,
				heightCheckTimer: null,

				// +号弹窗相关
				showPlusPopup: false,
				plusPopupVisible: false,
				showImageSourcePicker: false,

				// 工具调用相关
				activeToolCalls: [],

				// 记忆工具最短显示时间跟踪
				memoryToolStartTimes: {},    // { toolCallId: timestamp }
				memoryToolDelayedDone: {}, // { toolCallId: true } 延迟隐藏的工具ID

				// 问题反馈相关
				showFeedbackModal: false,
				feedbackTargetMsg: null,

				// 附件相关
				pendingAttachments: [],  // 待发送的附件列表
				uploadingFiles: [],      // 上传中的文件列表

				// 后台监控：最后一条用户消息的发送时间
				lastUserMessageTimestamp: null,

				// 模型选择相关
				availableModels: [],
				selectedModelId: null,
				showModelMenu: false
			}
		},

		onLoad(options) {
			this.chatId = options.chatId || ''
			if (options.conversationId) {
				const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
				if (uuidRegex.test(options.conversationId)) {
					this.conversationId = options.conversationId
					this.loadExistingConversation(options.conversationId)
				} else {
					uni.showToast({ title: '无效的对话ID', icon: 'none' })
				}
			} else {
				// 新对话：添加初始欢迎消息（不持久化）
				this.messages.push({
					id: this.nextId++,
					role: 'ai',
					content: `你好！我是你的学习助手，有什么我可以帮你的：

💬 **随便聊聊** — 任何学习上的问题都可以直接问我
📚 **学习空间** — 帮你查看、创建或进入学习空间，开始系统化学习
💾 **记住偏好** — 我会记住你的学习习惯和偏好，下次继续为你服务

想要更深入的学习体验（知识图谱、练习测试、资料检索等），可以进入具体的学习空间。现在有什么想问的？`,
					isWelcome: true
				})
			}
		},

		onShow() {
			// 检查后台监控结果并恢复
			const monitor = getActiveMonitor()
			if (monitor && monitor.conversationId === this.conversationId) {
				stopBackgroundMonitor()
				// Scenario A: 同一页面实例（onHide → onShow），有 streaming AI 消息
				if (this.messages.some(m => m.role === 'ai' && m.isStreaming)) {
					this.recoverFromBackground()
				} else {
					// Scenario B: 新页面实例（页面销毁后重建），loadExistingConversation 已处理
					clearPendingMessages(this.conversationId)
				}
			}

			// 页面显示时，合并本地缓存的待同步消息（历史加载中不重复 merge）
			if (this.conversationId && !this.isLoadingHistory) {
				this.mergePendingMessages()
			}
		},

		onHide() {
			console.log('[QuickChat] onHide triggered, isAiStreaming:', this.isAiStreaming,
				'conversationId:', this.conversationId, 'cancelSSE:', !!this.cancelSSE,
				'isSendingMessage:', this.isSendingMessage)
			this._tryStartMonitorOrSave('onHide')
		},

		// navigateBack 时 onHide 不触发，onUnload 才触发
		onUnload() {
			console.log('[QuickChat] onUnload triggered, isAiStreaming:', this.isAiStreaming,
				'conversationId:', this.conversationId, 'cancelSSE:', !!this.cancelSSE,
				'isSendingMessage:', this.isSendingMessage)
			this._tryStartMonitorOrSave('onUnload')
		},

		mounted() {
			console.log('[QuickChat] mounted() fired — model selector code is active')
			// #ifdef APP-PLUS
			if (this.$refs.sseRenderjs) {
				setSseEventBus(this.$refs.sseRenderjs)
			}
			// #endif

			this.loadModels()

			this.$nextTick(() => {
				this.adjustTextareaHeight()
				this.scrollToLatestMessage()
			})

			// 仅在非 H5 平台执行键盘监听
			// #ifndef H5
			uni.onKeyboardHeightChange((res) => {
				this.keyboardHeight = res.height
				if (res.height > 0) {
					this.isAutoScrollEnabled = true
					this.$nextTick(() => {
						this.scrollToLatestMessage()
					})
				}
			})
			// #endif
		},

		beforeDestroy() {
			console.log('[QuickChat] beforeDestroy triggered, activeMonitor:', !!getActiveMonitor())
			// onHide/onUnload 可能已经启动了监控，作为最后兜底
			this._tryStartMonitorOrSave('beforeDestroy')

			// #ifdef APP-PLUS
			clearSseEventBus()
			// #endif

			if (this.scrollTimer) {
				clearTimeout(this.scrollTimer)
				this.scrollTimer = null
			}
			if (this.heightCheckTimer) {
				clearInterval(this.heightCheckTimer)
				this.heightCheckTimer = null
			}
			if (this.cancelSSE) {
				this.cancelSSE()
				this.cancelSSE = null
			}
		},

		computed: {
			isAiStreaming() {
				return this.messages.some(msg => msg.role === 'ai' && msg.isStreaming)
			},
			canSend() {
				return this.inputText.trim().length > 0 || this.pendingAttachments.length > 0
			},
			selectedModelName() {
				const model = this.availableModels.find(m => m.id === this.selectedModelId)
				return model ? model.display_name : '模型'
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
			// ==================== 模型选择 ====================
			toggleModelMenu() {
				this.showModelMenu = !this.showModelMenu
			},
			selectModel(id) {
				this.selectedModelId = id
				this.showModelMenu = false
				uni.setStorageSync('uStudy_selectedModelId', id)
			},
			async loadModels() {
				console.log('[QuickChat] loadModels() called')
				try {
					const res = await getModels()
					console.log('[QuickChat] getModels() response:', JSON.stringify(res))
					const models = res.models || res || []
					this.availableModels = models
					console.log('[QuickChat] availableModels set, count:', models.length)
					const storedId = uni.getStorageSync('uStudy_selectedModelId')
					if (storedId && models.some(m => m.id === storedId)) {
						this.selectedModelId = storedId
					} else {
						const defaultModel = models.find(m => m.is_default)
						this.selectedModelId = defaultModel ? defaultModel.id : (models[0]?.id || null)
					}
					console.log('[QuickChat] selectedModelId:', this.selectedModelId)
				} catch (err) {
					console.error('[QuickChat] Failed to load models:', err, 'statusCode:', err?.statusCode, 'message:', err?.message)
				}
			},

			// ==================== 后台监控启动 ====================
			_tryStartMonitorOrSave(source) {
				// 已有监控则跳过
				if (getActiveMonitor()) {
					console.log(`[QuickChat] ${source}: monitor already active, skipping`)
					return
				}
				if (!this.conversationId) return

				const hasPendingUserMessage = this.messages.some(
					m => m.role === 'user' && m.pendingId && !m.synced
				)
				const hasActiveRequest = this.isAiStreaming || hasPendingUserMessage ||
					this.cancelSSE !== null || this.isSendingMessage

				console.log(`[QuickChat] ${source}: hasActiveRequest=${hasActiveRequest}`,
					`(streaming=${this.isAiStreaming}, pending=${hasPendingUserMessage},`,
					`cancelSSE=${!!this.cancelSSE}, sending=${this.isSendingMessage})`,
					`lastTs=${this.lastUserMessageTimestamp}`)

				if (hasActiveRequest && this.lastUserMessageTimestamp) {
					console.log(`[QuickChat] ${source}: starting background monitor`)
					startBackgroundMonitor({
						conversationId: this.conversationId,
						userMessageTimestamp: this.lastUserMessageTimestamp,
						chatMode: 'quick_chat',
					})
					clearPendingMessages(this.conversationId)
				} else {
					savePendingMessagesFromArray(this.conversationId, this.messages)
				}
			},

			// ==================== 后台监控辅助 ====================
			isBackgroundMonitorActive() {
				const monitor = getActiveMonitor()
				return monitor && monitor.conversationId === this.conversationId
			},

			async recoverFromBackground() {
				if (!this.conversationId) return

				try {
					const result = await getConversation(this.conversationId)
					this.messages = result.messages.map((m, i) => ({
						id: i + 1,
						role: m.role === 'user' ? 'user' : 'ai',
						content: m.content,
						attachments: m.attachments || [],
						created_at: m.created_at
					}))
					this.nextId = this.messages.length + 1
					clearPendingMessages(this.conversationId)
					this.$nextTick(() => this.scrollToLatestMessage())
				} catch (err) {
					// Recovery failed — leave current messages as-is
				} finally {
					this.activeToolCalls = []
					this.cancelSSE = null
					this.stopHeightMonitor()
				}
			},

			// ==================== Renderjs SSE 事件处理 ====================
			onRenderjsSseEvents(data) {
				handleSseEvents(data)
			},
			onRenderjsSseComplete(data) {
				handleSseComplete(data)
			},
			onRenderjsSseError(data) {
				handleSseError(data)
			},

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
						measuredLines = Math.max(1, Math.ceil(Math.max(0, contentH - padV) / lineH))
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

			goBack() {
				goBack()
			},

			openSettings() {
				uni.navigateTo({
					url: `/pages/quickChatSettings/quickChatSettings?chatId=${this.chatId}&conversationId=${this.conversationId || ''}`
				})
			},

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

				const remainingSlots = 9 - this.pendingAttachments.length
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
					const files = Array.from(e.target.files).slice(0, remainingSlots)
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
						console.error('[QuickChat] 选择文件失败:', getPickerErrorMessage(err), err)
						uni.showToast({ title: '选择文件失败', icon: 'none' })
					}
				}
				// #endif
			},

			handleSelectImage() {
				this.closePlusPopup()

				const remainingSlots = 9 - this.pendingAttachments.length
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
				const remainingSlots = 9 - this.pendingAttachments.length
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

					uni.showToast({ title: '上传成功', icon: 'success', duration: 1500 })
				} catch (err) {
					console.error('上传失败:', err)

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
					}, 3000)
				}
			},

			async removeAttachment(attachmentId) {
				try {
					const index = this.pendingAttachments.findIndex(att => att.id === attachmentId)
					if (index !== -1) {
						this.pendingAttachments.splice(index, 1)
					}

					await deleteAttachment(attachmentId)
				} catch (err) {
					console.error('删除附件失败:', err)
				}
			},

			handleRightButtonClick() {
				if (this.isAiStreaming) {
					this.stopAiReply()
				} else if (this.canSend) {
					this.sendMessage()
				}
			},

			stopAiReply() {
				if (this.cancelSSE) {
					this.cancelSSE()
					this.cancelSSE = null
				}
				const streamingMsg = this.messages.find(msg => msg.role === 'ai' && msg.isStreaming)
				if (streamingMsg) {
					streamingMsg.isStreaming = false
					streamingMsg.isWaitingOutput = false
				}
				this.stopHeightMonitor()
			},

			// ========== 消息片段处理 ==========

			getMessageSegments(msg) {
				// 如果有已处理的 segments，直接使用
				if (msg.segments && msg.segments.length > 0) {
					return msg.segments
				}

				// 如果有流式片段，使用流式片段
				if (msg.streamSegments && msg.streamSegments.length > 0) {
					const segments = [...msg.streamSegments]
					// 添加当前正在流式的文本
					if (msg.content && msg.content.length > 0) {
						segments.push({ type: 'text', content: msg.content })
					}
					return segments
				}

				// 否则整个内容作为文本片段
				if (msg.content) {
					return [{ type: 'text', content: msg.content }]
				}

				return []
			},

			getToolDisplayName(toolName) {
				return TOOL_DISPLAY_NAMES[toolName] || toolName
			},

			getToolIcon(toolName) {
				return TOOL_ICONS[toolName] || '/static/icons/phosphor-icons/SVGs/regular/folder-simple.svg'
			},

			isMemoryTool(toolName) {
				return MEMORY_TOOLS.has(toolName)
			},

			getMemoryToolText(toolName) {
				return MEMORY_TOOL_TEXT[toolName] || '正在访问记忆…'
			},

			getMemoryToolDisplayStatus(toolCall) {
				if (!toolCall) return 'running'
				// 如果工具在延迟隐藏集合中，继续显示为 running
				if (this.memoryToolDelayedDone[toolCall.id]) {
					return 'running'
				}
				return toolCall.status
			},

			getConfirmationText(toolCall) {
				if (toolCall.tool === 'rebind_to_learning_space') {
					return `确认将对话绑定到「${toolCall.arguments?.space_name || '学习空间'}」？`
				}
				if (toolCall.tool === 'create_learning_space') {
					return `确认创建学习空间「${toolCall.arguments?.name || '新空间'}」？`
				}
				return '确认执行此操作？'
			},

			// ========== 工具调用处理 ==========

			handleToolCallEvent(aiMsgId, data) {
				const msg = this.messages.find(m => m.id === aiMsgId)
				if (!msg) return

				const { id, tool, status, success, result, arguments: args, display_name, requires_confirmation, message } = data

				if (status === 'running') {
					// 工具开始执行：关闭等待输出状态
					if (msg.isWaitingOutput) {
						msg.isWaitingOutput = false
					}

					const existing = this.activeToolCalls.find(tc => tc.id === id)
					if (existing) return

					// 记忆工具：记录开始时间
					if (MEMORY_TOOLS.has(tool)) {
						this.memoryToolStartTimes[id] = Date.now()
					}

					// 初始化片段数组
					if (!msg.streamSegments) {
						msg.streamSegments = []
					}

					// 如果有累积的文本，保存为文本片段
					if (msg.content && msg.content.length > 0) {
						msg.streamSegments.push({ type: 'text', content: msg.content })
						msg.content = ''
					}

					// 创建工具调用对象
					const toolCall = { id, tool, arguments: args, status: 'running', display_name, requires_confirmation }

					// 添加工具调用片段
					msg.streamSegments.push({ type: 'tool', toolCall })

					// 添加到活动工具调用列表
					this.activeToolCalls.push(toolCall)

				} else if (status === 'pending_confirmation') {
					// 工具需要确认
					const toolCall = this.activeToolCalls.find(tc => tc.id === id)
					if (toolCall) {
						toolCall.status = 'pending_confirmation'
						toolCall.arguments = args
						toolCall.display_name = display_name
						toolCall.requires_confirmation = true
					}

					// 同步更新 streamSegments
					if (msg.streamSegments) {
						const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === id)
						if (seg && toolCall) {
							seg.toolCall = { ...toolCall }
						}
					}

				} else if (status === 'done') {
					// 工具完成：重新开启等待状态（等待后续输出）
					msg.isWaitingOutput = true

					const toolCall = this.activeToolCalls.find(tc => tc.id === id)
					if (toolCall) {
						toolCall.status = 'done'
						toolCall.success = success
						toolCall.result = result
						toolCall.message = message

						// 记忆工具：最短显示1秒
						if (MEMORY_TOOLS.has(tool)) {
							const startTime = this.memoryToolStartTimes[id]
							const elapsed = startTime ? Date.now() - startTime : 1000
							const minDisplayTime = 1000 // 最短显示1秒

							if (elapsed < minDisplayTime) {
								// 添加到延迟隐藏集合
								this.memoryToolDelayedDone[id] = true
								setTimeout(() => {
									delete this.memoryToolDelayedDone[id]
									delete this.memoryToolStartTimes[id]
								}, minDisplayTime - elapsed)
							} else {
								delete this.memoryToolStartTimes[id]
							}
						}
					}

					// 同步更新 streamSegments
					if (msg.streamSegments) {
						const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === id)
						if (seg && toolCall) {
							seg.toolCall = { ...toolCall }
						}
					}
				}

				// 触发 UI 更新
				this.$forceUpdate()
				this.scrollToLatestMessage()
			},

			async handleToolConfirm(msgId, toolCall) {
				try {
					const result = await confirmToolExecution(this.conversationId, toolCall.id, {
						tool_name: toolCall.tool,
						arguments: toolCall.arguments,
						confirmed: true
					})

					// 更新工具状态
					toolCall.status = 'done'
					toolCall.success = result.success
					toolCall.message = result.message
					toolCall.result = result.data

					// 同步更新消息中的工具片段
					const msg = this.messages.find(m => m.id === msgId)
					if (msg && msg.streamSegments) {
						const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
						if (seg) {
							seg.toolCall = { ...toolCall }
						}
					}

					this.$forceUpdate()

					// 如果需要跳转，延迟执行让用户看到成功状态
					if (result.data?.action === 'navigate_to_space_chat') {
						setTimeout(() => {
							this.navigateToSpaceChat(result.data.space_id, result.data.space_name, result.data.conversation_id)
						}, 1200) // 延迟 1.2 秒，让用户看到绑定成功的卡片状态
					}
				} catch (err) {
					uni.showToast({ title: err.message || '操作失败', icon: 'none' })
					toolCall.status = 'done'
					toolCall.success = false
					toolCall.message = '操作失败'
					this.$forceUpdate()
				}
			},

			async handleToolReject(msgId, toolCall) {
				try {
					await confirmToolExecution(this.conversationId, toolCall.id, {
						tool_name: toolCall.tool,
						arguments: toolCall.arguments,
						confirmed: false
					})
				} catch (err) {
					// 忽略拒绝时的错误
				}

				toolCall.status = 'done'
				toolCall.success = false
				toolCall.message = '用户取消了操作'

				// 同步更新消息中的工具片段
				const msg = this.messages.find(m => m.id === msgId)
				if (msg && msg.streamSegments) {
					const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
					if (seg) {
						seg.toolCall = { ...toolCall }
					}
				}

				this.$forceUpdate()
			},

			handleSpaceClick(space) {
				// 点击学习空间列表项，触发绑定
				this.inputText = `帮我进入「${space.name}」学习空间`
				this.sendMessage()
			},

			navigateToSpaceChat(spaceId, spaceName, conversationId) {
				uni.redirectTo({
					url: `/pages/spaceChat/spaceChat?id=${spaceId}&name=${encodeURIComponent(spaceName)}&conversationId=${conversationId || this.conversationId}`
				})
			},

			// ========== 滚动控制方法 ==========

			scrollToLatestMessage() {
				if (!this.isAutoScrollEnabled) return
				if (this.messages.length === 0) return

				this.$nextTick(() => {
					this.forceScrollUpdate(99999)
				})
			},

			forceScrollUpdate(targetScrollTop) {
				this.scrollTopValue = targetScrollTop + 0.1
				this.$nextTick(() => {
					this.scrollTopValue = targetScrollTop
				})
			},

			onScroll(e) {
				const currentScrollTop = e.detail.scrollTop

				if (this.scrollTimer) {
					clearTimeout(this.scrollTimer)
				}

				if (currentScrollTop < this.lastScrollTop - 10) {
					this.isUserScrolling = true
					this.isAutoScrollEnabled = false
				}

				this.lastScrollTop = currentScrollTop

				this.scrollTimer = setTimeout(() => {
					this.isUserScrolling = false
				}, 150)
			},

			// ========== AI 流式生成监听 ==========

			startHeightMonitor(msgId) {
				this.aiStreamingMsgId = msgId
				this.lastMsgHeight = 0

				this.heightCheckTimer = setInterval(() => {
					this.checkHeightChange()
				}, 100)
			},

			stopHeightMonitor() {
				if (this.heightCheckTimer) {
					clearInterval(this.heightCheckTimer)
					this.heightCheckTimer = null
				}
				this.aiStreamingMsgId = null
				this.lastMsgHeight = 0
			},

			checkHeightChange() {
				if (!this.aiStreamingMsgId) return

				const msgSelector = `#msg-${this.aiStreamingMsgId}`

				const query = uni.createSelectorQuery().in(this)
				query.select(msgSelector).boundingClientRect(rect => {
					if (!rect) return

					const lineHeightThreshold = 20

					if (rect.height > this.lastMsgHeight + lineHeightThreshold) {
						this.lastMsgHeight = rect.height
						this.scrollToLatestMessage()
					}
				}).exec()
			},

			// ========== 消息发送 ==========

			sendMessage() {
				const text = this.inputText.trim()
				if (!text && this.pendingAttachments.length === 0) return

				this.isAutoScrollEnabled = true

				// 获取附件 IDs 和完整附件信息
				const attachmentIds = this.pendingAttachments.map(att => att.id)
				const attachments = [...this.pendingAttachments]  // 保留副本
				this.pendingAttachments = []

				// 生成待同步消息的唯一标识
				const pendingId = `pending_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
				const userMessage = {
					id: this.nextId++,
					role: 'user',
					content: text,
					attachments: attachments,
					pendingId: pendingId,
					synced: false,
					isFailed: false,
					timestamp: Date.now()
				}

				this.messages.push(userMessage)
				this.inputText = ''
				this.scrollToLatestMessage()

				// 保存到本地存储，防止请求失败后消息丢失
				if (this.conversationId) {
					savePendingMessage(this.conversationId, userMessage)
				}

				this.sendRealMessage(text, attachmentIds.length > 0 ? attachmentIds : null, pendingId)
			},

			async initConversation() {
				if (this.conversationId) return

				try {
					const res = await createQuickChatConversation('快速对话')
					this.conversationId = res.id
				} catch (err) {
					uni.showToast({ title: '创建对话失败', icon: 'none' })
					throw err
				}
			},

			async loadExistingConversation(convId) {
				this.isLoadingHistory = true
				try {
					const result = await getConversation(convId)
					const historyMessages = result.messages || []

					historyMessages.forEach(msg => {
						this.messages.push({
							id: this.nextId++,
							role: msg.role === 'user' ? 'user' : 'ai',
							content: msg.content || '',
							attachments: msg.attachments || [],
							isStreaming: false
						})
					})

					// 后台监控 active 时，服务器数据已包含完整回复，清空缓存避免重复
					const monitor = getActiveMonitor()
					if (monitor && monitor.conversationId === this.conversationId) {
						clearPendingMessages(this.conversationId)
					} else {
						this.mergePendingMessages()
					}
					this.$nextTick(() => {
						this.scrollToLatestMessage()
					})
				} catch (err) {
					uni.showToast({ title: '加载对话失败', icon: 'none' })
				} finally {
					this.isLoadingHistory = false
				}
			},

			/**
			 * 合并本地缓存的待同步消息
			 * 用于页面重新显示时恢复未成功发送的消息
			 */
			mergePendingMessages() {
				if (!this.conversationId) return

				const pendingMessages = getPendingMessages(this.conversationId)
				if (!pendingMessages || pendingMessages.length === 0) return

				// 获取当前消息的 pendingId 集合，用于去重
				const existingPendingIds = new Set(
					this.messages.filter(m => m.pendingId).map(m => m.pendingId)
				)

				// 合并待同步消息（避免重复）
				for (const pm of pendingMessages) {
					if (!existingPendingIds.has(pm.pendingId)) {
						this.messages.push({
							id: this.nextId++,
							role: pm.role,
							content: pm.content,
							attachments: pm.attachments || [],
							pendingId: pm.pendingId,
							synced: false,
							timestamp: pm.timestamp,
							isFailed: true  // 标记为发送失败状态
						})
					}
				}

				if (pendingMessages.length > 0) {
					this.$nextTick(() => {
						this.scrollToLatestMessage()
					})
				}
			},

			async sendRealMessage(userMessage, attachmentIds = null, pendingId = null) {
				this.lastUserMessageTimestamp = Date.now()

				// 记录是否是新对话（创建对话前 conversationId 为空）
				const isNewConversation = !this.conversationId

				try {
					await this.initConversation()
				} catch {
					if (pendingId) {
						const userMsg = this.messages.find(m => m.pendingId === pendingId)
						if (userMsg) {
							userMsg.isFailed = true
						}
					}
					return
				}

				// 新对话创建成功后，保存用户消息到本地存储
				if (isNewConversation && pendingId && this.conversationId) {
					const userMsg = this.messages.find(m => m.pendingId === pendingId)
					if (userMsg) {
						savePendingMessage(this.conversationId, userMsg)
					}
				}

				const aiMsgId = this.nextId++
				this.messages.push({
					id: aiMsgId,
					role: 'ai',
					content: '',
					isStreaming: true,
					isWaitingOutput: true
				})
				this.scrollToLatestMessage()
				this.startHeightMonitor(aiMsgId)
				this.activeToolCalls = []

				const msgIndex = this.messages.length - 1

				this.cancelSSE = sendQuickChatMessage(
					this.conversationId,
					userMessage,
					{
						onTextDelta: (content) => {
							const msg = this.messages[msgIndex]
							if (msg.isWaitingOutput) {
								msg.isWaitingOutput = false
							}
							msg.content = msg.content + content
						},

						onToolCall: (data) => {
							this.handleToolCallEvent(aiMsgId, data)
						},

						onDone: (fullContent) => {
							const msg = this.messages.find(m => m.id === aiMsgId)
							if (msg) {
								// 构建最终片段
								const finalSegments = []

								if (msg.streamSegments && msg.streamSegments.length > 0) {
									for (const seg of msg.streamSegments) {
										if (seg.type === 'tool') {
											const tc = this.activeToolCalls.find(t => t.id === seg.toolCall.id)
											finalSegments.push({
												type: 'tool',
												toolCall: tc ? { ...tc } : { ...seg.toolCall }
											})
										} else {
											finalSegments.push({ ...seg })
										}
									}
									if (msg.content && msg.content.length > 0) {
										finalSegments.push({ type: 'text', content: msg.content })
									}
								} else if (fullContent) {
									finalSegments.push({ type: 'text', content: fullContent })
								}

								msg.segments = finalSegments
								msg.content = fullContent
								delete msg.streamSegments
								if (this.activeToolCalls.length > 0) {
									msg.toolCalls = this.activeToolCalls.map(tc => ({ ...tc }))
								}
								msg.isWaitingOutput = false
								msg.isStreaming = false
							}
							this.stopHeightMonitor()
							this.activeToolCalls = []
							this.scrollToLatestMessage()

							// 消息发送成功，标记用户消息为已同步并移除本地缓存
							if (pendingId && this.conversationId) {
								const userMsg = this.messages.find(m => m.pendingId === pendingId)
								if (userMsg) {
									userMsg.synced = true
								}
								removePendingMessage(this.conversationId, pendingId)
							}
						},

						onError: (message) => {
							// 后台断连时不标记失败（后台监控会处理）
							if (this.isBackgroundMonitorActive()) return

							uni.showToast({ title: message || 'AI回复失败', icon: 'none' })
							this.messages[msgIndex].isWaitingOutput = false
							this.messages[msgIndex].isStreaming = false
							this.messages[msgIndex].content = this.messages[msgIndex].content || '（回复失败）'
							this.stopHeightMonitor()
							if (pendingId) {
								const userMsg = this.messages.find(m => m.pendingId === pendingId)
								if (userMsg) {
									userMsg.isFailed = true
								}
							}
						},

						onComplete: () => {
							// 兜底：如果 onDone 未触发，标记用户消息为失败
							const aiMsg = this.messages[msgIndex]
							if (aiMsg && aiMsg.isStreaming) {
								// 后台断连时不标记失败（后台监控会处理）
								if (this.isBackgroundMonitorActive()) {
									this.cancelSSE = null
									return
								}

								aiMsg.isStreaming = false
								aiMsg.isWaitingOutput = false
								aiMsg.content = aiMsg.content || '（连接中断）'
								this.stopHeightMonitor()
								if (pendingId) {
									const userMsg = this.messages.find(m => m.pendingId === pendingId)
									if (userMsg) {
										userMsg.isFailed = true
									}
								}
							}
							this.cancelSSE = null
						}
					},
					attachmentIds,
					this.selectedModelId
				)
			},

			resendMessage(msg) {
				if (this.isAiStreaming) return
				this.isAutoScrollEnabled = true

				msg.isFailed = false

				// 移除对应的失败 AI 回复消息
				const msgIdx = this.messages.findIndex(m => m.id === msg.id)
				if (msgIdx >= 0 && msgIdx + 1 < this.messages.length) {
					const nextMsg = this.messages[msgIdx + 1]
					if (nextMsg.role === 'ai' && !nextMsg.isStreaming) {
						this.messages.splice(msgIdx + 1, 1)
					}
				}

				const attachmentIds = (msg.attachments && msg.attachments.length > 0)
					? msg.attachments.map(att => att.id).filter(Boolean)
					: null
				this.sendRealMessage(
					msg.content,
					attachmentIds && attachmentIds.length > 0 ? attachmentIds : null,
					msg.pendingId
				)
			},

			onInputFocus() {
				if (this.isAutoScrollEnabled) {
					this.scrollToLatestMessage()
				}
			},

			onInputBlur() {
				// keyboardHeight 会通过 onKeyboardHeightChange 自动重置
			},

			copyMessage(msg) {
				uni.setClipboardData({
					data: msg.content,
					success() {
						uni.showToast({ title: '已复制', icon: 'success' })
					}
				})
			},


			onScrollToTop() {
				// 预留：加载更多历史消息
			},

			// ========== 问题反馈相关 ==========
			openFeedbackModal(msg) {
				this.feedbackTargetMsg = msg
				this.showFeedbackModal = true
			},

			closeFeedbackModal() {
				this.showFeedbackModal = false
				this.feedbackTargetMsg = null
			},

			async handleFeedbackSubmit(feedbackContent) {
				if (!feedbackContent || !feedbackContent.trim()) {
					return
				}

				try {
					// 收集完整对话数据（包含时间戳）
					const conversationHistory = this.messages.map(msg => ({
						role: msg.role,
						content: msg.content,
						created_at: msg.created_at || new Date().toISOString(),
						toolCalls: msg.toolCalls || null,
						segments: msg.segments || null
					}))

					// Note: message_id 使用服务器端的 UUID，前端本地 ID 不发送
					const serverMsgId = this.feedbackTargetMsg?.serverId || null

					await submitFeedback({
						conversation_id: this.conversationId,
						message_id: serverMsgId,
						chat_mode: 'quick_chat',
						space_name: null,
						feedback_content: feedbackContent.trim(),
						conversation_history: conversationHistory
					})

					this.closeFeedbackModal()
					uni.showToast({ title: '感谢反馈', icon: 'success' })
				} catch (err) {
					uni.showToast({ title: '提交失败，请重试', icon: 'none' })
				}
			},

			/**
			 * 预览消息中的图片（全屏查看）
			 */
			previewMessageImage(url, message) {
				// 收集该消息中所有图片的URL
				const imageUrls = message.attachments
					.filter(att => att.attachment_type === 'image')
					.map(att => att.file_url)

				// 使用 uni.previewImage 预览
				uni.previewImage({
					urls: imageUrls,
					current: url,
					longPressActions: {
						itemList: ['保存图片'],
						success: (data) => {
							if (data.tapIndex === 0) {
								this.saveImage(url)
							}
						}
					}
				})
			},

			/**
			 * 保存图片到相册（可选功能）
			 */
			saveImage(url) {
				uni.showLoading({ title: '保存中...' })
				uni.downloadFile({
					url: url,
					success: (res) => {
						if (res.statusCode === 200) {
							uni.saveImageToPhotosAlbum({
								filePath: res.tempFilePath,
								success: () => {
									uni.hideLoading()
									uni.showToast({ title: '已保存到相册', icon: 'success' })
								},
								fail: () => {
									uni.hideLoading()
									uni.showToast({ title: '保存失败', icon: 'none' })
								}
							})
						}
					},
					fail: () => {
						uni.hideLoading()
						uni.showToast({ title: '下载失败', icon: 'none' })
					}
				})
			}
		}
	}
</script>

<style>
	view, text {
		box-sizing: border-box;
	}

	/* 页面容器 */
	.chat-page {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100vh;
		background-color: rgb(24, 24, 24);
		overflow: hidden;
	}

	/* 顶部导航栏 - 透明悬浮 */
	.chat-nav-bar {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 100;
		padding-top: calc(100vh * 1.5 / 26);
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: calc(100vw / 24);
		padding-right: calc(100vw / 24);
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

	/* 消息区域 */
	.message-area {
		flex: 1;
		padding-top: calc(100vh * 1.5 / 26 + 88rpx);
		padding-bottom: 0;
		width: 100%;
		height: 100vh;
	}

	.message-top-spacer {
		height: 30rpx;
	}

	.message-bottom-spacer {
		height: calc(100vh * 6 / 26);
	}

	/* 消息行 */
	.message-row {
		display: flex;
		flex-direction: column;
		padding: 12rpx calc(100vw / 24);
	}

	.message-row-right {
		align-items: flex-end;
	}

	.message-row-left {
		align-items: flex-start;
	}

	/* 消息气泡 */
	.message-bubble {
		max-width: 98%;
		padding: 20rpx 28rpx;
		border-radius: 28rpx;
		word-break: break-all;
	}

	.user-bubble-row {
		display: flex;
		flex-direction: row;
		align-items: center;
		max-width: 98%;
	}

	.msg-retry-btn {
		width: 40rpx;
		height: 40rpx;
		border-radius: 50%;
		background-color: #FF3B30;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-right: 16rpx;
		flex-shrink: 0;
	}

	.msg-retry-icon {
		width: 24rpx;
		height: 24rpx;
		filter: brightness(0) invert(1);
	}

	.bubble-user {
		background-color: #2d2d2d;
		border-radius: calc(100vh * 1.3 / 26 / 2);
		min-height: calc(100vh * 1.3 / 26);
		padding: 16rpx 28rpx;
		max-width: none;
		min-width: 0;
	}

	.bubble-ai {
		background-color: transparent;
	}

	.message-text {
		font-size: 30rpx;
		color: #ffffff;
		line-height: 1.6;
	}

	/* 图片附件外层容器（在气泡外） */
	.message-attachments-wrapper {
		display: flex;
		max-width: 98%;
		margin-bottom: 8rpx;
	}

	/* 消息附件容器 */
	.message-attachments {
		display: flex;
		flex-wrap: wrap;
		gap: 10rpx;
	}

	.message-attachment-item {
		position: relative;
	}

	/* 消息中的图片 */
	.message-image {
		width: 200rpx;
		height: 200rpx;
		border-radius: 10rpx;
		background-color: #f0f0f0;
	}

	/* 工具调用卡片 */
	.tool-call-card {
		margin: 16rpx 0;
		padding: 20rpx 24rpx;
		background-color: rgba(255, 255, 255, 0.05);
		border-radius: 16rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.tool-call-running {
		border-color: rgba(59, 130, 246, 0.5);
	}

	.tool-call-pending {
		border-color: rgba(251, 191, 36, 0.5);
		background-color: rgba(251, 191, 36, 0.08);
	}

	.tool-call-success {
		border-color: rgba(34, 197, 94, 0.3);
	}

	.tool-call-failed {
		border-color: rgba(239, 68, 68, 0.3);
	}

	.tool-call-header {
		display: flex;
		align-items: center;
		gap: 12rpx;
	}

	.tool-call-icon {
		width: 32rpx;
		height: 32rpx;
		filter: brightness(0) invert(1);
		opacity: 0.8;
	}

	.tool-call-name {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
		flex: 1;
	}

	.tool-call-spinner {
		width: 24rpx;
		height: 24rpx;
		border: 2rpx solid rgba(59, 130, 246, 0.3);
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* ========== 记忆工具行内波浪文字 ========== */
	.memory-tool-inline {
		margin: 8rpx 0;
		max-height: 0;
		opacity: 0;
		overflow: hidden;
		transition: max-height 0.3s ease, opacity 0.3s ease, margin 0.3s ease;
	}

	.memory-tool-active {
		max-height: 60rpx;
		opacity: 1;
	}

	.memory-tool-done {
		max-height: 0;
		opacity: 0;
		margin: 0;
	}

	.memory-tool-text {
		display: inline-block;
		font-size: 26rpx;
		color: #9ca3af;
		background: linear-gradient(
			90deg,
			#6b7280 0%,
			#9ca3af 15%,
			#d1d5db 30%,
			#9ca3af 45%,
			#6b7280 60%,
			#6b7280 100%
		);
		background-size: 300% 100%;
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
		animation: wave-shimmer 2s ease-in-out infinite;
	}

	@keyframes wave-shimmer {
		0% {
			background-position: 100% 0;
		}
		100% {
			background-position: -100% 0;
		}
	}

	.tool-call-status-icon {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) saturate(100%) invert(62%) sepia(93%) saturate(404%) hue-rotate(93deg) brightness(95%) contrast(92%);
	}

	.tool-call-status-failed {
		filter: brightness(0) saturate(100%) invert(42%) sepia(76%) saturate(2178%) hue-rotate(336deg) brightness(98%) contrast(89%);
	}

	/* 确认区域 */
	.tool-confirm-actions {
		margin-top: 16rpx;
		padding-top: 16rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.tool-confirm-info {
		margin-bottom: 16rpx;
	}

	.tool-confirm-text {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.8);
	}

	.tool-confirm-buttons {
		display: flex;
		gap: 16rpx;
	}

	.tool-btn {
		flex: 1;
		height: 72rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 12rpx;
		transition: all 0.15s ease;
	}

	.tool-btn:active {
		transform: scale(0.96);
	}

	.tool-btn-cancel {
		background-color: rgba(255, 255, 255, 0.1);
	}

	.tool-btn-confirm {
		background-color: #3b82f6;
	}

	.tool-btn-text {
		font-size: 28rpx;
		color: #ffffff;
		font-weight: 500;
	}

	/* 执行结果 */
	.tool-call-result {
		margin-top: 12rpx;
		padding-top: 12rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.08);
	}

	.tool-call-result-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.6);
	}

	/* 学习空间列表 */
	.tool-spaces-list {
		margin-top: 16rpx;
	}

	.tool-space-item {
		display: flex;
		align-items: center;
		padding: 16rpx 0;
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.tool-space-item:last-child {
		border-bottom: none;
	}

	.tool-space-color {
		width: 24rpx;
		height: 24rpx;
		border-radius: 6rpx;
		margin-right: 16rpx;
	}

	.tool-space-name {
		flex: 1;
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
	}

	.tool-space-arrow {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(1);
		opacity: 0.5;
	}

	/* AI 消息操作图标 */
	.ai-msg-actions {
		display: flex;
		align-items: center;
		gap: 24rpx;
		margin-top: 12rpx;
	}

	.ai-msg-action-icon {
		width: 32rpx;
		height: 32rpx;
		opacity: 1;
		filter: brightness(0) invert(1) brightness(0.75);
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

	/* 停止按钮 - 圆形背景 + 圆角矩形 */
	.stop-btn {
		width: 52rpx;
		height: 52rpx;
		border-radius: 50%;
		background-color: #FFFFFF;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.send-btn-wrapper .stop-btn {
		/* 与发送图标可视尺寸对齐（发送 SVG 本身存在内边距） */
		width: 65rpx;
		height: 65rpx;
	}

	.stop-btn-inner {
		width: 20rpx;
		height: 20rpx;
		border-radius: 4rpx;
		background-color: #000000;
	}

	.send-btn-wrapper .stop-btn-inner {
		width: 24rpx;
		height: 24rpx;
		border-radius: 5rpx;
	}

	/* 发送按钮禁用状态 */
	.send-btn-disabled {
		opacity: 0.3;
	}

	.input-field-wrapper {
		flex: 1;
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

	/* ========== 等待输出加载动画 ========== */
	.typing-indicator {
		display: flex;
		align-items: center;
		gap: 8rpx;
		padding: 8rpx 0;
	}

	.typing-dot {
		width: 12rpx;
		height: 12rpx;
		background-color: rgba(255, 255, 255, 0.5);
		border-radius: 50%;
		animation: typing-bounce 1.4s ease-in-out infinite;
	}

	.typing-dot:nth-child(1) { animation-delay: 0s; }
	.typing-dot:nth-child(2) { animation-delay: 0.2s; }
	.typing-dot:nth-child(3) { animation-delay: 0.4s; }

	@keyframes typing-bounce {
		0%, 60%, 100% {
			transform: translateY(0);
			opacity: 0.5;
		}
		30% {
			transform: translateY(-8rpx);
			opacity: 1;
		}
	}

	/* 待发送附件预览区域 */
	.pending-attachments-area {
		display: flex;
		flex-wrap: wrap;
		gap: 12rpx;
		padding: 16rpx 0;
		background-color: transparent;
		max-height: 400rpx;
		overflow-y: auto;
		width: 100%;
	}

	.attachment-preview-item {
		position: relative;
	}

	/* 图片预览 */
	.attachment-image-preview {
		position: relative;
		width: 160rpx;
		height: 160rpx;
		border-radius: 12rpx;
		overflow: hidden;
		/* 磨砂玻璃效果 */
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
		transition: all 0.2s ease;
	}

	.attachment-image-preview:hover {
		transform: scale(1.05);
		background: rgba(255, 255, 255, 0.12);
		box-shadow: 0 12rpx 48rpx rgba(0, 0, 0, 0.15);
	}

	.attachment-thumbnail {
		width: 100%;
		height: 100%;
		object-fit: cover;
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	/* 文件预览 */
	.attachment-file-preview {
		position: relative;
		display: flex;
		align-items: center;
		gap: 12rpx;
		padding: 16rpx 20rpx;
		border-radius: 12rpx;
		max-width: 500rpx;
		/* 磨砂玻璃效果 */
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
		transition: all 0.2s ease;
	}

	.attachment-file-preview:hover {
		background: rgba(255, 255, 255, 0.12);
		transform: translateY(-2rpx);
		box-shadow: 0 12rpx 48rpx rgba(0, 0, 0, 0.15);
	}

	.attachment-file-preview .file-icon {
		width: 32rpx;
		height: 32rpx;
		flex-shrink: 0;
		filter: brightness(0) invert(1);
		opacity: 0.8;
	}

	.attachment-uploading-item .file-icon {
		width: 48rpx;
		height: 48rpx;
		flex-shrink: 0;
		filter: brightness(0) invert(1);
		opacity: 0.9;
	}

	.attachment-file-preview .file-name {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.9);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* 删除按钮 */
	.attachment-remove-btn {
		position: absolute;
		top: 4rpx;
		right: 4rpx;
		width: 44rpx;
		height: 44rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		background-color: rgba(0, 0, 0, 0.75);
		border-radius: 50%;
		z-index: 10;
		backdrop-filter: blur(4px);
	}

	.remove-icon {
		width: 32rpx;
		height: 32rpx;
		filter: brightness(0) invert(1);
	}

	/* 上传中的文件 */
	.attachment-uploading-item {
		width: 160rpx;
		height: 160rpx;
		border-radius: 12rpx;
		/* 磨砂玻璃效果 */
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1rpx solid rgba(255, 255, 255, 0.15);
		box-shadow: 0 8rpx 32rpx 0 rgba(0, 0, 0, 0.08);
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		padding: 16rpx;
	}

	.uploading-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8rpx;
		width: 100%;
	}

	.uploading-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8rpx;
		width: 100%;
	}

	.attachment-uploading-item .file-name {
		font-size: 22rpx;
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
		font-size: 22rpx;
		color: #FEE2E2;
		text-align: center;
	}

	/* ==================== 模型选择器（输入框上方） ==================== */
	.model-bar {
		display: flex;
		justify-content: flex-end;
		padding: 0 8rpx 6rpx 0;
	}

	.model-selector-btn {
		display: flex;
		align-items: center;
		gap: 8rpx;
		padding: 8rpx 16rpx 8rpx 12rpx;
		background: rgba(255, 255, 255, 0.06);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 999rpx;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.model-selector-btn {
			background: rgba(80, 80, 95, 0.65);
		}
	}

	.model-selector-btn:active {
		background: rgba(255, 255, 255, 0.12);
	}

	.model-selector-icon {
		width: 28rpx;
		height: 28rpx;
		color: rgba(255, 255, 255, 0.5);
		flex-shrink: 0;
	}

	.model-selector-label {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.6);
		white-space: nowrap;
		max-width: 280rpx;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.model-selector-chevron {
		width: 20rpx;
		height: 20rpx;
		color: rgba(255, 255, 255, 0.35);
		flex-shrink: 0;
	}

	/* 模型菜单弹窗 */
	.model-menu-backdrop {
		position: fixed;
		inset: 0;
		z-index: 199;
	}

	.model-menu {
		position: absolute;
		bottom: 100%;
		left: 0;
		right: 0;
		z-index: 200;
		margin-bottom: 8rpx;
		background: rgba(22, 22, 42, 0.96);
		-webkit-backdrop-filter: blur(16px) saturate(180%);
		backdrop-filter: blur(16px) saturate(180%);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 24rpx;
		padding: 8rpx;
		box-shadow: 0 -8rpx 32rpx rgba(0, 0, 0, 0.4);
	}

	.model-menu-item {
		display: flex;
		align-items: center;
		padding: 20rpx 24rpx;
		border-radius: 16rpx;
		transition: background 0.15s ease;
	}

	.model-menu-item:active {
		background: rgba(255, 255, 255, 0.08);
	}

	.model-menu-item-active {
		background: rgba(59, 130, 246, 0.12);
	}

	.model-menu-item-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4rpx;
		min-width: 0;
	}

	.model-menu-item-name {
		font-size: 28rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.9);
	}

	.model-menu-item-active .model-menu-item-name {
		color: #60A5FA;
	}

	.model-menu-item-desc {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.model-menu-check {
		width: 36rpx;
		height: 36rpx;
		color: #60A5FA;
		flex-shrink: 0;
		margin-left: 16rpx;
	}
</style>
