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
			:scroll-with-animation="scrollAnimationEnabled"
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

					<!-- 用户消息操作图标 -->
					<view v-if="!isAiStreaming" class="user-msg-actions">
						<view class="user-msg-action-btn copy-btn" @click="copyMessage(msg)">
							<image
								class="user-msg-action-icon copy-icon-default"
								:class="{ 'copy-icon-hide': msg.copySuccess }"
								src="/static/icons/phosphor-icons/SVGs/regular/copy.svg"
								mode="aspectFit"
							></image>
							<image
								class="user-msg-action-icon copy-icon-check"
								:class="{ 'copy-icon-show': msg.copySuccess }"
								src="/static/icons/phosphor-icons/SVGs/regular/check.svg"
								mode="aspectFit"
							></image>
						</view>
						<image
							v-if="isLastUserMessage(msg)"
							class="user-msg-action-icon"
							src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg"
							mode="aspectFit"
							@click="editMessage(msg)"
						></image>
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

						<!-- 规划类工具 (get_tool_details)：行内银光掠过 -->
						<view
							v-else-if="seg.type === 'tool' && isPlanningTool(seg.toolCall.tool)"
							:key="'planning-tool-' + segIdx"
							class="planning-tool-inline"
							:class="{
								'planning-tool-active': seg.toolCall.status === 'running',
								'planning-tool-done': seg.toolCall.status === 'done'
							}"
						>
							<text class="planning-tool-text">{{ planningToolText }}</text>
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

						<!-- 测验成绩工具：pill + 可折叠结果卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'view_quiz_results'"
							:key="'quiz-results-' + segIdx"
							class="quiz-tool-wrap"
							:class="{ 'quiz-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- 胶囊指示器 -->
							<view class="quiz-tool-pill"
								:class="{
									'quiz-tool-running': seg.toolCall.status === 'running',
									'quiz-tool-done': seg.toolCall.status === 'done',
									'quiz-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && toggleQuizTool(seg.toolCall.id)"
							>
								<image class="quiz-tool-pill-icon" src="/static/icons/lucide/list-checks.svg" mode="aspectFit" />
								<text class="quiz-tool-pill-text">
									{{ seg.toolCall.status === 'running'
										? '正在查询测验成绩…'
										: (seg.toolCall.success
											? '已查询 ' + (seg.toolCall.result?.quizzes?.length || 0) + ' 份测验'
											: '查询测验成绩失败') }}
								</text>
								<view v-if="seg.toolCall.status === 'running'" class="quiz-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="quiz-tool-chevron"
									:class="{ 'quiz-tool-chevron-up': isQuizToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
							</view>

							<!-- 测验列表卡片 -->
								<view v-if="(isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.quizzes?.length"
									class="quiz-tool-results-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }">
									<view v-for="(quiz, idx) in seg.toolCall.result.quizzes" :key="idx"
										class="quiz-result-item"
										:class="{
											'quiz-result-clickable': getQuizClickAction(quiz) !== 'disabled',
											'quiz-result-evaluating': quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating'
										}"
										@click="onQuizItemClick(quiz)"
									>
										<view class="quiz-result-row">
											<text class="quiz-result-title">{{ quiz.title }}</text>
											<text class="quiz-result-difficulty"
												:class="'difficulty-' + quiz.difficulty">{{ getDifficultyLabel(quiz.difficulty) }}</text>
										</view>
										<view class="quiz-result-meta">
											<text v-if="quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating'"
												class="quiz-result-evaluating-text">评估中</text>
											<text v-else-if="quiz.has_attempt" class="quiz-result-score">{{ quiz.score }}/{{ quiz.total_score }}</text>
											<text v-else class="quiz-result-no-attempt">未作答</text>
											<text class="quiz-result-date">{{ quiz.created_at }}</text>
											<image v-if="getQuizClickAction(quiz) !== 'disabled'"
												class="quiz-result-arrow"
												src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
										</view>
									</view>
								</view>
							<!-- 无测验 -->
								<view v-else-if="(isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && !seg.toolCall.result?.quizzes?.length"
									class="quiz-tool-empty"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }">
									<text class="quiz-tool-empty-text">{{ seg.toolCall.result?.message || '当前学习空间没有测验' }}</text>
								</view>
						</view>

						<!-- 测验详情工具：pill + 可折叠分析卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'view_quiz_attempt_detail'"
							:key="'quiz-detail-' + segIdx"
							class="quiz-tool-wrap"
							:class="{ 'quiz-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- 胶囊指示器 -->
							<view class="quiz-tool-pill"
								:class="{
									'quiz-tool-running': seg.toolCall.status === 'running',
									'quiz-tool-done': seg.toolCall.status === 'done',
									'quiz-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && toggleQuizTool(seg.toolCall.id)"
							>
								<image class="quiz-tool-pill-icon" src="/static/icons/lucide/list-checks.svg" mode="aspectFit" />
								<text class="quiz-tool-pill-text">
									{{ seg.toolCall.status === 'running'
										? '正在分析测验详情…'
										: (seg.toolCall.success
											? '测验分析完成'
											: '测验分析失败') }}
								</text>
								<view v-if="seg.toolCall.status === 'running'" class="quiz-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="quiz-tool-chevron"
									:class="{ 'quiz-tool-chevron-up': isQuizToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
							</view>

							<!-- 详情分析卡片 -->
								<view v-if="(isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result"
									class="quiz-tool-detail-card quiz-tool-detail-clickable"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
									@click="navigateToResult(seg.toolCall.arguments?.quiz_id)">
								<!-- 得分概览区 -->
								<view class="quiz-detail-score-section">
									<view class="quiz-detail-score-header">
										<text class="quiz-detail-score-label">得分</text>
									</view>
									<view class="quiz-detail-score-row">
										<text class="quiz-detail-score-value">{{ seg.toolCall.result.score }}/{{ seg.toolCall.result.total_score }}</text>
										<text class="quiz-detail-score-percent">({{ seg.toolCall.result.percentage }}%)</text>
									</view>
									<view class="quiz-detail-score-bar-bg">
										<view class="quiz-detail-score-bar-fill"
											:style="{ width: (seg.toolCall.result.percentage || 0) + '%' }"
											:class="getScoreBarClass(seg.toolCall.result.percentage)"></view>
									</view>
								</view>

								<!-- 分析区 -->
								<view v-if="seg.toolCall.result.strengths?.length || seg.toolCall.result.weaknesses?.length"
									class="quiz-detail-analysis-section">
									<view class="quiz-detail-analysis-header">
										<text class="quiz-detail-section-title">分析</text>
									</view>

									<!-- 优势 -->
									<view v-if="seg.toolCall.result.strengths?.length" class="quiz-detail-subsection">
										<text class="quiz-detail-subsection-title">优势</text>
										<view v-for="(item, idx) in seg.toolCall.result.strengths" :key="'s-' + idx" class="quiz-detail-tag-item">
											<view class="quiz-detail-dot strength-dot"></view>
											<text class="quiz-detail-tag-text">{{ item }}</text>
										</view>
									</view>

									<!-- 不足 -->
									<view v-if="seg.toolCall.result.weaknesses?.length" class="quiz-detail-subsection">
										<text class="quiz-detail-subsection-title">不足</text>
										<view v-for="(item, idx) in seg.toolCall.result.weaknesses" :key="'w-' + idx" class="quiz-detail-tag-item">
											<view class="quiz-detail-dot weakness-dot"></view>
											<text class="quiz-detail-tag-text">{{ item }}</text>
										</view>
									</view>
								</view>

								<!-- 题目详情区 -->
								<view v-if="seg.toolCall.result.questions?.length" class="quiz-detail-questions-section">
									<view class="quiz-detail-questions-header">
										<text class="quiz-detail-section-title">题目详情</text>
										<text class="quiz-detail-questions-count">{{ seg.toolCall.result.questions.length }} 题</text>
									</view>
									<view v-for="(q, idx) in seg.toolCall.result.questions" :key="'q-' + idx" class="quiz-detail-q-row">
										<text class="quiz-detail-q-order">{{ q.order }}</text>
										<view class="quiz-detail-q-status-dot"
											:class="'status-dot-' + q.status"></view>
										<text class="quiz-detail-q-title">{{ q.title }}</text>
										<text class="quiz-detail-q-score">{{ q.score }}</text>
									</view>
								</view>

								<!-- 查看详情入口 -->
								<view class="quiz-detail-footer">
									<text class="quiz-detail-footer-text">查看完整评估结果</text>
									<image class="quiz-detail-footer-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
								</view>
								</view>
							<!-- 失败 -->
								<view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success && (isQuizToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id))"
									class="quiz-tool-empty"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }">
									<text class="quiz-tool-empty-text">{{ seg.toolCall.result?.message || '获取测验详情失败' }}</text>
								</view>
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
										? (getToolDisplayName(seg.toolCall.tool) + '...')
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

						<!-- 笔记创建工具（自包含 pill + 详情卡片） -->
						<NoteCreationCard
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'create_note'"
							:key="'note-tool-' + segIdx"
							:tool-call="seg.toolCall"
							:space-id="spaceId"
							:conversation-id="conversationId"
						/>

						<!-- 笔记读写工具（自包含 pill + 详情卡片） -->
						<NoteDisplayCard
							v-else-if="seg.type === 'tool' && isNoteReadWriteTool(seg.toolCall.tool)"
							:key="'note-rw-' + segIdx"
							:tool-call="seg.toolCall"
						/>

						<ArtifactGenerationCard
							v-else-if="seg.type === 'tool' && (seg.toolCall.tool === 'create_artifact' || seg.toolCall.tool === 'update_artifact')"
							:key="'artifact-tool-' + segIdx"
							:tool-call="seg.toolCall"
							@view="handleViewArtifact(seg.toolCall)"
						/>

						<!-- 图表生成工具：pill + 可折叠图片详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'generate_chart'"
							:key="'chart-tool-' + segIdx"
							class="chart-tool-wrap"
							:class="{ 'chart-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isChartExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill 指示器（done+success 时可点击折叠/展开） -->
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

							<!-- 详情卡片：图片预览（done + success + 展开时显示） -->
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
								<!-- 自动保存徽章 -->
								<view v-if="seg.toolCall.result?.auto_saved" class="chart-saved-badge">
									<image class="chart-saved-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook-white.svg" mode="aspectFit" />
									<text class="chart-saved-text">已保存为笔记</text>
									<template v-if="seg.toolCall.result?.node_label">
										<text class="chart-saved-text chart-saved-node"> · </text>
										<image class="chart-saved-icon" src="/static/icons/phosphor-icons/SVGs/regular/push-pin-white.svg" mode="aspectFit" />
										<text class="chart-saved-text chart-saved-node">{{ seg.toolCall.result.node_label }}</text>
									</template>
								</view>
							</view>

							<!-- 错误信息（done + failed 时显示） -->
							<view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="chart-error-msg">
								<text class="chart-error-text">{{ seg.toolCall.result?.message || '图表生成失败' }}</text>
							</view>
						</view>

						<!-- 代码执行工具：pill + 可折叠详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'run_python_code'"
							:key="'code-tool-' + segIdx"
						>
							<PythonExecutionCard :tool-call="seg.toolCall" />
						</view>

						<!-- 测试题生成工具：指示器 + 进入卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'generate_test'"
							:key="'quiz-gen-' + segIdx"
							class="quiz-gen-wrap"
						>
							<!-- 指示器 pill -->
							<view class="quiz-gen-indicator"
								:class="{
									'quiz-gen-running': seg.toolCall.status === 'running',
									'quiz-gen-polling': seg.toolCall.status === 'done' && seg.toolCall.success && msg.quizGenerating,
									'quiz-gen-done': seg.toolCall.status === 'done' && seg.toolCall.success && !msg.quizGenerating,
									'quiz-gen-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<!-- 左侧：加载中显示 spinner，完成/失败显示图标 -->
								<view v-if="seg.toolCall.status === 'running' || (seg.toolCall.status === 'done' && seg.toolCall.success && msg.quizGenerating)"
									class="quiz-gen-indicator-spinner"
									:class="{ 'quiz-gen-spinner-amber': seg.toolCall.status === 'done' && msg.quizGenerating }"></view>
								<image v-else class="quiz-gen-indicator-icon"
									src="/static/icons/lucide/list-checks.svg" mode="aspectFit" />
								<!-- 文字 -->
								<text class="quiz-gen-indicator-text">
									{{ seg.toolCall.status === 'running'
										? '启动测试题生成任务中…'
										: (seg.toolCall.success
											? (msg.quizGenerating ? '正在后台生成测试题…' : '已生成测试题')
											: '测试题生成失败') }}
								</text>
								<!-- 右侧：完成显示绿色勾，失败显示红叉 -->
								<image v-if="seg.toolCall.status === 'done' && seg.toolCall.success && !msg.quizGenerating"
									class="quiz-gen-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="quiz-gen-status-icon quiz-gen-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 测试题评估中卡片 -->
							<view
								v-if="msg.type === 'tool-request' && msg.toolState === 'evaluating'"
								class="quiz-entry-card quiz-entry-card--evaluating"
							>
								<view class="quiz-entry-icon-wrap quiz-entry-icon-wrap--evaluating">
									<image class="quiz-entry-icon quiz-evaluating-pulse" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit" />
								</view>
								<view class="quiz-entry-text-col">
									<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
									<text class="quiz-entry-meta quiz-entry-meta--evaluating">AI 正在评估中…</text>
								</view>
							</view>

							<!-- 测试题评估完成卡片 -->
							<view
								v-else-if="msg.type === 'tool-request' && msg.toolState === 'evaluated'"
								class="quiz-entry-card quiz-entry-card--evaluated"
								@click="navigateToResult(msg.quizId)"
							>
								<view class="quiz-entry-icon-wrap quiz-entry-icon-wrap--evaluated">
									<text class="quiz-score-number">{{ msg.quizScore || 0 }}</text>
								</view>
								<view class="quiz-entry-text-col">
									<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
									<text class="quiz-entry-meta quiz-entry-meta--evaluated">评估完成，点击查看详情</text>
								</view>
								<image class="quiz-entry-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
							</view>

							<!-- 测试题进入卡片（紧跟指示器下方） -->
							<view
								v-else-if="msg.type === 'tool-request' && msg.toolState === 'pending'"
								class="quiz-entry-card"
								@click="navigateToTest(msg.id)"
							>
								<view class="quiz-entry-icon-wrap">
									<image class="quiz-entry-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit" />
								</view>
								<view class="quiz-entry-text-col">
									<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
									<text class="quiz-entry-meta">点击进入测试</text>
								</view>
								<image class="quiz-entry-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
							</view>
						</view>

						<!-- 知识图谱概览工具：pill + 详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'get_graph_overview'"
							:key="'graph-overview-' + segIdx"
							class="graph-overview-wrap"
							:class="{ 'gm-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill 指示器 -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片 (done + success + 有快照) -->
								<view
									v-if="(isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && graphMutationSnapshots[seg.toolCall.id]"
									class="graph-overview-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
									@click="showGraphQuickView = true"
								>
								<!-- Header -->
								<view class="graph-overview-header">
									<view class="graph-overview-icon-wrap">
										<image class="graph-overview-icon-img" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
									</view>
									<view class="graph-overview-title-col">
										<text class="graph-overview-title">{{ spaceTitle }}知识图谱</text>
										<text class="graph-overview-meta">{{ graphMutationSnapshots[seg.toolCall.id].nodes.length }} 个节点 · {{ graphMutationSnapshots[seg.toolCall.id].edges.length }} 条边</text>
									</view>
								</view>

								<!-- Divider -->
								<view class="graph-overview-divider"></view>

								<!-- Graph thumbnail -->
								<view class="graph-overview-preview" :style="{ height: graphPreviewHeight + 'px' }">
									<knowledge-tree-mini
										:space-id="spaceId"
										:nodes="graphMutationSnapshots[seg.toolCall.id].nodes"
										:edges="graphMutationSnapshots[seg.toolCall.id].edges"
										:canvas-width="graphPreviewWidth"
										:canvas-height="graphPreviewHeight"
										:force-tree-mode="true"
										:canvas-id-suffix="graphMutationSnapshots[seg.toolCall.id].canvasSuffix"
									/>
									<view class="graph-overview-hint" @click.stop="showGraphQuickView = true">
										<image class="graph-overview-hint-icon" src="/static/icons/phosphor-icons/SVGs/regular/eye.svg" mode="aspectFit" />
										<text class="graph-overview-hint-text">快速查看</text>
									</view>
								</view>
								</view>
						</view>

						<!-- 知识图谱变更工具：pill + 详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isGraphMutationTool(seg.toolCall.tool)"
							:key="'graph-mutation-' + segIdx"
							class="gm-wrap"
							:class="{ 'gm-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill 指示器（复用样式） -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片 (done + success + 有快照数据) -->
								<view
									v-if="(isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && graphMutationSnapshots[seg.toolCall.id]"
									class="gm-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								>
								<!-- Header -->
								<view class="gm-card-header">
									<view class="gm-card-icon-wrap"
										:class="{
											'gm-icon-add': seg.toolCall.tool === 'add_node' || seg.toolCall.tool === 'add_edge',
											'gm-icon-delete': seg.toolCall.tool === 'delete_node' || seg.toolCall.tool === 'delete_edge',
											'gm-icon-update': seg.toolCall.tool === 'update_mastery'
										}"
									>
										<image class="gm-card-icon-img" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
									</view>
									<view class="gm-card-title-col">
										<text class="gm-card-title">{{ getGmCardTitle(seg.toolCall) }}</text>
										<text class="gm-card-meta">{{ getGmCardMeta(seg.toolCall.id) }}</text>
									</view>
								</view>

								<view class="gm-card-divider"></view>

								<!-- 完整知识图谱 + 高亮 -->
								<view class="gm-card-preview" :style="{ height: graphPreviewHeight + 'px' }">
									<knowledge-tree-mini
										:space-id="spaceId"
										:nodes="graphMutationSnapshots[seg.toolCall.id].nodes"
										:edges="graphMutationSnapshots[seg.toolCall.id].edges"
										:canvas-width="graphPreviewWidth"
										:canvas-height="graphPreviewHeight"
										:force-tree-mode="true"
										:canvas-id-suffix="graphMutationSnapshots[seg.toolCall.id].canvasSuffix"
										:highlight-node-labels="graphMutationSnapshots[seg.toolCall.id].highlightNodeLabels"
										:highlight-color="graphMutationSnapshots[seg.toolCall.id].highlightColor"
										:highlight-mode="graphMutationSnapshots[seg.toolCall.id].highlightMode"
									/>
								</view>
								</view>
						</view>

						<!-- 知识图谱查询工具：pill + 详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isGraphQueryTool(seg.toolCall.tool)"
							:key="'graph-query-' + segIdx"
							class="gm-wrap"
							:class="{ 'gm-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill 指示器 -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片 (done + success + 有快照数据) -->
								<view
									v-if="(isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && graphMutationSnapshots[seg.toolCall.id]"
									class="gm-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								>
								<view class="gm-card-header">
									<view class="gm-card-icon-wrap gm-icon-query">
										<image class="gm-card-icon-img" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
									</view>
									<view class="gm-card-title-col">
										<text class="gm-card-title">{{ getGmCardTitle(seg.toolCall) }}</text>
										<text class="gm-card-meta">{{ getGmCardMeta(seg.toolCall.id) }}</text>
									</view>
								</view>
								<view class="gm-card-divider"></view>
								<view class="gm-card-preview" :style="{ height: graphPreviewHeight + 'px' }">
									<knowledge-tree-mini
										:space-id="spaceId"
										:nodes="graphMutationSnapshots[seg.toolCall.id].nodes"
										:edges="graphMutationSnapshots[seg.toolCall.id].edges"
										:canvas-width="graphPreviewWidth"
										:canvas-height="graphPreviewHeight"
										:force-tree-mode="true"
										:canvas-id-suffix="graphMutationSnapshots[seg.toolCall.id].canvasSuffix"
										:highlight-node-labels="graphMutationSnapshots[seg.toolCall.id].highlightNodeLabels"
										:highlight-color="graphMutationSnapshots[seg.toolCall.id].highlightColor"
										:highlight-mode="graphMutationSnapshots[seg.toolCall.id].highlightMode"
									/>
								</view>
								</view>
						</view>

						<!-- 学习路径工具：pill + 详情卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isLearningPathTool(seg.toolCall.tool)"
							:key="'lp-tool-' + segIdx"
							class="gm-wrap"
							:class="{ 'gm-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill 指示器 -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片 (done + success + 有快照数据) -->
								<view
									v-if="(isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && graphMutationSnapshots[seg.toolCall.id]"
									class="gm-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								>
								<view class="gm-card-header">
									<view class="gm-card-icon-wrap"
										:class="{
											'gm-icon-path-generate': seg.toolCall.tool === 'generate_learning_path',
											'gm-icon-path-modify': seg.toolCall.tool !== 'generate_learning_path'
										}"
									>
										<image class="gm-card-icon-img" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
									</view>
									<view class="gm-card-title-col">
										<text class="gm-card-title">{{ getGmCardTitle(seg.toolCall) }}</text>
										<text class="gm-card-meta">{{ getGmCardMeta(seg.toolCall.id) }}</text>
									</view>
								</view>
								<view class="gm-card-divider"></view>
								<view class="gm-card-preview" :style="{ height: graphPreviewHeight + 'px' }">
									<knowledge-tree-mini
										:space-id="spaceId"
										:nodes="graphMutationSnapshots[seg.toolCall.id].nodes"
										:edges="graphMutationSnapshots[seg.toolCall.id].edges"
										:canvas-width="graphPreviewWidth"
										:canvas-height="graphPreviewHeight"
										:force-tree-mode="false"
										:canvas-id-suffix="graphMutationSnapshots[seg.toolCall.id].canvasSuffix"
										:highlight-node-labels="graphMutationSnapshots[seg.toolCall.id].highlightNodeLabels"
										:highlight-color="graphMutationSnapshots[seg.toolCall.id].highlightColor"
										:highlight-mode="graphMutationSnapshots[seg.toolCall.id].highlightMode"
										:highlight-edge-pairs="graphMutationSnapshots[seg.toolCall.id].highlightEdgePairs || []"
										:highlight-edge-color="graphMutationSnapshots[seg.toolCall.id].highlightEdgeColor || '#FFD93D'"
									/>
								</view>
								</view>
						</view>

						<!-- 后序遍历工具：pill + 知识图谱卡片 -->
						<view
							v-else-if="seg.type === 'tool' && isPostorderTool(seg.toolCall.tool)"
							:key="'postorder-' + segIdx"
							class="gm-wrap"
							:class="{ 'gm-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) }"
						>
							<!-- pill -->
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
								@click="seg.toolCall.status === 'done' && seg.toolCall.success && toggleGraphTool(seg.toolCall.id)"
							>
								<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-chevron"
									:class="{ 'graph-tool-chevron-up': isGraphToolExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>

							<!-- 详情卡片 (done + success + 有快照) -->
								<view
									v-if="(isGraphToolExpanded(seg.toolCall.id) || isToolCollapsing(seg.toolCall.id)) && seg.toolCall.status === 'done' && seg.toolCall.success && graphMutationSnapshots[seg.toolCall.id]"
									class="gm-card"
									:class="{ 'tool-card-leave': isToolCollapsing(seg.toolCall.id) }"
								>
								<view class="gm-card-header">
									<view class="gm-card-icon-wrap gm-icon-postorder">
										<image class="gm-card-icon-img" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
									</view>
									<view class="gm-card-title-col">
										<text class="gm-card-title">{{ getGmCardTitle(seg.toolCall) }}</text>
										<text class="gm-card-meta">{{ getGmCardMeta(seg.toolCall.id) }}</text>
									</view>
								</view>
								<view class="gm-card-divider"></view>
								<view class="gm-card-preview" :style="{ height: graphPreviewHeight + 'px' }">
									<knowledge-tree-mini
										:space-id="spaceId"
										:nodes="graphMutationSnapshots[seg.toolCall.id].nodes"
										:edges="graphMutationSnapshots[seg.toolCall.id].edges"
										:canvas-width="graphPreviewWidth"
										:canvas-height="graphPreviewHeight"
										:force-tree-mode="true"
										:canvas-id-suffix="graphMutationSnapshots[seg.toolCall.id].canvasSuffix"
										:highlight-node-labels="graphMutationSnapshots[seg.toolCall.id].highlightNodeLabels"
										:highlight-color="graphMutationSnapshots[seg.toolCall.id].highlightColor"
										:highlight-mode="graphMutationSnapshots[seg.toolCall.id].highlightMode"
									/>
								</view>
								</view>
						</view>

						<!-- 其他知识图谱工具：行内 pill -->
						<view
							v-else-if="seg.type === 'tool' && isGraphToolButNotOverview(seg.toolCall.tool)"
							:key="'graph-tool-' + segIdx"
							class="graph-tool-pill"
							:class="{
								'graph-tool-running': seg.toolCall.status === 'running',
								'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
								'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
							}"
						>
							<image class="graph-tool-pill-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
							<text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
							<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
							<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
								class="graph-tool-status-icon"
								src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
							<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
								class="graph-tool-status-icon graph-tool-status-failed"
								src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
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
								<!-- get_schedule 用 chevron（可展开） -->
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

						<!-- 文档检索工具：pill-only -->
						<view
							v-else-if="seg.type === 'tool' && isDocRetrievalTool(seg.toolCall.tool)"
							:key="'doc-tool-' + segIdx"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getDocRetrievalToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>
						</view>

						<!-- 知识库保存工具：pill -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'save_to_knowledge_base'"
							:key="'kb-tool-' + segIdx"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getKBToolText(seg.toolCall) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
							</view>
						</view>

						<!-- 深度爬取工具：pill + 可展开页面列表 -->
						<view
							v-else-if="seg.type === 'tool' && seg.toolCall.tool === 'web_crawl'"
							:key="'crawl-tool-' + segIdx"
							class="search-tool-wrap"
						>
							<!-- 指示器 pill -->
							<view class="search-indicator"
								:class="{
									'search-indicator-running': seg.toolCall.status === 'running',
									'search-indicator-expanded': seg.toolCall.status === 'done' && isSearchExpanded(seg.toolCall.id),
									'search-indicator-collapsed': seg.toolCall.status === 'done' && !isSearchExpanded(seg.toolCall.id)
								}"
								@click="toggleSearchResults(seg.toolCall.id)">
								<image class="search-indicator-globe"
									:src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="search-indicator-text">
									{{ seg.toolCall.status === 'running'
										? '正在深度爬取网站…'
										: '已爬取 ' + (seg.toolCall.result?.pages?.length || 0) + ' 个页面' }}
								</text>
								<view v-if="seg.toolCall.status === 'running'" class="search-indicator-spinner"></view>
								<image v-else class="search-indicator-chevron"
									:class="{ 'search-chevron-up': isSearchExpanded(seg.toolCall.id) }"
									src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
							</view>

							<!-- 爬取页面卡片横向滚动 -->
							<scroll-view
								v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.pages?.length && isSearchExpanded(seg.toolCall.id)"
								class="search-sources-scroll" scroll-x :show-scrollbar="false">
								<view class="search-sources-row">
									<view v-for="(page, idx) in seg.toolCall.result.pages" :key="idx"
										class="search-source-card" @click="openSearchResultUrl(page.url)">
										<view class="search-source-head">
											<view class="search-source-num">
												<text class="search-source-num-text">{{ idx + 1 }}</text>
											</view>
											<text class="search-source-site">{{ formatDisplayUrl(page.url) }}</text>
										</view>
										<text class="search-source-title">{{ page.title }}</text>
									</view>
								</view>
							</scroll-view>

							<!-- 无结果 -->
							<view v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success && !seg.toolCall.result?.pages?.length" class="search-tool-empty">
								<text class="search-tool-empty-text">{{ seg.toolCall.result?.message || '未爬取到页面' }}</text>
							</view>

							<!-- 失败 -->
							<view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="search-tool-error">
								<text class="search-tool-error-text">{{ seg.toolCall.result?.message || '深度爬取失败' }}</text>
							</view>
						</view>

						<!-- 默认工具：pill 胶囊样式 -->
						<view
							v-else-if="seg.type === 'tool'"
							:key="'tool-' + segIdx"
							class="default-tool-wrap"
						>
							<view class="graph-tool-pill"
								:class="{
									'graph-tool-running': seg.toolCall.status === 'running',
									'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
								}"
							>
								<image class="graph-tool-pill-icon" :src="getToolIcon(seg.toolCall.tool)" mode="aspectFit" />
								<text class="graph-tool-pill-text">{{ getToolDisplayName(seg.toolCall.tool) }}</text>
								<view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
								<image v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success"
									class="graph-tool-status-icon"
									src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
								<image v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success"
									class="graph-tool-status-icon graph-tool-status-failed"
									src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
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

					<!-- 测试题评估中卡片 (evaluating 状态，仅旧路径) -->
					<view
						v-if="msg.type === 'tool-request' && msg.toolState === 'evaluating' && !hasQuizGenSegment(msg)"
						class="quiz-entry-card quiz-entry-card--evaluating"
					>
						<view class="quiz-entry-icon-wrap quiz-entry-icon-wrap--evaluating">
							<image class="quiz-entry-icon quiz-evaluating-pulse" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit" />
						</view>
						<view class="quiz-entry-text-col">
							<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
							<text class="quiz-entry-meta quiz-entry-meta--evaluating">AI 正在评估中…</text>
						</view>
					</view>

					<!-- 测试题评估完成卡片 (evaluated 状态，仅旧路径) -->
					<view
						v-else-if="msg.type === 'tool-request' && msg.toolState === 'evaluated' && !hasQuizGenSegment(msg)"
						class="quiz-entry-card quiz-entry-card--evaluated"
						@click="navigateToResult(msg.quizId)"
					>
						<view class="quiz-entry-icon-wrap quiz-entry-icon-wrap--evaluated">
							<text class="quiz-score-number">{{ msg.quizScore || 0 }}</text>
						</view>
						<view class="quiz-entry-text-col">
							<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
							<text class="quiz-entry-meta quiz-entry-meta--evaluated">评估完成，点击查看详情</text>
						</view>
						<image class="quiz-entry-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
					</view>

					<!-- 测试题进入卡片 (pending 状态，仅旧路径无 generate_test 工具段时显示) -->
					<view
						v-else-if="msg.type === 'tool-request' && msg.toolState === 'pending' && !hasQuizGenSegment(msg)"
						class="quiz-entry-card"
						@click="navigateToTest(msg.id)"
					>
						<view class="quiz-entry-icon-wrap">
							<image class="quiz-entry-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit" />
						</view>
						<view class="quiz-entry-text-col">
							<text class="quiz-entry-title">{{ spaceTitle }} · 测试题</text>
							<text class="quiz-entry-meta">点击进入测试</text>
						</view>
						<image class="quiz-entry-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit" />
					</view>

					<!-- 引用来源列表 -->
					<view v-if="msg.citations && msg.citations.length && !msg.isStreaming" class="citation-footer">
						<view class="citation-footer-header">
							<image class="citation-footer-icon" src="/static/icons/lucide/book-search.svg" mode="aspectFit" />
							<text class="citation-footer-label">参考来源</text>
						</view>
						<view
							v-for="cite in msg.citations"
							:key="cite.index"
							class="citation-item"
							@click="openCitationSource(cite)"
						>
							<text class="citation-index">[{{ cite.index }}]</text>
							<view class="citation-info">
								<text class="citation-title">{{ cite.title }}</text>
								<text v-if="cite.page_number" class="citation-meta">第{{ cite.page_number }}页</text>
								<text v-if="cite.source_type === 'web'" class="citation-meta">{{ getDomain(cite.url) }}</text>
								<text v-if="cite.source_type === 'academic'" class="citation-meta">学术论文</text>
							</view>
							<image v-if="cite.url" class="citation-arrow"
								src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit" />
						</view>
					</view>

					<!-- AI 消息操作图标 (流式输出完成后显示，排除未完成的工具请求) -->
					<view v-if="msg.role === 'ai' && !msg.isStreaming && (msg.type !== 'tool-request' || msg.toolState === 'accepted' || msg.toolState === 'rejected' || msg.toolState === 'evaluating' || msg.toolState === 'evaluated')" class="ai-msg-actions">
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
						<view
							class="ai-msg-action-btn"
							:class="{ 'action-btn-active': msg.isBookmarked }"
							@click="toggleBookmark(msg)"
						>
							<image
								class="ai-msg-action-icon"
								src="/static/icons/phosphor-icons/SVGs/regular/bookmark-simple.svg"
								mode="aspectFit"
							></image>
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
			:actionText="snackbarActionType === 'view_result' ? '查看' : '进入'"
			actionIcon="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg"
			:duration="snackbarActionType === 'view_result' ? 6000 : 4000"
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
						<text
							class="model-menu-item-name"
							:style="{ color: m.locked ? '#9CA3AF' : '#C7CBD4', '-webkit-text-fill-color': m.locked ? '#9CA3AF' : '#C7CBD4' }"
						>{{ m.display_name }}</text>
						<text
							class="model-menu-item-desc"
							:style="{ color: '#A1A1AA', '-webkit-text-fill-color': '#A1A1AA' }"
						>{{ m.locked ? '升级订阅解锁' : m.description }}</text>
					</view>
					<image v-if="m.locked" class="model-menu-lock" src="/static/icons/phosphor-icons/SVGs/regular/lock.svg" mode="aspectFit"></image>
				</view>
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
					<!-- 左侧：模型选择 pill -->
					<view class="input-bottom-left">
						<view v-if="availableModels.length > 0" class="model-selector-btn" @click="toggleModelMenu">
							<image class="model-selector-icon" src="/static/icons/phosphor-icons/SVGs/regular/faders.svg" mode="aspectFit"></image>
							<text
								class="model-selector-label"
								:style="{ color: '#C7CBD4', '-webkit-text-fill-color': '#C7CBD4' }"
							>{{ selectedModelName }}</text>
							<image class="model-selector-chevron" src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit"></image>
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

		<!-- 知识图谱快速预览弹窗 -->
		<view
			v-if="showGraphQuickView && graphOverviewData"
			class="graph-quick-view-overlay"
			@click="showGraphQuickView = false"
		>
			<view class="graph-quick-view-panel" @click.stop>
				<!-- 头部 -->
				<view class="graph-quick-view-header">
					<view class="graph-quick-view-title-row">
						<image class="graph-quick-view-title-icon" src="/static/icons/git-pull-request.svg" mode="aspectFit" />
						<text class="graph-quick-view-title">{{ spaceTitle }}知识图谱</text>
					</view>
					<view class="graph-quick-view-close" @click="showGraphQuickView = false">
						<image class="graph-quick-view-close-icon" src="/static/icons/phosphor-icons/SVGs/regular/x.svg" mode="aspectFit" />
					</view>
				</view>

				<!-- 元信息 -->
				<text class="graph-quick-view-meta">{{ graphOverviewData.nodes.length }} 个节点 · {{ graphOverviewData.edges.length }} 条边</text>

				<!-- 图谱画布（可拖动/缩放） -->
				<view class="graph-quick-view-canvas" :style="{ height: graphQuickViewHeight + 'px' }">
					<knowledge-tree-mini
						:space-id="spaceId"
						:nodes="graphOverviewData.nodes"
						:edges="graphOverviewData.edges"
						:canvas-width="graphQuickViewWidth"
						:canvas-height="graphQuickViewHeight"
						:force-tree-mode="true"
						:interactive="true"
						:show-all-labels="true"
						canvas-id-suffix="_quickview"
					/>
				</view>
			</view>
		</view>

		<!-- 引用详情抽屉 -->
		<view v-if="showCitationDetail" class="cite-drawer-wrapper" @touchmove.stop.prevent>
			<view class="cite-drawer-overlay" :class="{ 'overlay-show': citationDetailAnimVisible }" @click="closeCitationDetail" />
			<view class="cite-drawer-container" :class="{ 'drawer-show': citationDetailAnimVisible }">
				<view class="cite-drawer-handle"><view class="handle-bar" /></view>
				<view class="cite-drawer-header">
					<view class="cite-drawer-badge">[{{ citationDetail.index }}]</view>
					<view class="cite-drawer-title-col">
						<text class="cite-drawer-title">{{ citationDetail.title }}</text>
						<view class="cite-drawer-meta-row">
							<text v-if="citationDetail.page_number" class="cite-drawer-meta">第{{ citationDetail.page_number }}页</text>
							<text v-if="citationDetail.source_type === 'web'" class="cite-drawer-meta">{{ getDomain(citationDetail.url) }}</text>
							<text v-if="citationDetail.source_type === 'academic'" class="cite-drawer-meta">学术论文</text>
							<text v-if="citationDetail.score" class="cite-drawer-meta">相关度 {{ Math.round(citationDetail.score * 100) }}%</text>
						</view>
					</view>
				</view>
				<scroll-view scroll-y class="cite-drawer-body">
					<text class="cite-drawer-content">{{ citationDetail.content || citationDetail.snippet || '' }}</text>
				</scroll-view>
				<view v-if="citationDetail.url" class="cite-drawer-footer">
					<view class="cite-drawer-open-btn" @click="openCitationUrl(citationDetail.url)">
						<image class="cite-drawer-open-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit" />
						<text class="cite-drawer-open-text">打开链接</text>
					</view>
				</view>
			</view>
		</view>

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
	import UCapsuleToast from '@/components/u-capsule-toast/u-capsule-toast.vue'
	import USnackbar from '@/components/u-snackbar/u-snackbar.vue'
	import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
	import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
	import PreKnowledgeCard from '@/components/pre-knowledge-card/pre-knowledge-card.vue'
	import ImageSourcePicker from '@/components/image-source-picker/image-source-picker.vue'
	import NoteCreationCard from '@/components/note-creation-card/note-creation-card.vue'
	import NoteDisplayCard from '@/components/note-display-card/note-display-card.vue'
	import ArtifactGenerationCard from '@/components/artifact-generation-card/artifact-generation-card.vue'
	import PythonExecutionCard from '@/components/python-execution-card/python-execution-card.vue'
	import KnowledgeTreeMini from '@/components/knowledge-tree-mini/knowledge-tree-mini.vue'
	import { generateQuiz, getTaskStatus, getSpaceGraph } from '@/api/space'
	import { createConversation, getConversation, sendMessage as sendChatMessage, submitFeedback, submitToolResult, getModels, getStreamingStatus, rollbackLastMessage } from '@/api/chat'
	import { connectNotificationStream } from '@/api/notification'
	import { executeCalendarTool } from '@/utils/calendar'
	import { createCalendarEvent, getCalendarEvents, updateCalendarEvent, deleteCalendarEvent } from '@/api/calendarEvents'
	import { uploadAttachment, deleteAttachment } from '@/api/attachment'
	import { PreKnowledgeTagParser } from '@/utils/preKnowledgeParser'
	import { chooseLocalFiles, isPickerCancel, getPickerErrorMessage } from '@/utils/filePicker'
	import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError, connectSSE } from '@/utils/sse'
	import { savePendingMessage, getPendingMessages, removePendingMessage, savePendingMessagesFromArray, clearPendingMessages } from '@/utils/messageDraft'
	import { startBackgroundMonitor, stopBackgroundMonitor, getActiveMonitor } from '@/utils/backgroundChatMonitor'
	import { consumeAllPending } from '@/utils/quizEvaluationBus'
	import { createNote } from '@/api/note'
	import { ensureAlbumWritePermission, ensureCameraPermission, isPermissionDenied, guideToSettings } from '@/utils/permission'
	// #ifdef APP-PLUS
	import SseRenderjs from '@/components/sse-renderjs/sse-renderjs.vue'
	// #endif

	// 工具名称映射
	const TOOL_DISPLAY_NAMES = {
		// 快速对话独有工具（重绑定后在此页面显示）
		view_learning_spaces: '查看学习空间',
		rebind_to_learning_space: '绑定到学习空间',
		create_learning_space: '创建学习空间',
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
		extend_learning_path: '延伸学习路径',
		update_learning_path_segment: '更新路径段',
		get_learning_paths: '获取学习路径',
		delete_all_learning_paths: '删除所有路径',
		get_postorder_traversal: '获取后序遍历',
		// 日程管理工具
		get_current_time: '获取当前时间',
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
		delete_from_space_memory: '删除空间记忆',
		// 复习事件工具
		get_review_events: '查看复习事件',
		mark_review_completed: '标记复习完成',
		// 测验成绩查看
		view_quiz_results: '查看测验成绩',
		view_quiz_attempt_detail: '查看测验详情',
		// 多渠道搜索工具
		academic_search: '学术搜索',
		encyclopedia_search: '百科搜索',
		course_search: 'B站课程搜索',
		// 笔记工具
		create_note: '创建笔记',
		list_notes: '查看笔记',
		view_note_detail: '查看笔记详情',
		update_note: '更新笔记',
		delete_note: '删除笔记',
		// 图表生成工具
		generate_chart: '生成图表',
		// 交互演示工具
		create_artifact: '创建交互演示',
		update_artifact: '更新交互演示',
		// 代码执行工具
		run_python_code: '执行 Python 代码',
		// 知识库管理
		save_to_knowledge_base: '保存到知识库',
		// 深度爬取
		web_crawl: '深度爬取网站'
	}

	// 工具图标映射
	const TOOL_ICONS = {
		// 快速对话独有工具（重绑定后在此页面显示）
		view_learning_spaces: '/static/icons/phosphor-icons/SVGs/regular/eye.svg',
		rebind_to_learning_space: '/static/icons/phosphor-icons/SVGs/regular/link.svg',
		create_learning_space: '/static/icons/phosphor-icons/SVGs/regular/plus-circle.svg',
		// 知识图谱工具
		get_graph_overview: '/static/icons/phosphor-icons/SVGs/regular/graph.svg',
		add_node: '/static/icons/phosphor-icons/SVGs/regular/plus-circle.svg',
		add_edge: '/static/icons/phosphor-icons/SVGs/regular/git-merge.svg',
		delete_node: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
		delete_edge: '/static/icons/phosphor-icons/SVGs/regular/link-break.svg',
		update_mastery: '/static/icons/phosphor-icons/SVGs/regular/graduation-cap.svg',
		get_child_nodes: '/static/icons/lucide/git-merge.svg',
		get_parent_nodes: '/static/icons/lucide/git-branch.svg',
		get_sibling_nodes: '/static/icons/lucide/git-pull-request-draft.svg',
		generate_learning_path: '/static/icons/phosphor-icons/SVGs/regular/flow-arrow.svg',
		extend_learning_path: '/static/icons/phosphor-icons/SVGs/regular/flow-arrow.svg',
		update_learning_path_segment: '/static/icons/phosphor-icons/SVGs/regular/arrows-left-right.svg',
		get_learning_paths: '/static/icons/phosphor-icons/SVGs/regular/path.svg',
		delete_all_learning_paths: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
		get_postorder_traversal: '/static/icons/phosphor-icons/SVGs/regular/tree-structure.svg',
		// 日程管理工具
		get_current_time: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
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
		delete_from_space_memory: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
		// 复习事件工具
		get_review_events: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
		mark_review_completed: '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
		// 测验成绩查看
		view_quiz_results: '/static/icons/phosphor-icons/SVGs/regular/list-checks.svg',
		view_quiz_attempt_detail: '/static/icons/phosphor-icons/SVGs/regular/chart-bar.svg',
		// 多渠道搜索工具
		academic_search: '/static/icons/phosphor-icons/SVGs/regular/graduation-cap.svg',
		encyclopedia_search: '/static/icons/phosphor-icons/SVGs/regular/books.svg',
		course_search: '/static/icons/phosphor-icons/SVGs/regular/globe.svg',
		// 笔记工具
		create_note: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
		list_notes: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
		view_note_detail: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
		update_note: '/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg',
		delete_note: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
		// 图表生成工具
		generate_chart: '/static/icons/lucide/chart-area.svg',
		// 交互演示工具
		create_artifact: '/static/icons/phosphor-icons/SVGs/regular/code.svg',
		update_artifact: '/static/icons/phosphor-icons/SVGs/regular/code.svg',
		// 代码执行工具
		run_python_code: '/static/icons/phosphor-icons/SVGs/regular/code.svg',
		// 知识库管理
		save_to_knowledge_base: '/static/icons/phosphor-icons/SVGs/regular/bookmark-simple.svg',
		// 深度爬取
		web_crawl: '/static/icons/phosphor-icons/SVGs/regular/globe.svg'
	}

	// 规划类工具（行内银光掠过效果）
	const PLANNING_TOOLS = new Set(['get_tool_details'])
	const PLANNING_TOOL_TEXT = '正在规划下一步……'

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

	// 知识图谱类工具集合（使用行内 pill 而非卡片）
	const GRAPH_TOOLS = new Set([
		'get_graph_overview',
		'add_node',
		'add_edge',
		'delete_node',
		'delete_edge',
		'update_mastery',
		'get_child_nodes',
		'get_parent_nodes',
		'get_sibling_nodes',
		'generate_learning_path',
		'extend_learning_path',
		'update_learning_path_segment',
		'get_learning_paths',
		'delete_all_learning_paths',
		'get_postorder_traversal'
	])

	// 知识图谱变更工具（有详情卡片 + 动画）
	const GRAPH_MUTATION_TOOLS = new Set([
		'add_node', 'add_edge', 'update_mastery'
	])

	// 知识图谱查询工具（有详情卡片 + 高亮）
	const GRAPH_QUERY_TOOLS = new Set([
		'get_child_nodes', 'get_parent_nodes', 'get_sibling_nodes'
	])

	// 详情卡片默认折叠的工具（需要手动点击展开）
	const GRAPH_DEFAULT_COLLAPSED = new Set([
		'get_child_nodes', 'get_parent_nodes', 'get_sibling_nodes',
		'get_postorder_traversal', 'add_edge'
	])

	// 学习路径工具（有详情卡片 + path mode 渲染 + 边高亮）
	const LEARNING_PATH_TOOLS = new Set([
		'generate_learning_path', 'extend_learning_path', 'update_learning_path_segment'
	])

	// 知识图谱工具显示文字 { running, done, failed }
	const GRAPH_TOOL_TEXT = {
		get_graph_overview:        { running: '正在查看知识图谱…',   done: '已查看知识图谱',   failed: '查看知识图谱失败' },
		add_node:                  { running: '正在添加知识节点…',   done: '已添加知识节点',   failed: '添加知识节点失败' },
		add_edge:                  { running: '正在添加知识关系…',   done: '已添加知识关系',   failed: '添加知识关系失败' },
		delete_node:               { running: '正在删除知识节点…',   done: '已删除知识节点',   failed: '删除知识节点失败' },
		delete_edge:               { running: '正在删除知识关系…',   done: '已删除知识关系',   failed: '删除知识关系失败' },
		update_mastery:            { running: '正在更新掌握度…',     done: '已更新掌握度',     failed: '更新掌握度失败' },
		get_child_nodes:           { running: '正在获取子节点…',     done: '已获取子节点',     failed: '获取子节点失败' },
		get_parent_nodes:          { running: '正在获取父节点…',     done: '已获取父节点',     failed: '获取父节点失败' },
		get_sibling_nodes:         { running: '正在获取兄弟节点…',   done: '已获取兄弟节点',   failed: '获取兄弟节点失败' },
		generate_learning_path:    { running: '正在生成学习路径…',   done: '已生成学习路径',   failed: '生成学习路径失败' },
		extend_learning_path:          { running: '正在延伸学习路径…',   done: '已延伸学习路径',   failed: '延伸学习路径失败' },
		update_learning_path_segment:  { running: '正在更新路径段…',     done: '已更新路径段',     failed: '更新路径段失败' },
		get_learning_paths:        { running: '正在获取学习路径…',   done: '已获取学习路径',   failed: '获取学习路径失败' },
		delete_all_learning_paths: { running: '正在删除学习路径…',   done: '已删除学习路径',   failed: '删除学习路径失败' },
		get_postorder_traversal:   { running: '正在遍历知识图谱…',   done: '已遍历知识图谱',   failed: '遍历知识图谱失败' }
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

	// 笔记读写工具集合（不含 create_note，那个由 NoteCreationCard 处理）
	const NOTE_RW_TOOLS = new Set([
		'list_notes', 'view_note_detail', 'update_note', 'delete_note'
	])

	// 复习工具集合
	const REVIEW_TOOLS = new Set([
		'get_review_events', 'mark_review_completed'
	])

	// 复习工具显示文字 { running, done, failed }
	const REVIEW_TOOL_TEXT = {
		get_review_events:      { running: '正在查看复习事项…', done: '查看复习事项', failed: '获取复习事项失败' },
		mark_review_completed:  { running: '正在标记复习完成…', done: '已标记复习完成', failed: '标记复习失败' }
	}

	// 文档检索类工具（pill-only，无详情卡片）
	const DOC_RETRIEVAL_TOOLS = new Set([
		'search_documents', 'web_fetch'
	])

	const DOC_RETRIEVAL_TOOL_TEXT = {
		search_documents: { running: '正在搜索文档…', done: '已搜索文档', failed: '搜索文档失败' },
		web_fetch:        { running: '正在获取网页…', done: '已获取网页', failed: '获取网页失败' }
	}

	export default {
		components: {
			UCapsuleToast,
			USnackbar,
			UInputModal,
			MarkdownRender,
			PreKnowledgeCard,
			ImageSourcePicker,
			NoteCreationCard,
			NoteDisplayCard,
			ArtifactGenerationCard,
			PythonExecutionCard,
			KnowledgeTreeMini,
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
				_initialWindowHeight: 0, // 键盘弹出前的窗口高度，用于检测 adjustResize
				nextId: 1,
				activeMoreMsgId: null,

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

				// thinking 打字机缓冲
				thinkingBuffer: '',
				thinkingTimer: null,
				thinkingMsgId: null,

				// 测试题 Snackbar 相关
				showTestSnackbar: false,
				snackbarMessage: '测试题已生成',
				snackbarActionType: 'enter_quiz', // 'enter_quiz' | 'view_result'
				pendingEvalQuizId: null,

				// 调试日志（quiz progress indicator 使用）
				debugLogs: [],
				isGeneratingQuiz: false,

				// 测试生成进度指示器
				quizProgressPhase: 'idle',  // 'idle' | 'generating' | 'completing' | 'done'
				quizProgressValue: 0,       // 0-100 进度值

				// 记忆工具最短显示时间跟踪
				memoryToolStartTimes: {},    // { toolCallId: timestamp }
				memoryToolDelayedDone: {}, // { toolCallId: true } 延迟隐藏的工具ID

				// 搜索结果展开状态
				expandedSearchResults: {}, // { toolCallId: true }
				expandedQuizTools: {}, // { toolCallId: true/false }
				expandedGraphTools: {}, // { toolCallId: true/false }
				collapsingTools: {}, // { toolCallId: true } — 正在播放折叠动画
				// 图表详情卡片展开状态（默认展开）
				expandedChartDetails: {}, // { toolCallId: true/false }

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

				// 模型选择
				availableModels: [],
				selectedModelId: null,
				showModelMenu: false,

				// 后台监控：最后一条用户消息的发送时间
				lastUserMessageTimestamp: null,

				// 知识图谱概览卡片
				graphOverviewData: null,
				graphPreviewWidth: 200,
				graphPreviewHeight: 110,

				// 图谱快速预览弹窗
				showGraphQuickView: false,
				graphQuickViewWidth: 300,
				graphQuickViewHeight: 300,

				// 图谱变更工具快照
				graphMutationSnapshots: {},
				gmCanvasCounter: 0,

				// 引用详情抽屉
				citationDetail: null,
				showCitationDetail: false,
				citationDetailAnimVisible: false
			}
		},

		computed: {
			planningToolText() {
				return PLANNING_TOOL_TEXT
			},
			isAiStreaming() {
				return this.messages.some(msg => msg.role === 'ai' && msg.isStreaming)
			},
			canSend() {
				return this.inputText.trim().length > 0
			},
			selectedModelName() {
				const model = this.availableModels.find(m => m.id === this.selectedModelId)
				return model ? model.display_name : '模型'
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

			// 计算图谱概览预览尺寸
			this.calculateGraphPreviewSize()

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

			// 加载模型列表
			this.loadModels()

			// 监听测试评估完成事件
			uni.$on('quizEvaluationDone', this.handleQuizEvaluationDone)
		},

		onShow() {
			// 同步已保存的模型选择
			const storedId = uni.getStorageSync('uStudy_selectedModelId')
			if (storedId && this.availableModels.some(m => m.id === storedId)) {
				this.selectedModelId = storedId
			}

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

			// 检查已完成的后台测试评估结果（处理 race condition：API 可能在 onShow 之前返回）
			const pendingEvals = consumeAllPending()
			for (const quizId in pendingEvals) {
				this.handleQuizEvaluationDone({ quizId, ...pendingEvals[quizId] })
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
			// 记录初始窗口高度，用于判断 adjustResize 是否生效
			this._initialWindowHeight = uni.getSystemInfoSync().windowHeight
			console.log(`[SpaceChat-KB] mounted: initialWindowH=${this._initialWindowHeight}`)

			// #ifdef APP-PLUS
			if (this.$refs.sseRenderjs) {
				setSseEventBus(this.$refs.sseRenderjs)
			}
			// #endif

			// 建立通知 SSE 连接
			this.setupNotificationStream()

			this.$nextTick(() => {
				// #ifdef H5
				this.adjustTextareaHeight()
				// #endif
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
				const sysInfo = uni.getSystemInfoSync()
				console.log(`[SpaceChat-KB] keyboardHeightChange: height=${res.height}px, windowH=${sysInfo.windowHeight}, initWindowH=${this._initialWindowHeight}, platform=${sysInfo.platform}, model=${sysInfo.model}`)

				// Android: 系统通过 adjustPan(平移) 或 adjustResize(缩小viewport) 自动处理键盘避让，
				// position:fixed 的输入栏已经被系统移到键盘上方，不需要再手动设 bottom 偏移，
				// 否则会与系统行为双重叠加，导致输入框被顶到屏幕顶部（vivo 等机型尤为明显）
				// iOS: 系统不自动处理 webview 键盘避让，需要手动设 bottom 偏移
				if (sysInfo.platform === 'android') {
					this.keyboardHeight = 0
				} else {
					this.keyboardHeight = res.height
				}

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

			// 清理测试评估监听
			uni.$off('quizEvaluationDone', this.handleQuizEvaluationDone)

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
				// #ifdef H5
				this.$nextTick(() => {
					this.adjustTextareaHeight()
				})
				// #endif
			}
		},

		methods: {
			// ==================== 模型选择 ====================
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
				uni.setStorageSync('uStudy_selectedModelId', id)
			},
			async loadModels() {
				try {
					const res = await getModels()
					const models = res.models || res || []
					this.availableModels = models
					const storedId = uni.getStorageSync('uStudy_selectedModelId')
					const storedModel = models.find(m => m.id === storedId)
					if (storedModel && !storedModel.locked) {
						this.selectedModelId = storedId
					} else {
						const defaultModel = models.find(m => m.is_default && !m.locked)
						this.selectedModelId = defaultModel ? defaultModel.id : (models.find(m => !m.locked)?.id || null)
					}
				} catch (err) {
					console.error('[SpaceChat] Failed to load models:', err)
				}
			},

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
			removeMasteryNotification(id) {
				this.masteryNotifications = this.masteryNotifications.filter(n => n.id !== id)
			},

			setupNotificationStream() {
				this.notificationAbort = connectNotificationStream({
					onMasteryUpdate: (data) => {
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
					onArtifactStream: (data) => {
						this.onArtifactStream(data)
					},
					onArtifactReady: (data) => {
						this.onArtifactReady(data)
					},
					onConnected: ({ isReconnect }) => {
						if (isReconnect) {
							this.restoreArtifactToolCalls({ onlyGenerating: true })
						}
					}
				})
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

					// 批量取出多个字符，减少 reactivity 触发频率
					const chunkSize = Math.min(3, this.typewriterBuffer.length)
					const chunk = this.typewriterBuffer.slice(0, chunkSize)
					this.typewriterBuffer = this.typewriterBuffer.slice(chunkSize)

					// 更新消息内容
					const msg = this.messages.find(m => m.id === this.typewriterMsgId)
					if (msg) {
						msg.content = msg.content + chunk
					}
				}, 80)
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

			// 监听滚动事件，检测用户手动滚动
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

			// 停止高度监听
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

			/**
			 * 从后台恢复时的处理
			 * 优先从 Redis 获取流式状态，避免丢失正在生成的内容
			 */
			async recoverFromBackground() {
				if (!this.conversationId) return

				console.log('[SpaceChat] recoverFromBackground start')

				this.flushTypewriter()
				this.preKnowledgeParser = null

				try {
					// 1. 先检查 Redis 流式状态
					const status = await getStreamingStatus(this.conversationId)
					console.log('[SpaceChat] Redis status:', status.is_streaming, 'content length:', status.partial_content?.length)

					if (status.is_streaming || status.partial_content) {
						// AI 仍在生成或有缓存内容，从 Redis 恢复
						this.resumeStreamingFromRedis(status)
						return
					}

					// 2. Redis 缓存已过期，从数据库加载完整对话
					const result = await getConversation(this.conversationId)
					this.messages = result.messages.map((m, i) => {
						const msg = {
							id: i + 1,
							role: m.role === 'user' ? 'user' : 'ai',
							content: m.content,
							attachments: m.attachments || [],
							citations: m.citations || null,
							created_at: m.created_at
						}
						if (msg.role === 'ai' && m.tool_calls && m.tool_calls.length > 0) {
							const segments = m.tool_calls.map(tc => ({ type: 'tool', toolCall: { ...tc } }))
							if (m.content && m.content.trim()) {
								segments.push({ type: 'text', content: m.content })
							}
							msg.segments = segments
							msg.toolCalls = m.tool_calls
						}
						// 恢复图谱变更快照
						if (msg.segments) {
							for (const seg of msg.segments) {
								if (seg.type === 'tool' && seg.toolCall &&
									seg.toolCall.tool === 'get_graph_overview' &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareGraphOverviewSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									GRAPH_MUTATION_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result) {
									this.prepareGraphMutationSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall.result)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									GRAPH_QUERY_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareGraphQuerySnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									LEARNING_PATH_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareLearningPathSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									seg.toolCall.tool === 'get_postorder_traversal' &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.preparePostorderSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
							}
						}
						return msg
					})
					this.nextId = this.messages.length + 1
					clearPendingMessages(this.conversationId)
					await this.restoreArtifactToolCalls({ onlyGenerating: true })
					this.$nextTick(() => this.scrollToLatestMessage())
				} catch (err) {
					console.warn('[SpaceChat] recoverFromBackground failed:', err)
					// 恢复失败时保留当前消息，不覆盖
				} finally {
					this.activeToolCalls = []
					this.isSendingMessage = false
					this.stopHeightMonitor()
				}
			},

			/**
			 * 从 Redis 流式状态恢复
			 */
			resumeStreamingFromRedis(status) {
				// 找到正在流式的 AI 消息
				let aiMsg = this.messages.find(m => m.role === 'ai' && m.isStreaming)

				if (!aiMsg && status.partial_content) {
					// 页面状态可能丢失，根据 Redis 数据创建 AI 消息
					aiMsg = {
						id: this.nextId++,
						role: 'ai',
						content: '',
						isStreaming: true,
						citations: null,
					}
					this.messages.push(aiMsg)
				}

				if (!aiMsg) return

				// 更新已生成的内容
				aiMsg.content = status.partial_content || ''
				if (status.partial_thinking) {
					aiMsg.thinkingContent = status.partial_thinking
				}

				console.log('[SpaceChat] Restored content from Redis, length:', aiMsg.content.length)

				// 如果 AI 仍在生成，重连 SSE
				if (status.is_streaming) {
					this.reconnectToResumeStream(aiMsg, aiMsg.content.length)
				} else {
					// 已完成，标记结束
					aiMsg.isStreaming = false
					this.cancelSSE = null
				}

				this.$nextTick(() => this.scrollToLatestMessage())
			},

			/**
			 * 重连到 resume-stream 端点继续接收
			 */
			reconnectToResumeStream(aiMsg, offset) {
				console.log('[SpaceChat] Reconnecting to resume-stream, offset:', offset)

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
							// done 事件的 content 是完整内容，如果有且不是续传就用它
							if (data.content && !data.resumed) {
								aiMsg.content = data.content
							}
							aiMsg.citations = data.citations || null
						}
					},
					onComplete: () => {
						aiMsg.isStreaming = false
						this.cancelSSE = null
						stopBackgroundMonitor()
					},
					onError: (err) => {
						console.warn('[SpaceChat] Resume SSE error:', err)
						// 重连失败不标记错误，后台监控会继续处理
					},
				})
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
				this.textareaLineCount = 1
				this.textareaHeight = 'auto'
				this.textareaOverflow = 'hidden'
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
					thinkingContent: '',
					isThinkingExpanded: true,
					thinkingStartTime: 0,
					thinkingDuration: 0,
					isStreaming: true,
					isWaitingOutput: true,
					citations: null
				})
				this.scrollToLatestMessage()
				this.startHeightMonitor(aiMsgId)
				this.activeToolCalls = []

				// 发送消息并处理 SSE
				this.cancelSSE = sendChatMessage(this.conversationId, text, {
					onThinking: (content) => {
						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg) {
							if (msg.isWaitingOutput) msg.isWaitingOutput = false
							if (!msg.thinkingStartTime) {
								msg.thinkingStartTime = Date.now()
							}
							this.appendThinkingText(aiMsgId, content)
						}
					},

					onTextDelta: (content) => {
						// Auto-collapse thinking + calculate duration
						const thinkMsg = this.messages.find(m => m.id === aiMsgId)
						if (thinkMsg && thinkMsg.isThinkingExpanded) {
							this.flushThinkingBuffer()
							thinkMsg.isThinkingExpanded = false
							if (thinkMsg.thinkingStartTime) {
								thinkMsg.thinkingDuration = Math.round((Date.now() - thinkMsg.thinkingStartTime) / 1000)
							}
						}
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

					onDone: (fullContent, citations) => {
						// 先刷新缓冲区中剩余内容
						this.flushThinkingBuffer()
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
										const resolved = tc ? {
											...tc,
											arguments: tc.arguments ? { ...tc.arguments } : null,
											result: tc.result ? { ...tc.result } : null
										} : { ...seg.toolCall }
										// done 事件已到达，所有工具必定已完成；强制修正未收到 tool_call(done) 的残留 running 状态
										if (resolved.status === 'running') {
											resolved.status = 'done'
											resolved.success = true
										}
										finalSegments.push({ type: 'tool', toolCall: resolved })
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
							// [debug] 检查日程工具片段
							for (const fs of finalSegments) {
								if (fs.type === 'tool' && SCHEDULE_TOOLS.has(fs.toolCall?.tool)) {
									console.log('[schedule-debug] onDone finalSeg:', fs.toolCall.tool, 'status:', fs.toolCall.status, 'success:', fs.toolCall.success, 'result keys:', fs.toolCall.result ? Object.keys(fs.toolCall.result) : 'null', 'expanded:', this.expandedGraphTools[fs.toolCall.id])
								}
							}
							// 保存完整文本用于复制等功能
							msg.content = fullContent
							// 保存引用来源
							msg.citations = citations || null
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

					onQuotaError: (info) => {
						this.flushThinkingBuffer()
						this.flushTypewriter()
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
						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg) {
							msg.content = shortText
							msg.isWaitingOutput = false
							msg.isStreaming = false
							msg.isError = true
						}
						this.stopHeightMonitor()
					},

					onError: (message) => {
						// 后台断连时不标记失败（后台监控会处理）
						if (this.isBackgroundMonitorActive()) return

						// 出错时也要清理打字机
						this.flushThinkingBuffer()
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
							this.flushThinkingBuffer()
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
				}, attachmentIds.length > 0 ? attachmentIds : null, this.selectedModelId)
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
				this.messages.push({ id: aiMsgId, role: 'ai', content: '', thinkingContent: '', isThinkingExpanded: true, thinkingStartTime: 0, thinkingDuration: 0, isStreaming: true, isWaitingOutput: true, citations: null })
				this.scrollToLatestMessage()
				this.startHeightMonitor(aiMsgId)
				this.activeToolCalls = []

				this.cancelSSE = sendChatMessage(this.conversationId, text, {
					onThinking: (content) => {
						const msg = this.messages.find(m => m.id === aiMsgId)
						if (msg) {
							if (msg.isWaitingOutput) msg.isWaitingOutput = false
							if (!msg.thinkingStartTime) {
								msg.thinkingStartTime = Date.now()
							}
							this.appendThinkingText(aiMsgId, content)
						}
					},
					onTextDelta: (content) => {
						// Auto-collapse thinking + calculate duration
						const thinkMsg = this.messages.find(m => m.id === aiMsgId)
						if (thinkMsg && thinkMsg.isThinkingExpanded) {
							this.flushThinkingBuffer()
							thinkMsg.isThinkingExpanded = false
							if (thinkMsg.thinkingStartTime) {
								thinkMsg.thinkingDuration = Math.round((Date.now() - thinkMsg.thinkingStartTime) / 1000)
							}
						}
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
					onDone: (fullContent, citations) => {
						this.flushThinkingBuffer()
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
										const resolved = tc ? { ...tc } : { ...seg.toolCall }
										// done 事件已到达，所有工具必定已完成；强制修正未收到 tool_call(done) 的残留 running 状态
										if (resolved.status === 'running') {
											resolved.status = 'done'
											resolved.success = true
										}
										finalSegments.push({ type: 'tool', toolCall: resolved })
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
							aiMsg.citations = citations || null
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
					onQuotaError: (info) => {
						this.flushThinkingBuffer()
						this.flushTypewriter()
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
						const aiMsg = this.messages.find(m => m.id === aiMsgId)
						if (aiMsg) {
							aiMsg.content = shortText
							aiMsg.isWaitingOutput = false
							aiMsg.isStreaming = false
							aiMsg.isError = true
						}
						this.stopHeightMonitor()
					},
					onError: (message) => {
						this.flushThinkingBuffer()
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
							this.flushThinkingBuffer()
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
				}, attachmentIds && attachmentIds.length > 0 ? attachmentIds : null, this.selectedModelId)
			},

			/**
			 * 加载对话历史消息
			 */
			async loadConversationHistory() {
				this.isLoadingHistory = true
				try {
					const result = await getConversation(this.conversationId)
					this.messages = result.messages.map((m, i) => {
						const msg = {
							id: i + 1,
							role: m.role === 'user' ? 'user' : 'ai',
							content: m.content,
							attachments: m.attachments || [],
							citations: m.citations || null,
							created_at: m.created_at
						}
						if (msg.role === 'ai' && m.tool_calls && m.tool_calls.length > 0) {
							const segments = m.tool_calls.map(tc => ({ type: 'tool', toolCall: { ...tc } }))
							if (m.content && m.content.trim()) {
								segments.push({ type: 'text', content: m.content })
							}
							msg.segments = segments
							msg.toolCalls = m.tool_calls
						}
						// 恢复图谱变更快照
						if (msg.segments) {
							for (const seg of msg.segments) {
								if (seg.type === 'tool' && seg.toolCall &&
									seg.toolCall.tool === 'get_graph_overview' &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareGraphOverviewSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									GRAPH_MUTATION_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result) {
									this.prepareGraphMutationSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall.result)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									GRAPH_QUERY_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareGraphQuerySnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									LEARNING_PATH_TOOLS.has(seg.toolCall.tool) &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.prepareLearningPathSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
								if (seg.type === 'tool' && seg.toolCall &&
									seg.toolCall.tool === 'get_postorder_traversal' &&
									seg.toolCall.status === 'done' && seg.toolCall.success) {
									this.preparePostorderSnapshot(seg.toolCall.id, seg.toolCall.tool, seg.toolCall)
								}
							}
						}
						return msg
					})
					this.nextId = this.messages.length + 1
					// 后台监控 active 时，服务器数据已包含完整回复，清空缓存避免重复
					const monitor = getActiveMonitor()
					if (monitor && monitor.conversationId === this.conversationId) {
						clearPendingMessages(this.conversationId)
					} else {
						this.mergePendingMessages()
					}
					await this.restoreArtifactToolCalls({ onlyGenerating: true })
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

				if (status === 'running' || status === 'pending_confirmation' || !status) {
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
					const toolCall = { id, tool, arguments: args, status: status || 'running' }

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
						// 客户端工具已由前端完成，跳过后端 SSE 的重复 done 事件（防止覆盖 result）
						if (toolCall._clientDone) return

						toolCall.status = 'done'
						toolCall.success = success
						toolCall.result = result
						if (args) toolCall.arguments = args
						if (SCHEDULE_TOOLS.has(tool)) {
							console.log('[schedule-debug] handleToolCallEvent done:', tool, 'success:', success, 'result type:', typeof result, 'result:', JSON.stringify(result)?.slice(0, 200))
						}

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

						// 如果是知识图谱概览工具完成，准备快照
						if (tool === 'get_graph_overview' && success) {
							this.prepareGraphOverviewSnapshot(id, tool, toolCall)
						}

						// 图谱变更工具完成 → 准备快照
						if (GRAPH_MUTATION_TOOLS.has(tool) && success) {
							this.prepareGraphMutationSnapshot(id, tool, result)
						}

						// 图谱查询工具完成 → 准备快照
						if (GRAPH_QUERY_TOOLS.has(tool) && success) {
							this.prepareGraphQuerySnapshot(id, tool, toolCall)
						}

						// 学习路径工具完成 → 准备快照
						if (LEARNING_PATH_TOOLS.has(tool) && success) {
							this.prepareLearningPathSnapshot(id, tool, toolCall)
						}

						// 后序遍历工具完成 → 准备快照
						if (tool === 'get_postorder_traversal' && success) {
							this.preparePostorderSnapshot(id, tool, toolCall)
						}

						// 学习路径工具完成，通知 learningSpace 页面刷新
						if (LEARNING_PATH_TOOLS.has(tool) && success) {
							uni.$emit('learningPathUpdated')
						}

						// 如果是测试生成工具完成，启动后台轮询
						if (tool === 'generate_test' && success && result?.task_id) {
							this.handleGenerateTestToolCompletion(aiMsgId, result.task_id)
						}
					}
					// 同步更新 streamSegments 中的工具片段（用新数组引用确保响应式更新）
					if (msg.streamSegments) {
						msg.streamSegments = msg.streamSegments.map(s => {
							if (s.type === 'tool' && s.toolCall && s.toolCall.id === id && toolCall) {
								return { type: 'tool', toolCall: { ...toolCall } }
							}
							return s
						})
					}
				}

				// 触发 UI 更新
				this.$forceUpdate()
			},

			/**
			 * 处理客户端工具请求（日历操作、笔记创建等）
			 * 后端通过 SSE 发送 client_tool_request → 前端执行或展示确认UI → POST 结果回后端
			 */
			async handleClientToolRequest(aiMsgId, data) {
				const { tool_call_id, tool, params } = data

				// create_note: 展示确认卡片，由 NoteCreationCard 组件处理确认/取消
				if (tool === 'create_note') {
					const msg = this.messages.find(m => m.id === aiMsgId)
					if (!msg) return

					const existing = this.activeToolCalls.find(tc => tc.id === tool_call_id)
					if (existing) {
						// tool_call(running) already created it — update status in-place
						existing.status = 'pending_confirmation'
						existing.arguments = params

						// Sync to streamSegments
						if (msg.streamSegments) {
							const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === tool_call_id)
							if (seg) {
								seg.toolCall = { ...existing }
							}
						}
					} else {
						// Fallback: no prior tool_call(running) — create fresh
						this.handleToolCallEvent(aiMsgId, {
							id: tool_call_id,
							tool,
							status: 'pending_confirmation',
							arguments: params
						})
					}

					this.$forceUpdate()
					return
				}

				// 日历工具等：自动执行
				this.handleToolCallEvent(aiMsgId, {
					id: tool_call_id,
					tool,
					status: 'running',
					arguments: params
				})

				const calendarResult = await executeCalendarTool(tool, params)

				// Dual-write: sync to backend DB (best-effort, don't block)
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

				// 标记为客户端已完成，防止后端 tool_call(done) SSE 覆盖 result
				const clientTc = this.activeToolCalls.find(tc => tc.id === tool_call_id)
				if (clientTc) clientTc._clientDone = true
			},

			/**
			 * Sync calendar tool results to backend DB (dual-write)
			 * Best-effort — Android calendar is primary, backend is secondary
			 */
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
						// Try to find and delete by external_id
						const events = await getCalendarEvents(
							new Date(Date.now() - 365 * 86400000).toISOString(),
							new Date(Date.now() + 365 * 86400000).toISOString()
						)
						const match = (events || []).find(e => e.external_id === String(params.schedule_id))
						if (match) {
							await deleteCalendarEvent(match.id)
						}
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
					// get_schedule doesn't need backend sync
				} catch (err) {
					console.warn('syncCalendarToBackend error:', err)
				}
			},

			/**
			 * Convert "YYYY-MM-DD HH:MM" to ISO string
			 */
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
					// fallback: 直接用 scheme 打开
					plus.runtime.openURL('content://com.android.calendar/time/' + Date.now())
				}
				// #endif
				// #ifdef H5
				uni.showToast({ title: '请在手机端打开日历', icon: 'none' })
				// #endif
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

			getChartToolText(toolCall) {
				if (toolCall.status === 'running') return '正在生成图表…'
				if (toolCall.status === 'done' && toolCall.success) return '已生成图表'
				if (toolCall.status === 'done' && !toolCall.success) return '图表生成失败'
				return '生成图表'
			},

			// ===== Artifact 辅助方法 =====
			isArtifactTool(toolName) {
				return toolName === 'create_artifact' || toolName === 'update_artifact'
			},
			handleViewArtifact(toolCall) {
				const noteId = toolCall.result?.note_id
				if (!noteId) return
				uni.navigateTo({
					url: `/pages/artifactViewer/artifactViewer?spaceId=${this.spaceId}&noteId=${noteId}`
				})
			},
			walkArtifactToolCalls(visitor) {
				for (const msg of this.messages) {
					for (const segmentKey of ['segments', 'streamSegments']) {
						const segments = msg[segmentKey]
						if (!Array.isArray(segments)) continue
						for (let index = 0; index < segments.length; index++) {
							const seg = segments[index]
							if (seg?.type === 'tool' && this.isArtifactTool(seg.toolCall?.tool)) {
								if (visitor(seg, msg, segmentKey, index)) {
									return true
								}
							}
						}
					}
				}
				return false
			},
			applyArtifactSnapshot(payload, { appendDelta = false } = {}) {
				const {
					taskId,
					noteId,
					title,
					status,
					delta,
					codeSnapshot,
					htmlSize,
					errorMessage
				} = payload
				let updated = false

				this.walkArtifactToolCalls((seg) => {
					const currentResult = seg.toolCall?.result || {}
					if (taskId) {
						if (String(currentResult.task_id) !== String(taskId)) return false
					} else if (noteId) {
						if (String(currentResult.note_id) !== String(noteId)) return false
					} else {
						return false
					}

					const nextResult = { ...currentResult }
					if (taskId) nextResult.task_id = taskId
					if (noteId) nextResult.note_id = noteId
					if (title) {
						nextResult.artifact_title = title
						if (!nextResult.title) {
							nextResult.title = title
						}
					}
					if (status) {
						nextResult.status = status
						nextResult.artifact_progress_status = status
					}
					if (typeof codeSnapshot === 'string') {
						nextResult.code_snapshot = codeSnapshot
					} else if (appendDelta && delta) {
						nextResult.code_snapshot = `${nextResult.code_snapshot || ''}${delta}`
					}
					if (typeof htmlSize === 'number') {
						nextResult.html_size = htmlSize
					}
					if (errorMessage) {
						nextResult.message = errorMessage
					}

					seg.toolCall = {
						...seg.toolCall,
						result: nextResult
					}
					updated = true
					return true
				})

				if (updated) {
					this.$forceUpdate()
				}
				return updated
			},
			resolveArtifactTaskStatus(taskResult) {
				if (taskResult.artifact_progress_status) {
					return taskResult.artifact_progress_status
				}
				if (taskResult.status === 'failed') return 'failed'
				if (taskResult.status === 'done') return 'done'
				return 'streaming'
			},
			async refreshArtifactTaskSnapshot(taskId) {
				if (!taskId) return null
				try {
					const taskResult = await getTaskStatus(taskId)
					if (taskResult.task_type !== 'generate_artifact') {
						return taskResult
					}

					this.applyArtifactSnapshot({
						taskId,
						noteId: taskResult.note_id,
						title: taskResult.artifact_title,
						status: this.resolveArtifactTaskStatus(taskResult),
						codeSnapshot: typeof taskResult.code_snapshot === 'string' ? taskResult.code_snapshot : undefined,
						htmlSize: typeof taskResult.html_size === 'number' ? taskResult.html_size : undefined,
						errorMessage: taskResult.error_message || ''
					})
					return taskResult
				} catch (error) {
					console.warn('[SpaceChat] refreshArtifactTaskSnapshot failed:', taskId, error)
					return null
				}
			},
			async restoreArtifactToolCalls({ onlyGenerating = true } = {}) {
				const taskIds = new Set()
				this.walkArtifactToolCalls((seg) => {
					const taskId = seg.toolCall?.result?.task_id
					const currentStatus = seg.toolCall?.result?.artifact_progress_status || seg.toolCall?.result?.status
					if (!taskId) return false
					if (
						onlyGenerating &&
						currentStatus !== 'generating' &&
						currentStatus !== 'streaming'
					) {
						return false
					}
					taskIds.add(taskId)
					return false
				})

				if (!taskIds.size) return
				await Promise.allSettled(
					Array.from(taskIds).map(taskId => this.refreshArtifactTaskSnapshot(taskId))
				)
			},
			onArtifactStream(data) {
				const { note_id, space_id, task_id, title, status, delta } = data || {}
				if (String(space_id) !== String(this.spaceId)) return
				this.applyArtifactSnapshot({
					taskId: task_id,
					noteId: note_id,
					title,
					status: status || 'streaming',
					delta
				}, { appendDelta: true })
			},
			async onArtifactReady(data) {
				const { note_id, space_id, task_id, status, title, error_message } = data || {}
				if (String(space_id) !== String(this.spaceId)) return

				const refreshed = task_id ? await this.refreshArtifactTaskSnapshot(task_id) : null
				if (task_id) {
					if (!refreshed) {
						this.applyArtifactSnapshot({
							taskId: task_id,
							noteId: note_id,
							title,
							status,
							errorMessage: error_message || ''
						})
					}
				} else {
					this.applyArtifactSnapshot({
						taskId: task_id,
						noteId: note_id,
						title,
						status,
						errorMessage: error_message || ''
					})
				}

				if (status === 'done') {
					uni.showToast({ title: `「${title || '交互演示'}」已生成`, icon: 'none', duration: 3000 })
				} else if (status === 'failed') {
					uni.showToast({ title: '演示生成失败', icon: 'none', duration: 3000 })
				}
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
			 * 判断是否为规划类工具
			 */
			isPlanningTool(toolName) {
				return PLANNING_TOOLS.has(toolName)
			},

			isGraphTool(toolName) {
				return GRAPH_TOOLS.has(toolName)
			},

			getGraphToolText(toolCall) {
				const texts = GRAPH_TOOL_TEXT[toolCall.tool]
				if (!texts) return toolCall.tool
				if (toolCall.status === 'running') return texts.running
				if (toolCall.status === 'done' && toolCall.success) return texts.done
				return texts.failed
			},

			isGraphToolButNotOverview(toolName) {
				return GRAPH_TOOLS.has(toolName)
					&& toolName !== 'get_graph_overview'
					&& !GRAPH_MUTATION_TOOLS.has(toolName)
					&& !GRAPH_QUERY_TOOLS.has(toolName)
					&& !LEARNING_PATH_TOOLS.has(toolName)
					&& toolName !== 'get_postorder_traversal'
			},

			isPostorderTool(toolName) {
				return toolName === 'get_postorder_traversal'
			},

			isGraphMutationTool(toolName) {
				return GRAPH_MUTATION_TOOLS.has(toolName)
			},

			isGraphQueryTool(toolName) {
				return GRAPH_QUERY_TOOLS.has(toolName)
			},

			isLearningPathTool(toolName) {
				return LEARNING_PATH_TOOLS.has(toolName)
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

			getKBToolText(toolCall) {
				if (toolCall.status === 'running') {
					return '正在保存到知识库…'
				}
				if (toolCall.status === 'done' && toolCall.success) {
					let title = toolCall.result?.data?.title || toolCall.arguments?.title || ''
					if (title.length > 20) title = title.slice(0, 20) + '…'
					return title ? `已保存「${title}」` : '已保存到知识库'
				}
				if (toolCall.status === 'done' && !toolCall.success) {
					return '保存失败'
				}
				return '保存到知识库'
			},

			isNoteReadWriteTool(toolName) {
				return NOTE_RW_TOOLS.has(toolName)
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

			calculateGraphPreviewSize() {
				const systemInfo = uni.getSystemInfoSync()
				const cardWidth = systemInfo.windowWidth * 0.75 - 48
				this.graphPreviewWidth = Math.floor(cardWidth)
				this.graphPreviewHeight = Math.floor(cardWidth * 0.55)

				// 快速预览弹窗：面板宽度 - 两侧 padding (24rpx * 2 = 48rpx)
				// rpx→px: rpx * windowWidth / 750
				const pxPerRpx = systemInfo.windowWidth / 750
				const panelPadding = 40 * 2 * pxPerRpx   // overlay padding 40rpx * 2
				const canvasPadding = 24 * 2 * pxPerRpx  // canvas margin 24rpx * 2
				const panelBorder = 2 * pxPerRpx         // borders
				const panelMaxWidth = 700 * pxPerRpx
				const panelWidth = Math.min(systemInfo.windowWidth - panelPadding, panelMaxWidth)
				const quickViewWidth = panelWidth - canvasPadding - panelBorder
				this.graphQuickViewWidth = Math.floor(quickViewWidth)
				this.graphQuickViewHeight = Math.floor(quickViewWidth * 0.75)
			},

			async loadGraphOverviewData() {
				try {
					const data = await getSpaceGraph(this.spaceId)
					if (data && data.nodes && data.nodes.length > 0) {
						this.graphOverviewData = {
							nodes: data.nodes.map(n => ({
								id: n.id,
								label: n.label || n.title || n.name,
								mastery: n.mastery
							})),
							edges: (data.edges || []).map(e => ({
								from: e.from_node_id || e.from,
								to: e.to_node_id || e.to,
								type: e.type || 'knowledge_tree'
							}))
						}
					}
				} catch (err) {
					console.error('[spaceChat] loadGraphOverviewData failed:', err)
				}
			},

			async prepareGraphOverviewSnapshot(toolCallId, tool, toolCall) {
				const suffix = '_ov_' + (++this.gmCanvasCounter)

				// 重新加载最新图谱数据
				await this.loadGraphOverviewData()
				if (!this.graphOverviewData) return

				this.graphMutationSnapshots = {
					...this.graphMutationSnapshots,
					[toolCallId]: {
						nodes: [...this.graphOverviewData.nodes],
						edges: [...this.graphOverviewData.edges],
						highlightNodeLabels: [],
						highlightColor: null,
						highlightMode: 'static',
						canvasSuffix: suffix
					}
				}
				this.$forceUpdate()
			},

			async prepareGraphMutationSnapshot(toolCallId, tool, result) {
				if (GRAPH_DEFAULT_COLLAPSED.has(tool) && this.expandedGraphTools[toolCallId] === undefined) {
					this.expandedGraphTools = { ...this.expandedGraphTools, [toolCallId]: false }
				}
				const isDelete = tool === 'delete_node' || tool === 'delete_edge'
				const suffix = '_gm_' + (++this.gmCanvasCounter)

				if (isDelete) {
					// 删除操作：先用旧数据快照（被删项还在），延迟刷新
					if (!this.graphOverviewData) {
						await this.loadGraphOverviewData()
					}
					if (this.graphOverviewData) {
						this.graphMutationSnapshots = {
							...this.graphMutationSnapshots,
							[toolCallId]: {
								nodes: [...this.graphOverviewData.nodes],
								edges: [...this.graphOverviewData.edges],
								highlightNodeLabels: this.extractHighlightLabels(tool, result),
								highlightColor: '#EF4444',
								highlightMode: 'static',
								canvasSuffix: suffix
							}
						}
						this.$forceUpdate()
					}
					// 2.5s 后刷新为删除后的真实数据
					setTimeout(async () => {
						await this.loadGraphOverviewData()
						if (this.graphOverviewData && this.graphMutationSnapshots[toolCallId]) {
							this.graphMutationSnapshots = {
								...this.graphMutationSnapshots,
								[toolCallId]: {
									...this.graphMutationSnapshots[toolCallId],
									nodes: [...this.graphOverviewData.nodes],
									edges: [...this.graphOverviewData.edges],
									highlightNodeLabels: [],
									highlightMode: 'static'
								}
							}
							this.$forceUpdate()
						}
					}, 2500)
				} else {
					// add / update：先刷新再快照
					await this.loadGraphOverviewData()
					if (this.graphOverviewData) {
						this.graphMutationSnapshots = {
							...this.graphMutationSnapshots,
							[toolCallId]: {
								nodes: [...this.graphOverviewData.nodes],
								edges: [...this.graphOverviewData.edges],
								highlightNodeLabels: this.extractHighlightLabels(tool, result),
								highlightColor: tool === 'update_mastery' ? '#49FFAA' : '#4A6CF7',
								highlightMode: 'static',
								canvasSuffix: suffix
							}
						}
						this.$forceUpdate()
					}
				}
			},

			extractHighlightLabels(tool, result) {
				if (!result) return []
				switch (tool) {
					case 'add_node':
						return [result.label].filter(Boolean)
					case 'add_edge':
						return [result.from_node, result.to_node].filter(Boolean)
					case 'delete_node':
						return [result.deleted_node_name].filter(Boolean)
					case 'delete_edge':
						return [result.from_node, result.to_node].filter(Boolean)
					case 'update_mastery':
						return [result.node_name].filter(Boolean)
					default:
						return []
				}
			},

			async prepareGraphQuerySnapshot(toolCallId, tool, toolCall) {
				if (GRAPH_DEFAULT_COLLAPSED.has(tool) && this.expandedGraphTools[toolCallId] === undefined) {
					this.expandedGraphTools = { ...this.expandedGraphTools, [toolCallId]: false }
				}
				const suffix = '_gq_' + (++this.gmCanvasCounter)
				const nodeName = toolCall.arguments?.node_name
				if (!nodeName) return

				if (!this.graphOverviewData) {
					await this.loadGraphOverviewData()
				}
				if (!this.graphOverviewData) return

				const highlights = this.computeQueryHighlights(tool, nodeName, this.graphOverviewData)

				this.graphMutationSnapshots = {
					...this.graphMutationSnapshots,
					[toolCallId]: {
						nodes: [...this.graphOverviewData.nodes],
						edges: [...this.graphOverviewData.edges],
						highlightNodeLabels: highlights,
						highlightColor: '#818CF8',
						highlightMode: 'static',
						canvasSuffix: suffix
					}
				}
				this.$forceUpdate()
			},

			async prepareLearningPathSnapshot(toolCallId, tool, toolCall) {
				const suffix = '_lp_' + (++this.gmCanvasCounter)

				// 刷新图谱数据（包含新建的 learning_path 边）
				await this.loadGraphOverviewData()
				if (!this.graphOverviewData) return

				const result = toolCall.result || {}
				const args = toolCall.arguments || {}
				const nodeSequence = args.node_sequence || []

				let highlightLabels = []
				let highlightEdgePairs = []
				let highlightColor = '#0088FF'
				let highlightEdgeColor = '#FFD93D'

				if (tool === 'generate_learning_path') {
					// 蓝色：高亮所有路径节点，边用默认蓝色（无需 override）
					highlightLabels = [...(result.path || nodeSequence)]
					highlightEdgePairs = []
					highlightColor = '#0088FF'
				} else if (tool === 'extend_learning_path') {
					// 黄色：新节点 = 除第一个外的所有（第一个是已有末端节点）
					highlightLabels = nodeSequence.slice(1)
					highlightColor = '#FFD93D'
					for (let i = 0; i < nodeSequence.length - 1; i++) {
						highlightEdgePairs.push([nodeSequence[i], nodeSequence[i + 1]])
					}
				} else if (tool === 'update_learning_path_segment') {
					// 黄色：中间新节点（首尾是锚点）
					highlightLabels = nodeSequence.slice(1, -1)
					highlightColor = '#FFD93D'
					for (let i = 0; i < nodeSequence.length - 1; i++) {
						highlightEdgePairs.push([nodeSequence[i], nodeSequence[i + 1]])
					}
				}

				this.graphMutationSnapshots = {
					...this.graphMutationSnapshots,
					[toolCallId]: {
						nodes: [...this.graphOverviewData.nodes],
						edges: [...this.graphOverviewData.edges],
						highlightNodeLabels: highlightLabels,
						highlightColor,
						highlightMode: 'static',
						canvasSuffix: suffix,
						highlightEdgePairs,
						highlightEdgeColor
					}
				}
				this.$forceUpdate()
			},

			async preparePostorderSnapshot(toolCallId, tool, toolCall) {
				if (this.expandedGraphTools[toolCallId] === undefined) {
					this.expandedGraphTools = { ...this.expandedGraphTools, [toolCallId]: false }
				}
				const suffix = '_po_' + (++this.gmCanvasCounter)

				if (!this.graphOverviewData) {
					await this.loadGraphOverviewData()
				}
				if (!this.graphOverviewData) return

				// 解析遍历结果字符串 "A->B->C" → ["A", "B", "C"]
				const result = toolCall.result
				let traversalNodes = []
				if (result && typeof result === 'string' && result !== '(空子树)') {
					traversalNodes = result.split('->')
				}

				this.graphMutationSnapshots = {
					...this.graphMutationSnapshots,
					[toolCallId]: {
						nodes: [...this.graphOverviewData.nodes],
						edges: [...this.graphOverviewData.edges],
						highlightNodeLabels: traversalNodes,
						highlightColor: '#49FFAA',
						highlightMode: 'static',
						canvasSuffix: suffix
					}
				}
				this.$forceUpdate()
			},

			computeQueryHighlights(tool, nodeName, graphData) {
				const highlights = [nodeName]

				const labelToId = new Map()
				const idToLabel = new Map()
				graphData.nodes.forEach(n => {
					labelToId.set(n.label, n.id)
					idToLabel.set(n.id, n.label)
				})

				const targetId = labelToId.get(nodeName)
				if (!targetId) return highlights

				const childrenOf = new Map()
				const parentsOf = new Map()

				graphData.edges.forEach(e => {
					if (e.type && e.type !== 'knowledge_tree') return
					if (!childrenOf.has(e.from)) childrenOf.set(e.from, [])
					childrenOf.get(e.from).push(e.to)
					if (!parentsOf.has(e.to)) parentsOf.set(e.to, [])
					parentsOf.get(e.to).push(e.from)
				})

				switch (tool) {
					case 'get_child_nodes': {
						const queue = [targetId]
						const visited = new Set([targetId])
						while (queue.length > 0) {
							const cur = queue.shift()
							const children = childrenOf.get(cur) || []
							for (const cid of children) {
								if (!visited.has(cid)) {
									visited.add(cid)
									const label = idToLabel.get(cid)
									if (label) highlights.push(label)
									queue.push(cid)
								}
							}
						}
						break
					}
					case 'get_parent_nodes': {
						const parents = parentsOf.get(targetId) || []
						for (const pid of parents) {
							const label = idToLabel.get(pid)
							if (label) highlights.push(label)
						}
						break
					}
					case 'get_sibling_nodes': {
						const parents = parentsOf.get(targetId) || []
						for (const pid of parents) {
							const siblings = childrenOf.get(pid) || []
							for (const sid of siblings) {
								if (sid !== targetId) {
									const label = idToLabel.get(sid)
									if (label && !highlights.includes(label)) {
										highlights.push(label)
									}
								}
							}
						}
						break
					}
				}

				return highlights
			},

			getGmCardTitle(toolCall) {
				// 查询工具：从 arguments 获取标题
				switch (toolCall.tool) {
					case 'get_child_nodes': return (toolCall.arguments?.node_name || '') + ' 的子节点'
					case 'get_parent_nodes': return (toolCall.arguments?.node_name || '') + ' 的父节点'
					case 'get_sibling_nodes': return (toolCall.arguments?.node_name || '') + ' 的兄弟节点'
					case 'generate_learning_path': {
						const path = toolCall.result?.path || toolCall.arguments?.node_sequence || []
						return '学习路径: ' + path.join(' → ')
					}
					case 'extend_learning_path': {
						const path = toolCall.result?.path || toolCall.arguments?.node_sequence || []
						return '延伸路径: ' + path.join(' → ')
					}
					case 'update_learning_path_segment': {
						const seq = toolCall.arguments?.node_sequence || []
						return '更新路径段: ' + seq.join(' → ')
					}
					case 'get_postorder_traversal': {
						const nodeName = toolCall.arguments?.node_name || ''
						const poResult = toolCall.result
						let count = 0
						if (poResult && typeof poResult === 'string' && poResult !== '(空子树)') {
							count = poResult.split('->').length
						}
						return nodeName + ' 的后序遍历 · ' + count + ' 个节点'
					}
				}
				// 变更工具：从 result 获取标题
				const r = toolCall.result
				if (!r) return ''
				switch (toolCall.tool) {
					case 'add_node': return '已添加节点: ' + r.label
					case 'add_edge': return '已连接: ' + r.from_node + ' → ' + r.to_node
					case 'delete_node': return '已删除节点: ' + r.deleted_node_name
					case 'delete_edge': return '已断开: ' + r.from_node + ' ↔ ' + r.to_node
					case 'update_mastery': return r.node_name + ' 掌握度: ' + r.mastery + '%'
					default: return ''
				}
			},

			getGmCardMeta(toolCallId) {
				const snap = this.graphMutationSnapshots[toolCallId]
				if (!snap) return ''
				return snap.nodes.length + ' 个节点 · ' + snap.edges.length + ' 条边'
			},

			/**
			 * 判断是否为测验成绩类工具
			 */
			isQuizResultTool(toolName) {
				return toolName === 'view_quiz_results' || toolName === 'view_quiz_attempt_detail'
			},

			/**
			 * 判断消息是否包含 generate_test 工具段（用于避免重复渲染进入卡片）
			 */
			hasQuizGenSegment(msg) {
				const segs = msg.segments || msg.streamSegments || []
				return segs.some(s => s.type === 'tool' && s.toolCall && s.toolCall.tool === 'generate_test')
			},

			/**
			 * 获取难度显示文字
			 */
			getDifficultyLabel(difficulty) {
				const map = { easy: '简单', medium: '中等', hard: '困难' }
				return map[difficulty] || difficulty
			},

			/**
			 * 判断是否为搜索类工具（含 web_search 和多渠道搜索）
			 */
			isSearchTool(toolName) {
				return ['web_search', 'academic_search', 'encyclopedia_search', 'course_search'].includes(toolName)
			},

			isDocRetrievalTool(toolName) {
				return DOC_RETRIEVAL_TOOLS.has(toolName)
			},

			getDocRetrievalToolText(toolCall) {
				const texts = DOC_RETRIEVAL_TOOL_TEXT[toolCall.tool]
				if (!texts) return toolCall.tool
				if (toolCall.status === 'running') return texts.running
				if (toolCall.status === 'done' && toolCall.success) return texts.done
				if (toolCall.status === 'done' && !toolCall.success) return texts.failed
				return texts.done
			},

			/**
			 * 获取可见搜索结果（折叠时只显示前2条）
			 */
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

			/**
			 * 搜索结果是否展开
			 */
			isSearchExpanded(toolCallId) {
				return this.expandedSearchResults[toolCallId] !== false
			},

			toggleSearchResults(toolCallId) {
				this.expandedSearchResults = {
					...this.expandedSearchResults,
					[toolCallId]: this.expandedSearchResults[toolCallId] === false
				}
			},

			isQuizToolExpanded(toolCallId) {
				return this.expandedQuizTools[toolCallId] !== false
			},

			toggleQuizTool(toolCallId) {
				const isCurrentlyExpanded = this.expandedQuizTools[toolCallId] !== false
				if (isCurrentlyExpanded) {
					// Collapsing: play exit animation first, then hide
					this.collapsingTools = { ...this.collapsingTools, [toolCallId]: true }
					setTimeout(() => {
						this.expandedQuizTools = { ...this.expandedQuizTools, [toolCallId]: false }
						const { [toolCallId]: _, ...rest } = this.collapsingTools
						this.collapsingTools = rest
					}, 200)
				} else {
					this.expandedQuizTools = { ...this.expandedQuizTools, [toolCallId]: true }
				}
			},

			isGraphToolExpanded(toolCallId) {
				return this.expandedGraphTools[toolCallId] !== false
			},

			isToolCollapsing(toolCallId) {
				return !!this.collapsingTools[toolCallId]
			},

			toggleGraphTool(toolCallId) {
				const isCurrentlyExpanded = this.expandedGraphTools[toolCallId] !== false
				if (isCurrentlyExpanded) {
					// Collapsing: play exit animation first, then hide
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

			/**
			 * 判断测验项的点击行为
			 */
			getQuizClickAction(quiz) {
				if (quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating') {
					return 'disabled'
				}
				if (quiz.has_attempt) {
					return 'view_result'
				}
				return 'take_quiz'
			},

			/**
			 * 测验项点击处理
			 */
			onQuizItemClick(quiz) {
				const action = this.getQuizClickAction(quiz)
				if (action === 'disabled') return
				if (action === 'view_result') {
					uni.navigateTo({
						url: `/pages/testResult/testResult?quizId=${quiz.id}&fromList=true`
					})
				} else {
					uni.navigateTo({
						url: `/pages/test/test?quizId=${quiz.id}`
					})
				}
			},

			/**
			 * 得分进度条颜色类名
			 */
			getScoreBarClass(percentage) {
				if (percentage >= 80) return 'score-bar-high'
				if (percentage >= 50) return 'score-bar-mid'
				return 'score-bar-low'
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

			/**
			 * 打开搜索结果 URL
			 */
			openSearchResultUrl(url) {
				if (!url) return
				// #ifdef H5
				window.open(url, '_blank')
				// #endif
				// #ifdef APP-PLUS
				plus.runtime.openURL(url)
				// #endif
			},

			/**
			 * 获取搜索来源显示标签
			 */
			getSourceLabel(source) {
				const map = {
					academic: '学术',
					encyclopedia: '百科',
					course: 'B站',
					web: '网页'
				}
				return map[source] || source
			},

			/**
			 * 从 URL 提取显示域名
			 */
			formatDisplayUrl(url) {
				try {
					const u = new URL(url)
					return u.hostname
				} catch {
					return url
				}
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
				const sysInfo = uni.getSystemInfoSync()
				console.log(`[SpaceChat-KB] onInputFocus: currentKeyboardH=${this.keyboardHeight}px, screenH=${sysInfo.screenHeight}, windowH=${sysInfo.windowHeight}, model=${sysInfo.model}`)
				if (this.isAutoScrollEnabled) {
					this.scrollToLatestMessage()
				}
			},

			onInputBlur() {
				console.log(`[SpaceChat-KB] onInputBlur: keyboardH=${this.keyboardHeight}px (应即将归零)`)
				// keyboardHeight 会通过 onKeyboardHeightChange 自动重置
			},

			openCitationSource(cite) {
				this.citationDetail = cite
				this.showCitationDetail = true
				this.$nextTick(() => {
					setTimeout(() => { this.citationDetailAnimVisible = true }, 10)
				})
			},

			closeCitationDetail() {
				this.citationDetailAnimVisible = false
				setTimeout(() => {
					this.showCitationDetail = false
					this.citationDetail = null
				}, 300)
			},

			openCitationUrl(url) {
				if (!url) return
				// #ifdef APP-PLUS
				plus.runtime.openURL(url)
				// #endif
				// #ifdef H5
				window.open(url, '_blank')
				// #endif
			},

			getDomain(url) {
				if (!url) return ''
				try { return new URL(url).hostname } catch { return url }
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
					chat_mode: 'space_chat',
					space_name: this.spaceTitle,
					feedback_type: newReaction === 'like' ? 'positive' : 'negative',
					feedback_content: newReaction === 'like' ? '👍 用户点赞了此回复' : '👎 用户点踩了此回复',
					conversation_history: conversationHistory
				}).catch(() => {
					// Silent failure — don't affect UI
				})
			},

			async toggleBookmark(msg) {
				if (msg.isBookmarked) {
					this.$set(msg, 'isBookmarked', false)
					return
				}

				const content = msg.content || ''
				if (!content.trim()) {
					uni.showToast({ title: '消息内容为空', icon: 'none' })
					return
				}

				const title = content.replace(/[#*`>\n]/g, '').trim().slice(0, 20) || '收藏笔记'

				try {
					await createNote(this.spaceId, { title, content })
					this.$set(msg, 'isBookmarked', true)
					uni.showToast({ title: '已添加到笔记', icon: 'success' })
				} catch (e) {
					console.error('[Bookmark] createNote failed:', e)
					uni.showToast({ title: '保存失败', icon: 'none' })
				}
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
				this.snackbarActionType = 'enter_quiz'
				this.showTestSnackbar = true
			},

			// 跳转到评估结果页面
			navigateToResult(quizId) {
				if (quizId) {
					uni.navigateTo({
						url: `/pages/testResult/testResult?quizId=${quizId}&fromList=true`
					})
				}
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

			// 处理后台测试评估完成
			handleQuizEvaluationDone({ quizId, status, result, error }) {
				if (this.isComponentDestroyed) return

				const msg = this.messages.find(m => m.quizId === quizId)

				// 评估中：卡片变为不可点击的等待状态
				if (status === 'evaluating') {
					if (msg) {
						msg.toolState = 'evaluating'
					}
					return
				}

				// 评估完成或已作答：卡片变为结果卡片
				if (status === 'success' || status === 'already_attempted') {
					if (msg) {
						msg.toolState = 'evaluated'
						if (status === 'success' && result) {
							msg.quizScore = result.score != null ? result.score : 0
							msg.quizTotalScore = result.total_score != null ? result.total_score : 0
						}
					}
				}

				if (status === 'success') {
					this.pendingEvalQuizId = quizId
					this.snackbarMessage = '测试评估完成'
					this.snackbarActionType = 'view_result'
					this.showTestSnackbar = true
				} else if (status === 'already_attempted') {
					this.pendingEvalQuizId = quizId
					this.snackbarMessage = '该测验已作答，点击查看结果'
					this.snackbarActionType = 'view_result'
					this.showTestSnackbar = true
				} else if (status === 'error') {
					uni.showToast({ title: error || '评估失败', icon: 'none', duration: 3000 })
				}
			},

			// Snackbar 操作按钮点击
			handleSnackbarAction() {
				this.showTestSnackbar = false
				if (this.snackbarActionType === 'view_result' && this.pendingEvalQuizId) {
					uni.navigateTo({
						url: `/pages/testResult/testResult?quizId=${this.pendingEvalQuizId}&fromList=true`
					})
					return
				}
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
				// 标记消息正在后台生成测试题（驱动指示器 pill 黄色状态）
				this.$set(this.messages[msgIndex], 'quizGenerating', true)

				try {
					// 轮询任务状态
					const result = await this.pollTaskStatus(taskId, msgIndex)
					if (this.isComponentDestroyed) return

					if (result.status === 'done' && result.quiz_id) {
						// 停止后台生成标记（指示器变为绿色完成态）
						this.messages[msgIndex].quizGenerating = false
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
						this.messages[msgIndex].quizGenerating = false
						const currentContent = this.messages[msgIndex].content || ''
						this.messages[msgIndex].content =
							currentContent + `\n\n测试生成失败：${result.error_message || '未知错误'}`
					}
				} catch (error) {
					console.error('测试生成轮询失败:', error)
					if (msgIndex >= 0 && this.messages[msgIndex]) {
						this.messages[msgIndex].quizGenerating = false
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
					// 确保 quizGenerating 标记被清除
					if (msgIndex >= 0 && this.messages[msgIndex]) {
						this.messages[msgIndex].quizGenerating = false
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

	.nav-icon {
		width: 48rpx;
		height: 48rpx;
		filter: brightness(0) invert(1);
	}

	.nav-title {
		font-size: 34rpx;
		font-weight: 600;
		color: rgb(248, 248, 248);
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
		color: rgb(248, 248, 248);
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
		background-color: #4A6CF7;
		border-radius: 32rpx 8rpx 32rpx 32rpx;
		padding: 24rpx 28rpx;
		max-width: none;
		min-width: 0;
	}

	.bubble-ai {
		background-color: transparent;
	}

	/* 引用来源列表 */
	.citation-footer {
		margin-top: 12px;
		padding-top: 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
	}
	.citation-footer-header {
		display: flex;
		align-items: center;
		margin-bottom: 8px;
	}
	.citation-footer-icon {
		width: 14px;
		height: 14px;
		margin-right: 6px;
		filter: brightness(0) saturate(100%) invert(45%) sepia(85%) saturate(1500%) hue-rotate(200deg) brightness(100%) contrast(96%);
	}
	.citation-footer-label {
		font-size: 12px;
		color: rgba(255, 255, 255, 0.65);
	}
	.citation-item {
		display: flex;
		align-items: center;
		padding: 6px 8px;
		margin-bottom: 4px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.04);
	}
	.citation-index {
		font-size: 11px;
		color: #3b82f6;
		font-weight: 600;
		margin-right: 8px;
		flex-shrink: 0;
	}
	.citation-info {
		flex: 1;
		overflow: hidden;
		display: flex;
		align-items: center;
	}
	.citation-title {
		font-size: 13px;
		color: rgba(255, 255, 255, 0.7);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.citation-meta {
		font-size: 11px;
		color: rgba(255, 255, 255, 0.3);
		margin-left: 8px;
		flex-shrink: 0;
	}
	.citation-arrow {
		width: 14px;
		height: 14px;
		opacity: 0.5;
		margin-left: 8px;
		flex-shrink: 0;
		filter: invert(1);
	}

	/* 引用详情抽屉 */
	.cite-drawer-wrapper {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1000;
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
	}
	.cite-drawer-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0);
		transition: background 200ms ease;
	}
	.cite-drawer-overlay.overlay-show {
		background: rgba(0, 0, 0, 0.6);
	}
	.cite-drawer-container {
		position: relative;
		background: rgba(20, 20, 30, 0.95);
		-webkit-backdrop-filter: blur(24px) saturate(180%);
		backdrop-filter: blur(24px) saturate(180%);
		border-top-left-radius: 32rpx;
		border-top-right-radius: 32rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.12);
		border-bottom: none;
		max-height: 65vh;
		display: flex;
		flex-direction: column;
		transform: translateY(100%);
		transition: transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}
	@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
		.cite-drawer-container {
			background: rgba(20, 20, 30, 0.98);
		}
	}
	.cite-drawer-container.drawer-show {
		transform: translateY(0);
	}
	.cite-drawer-handle {
		display: flex;
		justify-content: center;
		padding: 12rpx 0;
	}
	.cite-drawer-header {
		display: flex;
		align-items: flex-start;
		padding: 0 32rpx 20rpx;
		gap: 16rpx;
	}
	.cite-drawer-badge {
		color: #3b82f6;
		font-weight: 700;
		font-size: 28rpx;
		flex-shrink: 0;
		margin-top: 4rpx;
	}
	.cite-drawer-title-col {
		flex: 1;
		overflow: hidden;
	}
	.cite-drawer-title {
		font-size: 30rpx;
		color: #fff;
		font-weight: 600;
	}
	.cite-drawer-meta-row {
		display: flex;
		gap: 12rpx;
		margin-top: 6rpx;
		flex-wrap: wrap;
	}
	.cite-drawer-meta {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
	}
	.cite-drawer-body {
		flex: 1;
		max-height: 45vh;
		padding: 0 32rpx 24rpx;
	}
	.cite-drawer-content {
		font-size: 28rpx;
		color: rgba(255, 255, 255, 0.75);
		line-height: 1.8;
		white-space: pre-wrap;
	}
	.cite-drawer-footer {
		padding: 16rpx 32rpx;
		padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
		border-top: 1px solid rgba(255, 255, 255, 0.08);
	}
	.cite-drawer-open-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 16rpx;
		border-radius: 16rpx;
		background: rgba(59, 130, 246, 0.12);
	}
	.cite-drawer-open-icon {
		width: 28rpx;
		height: 28rpx;
		margin-right: 8rpx;
	}
	.cite-drawer-open-text {
		font-size: 28rpx;
		color: #3b82f6;
		font-weight: 500;
	}

	/* AI 消息操作图标 */
	.ai-msg-actions {
		display: flex;
		align-items: center;
		gap: 4rpx;
		margin-top: 12rpx;
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
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32rpx;
		height: 32rpx;
	}

	.user-msg-action-icon {
		width: 32rpx;
		height: 32rpx;
		opacity: 1;
		filter: brightness(0) invert(0.45) sepia(0.15);
	}

	.user-msg-action-btn .copy-icon-default,
	.user-msg-action-btn .copy-icon-check {
		position: absolute;
		transition: opacity 0.25s ease, transform 0.25s ease;
	}

	.user-msg-action-btn .copy-icon-default {
		opacity: 1;
		filter: brightness(0) invert(0.45) sepia(0.15);
		transform: scale(1);
	}

	.user-msg-action-btn .copy-icon-default.copy-icon-hide {
		opacity: 0;
		transform: scale(0.6);
	}

	.user-msg-action-btn .copy-icon-check {
		opacity: 0;
		transform: scale(0.6);
	}

	.user-msg-action-btn .copy-icon-check.copy-icon-show {
		opacity: 1;
		transform: scale(1);
		filter: brightness(0) invert(0.45) sepia(1) saturate(8) hue-rotate(90deg);
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

	.input-card {
		width: 100%;
		position: relative;
		background-color: rgb(36, 36, 36);
		border-radius: 40rpx;
		border: 2rpx solid rgba(255, 255, 255, 0.06);
		box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
		overflow: hidden;
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

	.input-bottom-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 12rpx 8rpx 12rpx;
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

	/* ========== 规划工具行内银光掠过 ========== */
	.planning-tool-inline {
		margin: 8rpx 0;
		max-height: 0;
		opacity: 0;
		overflow: hidden;
		transition: max-height 0.4s ease, opacity 0.4s ease, margin 0.4s ease;
	}

	.planning-tool-active {
		max-height: 60rpx;
		opacity: 1;
	}

	.planning-tool-done {
		max-height: 0;
		opacity: 0;
		margin: 0;
	}

	.planning-tool-text {
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
		animation: planning-shimmer 2s ease-in-out infinite;
	}

	.planning-tool-done .planning-tool-text {
		animation: none;
	}

	@keyframes planning-shimmer {
		0% {
			background-position: 100% 50%;
		}
		100% {
			background-position: -100% 50%;
		}
	}

	/* ========== 知识图谱工具 pill ========== */
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
		/* 中性底色，与 quiz-gen-done 一致 */
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
		width: 22rpx;
		height: 22rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.3);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: tool-spin 0.8s linear infinite;
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

	/* pending pill 样式（琥珀色） */
	.graph-tool-pending {
		border-color: rgba(232, 168, 56, 0.3);
		background: rgba(232, 168, 56, 0.06);
	}

	.graph-tool-pending .graph-tool-pill-icon {
		filter: invert(73%) sepia(54%) saturate(491%) hue-rotate(353deg) brightness(94%) contrast(89%);
	}

	.graph-tool-status-pending {
		filter: invert(73%) sepia(54%) saturate(491%) hue-rotate(353deg) brightness(94%) contrast(89%);
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
		animation: gm-card-enter 0.35s ease-out;
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

	/* ========== 知识图谱概览卡片 ========== */
	.graph-overview-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.graph-overview-card {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 20rpx 24rpx;
		overflow: hidden;
			animation: tool-card-enter 0.28s ease-out;
	}

	.graph-overview-header {
		display: flex;
		align-items: center;
		gap: 16rpx;
	}

	.graph-overview-icon-wrap {
		width: 56rpx;
		height: 56rpx;
		border-radius: 16rpx;
		background: rgba(74, 108, 247, 0.1);
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.graph-overview-icon-img {
		width: 32rpx;
		height: 32rpx;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.graph-overview-title-col {
		display: flex;
		flex-direction: column;
		gap: 4rpx;
		flex: 1;
		min-width: 0;
	}

	.graph-overview-title {
		font-size: 28rpx;
		font-weight: 600;
		color: #fff;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.graph-overview-meta {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.45);
	}

	.graph-overview-divider {
		height: 1rpx;
		background: rgba(255, 255, 255, 0.06);
		margin: 16rpx 0;
	}

	.graph-overview-preview {
		position: relative;
		background: rgba(0, 0, 0, 0.12);
		border-radius: 20rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.04);
		overflow: hidden;
	}

	.graph-overview-hint {
		position: absolute;
		top: 12rpx;
		right: 12rpx;
		display: flex;
		align-items: center;
		gap: 8rpx;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 100rpx;
		padding: 8rpx 16rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
	}

	.graph-overview-hint-icon {
		width: 24rpx;
		height: 24rpx;
		filter: invert(1);
		opacity: 0.6;
	}

	.graph-overview-hint-text {
		font-size: 20rpx;
		color: rgba(255, 255, 255, 0.6);
	}

	/* ========== 知识图谱快速预览弹窗 ========== */
	.graph-quick-view-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 9999;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40rpx;
	}

	.graph-quick-view-panel {
		width: 100%;
		max-width: 700rpx;
		background: #1a1a1a;
		border: 1rpx solid rgba(255, 255, 255, 0.1);
		border-radius: 32rpx;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.graph-quick-view-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 28rpx 32rpx 0;
	}

	.graph-quick-view-title-row {
		display: flex;
		align-items: center;
		gap: 14rpx;
		flex: 1;
		min-width: 0;
	}

	.graph-quick-view-title-icon {
		width: 36rpx;
		height: 36rpx;
		flex-shrink: 0;
		filter: brightness(0) invert(1);
		opacity: 0.6;
	}

	.graph-quick-view-title {
		font-size: 32rpx;
		font-weight: 600;
		color: #fff;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.graph-quick-view-close {
		width: 56rpx;
		height: 56rpx;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.06);
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.graph-quick-view-close:active {
		background: rgba(255, 255, 255, 0.12);
	}

	.graph-quick-view-close-icon {
		width: 28rpx;
		height: 28rpx;
		filter: invert(1);
		opacity: 0.5;
	}

	.graph-quick-view-meta {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.4);
		padding: 8rpx 32rpx 20rpx;
	}

	.graph-quick-view-canvas {
		margin: 0 24rpx 28rpx;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 24rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.04);
		overflow: hidden;
	}

	/* ========== 知识图谱变更工具详情卡片 ========== */
	.gm-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	.gm-card {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 20rpx 24rpx;
		animation: tool-card-enter 0.28s ease-out;
	}

	.gm-card-header {
		display: flex;
		align-items: center;
		gap: 16rpx;
	}

	.gm-card-icon-wrap {
		width: 48rpx;
		height: 48rpx;
		border-radius: 14rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.gm-icon-add {
		background: rgba(74, 108, 247, 0.12);
	}

	.gm-icon-delete {
		background: rgba(239, 68, 68, 0.12);
	}

	.gm-icon-update {
		background: rgba(73, 255, 170, 0.12);
	}

	.gm-card-icon-img {
		width: 28rpx;
		height: 28rpx;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.gm-icon-delete .gm-card-icon-img {
		filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
	}

	.gm-icon-update .gm-card-icon-img {
		filter: invert(70%) sepia(50%) saturate(500%) hue-rotate(100deg) brightness(105%) contrast(90%);
	}

	.gm-icon-query {
		background: rgba(129, 140, 248, 0.12);
	}

	.gm-icon-query .gm-card-icon-img {
		filter: invert(55%) sepia(60%) saturate(1500%) hue-rotate(210deg) brightness(105%) contrast(95%);
	}

	.gm-icon-path-generate {
		background: rgba(0, 136, 255, 0.12);
	}
	.gm-icon-path-generate .gm-card-icon-img {
		filter: invert(40%) sepia(80%) saturate(2000%) hue-rotate(190deg) brightness(105%) contrast(95%);
	}

	.gm-icon-path-modify {
		background: rgba(255, 217, 61, 0.12);
	}
	.gm-icon-path-modify .gm-card-icon-img {
		filter: invert(80%) sepia(50%) saturate(1000%) hue-rotate(10deg) brightness(105%) contrast(90%);
	}

	.gm-icon-postorder {
		background: rgba(74, 108, 247, 0.1);
	}
	.gm-icon-postorder .gm-card-icon-img {
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.gm-card-title-col {
		display: flex;
		flex-direction: column;
		gap: 2rpx;
		flex: 1;
		min-width: 0;
	}

	.gm-card-title {
		font-size: 26rpx;
		font-weight: 600;
		color: #fff;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.gm-card-meta {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.45);
	}

	.gm-card-divider {
		height: 1rpx;
		background: rgba(255, 255, 255, 0.06);
		margin: 14rpx 0;
	}

	.gm-card-preview {
		position: relative;
		background: rgba(0, 0, 0, 0.12);
		border-radius: 20rpx;
		border: 1rpx solid rgba(255, 255, 255, 0.04);
		overflow: hidden;
	}

	@keyframes gm-card-enter {
		from {
			opacity: 0;
			transform: translateY(8rpx);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}


	/* ========== 工具卡片展开/折叠过渡动画 ========== */
	.tool-card-leave {
		animation: tool-card-leave 0.2s ease-in forwards;
		pointer-events: none;
	}

	@keyframes tool-card-enter {
		from {
			opacity: 0;
			transform: translateY(-8rpx);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@keyframes tool-card-leave {
		from {
			opacity: 1;
			transform: translateY(0);
		}
		to {
			opacity: 0;
			transform: translateY(-8rpx);
		}
	}
	/* ========== 展开态统一容器 ========== */
	.gm-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 0;
		gap: 0;
	}

	.gm-expanded-container .graph-tool-pill {
		border: none;
		background: transparent;
		border-radius: 24rpx 24rpx 0 0;
		padding: 20rpx 24rpx 16rpx;
	}

	.gm-expanded-container .gm-card {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
	}

	.gm-expanded-container .graph-overview-card {
		border: none;
		background: transparent;
		border-radius: 0 0 24rpx 24rpx;
	}

	/* ========== 测试题生成工具指示器 ========== */
	.quiz-gen-wrap {
		display: flex;
		flex-direction: column;
		gap: 14rpx;
	}

	.quiz-gen-indicator {
		display: flex;
		align-items: center;
		gap: 16rpx;
		padding: 16rpx 24rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		transition: all 0.25s ease;
	}

	/* 状态1：启动测试题生成任务中（蓝色） */
	.quiz-gen-running {
		border-color: rgba(74, 108, 247, 0.3);
		background: rgba(74, 108, 247, 0.06);
	}

	/* 状态2：正在后台生成测试题（黄色） */
	.quiz-gen-polling {
		border-color: rgba(234, 179, 8, 0.3);
		background: rgba(234, 179, 8, 0.06);
	}

	/* 状态3：已生成测试题（中性底色，参考 Pencil 设计） */
	.quiz-gen-done {
		/* 无额外色调，保持基础中性风格 */
	}

	.quiz-gen-failed {
		border-color: rgba(239, 68, 68, 0.2);
		background: rgba(239, 68, 68, 0.05);
	}

	/* list-checks 图标：蓝色 #4A6CF7 */
	.quiz-gen-indicator-icon {
		width: 32rpx;
		height: 32rpx;
		flex-shrink: 0;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.quiz-gen-indicator-text {
		flex: 1;
		font-size: 26rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.7);
	}

	.quiz-gen-running .quiz-gen-indicator-text,
	.quiz-gen-polling .quiz-gen-indicator-text {
		color: rgba(255, 255, 255, 0.8);
	}

	.quiz-gen-indicator-spinner {
		width: 28rpx;
		height: 28rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.3);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: tool-spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	/* 黄色 spinner */
	.quiz-gen-spinner-amber {
		border-color: rgba(234, 179, 8, 0.3);
		border-top-color: #EAB308;
	}

	/* circle-check 图标：绿色 #3D8A5A */
	.quiz-gen-status-icon {
		width: 28rpx;
		height: 28rpx;
		flex-shrink: 0;
		filter: invert(48%) sepia(30%) saturate(900%) hue-rotate(100deg) brightness(85%) contrast(90%);
	}

	.quiz-gen-status-failed {
		filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
	}

	/* ========== 测试题进入卡片 ========== */
	.quiz-entry-card {
		margin-top: 20rpx;
		display: flex;
		align-items: center;
		gap: 20rpx;
		padding: 20rpx 24rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		transition: all 0.15s ease;
	}

	.quiz-entry-card:active {
		transform: scale(0.98);
		background: rgba(255, 255, 255, 0.08);
	}

	.quiz-entry-icon-wrap {
		width: 72rpx;
		height: 72rpx;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 18rpx;
		background: rgba(74, 108, 247, 0.1);
		flex-shrink: 0;
	}

	.quiz-entry-icon {
		width: 36rpx;
		height: 36rpx;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.quiz-entry-text-col {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4rpx;
	}

	.quiz-entry-title {
		font-size: 28rpx;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.92);
	}

	.quiz-entry-meta {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.45);
	}

	.quiz-entry-chevron {
		width: 36rpx;
		height: 36rpx;
		flex-shrink: 0;
		filter: brightness(0) invert(1);
		opacity: 0.4;
	}

	/* ========== 测试题评估中卡片变体 ========== */
	.quiz-entry-card--evaluating {
		border-color: rgba(255, 183, 77, 0.2);
		background: rgba(255, 183, 77, 0.06);
		cursor: default;
	}

	.quiz-entry-icon-wrap--evaluating {
		background: rgba(255, 183, 77, 0.12);
	}

	.quiz-evaluating-pulse {
		filter: invert(72%) sepia(58%) saturate(1000%) hue-rotate(1deg) brightness(103%) contrast(101%);
		animation: quizPulse 1.5s ease-in-out infinite;
	}

	@keyframes quizPulse {
		0%, 100% { opacity: 0.4; }
		50% { opacity: 1; }
	}

	.quiz-entry-meta--evaluating {
		color: rgba(255, 183, 77, 0.7);
	}

	/* ========== 测试题评估完成卡片变体 ========== */
	.quiz-entry-card--evaluated {
		border-color: rgba(76, 175, 80, 0.2);
		background: rgba(76, 175, 80, 0.06);
	}

	.quiz-entry-card--evaluated:active {
		background: rgba(76, 175, 80, 0.12);
	}

	.quiz-entry-icon-wrap--evaluated {
		background: rgba(76, 175, 80, 0.15);
	}

	.quiz-score-number {
		font-size: 28rpx;
		font-weight: 700;
		color: #4CAF50;
	}

	.quiz-entry-meta--evaluated {
		color: rgba(76, 175, 80, 0.7);
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


	/* ========== 默认工具 pill 容器 ========== */
	.default-tool-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	@keyframes tool-spin {
		to {
			transform: rotate(360deg);
		}
	}

	/* ========== Artifact 卡片 ========== */
	.artifact-card.ac-success {
		border-color: rgba(52, 211, 153, 0.25);
		background: rgba(52, 211, 153, 0.06);
	}

	.ac-body {
		padding: 8rpx 24rpx 20rpx;
	}

	.ac-status-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.45);
	}

	.ac-done-text {
		color: rgba(52, 211, 153, 0.7);
	}

	.ac-error-text {
		color: rgba(248, 113, 113, 0.7);
	}

	.ac-progress-bar {
		margin-top: 12rpx;
		height: 4rpx;
		border-radius: 2rpx;
		background: rgba(255, 255, 255, 0.06);
		overflow: hidden;
	}

	.ac-progress-fill {
		height: 100%;
		width: 40%;
		border-radius: 2rpx;
		background: linear-gradient(90deg, rgba(99, 102, 241, 0.5), rgba(138, 180, 248, 0.6));
		animation: ac-progress 1.5s ease-in-out infinite;
	}

	@keyframes ac-progress {
		0% {
			transform: translateX(-100%);
		}
		100% {
			transform: translateX(350%);
		}
	}

	.ac-view-btn {
		display: inline-flex;
		margin-top: 12rpx;
		padding: 8rpx 20rpx;
		border-radius: 8rpx;
		background: rgba(99, 102, 241, 0.15);
	}

	.ac-view-btn-text {
		font-size: 24rpx;
		color: rgba(138, 180, 248, 0.9);
	}

	/* ========== 图表生成卡片（pill + 详情） ========== */
	.chart-tool-wrap {
		display: flex;
		flex-direction: column;
		gap: 12rpx;
	}

	/* ========== 图表工具展开容器 ========== */
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
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		padding: 16rpx;
		overflow: hidden;
	}

	.chart-preview-img {
		width: 100%;
		border-radius: 12rpx;
	}

	.chart-saved-badge {
		margin-top: 12rpx;
		display: flex;
		align-items: center;
	}

	.chart-error-msg {
		padding: 12rpx 16rpx;
		background: rgba(239, 68, 68, 0.06);
		border: 1rpx solid rgba(239, 68, 68, 0.15);
		border-radius: 16rpx;
	}

	.chart-error-text {
		font-size: 24rpx;
		color: rgba(239, 68, 68, 0.8);
	}

	.chart-saved-icon {
		width: 28rpx;
		height: 28rpx;
		opacity: 0.5;
		margin-right: 4rpx;
		flex-shrink: 0;
	}

	.chart-saved-text {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.5);
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

	/* ========== 测验工具 - 胶囊 + 卡片 ========== */
	.quiz-tool-wrap {
		margin: 12rpx 0;
	}

	.quiz-tool-pill {
		display: flex;
		align-items: center;
		gap: 14rpx;
		padding: 14rpx 20rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 20rpx;
		transition: all 0.25s ease;
	}

	.quiz-tool-running {
		background: rgba(74, 108, 247, 0.06);
		border-color: rgba(74, 108, 247, 0.3);
	}

	.quiz-tool-done {
		background: rgba(255, 255, 255, 0.06);
		border-color: rgba(255, 255, 255, 0.12);
	}

	.quiz-expanded-container {
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.08);
		border-radius: 24rpx;
		overflow: hidden;
	}

	.quiz-expanded-container .quiz-tool-pill {
		border: none;
		background: transparent;
		border-radius: 0;
		padding: 18rpx 20rpx 14rpx;
	}

	.quiz-expanded-container .quiz-tool-results-card {
		border: none;
		background: transparent;
		border-radius: 0;
		margin-top: 0;
			animation: tool-card-enter 0.28s ease-out;
	}

	.quiz-expanded-container .quiz-tool-detail-card {
		border: none;
		background: transparent;
		border-radius: 0;
		margin-top: 0;
			animation: tool-card-enter 0.28s ease-out;
	}

	.quiz-expanded-container .quiz-tool-empty {
		border: none;
		background: transparent;
		border-radius: 0;
		margin-top: 0;
			animation: tool-card-enter 0.28s ease-out;
	}

	.quiz-tool-failed {
		border-color: rgba(239, 68, 68, 0.2);
		background: rgba(239, 68, 68, 0.05);
	}

	.quiz-tool-pill-icon {
		width: 30rpx;
		height: 30rpx;
		flex-shrink: 0;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
	}

	.quiz-tool-failed .quiz-tool-pill-icon {
		filter: brightness(0) saturate(100%) invert(42%) sepia(76%) saturate(2178%) hue-rotate(336deg) brightness(98%) contrast(89%);
	}

	.quiz-tool-pill-text {
		flex: 1;
		font-size: 25rpx;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.65);
	}

	.quiz-tool-spinner {
		width: 22rpx;
		height: 22rpx;
		border: 2rpx solid rgba(74, 108, 247, 0.25);
		border-top-color: #4A6CF7;
		border-radius: 50%;
		animation: tool-spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	.quiz-tool-chevron {
		width: 24rpx;
		height: 24rpx;
		flex-shrink: 0;
		opacity: 0.35;
		filter: brightness(0) invert(1);
		transition: transform 0.2s ease;
	}

	.quiz-tool-chevron-up {
		transform: rotate(180deg);
	}

	.quiz-tool-empty {
		margin-top: 10rpx;
		padding: 16rpx 20rpx;
		background: rgba(255, 255, 255, 0.04);
		border: 1rpx solid rgba(255, 255, 255, 0.06);
		border-radius: 12rpx;
	}

	.quiz-tool-empty-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.45);
	}

	/* -- 测验成绩列表卡片 -- */
	.quiz-tool-results-card {
		margin-top: 10rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.12);
		border-radius: 16rpx;
		padding: 16rpx 20rpx;
		display: flex;
		flex-direction: column;
		gap: 8rpx;
	}

	.quiz-result-item {
		background: rgba(255, 255, 255, 0.05);
		border: 1rpx solid rgba(255, 255, 255, 0.06);
		border-radius: 12rpx;
		padding: 14rpx 16rpx;
		transition: background 0.15s ease;
	}

	.quiz-result-clickable:active {
		background: rgba(255, 255, 255, 0.1);
	}

	.quiz-result-evaluating {
		opacity: 0.55;
	}

	.quiz-result-row {
		display: flex;
		align-items: center;
		gap: 8rpx;
	}

	.quiz-result-title {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 500;
		flex: 1;
	}

	.quiz-result-difficulty {
		font-size: 20rpx;
		padding: 2rpx 10rpx;
		border-radius: 6rpx;
	}

	.quiz-result-difficulty.difficulty-easy {
		color: rgba(34, 197, 94, 0.9);
		background: rgba(34, 197, 94, 0.15);
	}

	.quiz-result-difficulty.difficulty-medium {
		color: rgba(251, 191, 36, 0.9);
		background: rgba(251, 191, 36, 0.15);
	}

	.quiz-result-difficulty.difficulty-hard {
		color: rgba(239, 68, 68, 0.9);
		background: rgba(239, 68, 68, 0.15);
	}

	.quiz-result-meta {
		display: flex;
		align-items: center;
		gap: 12rpx;
		margin-top: 6rpx;
	}

	.quiz-result-score {
		font-size: 24rpx;
		color: rgba(59, 130, 246, 0.9);
		font-weight: 600;
	}

	.quiz-result-evaluating-text {
		font-size: 22rpx;
		color: rgba(251, 191, 36, 0.8);
		font-weight: 500;
	}

	.quiz-result-no-attempt {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
	}

	.quiz-result-date {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
		flex: 1;
	}

	.quiz-result-arrow {
		width: 24rpx;
		height: 24rpx;
		flex-shrink: 0;
		opacity: 0.3;
		filter: brightness(0) invert(1);
	}

	/* -- 测验详情分析卡片 -- */
	.quiz-tool-detail-card {
		margin-top: 10rpx;
		background: rgba(255, 255, 255, 0.06);
		border: 1rpx solid rgba(255, 255, 255, 0.12);
		border-radius: 16rpx;
		overflow: hidden;
	}

	/* 得分概览区 */
	.quiz-detail-score-section {
		padding: 20rpx 24rpx 16rpx;
	}

	.quiz-detail-score-header {
		margin-bottom: 6rpx;
	}

	.quiz-detail-score-label {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.45);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 1rpx;
	}

	.quiz-detail-score-row {
		display: flex;
		align-items: baseline;
		gap: 8rpx;
		margin-bottom: 10rpx;
	}

	.quiz-detail-score-value {
		font-size: 36rpx;
		color: rgba(59, 130, 246, 0.95);
		font-weight: 700;
	}

	.quiz-detail-score-percent {
		font-size: 26rpx;
		color: rgba(255, 255, 255, 0.5);
	}

	.quiz-detail-score-bar-bg {
		width: 100%;
		height: 6rpx;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 3rpx;
		overflow: hidden;
	}

	.quiz-detail-score-bar-fill {
		height: 100%;
		border-radius: 3rpx;
		transition: width 0.5s ease;
	}

	.score-bar-high {
		background: rgba(34, 197, 94, 0.8);
	}

	.score-bar-mid {
		background: rgba(251, 191, 36, 0.8);
	}

	.score-bar-low {
		background: rgba(239, 68, 68, 0.8);
	}

	/* 分析区 */
	.quiz-detail-analysis-section {
		padding: 16rpx 24rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.quiz-detail-analysis-header {
		margin-bottom: 10rpx;
	}

	.quiz-detail-section-title {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.45);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 1rpx;
	}

	.quiz-detail-subsection {
		margin-top: 10rpx;
	}

	.quiz-detail-subsection:first-child {
		margin-top: 0;
	}

	.quiz-detail-subsection-title {
		font-size: 23rpx;
		color: rgba(255, 255, 255, 0.6);
		font-weight: 500;
		margin-bottom: 6rpx;
	}

	.quiz-detail-tag-item {
		display: flex;
		align-items: flex-start;
		gap: 10rpx;
		padding: 4rpx 0;
	}

	.quiz-detail-dot {
		width: 10rpx;
		height: 10rpx;
		border-radius: 50%;
		flex-shrink: 0;
		margin-top: 10rpx;
	}

	.strength-dot {
		background: rgba(34, 197, 94, 0.9);
	}

	.weakness-dot {
		background: rgba(239, 68, 68, 0.9);
	}

	.quiz-detail-tag-text {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.8);
		flex: 1;
	}

	/* 题目详情区 */
	.quiz-detail-questions-section {
		padding: 16rpx 24rpx 20rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.quiz-detail-questions-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 10rpx;
	}

	.quiz-detail-questions-count {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.35);
	}

	.quiz-detail-q-row {
		display: flex;
		align-items: center;
		gap: 10rpx;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 8rpx;
		padding: 10rpx 12rpx;
		margin-top: 6rpx;
	}

	.quiz-detail-q-order {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.4);
		width: 32rpx;
		text-align: center;
		flex-shrink: 0;
	}

	.quiz-detail-q-status-dot {
		width: 12rpx;
		height: 12rpx;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.status-dot-correct {
		background: rgba(34, 197, 94, 0.9);
	}

	.status-dot-wrong {
		background: rgba(239, 68, 68, 0.9);
	}

	.status-dot-partial {
		background: rgba(251, 191, 36, 0.9);
	}

	.quiz-detail-q-title {
		font-size: 24rpx;
		color: rgba(255, 255, 255, 0.8);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.quiz-detail-q-score {
		font-size: 22rpx;
		color: rgba(255, 255, 255, 0.5);
		flex-shrink: 0;
	}

	.quiz-tool-detail-clickable:active {
		background: rgba(255, 255, 255, 0.09);
	}

	.quiz-detail-footer {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 6rpx;
		padding: 14rpx 24rpx;
		border-top: 1rpx solid rgba(255, 255, 255, 0.06);
	}

	.quiz-detail-footer-text {
		font-size: 23rpx;
		color: rgba(74, 108, 247, 0.8);
		font-weight: 500;
	}

	.quiz-detail-footer-arrow {
		width: 22rpx;
		height: 22rpx;
		filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
		opacity: 0.8;
	}

	/* ========== 搜索来源卡片 ========== */
	.search-tool-wrap {
		margin: 12rpx 0;
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
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(255, 255, 255, 0.2);
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
		animation: tool-spin 0.8s linear infinite;
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

	/* ========== 待发送附件预览 ========== */
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

	/* ==================== 模型选择器（底部工具行内） ==================== */
	.model-selector-btn {
		display: flex;
		align-items: center;
		gap: 8rpx;
		padding: 8rpx 16rpx 8rpx 12rpx;
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

	/* ==================== 底部行左侧容器 ==================== */
	.input-bottom-left {
		display: flex;
		align-items: center;
		gap: 8rpx;
		flex: 1;
		min-width: 0;
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
</style>
