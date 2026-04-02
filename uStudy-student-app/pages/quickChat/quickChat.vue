<template>
	<view class="chat-page" :class="pageThemeClass">
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
			:scroll-with-animation="scrollAnimationEnabled"
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

					<!-- 用户消息操作图标 -->
					<view v-if="!isAiStreaming" class="user-msg-actions">
						<view class="user-msg-action-btn" @click="copyMessage(msg)">
							<image
								class="user-msg-action-icon"
								src="/static/icons/phosphor-icons/SVGs/regular/copy.svg"
								mode="aspectFit"
							></image>
						</view>
						<view
							v-if="isLastUserMessage(msg)"
							class="user-msg-action-btn"
							@click="editMessage(msg)"
						>
							<image
								class="user-msg-action-icon"
								src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg"
								mode="aspectFit"
							></image>
						</view>
					</view>
				</template>

				<!-- AI消息：保持原有结构 -->
				<template v-else>
					<view class="message-bubble bubble-ai">

						<!-- 思考过程（reasoning 模型） -->
						<view v-if="msg.thinkingContent" class="thinking-section">
							<view class="thinking-header" @click="msg.isThinkingExpanded = !msg.isThinkingExpanded">
								<text class="thinking-label">{{ msg.isStreaming && !msg.content ? '思考中...' : '已思考' + (msg.thinkingDuration ? '（用时 ' + msg.thinkingDuration + ' 秒）' : '') }}</text>
								<image class="thinking-chevron" :class="{ 'thinking-chevron-up': msg.isThinkingExpanded }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
							</view>
							<view class="thinking-body" :class="{ 'thinking-body-collapsed': !msg.isThinkingExpanded }">
								<text class="thinking-text">{{ msg.thinkingContent }}</text>
							</view>
						</view>

						<!-- AI消息：按片段顺序渲染 -->
						<template v-for="(seg, segIdx) in getMessageSegments(msg)">
						<!-- 文本片段（Markdown渲染） -->
						<markdown-render
							v-if="seg.type === 'text' && seg.content && seg.content.trim()"
							:key="'text-' + segIdx"
							:content="seg.content"
							:theme-mode="homeThemeMode"
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

						<!-- 搜索类工具：来源卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isSearchTool(seg.toolCall.tool)"
							:key="'search-tool-' + segIdx"
							class="search-tool-wrap"
						>
							<!-- 指示器 -->
							<view class="search-indicator"
								:class="{
									'search-indicator-running': seg.toolCall.status === 'running',
									'search-indicator-expanded': seg.toolCall.status === 'done' && isSearchExpanded(seg.toolCall.id),
									'search-indicator-collapsed': seg.toolCall.status === 'done' && !isSearchExpanded(seg.toolCall.id)
								}"
								@click="toggleSearchResults(seg.toolCall.id)">
								<image class="search-indicator-globe"
									src="/static/icons/phosphor-icons/SVGs/regular/globe.svg" mode="aspectFit" />
								<text class="search-indicator-text">
									{{ seg.toolCall.status === 'running'
										? (seg.toolCall.display_name || getToolDisplayName(seg.toolCall.tool)) + '...'
										: '已搜索 ' + (seg.toolCall.result?.results?.length || 0) + ' 个来源' }}
								</text>
								<view v-if="seg.toolCall.status === 'running'" class="search-indicator-spinner"></view>
								<image v-else class="search-indicator-chevron"
									:class="{ 'search-chevron-up': isSearchExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
							</view>

							<!-- 来源卡片横向滚动 -->
							<scroll-view
								v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.results?.length && isSearchExpanded(seg.toolCall.id)"
								class="search-sources-scroll" scroll-x :show-scrollbar="false">
								<view class="search-sources-row">
									<view v-for="(item, idx) in seg.toolCall.result.results" :key="idx"
										class="search-source-card" @click="openSearchResultUrl(item.url)">
										<view class="search-source-head">
											<view class="search-source-num">
												<text class="search-source-num-text">{{ idx + 1 }}</text>
											</view>
											<text class="search-source-site">{{ formatDisplayUrl(item.url) }}</text>
										</view>
										<text class="search-source-title">{{ item.title }}</text>
									</view>
								</view>
							</scroll-view>

							<!-- 无结果 -->
							<view v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success && !seg.toolCall.result?.results?.length" class="search-tool-empty">
								<text class="search-tool-empty-text">{{ seg.toolCall.result?.message || '未找到相关结果' }}</text>
							</view>

							<!-- 失败 -->
							<view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="search-tool-error">
								<text class="search-tool-error-text">{{ seg.toolCall.result?.message || '搜索失败' }}</text>
							</view>
						</view>

						<!-- 图表生成工具：pill + 可折叠图片详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'generate_chart'"
							:key="'chart-tool-' + segIdx"
							class="chart-tool-wrap"
							:class="{ 'chart-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isChartExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleChartExpand(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getChartToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isChartExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片：图片预览 -->
							<view v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.image_url && (isChartExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="chart-detail-card"
							>
								<image
									:src="getFullImageUrl(seg.toolCall.result.image_url)"
									mode="widthFix"
									class="chart-preview-img"
									@click="previewChartImage(seg.toolCall.result.image_url)"
								/>
							</view>
						</view>

						<!-- 代码执行工具：pill + 可折叠详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'run_python_code'"
							:key="'code-tool-' + segIdx"
						>
							<PythonExecutionCard :tool-call="seg.toolCall" :theme-mode="homeThemeMode" />
						</view>

						<!-- 学习空间查询工具：胶囊指示器 + 结果卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'view_learning_spaces'"
							:key="'space-query-' + segIdx"
							class="space-query-wrap"
							:class="{ 'space-query-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result && seg.toolCall.result.spaces && seg.toolCall.result.spaces.length && (isSpaceQueryExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- 胶囊指示器（done 状态可点击折叠/展开） -->
							<view class="space-query-pill"
								:class="{
									'space-query-running': seg.toolCall.status === 'running'
								}"
								@click="seg.toolCall.status === 'done' && toggleSpaceQuery(seg.toolCall.id)"
							>
								<image class="space-query-icon"
									src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg"
									mode="aspectFit" />
								<text class="space-query-text">
									{{ seg.toolCall.status === 'running'
										? '正在查询学习空间'
										: '已查询 ' + (seg.toolCall.result && seg.toolCall.result.spaces ? seg.toolCall.result.spaces.length : 0) + ' 个学习空间' }}
								</text>
								<view v-if="seg.toolCall.status === 'running'" class="space-query-spinner"></view>
								<image v-else class="space-query-chevron"
									:class="{ 'space-query-chevron-up': isSpaceQueryExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
									mode="aspectFit" />
							</view>

							<!-- 学习空间结果卡片（可折叠） -->
							<view
								v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result && seg.toolCall.result.spaces && seg.toolCall.result.spaces.length && (isSpaceQueryExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="space-query-results"
							>
								<view class="space-query-results-header">
									<image class="space-query-results-icon" src="/static/icons/lucide/folder-open.svg" mode="aspectFit" />
									<text class="space-query-results-title">找到 {{ seg.toolCall.result.spaces.length }} 个学习空间</text>
								</view>
								<view
									v-for="space in seg.toolCall.result.spaces"
									:key="space.id"
									class="space-query-item"
									@click="handleSpaceClick(space)"
								>
									<view class="space-query-color" :style="{ backgroundColor: space.color }"></view>
									<text class="space-query-name">{{ space.name }}</text>
									<image class="space-query-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
								</view>
							</view>
						</view>

						<!-- 学习空间绑定/创建工具：pill + 确认卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isSpaceMutationTool(seg.toolCall.tool)"
							:key="'space-mut-' + segIdx"
							class="space-mutation-wrap"
							:class="{ 'space-mutation-expanded': seg.toolCall.status === 'pending_confirmation' }"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getSpaceMutationText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 确认卡片 (pending_confirmation 时显示) -->
							<view v-if="seg.toolCall.status === 'pending_confirmation'" class="space-mutation-confirm">
								<text class="space-mutation-confirm-text">{{ getConfirmationText(seg.toolCall) }}</text>
								<view class="space-mutation-confirm-buttons">
									<view class="tool-btn tool-btn-cancel" @click="handleToolReject(msg.id, seg.toolCall)">
										<text class="tool-btn-text">取消</text>
									</view>
									<view class="tool-btn tool-btn-confirm" @click="handleToolConfirm(msg.id, seg.toolCall)">
										<text class="tool-btn-text">确认</text>
									</view>
								</view>
							</view>
						</view>

						<!-- 日程管理工具：统一 pill（所有日程工具共用，get_schedule 额外有详情卡片） -->
						<view
							v-else-if="seg.type === 'tool' && isScheduleTool(seg.toolCall.tool)"
							:key="'schedule-tool-' + segIdx"
							class="schedule-view-wrap"
							:class="{ 'schedule-expanded-container': isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getScheduleToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<!-- 日程详情工具用 chevron（可展开） -->
								<image v-else-if="isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<!-- 其他日程工具用 circle-check -->
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 日程详情卡片（get/add/update_schedule） -->
							<view
								v-if="isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && getScheduleDisplayEvents(seg.toolCall).length && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="schedule-card schedule-card-clickable"
								@click="openNativeCalendar"
							>
								<template v-for="(group, gIdx) in groupScheduleByDate(getScheduleDisplayEvents(seg.toolCall))" :key="'dh-' + gIdx">
									<view class="schedule-date-header">
										<view class="schedule-date-dot" :class="{ 'schedule-date-dot-today': group.isToday }"></view>
										<text class="schedule-date-text" :class="{ 'schedule-date-text-today': group.isToday }">{{ group.label }}</text>
									</view>
									<view
										v-for="(ev, eIdx) in group.events"
										:key="'ev-' + gIdx + '-' + eIdx"
										class="schedule-event-row"
									>
										<view class="schedule-event-time">
											<text class="schedule-event-time-start">{{ ev.startShort }}</text>
											<text class="schedule-event-time-end">{{ ev.endShort }}</text>
										</view>
										<view class="schedule-event-bar" :style="{ background: ev.barColor }"></view>
										<view class="schedule-event-info">
											<text class="schedule-event-title">{{ ev.title }}</text>
											<text v-if="ev.details" class="schedule-event-desc">{{ ev.details }}</text>
										</view>
									</view>
								</template>
								<view v-if="seg.toolCall.tool === 'get_schedule'" class="schedule-card-footer">
									<text class="schedule-card-count">共 {{ getScheduleDisplayEvents(seg.toolCall).length }} 个日程</text>
								</view>
							</view>

							<!-- get_schedule 无日程 -->
							<view
								v-if="seg.toolCall.tool === 'get_schedule' && seg.toolCall.status === 'done' && seg.toolCall.success && !getScheduleDisplayEvents(seg.toolCall).length && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="schedule-card schedule-card-empty"
							>
								<text class="schedule-empty-text">该日期范围内没有日程安排</text>
							</view>
						</view>

						<!-- 复习工具：pill + 可折叠详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isReviewTool(seg.toolCall.tool)"
							:key="'review-tool-' + segIdx"
							class="review-tool-wrap"
							:class="{ 'review-expanded-container': seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getReviewToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<!-- get_review_events: chevron -->
								<image v-else-if="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<!-- mark_review_completed: circle-check -->
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 复习事项详情卡片 -->
							<view
								v-if="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && getReviewDisplayItems(seg.toolCall).length && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="review-card"
							>
								<view v-for="(item, idx) in getReviewDisplayItems(seg.toolCall)" :key="idx" class="review-event-item">
									<view class="review-event-header">
										<text class="review-event-label">{{ item.activity_title }}</text>
										<text v-if="item.study_depth" class="review-event-depth">{{ item.study_depth }}</text>
									</view>
									<view class="review-event-meta">
										<text class="review-event-round">第{{ item.review_number }}次复习</text>
										<view class="review-event-urgency-badge"
											:class="{ 'urgency-overdue': item.overdue_days > 0 }">
											<text class="review-event-urgency-text"
												:class="{ 'urgency-overdue-text': item.overdue_days > 0 }">
												{{ item.urgency }}
											</text>
										</view>
									</view>
								</view>
								<view class="review-card-footer">
									<text class="review-card-count">共 {{ getReviewDisplayItems(seg.toolCall).length }} 条待复习</text>
								</view>
							</view>

							<!-- 无复习项 -->
							<view
								v-if="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && !getReviewDisplayItems(seg.toolCall).length && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
								:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								class="review-card review-card-empty"
							>
								<text class="review-empty-text">当前没有待复习项</text>
							</view>
						</view>

						<!-- 默认工具：pill 胶囊样式 -->
						<view
							v-else-if="seg.type === 'tool'"
							:key="'tool-' + segIdx"
							class="default-tool-wrap"
							:class="{ 'default-tool-expanded': seg.toolCall.status === 'pending_confirmation' }"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ seg.toolCall.display_name || getToolDisplayName(seg.toolCall.tool) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 确认卡片 (pending_confirmation 时展开) -->
							<view v-if="seg.toolCall.status === 'pending_confirmation'" class="space-mutation-confirm">
								<text class="space-mutation-confirm-text">{{ getConfirmationText(seg.toolCall) }}</text>
								<view class="space-mutation-confirm-buttons">
									<view class="tool-btn tool-btn-cancel" @click="handleToolReject(msg.id, seg.toolCall)">
										<text class="tool-btn-text">取消</text>
									</view>
									<view class="tool-btn tool-btn-confirm" @click="handleToolConfirm(msg.id, seg.toolCall)">
										<text class="tool-btn-text">确认</text>
									</view>
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

					<view v-if="msg.responseStatus === 'stopped' && !msg.isStreaming" class="ai-status-badge">
						<text class="ai-status-badge-text">已终止</text>
					</view>

				</view>

				<!-- AI 消息操作图标 (流式输出完成后显示) -->
				<view v-if="msg.role === 'ai' && !msg.isStreaming" class="ai-msg-actions">
					<view class="ai-msg-action-btn copy-btn" @click="copyMessage(msg)">
						<image
							class="ai-msg-action-icon copy-icon-default"
							:class="{ 'copy-icon-hide': msg.copySuccess }"
							src="/static/icons/phosphor-icons/SVGs/regular/copy.svg"
							mode="aspectFit"
						></image>
						<image
							class="ai-msg-action-icon copy-icon-check"
							:class="{ 'copy-icon-show': msg.copySuccess }"
							src="/static/icons/phosphor-icons/SVGs/regular/check.svg"
							mode="aspectFit"
						></image>
					</view>
					<view
						class="ai-msg-action-btn"
						:class="{ 'action-btn-active': msg.userReaction === 'like' }"
						@click="reactToMessage(msg, 'like')"
					>
						<image
							class="ai-msg-action-icon"
							src="/static/icons/phosphor-icons/SVGs/regular/thumbs-up.svg"
							mode="aspectFit"
						></image>
					</view>
					<view
						class="ai-msg-action-btn"
						:class="{ 'action-btn-active': msg.userReaction === 'dislike' }"
						@click="reactToMessage(msg, 'dislike')"
					>
						<image
							class="ai-msg-action-icon"
							src="/static/icons/phosphor-icons/SVGs/regular/thumbs-down.svg"
							mode="aspectFit"
						></image>
					</view>
				</view>
			</template>
		</view>

		<view class="message-bottom-spacer" :style="messageBottomSpacerStyle"></view>
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
					:class="{
						'model-menu-item-active': m.id === selectedModelId,
						'model-menu-item-locked': m.locked
					}"
					@click="selectModel(m.id)"
				>
					<view class="model-menu-accent"></view>
					<view class="model-menu-item-info">
						<text class="model-menu-item-name">{{ m.display_name }}</text>
						<text class="model-menu-item-desc">{{ m.locked ? '升级订阅解锁' : m.description }}</text>
					</view>
					<image v-if="m.locked" class="model-menu-lock" src="/static/icons/phosphor-icons/SVGs/regular/lock.svg" mode="aspectFit"></image>
				</view>
			</view>

			<scroll-view
				v-if="showShortcutPills"
				class="shortcut-pills-scroll"
				scroll-x
				:show-scrollbar="false"
			>
				<view class="shortcut-pills-row">
					<view
						v-for="pill in shortcutPills"
						:key="pill.id"
						class="shortcut-pill"
						@click="handleShortcutPillTap(pill)"
					>
						<image class="shortcut-pill-icon" :src="pill.icon" mode="aspectFit"></image>
						<text class="shortcut-pill-text">{{ pill.label }}</text>
					</view>
				</view>
			</scroll-view>

			<view class="input-drawer-stack" :class="{ 'input-drawer-stack-active': agentTodoLoaded && hasAgentTodos }">
				<view v-if="agentTodoLoaded && hasAgentTodos" class="stacked-agent-drawer">
					<agent-todo-drawer
						:theme-mode="homeThemeMode"
						:items="agentTodos"
						:expanded="agentTodoExpanded"
						:loading-task-ids="agentTodoUpdatingTaskIds"
						@toggle="toggleAgentTodoDrawer"
						@toggle-item="handleAgentTodoToggle"
					/>
				</view>

				<view class="input-card">
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

				<view class="textarea-wrapper">
					<view class="custom-placeholder-row">
						<image class="placeholder-sparkle-icon" src="/static/icons/phosphor-icons/SVGs/fill/sparkle-fill.svg" mode="aspectFit"></image>
						<text
							v-if="!inputText"
							class="placeholder-text"
							:style="{ color: '#A1A1AA', '-webkit-text-fill-color': '#A1A1AA' }"
						>有问题，尽管问</text>
					</view>

					<textarea
						ref="textareaRef"
						class="input-field"
						v-model="inputText"
						placeholder=""
						:focus="inputFocusActive"
						:cursor="inputCursor"
						:maxlength="-1"
						:adjust-position="false"
						confirm-type="send"
						:auto-height="autoHeightEnabled"
						:style="textareaStyle"
						@input="onTextareaInput"
						@linechange="onTextareaLineChange"
						@confirm="sendMessage"
						@focus="onInputFocus"
						@blur="onInputBlur"
					/>
				</view>

				<view class="input-bottom-row">
					<view class="input-bottom-left">
						<!-- 左侧：模型选择 pill -->
						<view v-if="availableModels.length > 0" class="model-selector-btn" @click="toggleModelMenu">
							<image class="model-selector-icon" src="/static/icons/phosphor-icons/SVGs/regular/faders.svg" mode="aspectFit"></image>
							<text class="model-selector-label">{{ selectedModelName }}</text>
							<image class="model-selector-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit"></image>
						</view>
						<!-- 深度思考切换按钮 -->
						<view
							v-if="currentModelSupportsThinking"
							class="thinking-toggle-btn"
							@click="toggleThinking"
						>
							<image class="thinking-toggle-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit"></image>
							<text class="thinking-toggle-label">深度思考</text>
							<view
								class="thinking-toggle-indicator"
								:class="{ 'thinking-toggle-indicator-active': thinkingEnabled }"
							>
								<view
									class="thinking-toggle-indicator-core"
									:class="{ 'thinking-toggle-indicator-core-active': thinkingEnabled }"
								></view>
							</view>
						</view>
					</view>

					<!-- 右侧：操作按钮 -->
					<view class="right-actions">
						<view class="input-action" @click="handlePlusClick">
							<image class="input-action-icon" src="/static/icons/phosphor-icons/SVGs/regular/plus.svg" mode="aspectFit"></image>
						</view>
						<view class="input-action send-btn-wrapper" :class="{ 'send-btn-disabled': !canSend && !isAiStreaming }" @click="handleRightButtonClick">
							<!-- AI正在回复 → 停止按钮 -->
							<view v-if="isAiStreaming" class="stop-btn">
								<view class="stop-btn-inner"></view>
							</view>
							<!-- 可发送 / 禁用状态 → 发送按钮 -->
							<image
								v-else
								class="input-action-icon send-action-icon"
								src="/static/icons/lucide/arrow-up.svg"
								mode="aspectFit"
							></image>
						</view>
					</view>
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
	import config from '@/config/index.js'
	import { getSelectedModelId, setSelectedModelId, getThinkingMode, setThinkingMode } from '@/utils/storage'
	import { getStoredThemeMode } from '@/utils/themeMode'
	import { createQuickChatConversation, sendQuickChatMessage, confirmToolExecution, getConversation, getConversationTodos, updateConversationTodoStatus, submitFeedback, submitToolResult, getModels, getStreamingStatus, rollbackLastMessage, getQuickChatToolTaskStatus, listQuickChatToolTasks, bindQuickChatToolTask, stopStreamingReply } from '@/api/chat'
	import { executeCalendarTool } from '@/utils/calendar'
	import { createCalendarEvent, getCalendarEvents, updateCalendarEvent, deleteCalendarEvent } from '@/api/calendarEvents'
	import { uploadAttachment, deleteAttachment, formatFileSize } from '@/api/attachment'
	import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
	import AgentTodoDrawer from '@/components/agent-todo-drawer/agent-todo-drawer.vue'
	import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
	import ImageSourcePicker from '@/components/image-source-picker/image-source-picker.vue'
	import PythonExecutionCard from '@/components/python-execution-card/python-execution-card.vue'
	import { goBack } from '@/utils/navigation'
	import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
	import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError, connectSSE } from '@/utils/sse'
	import { savePendingMessage, getPendingMessages, removePendingMessage, savePendingMessagesFromArray, clearPendingMessages } from '@/utils/messageDraft'
	import { startBackgroundMonitor, stopBackgroundMonitor, getActiveMonitor } from '@/utils/backgroundChatMonitor'
	import { ensureAlbumWritePermission, ensureCameraPermission, isPermissionDenied, guideToSettings } from '@/utils/permission'
	import { CHAT_PROMPT_PILL_ACTIONS, CHAT_PROMPT_PAGE_KEYS, getChatPromptPills } from '@/config/chatPromptPills.js'
	// #ifdef APP-PLUS
	import SseRenderjs from '@/components/sse-renderjs/sse-renderjs.vue'
	// #endif

	const MAX_MESSAGE_LENGTH = 10000
	const AGENT_TODO_TOOL_NAMES = new Set([
		'create_todo', 'update_todo', 'complete_todo', 'delete_todo'
	])

	const HIDDEN_AGENT_TODO_TOOL_NAMES = new Set([
		'create_todo'
	])

	// 工具名称映射
	const TOOL_DISPLAY_NAMES = {
		view_learning_spaces: '查看学习空间',
		rebind_to_learning_space: '绑定到学习空间',
		create_learning_space: '创建学习空间',
		create_todo: '创建待办',
		update_todo: '更新待办',
		complete_todo: '完成待办',
		delete_todo: '删除待办',
		// 网络搜索工具
		web_search: '联网搜索',
		web_fetch: '获取网页',
		// 多渠道搜索工具
		academic_search: '学术搜索',
		encyclopedia_search: '百科搜索',
		course_search: 'B站课程搜索',
		// 复习事件工具
		get_review_events: '查看复习事件',
		mark_review_completed: '标记复习完成',
		// 图表生成工具
		generate_chart: '生成图表',
		// 代码执行工具
		run_python_code: '执行 Python 代码',
		// 日程管理工具
		get_current_time: '获取当前时间',
		get_schedule: '查看日程',
		add_schedule: '添加日程',
		delete_schedule: '删除日程',
		update_schedule: '更新日程',
		// 知识库管理
		save_to_knowledge_base: '保存到知识库',
		// 深度爬取
		web_crawl: '深度爬取网站'
	}

	// 工具图标映射
	const TOOL_ICONS = {
		view_learning_spaces: '/static/icons/phosphor-icons/SVGs/regular/eye.svg',
		rebind_to_learning_space: '/static/icons/phosphor-icons/SVGs/regular/link.svg',
		create_learning_space: '/static/icons/phosphor-icons/SVGs/regular/plus-circle.svg',
		create_todo: '/static/icons/lucide/list-checks.svg',
		update_todo: '/static/icons/lucide/list-checks.svg',
		complete_todo: '/static/icons/lucide/list-checks.svg',
		delete_todo: '/static/icons/lucide/list-checks.svg',
		// 网络搜索工具
		web_search: '/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg',
		web_fetch: '/static/icons/phosphor-icons/SVGs/regular/globe.svg',
		// 多渠道搜索工具
		academic_search: '/static/icons/phosphor-icons/SVGs/regular/graduation-cap.svg',
		encyclopedia_search: '/static/icons/phosphor-icons/SVGs/regular/books.svg',
		course_search: '/static/icons/phosphor-icons/SVGs/regular/globe.svg',
		// 复习事件工具
		get_review_events: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
		mark_review_completed: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
		// 图表生成工具
		generate_chart: '/static/icons/phosphor-icons/SVGs/regular/image.svg',
		// 代码执行工具
		run_python_code: '/static/icons/phosphor-icons/SVGs/regular/code.svg',
		// 日程管理工具
		get_current_time: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
		get_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar.svg',
		add_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-plus.svg',
		delete_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-x.svg',
		update_schedule: '/static/icons/phosphor-icons/SVGs/regular/calendar-check.svg',
		// 知识库管理
		save_to_knowledge_base: '/static/icons/phosphor-icons/SVGs/regular/bookmark-simple.svg',
		// 深度爬取
		web_crawl: '/static/icons/phosphor-icons/SVGs/regular/globe.svg'
	}

	// 记忆类工具集合（使用行内银光掠过效果）
	const MEMORY_TOOLS = new Set([
		// 旧版工具名
		'write_to_long_term_memory',
		'delete_from_long_term_memory',
		'write_to_space_memory',
		'delete_from_space_memory',
		// 新版向量记忆工具名
		'remember',
		'remember_space',
		'forget',
		'search_memories'
	])

	// 记忆工具显示文字
	const MEMORY_TOOL_TEXT = {
		write_to_long_term_memory: '记忆信息到长期偏好中…',
		remember: '记忆信息到长期偏好中…',
		write_to_space_memory: '记忆信息到学习空间偏好中…',
		remember_space: '记忆信息到学习空间偏好中…',
		search_memories: '查询记忆中…',
		delete_from_long_term_memory: '优化记忆中…',
		delete_from_space_memory: '优化记忆中…',
		forget: '优化记忆中…'
	}

	// 日程管理工具集合
	const SCHEDULE_TOOLS = new Set([
		'get_current_time', 'get_schedule', 'add_schedule', 'delete_schedule', 'update_schedule'
	])

	// 日程工具显示文字 { running, done, failed }
	const SCHEDULE_TOOL_TEXT = {
		get_current_time: { running: '正在获取当前时间…', done: '已获取当前时间', failed: '获取时间失败' },
		get_schedule:     { running: '正在查看日程…',     done: '已查看日程',     failed: '查看日程失败' },
		add_schedule:     { running: '正在添加日程…',     done: '已添加日程',     failed: '添加日程失败' },
		delete_schedule:  { running: '正在删除日程…',     done: '已删除日程',     failed: '删除日程失败' },
		update_schedule:  { running: '正在更新日程…',     done: '已更新日程',     failed: '更新日程失败' }
	}

	// 复习工具集合
	const REVIEW_TOOLS = new Set([
		'get_review_events', 'mark_review_completed'
	])

	// 复习工具显示文字 { running, done, failed }
	const REVIEW_TOOL_TEXT = {
		get_review_events:      { running: '正在查看复习事项…', done: '查看复习事项', failed: '获取复习事项失败' },
		mark_review_completed:  { running: '正在标记复习完成…', done: '已标记复习完成', failed: '标记复习失败' }
	}

	// 创建学习空间异步任务 — 各阶段运行文案
	const CREATE_SPACE_RUNNING_STAGE_TEXT = {
		queued: '创建任务排队中…',
		space_created: '学习空间已创建，正在生成知识图谱…',
		kg_running: '正在生成知识图谱…',
		kg_done: '知识图谱已生成，正在绑定学习空间…',
		binding: '正在绑定学习空间…'
	}
	const CREATE_SPACE_SUCCESS_TEXT = '学习空间已创建并绑定，正在跳转…'

	export default {
		components: {
			MarkdownRender,
			AgentTodoDrawer,
			UInputModal,
			ImageSourcePicker,
			PythonExecutionCard,
			// #ifdef APP-PLUS
			SseRenderjs,
			// #endif
		},
		data() {
			return {
				homeThemeMode: 'dark',
				chatId: '',
				conversationId: null,
				messages: [],
				inputText: '',
				inputFocusActive: false,
				inputCursor: -1,
				textareaHeight: 'auto',
				textareaOverflow: 'hidden',
				textareaMaxLines: 4, // 输入框可撑高的最大行数
				textareaLineCount: 1, // 记录 linechange 上报的真实行数（用于非 H5 兜底）
				keyboardHeight: 0,
				inputBarHeight: 0,
				agentTodoDrawerHeight: 0,
				_initialWindowHeight: 0, // 键盘弹出前的窗口高度，用于检测 adjustResize
				nextId: 1,
				cancelSSE: null,
				isLoadingHistory: false,

				// 滚动控制
				scrollTopValue: 0,
				scrollAnimationEnabled: false,
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

				// thinking 打字机缓冲
				thinkingBuffer: '',
				thinkingTimer: null,
				thinkingMsgId: null,

				// 工具调用相关
				activeToolCalls: [],
				agentTodos: [],
				agentTodoLoaded: false,
				agentTodoExpanded: false,
				agentTodoUpdatingTaskIds: [],

				// 记忆工具最短显示时间跟踪
				memoryToolStartTimes: {},    // { toolCallId: timestamp }
				memoryToolDelayedDone: {}, // { toolCallId: true } 延迟隐藏的工具ID

				// 搜索结果展开状态
				expandedSearchResults: {}, // { toolCallId: true }
				expandedSpaceQueries: {}, // { toolCallId: true/false }
				expandedGraphTools: {}, // { toolCallId: true/false } — 日程工具折叠状态
				expandedChartDetails: {}, // { toolCallId: true/false } — 图表详情展开状态
				collapsingTools: {}, // { toolCallId: true } — 折叠动画中

				// 问题反馈相关
				showFeedbackModal: false,
				feedbackTargetMsg: null,

				// 附件相关
				pendingAttachments: [],  // 待发送的附件列表
				uploadingFiles: [],      // 上传中的文件列表

				// 后台监控：最后一条用户消息的发送时间
				lastUserMessageTimestamp: null,
				isStoppingReply: false,

				// 模型选择相关
				availableModels: [],
				selectedModelId: null,
				showModelMenu: false,
				thinkingEnabled: true,

				// 异步创建空间任务轮询
				taskPollTimers: {},
				taskBindingLocks: {},
				taskNavigated: {}
			}
		},

		onLoad(options) {
			this.restoreThemeMode()
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
			this.restoreThemeMode()
			// 检查后台监控结果并恢复
			const monitor = getActiveMonitor()
			if (monitor && monitor.conversationId === this.conversationId) {
				if (!this.isLoadingHistory) {
					this.recoverFromBackground({
						stopMonitorFirst: true
					})
				}
			}

			// 页面显示时，合并本地缓存的待同步消息（历史加载中不重复 merge）
			if (this.conversationId && !this.isLoadingHistory &&
				(!monitor || monitor.conversationId !== this.conversationId)) {
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
			this.stopAllTaskPolling()
		},

		mounted() {
			// 记录初始窗口高度，用于判断 adjustResize 是否生效
			this._initialWindowHeight = uni.getSystemInfoSync().windowHeight
			console.log(`[QuickChat-KB] mounted: initialWindowH=${this._initialWindowHeight}`)

			console.log('[QuickChat] mounted() fired — model selector code is active')
			// #ifdef APP-PLUS
			if (this.$refs.sseRenderjs) {
				setSseEventBus(this.$refs.sseRenderjs)
			}
			// #endif

			this.loadModels()

			this.$nextTick(() => {
				// #ifdef H5
				this.adjustTextareaHeight()
				// #endif
				this.scheduleInputBarMeasure()
				this.scrollToLatestMessage()
			})

			// 仅在非 H5 平台执行键盘监听
			// #ifndef H5
			uni.onKeyboardHeightChange((res) => {
				const sysInfo = uni.getSystemInfoSync()
				console.log(`[QuickChat-KB] keyboardHeightChange: height=${res.height}px, windowH=${sysInfo.windowHeight}, initWindowH=${this._initialWindowHeight}, platform=${sysInfo.platform}, model=${sysInfo.model}`)

				// Android: 系统通过 adjustPan/adjustResize 自动处理键盘避让，不需要手动偏移
				// iOS: 需要手动设 bottom 偏移
				if (sysInfo.platform === 'android') {
					this.keyboardHeight = 0
				} else {
					this.keyboardHeight = res.height
				}

				if (res.height > 0) {
					this.isAutoScrollEnabled = true
					this.$nextTick(() => {
						this.scrollToLatestMessage()
						this.scheduleInputBarMeasure()
					})
				}
			})
			// #endif
		},

		beforeDestroy() {
			console.log('[QuickChat] beforeDestroy triggered, activeMonitor:', !!getActiveMonitor())
			// onHide/onUnload 可能已经启动了监控，作为最后兜底
			this._tryStartMonitorOrSave('beforeDestroy')
			this.stopAllTaskPolling()

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
			// #ifdef H5
			if (this._resizeObserver) {
				this._resizeObserver.disconnect()
				this._resizeObserver = null
			}
			// #endif
			if (this._scrollRAF) {
				cancelAnimationFrame(this._scrollRAF)
				this._scrollRAF = null
			}
			if (this._inputBarMeasureRAF) {
				cancelAnimationFrame(this._inputBarMeasureRAF)
				this._inputBarMeasureRAF = null
			}
			if (this._inputBarMeasureTimer) {
				clearTimeout(this._inputBarMeasureTimer)
				this._inputBarMeasureTimer = null
			}
			if (this.cancelSSE) {
				this.cancelSSE()
				this.cancelSSE = null
			}
		},

		computed: {
			isLightTheme() {
				return this.homeThemeMode === 'light'
			},
			pageThemeClass() {
				return this.isLightTheme ? 'theme-light' : 'theme-dark'
			},
			isAiStreaming() {
				return this.messages.some(msg => msg.role === 'ai' && msg.isStreaming)
			},
			maxMessageLength() {
				return MAX_MESSAGE_LENGTH
			},
			messageCharCount() {
				return this.getMessageCharCount(this.inputText)
			},
			isInputTooLong() {
				return this.messageCharCount > MAX_MESSAGE_LENGTH
			},
			inputLimitTip() {
				if (this.isInputTooLong) {
					return `已超出 ${this.messageCharCount - MAX_MESSAGE_LENGTH} 字，请删减后再发送`
				}
				return '单次最多发送 10000 字符'
			},
			canSend() {
				return this.inputText.trim().length > 0 && !this.isInputTooLong
			},
			pendingAttachmentCount() {
				return this.pendingAttachments.length
			},
			uploadingFileCount() {
				return this.uploadingFiles.length
			},
			hasAgentTodos() {
				return this.agentTodos.length > 0
			},
			showShortcutPills() {
				return this.shortcutPills.length > 0 && !this.hasAgentTodos
			},
			messageBottomSpacerStyle() {
				const baseWindowHeight = this._initialWindowHeight || uni.getSystemInfoSync().windowHeight || 0
				const shortcutPillsReserveHeight = this.showShortcutPills ? uni.upx2px(144) : 0
				const legacyReserveHeight = (baseWindowHeight ? baseWindowHeight * 6 / 26 : uni.upx2px(280)) + shortcutPillsReserveHeight + (Number(this.keyboardHeight) || 0)
				const measuredCoveredHeight = Number(this.inputBarHeight) || 0
				const drawerHeight = Number(this.agentTodoDrawerHeight) || 0
				const overlaySafetyGap = this.hasAgentTodos
					? Math.max(
						uni.upx2px(this.agentTodoExpanded ? 110 : 124),
						Math.round(drawerHeight * (this.agentTodoExpanded ? 0.28 : 0.40))
					)
					: uni.upx2px(this.showShortcutPills ? 104 : 80)
				const spacerBaseHeight = measuredCoveredHeight > 0 ? measuredCoveredHeight : legacyReserveHeight
				const spacerHeight = spacerBaseHeight + overlaySafetyGap
				return { height: `${Math.ceil(spacerHeight)}px` }
			},
			shortcutPills() {
				return getChatPromptPills(CHAT_PROMPT_PAGE_KEYS.QUICK_CHAT)
			},
			selectedModelName() {
				const model = this.availableModels.find(m => m.id === this.selectedModelId)
				return model ? model.display_name : '模型'
			},
			currentModelSupportsThinking() {
				const model = this.availableModels.find(m => m.id === this.selectedModelId)
				return model?.supports_thinking || false
			},
			autoHeightEnabled() {
				// #ifdef H5
				return false
				// #endif
				// #ifndef H5
				return this.textareaLineCount <= this.textareaMaxLines
				// #endif
			},
			textareaStyle() {
				// #ifdef H5
				return {
					height: this.textareaHeight,
					overflowY: this.textareaOverflow
				}
				// #endif
				// #ifndef H5
				if (this.textareaLineCount > this.textareaMaxLines) {
					const lineH = uni.upx2px(40)
					const padV = uni.upx2px(44)
					const maxH = lineH * this.textareaMaxLines + padV
					return {
						height: maxH + 'px',
						overflowY: 'auto'
					}
				}
				return {}
				// #endif
			}
		},

		watch: {
			inputText() {
				// #ifdef H5
				this.$nextTick(() => {
					this.adjustTextareaHeight()
					this.scheduleInputBarMeasure()
				})
				// #endif
				// #ifndef H5
				this.scheduleInputBarMeasure()
				// #endif
			},
			pendingAttachmentCount() {
				this.scheduleInputBarMeasure()
			},
			uploadingFileCount() {
				this.scheduleInputBarMeasure()
			},
			keyboardHeight() {
				this.scheduleInputBarMeasure()
			}
		},

		methods: {
			restoreThemeMode() {
				this.homeThemeMode = getStoredThemeMode('dark')
				this.syncThemeSystemUi(this.homeThemeMode)
			},
			syncThemeSystemUi(mode) {
				// #ifdef APP-PLUS
				try {
					if (typeof plus !== 'undefined' && plus.navigator) {
						plus.navigator.setStatusBarStyle(mode === 'light' ? 'dark' : 'light')
						if (typeof plus.navigator.setStatusBarBackground === 'function') {
							plus.navigator.setStatusBarBackground(mode === 'light' ? '#F3EDE3' : '#1D1E20')
						}
					}
				} catch (_) {}
				// #endif
			},

			// ==================== 模型选择 ====================
			getMessageCharCount(text) {
				return Array.from((text || '').trim()).length
			},
			isMessageWithinLimit(text) {
				return this.getMessageCharCount(text) <= MAX_MESSAGE_LENGTH
			},
			showMessageLengthExceededToast() {
				uni.showToast({
					title: '内容过长，请删减到10000字以内',
					icon: 'none'
				})
			},
			toggleModelMenu() {
				this.showModelMenu = !this.showModelMenu
			},
			selectModel(id) {
				const model = this.availableModels.find(m => m.id === id)
				if (model?.locked) {
					uni.showToast({ title: '升级订阅以解锁该模型', icon: 'none' })
					return
				}
				this.selectedModelId = id
				this.showModelMenu = false
				setSelectedModelId(id)
				// 切换模型后，若新模型不支持思考则自动关闭
				if (!model?.supports_thinking) {
					this.thinkingEnabled = false
					setThinkingMode(false)
				}
			},
			toggleThinking() {
				if (!this.currentModelSupportsThinking) return
				this.thinkingEnabled = !this.thinkingEnabled
				setThinkingMode(this.thinkingEnabled)
			},
			async loadModels() {
				try {
					const res = await getModels()
					const models = res.models || res || []
					this.availableModels = models
					const storedId = getSelectedModelId()
					const storedModel = models.find(m => m.id === storedId)
					if (storedModel && !storedModel.locked) {
						this.selectedModelId = storedId
					} else {
						const defaultModel = models.find(m => m.is_default && !m.locked)
						this.selectedModelId = defaultModel ? defaultModel.id : (models.find(m => !m.locked)?.id || null)
					}
					const currentModel = models.find(m => m.id === this.selectedModelId)
					this.thinkingEnabled = !!currentModel?.supports_thinking && getThinkingMode()
					if (!currentModel?.supports_thinking) {
						setThinkingMode(false)
					}
				} catch (err) {
					console.error('[QuickChat] Failed to load models:', err)
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

			isAgentTodoTool(toolName) {
				return AGENT_TODO_TOOL_NAMES.has(toolName)
			},

			isHiddenAgentTodoTool(toolName) {
				return HIDDEN_AGENT_TODO_TOOL_NAMES.has(toolName)
			},

			cloneAgentTodos(todos = []) {
				return (Array.isArray(todos) ? todos : []).map(todo => ({ ...todo }))
			},

			filterVisibleToolCalls(toolCalls = []) {
				return (Array.isArray(toolCalls) ? toolCalls : []).filter(tc => !this.isHiddenAgentTodoTool(tc?.tool))
			},

			filterVisibleSegments(segments = []) {
				return (Array.isArray(segments) ? segments : []).filter(seg => {
					return !(seg?.type === 'tool' && this.isHiddenAgentTodoTool(seg.toolCall?.tool))
				})
			},

			replaceAgentTodos(todos, { autoExpand = false } = {}) {
				const nextTodos = this.cloneAgentTodos(todos)
				this.agentTodos = nextTodos
				this.agentTodoLoaded = true
				if (nextTodos.length === 0) {
					this.agentTodoExpanded = false
				} else if (autoExpand) {
					this.agentTodoExpanded = true
				}
				this.$nextTick(() => {
					this.scheduleInputBarMeasure()
				})
			},

			applyAgentTodoPayload(payload, { autoExpand = false } = {}) {
				if (!payload || !Array.isArray(payload.todos)) return false
				this.replaceAgentTodos(payload.todos, { autoExpand })
				return true
			},

			syncAgentTodosFromToolCalls(toolCalls, { autoExpand = false } = {}) {
				if (!Array.isArray(toolCalls)) return false
				for (let i = toolCalls.length - 1; i >= 0; i--) {
					const toolCall = toolCalls[i]
					if (this.isAgentTodoTool(toolCall?.tool) && Array.isArray(toolCall?.result?.todos)) {
						this.replaceAgentTodos(toolCall.result.todos, { autoExpand })
						return true
					}
				}
				return false
			},

			toggleAgentTodoDrawer() {
				if (!this.agentTodos.length) return
				this.agentTodoExpanded = !this.agentTodoExpanded
				this.$nextTick(() => {
					this.scheduleInputBarMeasure()
				})
			},

			isAgentTodoUpdating(taskId) {
				return this.agentTodoUpdatingTaskIds.includes(taskId)
			},

			async handleAgentTodoToggle(payload) {
				const taskId = payload?.taskId
				const completed = !!payload?.completed
				if (!taskId || this.isAgentTodoUpdating(taskId)) return
				if (!this.conversationId) {
					uni.showToast({ title: '待办尚未初始化', icon: 'none' })
					return
				}

				this.agentTodoUpdatingTaskIds = [...this.agentTodoUpdatingTaskIds, taskId]
				try {
					const result = await updateConversationTodoStatus(this.conversationId, taskId, !completed)
					if (Array.isArray(result?.todos)) {
						this.replaceAgentTodos(result.todos, { autoExpand: true })
					} else {
						await this.loadAgentTodos()
					}
				} catch (error) {
					uni.showToast({ title: error?.message || '更新待办失败', icon: 'none' })
				} finally {
					this.agentTodoUpdatingTaskIds = this.agentTodoUpdatingTaskIds.filter(id => id !== taskId)
				}
			},

			async loadAgentTodos() {
				if (!this.conversationId) return
				try {
					const result = await getConversationTodos(this.conversationId)
					this.replaceAgentTodos(result?.todos || [], {
						autoExpand: Array.isArray(result?.todos) && result.todos.length > 0
					})
				} catch (error) {
					console.warn('[QuickChat] Failed to load agent todos:', error)
					this.agentTodoLoaded = true
					this.$nextTick(() => {
						this.scheduleInputBarMeasure()
					})
				}
			},

			buildHistoryMessage(msg) {
				const visibleToolCalls = this.filterVisibleToolCalls(msg.tool_calls || [])
				const mapped = {
					id: this.nextId++,
					role: msg.role === 'user' ? 'user' : 'ai',
					content: msg.content || '',
					attachments: msg.attachments || [],
					created_at: msg.created_at,
					isStreaming: false,
					responseStatus: msg.response_status || 'completed'
				}
				if (mapped.role === 'ai' && visibleToolCalls.length > 0) {
					const segments = visibleToolCalls.map(tc => ({ type: 'tool', toolCall: { ...tc } }))
					if (msg.content && msg.content.trim()) {
						segments.push({ type: 'text', content: msg.content })
					}
					mapped.segments = segments
					mapped.toolCalls = visibleToolCalls.map(tc => ({ ...tc }))
				}
				return mapped
			},

			markLatestPendingUserMessageSynced() {
				if (!this.conversationId) return
				const userMsg = [...this.messages].reverse().find(
					msg => msg.role === 'user' && msg.pendingId && !msg.synced
				)
				if (!userMsg) return
				userMsg.synced = true
				userMsg.isFailed = false
				removePendingMessage(this.conversationId, userMsg.pendingId)
			},

			applyStoppedStatusToMessage(aiMsg, status) {
				if (!aiMsg) return
				aiMsg.content = status.partial_content || aiMsg.content || ''
				if (status.partial_thinking) {
					aiMsg.thinkingContent = status.partial_thinking
				}
				this.syncAgentTodosFromToolCalls(status.tool_calls, { autoExpand: true })
				const visibleToolCalls = this.filterVisibleToolCalls(status.tool_calls || [])
				if (visibleToolCalls.length > 0) {
					aiMsg.toolCalls = visibleToolCalls.map(tc => ({ ...tc }))
					aiMsg.streamSegments = visibleToolCalls.map(tc => ({
						type: 'tool',
						toolCall: { ...tc }
					}))
				} else {
					delete aiMsg.toolCalls
					delete aiMsg.streamSegments
				}
				aiMsg.isStreaming = false
				aiMsg.isWaitingOutput = false
				aiMsg.responseStatus = 'stopped'
			},

			/**
			 * 从后台恢复时的处理
			 * 优先从 Redis 获取流式状态，避免丢失正在生成的内容
			 */
			async recoverFromBackground(options = {}) {
				if (!this.conversationId) return

				const {
					historyAlreadyLoaded = false,
					stopMonitorFirst = false
				} = options

				console.log('[QuickChat] recoverFromBackground start')

				try {
					if (stopMonitorFirst) {
						stopBackgroundMonitor()
					}

					// 1. 先检查 Redis 流式状态
					const status = await getStreamingStatus(this.conversationId)
					console.log('[QuickChat] Redis status:', status.is_streaming, 'content length:', status.partial_content?.length)

					if (status.is_streaming || status.is_stopped || status.partial_content) {
						// AI 仍在生成或有缓存内容，从 Redis 恢复
						this.resumeStreamingFromRedis(status)
						return
					}

					// 2. Redis 缓存已过期，从数据库加载完整对话
					if (!historyAlreadyLoaded) {
						const [result, todoResult] = await Promise.all([
							getConversation(this.conversationId),
							getConversationTodos(this.conversationId).catch((error) => {
								console.warn('[QuickChat] Failed to refresh agent todos during recovery:', error)
								return null
							})
						])
						this.messages = []
						this.nextId = 1
						result.messages.forEach(msg => {
							this.messages.push(this.buildHistoryMessage(msg))
						})
						if (todoResult && Array.isArray(todoResult.todos)) {
							this.replaceAgentTodos(todoResult.todos, { autoExpand: todoResult.todos.length > 0 })
						} else {
							this.agentTodoLoaded = true
						}
					}
					clearPendingMessages(this.conversationId)
					this.$nextTick(() => this.scrollToLatestMessage())
				} catch (err) {
					console.warn('[QuickChat] recoverFromBackground failed:', err)
					// 恢复失败时保留当前消息，不覆盖
				} finally {
					this.activeToolCalls = []
					this.stopHeightMonitor()
				}
			},

			/**
			 * 从 Redis 流式状态恢复
			 */
			resumeStreamingFromRedis(status) {
				// 找到正在流式的 AI 消息
				let aiMsg = this.messages.find(m => m.role === 'ai' && m.isStreaming)

				if (!aiMsg) {
					const lastAiMsg = [...this.messages].reverse().find(m => m.role === 'ai')
					const partialContent = status.partial_content || ''
					const lastContent = lastAiMsg?.content || ''
					if (
						lastAiMsg &&
						(
							(partialContent && lastContent === partialContent) ||
							(partialContent && lastContent && partialContent.startsWith(lastContent)) ||
							(partialContent && lastContent && lastContent.startsWith(partialContent))
						)
					) {
						aiMsg = lastAiMsg
					}
				}

				if (!aiMsg && (status.partial_content || status.partial_thinking || (status.tool_calls && status.tool_calls.length > 0))) {
					// 页面状态可能丢失，根据 Redis 数据创建 AI 消息
					aiMsg = {
						id: this.nextId++,
						role: 'ai',
						content: '',
						isStreaming: true,
						responseStatus: status.is_stopped ? 'stopped' : 'completed'
					}
					this.messages.push(aiMsg)
				}

				if (!aiMsg) return

				// 更新已生成的内容
				aiMsg.content = status.partial_content || ''
				if (status.partial_thinking) {
					aiMsg.thinkingContent = status.partial_thinking
				}
				this.syncAgentTodosFromToolCalls(status.tool_calls, { autoExpand: true })
				const visibleToolCalls = this.filterVisibleToolCalls(status.tool_calls || [])
				if (visibleToolCalls.length > 0) {
					aiMsg.toolCalls = visibleToolCalls.map(tc => ({ ...tc }))
					aiMsg.streamSegments = visibleToolCalls.map(tc => ({
						type: 'tool',
						toolCall: { ...tc }
					}))
				} else {
					delete aiMsg.toolCalls
					delete aiMsg.streamSegments
				}
				if (status.is_stopped) {
					aiMsg.responseStatus = 'stopped'
				} else if (!status.is_streaming) {
					aiMsg.responseStatus = 'completed'
				}

				console.log('[QuickChat] Restored content from Redis, length:', aiMsg.content.length)

				// 如果 AI 仍在生成，重连 SSE
				if (status.is_streaming && !status.is_stopped) {
					if (aiMsg.segments) {
						delete aiMsg.segments
					}
					aiMsg.isStreaming = true
					this.reconnectToResumeStream(aiMsg, aiMsg.content.length)
				} else {
					// 已完成，标记结束
					aiMsg.isStreaming = false
					aiMsg.isWaitingOutput = false
					this.cancelSSE = null
				}

				this.$nextTick(() => this.scrollToLatestMessage())
			},

			/**
			 * 重连到 resume-stream 端点继续接收
			 */
			reconnectToResumeStream(aiMsg, offset) {
				console.log('[QuickChat] Reconnecting to resume-stream, offset:', offset)

				this.cancelSSE = connectSSE({
					url: `/api/conversations/${this.conversationId}/resume-stream?offset=${offset}`,
					method: 'GET',
					onEvent: (eventType, data) => {
						if (eventType === 'text_delta') {
							aiMsg.content += data.content || ''
						} else if (eventType === 'thinking_delta') {
							aiMsg.thinkingContent = (aiMsg.thinkingContent || '') + (data.content || '')
						} else if (eventType === 'done') {
							aiMsg.isStreaming = false
							aiMsg.isWaitingOutput = false
							// done 事件的 content 是完整内容，如果有且不是续传就用它
							if (data.content && !data.resumed) {
								aiMsg.content = data.content
							}
							aiMsg.responseStatus = data.response_status || 'completed'
						}
					},
					onComplete: () => {
						aiMsg.isStreaming = false
						this.cancelSSE = null
						stopBackgroundMonitor()
					},
					onError: (err) => {
						console.warn('[QuickChat] Resume SSE error:', err)
						// 重连失败不标记错误，后台监控会继续处理
					},
				})
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
				// #ifdef H5
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
				// #endif
				// #ifndef H5
				// APP 原生端：检测内容减少时主动同步行数，确保从滚动模式正确回退
				const text = this.inputText || ''
				if (!text) {
					this.textareaLineCount = 1
				} else {
					const explicitLines = text.split('\n').length
					if (explicitLines < this.textareaLineCount) {
						this.textareaLineCount = explicitLines
					}
				}
				// #endif
			},

			onTextareaLineChange(e) {
				const detail = e && e.detail ? e.detail : {}
				const lineCount = Number(detail.lineCount)
				if (!lineCount || Number.isNaN(lineCount)) {
					// #ifdef H5
					this.adjustTextareaHeight()
					// #endif
					return
				}

				const normalizedLineCount = Math.max(1, lineCount)
				this.textareaLineCount = normalizedLineCount

				// #ifdef H5
				const lineH = uni.upx2px(40)
				const padV = uni.upx2px(44)
				const maxLines = Math.max(1, Number(this.textareaMaxLines) || 4)
				const visibleLines = Math.min(maxLines, normalizedLineCount)
				this.textareaHeight = lineH * visibleLines + padV + 'px'
				this.textareaOverflow = normalizedLineCount > maxLines ? 'auto' : 'hidden'
				// #endif
				this.scheduleInputBarMeasure()
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
				this.scheduleInputBarMeasure()
			},

			scheduleInputBarMeasure() {
				if (this._inputBarMeasureTimer) {
					clearTimeout(this._inputBarMeasureTimer)
					this._inputBarMeasureTimer = null
				}
				if (this._inputBarMeasureRAF) {
					cancelAnimationFrame(this._inputBarMeasureRAF)
					this._inputBarMeasureRAF = null
				}
				this.$nextTick(() => {
					const runMeasure = () => {
						this._inputBarMeasureTimer = null
						this._inputBarMeasureRAF = null
						this.measureInputBarHeight()
					}
					if (typeof requestAnimationFrame === 'function') {
						this._inputBarMeasureRAF = requestAnimationFrame(runMeasure)
						return
					}
					this._inputBarMeasureTimer = setTimeout(runMeasure, 0)
				})
			},

			measureInputBarHeight() {
				const query = uni.createSelectorQuery().in(this)
				let barRect = null
				let drawerRect = null
				let cardRect = null
				query.select('.input-bar').boundingClientRect(rect => {
					barRect = rect
				})
				query.select('.stacked-agent-drawer').boundingClientRect(rect => {
					drawerRect = rect
				})
				query.select('.input-card').boundingClientRect(rect => {
					cardRect = rect
				})
				query.exec(() => {
					const viewportHeight = uni.getSystemInfoSync().windowHeight || this._initialWindowHeight || 0
					const topCandidates = [barRect?.top, drawerRect?.top, cardRect?.top].filter(v => typeof v === 'number')
					const heightCandidates = [barRect?.height, cardRect?.height].filter(v => typeof v === 'number')
					if (topCandidates.length === 0 && heightCandidates.length === 0) return
					const overlayTop = topCandidates.length > 0 ? Math.min(...topCandidates) : 0
					const baseHeight = heightCandidates.length > 0 ? Math.max(...heightCandidates) : 0
					const coveredHeight = viewportHeight > 0
						? Math.max(baseHeight, viewportHeight - overlayTop)
						: baseHeight
					const nextHeight = Math.ceil(coveredHeight)
					const nextDrawerHeight = Math.ceil(drawerRect?.height || 0)
					const heightChanged = Math.abs(nextHeight - this.inputBarHeight) > 1
					const drawerChanged = Math.abs(nextDrawerHeight - this.agentTodoDrawerHeight) > 1
					if (heightChanged) {
						this.inputBarHeight = nextHeight
					}
					if (drawerChanged) {
						this.agentTodoDrawerHeight = nextDrawerHeight
					}
					if ((heightChanged || drawerChanged) && this.isAutoScrollEnabled) {
						this.$nextTick(() => this.scrollToLatestMessage())
					}
				})
			},

			isShortcutPillDisabled(pill) {
				return pill.actionType === CHAT_PROMPT_PILL_ACTIONS.SEND && this.isAiStreaming
			},

			handleShortcutPillTap(pill) {
				if (!pill || this.isShortcutPillDisabled(pill)) return

				if (pill.actionType === CHAT_PROMPT_PILL_ACTIONS.FILL) {
					this.inputText = pill.promptText
					this.$nextTick(() => {
						this.adjustTextareaHeight()
						this.focusInputToEnd()
					})
					return
				}

				this.inputText = pill.promptText
				this.sendMessage()
			},

			focusInputToEnd() {
				const cursor = (this.inputText || '').length
				this.inputFocusActive = false
				this.inputCursor = cursor

				this.$nextTick(() => {
					this.inputCursor = cursor
					this.inputFocusActive = true

					// #ifdef H5
					const ref = this.$refs.textareaRef
					const el = ref && ref.$el
						? (ref.$el.querySelector('textarea') || ref.$el)
						: ref
					if (el && typeof el.focus === 'function') {
						setTimeout(() => {
							el.focus()
							if (typeof el.setSelectionRange === 'function') {
								el.setSelectionRange(cursor, cursor)
							}
						}, 0)
					}
					// #endif
				})
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

			async handleCameraSelect() {
				this.showImageSourcePicker = false
				const permitted = await ensureCameraPermission()
				if (!permitted) return
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
						if (err.errMsg === 'chooseImage:fail cancel') return
						if (isPermissionDenied(err)) {
							guideToSettings('需要相机权限', '拍照需要相机权限，请在设置中开启')
						} else {
							uni.showToast({ title: '拍照失败', icon: 'none' })
						}
					}
				})
			},

			async handleAlbumSelect() {
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
						if (err.errMsg === 'chooseImage:fail cancel') return
						if (isPermissionDenied(err)) {
							guideToSettings('需要相册权限', '选择图片需要访问相册权限，请在设置中开启')
						} else {
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
				} else if (this.isInputTooLong) {
					this.showMessageLengthExceededToast()
				} else if (this.canSend) {
					this.sendMessage()
				}
			},

			async stopAiReply() {
				if (this.isStoppingReply || !this.conversationId) return

				const streamingMsg = this.messages.find(msg => msg.role === 'ai' && msg.isStreaming)
				if (!streamingMsg) return

				this.isStoppingReply = true
				this.flushThinkingBuffer()
				stopBackgroundMonitor()

				if (this.cancelSSE) {
					this.cancelSSE()
					this.cancelSSE = null
				}

				streamingMsg.isStreaming = false
				streamingMsg.isWaitingOutput = false
				this.stopHeightMonitor()

				try {
					const result = await stopStreamingReply(this.conversationId)
					if (result.stopped || result.is_stopped) {
						this.applyStoppedStatusToMessage(streamingMsg, result)
						this.markLatestPendingUserMessageSynced()
						return
					}

					const status = await getStreamingStatus(this.conversationId)
					if (status.is_stopped) {
						this.applyStoppedStatusToMessage(streamingMsg, status)
						this.markLatestPendingUserMessageSynced()
						return
					}
					if (status.is_streaming) {
						uni.showToast({ title: '终止失败，请重试', icon: 'none' })
						this.resumeStreamingFromRedis(status)
						return
					}
					if (status.partial_content) {
						this.resumeStreamingFromRedis(status)
						this.markLatestPendingUserMessageSynced()
					}
				} catch (err) {
					console.warn('[QuickChat] stopAiReply failed:', err)
					try {
						const status = await getStreamingStatus(this.conversationId)
						if (status.is_stopped) {
							this.applyStoppedStatusToMessage(streamingMsg, status)
							this.markLatestPendingUserMessageSynced()
							return
						}
						if (status.is_streaming) {
							uni.showToast({ title: '终止失败，请重试', icon: 'none' })
							this.resumeStreamingFromRedis(status)
							return
						}
						if (status.partial_content) {
							this.resumeStreamingFromRedis(status)
							this.markLatestPendingUserMessageSynced()
							return
						}
					} catch (statusErr) {
						console.warn('[QuickChat] stopAiReply status check failed:', statusErr)
					}
					uni.showToast({ title: '终止失败，请重试', icon: 'none' })
				} finally {
					this.isStoppingReply = false
				}
			},

			// ========== 消息片段处理 ==========

			getMessageSegments(msg) {
				// 如果有已处理的 segments，直接使用
				if (msg.segments && msg.segments.length > 0) {
					const visibleSegments = this.filterVisibleSegments(msg.segments)
					if (visibleSegments.length > 0) {
						return visibleSegments
					}
				}

				// 如果有流式片段，使用流式片段
				if (msg.streamSegments && msg.streamSegments.length > 0) {
					const segments = this.filterVisibleSegments(msg.streamSegments).map(seg => ({ ...seg }))
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

			getFullImageUrl(relativePath) {
				if (!relativePath) return ''
				if (relativePath.startsWith('http')) return relativePath
				return `${config.API_BASE_URL}${relativePath}`
			},

			previewChartImage(imageUrl) {
				const fullUrl = this.getFullImageUrl(imageUrl)
				uni.previewImage({
					urls: [fullUrl],
					current: fullUrl
				})
			},

			isMemoryTool(toolName) {
				return MEMORY_TOOLS.has(toolName)
			},

			isSearchTool(toolName) {
				return ['web_search', 'academic_search', 'encyclopedia_search', 'course_search'].includes(toolName)
			},

			getVisibleSearchResults(toolCall) {
				const results = toolCall.result?.results || []
				if (this.expandedSearchResults[toolCall.id]) {
					return results
				}
				return results.slice(0, 5)
			},

			getFaviconUrl(url) {
				try { return new URL(url).origin + '/favicon.ico' }
				catch { return '' }
			},

			isSearchExpanded(toolCallId) {
				return this.expandedSearchResults[toolCallId] !== false
			},

			toggleSearchResults(toolCallId) {
				this.expandedSearchResults = {
					...this.expandedSearchResults,
					[toolCallId]: this.expandedSearchResults[toolCallId] === false
				}
			},

			isSpaceQueryExpanded(toolCallId) {
				return this.expandedSpaceQueries[toolCallId] !== false
			},

			toggleSpaceQuery(toolCallId) {
				const isCurrentlyExpanded = this.expandedSpaceQueries[toolCallId] !== false
				if (isCurrentlyExpanded) {
					this.collapsingTools = { ...this.collapsingTools, [toolCallId]: true }
					setTimeout(() => {
						this.expandedSpaceQueries = { ...this.expandedSpaceQueries, [toolCallId]: false }
						const { [toolCallId]: _, ...rest } = this.collapsingTools
						this.collapsingTools = rest
					}, 200)
				} else {
					this.expandedSpaceQueries = { ...this.expandedSpaceQueries, [toolCallId]: true }
				}
			},

			isToolCollapsing(toolCallId) {
				return !!this.collapsingTools[toolCallId]
			},

			isSpaceMutationTool(toolName) {
				return toolName === 'rebind_to_learning_space' || toolName === 'create_learning_space'
			},

			getSpaceMutationText(toolCall) {
				const spaceName = toolCall.arguments?.space_name || toolCall.arguments?.name || '学习空间'
				if (toolCall.tool === 'rebind_to_learning_space') {
					if (toolCall.status === 'pending_confirmation') return `确认绑定到「${spaceName}」`
					if (toolCall.status === 'running') return '正在绑定学习空间…'
					if (toolCall.status === 'done' && toolCall.success) return `已绑定到「${spaceName}」`
					return '绑定学习空间失败'
				}
				if (toolCall.status === 'pending_confirmation') return `确认创建「${spaceName}」`
				if (toolCall.status === 'running') return '正在创建学习空间…'
				if (toolCall.status === 'done' && toolCall.success) return `已创建「${spaceName}」`
				return '创建学习空间失败'
			},

			isScheduleTool(toolName) {
				return SCHEDULE_TOOLS.has(toolName)
			},

			getScheduleToolText(toolCall) {
				const texts = SCHEDULE_TOOL_TEXT[toolCall.tool]
				if (!texts) return toolCall.tool
				if (toolCall.status === 'running') return texts.running
				if (toolCall.status === 'done' && toolCall.success) {
					if (toolCall.tool === 'get_current_time' && toolCall.result?.current_time) {
						const ts = toolCall.result.current_time
						const short = ts.length >= 16 ? ts.slice(5, 16) : ts
						const weekday = toolCall.result.weekday || ''
						return texts.done + ' · ' + short + (weekday ? ' ' + weekday : '')
					}
					if (toolCall.tool === 'get_schedule') {
						const dr = toolCall.result?.date_range || toolCall.result?.data?.date_range
						if (dr) return texts.done + ' · ' + dr
					}
					return texts.done
				}
				return texts.failed
			},

			isReviewTool(toolName) {
				return REVIEW_TOOLS.has(toolName)
			},

			getReviewToolText(toolCall) {
				const texts = REVIEW_TOOL_TEXT[toolCall.tool]
				if (!texts) return toolCall.tool
				if (toolCall.status === 'running') return texts.running
				if (toolCall.status === 'done' && toolCall.success) {
					if (toolCall.tool === 'get_review_events') {
						const total = toolCall.result?.total || toolCall.result?.items?.length || 0
						if (total > 0) return texts.done + ' · ' + total + ' 条待复习'
					}
					if (toolCall.tool === 'mark_review_completed' && toolCall.result?.completed_count) {
						return texts.done + ' · ' + toolCall.result.completed_count + ' 条'
					}
					return texts.done
				}
				return texts.failed
			},

			getReviewDisplayItems(toolCall) {
				const result = toolCall.result
				if (!result) return []
				if (toolCall.tool === 'get_review_events') {
					return result.items || []
				}
				return []
			},

			isScheduleDetailTool(tool) {
				return tool === 'get_schedule' || tool === 'add_schedule' || tool === 'update_schedule'
			},

			getScheduleEvents(result) {
				if (!result) return []
				if (result.events) return result.events
				if (result.data?.events) return result.data.events
				return []
			},

			getScheduleDisplayEvents(toolCall) {
				const result = toolCall.result
				if (!result) return []
				if (toolCall.tool === 'get_schedule') {
					if (result.events) return result.events
					if (result.data?.events) return result.data.events
					return []
				}
				// add_schedule / update_schedule: single event → wrap as array
				if (result.start_time) {
					return [{
						id: result.id || result.updated_id,
						title: result.title || '',
						start_time: result.start_time,
						end_time: result.end_time || result.start_time,
						details: result.details
					}]
				}
				return []
			},

			groupScheduleByDate(events) {
				if (!events || !events.length) return []
				const groups = {}
				const today = new Date()
				const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
				const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
				const BAR_COLORS = [
					'rgba(74, 108, 247, 0.8)',
					'rgba(232, 168, 56, 0.8)',
					'rgba(94, 194, 105, 0.8)',
					'rgba(129, 140, 248, 0.8)',
					'rgba(239, 68, 68, 0.8)'
				]
				let colorIdx = 0
				for (const ev of events) {
					const dateStr = ev.start_time ? ev.start_time.slice(0, 10) : 'unknown'
					if (!groups[dateStr]) {
						const d = new Date(dateStr.replace(/-/g, '/'))
						const isToday = dateStr === todayStr
						const month = d.getMonth() + 1
						const day = d.getDate()
						const weekday = WEEKDAYS[d.getDay()]
						groups[dateStr] = {
							date: dateStr,
							label: `${month}月${day}日 ${weekday}` + (isToday ? ' · 今天' : ''),
							isToday,
							events: []
						}
					}
					groups[dateStr].events.push({
						...ev,
						startShort: ev.start_time ? ev.start_time.slice(11, 16) : '',
						endShort: ev.end_time ? ev.end_time.slice(11, 16) : '',
						barColor: BAR_COLORS[colorIdx % BAR_COLORS.length]
					})
					colorIdx++
				}
				return Object.values(groups).sort((a, b) => a.date.localeCompare(b.date))
			},

			isGraphToolExpanded(toolCallId) {
				return this.expandedGraphTools[toolCallId] !== false
			},

			toggleGraphTool(toolCallId) {
				const isCurrentlyExpanded = this.expandedGraphTools[toolCallId] !== false
				if (isCurrentlyExpanded) {
					this.collapsingTools = { ...this.collapsingTools, [toolCallId]: true }
					setTimeout(() => {
						this.expandedGraphTools = { ...this.expandedGraphTools, [toolCallId]: false }
						const { [toolCallId]: _, ...rest } = this.collapsingTools
						this.collapsingTools = rest
					}, 200)
				} else {
					this.expandedGraphTools = { ...this.expandedGraphTools, [toolCallId]: true }
				}
			},

			isChartExpanded(toolCallId) {
				return this.expandedChartDetails[toolCallId] !== false
			},

			toggleChartExpand(toolCallId) {
				const isCurrentlyExpanded = this.expandedChartDetails[toolCallId] !== false
				if (isCurrentlyExpanded) {
					this.collapsingTools = { ...this.collapsingTools, [toolCallId]: true }
					setTimeout(() => {
						this.expandedChartDetails = { ...this.expandedChartDetails, [toolCallId]: false }
						const { [toolCallId]: _, ...rest } = this.collapsingTools
						this.collapsingTools = rest
					}, 200)
				} else {
					this.expandedChartDetails = { ...this.expandedChartDetails, [toolCallId]: true }
				}
			},

			getChartToolText(toolCall) {
				if (toolCall.status === 'running') return '正在生成图表…'
				if (toolCall.status === 'done' && toolCall.success) return '已生成图表'
				return '图表生成失败'
			},

			openSearchResultUrl(url) {
				if (!url || !/^https?:\/\//i.test(String(url))) return
				// #ifdef H5
				window.open(url, '_blank')
				// #endif
				// #ifdef APP-PLUS
				plus.runtime.openURL(url)
				// #endif
			},

			getSourceLabel(source) {
				const map = {
					academic: '学术',
					encyclopedia: '百科',
					course: 'B站',
					web: '网页'
				}
				return map[source] || source
			},

			formatDisplayUrl(url) {
				try {
					const u = new URL(url)
					return u.hostname
				} catch {
					return url
				}
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
				if (this.isAgentTodoTool(tool) && status === 'done') {
					this.applyAgentTodoPayload(result, { autoExpand: true })
				}
				if (this.isHiddenAgentTodoTool(tool)) {
					this.$forceUpdate()
					return
				}

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
						// 防止后端 tool_call(done) 覆盖客户端已完成的工具结果
						if (toolCall._clientDone) return

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

					// 创建学习空间：走异步处理链路
					if (toolCall.tool === 'create_learning_space') {
						await this.handleCreateLearningSpaceConfirmResult(msgId, toolCall, result)
						return
					}

					// 更新工具状态
					toolCall.status = 'done'
					toolCall.success = result.success
					toolCall.message = result.message
					toolCall.result = result.data

					// 同步更新消息中的工具片段
					const msg = this.messages.find(m => m.id === msgId)
					this.syncToolCallInMessage(msg, toolCall)

					this.$forceUpdate()

					// 如果需要跳转，延迟执行让用户看到成功状态
					if (result.data?.action === 'navigate_to_space_chat') {
						setTimeout(() => {
							this.navigateToSpaceChat(result.data.space_id, result.data.space_name, result.data.conversation_id)
						}, 1200)
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

			// ========== 创建学习空间异步任务处理 ==========

			/**
			 * 处理 create_learning_space 确认后的异步分发
			 */
			async handleCreateLearningSpaceConfirmResult(msgId, toolCall, result) {
				const action = result?.data?.action

				// Case 1: 异步创建（正常流程）
				if (result?.status === 'accepted' && action === 'async_create_learning_space') {
					toolCall.status = 'running'
					toolCall.success = null
					toolCall.result = result.data || {}
					toolCall.message = this.getCreateSpaceRunningText(result?.data?.stage || 'kg_running')

					const msg = this.messages.find(m => m.id === msgId)
					this.syncToolCallInMessage(msg, toolCall)
					this.$forceUpdate()

					this.startCreateSpaceTaskPolling(toolCall.id)
					return
				}

				// Case 2: 已有运行中的任务
				if (result?.status === 'accepted' && action === 'existing_running_task') {
					const existingStage = result?.data?.existing_stage
					toolCall.status = 'done'
					toolCall.success = false
					toolCall.result = result.data || {}
					toolCall.message = `已有任务进行中（${this.getCreateSpaceStageLabel(existingStage)}）`

					const msg = this.messages.find(m => m.id === msgId)
					this.syncToolCallInMessage(msg, toolCall)
					this.$forceUpdate()

					const existingToolCallId = result?.data?.existing_tool_call_id
					if (existingToolCallId) {
						const holder = this.ensureCreateSpaceToolCard(existingToolCallId, {
							message: this.getCreateSpaceRunningText(existingStage)
						})
						holder.toolCall.status = 'running'
						holder.toolCall.success = null
						holder.toolCall.message = this.getCreateSpaceRunningText(existingStage)
						this.syncToolCallInMessage(holder.msg, holder.toolCall)
						this.$forceUpdate()
						this.startCreateSpaceTaskPolling(existingToolCallId)
					}
					return
				}

				// Case 3: 其他结果（同步成功/失败）
				toolCall.status = 'done'
				toolCall.success = !!result?.success
				toolCall.message = result?.message || '创建学习空间失败'
				toolCall.result = result?.data || null

				const msg = this.messages.find(m => m.id === msgId)
				this.syncToolCallInMessage(msg, toolCall)
				this.$forceUpdate()

				if (result?.data?.action === 'navigate_to_space_chat' && result?.data?.space_id) {
					setTimeout(() => {
						this.navigateToSpaceChat(result.data.space_id, result.data.space_name, result.data.conversation_id)
					}, 1200)
				}
			},

			/**
			 * 启动 2s 间隔轮询任务状态
			 */
			startCreateSpaceTaskPolling(toolCallId) {
				if (!this.conversationId || !toolCallId) return
				if (this.taskPollTimers[toolCallId]) return

				const poll = async () => {
					await this.pollCreateSpaceTaskStatus(toolCallId)
				}

				const timerId = setInterval(poll, 2000)
				this.taskPollTimers = { ...this.taskPollTimers, [toolCallId]: timerId }
				poll()
			},

			/**
			 * 停止单个任务的轮询
			 */
			stopCreateSpaceTaskPolling(toolCallId) {
				const timerId = this.taskPollTimers[toolCallId]
				if (timerId) {
					clearInterval(timerId)
				}
				const { [toolCallId]: _timer, ...restTimers } = this.taskPollTimers
				this.taskPollTimers = restTimers
				const { [toolCallId]: _lock, ...restLocks } = this.taskBindingLocks
				this.taskBindingLocks = restLocks
			},

			/**
			 * 停止所有轮询（页面销毁时调用）
			 */
			stopAllTaskPolling() {
				Object.values(this.taskPollTimers).forEach(timerId => clearInterval(timerId))
				this.taskPollTimers = {}
				this.taskBindingLocks = {}
				this.taskNavigated = {}
			},

			/**
			 * 单次轮询：获取状态 → 更新 UI → kg_done 时触发绑定
			 */
			async pollCreateSpaceTaskStatus(toolCallId) {
				try {
					const response = await getQuickChatToolTaskStatus(this.conversationId, toolCallId)
					if (!response) return

					if (!response.success) {
						const holder = this.ensureCreateSpaceToolCard(toolCallId, {
							message: response?.message || '任务状态获取失败'
						})
						this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, {
							status: 'failed',
							stage: 'kg_failed',
							error_stage: 'kg_generation',
							error_message: response?.message || '任务状态获取失败'
						})
						this.stopCreateSpaceTaskPolling(toolCallId)
						return
					}

					if (!response.data) return

					const task = response.data
					const holder = this.ensureCreateSpaceToolCard(toolCallId, {
						message: this.getCreateSpaceRunningText(task.stage)
					})

					this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, task)

					if (task.status === 'running' && (task.can_bind || task.stage === 'kg_done')) {
						await this.tryBindCreateSpaceTask(toolCallId)
						return
					}

					if (task.status === 'failed') {
						this.stopCreateSpaceTaskPolling(toolCallId)
						return
					}

					if (task.status === 'done' && task.stage === 'binding_done') {
						this.stopCreateSpaceTaskPolling(toolCallId)
						if (!this.taskNavigated[toolCallId] && task.space_id) {
							this.taskNavigated = { ...this.taskNavigated, [toolCallId]: true }
							setTimeout(() => {
								this.navigateToSpaceChat(task.space_id, task.request_payload?.name, this.conversationId)
							}, 900)
						}
					}
				} catch (err) {
					// 忽略瞬时轮询错误，继续轮询
				}
			},

			/**
			 * KG 完成后尝试绑定任务
			 */
			async tryBindCreateSpaceTask(toolCallId) {
				if (!this.conversationId || !toolCallId) return
				if (this.taskBindingLocks[toolCallId]) return

				this.taskBindingLocks = { ...this.taskBindingLocks, [toolCallId]: true }

				const holder = this.ensureCreateSpaceToolCard(toolCallId, {
					message: CREATE_SPACE_RUNNING_STAGE_TEXT.binding
				})
				holder.toolCall.status = 'running'
				holder.toolCall.success = null
				holder.toolCall.message = CREATE_SPACE_RUNNING_STAGE_TEXT.binding
				this.syncToolCallInMessage(holder.msg, holder.toolCall)
				this.$forceUpdate()

				try {
					const response = await bindQuickChatToolTask(this.conversationId, toolCallId)
					if (!response?.success) {
						const task = response?.data
						if (task?.stage === 'kg_done' || String(response?.message || '').includes('尚未生成完成')) {
							return
						}

						this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, task || {
							status: 'failed',
							stage: 'binding_failed',
							error_stage: 'binding',
							error_message: response?.message || '学习空间绑定失败'
						})
						this.stopCreateSpaceTaskPolling(toolCallId)
						return
					}

					const task = response?.data || {}
					this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, {
						...task,
						status: task.status || 'done',
						stage: task.stage || 'binding_done'
					})
					this.stopCreateSpaceTaskPolling(toolCallId)

					const spaceId = task.space_id
					if (spaceId && !this.taskNavigated[toolCallId]) {
						this.taskNavigated = { ...this.taskNavigated, [toolCallId]: true }
						setTimeout(() => {
							this.navigateToSpaceChat(spaceId, task.space_name, this.conversationId)
						}, 900)
					}
				} catch (err) {
					this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, {
						status: 'failed',
						stage: 'binding_failed',
						error_stage: 'binding',
						error_message: err?.message || '学习空间绑定失败'
					})
					this.stopCreateSpaceTaskPolling(toolCallId)
				} finally {
					const { [toolCallId]: _lock, ...restLocks } = this.taskBindingLocks
					this.taskBindingLocks = restLocks
				}
			},

			/**
			 * 页面加载时恢复进行中的异步任务
			 */
			async restoreQuickChatToolTasks() {
				if (!this.conversationId) return

				try {
					const response = await listQuickChatToolTasks(this.conversationId)
					if (!response?.success || !response?.data?.tasks) return

					const tasks = response.data.tasks || []
					for (const task of tasks) {
						if (task.tool_name !== 'create_learning_space' || !task.tool_call_id) continue

						const holder = this.ensureCreateSpaceToolCard(task.tool_call_id, {
							message: this.getCreateSpaceRunningText(task.stage)
						})
						this.applyCreateSpaceTaskToCard(holder.msg, holder.toolCall, task)

						if (task.status === 'running') {
							this.startCreateSpaceTaskPolling(task.tool_call_id)
						}
					}
				} catch (err) {
					// 恢复是尽力而为，忽略错误
				}
			},

			/**
			 * 确保指定 toolCallId 有对应的 UI 卡片，不存在则创建
			 */
			ensureCreateSpaceToolCard(toolCallId, options = {}) {
				const existing = this.findToolCallCard(toolCallId)
				if (existing) return existing

				const toolCall = {
					id: toolCallId,
					tool: 'create_learning_space',
					status: 'running',
					success: null,
					display_name: TOOL_DISPLAY_NAMES.create_learning_space,
					requires_confirmation: false,
					arguments: {},
					result: null,
					message: options.message || CREATE_SPACE_RUNNING_STAGE_TEXT.kg_running
				}

				const msg = {
					id: this.nextId++,
					role: 'ai',
					content: '',
					isStreaming: false,
					isWaitingOutput: false,
					isError: false,
					segments: [{ type: 'tool', toolCall: { ...toolCall } }],
					streamSegments: null,
					toolCalls: [{ ...toolCall }],
					isSystemToolStatus: true
				}

				this.messages = [...this.messages, msg]
				this.$nextTick(() => this.scrollToLatestMessage())

				return this.findToolCallCard(toolCallId)
			},

			/**
			 * 根据任务状态更新卡片 UI
			 */
			applyCreateSpaceTaskToCard(msg, toolCall, task) {
				if (!toolCall || !task) return

				toolCall.result = task

				if (task.status === 'running') {
					toolCall.status = 'running'
					toolCall.success = null
					toolCall.message = this.getCreateSpaceRunningText(task.stage)
				} else if (task.status === 'failed') {
					toolCall.status = 'done'
					toolCall.success = false
					toolCall.message = this.getCreateSpaceFailedText(task)
				} else if (task.status === 'done') {
					toolCall.status = 'done'
					toolCall.success = true
					toolCall.message = CREATE_SPACE_SUCCESS_TEXT
				}

				this.syncToolCallInMessage(msg, toolCall)
				this.$forceUpdate()
			},

			/**
			 * 按 toolCallId 查找消息中的工具卡片
			 */
			findToolCallCard(toolCallId) {
				if (!toolCallId) return null

				for (let i = this.messages.length - 1; i >= 0; i -= 1) {
					const msg = this.messages[i]
					const segmentSources = [msg?.segments, msg?.streamSegments]

					for (const source of segmentSources) {
						if (!Array.isArray(source)) continue
						const seg = source.find(s => s?.type === 'tool' && s?.toolCall?.id === toolCallId)
						if (seg?.toolCall) {
							return { msg, toolCall: seg.toolCall }
						}
					}

					if (Array.isArray(msg?.toolCalls)) {
						const tc = msg.toolCalls.find(t => t?.id === toolCallId)
						if (tc) {
							return { msg, toolCall: tc }
						}
					}
				}

				return null
			},

			/**
			 * 同步工具状态到 message 的 segments/streamSegments/toolCalls
			 */
			syncToolCallInMessage(msg, toolCall) {
				if (!msg || !toolCall) return

				const syncInArray = (arr) => {
					if (!Array.isArray(arr)) return
					for (let i = 0; i < arr.length; i++) {
						if (arr[i]?.type === 'tool' && arr[i]?.toolCall?.id === toolCall.id) {
							arr[i].toolCall = { ...toolCall }
						}
					}
				}

				syncInArray(msg.segments)
				syncInArray(msg.streamSegments)

				if (Array.isArray(msg.toolCalls)) {
					for (let i = 0; i < msg.toolCalls.length; i++) {
						if (msg.toolCalls[i]?.id === toolCall.id) {
							msg.toolCalls[i] = { ...toolCall }
						}
					}
				}
			},

			// ========== 创建学习空间文案辅助方法 ==========

			getCreateSpaceRunningText(stage) {
				return CREATE_SPACE_RUNNING_STAGE_TEXT[stage] || '正在处理学习空间创建任务…'
			},

			getCreateSpaceStageLabel(stage) {
				const mapping = {
					queued: '排队中',
					space_created: '空间已创建',
					kg_running: '知识图谱生成中',
					kg_done: '知识图谱已完成',
					binding: '绑定中',
					binding_done: '绑定完成',
					kg_failed: '知识图谱失败',
					binding_failed: '绑定失败',
					timeout: '任务超时',
					cleanup_done: '清理完成',
					cleanup_failed: '清理失败'
				}
				return mapping[stage] || '处理中'
			},

			getCreateSpaceFailedText(task) {
				if (!task) return '学习空间创建失败'

				const errorStage = task.error_stage
				const errorMessage = task.error_message || '未知错误'

				let mainText = ''
				if (errorStage === 'kg_generation') {
					mainText = `知识图谱生成失败：${errorMessage}`
				} else if (errorStage === 'binding') {
					mainText = `学习空间绑定失败：${errorMessage}`
				} else if (errorStage === 'kg_generation_timeout') {
					mainText = '知识图谱生成超时（2分钟）'
				} else if (errorStage === 'cleanup') {
					mainText = `失败后清理空间失败：${errorMessage}`
				} else {
					mainText = `学习空间创建失败：${errorMessage}`
				}

				const cleanupStage = task?.result_payload?.cleanup_stage
				if (cleanupStage === 'cleanup_failed') {
					const cleanupError = task?.result_payload?.cleanup_error || '未知错误'
					const cleanupText = `失败后清理空间失败：${cleanupError}`
					if (!mainText.includes(cleanupText)) {
						mainText = `${mainText}\n${cleanupText}`
					}
				}

				return mainText
			},

			/**
			 * 处理客户端工具请求（日历操作等）
			 */
			async handleClientToolRequest(aiMsgId, data) {
				const { tool_call_id, tool, params } = data

				// 日历工具：自动执行
				this.handleToolCallEvent(aiMsgId, {
					id: tool_call_id,
					tool,
					status: 'running',
					arguments: params
				})

				const calendarResult = await executeCalendarTool(tool, params)

				// Dual-write: sync to backend DB (best-effort)
				this.syncCalendarToBackend(tool, params, calendarResult).catch(err => {
					console.warn('Calendar backend sync failed:', err)
				})

				// POST 结果回后端（带重试）
				const maxRetries = 3
				for (let attempt = 1; attempt <= maxRetries; attempt++) {
					try {
						await submitToolResult(this.conversationId, {
							tool_call_id,
							success: calendarResult.success,
							result: calendarResult.result || null,
							error: calendarResult.error || null
						})
						break
					} catch (err) {
						console.error(`submitToolResult attempt ${attempt} failed:`, err)
						if (attempt < maxRetries) {
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

				// 标记为客户端已完成
				const clientTc = this.activeToolCalls.find(tc => tc.id === tool_call_id)
				if (clientTc) clientTc._clientDone = true
			},

			async syncCalendarToBackend(tool, params, calendarResult) {
				if (!calendarResult.success) return
				try {
					if (tool === 'add_schedule') {
						const externalId = calendarResult.result?.id || null
						await createCalendarEvent({
							title: params.title,
							start_time: this.calendarTimeToISO(params.start_time),
							end_time: this.calendarTimeToISO(params.end_time),
							details: params.details || null,
							external_id: externalId ? String(externalId) : null,
							source_conversation_id: this.conversationId || null
						})
					} else if (tool === 'delete_schedule' && params.schedule_id) {
						const events = await getCalendarEvents(
							new Date(Date.now() - 365 * 86400000).toISOString(),
							new Date(Date.now() + 365 * 86400000).toISOString()
						)
						const match = (events || []).find(e => e.external_id === String(params.schedule_id))
						if (match) await deleteCalendarEvent(match.id)
					} else if (tool === 'update_schedule' && params.schedule_id) {
						const events = await getCalendarEvents(
							new Date(Date.now() - 365 * 86400000).toISOString(),
							new Date(Date.now() + 365 * 86400000).toISOString()
						)
						const match = (events || []).find(e => e.external_id === String(params.schedule_id))
						if (match) {
							const updateData = {}
							if (params.title) updateData.title = params.title
							if (params.start_time) updateData.start_time = this.calendarTimeToISO(params.start_time)
							if (params.end_time) updateData.end_time = this.calendarTimeToISO(params.end_time)
							if (params.details) updateData.details = params.details
							await updateCalendarEvent(match.id, updateData)
						}
					}
				} catch (err) {
					console.warn('syncCalendarToBackend error:', err)
				}
			},

			calendarTimeToISO(timeStr) {
				if (!timeStr) return new Date().toISOString()
				const [datePart, timePart] = timeStr.split(' ')
				if (!datePart || !timePart) return new Date().toISOString()
				return new Date(`${datePart}T${timePart}:00`).toISOString()
			},

			openNativeCalendar() {
				// #ifdef APP-PLUS
				try {
					const Intent = plus.android.importClass('android.content.Intent')
					const Uri = plus.android.importClass('android.net.Uri')
					const intent = new Intent(Intent.ACTION_VIEW)
					intent.setData(Uri.parse('content://com.android.calendar/time/' + Date.now()))
					const main = plus.android.runtimeMainActivity()
					main.startActivity(intent)
				} catch (e) {
					plus.runtime.openURL('content://com.android.calendar/time/' + Date.now())
				}
				// #endif
				// #ifdef H5
				uni.showToast({ title: '请在手机端打开日历', icon: 'none' })
				// #endif
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

			// 强制触发滚动更新（RAF 防抖，每帧最多一次）
			forceScrollUpdate(targetScrollTop) {
				if (this._scrollRAF) cancelAnimationFrame(this._scrollRAF)
				this._scrollRAF = requestAnimationFrame(() => {
					this._isProgrammaticScroll = true
					if (this.scrollTopValue === targetScrollTop) {
						this.scrollTopValue = targetScrollTop + 0.5
						this.$nextTick(() => { this.scrollTopValue = targetScrollTop })
					} else {
						this.scrollTopValue = targetScrollTop
					}
					this._scrollRAF = null
				})
			},

			onScroll(e) {
				const currentScrollTop = e.detail.scrollTop

				// 跳过程序触发的滚动事件
				if (this._isProgrammaticScroll) {
					this._isProgrammaticScroll = false
					this.lastScrollTop = currentScrollTop
					return
				}

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

			// ========== Thinking 打字机效果 ==========

			appendThinkingText(msgId, text) {
				if (this.thinkingMsgId !== msgId) {
					this.flushThinkingBuffer()
					this.thinkingMsgId = msgId
				}
				this.thinkingBuffer += text
				if (!this.thinkingTimer) {
					this.thinkingTimer = setInterval(() => {
						if (this.thinkingBuffer.length === 0) {
							clearInterval(this.thinkingTimer)
							this.thinkingTimer = null
							return
						}
						// 每次渲染 2 个字符，15ms 间隔 ≈ 133字/秒
						const chunk = this.thinkingBuffer.slice(0, 2)
						this.thinkingBuffer = this.thinkingBuffer.slice(2)
						const msg = this.messages.find(m => m.id === this.thinkingMsgId)
						if (msg) {
							msg.thinkingContent = (msg.thinkingContent || '') + chunk
						}
					}, 15)
				}
			},

			flushThinkingBuffer() {
				if (this.thinkingTimer) {
					clearInterval(this.thinkingTimer)
					this.thinkingTimer = null
				}
				if (this.thinkingBuffer && this.thinkingMsgId) {
					const msg = this.messages.find(m => m.id === this.thinkingMsgId)
					if (msg) {
						msg.thinkingContent = (msg.thinkingContent || '') + this.thinkingBuffer
					}
				}
				this.thinkingBuffer = ''
				this.thinkingMsgId = null
			},

			// ========== AI 流式生成监听 ==========

			startHeightMonitor(msgId) {
				this.aiStreamingMsgId = msgId
				this.lastMsgHeight = 0
				this.scrollAnimationEnabled = false

				// #ifdef H5
				if (typeof ResizeObserver !== 'undefined') {
					this.$nextTick(() => {
						const el = document.querySelector(`#msg-${msgId}`)
						if (el) {
							this._resizeObserver = new ResizeObserver(() => {
								if (this.isAutoScrollEnabled) this.scrollToLatestMessage()
							})
							this._resizeObserver.observe(el)
							return
						}
					})
				}
				// #endif

				this.heightCheckTimer = setInterval(() => {
					this.checkHeightChange()
				}, 300)
			},

			stopHeightMonitor() {
				if (this.heightCheckTimer) {
					clearInterval(this.heightCheckTimer)
					this.heightCheckTimer = null
				}
				// #ifdef H5
				if (this._resizeObserver) {
					this._resizeObserver.disconnect()
					this._resizeObserver = null
				}
				// #endif
				this.aiStreamingMsgId = null
				this.lastMsgHeight = 0
				this.scrollAnimationEnabled = true
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
				if (!this.isMessageWithinLimit(text)) {
					this.showMessageLengthExceededToast()
					return
				}

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
				this.textareaLineCount = 1
				this.textareaHeight = 'auto'
				this.textareaOverflow = 'hidden'
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
					await this.loadAgentTodos()
				} catch (err) {
					uni.showToast({ title: '创建对话失败', icon: 'none' })
					throw err
				}
			},

			async loadExistingConversation(convId) {
				this.isLoadingHistory = true
				try {
					const [result, todoResult] = await Promise.all([
						getConversation(convId),
						getConversationTodos(convId).catch((error) => {
							console.warn('[QuickChat] Failed to load agent todos:', error)
							return null
						})
					])
					const historyMessages = result.messages || []
					this.messages = []
					this.nextId = 1

					historyMessages.forEach(msg => {
						this.messages.push(this.buildHistoryMessage(msg))
					})
					if (todoResult && Array.isArray(todoResult.todos)) {
						this.replaceAgentTodos(todoResult.todos, { autoExpand: todoResult.todos.length > 0 })
					} else {
						this.agentTodoLoaded = true
					}

					// 后台监控 active 时，服务器数据已包含完整回复，清空缓存避免重复
					const monitor = getActiveMonitor()
					if (monitor && monitor.conversationId === this.conversationId) {
						clearPendingMessages(this.conversationId)
					} else {
						this.mergePendingMessages()
					}
					await this.recoverFromBackground({
						historyAlreadyLoaded: true,
						stopMonitorFirst: !!(monitor && monitor.conversationId === this.conversationId)
					})
					this.$nextTick(() => {
						this.scrollToLatestMessage()
					})

					// 恢复进行中的异步任务（创建学习空间等）
					this.restoreQuickChatToolTasks()
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
				if (!this.isMessageWithinLimit(userMessage)) {
					this.showMessageLengthExceededToast()
					if (pendingId) {
						const userMsg = this.messages.find(m => m.pendingId === pendingId)
						if (userMsg) {
							userMsg.isFailed = true
						}
					}
					return
				}

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
					thinkingContent: '',
					isThinkingExpanded: true,
					thinkingStartTime: 0,
					thinkingDuration: 0,
					isStreaming: true,
					isWaitingOutput: true,
					responseStatus: 'completed'
				})
				this.scrollToLatestMessage()
				this.startHeightMonitor(aiMsgId)
				this.activeToolCalls = []

				const msgIndex = this.messages.length - 1

				this.cancelSSE = sendQuickChatMessage(
					this.conversationId,
					userMessage,
					{
						onThinking: (content) => {
							const msg = this.messages[msgIndex]
							if (msg.isWaitingOutput) msg.isWaitingOutput = false
							if (!msg.thinkingStartTime) {
								msg.thinkingStartTime = Date.now()
							}
							this.appendThinkingText(aiMsgId, content)
						},

						onTextDelta: (content) => {
							const msg = this.messages[msgIndex]
							if (msg.isWaitingOutput) {
								msg.isWaitingOutput = false
							}
							// Auto-collapse thinking + calculate duration
							if (msg.isThinkingExpanded) {
								this.flushThinkingBuffer()
								msg.isThinkingExpanded = false
								if (msg.thinkingStartTime) {
									msg.thinkingDuration = Math.round((Date.now() - msg.thinkingStartTime) / 1000)
								}
							}
							msg.content = msg.content + content
						},

						onToolCall: (data) => {
							this.handleToolCallEvent(aiMsgId, data)
						},

						onClientToolRequest: (data) => {
							this.handleClientToolRequest(aiMsgId, data)
						},

						onDone: (fullContent, citations, doneData) => {
							this.flushThinkingBuffer()
							const msg = this.messages.find(m => m.id === aiMsgId)
							if (msg) {
								// 构建最终片段
								const finalSegments = []

								if (msg.streamSegments && msg.streamSegments.length > 0) {
									for (const seg of msg.streamSegments) {
										if (seg.type === 'tool') {
											if (this.isHiddenAgentTodoTool(seg.toolCall?.tool)) {
												continue
											}
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
								const visibleToolCalls = this.filterVisibleToolCalls(this.activeToolCalls)
								if (visibleToolCalls.length > 0) {
									msg.toolCalls = visibleToolCalls.map(tc => ({ ...tc }))
								} else {
									delete msg.toolCalls
								}
								msg.isWaitingOutput = false
								msg.isStreaming = false
								msg.responseStatus = doneData?.response_status || 'completed'
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

						onQuotaError: (info) => {
							this.flushThinkingBuffer()
							const isDaily = info.code === 'DAILY_MESSAGE_QUOTA_EXCEEDED'
							const shortText = isDaily ? '今日消息已用完' : '配额已达上限'
							uni.showModal({
								title: '配额已达上限',
								content: isDaily
									? '今日消息次数已用完，明日自动重置。升级后可无限对话'
									: (info.message || '当前套餐不支持此功能，升级后可使用'),
								confirmText: '去升级',
								cancelText: '知道了',
								success: (res) => {
									if (res.confirm) {
										uni.navigateTo({ url: '/pages/subscription/subscription' })
									}
								}
							})
							this.messages[msgIndex].isWaitingOutput = false
							this.messages[msgIndex].isStreaming = false
							this.messages[msgIndex].content = shortText
							this.messages[msgIndex].isError = true
							this.stopHeightMonitor()
						},

						onError: (message) => {
							// 后台断连时不标记失败（后台监控会处理）
							if (this.isBackgroundMonitorActive()) return

							this.flushThinkingBuffer()
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

						onReconnecting: (attempt) => {
							console.log(`[QuickChat] Reconnecting attempt ${attempt}`)
							uni.showToast({
								title: `重连中 (${attempt}/3)...`,
								icon: 'loading',
								duration: 10000,
								mask: false
							})
						},

						onReconnected: () => {
							console.log('[QuickChat] Reconnected successfully')
							uni.hideToast()
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

								this.flushThinkingBuffer()
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
					this.selectedModelId,
					{ thinking: this.thinkingEnabled }
				)
			},

			resendMessage(msg) {
				if (this.isAiStreaming) return
				if (!this.isMessageWithinLimit(msg.content)) {
					this.showMessageLengthExceededToast()
					return
				}
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
				this.inputFocusActive = true
				const sysInfo = uni.getSystemInfoSync()
				console.log(`[QuickChat-KB] onInputFocus: currentKeyboardH=${this.keyboardHeight}px, screenH=${sysInfo.screenHeight}, windowH=${sysInfo.windowHeight}, model=${sysInfo.model}`)
				if (this.isAutoScrollEnabled) {
					this.scrollToLatestMessage()
				}
			},

			onInputBlur() {
				this.inputFocusActive = false
				console.log(`[QuickChat-KB] onInputBlur: keyboardH=${this.keyboardHeight}px (应即将归零)`)
				// keyboardHeight 会通过 onKeyboardHeightChange 自动重置
			},

			copyMessage(msg) {
				uni.setClipboardData({
					data: msg.content,
					showToast: false,
					success: () => {
						this.$set(msg, 'copySuccess', true)
						setTimeout(() => {
							this.$set(msg, 'copySuccess', false)
						}, 1500)
					}
				})
			},

			reactToMessage(msg, reaction) {
				const current = msg.userReaction
				const newReaction = current === reaction ? null : reaction
				this.$set(msg, 'userReaction', newReaction)

				// Only send feedback when setting a reaction (not when clearing)
				if (!newReaction) return

				const conversationHistory = this.messages.map(m => ({
					role: m.role,
					content: m.content,
					created_at: m.created_at || new Date().toISOString(),
					toolCalls: m.toolCalls || null,
					segments: m.segments || null
				}))

				submitFeedback({
					conversation_id: this.conversationId,
					message_id: msg.serverId || null,
					chat_mode: 'quick_chat',
					space_name: null,
					feedback_type: newReaction === 'like' ? 'positive' : 'negative',
					feedback_content: newReaction === 'like' ? '👍 用户点赞了此回复' : '👎 用户点踩了此回复',
					conversation_history: conversationHistory
				}).catch(() => {
					// Silent failure — don't affect UI
				})
			},

			isLastUserMessage(msg) {
				for (let i = this.messages.length - 1; i >= 0; i--) {
					if (this.messages[i].role === 'user') {
						return this.messages[i].id === msg.id
					}
				}
				return false
			},

			async editMessage(msg) {
				if (this.isAiStreaming) return

				// 1. 回填内容到输入框
				this.inputText = msg.content

				// 2. 调用后端 rollback API
				if (this.conversationId) {
					try {
						await rollbackLastMessage(this.conversationId)
					} catch (err) {
						console.error('Rollback failed:', err)
					}
				}

				// 3. 前端删除该消息及其后的所有消息
				const msgIdx = this.messages.findIndex(m => m.id === msg.id)
				if (msgIdx >= 0) {
					this.messages.splice(msgIdx)
				}
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
			async saveImage(url) {
				const permitted = await ensureAlbumWritePermission()
				if (!permitted) return
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
								fail: (err) => {
									uni.hideLoading()
									if (isPermissionDenied(err)) {
										guideToSettings('需要存储权限', '保存图片需要访问相册权限，请在设置中开启')
									} else {
										uni.showToast({ title: '保存失败', icon: 'none' })
									}
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
		background-color: rgb(29, 30, 32);
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

	.chat-page .nav-icon {
		width: 48rpx;
		height: 48rpx;
		filter: brightness(0) invert(1);
	}

	.nav-title {
		font-size: 34rpx;
		font-weight: 600;
		color: rgb(248, 248, 248);
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
		/* #ifdef H5 */
		content-visibility: auto;
		contain-intrinsic-size: auto 120px;
		/* #endif */
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
		background-color: #4A6CF7;
		border-radius: 32rpx 8rpx 32rpx 32rpx;
		padding: 24rpx 28rpx;
		max-width: none;
		min-width: 0;
	}

	.bubble-ai {
		background-color: transparent;
	}

	.message-text {
		font-size: 30rpx;
		color: rgb(248, 248, 248);
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

	/* ========== 默认工具 pill 容器 ========== */
	.default-tool-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.default-tool-expanded {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.default-tool-expanded .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* ========== 记忆工具行内银光掠过 ========== */
	.memory-tool-inline {
		margin: 8rpx 0;
		max-height: 0;
		opacity: 0;
		overflow: hidden;
		transition: max-height 0.4s ease, opacity 0.4s ease, margin 0.4s ease;
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

	.memory-tool-done .memory-tool-text {
		animation: none;
	}

	.memory-tool-text {
		display: inline-block;
		font-size: 26rpx;
		font-style: italic;
		color: rgba(192, 199, 210, 0.5);
		background: linear-gradient(
			90deg,
			rgba(160, 170, 185, 0.4) 0%,
			rgba(200, 210, 225, 0.7) 20%,
			rgba(230, 238, 250, 1) 40%,
			rgba(200, 210, 225, 0.7) 60%,
			rgba(160, 170, 185, 0.4) 80%,
			rgba(160, 170, 185, 0.4) 100%
		);
		background-size: 250% 100%;
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
		animation: memory-shimmer 2s ease-in-out infinite;
	}

	@keyframes memory-shimmer {
		0% {
			background-position: 100% 50%;
		}
		100% {
			background-position: -100% 50%;
		}
	}

	/* 学习空间查询工具 - 胶囊指示器 */
	.space-query-pill {
		display: flex;
		align-items: center;
		gap: 14rpx;
		padding: 14rpx 20rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 20rpx;
	}

	.space-query-running {
		background: rgba(74, 108, 247, 0.06);
		border-color: rgba(74, 108, 247, 0.3);
	}

	.space-query-done {
		background: rgba(255, 255, 255, 0.06);
		border-color: rgba(255, 255, 255, 0.12);
	}

	.space-query-expanded {
		background: rgba(74, 108, 247, 0.08);
		border-color: rgba(74, 108, 247, 0.25);
	}

	.space-query-icon {
		width: 30rpx;
		height: 30rpx;
		flex-shrink: 0;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.space-query-text {
		flex: 1;
		font-size: 25rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.65);
	}

	.space-query-spinner {
		width: 22rpx;
		height: 22rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.25);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	.space-query-chevron {
		width: 24rpx;
		height: 24rpx;
		flex-shrink: 0;
		opacity: 0.35;
		filter: brightness(0) invert(1);
		transition: transform 0.2s ease;
	}

	.space-query-chevron-up {
		transform: rotate(180deg);
	}

	.space-query-wrap {
	}

	.space-query-wrap .space-query-pill {
	}

	.space-query-results {
		margin-top: 12rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.12);
		border-radius: 16rpx;
		padding: 20rpx 24rpx;
	}

	.space-query-results-header {
		display: flex;
		align-items: center;
		gap: 10rpx;
		padding-bottom: 16rpx;
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
		margin-bottom: 4rpx;
	}

	.space-query-results-icon {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(1);
		opacity: 0.5;
	}

	.space-query-results-title {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.45);
		font-weight: 500;
	}

	.space-query-item {
		display: flex;
		align-items: center;
		padding: 16rpx 0;
		border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.space-query-item:last-child {
		border-bottom: none;
	}

	.space-query-color {
		width: 24rpx;
		height: 24rpx;
		border-radius: 6rpx;
		margin-right: 16rpx;
		flex-shrink: 0;
	}

	.space-query-name {
		flex: 1;
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
	}

	.space-query-arrow {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(1);
		opacity: 0.4;
	}

	/* ========== 学习空间查询展开容器 ========== */
	.space-query-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.space-query-expanded-container .space-query-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.space-query-expanded-container .space-query-results {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
		margin-top: 0;
		animation: tool-card-enter 0.28s ease-out;
	}

	/* ========== 学习空间绑定/创建 pill 容器 ========== */
	.space-mutation-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.space-mutation-expanded {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.space-mutation-expanded .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.space-mutation-confirm {
		padding: 0 24rpx 20rpx;
		display: flex;
		flex-direction: column;
		gap: 16rpx;
		animation: tool-card-enter 0.28s ease-out;
	}

	.space-mutation-confirm-text {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.8);
	}

	.space-mutation-confirm-buttons {
		display: flex;
		gap: 16rpx;
	}

	/* ========== 折叠过渡动画 ========== */
	.tool-card-leave {
		animation: tool-card-leave 0.2s ease-in forwards;
		pointer-events: none;
	}

	@keyframes tool-card-enter {
		from { opacity: 0; transform: translateY(-8rpx); }
		to { opacity: 1; transform: translateY(0); }
	}

	@keyframes tool-card-leave {
		from { opacity: 1; transform: translateY(0); }
		to { opacity: 0; transform: translateY(-8rpx); }
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
		color: rgb(248, 248, 248);
		font-weight: 500;
	}

	/* 图表预览 */
	/* ========== 图表工具 pill 容器 ========== */
	.chart-tool-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.chart-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.chart-expanded-container .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.chart-expanded-container .chart-detail-card {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
		animation: tool-card-enter 0.28s ease-out;
	}

	.chart-detail-card {
		padding: 0 24rpx 20rpx;
		border-radius: 24rpx;
	}

	.chart-preview-img {
		width: 100%;
		border-radius: 12rpx;
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
		gap: 4rpx;
		margin-top: 12rpx;
	}

	.ai-status-badge {
		display: inline-flex;
		align-items: center;
		margin-top: 16rpx;
		padding: 8rpx 18rpx;
		border-radius: 999rpx;
		background: rgba(255, 255, 255, 0.08);
		border: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.ai-status-badge-text {
		font-size: 22rpx;
		line-height: 1;
		color: rgba(255, 255, 255, 0.62);
	}

	.ai-msg-action-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 56rpx;
		height: 56rpx;
		border-radius: 12rpx;
		transition: background-color 0.15s ease, transform 0.1s ease;
	}

	.ai-msg-action-btn:active {
		transform: scale(0.88);
		background-color: rgba(255, 255, 255, 0.08);
	}

	.ai-msg-action-icon {
		width: 30rpx;
		height: 30rpx;
		opacity: 0.4;
		filter: brightness(0) invert(1);
		transition: opacity 0.15s ease, filter 0.15s ease;
	}

	.action-btn-active .ai-msg-action-icon {
		opacity: 1;
		filter: brightness(0) invert(1);
	}

	/* 复制按钮：两个图标叠加 crossfade */
	.copy-btn {
		position: relative;
	}

	.copy-icon-default,
	.copy-icon-check {
		position: absolute;
		transition: opacity 0.25s ease, transform 0.25s ease;
	}

	.copy-icon-default {
		opacity: 0.4;
		transform: scale(1);
	}

	.copy-icon-default.copy-icon-hide {
		opacity: 0;
		transform: scale(0.6);
	}

	.copy-icon-check {
		opacity: 0;
		transform: scale(0.6);
	}

	.copy-icon-check.copy-icon-show {
		opacity: 1;
		transform: scale(1);
		filter: brightness(0) invert(0.45) sepia(1) saturate(8) hue-rotate(90deg);
	}

	/* 用户消息操作图标 */
	.user-msg-actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 24rpx;
		margin-top: 8rpx;
	}

	.user-msg-action-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 56rpx;
		height: 56rpx;
		border-radius: 12rpx;
		transition: background-color 0.15s ease, transform 0.1s ease;
	}

	.user-msg-action-btn:active {
		transform: scale(0.88);
		background-color: rgba(255, 255, 255, 0.08);
	}

	.user-msg-action-icon {
		width: 32rpx;
		height: 32rpx;
		opacity: 1;
		filter: brightness(0) invert(0.45) sepia(0.15);
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

	.input-drawer-stack {
		position: relative;
		width: 100%;
	}

	.stacked-agent-drawer {
		position: relative;
		z-index: 0;
		width: calc(100% - 44rpx);
		margin: 0 auto -42rpx;
	}

	.input-card {
		width: 100%;
		position: relative;
		z-index: 2;
		background-color: rgb(36, 36, 36);
		border-radius: 40rpx;
		border: 2rpx solid rgba(255, 255, 255, 0.06);
		box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
		overflow: hidden;
	}

	.input-drawer-stack-active .input-card {
		box-shadow:
			0 18rpx 36rpx rgba(0, 0, 0, 0.18),
			0 4rpx 18rpx rgba(0, 0, 0, 0.12);
	}

	.input-field {
		width: 100%;
		font-size: 28rpx;
		color: #F5F5F5;
		-webkit-text-fill-color: #F5F5F5;
		min-height: 40rpx;
		line-height: 1.4;
		padding: 24rpx 28rpx 12rpx 72rpx;
		box-sizing: border-box;
		resize: none;
		overflow-y: hidden;
	}

	.shortcut-pills-scroll {
		width: 100%;
		padding: 0 16rpx 20rpx;
		box-sizing: border-box;
	}

	.shortcut-pills-row {
		display: inline-flex;
		align-items: center;
		gap: 12rpx;
		padding-right: 4rpx;
	}

	.shortcut-pill {
		--shortcut-pill-bg: #2A2C31;
		--shortcut-pill-border: #4A4D55;
		--shortcut-pill-text: #E2E4E8;
		display: inline-flex;
		align-items: center;
		gap: 8rpx;
		flex-shrink: 0;
		min-height: 56rpx;
		padding: 10rpx 18rpx 10rpx 16rpx;
		border-radius: 20rpx;
		border: 2rpx solid var(--shortcut-pill-border);
		background: var(--shortcut-pill-bg);
		box-shadow: none;
		transition: transform 0.15s ease, filter 0.15s ease, border-color 0.15s ease;
	}

	.shortcut-pill:active {
		transform: scale(0.97);
		filter: brightness(0.96);
	}

	.shortcut-pill-icon {
		width: 22rpx;
		height: 22rpx;
		filter: brightness(0) invert(1);
		opacity: 0.86;
		flex-shrink: 0;
	}

	.shortcut-pill-text {
		font-size: 23rpx;
		line-height: 1.1;
		color: var(--shortcut-pill-text);
		-webkit-text-fill-color: var(--shortcut-pill-text);
		white-space: nowrap;
	}

	.input-bottom-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 12rpx 8rpx 12rpx;
	}

	.input-bottom-left {
		display: flex;
		align-items: center;
		gap: 8rpx;
		flex: 1;
		min-width: 0;
	}

	.input-bottom-row-spacer {
		flex: 1;
	}

	.right-actions {
		display: flex;
		align-items: center;
		gap: 16rpx;
	}

	.input-action {
		width: 64rpx;
		height: 64rpx;
		flex-shrink: 0;
		display: flex;
		justify-content: center;
		align-items: center;
		background: rgb(52, 52, 54);
		border: 1.5rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 50%;
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.05),
			0 2rpx 10rpx rgba(0, 0, 0, 0.14);
	}

	.input-action-icon {
		width: 36rpx;
		height: 36rpx;
		filter: brightness(0) invert(0.72) sepia(0.08);
	}

	.send-btn-wrapper {
		background: #4A6CF7;
		border-color: transparent;
		box-shadow: 0 4rpx 14rpx rgba(74, 108, 247, 0.28);
	}

	.send-btn-wrapper .send-action-icon {
		width: 36rpx !important;
		height: 36rpx !important;
		filter: none !important;
		display: block;
	}

	/* 停止按钮 - 圆形背景 + 圆角矩形 */
	.stop-btn {
		width: 48rpx;
		height: 48rpx;
		border-radius: 50%;
		background-color: #FFFFFF;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.send-btn-wrapper .stop-btn {
		width: 56rpx;
		height: 56rpx;
	}

	.stop-btn-inner {
		width: 20rpx;
		height: 20rpx;
		border-radius: 4rpx;
		background-color: #000000;
	}

	.send-btn-wrapper .stop-btn-inner {
		width: 22rpx;
		height: 22rpx;
		border-radius: 5rpx;
	}

	/* 发送按钮禁用状态 */
	.send-btn-disabled {
		opacity: 0.5;
	}

	.input-placeholder {
		color: #A1A1AA;
		-webkit-text-fill-color: #A1A1AA;
		font-size: 28rpx;
	}

	.textarea-wrapper {
		position: relative;
	}

	.input-limit-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16rpx;
		margin: 8rpx 20rpx 10rpx;
		padding: 10rpx 14rpx;
		border-radius: 16rpx;
		border: 1.5rpx solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
	}

	.input-limit-row-warning {
		border-color: rgba(248, 113, 113, 0.42);
		background: rgba(127, 29, 29, 0.22);
	}

	.input-limit-text {
		flex: 1;
		min-width: 0;
		font-size: 22rpx;
		color: #9CA3AF;
		-webkit-text-fill-color: #9CA3AF;
	}

	.input-limit-row-warning .input-limit-text {
		color: #FCA5A5;
		-webkit-text-fill-color: #FCA5A5;
	}

	.input-limit-counter {
		flex-shrink: 0;
		font-size: 22rpx;
		color: #D4D4D8;
		-webkit-text-fill-color: #D4D4D8;
	}

	.input-limit-row-warning .input-limit-counter {
		color: #FCA5A5;
		-webkit-text-fill-color: #FCA5A5;
	}

	.custom-placeholder-row {
		position: absolute;
		top: 24rpx;
		left: 28rpx;
		display: flex;
		align-items: center;
		gap: 12rpx;
		pointer-events: none;
		z-index: 1;
	}

	.placeholder-sparkle-icon {
		width: 32rpx;
		height: 32rpx;
	}

	.placeholder-text {
		color: #A1A1AA;
		-webkit-text-fill-color: #A1A1AA;
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
		right: calc(100vw / 24);
		bottom: calc(100vh * 1.5 / 26 + 100rpx);
		min-width: 280rpx;
		background: rgb(41, 41, 41);
		border: 2rpx solid rgba(255, 255, 255, 0.06);
		border-radius: 20rpx;
		box-shadow: 0 12rpx 40rpx rgba(0, 0, 0, 0.3);
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
		background: rgb(44, 44, 44);
	}

	.popup-option-icon {
		width: 44rpx;
		height: 44rpx;
		margin-right: 24rpx;
		filter: brightness(0) invert(0.75);
		opacity: 1;
	}

	.popup-option-text {
		font-size: 30rpx;
		color: rgba(255, 255, 255, 0.85);
		font-weight: 500;
	}

	.popup-divider {
		height: 1rpx;
		background: rgba(255, 255, 255, 0.06);
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
		border-top: 16rpx solid rgb(41, 41, 41);
	}


	/* ========== 搜索来源卡片 ========== */
	.search-tool-wrap {
	}

	.search-indicator {
		display: flex;
		align-items: center;
		gap: 14rpx;
		padding: 14rpx 20rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 20rpx;
	}

	.search-indicator-running {
		border-color: rgba(74, 108, 247, 0.3);
		background: rgba(74, 108, 247, 0.06);
	}

	.search-indicator-expanded {
		background: rgba(74, 108, 247, 0.08);
		border-color: rgba(74, 108, 247, 0.25);
	}

	.search-indicator-collapsed {
		background: rgba(255, 255, 255, 0.03);
		border-color: rgba(255, 255, 255, 0.06);
	}

	.search-indicator-collapsed .search-indicator-text {
		color: rgba(255, 255, 255, 0.45);
	}

	.search-indicator-collapsed .search-indicator-globe {
		opacity: 0.5;
	}

	.search-indicator-globe {
		width: 30rpx;
		height: 30rpx;
		flex-shrink: 0;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.search-indicator-text {
		flex: 1;
		font-size: 25rpx;
		color: rgba(255, 255, 255, 0.65);
		font-weight: 500;
	}

	.search-indicator-spinner {
		width: 22rpx;
		height: 22rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.25);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	.search-indicator-chevron {
		width: 24rpx;
		height: 24rpx;
		flex-shrink: 0;
		opacity: 0.35;
		filter: brightness(0) invert(1);
		transition: transform 0.2s ease;
	}

	.search-chevron-up {
		transform: rotate(180deg);
	}

	.search-sources-scroll {
		margin-top: 12rpx;
		white-space: nowrap;
	}

	.search-sources-row {
		display: inline-flex;
		gap: 12rpx;
	}

	.search-source-card {
		display: inline-flex;
		flex-direction: column;
		gap: 10rpx;
		padding: 16rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 20rpx;
		width: 260rpx;
		flex-shrink: 0;
		white-space: normal;
	}

	.search-source-head {
		display: flex;
		align-items: center;
		gap: 8rpx;
	}

	.search-source-num {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28rpx;
		height: 28rpx;
		border-radius: 6rpx;
		background: rgba(74, 108, 247, 0.15);
		flex-shrink: 0;
	}

	.search-source-num-text {
		font-size: 18rpx;
		font-weight: 600;
		color: #4A6CF7;
	}

	.search-source-site {
		font-size: 20rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.45);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.search-source-title {
		font-size: 24rpx;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.85);
		line-height: 1.3;
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		white-space: normal;
	}

	.search-tool-empty,
	.search-tool-error {
		margin-top: 8rpx;
		padding: 8rpx 0;
	}

	.search-tool-empty-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.search-tool-error-text {
		font-size: 24rpx;
		color: rgba(239, 68, 68, 0.7);
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
		padding: 16rpx 24rpx 0;
		background-color: transparent;
		max-height: 400rpx;
		overflow-y: auto;
		width: 100%;
		box-sizing: border-box;
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
		color: rgb(248, 248, 248);
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

	/* ==================== 模型选择器（底部工具行内） ==================== */
	.model-selector-btn {
		display: flex;
		align-items: center;
		gap: 8rpx;
		padding: 8rpx 16rpx 8rpx 12rpx;
		min-height: 44rpx;
		background: rgb(46, 46, 48);
		border: 1.5rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 999rpx;
		cursor: pointer;
		transition: background 0.15s ease;
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
			0 2rpx 8rpx rgba(0, 0, 0, 0.12);
	}

	.model-selector-btn:active {
		background: rgb(56, 56, 59);
	}

	.model-selector-icon {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(0.7);
		opacity: 1;
		flex-shrink: 0;
	}

	.model-selector-label {
		font-size: 24rpx;
		color: #C7CBD4;
		-webkit-text-fill-color: #C7CBD4;
		white-space: nowrap;
		max-width: 280rpx;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.model-selector-chevron {
		width: 20rpx;
		height: 20rpx;
		filter: brightness(0) invert(0.62);
		opacity: 1;
		flex-shrink: 0;
	}

	/* 深度思考切换按钮 */
	.thinking-toggle-btn {
		display: flex;
		align-items: center;
		gap: 10rpx;
		padding: 8rpx 16rpx 8rpx 12rpx;
		min-height: 44rpx;
		background: rgb(46, 46, 48);
		border: 1.5rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 999rpx;
		transition: background 0.15s ease;
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
			0 2rpx 8rpx rgba(0, 0, 0, 0.12);
		flex-shrink: 0;
	}

	.thinking-toggle-btn:active {
		background: rgb(56, 56, 59);
	}

	.thinking-toggle-icon {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(0.62);
		flex-shrink: 0;
	}

	.thinking-toggle-label {
		font-size: 24rpx;
		color: #C7CBD4;
		-webkit-text-fill-color: #C7CBD4;
		white-space: nowrap;
	}

	.thinking-toggle-indicator {
		width: 56rpx;
		height: 32rpx;
		border-radius: 999rpx;
		background: rgba(255, 255, 255, 0.1);
		border: 1.5rpx solid rgba(255, 255, 255, 0.08);
		padding: 0 6rpx;
		display: flex;
		align-items: center;
		transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
		flex-shrink: 0;
		box-sizing: border-box;
		box-shadow: inset 0 1rpx 2rpx rgba(0, 0, 0, 0.16);
	}

	.thinking-toggle-indicator-active {
		background: rgba(74, 108, 247, 0.32);
		border-color: rgba(74, 108, 247, 0.42);
		box-shadow:
			inset 0 1rpx 2rpx rgba(255, 255, 255, 0.06),
			0 0 0 4rpx rgba(74, 108, 247, 0.08);
	}

	.thinking-toggle-indicator-core {
		width: 20rpx;
		height: 20rpx;
		border-radius: 50%;
		background: #F8FAFC;
		box-shadow:
			0 2rpx 8rpx rgba(0, 0, 0, 0.26),
			inset 0 1rpx 1rpx rgba(255, 255, 255, 0.5);
		transform: translateX(0);
		transition: transform 0.18s ease, background 0.18s ease;
	}

	.thinking-toggle-indicator-core-active {
		transform: translateX(24rpx);
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
		left: 12rpx;
		width: max-content;
		min-width: 360rpx;
		max-width: 80%;
		z-index: 200;
		margin-bottom: 8rpx;
		background: rgb(41, 41, 41);
		border: 2rpx solid rgba(255, 255, 255, 0.06);
		border-radius: 20rpx;
		padding: 6rpx;
		box-shadow: 0 -6rpx 24rpx rgba(0, 0, 0, 0.25);
	}

	.model-menu-item {
		display: flex;
		align-items: center;
		padding: 20rpx 24rpx;
		border: 1.5rpx solid transparent;
		border-radius: 16rpx;
		transition: background 0.15s ease;
	}

	.model-menu-item:active {
		background: rgb(44, 44, 44);
	}

	.model-menu-item-active {
		background: rgba(74, 108, 247, 0.18);
		border-color: rgba(74, 108, 247, 0.42);
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.05),
			0 4rpx 12rpx rgba(74, 108, 247, 0.12);
	}

	.model-menu-accent {
		width: 8rpx;
		height: 42rpx;
		margin-right: 18rpx;
		border-radius: 999rpx;
		background: rgba(255, 255, 255, 0.06);
		opacity: 0;
		flex-shrink: 0;
		transition: opacity 0.15s ease, background 0.15s ease;
	}

	.model-menu-item-active .model-menu-accent {
		background: linear-gradient(180deg, #7A93FF 0%, #4A6CF7 100%);
		box-shadow: 0 0 12rpx rgba(74, 108, 247, 0.35);
		opacity: 1;
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
		color: #C7CBD4;
		-webkit-text-fill-color: #C7CBD4;
	}

	.model-menu-item-active .model-menu-item-name {
		color: rgb(248, 248, 248);
	}

	.model-menu-item-active .model-menu-item-desc {
		color: #A1A1AA;
		-webkit-text-fill-color: #A1A1AA;
	}

	.model-menu-item-desc {
		font-size: 22rpx;
		color: #A1A1AA;
		-webkit-text-fill-color: #A1A1AA;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.model-menu-item-locked {
		opacity: 0.5;
	}

	.model-menu-item-locked .model-menu-item-name {
		color: #9CA3AF;
	}

	.model-menu-lock {
		width: 28rpx;
		height: 28rpx;
		filter: brightness(0) invert(0.58);
		opacity: 1;
		flex-shrink: 0;
		margin-left: 16rpx;
	}

	/* ===== Thinking/Reasoning Section (DeepSeek style) ===== */
	.thinking-section {
		margin-bottom: 16rpx;
	}

	.thinking-header {
		display: flex;
		align-items: center;
		gap: 8rpx;
	}

	.thinking-label {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.85);
	}

	.thinking-chevron {
		width: 28rpx;
		height: 28rpx;
		filter: invert(1);
		opacity: 0.7;
		transition: transform 0.2s ease;
	}

	.thinking-chevron-up {
		transform: rotate(180deg);
	}

	.thinking-body {
		margin-top: 8rpx;
		padding-left: 20rpx;
		border-left: 4rpx solid rgba(255, 255, 255, 0.25);
		max-height: 1500rpx;
		opacity: 1;
		overflow: hidden;
		transition: max-height 0.35s ease-out, opacity 0.25s ease 0.05s, margin-top 0.25s ease;
	}

	.thinking-body-collapsed {
		max-height: 0;
		opacity: 0;
		margin-top: 0;
		transition: max-height 0.2s cubic-bezier(0, 0.8, 0.3, 1), opacity 0.15s ease, margin-top 0.15s ease;
	}

	.thinking-text {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.75);
		line-height: 1.7;
		word-break: break-all;
	}

	/* ========== 知识图谱/日程工具 pill ========== */
	.graph-tool-pill {
		display: flex;
		align-items: center;
		gap: 16rpx;
		padding: 16rpx 24rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		transition: all 0.25s ease;
	}

	.graph-tool-running {
		border-color: rgba(74, 108, 247, 0.3);
		background: rgba(74, 108, 247, 0.06);
	}

	.graph-tool-done {
		/* 中性底色 */
	}

	.graph-tool-failed {
		border-color: rgba(239, 68, 68, 0.2);
		background: rgba(239, 68, 68, 0.05);
	}

	.graph-tool-pill-icon {
		width: 32rpx;
		height: 32rpx;
		flex-shrink: 0;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.graph-tool-pill-text {
		flex: 1;
		font-size: 26rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.7);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.graph-tool-running .graph-tool-pill-text {
		color: rgba(255, 255, 255, 0.8);
	}

	.graph-tool-spinner {
		width: 28rpx;
		height: 28rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.3);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	.graph-tool-status-icon {
		width: 28rpx;
		height: 28rpx;
		flex-shrink: 0;
		filter: invert(48%) sepia(30%) saturate(900%) hue-rotate(100deg) brightness(85%) contrast(90%);
	}

	.graph-tool-status-failed {
		filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
	}

	.graph-tool-expanded {
		border-color: rgba(255, 255, 255, 0.2);
		background: rgba(255, 255, 255, 0.08);
	}

	.graph-tool-chevron {
		width: 24rpx;
		height: 24rpx;
		flex-shrink: 0;
		opacity: 0.35;
		filter: brightness(0) invert(1);
		transition: transform 0.2s ease;
	}

	.graph-tool-chevron-up {
		transform: rotate(180deg);
	}

	/* ========== 日程详情卡片 ========== */
	.schedule-view-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	/* ========== 日程工具展开容器 ========== */
	.schedule-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.schedule-expanded-container .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.schedule-expanded-container .schedule-card {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
		animation: tool-card-enter 0.28s ease-out;
	}

	.schedule-card {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 20rpx 24rpx 14rpx;
		display: flex;
		flex-direction: column;
		gap: 8rpx;
	}

	.schedule-date-header {
		display: flex;
		align-items: center;
		gap: 12rpx;
		padding: 6rpx 0;
	}

	.schedule-date-dot {
		width: 10rpx;
		height: 10rpx;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.25);
		flex-shrink: 0;
	}

	.schedule-date-dot-today {
		background: rgba(74, 108, 247, 0.8);
	}

	.schedule-date-text {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.45);
		font-weight: 600;
	}

	.schedule-date-text-today {
		color: rgba(255, 255, 255, 0.6);
	}

	.schedule-event-row {
		display: flex;
		align-items: flex-start;
		gap: 16rpx;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 16rpx;
		padding: 14rpx 16rpx;
	}

	.schedule-event-time {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2rpx;
		width: 80rpx;
		flex-shrink: 0;
	}

	.schedule-event-time-start {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.8);
		font-weight: 600;
	}

	.schedule-event-time-end {
		font-size: 20rpx;
		color: rgba(255, 255, 255, 0.35);
	}

	.schedule-event-bar {
		width: 4rpx;
		min-height: 48rpx;
		align-self: stretch;
		border-radius: 2rpx;
		flex-shrink: 0;
	}

	.schedule-event-info {
		display: flex;
		flex-direction: column;
		gap: 4rpx;
		flex: 1;
		min-width: 0;
	}

	.schedule-event-title {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.85);
		font-weight: 500;
	}

	.schedule-event-desc {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.schedule-card-clickable:active {
		opacity: 0.7;
	}

	.schedule-card-footer {
		display: flex;
		justify-content: flex-end;
		padding: 6rpx 4rpx 0;
	}

	.schedule-card-count {
		font-size: 20rpx;
		color: rgba(255, 255, 255, 0.25);
	}

	.schedule-card-empty {
		padding: 24rpx;
		align-items: center;
	}

	.schedule-empty-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.35);
	}

	/* ========== 复习工具 pill + 卡片 ========== */
	.review-tool-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	/* ========== 复习工具展开容器 ========== */
	.review-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.review-expanded-container .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.review-expanded-container .review-card {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
		animation: tool-card-enter 0.28s ease-out;
	}

	.review-card {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 16rpx 20rpx 12rpx;
		display: flex;
		flex-direction: column;
		gap: 8rpx;
	}

	.review-card-empty {
		align-items: center;
		padding: 24rpx 16rpx;
	}

	.review-empty-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.review-card-footer {
		margin-top: 4rpx;
		text-align: right;
	}

	.review-card-count {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.review-event-item {
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 12rpx;
		padding: 12rpx 16rpx;
	}

	.review-event-header {
		display: flex;
		align-items: center;
		gap: 8rpx;
	}

	.review-event-label {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
		flex: 1;
	}

	.review-event-depth {
		font-size: 20rpx;
		color: rgba(129, 140, 248, 0.9);
		background: rgba(129, 140, 248, 0.12);
		padding: 2rpx 10rpx;
		border-radius: 6rpx;
	}

	.review-event-meta {
		display: flex;
		align-items: center;
		gap: 12rpx;
		margin-top: 6rpx;
	}

	.review-event-round {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.5);
	}

	.review-event-urgency-badge {
		background: rgba(94, 194, 105, 0.10);
		padding: 2rpx 10rpx;
		border-radius: 6rpx;
	}

	.review-event-urgency-badge.urgency-overdue {
		background: rgba(232, 168, 56, 0.10);
	}

	.review-event-urgency-text {
		font-size: 22rpx;
		color: rgba(94, 194, 105, 0.9);
	}

	.review-event-urgency-text.urgency-overdue-text {
		color: rgba(232, 168, 56, 0.9);
	}

	.chat-page.theme-light {
		--chat-page-bg: #F3EDE3;
		--chat-surface: rgba(255, 250, 244, 0.82);
		--chat-surface-strong: rgba(255, 255, 255, 0.78);
		--chat-surface-soft: rgba(63, 53, 42, 0.05);
		--chat-border: rgba(63, 53, 42, 0.1);
		--chat-border-strong: rgba(63, 53, 42, 0.14);
		--chat-outline: rgba(255, 255, 255, 0.72);
		--chat-shadow: 0 14rpx 36rpx rgba(118, 101, 80, 0.14);
		--chat-shadow-soft: 0 8rpx 24rpx rgba(118, 101, 80, 0.12);
		--chat-text-primary: #1F1A16;
		--chat-text-secondary: rgba(31, 26, 22, 0.76);
		--chat-text-muted: rgba(31, 26, 22, 0.58);
		--chat-text-faint: rgba(31, 26, 22, 0.42);
		--chat-accent: #2F6EEA;
		--chat-accent-strong: #2459C8;
		--chat-accent-soft: rgba(47, 110, 234, 0.1);
		--chat-accent-soft-strong: rgba(47, 110, 234, 0.16);
		--chat-danger: #D14F4F;
		--chat-danger-soft: rgba(209, 79, 79, 0.1);
		--chat-success: #2F8F66;
		--chat-success-soft: rgba(47, 143, 102, 0.12);
		--chat-warning: #C77716;
		--chat-warning-soft: rgba(199, 119, 22, 0.12);
		background-color: var(--chat-page-bg);
	}

	.chat-page.theme-light .nav-left,
	.chat-page.theme-light .plus-popup,
	.chat-page.theme-light .model-menu,
	.chat-page.theme-light .input-card,
	.chat-page.theme-light .default-tool-expanded,
	.chat-page.theme-light .space-query-expanded-container,
	.chat-page.theme-light .space-mutation-expanded,
	.chat-page.theme-light .chart-expanded-container,
	.chat-page.theme-light .schedule-expanded-container,
	.chat-page.theme-light .review-expanded-container {
		background: var(--chat-surface);
		border-color: var(--chat-border);
		box-shadow: var(--chat-shadow);
	}

	.chat-page.theme-light .input-drawer-stack-active .input-card {
		box-shadow:
			var(--chat-shadow),
			0 18rpx 34rpx rgba(155, 129, 94, 0.10);
	}

	.chat-page.theme-light .space-mutation-confirm-text {
		color: var(--chat-text-secondary);
	}

	.chat-page.theme-light .nav-left {
		outline-color: var(--chat-outline);
	}

	.chat-page.theme-light .nav-icon,
	.chat-page.theme-light .space-query-arrow,
	.chat-page.theme-light .tool-space-arrow,
	.chat-page.theme-light .graph-tool-chevron,
	.chat-page.theme-light .search-indicator-chevron {
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .nav-title,
	.chat-page.theme-light .message-text,
	.chat-page.theme-light .space-query-name,
	.chat-page.theme-light .tool-space-name,
	.chat-page.theme-light .graph-tool-running .graph-tool-pill-text,
	.chat-page.theme-light .schedule-event-time-start,
	.chat-page.theme-light .schedule-event-title,
	.chat-page.theme-light .review-event-label {
		color: var(--chat-text-primary);
	}

	.chat-page.theme-light .bubble-user {
		background-color: var(--chat-accent);
		box-shadow: 0 10rpx 24rpx rgba(47, 110, 234, 0.2);
	}

	.chat-page.theme-light .bubble-user .message-text {
		color: #FFFFFF;
	}

	.chat-page.theme-light .message-image {
		background-color: rgba(63, 53, 42, 0.08);
	}

	.chat-page.theme-light .typing-dot {
		background-color: rgba(31, 26, 22, 0.72);
	}

	.chat-page.theme-light .msg-retry-btn {
		background-color: var(--chat-danger);
	}

	.chat-page.theme-light .space-query-pill,
	.chat-page.theme-light .graph-tool-pill,
	.chat-page.theme-light .search-indicator,
	.chat-page.theme-light .search-source-card,
	.chat-page.theme-light .space-query-results,
	.chat-page.theme-light .schedule-card,
	.chat-page.theme-light .schedule-event-row,
	.chat-page.theme-light .review-card,
	.chat-page.theme-light .review-event-item,
	.chat-page.theme-light .chart-detail-card {
		background: var(--chat-surface);
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .space-query-running,
	.chat-page.theme-light .graph-tool-running,
	.chat-page.theme-light .search-indicator-running,
	.chat-page.theme-light .search-indicator-expanded,
	.chat-page.theme-light .space-query-expanded {
		background: var(--chat-accent-soft);
		border-color: rgba(47, 110, 234, 0.22);
	}

	.chat-page.theme-light .graph-tool-failed {
		background: var(--chat-danger-soft);
		border-color: rgba(209, 79, 79, 0.18);
	}

	.chat-page.theme-light .space-query-text,
	.chat-page.theme-light .space-query-results-title,
	.chat-page.theme-light .search-indicator-text,
	.chat-page.theme-light .search-source-site,
	.chat-page.theme-light .graph-tool-pill-text,
	.chat-page.theme-light .schedule-date-text,
	.chat-page.theme-light .schedule-event-desc,
	.chat-page.theme-light .schedule-card-count,
	.chat-page.theme-light .schedule-empty-text,
	.chat-page.theme-light .review-empty-text,
	.chat-page.theme-light .review-card-count,
	.chat-page.theme-light .review-event-round,
	.chat-page.theme-light .search-tool-empty-text {
		color: var(--chat-text-muted);
	}

	.chat-page.theme-light .search-tool-error-text {
		color: var(--chat-danger);
	}

	.chat-page.theme-light .space-query-results-header,
	.chat-page.theme-light .tool-space-item,
	.chat-page.theme-light .search-source-card,
	.chat-page.theme-light .schedule-expanded-container .graph-tool-pill,
	.chat-page.theme-light .review-expanded-container .graph-tool-pill,
	.chat-page.theme-light .space-query-expanded-container .space-query-pill {
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .space-query-icon,
	.chat-page.theme-light .search-indicator-globe,
	.chat-page.theme-light .graph-tool-pill-icon {
		filter: brightness(0) saturate(100%) invert(34%) sepia(61%) saturate(1869%) hue-rotate(211deg) brightness(96%) contrast(91%);
	}

	.chat-page.theme-light .space-query-results-icon {
		filter: brightness(0) saturate(100%);
		opacity: 0.45;
	}

	.chat-page.theme-light .space-query-spinner,
	.chat-page.theme-light .search-indicator-spinner,
	.chat-page.theme-light .graph-tool-spinner {
		border-color: rgba(47, 110, 234, 0.22);
		border-top-color: var(--chat-accent);
	}

	.chat-page.theme-light .graph-tool-status-icon {
		filter: brightness(0) saturate(100%) invert(37%) sepia(26%) saturate(1030%) hue-rotate(105deg) brightness(92%) contrast(88%);
	}

	.chat-page.theme-light .graph-tool-status-failed {
		filter: brightness(0) saturate(100%) invert(39%) sepia(31%) saturate(2143%) hue-rotate(329deg) brightness(96%) contrast(86%);
	}

	.chat-page.theme-light .tool-btn-cancel {
		background-color: rgba(63, 53, 42, 0.08);
	}

	.chat-page.theme-light .tool-btn-confirm {
		background-color: var(--chat-accent);
	}

	.chat-page.theme-light .tool-btn-cancel .tool-btn-text {
		color: var(--chat-text-primary);
		-webkit-text-fill-color: var(--chat-text-primary);
	}

	.chat-page.theme-light .tool-btn-confirm .tool-btn-text {
		color: #FFFFFF;
		-webkit-text-fill-color: #FFFFFF;
	}

	.chat-page.theme-light .ai-status-badge {
		background: rgba(63, 53, 42, 0.06);
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .ai-status-badge-text,
	.chat-page.theme-light .ai-msg-action-icon:not(.copy-icon-default):not(.copy-icon-check),
	.chat-page.theme-light .user-msg-action-icon,
	.chat-page.theme-light .model-menu-lock {
		color: var(--chat-text-faint);
		filter: brightness(0) saturate(100%);
		opacity: 0.5;
	}

	.chat-page.theme-light .copy-icon-default {
		opacity: 0.5;
		transform: scale(1);
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .copy-icon-default.copy-icon-hide {
		opacity: 0;
		transform: scale(0.6);
	}

	.chat-page.theme-light .copy-icon-check {
		opacity: 0;
		transform: scale(0.6);
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .copy-icon-check.copy-icon-show {
		opacity: 1;
		transform: scale(1);
		filter: brightness(0) saturate(100%) invert(31%) sepia(64%) saturate(1481%) hue-rotate(210deg) brightness(97%) contrast(93%);
	}

	.chat-page.theme-light .ai-msg-action-btn:active,
	.chat-page.theme-light .user-msg-action-btn:active {
		background-color: rgba(63, 53, 42, 0.08);
	}

	.chat-page.theme-light .input-card {
		background-color: rgba(255, 250, 244, 0.94);
		border-color: var(--chat-border);
		box-shadow: var(--chat-shadow);
	}

	.chat-page.theme-light .input-field {
		color: var(--chat-text-primary);
		-webkit-text-fill-color: var(--chat-text-primary);
	}

	.chat-page.theme-light .input-placeholder,
	.chat-page.theme-light .placeholder-text,
	.chat-page.theme-light .input-limit-text {
		color: var(--chat-text-muted);
		-webkit-text-fill-color: var(--chat-text-muted);
	}

	.chat-page.theme-light .input-limit-row {
		background: rgba(63, 53, 42, 0.04);
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .input-limit-counter {
		color: var(--chat-text-secondary);
		-webkit-text-fill-color: var(--chat-text-secondary);
	}

	.chat-page.theme-light .input-action:not(.send-btn-wrapper),
	.chat-page.theme-light .model-selector-btn,
	.chat-page.theme-light .thinking-toggle-btn {
		background: var(--chat-surface-strong);
		border-color: var(--chat-border);
		box-shadow: var(--chat-shadow-soft);
	}

	.chat-page.theme-light .shortcut-pill {
		--shortcut-pill-bg: var(--chat-surface-strong);
		--shortcut-pill-border: var(--chat-border);
		--shortcut-pill-text: var(--chat-text-primary);
		background: var(--chat-surface-strong);
		border-color: var(--chat-border);
		box-shadow: var(--chat-shadow-soft);
	}

	.chat-page.theme-light .shortcut-pill:active {
		background: var(--chat-surface);
		border-color: var(--chat-border-strong);
	}

	.chat-page.theme-light .shortcut-pill-icon {
		filter: brightness(0) saturate(100%);
		opacity: 0.72;
	}

	.chat-page.theme-light .shortcut-pill-text {
		color: var(--chat-text-primary);
		-webkit-text-fill-color: var(--chat-text-primary);
	}

	.chat-page.theme-light .input-action-icon:not(.send-action-icon),
	.chat-page.theme-light .model-selector-icon,
	.chat-page.theme-light .model-selector-chevron,
	.chat-page.theme-light .thinking-toggle-icon {
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .model-selector-label,
	.chat-page.theme-light .thinking-toggle-label,
	.chat-page.theme-light .model-menu-item-name {
		color: var(--chat-text-primary);
		-webkit-text-fill-color: var(--chat-text-primary);
	}

	.chat-page.theme-light .model-menu-item-desc {
		color: var(--chat-text-muted);
		-webkit-text-fill-color: var(--chat-text-muted);
	}

	.chat-page.theme-light .model-menu-item-locked .model-menu-item-name,
	.chat-page.theme-light .model-menu-item-locked .model-menu-item-desc {
		color: var(--chat-text-faint);
		-webkit-text-fill-color: var(--chat-text-faint);
	}

	.chat-page.theme-light .model-menu-item:active,
	.chat-page.theme-light .popup-option:active {
		background: var(--chat-surface-soft);
	}

	.chat-page.theme-light .model-menu-item-active {
		background: var(--chat-accent-soft);
		border-color: rgba(47, 110, 234, 0.22);
		box-shadow:
			inset 0 1rpx 0 rgba(255, 255, 255, 0.58),
			0 4rpx 12rpx rgba(47, 110, 234, 0.12);
	}

	.chat-page.theme-light .model-menu-accent {
		background: rgba(63, 53, 42, 0.08);
	}

	.chat-page.theme-light .model-menu-item-active .model-menu-accent {
		background: linear-gradient(180deg, #6F94F5 0%, var(--chat-accent) 100%);
		box-shadow: 0 0 12rpx rgba(47, 110, 234, 0.24);
	}

	.chat-page.theme-light .thinking-toggle-indicator {
		background: rgba(63, 53, 42, 0.08);
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .thinking-toggle-indicator-active {
		background: rgba(47, 110, 234, 0.24);
		border-color: rgba(47, 110, 234, 0.28);
		box-shadow: 0 0 0 4rpx rgba(47, 110, 234, 0.08);
	}

	.chat-page.theme-light .thinking-label,
	.chat-page.theme-light .thinking-text,
	.chat-page.theme-light .search-source-title {
		color: var(--chat-text-secondary);
	}

	.chat-page.theme-light .thinking-chevron {
		filter: brightness(0) saturate(100%);
		opacity: 0.5;
	}

	.chat-page.theme-light .thinking-body {
		border-left-color: rgba(63, 53, 42, 0.18);
	}

	.chat-page.theme-light .plus-popup {
		border-color: var(--chat-border);
	}

	.chat-page.theme-light .popup-option-icon {
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .popup-option-text {
		color: var(--chat-text-primary);
	}

	.chat-page.theme-light .popup-divider {
		background: var(--chat-border);
	}

	.chat-page.theme-light .popup-arrow {
		border-top-color: rgba(255, 250, 244, 0.95);
	}

	.chat-page.theme-light .pending-attachments-area {
		background-color: transparent;
	}

	.chat-page.theme-light .attachment-image-preview,
	.chat-page.theme-light .attachment-file-preview,
	.chat-page.theme-light .attachment-uploading-item {
		background: rgba(255, 255, 255, 0.68);
		border-color: rgba(63, 53, 42, 0.12);
		box-shadow: var(--chat-shadow-soft);
	}

	.chat-page.theme-light .attachment-file-preview .file-icon,
	.chat-page.theme-light .attachment-uploading-item .file-icon,
	.chat-page.theme-light .remove-icon {
		filter: brightness(0) saturate(100%);
	}

	.chat-page.theme-light .attachment-file-preview .file-name,
	.chat-page.theme-light .attachment-uploading-item .file-name {
		color: var(--chat-text-primary);
	}

	.chat-page.theme-light .attachment-remove-btn {
		background-color: rgba(255, 250, 244, 0.92);
	}

	.chat-page.theme-light .upload-error {
		color: var(--chat-danger);
	}

	.chat-page.theme-light .wave-loading-text,
	.chat-page.theme-light .memory-tool-text {
		background: linear-gradient(
			90deg,
			rgba(122, 111, 98, 0.42) 0%,
			rgba(122, 111, 98, 0.72) 22%,
			rgba(31, 26, 22, 0.92) 44%,
			rgba(122, 111, 98, 0.72) 66%,
			rgba(122, 111, 98, 0.42) 100%
		);
		background-size: 300% 100%;
	}

	.chat-page.theme-light .review-event-depth {
		color: var(--chat-accent);
		background: var(--chat-accent-soft);
	}

	.chat-page.theme-light .review-event-urgency-badge {
		background: var(--chat-success-soft);
	}

	.chat-page.theme-light .review-event-urgency-badge.urgency-overdue {
		background: var(--chat-warning-soft);
	}

	.chat-page.theme-light .review-event-urgency-text {
		color: var(--chat-success);
	}

	.chat-page.theme-light .review-event-urgency-text.urgency-overdue-text {
		color: var(--chat-warning);
	}
</style>
