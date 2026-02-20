<template>
	<view class="chat-page">
		<!-- 掌握分胶囊通知 -->
		<u-capsule-toast
			v-for="(item, idx) in masteryNotifications"
			:key="item.id"
			:visible="item.visible"
			:node-name="item.nodeName"
			:change="item.change"
			:index="idx"
			@close="removeMasteryNotification(item.id)"
		/>

		<!-- 顶部导航栏 -->
		<view class="chat-nav-bar">
			<view class="nav-left" @click="goBack">
				<image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
			</view>
			<text class="debug-btn" @click="toggleSseDebugPanel">DBG</text>
			<text class="nav-title">{{ spaceTitle }}</text>
			<view class="nav-right" @click="openSettings">
				<image class="nav-icon" src="/static/icons/phosphor-icons/PNGs/bold/clock-clockwise-bold.png" mode="aspectFit"></image>
			</view>
		</view>

		<!-- 前置知识卡片 -->
		<pre-knowledge-card
			:visible="showPreKnowledgeCard"
			:main-node="preKnowledgeMainNode"
			:child-nodes="preKnowledgeChildNodes"
			:highlighted-labels="preKnowledgeHighlights"
			@close="dismissPreKnowledgeCard"
		/>

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
				v-for="msg in messages"
				:key="msg.id"
				:id="'msg-' + msg.id"
				class="message-row"
				:class="msg.role === 'user' ? 'message-row-right' : 'message-row-left'"
			>
				<!-- 用户消息：图片在气泡外上方 -->
				<template v-if="msg.role === 'user'">
					<!-- 附件容器（独立于气泡外） -->
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
								<!-- 图片附件：可点击预览 -->
								<image
									v-if="att.attachment_type === 'image'"
									:src="att.thumbnail_url || att.file_url"
									mode="aspectFill"
									class="message-image"
									@click="previewMessageImage(att.file_url, msg)"
								></image>

								<!-- 文件附件：显示文件名 -->
								<view v-else class="message-attachment-file">
									<image class="file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit"></image>
									<text class="file-name">{{ att.original_filename }}</text>
								</view>
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

						<!-- AI消息：按片段顺序渲染（支持文本与工具调用交错） -->
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
								<text class="tool-call-name">{{ getToolDisplayName(seg.toolCall.tool) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
								<image
									v-else-if="seg.toolCall.success"
									class="tool-call-status-icon"
									src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg"
									mode="aspectFit"
								></image>
								<image
									v-else
									class="tool-call-status-icon tool-call-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
									mode="aspectFit"
								></image>
							</view>
							<view v-if="seg.toolCall.arguments && Object.keys(seg.toolCall.arguments).length > 0" class="tool-call-args">
								<text class="tool-call-args-text">{{ formatToolArgs(seg.toolCall.arguments) }}</text>
							</view>
							<view v-if="seg.toolCall.result && seg.toolCall.status === 'done'" class="tool-call-result">
								<text class="tool-call-result-text">{{ seg.toolCall.result.message || '操作完成' }}</text>
							</view>
						</view>
					</template>

					<!-- 等待输出加载动画（显示在已有内容之后） -->
					<view v-if="msg.isStreaming && msg.isWaitingOutput" class="typing-indicator">
						<view class="typing-dot"></view>
						<view class="typing-dot"></view>
						<view class="typing-dot"></view>
					</view>

					<!-- 波浪加载文字 (tool-request 且 loading 状态) -->
					<view v-if="msg.type === 'tool-request' && msg.toolState === 'loading'" class="wave-loading-wrapper">
						<text class="wave-loading-text">正在调用生成测试Agent</text>
					</view>

					<!-- 测试题进入卡片 (pending 状态) -->
					<view
						v-if="msg.type === 'tool-request' && msg.toolState === 'pending'"
						class="test-entry-card"
						@click="navigateToTest(msg.id)"
					>
						<view class="test-card-icon-wrapper">
							<image class="test-card-icon" src="/static/icons/phosphor-icons/SVGs/regular/exam.svg" mode="aspectFit"></image>
						</view>
						<view class="test-card-content">
							<text class="test-card-title">测试题已生成</text>
							<text class="test-card-desc">点击进入测试</text>
						</view>
						<view class="test-card-arrow">
							<image class="test-card-arrow-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
						</view>
					</view>

					<!-- AI 消息操作图标 (流式输出完成后显示，排除未完成的工具请求) -->
					<view v-if="msg.role === 'ai' && !msg.isStreaming && (msg.type !== 'tool-request' || msg.toolState === 'accepted' || msg.toolState === 'rejected')" class="ai-msg-actions">
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
						<view class="more-btn-wrapper">
							<image
								class="ai-msg-action-icon"
								src="/static/icons/phosphor-icons/SVGs/regular/dots-three.svg"
								mode="aspectFit"
								@click.stop="toggleMorePopup(msg.id)"
							></image>
							<view class="more-popup" :class="{ 'more-popup-visible': activeMoreMsgId === msg.id }" @click.stop>
								<view class="more-popup-item" @click="addToMemory(msg)">
									<image class="more-popup-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit"></image>
									<text class="more-popup-text">添加到记忆库</text>
								</view>
							</view>
						</view>
					</view>
				</view>
			</template>
		</view>

		<view class="message-bottom-spacer" :style="keyboardHeight > 0 ? { height: 'calc(100vh * 6 / 26 + ' + keyboardHeight + 'px)' } : {}"></view>
		</scroll-view>

		<!-- 弹出菜单遮罩 -->
		<view class="popup-overlay" :class="{ 'popup-overlay-visible': activeMoreMsgId !== null }" @click="closeMorePopup"></view>

		<!-- 底部 Snackbar -->
		<u-snackbar
			:visible="showTestSnackbar"
			:message="snackbarMessage"
			actionText="进入"
			actionIcon="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg"
			:duration="4000"
			@action="handleSnackbarAction"
			@close="showTestSnackbar = false"
		></u-snackbar>

		<!-- 测试题生成进度指示器 -->
		<view
			v-if="isGeneratingQuiz || quizProgressPhase === 'completing'"
			class="quiz-progress-fab"
			:class="{
				'quiz-progress-completing': quizProgressPhase === 'completing',
				'quiz-progress-done': quizProgressPhase === 'done'
			}"
			@click="toggleDebugPanel"
		>
			<!-- SVG 圆环进度条 -->
			<svg class="progress-ring" viewBox="0 0 44 44">
				<circle class="progress-ring-bg" cx="22" cy="22" r="18" fill="none" stroke-width="3" />
				<circle
					class="progress-ring-progress"
					cx="22" cy="22" r="18"
					fill="none" stroke-width="3"
					:stroke-dasharray="progressCircumference"
					:stroke-dashoffset="progressOffset"
				/>
			</svg>

			<!-- 图标容器 -->
			<view class="quiz-progress-icon-wrapper">
				<image
					v-show="quizProgressPhase !== 'done'"
					class="quiz-progress-icon"
					:class="{ 'icon-fade-out': quizProgressPhase === 'completing' }"
					src="/static/icons/phosphor-icons/SVGs/regular/exam.svg"
					mode="aspectFit"
				/>
				<image
					v-show="quizProgressPhase === 'completing' || quizProgressPhase === 'done'"
					class="quiz-progress-check"
					:class="{ 'icon-fade-in': quizProgressPhase === 'completing' || quizProgressPhase === 'done' }"
					src="/static/icons/phosphor-icons/SVGs/regular/check-circle.svg"
					mode="aspectFit"
				/>
			</view>
		</view>

		<!-- 调试2号悬浮按钮 (已隐藏) -->
		<!-- <view class="debug2-fab" @click="toggleDebugToolPanel">
			<image
				class="debug2-fab-icon"
				src="/static/icons/phosphor-icons/SVGs/regular/bug.svg"
				mode="aspectFit"
			></image>
			<view class="debug2-fab-badge">2</view>
		</view> -->

		<!-- 调试面板弹窗 -->
		<view v-if="showDebugPanel" class="debug-panel-overlay" @click="toggleDebugPanel">
			<view class="debug-panel" @click.stop>
				<view class="debug-panel-header">
					<text class="debug-panel-title">LLM 调试日志</text>
					<view class="debug-panel-close" @click="toggleDebugPanel">
						<image
							class="debug-panel-close-icon"
							src="/static/icons/phosphor-icons/SVGs/regular/x.svg"
							mode="aspectFit"
						></image>
					</view>
				</view>

				<scroll-view
					class="debug-panel-content"
					scroll-y
					:scroll-into-view="debugScrollTarget"
				>
					<view v-if="debugLogs.length === 0" class="debug-empty">
						<text class="debug-empty-text">等待 LLM 响应...</text>
					</view>

					<view
						v-for="(log, index) in debugLogs"
						:key="index"
						:id="'debug-log-' + index"
						class="debug-log-item"
						:class="{ 'debug-log-item-loading': log.status === 'calling_llm' }"
					>
						<view class="debug-log-header">
							<text class="debug-log-iteration">迭代 {{ log.iteration }}</text>
							<text v-if="log.status === 'calling_llm'" class="debug-log-status-loading">⏳ 调用中</text>
							<text class="debug-log-time">{{ formatDebugTime(log.timestamp) }}</text>
						</view>
						<view class="debug-log-meta">
							<text class="debug-log-meta-item">工具调用: {{ log.tool_calls_count }}</text>
							<text class="debug-log-meta-item">进度: {{ log.progress }}</text>
							<text v-if="log.finish_reason" class="debug-log-meta-item">结束原因: {{ log.finish_reason }}</text>
						</view>
						<view v-if="log.llm_content" class="debug-log-content" :class="{ 'debug-log-content-loading': log.status === 'calling_llm' }">
							<text class="debug-log-content-text">{{ log.llm_content }}</text>
						</view>
						<view v-else class="debug-log-content debug-log-content-empty">
							<text class="debug-log-content-text">(无文本内容，仅工具调用)</text>
						</view>
					</view>

					<view id="debug-log-bottom"></view>
				</scroll-view>
			</view>
		</view>

		<!-- SSE 诊断面板 -->
		<view v-if="showSseDebugPanel" class="sse-debug-panel">
			<view class="sse-debug-header">
				<text class="sse-debug-title">SSE Diag</text>
				<text class="sse-debug-close" @click="showSseDebugPanel = false">X</text>
			</view>
			<scroll-view scroll-y class="sse-debug-body">
				<text v-if="sseDebugLog.length === 0" class="sse-debug-empty">等待 SSE 事件...</text>
				<text v-for="(log, i) in sseDebugLog" :key="i" class="sse-debug-line">{{ log }}</text>
			</scroll-view>
			<view class="sse-debug-actions">
				<text class="sse-debug-action-btn" @click="debugTriggerNotification">触发假弹窗</text>
				<text class="sse-debug-action-btn" @click="debugReconnectSse">重连SSE</text>
				<text class="sse-debug-action-btn" @click="sseDebugLog = []">清空</text>
			</view>
		</view>

		<!-- 调试2号面板弹窗 -->
		<view v-if="showDebugToolPanel" class="debug2-panel-overlay" @click="toggleDebugToolPanel">
			<view class="debug2-panel" @click.stop>
				<view class="debug2-panel-header">
					<text class="debug2-panel-title">调试2号：工具调用</text>
					<view class="debug2-panel-close" @click="toggleDebugToolPanel">
						<image
							class="debug2-panel-close-icon"
							src="/static/icons/phosphor-icons/SVGs/regular/x.svg"
							mode="aspectFit"
						></image>
					</view>
				</view>

				<view class="debug2-panel-body">
					<text class="debug2-section-title">输入 tool_call JSON</text>
					<textarea
						class="debug2-input"
						v-model="debugToolInput"
						placeholder="粘贴 LLM 实际 tool_call JSON"
						placeholder-class="debug2-input-placeholder"
						:disabled="debugToolLoading"
						:maxlength="-1"
					/>

					<view class="debug2-actions">
						<view class="debug2-btn debug2-btn-secondary" @click="clearDebugToolForm">清空</view>
						<view class="debug2-btn debug2-btn-primary" @click="submitDebugToolCall">
							{{ debugToolLoading ? '执行中...' : '执行' }}
						</view>
					</view>

					<text class="debug2-section-title">原始输出</text>
					<text v-if="debugToolError" class="debug2-error-text">{{ debugToolError }}</text>
					<scroll-view class="debug2-output" scroll-y>
						<text class="debug2-output-text">{{ debugToolOutput || '(无输出)' }}</text>
					</scroll-view>
				</view>
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
	import UCapsuleToast from '@/components/u-capsule-toast/u-capsule-toast.vue'
	import USnackbar from '@/components/u-snackbar/u-snackbar.vue'
	import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
	import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
	import PreKnowledgeCard from '@/components/pre-knowledge-card/pre-knowledge-card.vue'
	import ImageSourcePicker from '@/components/image-source-picker/image-source-picker.vue'
	import { generateQuiz, getTaskStatus, getSpaceGraph } from '@/api/space'
	import { createConversation, getConversation, sendMessage as sendChatMessage, executeToolCall, submitFeedback, submitToolResult } from '@/api/chat'
	import { connectNotificationStream } from '@/api/notification'
	import { executeCalendarTool } from '@/utils/calendar'
	import { uploadAttachment, deleteAttachment } from '@/api/attachment'
	import { PreKnowledgeTagParser } from '@/utils/preKnowledgeParser'
	import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
	import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError } from '@/utils/sse'
	import { savePendingMessage, getPendingMessages, removePendingMessage, savePendingMessagesFromArray, clearPendingMessages } from '@/utils/messageDraft'
	import { startBackgroundMonitor, stopBackgroundMonitor, getActiveMonitor } from '@/utils/backgroundChatMonitor'
	// #ifdef APP-PLUS
	import SseRenderjs from '@/components/sse-renderjs/sse-renderjs.vue'
	// #endif

	// 工具名称映射
	const TOOL_DISPLAY_NAMES = {
		// 知识图谱工具
		get_graph_overview: '获取知识图谱',
		add_node: '添加知识点',
		add_edge: '添加关系',
		delete_node: '删除知识点',
		delete_edge: '删除关系',
		update_mastery: '更新掌握度',
		get_child_nodes: '获取子节点',
		get_parent_nodes: '获取父节点',
		get_sibling_nodes: '获取兄弟节点',
		generate_learning_path: '生成学习路径',
		get_learning_paths: '获取学习路径',
		delete_all_learning_paths: '删除所有路径',
		get_postorder_traversal: '获取后序遍历',
		// 日程管理工具
		get_schedule: '查看日程',
		add_schedule: '添加日程',
		delete_schedule: '删除日程',
		update_schedule: '更新日程',
		// 网络搜索工具
		web_search: '联网搜索',
		web_fetch: '获取网页',
		// RAG 文档搜索
		search_documents: '搜索文档',
		// 测试生成
		generate_test: '生成测试',
		// 长期记忆工具
		write_to_long_term_memory: '写入长期记忆',
		delete_from_long_term_memory: '删除长期记忆',
		// 空间记忆工具
		write_to_space_memory: '写入空间记忆',
		delete_from_space_memory: '删除空间记忆'
	}

	// 工具图标映射
	const TOOL_ICONS = {
		// 知识图谱工具
		get_graph_overview: '/static/icons/phosphor-icons/SVGs/regular/graph.svg',
		add_node: '/static/icons/phosphor-icons/SVGs/regular/plus-circle.svg',
		add_edge: '/static/icons/phosphor-icons/SVGs/regular/git-merge.svg',
		delete_node: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
		delete_edge: '/static/icons/phosphor-icons/SVGs/regular/link-break.svg',
		update_mastery: '/static/icons/phosphor-icons/SVGs/regular/graduation-cap.svg',
		get_child_nodes: '/static/icons/phosphor-icons/SVGs/regular/arrow-down.svg',
		get_parent_nodes: '/static/icons/phosphor-icons/SVGs/regular/arrow-up.svg',
		get_sibling_nodes: '/static/icons/phosphor-icons/SVGs/regular/arrows-left-right.svg',
		generate_learning_path: '/static/icons/phosphor-icons/SVGs/regular/flow-arrow.svg',
		get_learning_paths: '/static/icons/phosphor-icons/SVGs/regular/path.svg',
		delete_all_learning_paths: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
		get_postorder_traversal: '/static/icons/phosphor-icons/SVGs/regular/tree-structure.svg',
		// 日程管理工具
		get_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar.svg',
		add_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-plus.svg',
		delete_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-x.svg',
		update_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-check.svg',
		// 网络搜索工具
		web_search: '/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg',
		web_fetch: '/static/icons/phosphor-icons/SVGs/regular/globe.svg',
		// RAG 文档搜索
		search_documents: '/static/icons/phosphor-icons/SVGs/regular/file-magnifying-glass.svg',
		// 测试生成
		generate_test: '/static/icons/phosphor-icons/SVGs/regular/exam.svg',
		// 长期记忆工具
		write_to_long_term_memory: '/static/icons/phosphor-icons/SVGs/regular/brain.svg',
		delete_from_long_term_memory: '/static/icons/phosphor-icons/SVGs/regular/brain.svg',
		// 空间记忆工具
		write_to_space_memory: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
		delete_from_space_memory: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg'
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
			UCapsuleToast,
			USnackbar,
			UInputModal,
			MarkdownRender,
			PreKnowledgeCard,
			ImageSourcePicker,
			// #ifdef APP-PLUS
			SseRenderjs,
			// #endif
		},

		data() {
			return {
				spaceId: null,
				spaceTitle: '学习空间',
				messages: [],
				inputText: '',
				textareaHeight: 'auto',
				textareaOverflow: 'hidden',
				textareaMaxLines: 4, // 输入框可撑高的最大行数
				textareaLineCount: 1, // 记录 linechange 上报的真实行数（用于非 H5 兜底）
				keyboardHeight: 0,
				nextId: 1,
				activeMoreMsgId: null,

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

				// 初始消息（用于 mounted 后发送）
				pendingInitialMessage: null,
				pendingInitialAttachments: [],

				// 键盘监听回调引用（用于清理）
				keyboardCallback: null,

				// 工具确认相关
				activeToolMsgId: null,
				activeQuizId: null,

				// 组件销毁标记（用于取消异步操作）
				isComponentDestroyed: false,

				// AI 流式回复定时器（用于清理）
				streamInterval: null,

				// 打字机效果缓冲区
				typewriterBuffer: '',
				typewriterTimer: null,
				typewriterMsgId: null,
				typewriterSpeed: 30, // 每字间隔(ms)，可调节

				// 测试题 Snackbar 相关
				showTestSnackbar: false,
				snackbarMessage: '测试题已生成',

				// 调试面板相关
				showDebugPanel: false,
				debugLogs: [],
				isGeneratingQuiz: false,
				debugScrollTarget: '',

				// 测试生成进度指示器
				quizProgressPhase: 'idle',  // 'idle' | 'generating' | 'completing' | 'done'
				quizProgressValue: 0,       // 0-100 进度值

				// 调试2号面板相关
				showDebugToolPanel: false,
				debugToolInput: '',
				debugToolOutput: '',
				debugToolLoading: false,
				debugToolError: '',

				// 记忆工具最短显示时间跟踪
				memoryToolStartTimes: {},    // { toolCallId: timestamp }
				memoryToolDelayedDone: {}, // { toolCallId: true } 延迟隐藏的工具ID

				// +号弹窗相关
				showPlusPopup: false,
				plusPopupVisible: false,
				showImageSourcePicker: false,

				// 对话管理相关
				conversationId: null,
				isLoadingHistory: false,
				cancelSSE: null,
				activeToolCalls: [],
				isSendingMessage: false,

				// 前置知识卡片状态
				showPreKnowledgeCard: false,
				preKnowledgeMainNode: null,
				preKnowledgeChildNodes: [],
				preKnowledgeHighlights: [],
				preKnowledgeParser: null,
				preKnowledgeDismissTimer: null,
				preKnowledgeGraphCache: null,

				// 问题反馈相关
				showFeedbackModal: false,
				feedbackTargetMsg: null,

				// 附件管理
				pendingAttachments: [],  // 已上传待发送的附件列表
				uploadingFiles: [],      // 上传中的文件列表

				// 掌握分通知
				masteryNotifications: [],
				notificationAbort: null,
				notificationIdCounter: 0,

				// SSE 诊断面板
				sseDebugLog: [],
				showSseDebugPanel: false,

				// 后台监控：最后一条用户消息的发送时间
				lastUserMessageTimestamp: null
			}
		},

		computed: {
			isAiStreaming() {
				return this.messages.some(msg => msg.role === 'ai' && msg.isStreaming)
			},
			canSend() {
				return this.inputText.trim().length > 0 || this.pendingAttachments.length > 0
			},
			// 从 debugLogs 提取进度百分比
			calculatedQuizProgress() {
				if (this.debugLogs.length === 0) {
					console.log('[PROGRESS] debugLogs 为空')
					return 0
				}
				const lastLog = this.debugLogs[this.debugLogs.length - 1]
				console.log('[PROGRESS] lastLog:', JSON.stringify(lastLog))
				if (!lastLog.progress) {
					// 如果没有 progress 字段，尝试从 iteration 估算
					const iteration = lastLog.iteration || 0
					const estimated = Math.min(90, iteration * 15)
					console.log('[PROGRESS] 无 progress 字段，从 iteration 估算:', estimated)
					return estimated
				}
				const match = String(lastLog.progress).match(/(\d+)/)
				const result = match ? parseInt(match[1], 10) : 0
				console.log('[PROGRESS] progress:', lastLog.progress, '-> 解析结果:', result)
				return result
			},
			// SVG 圆环周长 (2 * PI * r, r=18)
			progressCircumference() {
				return 2 * Math.PI * 18
			},
			// 圆环偏移量
			progressOffset() {
				const progress = this.calculatedQuizProgress
				return this.progressCircumference - (progress / 100) * this.progressCircumference
			}
		},

		async onLoad(options) {
			if (options.id) {
				this.spaceId = options.id
			}

			if (options.name) {
				try {
					const decodedName = decodeURIComponent(options.name)
					this.spaceTitle = decodedName.slice(0, 100).trim() || '学习空间'
				} catch (e) {
					this.spaceTitle = '学习空间'
				}
			}

			// 如果传入了 conversationId，加载历史消息
			if (options.conversationId) {
				this.conversationId = options.conversationId
				await this.loadConversationHistory()
			} else {
				// 新对话：添加初始欢迎消息（不持久化）
				this.messages.push({
					id: this.nextId++,
					role: 'ai',
					content: `你好！我是你的${this.spaceTitle}学习助手，这些是我能帮你做的事：

📖 **知识问答** — 随时提问，我会优先从你的学习资料中查找答案
🧠 **知识图谱** — 帮你梳理知识结构，追踪每个知识点的掌握程度
🗺️ **学习路径** — 根据你的掌握情况，规划个性化的学习顺序
📝 **练习测试** — 生成选择题、判断题、简答题，检验学习效果
🔍 **联网搜索** — 查找最新资料和权威来源，补充学习内容
📅 **学习日程** — 管理你的学习计划和时间安排
💾 **学习记忆** — 记住你的学习偏好和进度，跨对话持续服务

上传学习资料（PDF、Word等）后，我还能直接从你的资料中查找答案。有什么想学的，直接问我就好！`,
					isWelcome: true
				})
			}

			// 如果有初始消息，保存待发送
			if (options.initialMessage) {
				try {
					this.pendingInitialMessage = decodeURIComponent(options.initialMessage)
				} catch (e) {
					// 解码失败，忽略初始消息
				}
			}

			// 读取 learningSpace 传入的初始附件（优先 key + storage）
			if (options.initialAttachmentKey) {
				try {
					const key = decodeURIComponent(options.initialAttachmentKey)
					const raw = uni.getStorageSync(key)
					if (raw) {
						const parsed = JSON.parse(raw)
						if (Array.isArray(parsed)) {
							this.pendingInitialAttachments = parsed
						}
					}
					uni.removeStorageSync(key)
				} catch (e) {
					console.warn('[spaceChat] parse initialAttachmentKey failed:', e)
				}
			} else if (options.initialAttachmentIds) {
				// 兜底：仅有 IDs 时，构造最小附件对象，保证可发送
				try {
					const ids = decodeURIComponent(options.initialAttachmentIds)
						.split(',')
						.map(s => s.trim())
						.filter(Boolean)
					this.pendingInitialAttachments = ids.map(id => ({
						id,
						attachment_type: 'file',
						original_filename: '附件',
						file_url: '',
						thumbnail_url: ''
					}))
				} catch (e) {
					console.warn('[spaceChat] parse initialAttachmentIds failed:', e)
				}
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
					// Scenario B: 新页面实例（页面销毁后重建），loadConversationHistory 已处理
					clearPendingMessages(this.conversationId)
				}
			}

			// 页面显示时，合并本地缓存的待同步消息（历史加载中不重复 merge）
			if (this.conversationId && !this.isLoadingHistory) {
				this.mergePendingMessages()
			}
		},

		onHide() {
			console.log('[SpaceChat] onHide triggered, isAiStreaming:', this.isAiStreaming,
				'conversationId:', this.conversationId, 'cancelSSE:', !!this.cancelSSE,
				'isSendingMessage:', this.isSendingMessage)
			this._tryStartMonitorOrSave('onHide')
		},

		// navigateBack 时 onHide 不触发，onUnload 才触发
		onUnload() {
			console.log('[SpaceChat] onUnload triggered, isAiStreaming:', this.isAiStreaming,
				'conversationId:', this.conversationId, 'cancelSSE:', !!this.cancelSSE,
				'isSendingMessage:', this.isSendingMessage)
			this._tryStartMonitorOrSave('onUnload')
		},

		mounted() {
			// #ifdef APP-PLUS
			if (this.$refs.sseRenderjs) {
				setSseEventBus(this.$refs.sseRenderjs)
			}
			// #endif

			// 建立通知 SSE 连接
			this.setupNotificationStream()

			this.$nextTick(() => {
				this.adjustTextareaHeight()
				this.scrollToLatestMessage()

				// 组件准备就绪后发送待发送的初始消息
				if (this.pendingInitialAttachments && this.pendingInitialAttachments.length > 0) {
					this.pendingAttachments = [...this.pendingAttachments, ...this.pendingInitialAttachments]
					this.pendingInitialAttachments = []
				}

				if (this.pendingInitialMessage) {
					this.inputText = this.pendingInitialMessage.trim()
					this.pendingInitialMessage = null
				}

				if (this.inputText.trim() || this.pendingAttachments.length > 0) {
					this.sendMessage()
				}
			})

			// 存储回调引用以便清理
			this.keyboardCallback = (res) => {
				this.keyboardHeight = res.height
				if (res.height > 0) {
					this.isAutoScrollEnabled = true
					this.$nextTick(() => {
						this.scrollToLatestMessage()
					})
				}
			}
			uni.onKeyboardHeightChange(this.keyboardCallback)
		},

		beforeDestroy() {
			console.log('[SpaceChat] beforeDestroy triggered, activeMonitor:', !!getActiveMonitor())
			// onHide/onUnload 可能已经启动了监控，作为最后兜底
			this._tryStartMonitorOrSave('beforeDestroy')

			// #ifdef APP-PLUS
			clearSseEventBus()
			// #endif

			// 标记组件销毁（取消异步操作）
			this.isComponentDestroyed = true

			// 清理滚动定时器
			if (this.scrollTimer) {
				clearTimeout(this.scrollTimer)
				this.scrollTimer = null
			}

			// 清理高度监听定时器
			if (this.heightCheckTimer) {
				clearInterval(this.heightCheckTimer)
				this.heightCheckTimer = null
			}

			// 清理流式回复定时器
			if (this.streamInterval) {
				clearInterval(this.streamInterval)
				this.streamInterval = null
			}

			// 清理打字机定时器
			this.stopTypewriter()

			// 清理键盘监听
			if (this.keyboardCallback) {
				uni.offKeyboardHeightChange(this.keyboardCallback)
				this.keyboardCallback = null
			}

			// 清理 SSE 连接
			if (this.cancelSSE) {
				this.cancelSSE()
				this.cancelSSE = null
			}

			// 清理通知 SSE 连接
			if (this.notificationAbort) {
				this.notificationAbort()
				this.notificationAbort = null
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
			// ==================== 后台监控启动 ====================
			_tryStartMonitorOrSave(source) {
				// 已有监控则跳过
				if (getActiveMonitor()) {
					console.log(`[SpaceChat] ${source}: monitor already active, skipping`)
					return
				}
				if (!this.conversationId) return

				// 多重信号判断是否有未完成的 AI 请求：
				// 1. isAiStreaming: AI 消息仍在流式（onError 可能已清除）
				// 2. hasPendingUserMessage: 用户消息未同步（onError 不会修改 synced）
				// 3. cancelSSE: SSE 连接仍存在（renderjs 错误时 onComplete 不触发，不会清 null）
				// 4. isSendingMessage: 发送流程未结束（同上）
				const hasPendingUserMessage = this.messages.some(
					m => m.role === 'user' && m.pendingId && !m.synced
				)
				const hasActiveRequest = this.isAiStreaming || hasPendingUserMessage ||
					this.cancelSSE !== null || this.isSendingMessage

				console.log(`[SpaceChat] ${source}: hasActiveRequest=${hasActiveRequest}`,
					`(streaming=${this.isAiStreaming}, pending=${hasPendingUserMessage},`,
					`cancelSSE=${!!this.cancelSSE}, sending=${this.isSendingMessage})`,
					`lastTs=${this.lastUserMessageTimestamp}`)

				if (hasActiveRequest && this.lastUserMessageTimestamp) {
					console.log(`[SpaceChat] ${source}: starting background monitor`)
					startBackgroundMonitor({
						conversationId: this.conversationId,
						userMessageTimestamp: this.lastUserMessageTimestamp,
						chatMode: 'space_chat',
						spaceId: this.spaceId,
						spaceTitle: this.spaceTitle,
					})
					// 服务器已收到消息，清除本地缓存避免重复
					clearPendingMessages(this.conversationId)
				} else {
					// 无活跃请求时正常保存
					savePendingMessagesFromArray(this.conversationId, this.messages)
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

			// ==================== 掌握分通知 ====================
			debugTriggerNotification() {
				this.notificationIdCounter++
				this.masteryNotifications = [
					...this.masteryNotifications,
					{
						id: this.notificationIdCounter,
						visible: true,
						nodeName: '测试节点',
						change: 5
					}
				]
				this.addSseDebugLog('触发假弹窗')
			},

			removeMasteryNotification(id) {
				this.masteryNotifications = this.masteryNotifications.filter(n => n.id !== id)
			},

			// ==================== SSE 诊断 ====================
			addSseDebugLog(msg) {
				const time = new Date().toLocaleTimeString()
				this.sseDebugLog = [...this.sseDebugLog, `[${time}] ${msg}`]
			},

			toggleSseDebugPanel() {
				this.showSseDebugPanel = !this.showSseDebugPanel
			},

			debugReconnectSse() {
				this.addSseDebugLog('手动重连...')
				if (this.notificationAbort) {
					this.notificationAbort()
					this.notificationAbort = null
				}
				this.setupNotificationStream()
			},

			setupNotificationStream() {
				// #ifdef APP-PLUS
				const hasBus = !!this.$refs.sseRenderjs
				this.addSseDebugLog(`sseEventBus: ${hasBus ? 'YES' : 'NO'}`)
				// #endif

				this.addSseDebugLog('连接 notification SSE...')

				this.notificationAbort = connectNotificationStream({
					onMasteryUpdate: (data) => {
						this.addSseDebugLog(`收到 mastery_update: ${data.node_name} ${data.change > 0 ? '+' : ''}${data.change}`)
						this.notificationIdCounter++
						this.masteryNotifications = [
							...this.masteryNotifications,
							{
								id: this.notificationIdCounter,
								visible: true,
								nodeName: data.node_name,
								change: data.change
							}
						]
					},
					onDebugLog: (msg) => {
						this.addSseDebugLog(msg)
					}
				})
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
					url: `/pages/chatHistory/chatHistory?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceTitle)}`
				})
			},

			// ========== 打字机效果方法 ==========

			/**
			 * 将文本添加到打字机缓冲区
			 * @param {string} msgId - 消息ID
			 * @param {string} text - 要添加的文本
			 */
			appendToTypewriter(msgId, text) {
				// 找到消息并关闭等待输出状态
				const msg = this.messages.find(m => m.id === msgId)
				if (msg && msg.isWaitingOutput) {
					msg.isWaitingOutput = false
				}

				// 如果是新消息或不同消息，重置缓冲区
				if (this.typewriterMsgId !== msgId) {
					this.stopTypewriter()
					this.typewriterMsgId = msgId
					this.typewriterBuffer = ''
				}

				// 添加文本到缓冲区
				this.typewriterBuffer += text

				// 如果定时器未启动，启动它
				if (!this.typewriterTimer) {
					this.startTypewriter()
				}
			},

			/**
			 * 启动打字机定时器
			 */
			startTypewriter() {
				if (this.typewriterTimer) return

				this.typewriterTimer = setInterval(() => {
					if (this.typewriterBuffer.length === 0) {
						// 缓冲区空了，暂停定时器（等待新内容）
						this.pauseTypewriter()
						return
					}

					// 取出一个字符
					const char = this.typewriterBuffer.charAt(0)
					this.typewriterBuffer = this.typewriterBuffer.slice(1)

					// 更新消息内容
					const msg = this.messages.find(m => m.id === this.typewriterMsgId)
					if (msg) {
						msg.content = msg.content + char
					}
				}, this.typewriterSpeed)
			},

			/**
			 * 暂停打字机（缓冲区空时）
			 */
			pauseTypewriter() {
				if (this.typewriterTimer) {
					clearInterval(this.typewriterTimer)
					this.typewriterTimer = null
				}
			},

			/**
			 * 停止并清理打字机
			 */
			stopTypewriter() {
				this.pauseTypewriter()
				this.typewriterBuffer = ''
				this.typewriterMsgId = null
			},

			/**
			 * 强制刷新剩余缓冲区内容（流结束时调用）
			 */
			flushTypewriter() {
				if (this.typewriterBuffer.length > 0 && this.typewriterMsgId) {
					const msg = this.messages.find(m => m.id === this.typewriterMsgId)
					if (msg) {
						msg.content = msg.content + this.typewriterBuffer
					}
				}
				this.stopTypewriter()
			},

			// ========== 打字机效果方法结束 ==========

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
						console.error('[SpaceChat] 选择文件失败:', getPickerErrorMessage(err), err)
						uni.showToast({ title: '选择文件失败', icon: 'none' })
					}
				}
				// #endif
			},

			handleSelectImage() {
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

			previewMessageImage(url, message) {
				const imageUrls = message.attachments
					.filter(att => att.attachment_type === 'image')
					.map(att => att.file_url)

				uni.previewImage({
					urls: imageUrls,
					current: url
				})
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
				this.isSendingMessage = false
				this.stopHeightMonitor()
			},

			// ========== 前置知识卡片方法 ==========

			/**
			 * 处理 <PreKnowledge>label</PreKnowledge> 标签
			 */
			async handlePreKnowledgeTag(nodeLabel) {
				// 清除已有的消失计时器
				if (this.preKnowledgeDismissTimer) {
					clearTimeout(this.preKnowledgeDismissTimer)
					this.preKnowledgeDismissTimer = null
				}

				// 立即显示卡片（loading 状态）
				this.preKnowledgeMainNode = null
				this.preKnowledgeChildNodes = []
				this.preKnowledgeHighlights = []
				this.showPreKnowledgeCard = true

				try {
					// 获取图谱数据（使用缓存或重新获取）
					let graphData = this.preKnowledgeGraphCache
					if (!graphData) {
						graphData = await getSpaceGraph(this.spaceId)
						this.preKnowledgeGraphCache = graphData
					}

					// 找到主知识点
					const mainNode = graphData.nodes.find(n => n.label === nodeLabel)
					if (!mainNode) {
						console.warn('[PreKnowledge] 未找到节点:', nodeLabel)
						this.showPreKnowledgeCard = false
						return
					}

					// 找到一级子节点（只找直接子节点，knowledge_tree 类型）
					const childEdges = graphData.edges.filter(
						e => e.from_node_id === mainNode.id && e.type === 'knowledge_tree'
					)
					const childNodes = childEdges
						.map(e => graphData.nodes.find(n => n.id === e.to_node_id))
						.filter(Boolean)

					// 更新状态
					this.preKnowledgeMainNode = {
						id: mainNode.id,
						label: mainNode.label,
						mastery: mainNode.mastery
					}
					this.preKnowledgeChildNodes = childNodes.map(n => ({
						id: n.id,
						label: n.label,
						mastery: n.mastery
					}))
				} catch (err) {
					console.error('[PreKnowledge] 获取图谱失败:', err)
					this.showPreKnowledgeCard = false
				}
			},

			/**
			 * 处理 <Highlight>label</Highlight> 标签
			 */
			handleHighlightTag(nodeLabel) {
				if (!this.preKnowledgeHighlights.includes(nodeLabel)) {
					this.preKnowledgeHighlights = [...this.preKnowledgeHighlights, nodeLabel]
				}
			},

			/**
			 * 关闭前置知识卡片（带动画）
			 */
			dismissPreKnowledgeCard() {
				// 清除计时器
				if (this.preKnowledgeDismissTimer) {
					clearTimeout(this.preKnowledgeDismissTimer)
					this.preKnowledgeDismissTimer = null
				}

				// 隐藏卡片（组件内部会处理动画）
				this.showPreKnowledgeCard = false

				// 延迟清空数据（等待动画完成）
				setTimeout(() => {
					this.preKnowledgeMainNode = null
					this.preKnowledgeChildNodes = []
					this.preKnowledgeHighlights = []
				}, 300)
			},

			/**
			 * 安排前置知识卡片自动消失（AI 回复结束后 1 秒）
			 */
			schedulePreKnowledgeDismiss() {
				if (this.preKnowledgeDismissTimer) {
					clearTimeout(this.preKnowledgeDismissTimer)
				}
				this.preKnowledgeDismissTimer = setTimeout(() => {
					this.dismissPreKnowledgeCard()
				}, 1000)
			},

			// ========== 滚动控制方法 ==========

			// 滚动到底部（spacer 确保消息底部对齐到倒数3/4格分界线）
			scrollToLatestMessage() {
				if (!this.isAutoScrollEnabled) return
				if (this.messages.length === 0) return

				this.$nextTick(() => {
					// 滚动到最大值（底部），spacer 会确保正确对齐
					this.forceScrollUpdate(99999)
				})
			},

			// 强制触发滚动更新
			forceScrollUpdate(targetScrollTop) {
				this.scrollTopValue = targetScrollTop + 0.1
				this.$nextTick(() => {
					this.scrollTopValue = targetScrollTop
				})
			},

			// 监听滚动事件，检测用户手动滚动
			onScroll(e) {
				const currentScrollTop = e.detail.scrollTop

				if (this.scrollTimer) {
					clearTimeout(this.scrollTimer)
				}

				// 检测向上滚动（用户查看历史）
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

			// 开始监听 AI 消息高度变化
			startHeightMonitor(msgId) {
				this.aiStreamingMsgId = msgId
				this.lastMsgHeight = 0

				this.heightCheckTimer = setInterval(() => {
					this.checkHeightChange()
				}, 100)
			},

			// 停止高度监听
			stopHeightMonitor() {
				if (this.heightCheckTimer) {
					clearInterval(this.heightCheckTimer)
					this.heightCheckTimer = null
				}
				this.aiStreamingMsgId = null
				this.lastMsgHeight = 0
			},

			// 检查消息高度变化（行数增加）
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

			// ========== 后台监控辅助 ==========

			isBackgroundMonitorActive() {
				const monitor = getActiveMonitor()
				return monitor && monitor.conversationId === this.conversationId
			},

			async recoverFromBackground() {
				if (!this.conversationId) return

				this.flushTypewriter()
				this.preKnowledgeParser = null

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
					this.isSendingMessage = false
					this.cancelSSE = null
					this.stopHeightMonitor()
				}
			},

			// ========== 消息发送 ==========

			async sendMessage() {
				const text = this.inputText.trim()
				if (!text && this.pendingAttachments.length === 0) return
				if (this.isSendingMessage) return

				// 恢复自动滚动（用户主动发送消息时）
				this.isAutoScrollEnabled = true
				this.isSendingMessage = true
				this.lastUserMessageTimestamp = Date.now()

				// 收集附件IDs
				const attachmentIds = this.pendingAttachments.map(att => att.id)
				const attachments = [...this.pendingAttachments]

				// 生成待同步消息的唯一标识
				const pendingId = `pending_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

				// 添加用户消息到 UI
				const userMsgId = this.nextId++
				const userMessage = {
					id: userMsgId,
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
				this.pendingAttachments = []  // 清空待发送列表
				this.scrollToLatestMessage()

				// 保存到本地存储，防止请求失败后消息丢失
				// 注意：pendingId 通过闭包捕获，在后续 onDone 回调中使用
				if (this.conversationId) {
					savePendingMessage(this.conversationId, userMessage)
				}

				// 检测是否为 Generate_Test JSON 请求（保留旧逻辑）
				const generateTestRequest = this.parseGenerateTestRequest(text)
				if (generateTestRequest) {
					this.isSendingMessage = false
					this.handleGenerateTestRequest(generateTestRequest)
					return
				}

				// 如果没有对话，先创建
				if (!this.conversationId) {
					try {
						const conv = await createConversation(this.spaceId, text.slice(0, 50))
						this.conversationId = conv.id
						// 新对话创建成功后，保存用户消息到本地存储
						savePendingMessage(this.conversationId, userMessage)
					} catch (err) {
						this.isSendingMessage = false
						userMessage.isFailed = true
						uni.showToast({ title: '创建对话失败', icon: 'none' })
						return
					}
				}

				// 添加 AI 消息占位
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

				// 发送消息并处理 SSE
				this.cancelSSE = sendChatMessage(this.conversationId, text, {
					onTextDelta: (content) => {
						// 初始化前置知识解析器
						if (!this.preKnowledgeParser) {
							this.preKnowledgeParser = new PreKnowledgeTagParser()
						}

						// 解析前置知识标签
						const { cleanText, events } = this.preKnowledgeParser.parse(content)

						// 处理解析事件
						for (const event of events) {
							if (event.type === 'preknowledge') {
								this.handlePreKnowledgeTag(event.payload)
							} else if (event.type === 'highlight') {
								this.handleHighlightTag(event.payload)
							}
						}

						// 使用打字机缓冲区实现均匀逐字输出（使用干净文本）
						if (cleanText) {
							this.appendToTypewriter(aiMsgId, cleanText)
						}
					},

					onToolCall: (data) => {
						this.handleToolCallEvent(aiMsgId, data)
					},

					onClientToolRequest: (data) => {
						this.handleClientToolRequest(aiMsgId, data)
					},

					onDone: (fullContent) => {
						// 先刷新打字机缓冲区中剩余内容
						this.flushTypewriter()

						// 安排前置知识卡片自动消失
						if (this.showPreKnowledgeCard) {
							this.schedulePreKnowledgeDismiss()
						}
						// 重置解析器
						this.preKnowledgeParser = null

						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg) {
							// 构建最终的片段数组（保持文本与工具调用的交错顺序）
							const finalSegments = []

							if (msg.streamSegments && msg.streamSegments.length > 0) {
								// 复制已保存的片段，并更新工具调用状态
								for (const seg of msg.streamSegments) {
									if (seg.type === 'tool') {
										const tc = this.activeToolCalls.find(t => t.id === seg.toolCall.id)
										finalSegments.push({
											type: 'tool',
											toolCall: tc ? {
												...tc,
												arguments: tc.arguments ? { ...tc.arguments } : null,
												result: tc.result ? { ...tc.result } : null
											} : { ...seg.toolCall }
										})
									} else {
										finalSegments.push({ ...seg })
									}
								}
								// 添加最后一个工具调用后的文本（如果有）
								if (msg.content && msg.content.length > 0) {
									finalSegments.push({ type: 'text', content: msg.content })
								}
							} else if (fullContent) {
								// 没有工具调用，纯文本消息
								finalSegments.push({ type: 'text', content: fullContent })
							}

							// 保存最终片段
							msg.segments = finalSegments
							// 保存完整文本用于复制等功能
							msg.content = fullContent
							// 清理流式片段
							delete msg.streamSegments
							// 保存工具调用记录（兼容旧逻辑）
							if (this.activeToolCalls.length > 0) {
								msg.toolCalls = this.activeToolCalls.map(tc => ({
									...tc,
									arguments: tc.arguments ? { ...tc.arguments } : null,
									result: tc.result ? { ...tc.result } : null
								}))
							}
							msg.isWaitingOutput = false
							msg.isStreaming = false
						}
						this.stopHeightMonitor()
						this.activeToolCalls = []
						this.scrollToLatestMessage()

						// 消息发送成功，标记用户消息为已同步并移除本地缓存
						// 使用闭包捕获的 pendingId，避免竞态条件
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

						// 出错时也要清理打字机
						this.flushTypewriter()

						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg) {
							msg.content = msg.content || '请求失败'
							msg.isWaitingOutput = false
							msg.isStreaming = false
							msg.isError = true
						}
						this.stopHeightMonitor()
						uni.showToast({ title: message || '请求失败', icon: 'none' })
						if (pendingId) {
							const userMsg = this.messages.find(m => m.pendingId === pendingId)
							if (userMsg) {
								userMsg.isFailed = true
							}
						}
					},

					onComplete: () => {
						// 安全兜底：如果 onDone 未触发，确保清理流式状态
						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg && msg.isStreaming) {
							// 后台断连时不标记失败（后台监控会处理）
							if (this.isBackgroundMonitorActive()) {
								this.cancelSSE = null
								this.isSendingMessage = false
								return
							}

							console.warn('[SpaceChat] SSE connection closed but message still streaming, forcing end')
							this.flushTypewriter()
							if (this.showPreKnowledgeCard) {
								this.schedulePreKnowledgeDismiss()
							}
							this.preKnowledgeParser = null
							msg.isWaitingOutput = false
							msg.isStreaming = false
							this.stopHeightMonitor()
							this.activeToolCalls = []

							// 若 AI 未生成任何文本（仅有工具卡片），显示断连提示
							const hasText = msg.content && msg.content.trim() !== ''
							const hasTextSegments = msg.streamSegments && msg.streamSegments.some(s => s.type === 'text' && s.content.trim())
							if (!hasText && !hasTextSegments) {
								msg.content = '网络连接中断，AI 未能完成回复。请重新发送消息。'
							}
							// 标记用户消息为失败
							if (pendingId) {
								const userMsg = this.messages.find(m => m.pendingId === pendingId)
								if (userMsg) {
									userMsg.isFailed = true
								}
							}
						}
						// 清理残留 running 状态的工具卡片（标记为超时失败）
						if (this.activeToolCalls.length > 0) {
							for (const tc of this.activeToolCalls) {
								if (tc.status === 'running') {
									tc.status = 'done'
									tc.success = false
									tc.result = '连接已关闭，工具未完成'
								}
							}
							this.activeToolCalls = []
						}
						this.cancelSSE = null
						this.isSendingMessage = false
					}
				}, attachmentIds.length > 0 ? attachmentIds : null)
			},

			async resendMessage(msg) {
				if (this.isAiStreaming || this.isSendingMessage) return

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

				const pendingId = msg.pendingId
				const text = msg.content
				const attachmentIds = (msg.attachments && msg.attachments.length > 0)
					? msg.attachments.map(att => att.id).filter(Boolean)
					: null

				this.isSendingMessage = true

				// 如果没有对话，先创建
				if (!this.conversationId) {
					try {
						const conv = await createConversation(this.spaceId, text.slice(0, 50))
						this.conversationId = conv.id
						savePendingMessage(this.conversationId, msg)
					} catch {
						this.isSendingMessage = false
						msg.isFailed = true
						uni.showToast({ title: '创建对话失败', icon: 'none' })
						return
					}
				}

				// 添加 AI 消息占位并启动 SSE
				const aiMsgId = this.nextId++
				this.messages.push({ id: aiMsgId, role: 'ai', content: '', isStreaming: true, isWaitingOutput: true })
				this.scrollToLatestMessage()
				this.startHeightMonitor(aiMsgId)
				this.activeToolCalls = []

				this.cancelSSE = sendChatMessage(this.conversationId, text, {
					onTextDelta: (content) => {
						if (!this.preKnowledgeParser) {
							this.preKnowledgeParser = new PreKnowledgeTagParser()
						}
						const { cleanText, events } = this.preKnowledgeParser.parse(content)
						for (const event of events) {
							if (event.type === 'preknowledge') this.handlePreKnowledgeTag(event.payload)
							else if (event.type === 'highlight') this.handleHighlightTag(event.payload)
						}
						if (cleanText) this.appendToTypewriter(aiMsgId, cleanText)
					},
					onToolCall: (data) => { this.handleToolCallEvent(aiMsgId, data) },
					onClientToolRequest: (data) => { this.handleClientToolRequest(aiMsgId, data) },
					onDone: (fullContent) => {
						this.flushTypewriter()
						if (this.showPreKnowledgeCard) this.schedulePreKnowledgeDismiss()
						this.preKnowledgeParser = null

						const aiMsg = this.messages.find(m => m.id === aiMsgId)
						if (aiMsg) {
							const finalSegments = []
							if (aiMsg.streamSegments && aiMsg.streamSegments.length > 0) {
								for (const seg of aiMsg.streamSegments) {
									if (seg.type === 'tool') {
										const tc = this.activeToolCalls.find(t => t.id === seg.toolCall.id)
										finalSegments.push({ type: 'tool', toolCall: tc ? { ...tc } : { ...seg.toolCall } })
									} else {
										finalSegments.push({ ...seg })
									}
								}
								if (aiMsg.content && aiMsg.content.length > 0) {
									finalSegments.push({ type: 'text', content: aiMsg.content })
								}
							} else if (fullContent) {
								finalSegments.push({ type: 'text', content: fullContent })
							}
							aiMsg.segments = finalSegments
							aiMsg.content = fullContent
							delete aiMsg.streamSegments
							if (this.activeToolCalls.length > 0) {
								aiMsg.toolCalls = this.activeToolCalls.map(tc => ({ ...tc }))
							}
							aiMsg.isWaitingOutput = false
							aiMsg.isStreaming = false
						}
						this.stopHeightMonitor()
						this.activeToolCalls = []
						this.scrollToLatestMessage()

						if (pendingId && this.conversationId) {
							const userMsg = this.messages.find(m => m.pendingId === pendingId)
							if (userMsg) userMsg.synced = true
							removePendingMessage(this.conversationId, pendingId)
						}
					},
					onError: (message) => {
						this.flushTypewriter()
						const aiMsg = this.messages.find(m => m.id === aiMsgId)
						if (aiMsg) {
							aiMsg.content = aiMsg.content || '请求失败'
							aiMsg.isWaitingOutput = false
							aiMsg.isStreaming = false
							aiMsg.isError = true
						}
						this.stopHeightMonitor()
						uni.showToast({ title: message || '请求失败', icon: 'none' })
						if (pendingId) {
							const userMsg = this.messages.find(m => m.pendingId === pendingId)
							if (userMsg) userMsg.isFailed = true
						}
					},
					onComplete: () => {
						const aiMsg = this.messages.find(m => m.id === aiMsgId)
						if (aiMsg && aiMsg.isStreaming) {
							this.flushTypewriter()
							this.preKnowledgeParser = null
							aiMsg.isWaitingOutput = false
							aiMsg.isStreaming = false
							this.stopHeightMonitor()
							this.activeToolCalls = []
							const hasText = aiMsg.content && aiMsg.content.trim() !== ''
							if (!hasText) {
								aiMsg.content = '网络连接中断，AI 未能完成回复。请重新发送消息。'
							}
							if (pendingId) {
								const userMsg = this.messages.find(m => m.pendingId === pendingId)
								if (userMsg) userMsg.isFailed = true
							}
						}
						this.cancelSSE = null
						this.isSendingMessage = false
					}
				}, attachmentIds && attachmentIds.length > 0 ? attachmentIds : null)
			},

			/**
			 * 加载对话历史消息
			 */
			async loadConversationHistory() {
				this.isLoadingHistory = true
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
					// 后台监控 active 时，服务器数据已包含完整回复，清空缓存避免重复
					const monitor = getActiveMonitor()
					if (monitor && monitor.conversationId === this.conversationId) {
						clearPendingMessages(this.conversationId)
					} else {
						this.mergePendingMessages()
					}
					this.$nextTick(() => this.scrollToLatestMessage())
				} catch (err) {
					uni.showToast({ title: '加载对话失败', icon: 'none' })
					// 加载失败时显示欢迎消息
					this.messages.push({
						id: this.nextId++,
						role: 'ai',
						content: `你好！我是你的${this.spaceTitle}学习助手。`,
						isWelcome: true
					})
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

			/**
			 * 处理工具调用事件（支持文本与工具调用交错显示）
			 */
			handleToolCallEvent(aiMsgId, data) {
				const msg = this.messages.find(m => m.id === aiMsgId)
				if (!msg) return

				const { id, tool, status, success, result, arguments: args } = data

				if (status === 'running' || !status) {
					// 工具开始：关闭等待状态（显示工具卡片）
					if (msg.isWaitingOutput) {
						msg.isWaitingOutput = false
					}

					// 检查是否已存在
					const existing = this.activeToolCalls.find(tc => tc.id === id)
					if (existing) return

					// 先刷新打字机，确保当前文本已更新到 msg.content
					this.flushTypewriter()

					// 初始化片段数组
					if (!msg.streamSegments) {
						msg.streamSegments = []
					}

					// 如果有累积的文本，保存为文本片段
					if (msg.content && msg.content.length > 0) {
						msg.streamSegments.push({ type: 'text', content: msg.content })
						msg.content = ''  // 清空，准备接收后续文本
					}

					// 创建工具调用对象
					const toolCall = { id, tool, arguments: args, status: 'running' }

					// 记忆工具：在创建时就记录开始时间
					if (MEMORY_TOOLS.has(tool)) {
						this.memoryToolStartTimes[id] = Date.now()
					}

					// 添加工具调用片段
					msg.streamSegments.push({ type: 'tool', toolCall })

					// 添加到活动工具调用列表
					this.activeToolCalls.push(toolCall)

				} else if (status === 'done') {
					// 工具完成：重新开启等待状态（等待后续输出）
					msg.isWaitingOutput = true

					// 更新活动工具调用状态
					const toolCall = this.activeToolCalls.find(tc => tc.id === id)
					if (toolCall) {
						toolCall.status = 'done'
						toolCall.success = success
						toolCall.result = result

						// 记忆工具：最短显示1秒
						if (MEMORY_TOOLS.has(tool)) {
							const startTime = this.memoryToolStartTimes[id]
							const elapsed = startTime ? Date.now() - startTime : 1000
							const minDisplayTime = 1000 // 最短显示1秒

							if (elapsed < minDisplayTime) {
								// 添加到延迟隐藏集合（Vue 3 直接赋值即可响应式）
								this.memoryToolDelayedDone[id] = true
								setTimeout(() => {
									delete this.memoryToolDelayedDone[id]
									delete this.memoryToolStartTimes[id]
								}, minDisplayTime - elapsed)
							} else {
								delete this.memoryToolStartTimes[id]
							}
						}

						// 如果是学习路径生成工具完成，通知 learningSpace 页面刷新
						if (tool === 'generate_learning_path' && success) {
							uni.$emit('learningPathUpdated')
						}

						// 如果是测试生成工具完成，启动后台轮询
						if (tool === 'generate_test' && success && result?.task_id) {
							this.handleGenerateTestToolCompletion(aiMsgId, result.task_id)
						}
					}
					// 同步更新 streamSegments 中的工具片段
					if (msg.streamSegments) {
						const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === id)
						if (seg && toolCall) {
							seg.toolCall = { ...toolCall }
						}
					}
				}

				// 触发 UI 更新
				this.$forceUpdate()
			},

			/**
			 * 处理客户端工具请求（日历操作等）
			 * 后端通过 SSE 发送 client_tool_request → 前端执行 → POST 结果回后端
			 */
			async handleClientToolRequest(aiMsgId, data) {
				const { tool_call_id, tool, params } = data

				// 显示工具卡片 (running 状态)
				this.handleToolCallEvent(aiMsgId, {
					id: tool_call_id,
					tool,
					status: 'running',
					arguments: params
				})

				// 执行日历工具
				const calendarResult = await executeCalendarTool(tool, params)

				// POST 结果回后端（带重试）
				const maxRetries = 3
				for (let attempt = 1; attempt <= maxRetries; attempt++) {
					try {
						await submitToolResult(this.conversationId, {
							tool_call_id,
							success: calendarResult.success,
							result: calendarResult.result ? { data: calendarResult.result } : null,
							error: calendarResult.error || null
						})
						break
					} catch (err) {
						console.error(`submitToolResult attempt ${attempt} failed:`, err)
						if (attempt < maxRetries) {
							// 指数退避: 1s, 2s, 4s
							await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt - 1)))
						}
					}
				}

				// 更新工具卡片为完成状态
				this.handleToolCallEvent(aiMsgId, {
					id: tool_call_id,
					tool,
					status: 'done',
					success: calendarResult.success,
					result: calendarResult.result || calendarResult.error
				})
			},

			/**
			 * 获取工具显示名称
			 */
			getToolDisplayName(toolName) {
				return TOOL_DISPLAY_NAMES[toolName] || toolName
			},

			getToolIcon(toolName) {
				return TOOL_ICONS[toolName] || '/static/icons/phosphor-icons/SVGs/regular/graph.svg'
			},

			/**
			 * 获取记忆工具的显示状态（考虑最短显示时间）
			 */
			getMemoryToolDisplayStatus(toolCall) {
				if (!toolCall) return 'running'
				// 如果工具在延迟隐藏集合中，继续显示为 running
				if (this.memoryToolDelayedDone[toolCall.id]) {
					return 'running'
				}
				return toolCall.status
			},

			/**
			 * 判断是否为记忆类工具
			 */
			isMemoryTool(toolName) {
				return MEMORY_TOOLS.has(toolName)
			},

			/**
			 * 获取记忆工具显示文字
			 */
			getMemoryToolText(toolName) {
				return MEMORY_TOOL_TEXT[toolName] || '正在访问记忆…'
			},

			/**
			 * 格式化工具参数显示
			 */
			formatToolArgs(args) {
				if (!args) return ''
				const entries = Object.entries(args)
				if (entries.length === 0) return ''
				return entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')
			},

			/**
			 * 获取消息的渲染片段（支持文本和工具调用交错显示）
			 */
			getMessageSegments(msg) {
				// 流式响应中：使用实时构建的片段
				if (msg.isStreaming) {
					return this.buildStreamingSegments(msg)
				}
				// 流式结束后：使用保存的片段，若无则回退到纯文本
				if (msg.segments && msg.segments.length > 0) {
					return msg.segments
				}
				// 兼容旧数据：纯文本消息
				if (msg.content) {
					return [{ type: 'text', content: msg.content }]
				}
				return []
			},

			/**
			 * 构建流式响应中的片段列表
			 */
			buildStreamingSegments(msg) {
				const segments = []

				// 使用消息的实时片段数组（如果有）
				if (msg.streamSegments && msg.streamSegments.length > 0) {
					for (const seg of msg.streamSegments) {
						if (seg.type === 'tool') {
							// 同步最新的工具调用状态
							const tc = this.activeToolCalls.find(t => t.id === seg.toolCall.id)
							segments.push({ type: 'tool', toolCall: tc ? { ...tc } : { ...seg.toolCall } })
						} else {
							segments.push({ ...seg })
						}
					}
				}

				// 添加当前累积的文本（工具调用后的新文本）
				if (msg.content && msg.content.length > 0) {
					segments.push({ type: 'text', content: msg.content })
				}

				// 如果没有任何片段（纯文本消息刚开始，还没有工具调用）
				if (segments.length === 0 && !msg.streamSegments) {
					// 返回空数组，等待内容累积
				}

				return segments
			},

			/**
			 * 解析 Generate_Test JSON 请求
			 * @param {string} text - 用户输入文本
			 * @returns {Object|null} 解析后的请求对象，或 null（非测试生成请求）
			 */
			parseGenerateTestRequest(text) {
				try {
					const parsed = JSON.parse(text)
					if (parsed && parsed.tool === 'Generate_Test' && parsed.topic && parsed.test_struct) {
						return {
							topic: parsed.topic,
							difficulty_level: parsed.difficulty_level || 'medium',
							test_struct: parsed.test_struct
						}
					}
				} catch (e) {
					// 不是 JSON，忽略
				}
				return null
			},

			/**
			 * 处理测试生成请求（调用后端 API）
			 */
			async handleGenerateTestRequest(request) {
				const aiMsgId = this.nextId++
				let msgIndex = -1

				// 启动测试生成（使用新方法）
				this.startQuizGeneration()

				try {
					// 创建工具消息
					this.messages.push({
						id: aiMsgId,
						role: 'ai',
						content: '',
						type: 'tool-request',
						toolState: 'streaming',
						toolName: '测试生成工具'
					})
					msgIndex = this.messages.length - 1
					this.scrollToLatestMessage()
					this.startHeightMonitor(aiMsgId)

					// Step 1: 流式输出提示文本
					await this.streamText(msgIndex, '正在调用生成测试Sub-Agent……')
					if (this.isComponentDestroyed) return

					// Step 2: 切换到波浪加载状态
					this.messages[msgIndex].toolState = 'loading'

					// Step 3: 调用后端 API
					if (!this.spaceId) {
						throw new Error('学习空间 ID 不存在')
					}

					const response = await generateQuiz(this.spaceId, request)
					if (this.isComponentDestroyed) return

					const taskId = response.task_id
					if (!taskId) {
						throw new Error('未返回任务 ID')
					}

					// Step 4: 轮询任务状态
					const result = await this.pollTaskStatus(taskId, msgIndex)
					if (this.isComponentDestroyed) return

					if (result.status === 'done' && result.quiz_id) {
						// 成功：触发完成动画，然后显示测试卡片和 Snackbar
						await this.triggerCompletionAnimation()
						this.activeQuizId = result.quiz_id
						this.activeToolMsgId = aiMsgId
						this.messages[msgIndex].toolState = 'pending'
						this.messages[msgIndex].quizId = result.quiz_id
						this.showTestEntrySnackbar()
					} else if (result.status === 'failed') {
						// 失败：重置进度指示器状态
						this.quizProgressPhase = 'idle'
						this.messages[msgIndex].toolState = 'rejected'
						this.messages[msgIndex].content =
							this.messages[msgIndex].content + `\n\n生成失败：${result.error_message || '未知错误'}`
					}
				} catch (error) {
					if (this.isComponentDestroyed) return
					console.error('测试生成请求失败:', error)
					// 重置进度指示器状态
					this.quizProgressPhase = 'idle'
					if (msgIndex >= 0 && this.messages[msgIndex]) {
						this.messages[msgIndex].toolState = 'rejected'
						this.messages[msgIndex].content =
							this.messages[msgIndex].content + `\n\n请求失败：${error.message || '网络错误'}`
					}
				} finally {
					this.stopHeightMonitor()
					// isGeneratingQuiz 由 triggerCompletionAnimation 处理（成功时）
					// 失败/异常时在此处理
					if (this.quizProgressPhase !== 'completing' && this.quizProgressPhase !== 'done') {
						this.isGeneratingQuiz = false
					}
					if (!this.isComponentDestroyed) {
						this.scrollToLatestMessage()
					}
				}
			},

			/**
			 * 轮询任务状态
			 * @param {string} taskId - 任务 ID
			 * @param {number} msgIndex - 消息索引（用于更新状态）
			 * @returns {Promise<Object>} 任务结果
			 */
			async pollTaskStatus(taskId, msgIndex) {
				const maxAttempts = 150  // 最多轮询 5 分钟
				const pollInterval = 2000  // 2秒轮询一次
				let attempts = 0

				while (attempts < maxAttempts && !this.isComponentDestroyed) {
					try {
						const result = await getTaskStatus(taskId)

						// 更新调试日志（如果有）
						if (result.debug_logs && result.debug_logs.length > 0) {
							this.updateDebugLogs(result.debug_logs)
						}

						if (result.status === 'done' || result.status === 'failed') {
							return result
						}

						// 继续等待
						await this.delay(pollInterval)
						attempts++
					} catch (error) {
						// 认证错误不重试
						if (error.statusCode === 401 || error.statusCode === 403) {
							return { status: 'failed', error_message: '认证失败，请重新登录' }
						}
						// 网络错误继续重试
						await this.delay(pollInterval)
						attempts++
					}
				}

				// 超时
				return { status: 'failed', error_message: '任务超时' }
			},

			// AI 流式响应模拟
			simulateAIStreamResponse() {
				const aiMsgId = this.nextId++
				const aiMsg = {
					id: aiMsgId,
					role: 'ai',
					content: ''
				}
				this.messages.push(aiMsg)

				// AI 消息创建后立即滚动一次（确保第一行可见）
				this.scrollToLatestMessage()

				// 开始监听高度变化
				this.startHeightMonitor(aiMsgId)

				// 模拟流式输出
				const fullResponse = `这是一条关于${this.spaceTitle}的模拟回复。实际接入API后，这里会显示针对该学习空间的专业回答。这段话会逐字显示，模拟流式输出效果，当内容换行时会自动滚动。`
				let currentIndex = 0

				// 找到消息在数组中的索引（用于响应式更新）
				const msgIndex = this.messages.length - 1

				// 清理上一个定时器（如果存在）
				if (this.streamInterval) {
					clearInterval(this.streamInterval)
				}

				this.streamInterval = setInterval(() => {
					if (this.isComponentDestroyed) {
						clearInterval(this.streamInterval)
						this.streamInterval = null
						return
					}

					if (currentIndex < fullResponse.length) {
						// 直接更新响应式数据，实现真正的逐字显示
						const newContent = this.messages[msgIndex].content + fullResponse[currentIndex]
						this.messages[msgIndex].content = newContent
						currentIndex++
					} else {
						clearInterval(this.streamInterval)
						this.streamInterval = null
						this.stopHeightMonitor()
						this.scrollToLatestMessage()
					}
				}, 50)
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

			toggleMorePopup(msgId) {
				this.activeMoreMsgId = this.activeMoreMsgId === msgId ? null : msgId
			},

			closeMorePopup() {
				this.activeMoreMsgId = null
			},

			addToMemory(msg) {
				this.activeMoreMsgId = null
				uni.showToast({ title: '已添加到记忆库', icon: 'none' })
			},

			onScrollToTop() {
				// 预留：加载更多历史消息
			},

			// ========== 问题反馈方法 ==========
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
						chat_mode: 'space_chat',
						space_name: this.spaceTitle,
						feedback_content: feedbackContent.trim(),
						conversation_history: conversationHistory
					})

					this.closeFeedbackModal()
					uni.showToast({ title: '感谢反馈', icon: 'success' })
				} catch (err) {
					uni.showToast({ title: '提交失败，请重试', icon: 'none' })
				}
			},

			// ========== 调试面板方法 ==========

			toggleDebugPanel() {
				this.showDebugPanel = !this.showDebugPanel
				console.log('[DEBUG] showDebugPanel:', this.showDebugPanel, 'debugLogs:', this.debugLogs.length)
				if (this.showDebugPanel && this.debugLogs.length > 0) {
					// 滚动到最新日志
					this.$nextTick(() => {
						this.debugScrollTarget = 'debug-log-bottom'
					})
				}
			},

			// ========== 调试2号面板方法 ==========

			toggleDebugToolPanel() {
				this.showDebugToolPanel = !this.showDebugToolPanel
			},

			clearDebugToolForm() {
				if (this.debugToolLoading) return
				this.debugToolInput = ''
				this.debugToolOutput = ''
				this.debugToolError = ''
			},

			async submitDebugToolCall() {
				if (this.debugToolLoading) return

				const rawInput = this.debugToolInput.trim()
				if (!rawInput) {
					uni.showToast({ title: '请输入 JSON', icon: 'none' })
					return
				}

				let payload = null
				try {
					payload = JSON.parse(rawInput)
				} catch (e) {
					uni.showToast({ title: 'JSON 格式错误', icon: 'none' })
					return
				}

				if (!this.spaceId) {
					uni.showToast({ title: '学习空间 ID 不存在', icon: 'none' })
					return
				}

				this.debugToolLoading = true
				this.debugToolError = ''
				this.debugToolOutput = ''

				try {
					const result = await executeToolCall(this.spaceId, payload)
					this.debugToolOutput = result?.raw_tool_output || ''
				} catch (err) {
					const message =
						err?.data?.detail?.message ||
						err?.data?.detail ||
						err?.message ||
						'执行失败'
					this.debugToolError = message
				} finally {
					this.debugToolLoading = false
				}
			},

			updateDebugLogs(logs) {
				if (!logs || logs.length === 0) return

				// 检查是否有变化（长度变化或最后一条内容变化）
				const hasLengthChange = logs.length !== this.debugLogs.length
				const lastLog = logs[logs.length - 1]
				const lastStoredLog = this.debugLogs[this.debugLogs.length - 1]
				const hasContentChange = !lastStoredLog ||
					lastLog.status !== lastStoredLog.status ||
					lastLog.llm_content !== lastStoredLog.llm_content

				if (hasLengthChange || hasContentChange) {
					this.debugLogs = [...logs]
					// 如果面板打开，滚动到最新
					if (this.showDebugPanel && hasLengthChange) {
						this.$nextTick(() => {
							this.debugScrollTarget = ''
							setTimeout(() => {
								this.debugScrollTarget = 'debug-log-bottom'
							}, 50)
						})
					}
				}
			},

			formatDebugTime(timestamp) {
				if (!timestamp) return ''
				try {
					const date = new Date(timestamp)
					return date.toLocaleTimeString('zh-CN', {
						hour: '2-digit',
						minute: '2-digit',
						second: '2-digit'
					})
				} catch (e) {
					return timestamp
				}
			},

			// ========== 测试生成流程 ==========

			// 延时辅助方法
			delay(ms) {
				return new Promise(resolve => setTimeout(resolve, ms))
			},

			// 流式文本输出辅助方法
			async streamText(msgIndex, text) {
				for (let i = 0; i < text.length; i++) {
					// 组件销毁时提前退出
					if (this.isComponentDestroyed) return
					// 防御性检查：确保消息仍然存在
					if (!this.messages[msgIndex]) return

					const newContent = this.messages[msgIndex].content + text[i]
					this.messages[msgIndex].content = newContent
					await this.delay(50)
				}
			},

			/**
			 * 测试生成流程模拟
			 *
			 * Tool Request State Machine:
			 *   streaming ──> loading ──> pending ──> accepted
			 *                                │
			 *                                └──────> rejected
			 */
			async simulateTestGenerationFlow() {
				const aiMsgId = this.nextId++
				let msgIndex = -1

				try {
					this.messages.push({
						id: aiMsgId,
						role: 'ai',
						content: '',
						type: 'tool-request',
						toolState: 'streaming',
						toolName: '测试生成工具'
					})

					msgIndex = this.messages.length - 1
					this.scrollToLatestMessage()

					// 开始监听高度变化
					this.startHeightMonitor(aiMsgId)

					// Step 1: 逐字流式输出
					await this.streamText(msgIndex, '正在模拟调用生成测试Sub-Agent……')

					// 检查组件是否已销毁
					if (this.isComponentDestroyed) return

					// Step 2: 切换到波浪加载状态
					this.messages[msgIndex].toolState = 'loading'

					// Step 3: 等待 3 秒
					await this.delay(3000)

					// 再次检查组件是否已销毁
					if (this.isComponentDestroyed) return

					// Step 4: 显示测试题进入卡片 + 弹出 snackbar
					this.messages[msgIndex].toolState = 'pending'
					this.activeToolMsgId = aiMsgId
					this.showTestEntrySnackbar()
				} finally {
					this.stopHeightMonitor()
					if (!this.isComponentDestroyed) {
						this.scrollToLatestMessage()
					}
				}
			},

			// ========== 测试生成进度指示器方法 ==========

			// 开始生成测试题
			startQuizGeneration() {
				this.isGeneratingQuiz = true
				this.debugLogs = []
				this.quizProgressPhase = 'generating'
				this.quizProgressValue = 0
			},

			// 触发完成动画
			async triggerCompletionAnimation() {
				this.quizProgressValue = 100
				this.quizProgressPhase = 'completing'
				await this.delay(600)
				this.quizProgressPhase = 'done'
				await this.delay(1200)
				this.isGeneratingQuiz = false
				this.quizProgressPhase = 'idle'
				this.quizProgressValue = 0
			},

			// ========== 测试生成进度指示器方法结束 ==========

			// 显示测试题进入 Snackbar
			showTestEntrySnackbar() {
				this.snackbarMessage = '测试题已生成'
				this.showTestSnackbar = true
			},

			// 跳转到测试页面
			navigateToTest(msgId) {
				// 从消息中获取 quizId
				const msg = this.messages.find(m => m.id === msgId)
				const quizId = msg?.quizId || this.activeQuizId

				if (quizId) {
					uni.navigateTo({
						url: `/pages/test/test?quizId=${quizId}`
					})
				} else {
					// 兼容模拟模式
					uni.navigateTo({
						url: `/pages/test/test?msgId=${msgId}`
					})
				}
			},

			// Snackbar 操作按钮点击
			handleSnackbarAction() {
				this.showTestSnackbar = false
				if (this.activeToolMsgId) {
					this.navigateToTest(this.activeToolMsgId)
				}
			},

			/**
			 * 处理 AI 工具调用 generate_test 完成后的轮询和卡片显示
			 * @param {number} aiMsgId - AI 消息 ID
			 * @param {string} taskId - 后台任务 ID
			 */
			async handleGenerateTestToolCompletion(aiMsgId, taskId) {
				// 找到消息索引
				const msgIndex = this.messages.findIndex(m => m.id === aiMsgId)
				if (msgIndex < 0) return

				// 启用调试模式（显示调试按钮）- 使用统一方法
				this.startQuizGeneration()

				try {
					// 轮询任务状态
					const result = await this.pollTaskStatus(taskId, msgIndex)
					if (this.isComponentDestroyed) return

					if (result.status === 'done' && result.quiz_id) {
						// 成功：设置消息类型和状态以显示测试卡片
						this.activeQuizId = result.quiz_id
						this.activeToolMsgId = aiMsgId
						this.messages[msgIndex].type = 'tool-request'
						this.messages[msgIndex].toolState = 'pending'
						this.messages[msgIndex].quizId = result.quiz_id

						// 触发完成动画并显示 Snackbar 通知
						await this.triggerCompletionAnimation()
						this.showTestEntrySnackbar()
					} else if (result.status === 'failed') {
						// 失败：在消息内容后追加错误信息
						const currentContent = this.messages[msgIndex].content || ''
						this.messages[msgIndex].content =
							currentContent + `\n\n测试生成失败：${result.error_message || '未知错误'}`
					}
				} catch (error) {
					console.error('测试生成轮询失败:', error)
					if (msgIndex >= 0 && this.messages[msgIndex]) {
						const currentContent = this.messages[msgIndex].content || ''
						this.messages[msgIndex].content =
							currentContent + `\n\n轮询失败：${error.message || '网络错误'}`
					}
				} finally {
					// isGeneratingQuiz 由 triggerCompletionAnimation 处理（成功时）
					if (this.quizProgressPhase !== 'completing' && this.quizProgressPhase !== 'done') {
						this.isGeneratingQuiz = false
						this.quizProgressPhase = 'idle'
					}
					if (!this.isComponentDestroyed) {
						this.scrollToLatestMessage()
					}
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

	.debug-btn {
		font-size: 22rpx;
		color: #F59E0B;
		padding: 8rpx 16rpx;
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
		max-width: 60%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
		/* 补偿输入框遮挡 + 对齐到倒数3/4格分界线 */
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

	/* 头像 */
	.avatar-wrapper {
		flex-shrink: 0;
		margin-right: 16rpx;
	}

	.avatar {
		width: 64rpx;
		height: 64rpx;
		border-radius: 50%;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.avatar-ai {
		background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
	}

	.avatar-text {
		font-size: 22rpx;
		color: #ffffff;
		font-weight: 600;
	}

	/* 消息气泡 */
	.message-bubble {
		max-width: 98%;
		padding: 20rpx 28rpx;
		border-radius: 28rpx;
		word-break: break-all;
		display: flex;
		flex-direction: column;
		gap: 8rpx;
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

	/* 三个点按钮容器 */
	.more-btn-wrapper {
		position: relative;
		overflow: visible;
	}

	/* 弹出卡片 */
	.more-popup {
		position: absolute;
		bottom: calc(100% + 12rpx);
		left: 0;
		min-width: 280rpx;
		background-color: #2a2a2a;
		border-radius: 16rpx;
		padding: 0;
		z-index: 200;
		box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.5);
		opacity: 0;
		transform: scale(0.85) translateY(8rpx);
		pointer-events: none;
		transition: opacity 0.2s ease, transform 0.2s ease;
		transform-origin: bottom left;
	}

	.more-popup-visible {
		opacity: 1;
		transform: scale(1) translateY(0);
		pointer-events: auto;
	}

	.more-popup-item {
		display: flex;
		align-items: center;
		gap: 16rpx;
		padding: 14rpx 24rpx;
	}

	.more-popup-icon {
		width: 36rpx;
		height: 36rpx;
		filter: brightness(0) invert(1);
		flex-shrink: 0;
	}

	.more-popup-text {
		font-size: 28rpx;
		color: #ffffff;
		white-space: nowrap;
	}

	/* 透明遮罩 */
	.popup-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 150;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.15s ease;
	}

	.popup-overlay-visible {
		pointer-events: auto;
		opacity: 1;
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

	/* ========== 波浪加载动画 ========== */
	.wave-loading-wrapper {
		margin-top: 16rpx;
	}

	.wave-loading-text {
		font-size: 26rpx;
		color: #9ca3af; /* Fallback color for unsupported platforms */
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
		-webkit-text-fill-color: transparent; /* Better Safari support */
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

	/* ========== 测试题进入卡片 ========== */
	.test-entry-card {
		margin-top: 20rpx;
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.12);
		border-radius: 20rpx;
		padding: 24rpx;
		-webkit-backdrop-filter: blur(20px);
		backdrop-filter: blur(20px);
		display: flex;
		align-items: center;
		gap: 20rpx;
		transition: all 0.15s ease;
	}

	.test-entry-card:active {
		transform: scale(0.98);
		background: rgba(255, 255, 255, 0.12);
	}

	.test-card-icon-wrapper {
		width: 64rpx;
		height: 64rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-shrink: 0;
	}

	.test-card-icon {
		width: 64rpx;
		height: 64rpx;
		filter: brightness(0) invert(1);
	}

	.test-card-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 6rpx;
	}

	.test-card-title {
		font-size: 30rpx;
		color: #ffffff;
		font-weight: 600;
	}

	.test-card-desc {
		font-size: 24rpx;
		color: #9ca3af;
	}

	.test-card-arrow {
		width: 48rpx;
		height: 48rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-shrink: 0;
	}

	.test-card-arrow-icon {
		width: 32rpx;
		height: 32rpx;
		filter: brightness(0) invert(1);
		opacity: 0.6;
	}

	/* ========== 测试题生成进度指示器样式 ========== */

	.quiz-progress-fab {
		position: fixed;
		right: 32rpx;
		bottom: calc(100vh * 4.5 / 26);
		width: 96rpx;
		height: 96rpx;
		border-radius: 50%;
		background: rgba(59, 130, 246, 0.12);
		-webkit-backdrop-filter: blur(20px) saturate(180%);
		backdrop-filter: blur(20px) saturate(180%);
		border: 1rpx solid rgba(59, 130, 246, 0.25);
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 200;
		box-shadow: inset 0 1rpx 2rpx rgba(255,255,255,0.1), 0 4rpx 16rpx rgba(0,0,0,0.3);
		transition: all 0.3s ease;
	}

	.quiz-progress-completing, .quiz-progress-done {
		background: rgba(34, 197, 94, 0.15);
		border-color: rgba(34, 197, 94, 0.35);
	}

	.quiz-progress-done {
		opacity: 0;
		transform: scale(0.8);
		pointer-events: none;
		transition: all 0.5s ease-out;
	}

	/* SVG 进度圆环 */
	.progress-ring {
		position: absolute;
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	.progress-ring-bg { stroke: rgba(255,255,255,0.1); }

	.progress-ring-progress {
		stroke: #3b82f6;
		stroke-linecap: round;
		transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease;
	}

	.quiz-progress-completing .progress-ring-progress,
	.quiz-progress-done .progress-ring-progress {
		stroke: #22c55e;
	}

	/* 图标 */
	.quiz-progress-icon-wrapper {
		position: relative;
		width: 44rpx;
		height: 44rpx;
	}

	.quiz-progress-icon {
		width: 40rpx;
		height: 40rpx;
		filter: brightness(0) saturate(100%) invert(55%) sepia(70%) saturate(2000%) hue-rotate(200deg) brightness(100%) contrast(96%);
		transition: opacity 0.3s ease, transform 0.3s ease;
	}

	.icon-fade-out { opacity: 0; transform: scale(0.5); }

	.quiz-progress-check {
		position: absolute;
		top: 0;
		left: 0;
		width: 44rpx;
		height: 44rpx;
		filter: brightness(0) saturate(100%) invert(65%) sepia(52%) saturate(5000%) hue-rotate(100deg) brightness(95%) contrast(90%);
		opacity: 0;
		transform: scale(0.5);
		transition: opacity 0.3s ease, transform 0.3s ease;
	}

	.icon-fade-in { opacity: 1; transform: scale(1); }

	/* 脉冲动画 */
	.quiz-progress-fab:not(.quiz-progress-done) {
		animation: quiz-pulse 2s ease-in-out infinite;
	}

	@keyframes quiz-pulse {
		0%, 100% { box-shadow: inset 0 1rpx 2rpx rgba(255,255,255,0.1), 0 4rpx 16rpx rgba(0,0,0,0.3), 0 0 0 0 rgba(59,130,246,0.4); }
		50% { box-shadow: inset 0 1rpx 2rpx rgba(255,255,255,0.1), 0 4rpx 16rpx rgba(0,0,0,0.3), 0 0 0 12rpx rgba(59,130,246,0); }
	}

	.quiz-progress-completing {
		animation: completion-pulse 0.5s ease-out;
	}

	@keyframes completion-pulse {
		0% { box-shadow: inset 0 1rpx 2rpx rgba(255,255,255,0.1), 0 4rpx 16rpx rgba(0,0,0,0.3), 0 0 0 0 rgba(34,197,94,0.6); }
		100% { box-shadow: inset 0 1rpx 2rpx rgba(255,255,255,0.1), 0 4rpx 16rpx rgba(0,0,0,0.3), 0 0 0 20rpx rgba(34,197,94,0); }
	}

	/* ========== 调试面板样式 ========== */

	/* 调试面板遮罩 */
	.debug-panel-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 300;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	/* 调试面板 */
	.debug-panel {
		width: 90%;
		max-width: 800rpx;
		min-height: 300rpx;
		max-height: 70vh;
		background: rgba(20, 20, 30, 0.98);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border-radius: 24rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.debug-panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 24rpx 28rpx;
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.1);
		background: rgba(255, 136, 0, 0.1);
	}

	.debug-panel-title {
		font-size: 30rpx;
		font-weight: 600;
		color: #ff8800;
	}

	.debug-panel-close {
		width: 56rpx;
		height: 56rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.08);
	}

	.debug-panel-close-icon {
		width: 32rpx;
		height: 32rpx;
		filter: brightness(0) invert(1);
		opacity: 0.7;
	}

	.debug-panel-content {
		flex: 1;
		padding: 20rpx;
		overflow-y: auto;
	}

	.debug-empty {
		padding: 60rpx 20rpx;
		text-align: center;
	}

	.debug-empty-text {
		font-size: 26rpx;
		color: #666;
	}

	/* 调试日志条目 */
	.debug-log-item {
		background: rgba(255, 255, 255, 0.04);
		border-radius: 16rpx;
		padding: 20rpx;
		margin-bottom: 16rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.debug-log-item-loading {
		border-color: rgba(255, 136, 0, 0.3);
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.7; }
	}

	.debug-log-status-loading {
		font-size: 22rpx;
		color: #ff8800;
		margin-left: 12rpx;
	}

	.debug-log-content-loading {
		color: #ff8800;
	}

	.debug-log-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12rpx;
	}

	.debug-log-iteration {
		font-size: 26rpx;
		font-weight: 600;
		color: #ff8800;
	}

	.debug-log-time {
		font-size: 22rpx;
		color: #666;
	}

	.debug-log-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 16rpx;
		margin-bottom: 12rpx;
	}

	.debug-log-meta-item {
		font-size: 22rpx;
		color: #888;
		background: rgba(255, 255, 255, 0.06);
		padding: 4rpx 12rpx;
		border-radius: 8rpx;
	}

	.debug-log-content {
		background: rgba(0, 0, 0, 0.3);
		border-radius: 12rpx;
		padding: 16rpx;
		max-height: 300rpx;
		overflow-y: auto;
	}

	.debug-log-content-empty {
		opacity: 0.5;
	}

	.debug-log-content-text {
		font-size: 24rpx;
		color: #ccc;
		line-height: 1.5;
		word-break: break-all;
		white-space: pre-wrap;
	}

	/* ========== 调试2号面板样式 ========== */

	.debug2-fab {
		position: fixed;
		right: 32rpx;
		bottom: calc(100vh * 6 / 26);
		width: 88rpx;
		height: 88rpx;
		border-radius: 50%;
		background: rgba(59, 130, 246, 0.16);
		-webkit-backdrop-filter: blur(20px) saturate(180%);
		backdrop-filter: blur(20px) saturate(180%);
		border: 1rpx solid rgba(59, 130, 246, 0.35);
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 210;
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.1),
			0 4rpx 16rpx rgba(0, 0, 0, 0.3);
	}

	.debug2-fab-icon {
		width: 44rpx;
		height: 44rpx;
		filter: brightness(0) saturate(100%) invert(66%) sepia(36%) saturate(2540%) hue-rotate(197deg) brightness(97%) contrast(96%);
	}

	.debug2-fab-badge {
		position: absolute;
		top: -4rpx;
		right: -4rpx;
		min-width: 36rpx;
		height: 36rpx;
		padding: 0 8rpx;
		border-radius: 18rpx;
		background: #3b82f6;
		color: #ffffff;
		font-size: 22rpx;
		font-weight: 600;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.debug2-panel-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.55);
		z-index: 320;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.debug2-panel {
		width: 92%;
		max-width: 720rpx;
		max-height: 78vh;
		background: rgba(16, 18, 28, 0.96);
		-webkit-backdrop-filter: blur(40px) saturate(180%);
		backdrop-filter: blur(40px) saturate(180%);
		border-radius: 24rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.debug2-panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 24rpx 28rpx;
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
		background: rgba(59, 130, 246, 0.12);
	}

	.debug2-panel-title {
		font-size: 30rpx;
		font-weight: 600;
		color: #60a5fa;
	}

	.debug2-panel-close {
		width: 56rpx;
		height: 56rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.08);
	}

	.debug2-panel-close-icon {
		width: 32rpx;
		height: 32rpx;
		filter: brightness(0) invert(1);
		opacity: 0.7;
	}

	.debug2-panel-body {
		padding: 24rpx;
		display: flex;
		flex-direction: column;
		gap: 16rpx;
	}

	.debug2-section-title {
		font-size: 24rpx;
		color: #a5b4fc;
		font-weight: 500;
	}

	.debug2-input {
		width: 100%;
		min-height: 180rpx;
		padding: 16rpx;
		border-radius: 16rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		color: #ffffff;
		font-size: 24rpx;
		line-height: 1.5;
	}

	.debug2-input-placeholder {
		color: rgba(255, 255, 255, 0.4);
		font-size: 24rpx;
	}

	.debug2-actions {
		display: flex;
		justify-content: flex-end;
		gap: 16rpx;
	}

	.debug2-btn {
		min-width: 120rpx;
		padding: 14rpx 22rpx;
		border-radius: 999rpx;
		text-align: center;
		font-size: 24rpx;
	}

	.debug2-btn-secondary {
		background: rgba(255, 255, 255, 0.08);
		color: #d1d5db;
		border: 1rpx solid rgba(255, 255, 255, 0.12);
	}

	.debug2-btn-primary {
		background: rgba(59, 130, 246, 0.9);
		color: #ffffff;
		border: 1rpx solid rgba(59, 130, 246, 0.9);
	}

	.debug2-error-text {
		color: #f87171;
		font-size: 22rpx;
	}

	.debug2-output {
		background: rgba(0, 0, 0, 0.35);
		border-radius: 16rpx;
		padding: 16rpx;
		max-height: 280rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.08);
	}

	.debug2-output-text {
		font-size: 22rpx;
		color: #e5e7eb;
		line-height: 1.5;
		word-break: break-all;
		white-space: pre-wrap;
		font-family: monospace;
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

	/* ========== 工具调用卡片 ========== */
	.tool-calls-container {
		margin-top: 16rpx;
		display: flex;
		flex-direction: column;
		gap: 12rpx;
		width: 500rpx;
		max-width: 100%;
	}

	.tool-call-card {
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 16rpx;
		padding: 16rpx 20rpx;
		transition: all 0.2s ease;
		width: 500rpx;
		max-width: 100%;
	}

	.tool-call-running {
		border-color: rgba(59, 130, 246, 0.4);
		background: rgba(59, 130, 246, 0.08);
	}

	.tool-call-success {
		border-color: rgba(34, 197, 94, 0.3);
		background: rgba(34, 197, 94, 0.06);
	}

	.tool-call-failed {
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(239, 68, 68, 0.06);
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
		flex-shrink: 0;
	}

	.tool-call-name {
		flex: 1;
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
	}

	.tool-call-spinner {
		width: 24rpx;
		height: 24rpx;
		border: 2rpx solid rgba(59, 130, 246, 0.3);
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: tool-spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	@keyframes tool-spin {
		to {
			transform: rotate(360deg);
		}
	}

	.tool-call-status-icon {
		width: 28rpx;
		height: 28rpx;
		flex-shrink: 0;
	}

	.tool-call-status-icon:not(.tool-call-status-failed) {
		filter: brightness(0) saturate(100%) invert(65%) sepia(52%) saturate(5765%) hue-rotate(108deg) brightness(92%) contrast(87%);
	}

	.tool-call-status-failed {
		filter: brightness(0) saturate(100%) invert(39%) sepia(87%) saturate(2345%) hue-rotate(338deg) brightness(96%) contrast(93%);
	}

	.tool-call-args {
		margin-top: 10rpx;
		padding-top: 10rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.tool-call-args-text {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.5);
		line-height: 1.4;
		word-break: break-all;
	}

	.tool-call-result {
		margin-top: 10rpx;
		padding: 10rpx 12rpx;
		background: rgba(34, 197, 94, 0.1);
		border-radius: 8rpx;
	}

	.tool-call-result-text {
		font-size: 22rpx;
		color: rgba(34, 197, 94, 0.9);
		line-height: 1.4;
	}

	.tool-call-failed .tool-call-result {
		background: rgba(239, 68, 68, 0.1);
	}

	.tool-call-failed .tool-call-result-text {
		color: rgba(239, 68, 68, 0.9);
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

	/* ========== 待发送附件预览 ========== */
	.pending-attachments-area {
		display: flex;
		flex-wrap: wrap;
		gap: 12rpx;
		padding: 8rpx 0;
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

	/* ========== 消息中的附件 ========== */
	.message-attachment-file {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		width: 160rpx;
		height: 160rpx;
		padding: 16rpx;
		border-radius: 16rpx;
		background-color: rgba(255, 255, 255, 0.8);
		backdrop-filter: blur(10rpx);
		box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.1);
	}

	.message-attachment-file .file-icon {
		width: 60rpx;
		height: 60rpx;
		margin-bottom: 8rpx;
	}

	.message-attachment-file .file-name {
		font-size: 24rpx;
		color: #333;
		text-align: center;
		word-break: break-all;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		line-height: 1.4;
	}

	/* ========== SSE 诊断面板样式 ========== */
	.sse-debug-panel {
		position: fixed;
		top: 160rpx;
		left: 20rpx;
		right: 20rpx;
		max-height: 500rpx;
		background: rgba(0, 0, 0, 0.92);
		border-radius: 16rpx;
		z-index: 9999;
		padding: 16rpx;
		border: 1rpx solid rgba(245, 158, 11, 0.3);
	}
	.sse-debug-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8rpx;
	}
	.sse-debug-title {
		color: #F59E0B;
		font-size: 28rpx;
		font-weight: bold;
	}
	.sse-debug-close {
		color: #fff;
		font-size: 28rpx;
		padding: 8rpx 16rpx;
	}
	.sse-debug-body {
		max-height: 300rpx;
	}
	.sse-debug-empty {
		color: #666;
		font-size: 22rpx;
	}
	.sse-debug-line {
		color: #22D3EE;
		font-size: 20rpx;
		display: block;
		margin-bottom: 4rpx;
	}
	.sse-debug-actions {
		display: flex;
		gap: 16rpx;
		margin-top: 12rpx;
	}
	.sse-debug-action-btn {
		color: #F59E0B;
		font-size: 24rpx;
		padding: 8rpx 20rpx;
		border: 1px solid #F59E0B;
		border-radius: 8rpx;
	}
</style>
