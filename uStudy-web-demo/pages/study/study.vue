<template>
  <view class="study-page">
    <!-- Aurora Background -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Sidebar -->
    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @select-space="handleSelectSpace"
      @create-space="handleCreateSpace"
    />

    <!-- Main Content -->
    <view class="study-main">
      <!-- Header Bar -->
      <view class="study-header">
        <text class="study-header-title">{{ spaceName }}{{ isCollaborative && userRole === 'member' ? ' (协作)' : '' }}</text>
        <view class="study-header-actions">
          <view
            class="share-space-btn"
            :class="{ 'share-space-btn-disabled': !spaceId || isGeneratingShareCode }"
            @tap="handleShareSpace"
          >
            <svg viewBox="0 0 256 256" class="share-space-icon">
              <rect width="256" height="256" fill="none"/>
              <line x1="128" y1="144" x2="128" y2="32" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <polyline points="216 144 216 208 40 208 40 144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <polyline points="88 72 128 32 168 72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
          </view>
          <view
            class="delete-space-btn"
            :class="{ 'delete-space-btn-disabled': !spaceId || isDeletingSpace }"
            @tap="handleDeleteSpace"
          >
            <svg viewBox="0 0 256 256" class="delete-space-icon">
              <rect width="256" height="256" fill="none"/>
              <line x1="216" y1="56" x2="40" y2="56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="104" y1="104" x2="104" y2="168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="152" y1="104" x2="152" y2="168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <path d="M200,56V208a8,8,0,0,1-8,8H64a8,8,0,0,1-8-8V56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <path d="M168,56V40a16,16,0,0,0-16-16H104A16,16,0,0,0,88,40V56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
          </view>
        </view>
      </view>

      <!-- Two-Panel Layout -->
      <view class="study-panels">
        <!-- Left Panel: Knowledge Graph -->
        <view class="panel-graph">
          <view class="panel-graph-inner" :class="{ 'panel-synced': dualSyncEnabled }">
            <!-- Chrome-style Tab Bar -->
            <view class="chrome-tabs-bar">
              <view
                v-for="tab in tabs"
                :key="tab.id"
                class="chrome-tab"
                :class="{ 'chrome-tab-active': activeTab === tab.id }"
                @tap="handleTabChange(tab.id)"
              >
                <text class="chrome-tab-label">{{ tab.label }}</text>
              </view>
              <view class="chrome-tabs-spacer"></view>
            </view>

            <!-- Collaborative User Filter -->
            <view v-if="isCollaborative && activeTab === 'graph'" class="collab-user-filter">
              <view class="filter-trigger" @tap="showMemberDropdown = !showMemberDropdown">
                <view class="color-dot" :style="{ background: selectedMemberColor }"></view>
                <text class="filter-label">{{ selectedMemberName }}</text>
                <text class="filter-arrow">&#9660;</text>
              </view>
              <view v-if="showMemberDropdown" class="member-dropdown">
                <view
                  v-for="m in spaceMembers"
                  :key="m.user_id"
                  class="member-item"
                  :class="{ 'member-item-active': m.user_id === (selectedMemberUserId || currentUserId) }"
                  @tap="selectMemberFilter(m)"
                >
                  <view class="color-dot" :style="{ background: m.color || '#0088FF' }"></view>
                  <text class="member-name">{{ m.nickname }}{{ m.role === 'owner' ? ' (管理员)' : '' }}</text>
                </view>
              </view>
            </view>

            <!-- Tab Content Area -->
            <view class="tab-content-area">
              <KnowledgeGraph
                ref="knowledgeGraph"
                v-if="activeTab === 'graph'"
                :spaceId="spaceId"
                :pathHighlight="isPathHighlightOn"
                :generating="graphGenerating"
                :targetUserId="selectedMemberUserId"
                :pathColor="selectedMemberColor"
                @node-selected="onNodeSelected"
                @graph-loaded="onGraphLoaded"
                @retry="handleGraphRetry"
                @quick-learn="onQuickLearn"
              />
              <StudyMaterialsPanel
                v-else-if="activeTab === 'materials'"
                class="materials-tab-panel"
                :space-id="spaceId"
                :user-tier="currentUserTier"
                :visible="activeTab === 'materials'"
                :is-collaborative="isCollaborative"
                :user-role="userRole"
                :current-user-id="currentUserId"
                :space-members="spaceMembers"
              />
              <QuizPanel
                ref="quizPanel"
                v-else-if="activeTab === 'quizzes'"
                :space-id="spaceId"
                :key="`quiz-panel-${spaceId || 'none'}`"
              />
              <NotesPanel
                ref="notesPanel"
                v-else-if="activeTab === 'notes'"
                :space-id="spaceId"
                :is-collaborative="isCollaborative"
                :user-role="userRole"
                :current-user-id="currentUserId"
                :space-members="spaceMembers"
                :key="`notes-panel-${spaceId || 'none'}`"
              />
              <template v-else-if="activeTab === 'browser'">
                <!-- #ifdef H5 -->
                <view class="browser-panel">
                  <view class="browser-nav">
                    <view
                      class="browser-nav-btn"
                      :class="{ 'browser-nav-btn-disabled': !canBrowserBack }"
                      @tap="handleBrowserBack"
                    >
                      <image class="browser-nav-icon" mode="aspectFit" src="/static/icons/phosphor/regular/arrow-left-white.svg" />
                    </view>
                    <view
                      class="browser-nav-btn"
                      :class="{ 'browser-nav-btn-disabled': !canBrowserForward }"
                      @tap="handleBrowserForward"
                    >
                      <image class="browser-nav-icon" mode="aspectFit" src="/static/icons/phosphor/regular/arrow-right-white.svg" />
                    </view>
                    <view class="browser-nav-btn" @tap="handleBrowserRefresh">
                      <image class="browser-nav-icon" mode="aspectFit" src="/static/icons/phosphor/regular/arrow-clockwise-white.svg" />
                    </view>
                    <input
                      class="browser-input"
                      type="text"
                      v-model="browserInputUrl"
                      placeholder="输入网址，例如 example.com"
                      @confirm="handleBrowserGo"
                    />
                    <view class="browser-go-btn" @tap="handleBrowserGo">
                      <image class="browser-go-icon" mode="aspectFit" src="/static/icons/phosphor/regular/paper-plane-right-white.svg" />
                    </view>
                  </view>

                  <view class="browser-frame-wrap">
                    <iframe
                      :key="browserFrameKey"
                      class="browser-iframe"
                      :src="browserCurrentUrl"
                      @load="onBrowserFrameLoad"
                    ></iframe>

                    <view v-if="browserLoading" class="browser-status-overlay">
                      <text class="browser-status-text">网页加载中...</text>
                    </view>

                    <view v-if="browserLoadError" class="browser-error-overlay">
                      <view class="browser-error-card">
                        <text class="browser-error-title">网页无法在面板内显示</text>
                        <text class="browser-error-sub">{{ browserErrorMessage }}</text>
                        <view class="browser-open-external-btn" @tap="openBrowserInNewTab">
                          <text class="browser-open-external-btn-text">新窗口打开</text>
                        </view>
                      </view>
                    </view>
                  </view>
                </view>
                <!-- #endif -->
                <!-- #ifndef H5 -->
                <view class="browser-unsupported">
                  <text class="placeholder-text">当前平台暂不支持内嵌网页</text>
                  <text class="placeholder-sub">请在 H5 页面使用自由网页功能</text>
                </view>
                <!-- #endif -->
              </template>
              <template v-else>
                <view class="placeholder-wrap">
                  <text class="placeholder-text">{{ activeTabInfo.placeholder }}</text>
                  <text class="placeholder-sub">{{ activeTabInfo.sub }}</text>
                </view>
              </template>
            </view>

            <!-- Annotation overlay for dual-sync mode -->
            <view v-if="annotations.length > 0" class="annotation-overlay">
              <view
                v-for="ann in annotations"
                :key="ann.id"
                class="ann-rect"
                :style="{
                  left: ann.x + '%',
                  top: ann.y + '%',
                  width: ann.w + '%',
                  height: ann.h + '%',
                  borderColor: ann.color || '#FF6B6B'
                }"
              >
                <view class="ann-comment">{{ ann.comment }}</view>
              </view>
            </view>

            <!-- Bottom Action Buttons (graph tab only) -->
            <view v-if="activeTab === 'graph'" class="graph-actions">
              <view
                class="graph-action-btn"
                :class="{ 'graph-action-btn-active': isPathHighlightOn }"
                @tap="togglePathHighlight"
              >
                <image
                  class="action-icon-img"
                  mode="aspectFit"
                  src="/static/icons/phosphor/regular/path-white.svg"
                />
              </view>
              <view class="graph-action-btn">
                <image
                  class="action-icon-img"
                  mode="aspectFit"
                  src="/static/icons/phosphor/flat-regular/link-white.svg"
                />
              </view>
            </view>
          </view>
        </view>

        <!-- Dual-sync link indicator -->
        <view v-if="dualSyncEnabled" class="dual-sync-link-indicator link-active">
          <svg viewBox="0 0 256 256" class="link-icon">
            <rect width="256" height="256" fill="none"/>
            <!-- Opaque capsule fill behind strokes -->
            <rect x="16" y="80" width="224" height="96" rx="48" ry="48" fill="#181825"/>
            <line x1="80" y1="128" x2="176" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <path d="M104,176H64a48,48,0,0,1,0-96h40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <path d="M152,80h40a48,48,0,0,1,48,48h0a48,48,0,0,1-48,48H152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          </svg>
        </view>

        <!-- Right Panel: Chat -->
        <view class="panel-chat">
          <!-- Mastery score toast notifications -->
          <UMasteryToast
            v-for="toast in masteryNotifications"
            :key="toast.id"
            :visible="toast.visible"
            :nodeName="toast.nodeName"
            :change="toast.change"
            :index="toast.index"
            @close="removeMasteryNotification(toast.id)"
          />

          <!-- Quiz evaluation completion notifications -->
          <UQuizNotification
            v-for="notif in quizEvaluationNotifications"
            :key="'quiz-notif-' + notif.id"
            :visible="notif.visible"
            :quizTopic="notif.quizTopic"
            :score="notif.score"
            :totalScore="notif.totalScore"
            :status="notif.status"
            :index="notif.index"
            @click="handleQuizNotificationClick(notif)"
            @close="removeQuizNotification(notif.id)"
          />

          <!-- Artifact completion notifications -->
          <UArtifactNotification
            v-for="notif in artifactNotifications"
            :key="'artifact-notif-' + notif.id"
            :visible="notif.visible"
            :title="notif.title"
            :status="notif.status"
            :error-message="notif.errorMessage"
            :index="notif.index"
            @click="handleArtifactNotificationClick(notif)"
            @close="removeArtifactNotification(notif.id)"
          />
          <view class="panel-chat-inner" :class="{ 'panel-synced': dualSyncEnabled }">
            <!-- Chat Panel Header -->
            <view class="chat-panel-header">
              <view
                class="chat-header-btn-wrap"
              >
                <view
                  class="chat-header-btn"
                  :class="{ 'chat-header-btn-disabled': !spaceId }"
                  @tap="openHistoryPopup"
                >
                  <image
                    class="chat-header-icon"
                    mode="aspectFit"
                    src="/static/icons/phosphor/bold/clock-clockwise-white.svg"
                  />
                </view>

                <!-- History popup anchored to button -->
                <transition name="history-fade">
                  <view v-if="showHistoryPopup" class="history-popup">
                    <view class="history-popup-header">
                      <text class="history-popup-title">对话记录</text>
                      <view class="history-popup-close" @tap="showHistoryPopup = false">
                        <text class="history-popup-close-text">✕</text>
                      </view>
                    </view>
                    <view v-if="isLoadingConversations" class="history-loading">
                      <view class="typing-indicator">
                        <view class="typing-dot"></view>
                        <view class="typing-dot"></view>
                        <view class="typing-dot"></view>
                      </view>
                    </view>
                    <scroll-view v-else class="history-list" scroll-y>
                      <view v-if="historyConversations.length === 0" class="history-empty">
                        <text class="history-empty-text">暂无对话记录</text>
                      </view>
                      <view
                        v-for="conv in historyConversations"
                        :key="conv.id"
                        class="history-item"
                        :class="{ 'history-item-active': conv.id === conversationId }"
                        @tap="selectConversation(conv)"
                      >
                        <text class="history-item-title">{{ conv.title || 'Untitled' }}</text>
                        <text class="history-item-date">{{ formatConvDate(conv.updated_at || conv.created_at) }}</text>
                      </view>
                    </scroll-view>
                  </view>
                </transition>
              </view>

              <!-- Model selector (center of header) -->
              <view v-if="availableModels.length > 0" class="model-selector-wrap">
                <view class="model-selector-btn" @tap="toggleModelMenu">
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
                <!-- Model dropdown menu (opens downward from header) -->
                <transition name="model-menu-fade">
                  <view v-if="showModelMenu" class="model-menu model-menu-down">
                    <view
                      v-for="m in availableModels"
                      :key="m.id"
                      class="model-menu-item"
                      :class="{
                        'model-menu-item-active': m.id === selectedModelId,
                        'model-menu-item-locked': m.locked
                      }"
                      @tap="selectModel(m.id)"
                    >
                      <view class="model-menu-item-info">
                        <text class="model-menu-item-name">{{ m.display_name }}</text>
                        <text class="model-menu-item-desc">{{ m.locked ? '升级订阅解锁' : m.description }}</text>
                      </view>
                      <svg v-if="m.locked" viewBox="0 0 256 256" class="model-menu-lock">
                        <rect x="40" y="112" width="176" height="112" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                        <path d="M88,112V80a40,40,0,0,1,80,0v32" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                      </svg>
                      <svg v-else-if="m.id === selectedModelId" viewBox="0 0 256 256" class="model-menu-check">
                        <polyline points="40 144 96 200 216 80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                      </svg>
                    </view>
                  </view>
                </transition>
              </view>

              <!-- Dual Sync Toggle -->
              <view v-if="spaceId" class="dual-sync-toggle" :class="{ 'dual-sync-active': dualSyncEnabled }" @tap="dualSyncEnabled = !dualSyncEnabled">
                <text class="dual-sync-label">双栏同步</text>
              </view>

              <view
                class="chat-header-btn"
                :class="{ 'chat-header-btn-disabled': !spaceId }"
                @tap="handleNewConversation"
              >
                <svg viewBox="0 0 256 256" class="chat-header-icon">
                  <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
            </view>

            <!-- Tool menu backdrop -->
            <view v-if="showToolMenu" class="tool-menu-backdrop" @tap="showToolMenu = false"></view>

            <!-- Messages Area -->
            <scroll-view
              class="chat-messages-list"
              scroll-y
              :scroll-top="scrollTopValue"
              @scroll="onChatScroll"
            >
              <!-- Empty state -->
              <view v-if="messages.length === 0 && !isLoadingHistory" class="chat-empty-state">
                <text class="chat-empty-icon">
                  <svg viewBox="0 0 256 256" width="48" height="48">
                    <rect width="256" height="256" fill="none"/>
                    <path d="M128,24A104,104,0,0,0,36.18,176.88L24.83,210.93a8,8,0,0,0,10.24,10.24l34.05-11.35A104,104,0,1,0,128,24Z" fill="none" stroke="rgba(255,255,255,0.15)" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  </svg>
                </text>
                <text class="chat-empty-title">{{ spaceId ? 'Start a conversation' : 'Select a space' }}</text>
                <text class="chat-empty-sub">{{ spaceId ? 'Ask anything about your study materials' : 'Choose a learning space from the sidebar' }}</text>
              </view>

              <!-- Loading history -->
              <view v-if="isLoadingHistory" class="chat-loading">
                <view class="typing-indicator">
                  <view class="typing-dot"></view>
                  <view class="typing-dot"></view>
                  <view class="typing-dot"></view>
                </view>
                <text class="chat-loading-text">Loading history...</text>
              </view>

              <!-- Message list -->
              <view
                v-for="msg in messages"
                :key="msg.id"
                class="message-row"
                :class="msg.role === 'user' ? 'message-row-right' : 'message-row-left'"
              >
                <!-- User message -->
                <view v-if="msg.role === 'user'" class="user-msg-group">
                  <!-- Image attachments outside bubble -->
                  <view v-if="msg.attachments && msg.attachments.length > 0" class="msg-attachments-wrapper">
                    <view class="msg-attachments">
                      <template v-for="att in msg.attachments" :key="att.id">
                        <image
                          v-if="att.attachment_type === 'image'"
                          class="msg-attach-img"
                          :src="resolveUrl(att.thumbnail_url || att.file_url)"
                          mode="aspectFill"
                          @tap="previewImage(resolveUrl(att.file_url))"
                        />
                        <view v-else class="msg-attach-file" @tap="openFileUrl(att.file_url)">
                          <text class="msg-attach-file-name">{{ att.original_filename }}</text>
                        </view>
                      </template>
                    </view>
                  </view>
                  <!-- Text bubble -->
                  <view class="user-bubble-row">
                    <view v-if="msg.isFailed" class="msg-retry-btn" @tap="resendMessage(msg)">
                      <svg viewBox="0 0 256 256" class="msg-retry-icon">
                        <polyline points="176.17 99.71 224.17 99.71 224.17 51.71" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                        <path d="M65.78,65.78a88,88,0,0,1,124.44,0l34,33.93" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                        <polyline points="79.83 156.29 31.83 156.29 31.83 204.29" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                        <path d="M190.22,190.22a88,88,0,0,1-124.44,0l-34-33.93" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                      </svg>
                    </view>
                    <view v-if="msg.content && msg.content.trim()" class="message-bubble bubble-user">
                      <text class="bubble-text">{{ msg.content }}</text>
                    </view>
                  </view>
                  <view v-if="msg.content && msg.content.trim()" class="user-msg-actions">
                    <svg viewBox="0 0 256 256" class="ai-msg-action-icon" @tap="copyMessage(msg)">
                      <rect x="32" y="80" width="128" height="144" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                      <path d="M96,80V40a8,8,0,0,1,8-8h112a8,8,0,0,1,8,8V176a8,8,0,0,1-8,8H160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                    </svg>
                  </view>
                </view>

                <!-- AI message -->
                <view v-else class="message-bubble bubble-ai">
                  <!-- Thinking block -->
                  <view v-if="msg.thinkingContent" class="thinking-block" :class="{ 'thinking-active': msg.isThinking }">
                    <view class="thinking-header" @tap="toggleThinking(msg.id)">
                      <view v-if="msg.isThinking" class="thinking-spinner"></view>
                      <text class="thinking-label">
                        {{ msg.isThinking ? '深度思考中...' : `已深度思考 ${msg.thinkingDuration} 秒` }}
                      </text>
                      <text class="thinking-chevron" :class="{ 'thinking-chevron-expanded': isThinkingExpanded(msg.id) || msg.isThinking }">&#9662;</text>
                    </view>
                    <view class="thinking-body" :class="{ 'thinking-body-collapsed': !isThinkingExpanded(msg.id) && !msg.isThinking }">
                      <text class="thinking-text">{{ msg.thinkingContent }}</text>
                    </view>
                  </view>

                  <!-- Segment-based rendering -->
                  <template v-for="(seg, segIdx) in getMessageSegments(msg)" :key="segIdx">
                    <!-- Text segment -->
                    <view v-if="seg.type === 'text'" class="segment-text">
                      <MarkdownRender :content="seg.content" />
                    </view>

                    <!-- Tool call segment -->
                    <view v-else-if="seg.type === 'tool'" class="segment-tool">
                      <!-- Memory tools: inline shimmer text -->
                      <view
                        v-if="isMemoryTool(seg.toolCall.tool)"
                        class="memory-tool-inline"
                        :class="{ 'memory-tool-active': getMemoryToolDisplayStatus(seg.toolCall) === 'running' }"
                      >
                        <text class="memory-tool-text">{{ getMemoryToolText(seg.toolCall.tool) }}</text>
                      </view>

                      <!-- Planning tools (get_tool_details): inline silver shimmer -->
                      <view
                        v-else-if="isPlanningTool(seg.toolCall.tool)"
                        class="planning-tool-inline"
                        :class="{
                          'planning-tool-active': getPlanningToolDisplayStatus(seg.toolCall) === 'running',
                          'planning-tool-done': getPlanningToolDisplayStatus(seg.toolCall) === 'done'
                        }"
                      >
                        <text class="planning-tool-text">{{ planningToolText }}</text>
                      </view>

                      <!-- Search tools: structured result card -->
                      <view
                        v-else-if="isSearchTool(seg.toolCall.tool)"
                        class="tool-call-card search-result-card"
                        :class="getToolCardClass(seg.toolCall)"
                      >
                        <view class="tool-call-header">
                          <view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <view class="tool-call-icon" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="tool-call-name">{{ getToolDisplayName(seg.toolCall.tool) }}</text>
                        </view>
                        <view v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.results?.length"
                          class="search-results-list">
                          <view v-for="(item, idx) in getVisibleSearchResults(seg.toolCall)" :key="idx"
                            class="search-result-item" @click="openSearchResultUrl(item.url)">
                            <image class="search-result-favicon"
                              :src="getFaviconUrl(item.url)" mode="aspectFit" />
                            <text class="search-result-title">{{ item.title }}</text>
                            <text class="search-result-domain">{{ formatDisplayUrl(item.url) }}</text>
                          </view>
                          <view v-if="seg.toolCall.result.results.length > 5"
                            class="search-results-toggle" @click="toggleSearchResults(seg.toolCall.id)">
                            <text class="search-results-toggle-text">
                              {{ isSearchExpanded(seg.toolCall.id) ? '收起' : '展开全部 ' + seg.toolCall.result.results.length + ' 条结果' }}
                            </text>
                          </view>
                        </view>
                        <text v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" class="tool-call-args">
                          {{ seg.toolCall.result?.message || '未找到相关结果' }}
                        </text>
                        <text v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="tool-call-args">
                          {{ seg.toolCall.result?.message || '搜索失败' }}
                        </text>
                      </view>

                      <!-- Note creation: rich card -->
                      <NoteCreationCard
                        v-else-if="seg.toolCall.tool === 'create_note'"
                        :tool-call="seg.toolCall"
                        :space-id="spaceId"
                        :conversation-id="conversationId"
                      />

                      <!-- Artifact creation/update: card -->
                      <ArtifactCreationCard
                        v-else-if="seg.toolCall.tool === 'create_artifact' || seg.toolCall.tool === 'update_artifact'"
                        :tool-call="seg.toolCall"
                        :space-id="spaceId"
                        :conversation-id="conversationId"
                        @view-artifact="handleViewArtifact"
                      />

                      <!-- Chart generation tool: image preview card -->
                      <view
                        v-else-if="seg.toolCall.tool === 'generate_chart'"
                        class="tool-call-card"
                        :class="getToolCardClass(seg.toolCall)"
                      >
                        <view class="tool-call-header">
                          <view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <view class="tool-call-icon" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="tool-call-name">{{ getToolDisplayName(seg.toolCall.tool) }}</text>
                        </view>
                        <view v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.image_url" class="chart-image-preview">
                          <img
                            :src="getFullImageUrl(seg.toolCall.result.image_url)"
                            class="chart-preview-img"
                            @click="previewChartImage(seg.toolCall.result.image_url)"
                          />
                        </view>
                        <view v-if="seg.toolCall.result?.auto_saved" class="chart-saved-badge">
                          <image class="chart-saved-icon" src="/static/icons/phosphor/regular/notebook-white.svg" mode="aspectFit" />
                          <span class="chart-saved-text">已保存为笔记</span>
                          <template v-if="seg.toolCall.result?.node_label">
                            <span class="chart-saved-text chart-saved-node"> · </span>
                            <image class="chart-saved-icon" src="/static/icons/phosphor/regular/push-pin-white.svg" mode="aspectFit" />
                            <span class="chart-saved-text chart-saved-node">{{ seg.toolCall.result.node_label }}</span>
                          </template>
                        </view>
                        <view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="tool-call-result">
                          <text class="tool-call-result-text">{{ seg.toolCall.result?.message || '图表生成失败' }}</text>
                        </view>
                      </view>

                      <!-- Code execution tool: code + output card -->
                      <view
                        v-else-if="seg.toolCall.tool === 'run_python_code'"
                        class="tool-call-card code-execution-card"
                        :class="getToolCardClass(seg.toolCall)"
                      >
                        <view class="tool-call-header">
                          <view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <view class="tool-call-icon" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="tool-call-name">{{ seg.toolCall.arguments?.description || getToolDisplayName(seg.toolCall.tool) }}</text>
                        </view>
                        <!-- Collapsible code block -->
                        <view class="code-block-section">
                          <view class="code-toggle-link" @click="toggleCodeExpand(seg.toolCall.id)">
                            <text class="code-toggle-text">{{ isCodeExpanded(seg.toolCall.id) ? '收起代码' : '查看代码' }}</text>
                            <text class="code-toggle-chevron" :class="{ 'code-toggle-chevron-expanded': isCodeExpanded(seg.toolCall.id) }">&#9662;</text>
                          </view>
                          <view class="code-block-wrapper" :class="{ 'code-block-collapsed': !isCodeExpanded(seg.toolCall.id) }">
                            <pre class="code-block-pre"><code class="code-block-code">{{ seg.toolCall.arguments?.code || '' }}</code></pre>
                          </view>
                        </view>
                        <!-- Output section -->
                        <view v-if="seg.toolCall.status === 'done'" class="code-output-section">
                          <pre v-if="seg.toolCall.result?.stdout" class="code-output-stdout">{{ seg.toolCall.result.stdout }}</pre>
                          <pre v-if="seg.toolCall.result?.stderr" class="code-output-stderr">{{ seg.toolCall.result.stderr }}</pre>
                          <view v-if="seg.toolCall.result?.image_url" class="chart-image-preview">
                            <img
                              :src="getFullImageUrl(seg.toolCall.result.image_url)"
                              class="chart-preview-img"
                              @click="previewChartImage(seg.toolCall.result.image_url)"
                            />
                          </view>
                          <text v-if="!seg.toolCall.success && seg.toolCall.result?.message" class="tool-call-result-text">{{ seg.toolCall.result.message }}</text>
                        </view>
                      </view>

                      <!-- Regular tools: card -->
                      <view
                        v-else
                        class="tool-call-card"
                        :class="getToolCardClass(seg.toolCall)"
                      >
                        <view class="tool-call-header">
                          <!-- Status icon -->
                          <view v-if="seg.toolCall.status === 'running'" class="tool-call-spinner"></view>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>

                          <!-- Tool icon -->
                          <view class="tool-call-icon" v-html="getToolIconSvg(seg.toolCall.tool)"></view>

                          <!-- Tool name -->
                          <text class="tool-call-name">{{ getToolDisplayName(seg.toolCall.tool) }}</text>
                        </view>

                        <!-- Tool arguments -->
                        <text v-if="seg.toolCall.arguments" class="tool-call-args">{{ formatToolArgs(seg.toolCall.arguments) }}</text>

                        <!-- Quiz entry card -->
                        <view
                          v-if="seg.toolCall.tool === 'generate_test' && seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.quizId"
                          class="quiz-entry-card"
                          @click="handleQuizEntryClick(seg.toolCall.quizId)"
                        >
                          <view class="quiz-entry-content">
                            <view class="quiz-entry-icon">
                              <svg viewBox="0 0 256 256" width="20" height="20">
                                <path d="M200,40H56A16,16,0,0,0,40,56V200a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V56A16,16,0,0,0,200,40Zm-36.69,77.49-56,56a8,8,0,0,1-11.32,0l-24-24a8,8,0,0,1,11.32-11.32L101.65,156.5l50.34-50.34a8,8,0,0,1,11.32,11.32Z" fill="currentColor"/>
                              </svg>
                            </view>
                            <view class="quiz-entry-text">
                              <text class="quiz-entry-title">测试题已生成</text>
                              <text class="quiz-entry-subtitle">点击进入测试</text>
                            </view>
                            <view class="quiz-entry-arrow">
                              <svg viewBox="0 0 256 256" width="16" height="16">
                                <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                              </svg>
                            </view>
                          </view>
                        </view>
                      </view>
                    </view>
                  </template>

                  <!-- Typing indicator during streaming -->
                  <view v-if="msg.isWaitingOutput" class="typing-indicator">
                    <view class="typing-dot"></view>
                    <view class="typing-dot"></view>
                    <view class="typing-dot"></view>
                  </view>
                </view>
              </view>

              <!-- Bottom padding for scroll -->
              <view style="height: 16px;"></view>
            </scroll-view>

            <!-- Attachment Preview Area -->
            <view v-if="pendingAttachments.length > 0" class="attach-preview-area">
              <view class="attach-preview-scroll">
                <view
                  v-for="(att, idx) in pendingAttachments"
                  :key="att.id"
                  class="attach-preview-item"
                >
                  <image
                    v-if="att.type === 'image'"
                    class="attach-preview-img"
                    :src="att.localPreview || att.thumbnail_url || att.file_url"
                    mode="aspectFill"
                  />
                  <view v-else class="attach-preview-file">
                    <text class="attach-preview-file-icon">📄</text>
                    <text class="attach-preview-file-name">{{ att.original_filename }}</text>
                  </view>
                  <view class="attach-preview-remove" @tap="removeAttachment(idx)">✕</view>
                  <view v-if="att.uploading" class="attach-preview-uploading">
                    <view class="attach-upload-spinner"></view>
                  </view>
                </view>
              </view>
            </view>

            <!-- Input Bar -->
            <view class="chat-input-bar">
              <!-- "+" button -->
              <view class="attach-btn-wrap">
                <view
                  class="attach-btn"
                  :class="{ 'attach-btn-disabled': !spaceId || isSending }"
                  @tap="toggleAttachMenu"
                >
                  <svg viewBox="0 0 256 256" class="attach-btn-icon">
                    <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                    <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                  </svg>
                </view>
                <transition name="attach-menu-fade">
                  <view v-if="showAttachMenu" class="attach-menu">
                    <view class="attach-menu-item" @tap="pickImage">
                      <image class="attach-menu-icon" mode="aspectFit" src="/static/icons/phosphor/regular/attach-image-white.svg" />
                      <text class="attach-menu-label">图片</text>
                    </view>
                    <view class="attach-menu-item" @tap="pickFile">
                      <image class="attach-menu-icon" mode="aspectFit" src="/static/icons/phosphor/flat-regular/attach-link-white.svg" />
                      <text class="attach-menu-label">文件</text>
                    </view>
                  </view>
                </transition>
              </view>

              <textarea
                ref="chatInput"
                class="chat-input chat-input-textarea"
                placeholder="Ask anything..."
                :rows="1"
                :maxlength="100000"
                confirm-type="send"
                :auto-height="false"
                :disabled="!spaceId"
                :style="chatInputDynamicStyle"
                v-model="inputText"
                @input="handleChatInput"
                @linechange="handleChatLineChange"
                @keydown="handleChatKeydown"
                @confirm="handleChatConfirm"
              />
              <!-- Stop button during streaming -->
              <view v-if="isStreaming" class="chat-stop-btn" @tap="handleStop">
                <svg viewBox="0 0 256 256" class="stop-icon">
                  <rect x="52" y="52" width="152" height="152" rx="12" fill="currentColor"/>
                </svg>
              </view>
              <!-- Send button -->
              <view v-else class="chat-send-btn" :class="{ 'chat-send-btn-disabled': !canSend }" @tap="handleSend">
                <svg viewBox="0 0 256 256" class="send-icon">
                  <rect width="256" height="256" fill="none"/>
                  <line x1="108" y1="148" x2="160" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M223.69,42.18a8,8,0,0,0-9.87-9.87l-192,58.22a8,8,0,0,0-1.25,14.93L108,148l42.54,87.42a8,8,0,0,0,14.93-1.25Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
            </view>

            <!-- Attach menu backdrop -->
            <view v-if="showAttachMenu" class="attach-menu-backdrop" @tap="showAttachMenu = false"></view>
          </view>
        </view>
      </view>
      <!-- History popup backdrop -->
      <view v-if="showHistoryPopup" class="history-backdrop" @tap="showHistoryPopup = false"></view>
      <!-- Model menu backdrop -->
      <view v-if="showModelMenu" class="model-menu-backdrop" @tap="showModelMenu = false"></view>

      <u-modal
        :visible="showDeleteSpaceModal"
        title="删除学习空间"
        :content="deleteSpaceModalContent"
        confirm-text="删除"
        confirm-type="danger"
        @confirm="confirmDeleteSpace"
        @close="showDeleteSpaceModal = false"
      />

      <!-- Share Mode Selection Modal -->
      <view v-if="showShareModeModal" class="share-modal-backdrop" @tap.self="showShareModeModal = false">
        <view class="share-modal-card">
          <text class="share-modal-title">选择分享方式</text>
          <view class="share-mode-options">
            <view class="share-mode-option" @tap="selectShareMode('clone')">
              <view class="share-mode-icon-wrap">
                <svg viewBox="0 0 256 256" class="share-mode-svg-icon">
                  <rect width="256" height="256" fill="none"/>
                  <rect x="40" y="72" width="144" height="144" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M72,72V56a8,8,0,0,1,8-8H216a8,8,0,0,1,8,8V200a8,8,0,0,1-8,8H184" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
              <view class="share-mode-info">
                <text class="share-mode-label">创建副本</text>
                <text class="share-mode-desc">对方导入后获得此空间的副本</text>
              </view>
              <svg viewBox="0 0 256 256" class="share-mode-arrow">
                <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              </svg>
            </view>
            <view class="share-mode-divider"></view>
            <view class="share-mode-option" @tap="selectShareMode('collaborative')">
              <view class="share-mode-icon-wrap">
                <svg viewBox="0 0 256 256" class="share-mode-svg-icon">
                  <rect width="256" height="256" fill="none"/>
                  <circle cx="88" cy="108" r="52" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M155.4,57.9A54,54,0,1,1,169.5,160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M16,197.4a88,88,0,0,1,144,0" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M169.5,160a88,88,0,0,1,72,37.4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
              <view class="share-mode-info">
                <text class="share-mode-label">共同学习</text>
                <text class="share-mode-desc">对方导入后加入此空间一起学习</text>
              </view>
              <svg viewBox="0 0 256 256" class="share-mode-arrow">
                <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              </svg>
            </view>
          </view>
        </view>
      </view>

      <!-- Share Code Modal -->
      <view v-if="showShareCodeModal" class="share-modal-backdrop" @tap.self="showShareCodeModal = false">
        <view class="share-modal-card">
          <text class="share-modal-title">分享学习空间</text>
          <text class="share-modal-sub">{{ currentShareMode === 'collaborative' ? '对方导入后将加入此空间共同学习' : '将分享码发送给好友，对方可导入此空间的知识图谱和笔记' }}</text>
          <view class="share-modal-code-box">
            <text class="share-modal-code">{{ displayShareCode }}</text>
          </view>
          <view class="share-modal-actions">
            <view class="share-modal-copy-btn" @tap="handleCopyShareCode">
              <text class="share-modal-copy-text">{{ copyBtnText }}</text>
            </view>
            <view class="share-modal-close-btn" @tap="showShareCodeModal = false">
              <text class="share-modal-close-text">关闭</text>
            </view>
          </view>
        </view>
      </view>
    </view>

  </view>

</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import KnowledgeGraph from '@/components/graph/KnowledgeGraph.vue'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import StudyMaterialsPanel from '@/components/study/StudyMaterialsPanel.vue'
import QuizPanel from '@/components/study/quiz/QuizPanel.vue'
import NotesPanel from '@/components/study/notes/NotesPanel.vue'
import NoteCreationCard from '@/components/study/notes/NoteCreationCard.vue'
import ArtifactCreationCard from '@/components/study/notes/ArtifactCreationCard.vue'
import UModal from '@/components/u-modal/u-modal.vue'
import UMasteryToast from '@/components/u-mastery-toast/u-mastery-toast.vue'
import UQuizNotification from '@/components/u-quiz-notification/u-quiz-notification.vue'
import UArtifactNotification from '@/components/u-artifact-notification/u-artifact-notification.vue'
import { connectNotificationStream } from '@/api/notification'
import { getSpaces, deleteSpace, getTaskStatus, generateKnowledgeGraph, getToolCatalog, updateSpace, getSpace, generateShareCode, getSpaceMembers } from '@/api/space'
import { createConversation, getSpaceConversations, getConversation, sendMessage, submitToolResult, uploadAttachment, deleteAttachment, getModels } from '@/api/chat'
import { getCalendarEvents, createCalendarEvent, updateCalendarEvent, deleteCalendarEvent } from '@/api/calendar'
import { useUserStore } from '@/store/user'
import { useSpacesStore } from '@/store/spaces'
import config from '@/config'

// Tool display name mapping
const TOOL_DISPLAY_NAMES = {
  get_graph_overview: 'Get Knowledge Graph',
  add_node: 'Add Node',
  add_edge: 'Add Edge',
  delete_node: 'Delete Node',
  delete_edge: 'Delete Edge',
  update_mastery: 'Update Mastery',
  get_child_nodes: 'Get Child Nodes',
  get_parent_nodes: 'Get Parent Nodes',
  get_sibling_nodes: 'Get Siblings',
  generate_learning_path: 'Generate Path',
  extend_learning_path: 'Extend Path',
  get_learning_paths: 'Get Paths',
  delete_all_learning_paths: 'Delete Paths',
  get_postorder_traversal: 'Traverse Graph',
  get_schedule: 'View Schedule',
  add_schedule: 'Add Schedule',
  delete_schedule: 'Delete Schedule',
  update_schedule: 'Update Schedule',
  web_search: 'Web Search',
  web_fetch: 'Fetch Page',
  search_documents: 'Search Documents',
  generate_test: 'Generate Test',
  write_to_long_term_memory: 'Update Memory',
  delete_from_long_term_memory: 'Delete Memory',
  write_to_space_memory: 'Update Space Memory',
  delete_from_space_memory: 'Delete Space Memory',
  get_review_events: 'View Reviews',
  mark_review_completed: 'Mark Reviewed',
  academic_search: '学术搜索',
  encyclopedia_search: '百科搜索',
  course_search: 'B站课程搜索',
  create_note: '创建笔记',
  list_notes: 'List Notes',
  view_note_detail: 'View Note',
  update_note: 'Update Note',
  delete_note: 'Delete Note',
  generate_chart: 'Generate Chart',
  annotate_panel: '面板标注',
  run_python_code: '执行 Python 代码'
}

// Graph-mutating tools (trigger auto-refresh of knowledge graph)
const GRAPH_MUTATING_TOOLS = new Set([
  'add_node',
  'add_edge',
  'delete_node',
  'delete_edge',
  'update_mastery',
  'generate_learning_path',
  'extend_learning_path',
  'delete_all_learning_paths'
])

// Schedule tools (auto-executed via backend API on web)
const SCHEDULE_TOOLS = new Set(['get_schedule', 'add_schedule', 'delete_schedule', 'update_schedule'])

// Planning tools (shown as inline shimmer text that fades out)
const PLANNING_TOOLS = new Set(['get_tool_details'])
const PLANNING_TOOL_TEXT = '正在规划下一步……'

// Memory tools (shown as inline shimmer text, not cards)
const MEMORY_TOOLS = new Set([
  'write_to_long_term_memory',
  'delete_from_long_term_memory',
  'write_to_space_memory',
  'delete_from_space_memory'
])

const MEMORY_TOOL_TEXT = {
  write_to_long_term_memory: 'Updating long-term memory...',
  delete_from_long_term_memory: 'Deleting long-term memory...',
  write_to_space_memory: 'Updating space preferences...',
  delete_from_space_memory: 'Deleting space preferences...'
}

// Tool icon SVGs by category
const TOOL_ICON_SVGS = {
  graph: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="96" cy="96" r="24" fill="none" stroke="currentColor" stroke-width="16"/><circle cx="176" cy="160" r="24" fill="none" stroke="currentColor" stroke-width="16"/><circle cx="176" cy="64" r="24" fill="none" stroke="currentColor" stroke-width="16"/><line x1="116" y1="81" x2="156" y2="70" fill="none" stroke="currentColor" stroke-width="16"/><line x1="113" y1="110" x2="159" y2="147" fill="none" stroke="currentColor" stroke-width="16"/></svg>',
  memory: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M128,24A96,96,0,0,0,64,184V224h128V184A96,96,0,0,0,128,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="112" y1="224" x2="112" y2="192" fill="none" stroke="currentColor" stroke-width="16"/><line x1="144" y1="224" x2="144" y2="192" fill="none" stroke="currentColor" stroke-width="16"/></svg>',
  search: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="116" cy="116" r="84" fill="none" stroke="currentColor" stroke-width="16"/><line x1="175.4" y1="175.4" x2="224" y2="224" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>',
  calendar: '<svg viewBox="0 0 256 256" width="14" height="14"><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-width="16"/><line x1="176" y1="24" x2="176" y2="56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><line x1="80" y1="24" x2="80" y2="56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><line x1="40" y1="88" x2="216" y2="88" fill="none" stroke="currentColor" stroke-width="16"/></svg>',
  review: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-width="16"/><polyline points="128 80 128 128 168 152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  note: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M200,32H56A16,16,0,0,0,40,48V208a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32ZM80,80h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h64a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Z" fill="currentColor"/></svg>',
  image: '<svg viewBox="0 0 256 256" width="14" height="14"><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="100" cy="92" r="16" fill="none" stroke="currentColor" stroke-width="16"/><path d="M80,160l40-48,40,32,48-56,48,40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  code: '<svg viewBox="0 0 256 256" width="14" height="14"><polyline points="64 88 16 128 64 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="192 88 240 128 192 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="160" y1="40" x2="96" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  default: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-width="16"/><path d="M128,48a80,80,0,0,1,80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M48,128a80,80,0,0,1,80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M208,128a80,80,0,0,1-80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M128,208a80,80,0,0,1-80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>'
}

// Map tool names to icon categories
const TOOL_ICON_MAP = {
  get_graph_overview: 'graph', add_node: 'graph', add_edge: 'graph',
  delete_node: 'graph', delete_edge: 'graph', update_mastery: 'graph',
  get_child_nodes: 'graph', get_parent_nodes: 'graph', get_sibling_nodes: 'graph',
  generate_learning_path: 'graph', extend_learning_path: 'graph', get_learning_paths: 'graph',
  delete_all_learning_paths: 'graph', get_postorder_traversal: 'graph',
  get_schedule: 'calendar', add_schedule: 'calendar',
  delete_schedule: 'calendar', update_schedule: 'calendar',
  generate_test: 'default',
  web_search: 'search', web_fetch: 'search', search_documents: 'search',
  write_to_long_term_memory: 'memory', delete_from_long_term_memory: 'memory',
  write_to_space_memory: 'memory', delete_from_space_memory: 'memory',
  get_review_events: 'review', mark_review_completed: 'review',
  create_note: 'note', list_notes: 'note', view_note_detail: 'note',
  update_note: 'note', delete_note: 'note',
  generate_chart: 'image',
  annotate_panel: 'default',
  run_python_code: 'code'
}

const DEFAULT_BROWSER_URL = 'https://www.wikipedia.org'
const BROWSER_LOAD_TIMEOUT_MS = 8000

export default {
  components: { HomeSidebar, KnowledgeGraph, MarkdownRender, StudyMaterialsPanel, QuizPanel, NotesPanel, NoteCreationCard, ArtifactCreationCard, UModal, UMasteryToast, UQuizNotification, UArtifactNotification },
  data() {
    return {
      sidebarCollapsed: false,
      spaceId: null,
      spaceName: 'Study',
      activeTab: 'graph',
      isPathHighlightOn: false,
      graphDirty: false,
      tabs: [
        { id: 'graph', label: '知识图谱', placeholder: 'Knowledge Graph', sub: 'Canvas area for nodes and edges' },
        { id: 'materials', label: '学习资料', placeholder: 'Study Materials', sub: 'Upload and manage learning resources' },
        { id: 'quizzes', label: '测试题', placeholder: 'Quizzes', sub: 'Practice tests and assessments' },
        { id: 'notes', label: '笔记', placeholder: 'Notes', sub: 'Your study notes and highlights' },
        { id: 'browser', label: '自由网页', placeholder: 'Web Browser', sub: 'Browse the web freely' }
      ],
      browserInputUrl: DEFAULT_BROWSER_URL,
      browserCurrentUrl: DEFAULT_BROWSER_URL,
      browserHistory: [DEFAULT_BROWSER_URL],
      browserHistoryIndex: 0,
      browserFrameKey: 1,
      browserLoading: false,
      browserLoadError: false,
      browserErrorMessage: '',
      browserLoadTimeoutId: null,
      browserInitialized: false,

      // Chat state
      messages: [],
      conversationId: null,
      inputText: '',
      chatInputHeight: 36,
      chatInputLineHeight: 20,
      chatInputVerticalPadding: 14,
      chatInputExtraPerWrappedLine: 0,
      chatInputMultiLineCompensation: 2,
      chatInputMaxLines: 6,
      chatInputMinHeight: 36,
      nextId: 1,
      isStreaming: false,
      isSending: false,
      isLoadingHistory: false,
      cancelSSE: null,
      activeToolCalls: [],
      scrollTopValue: 0,
      isAutoScrollEnabled: true,
      memoryToolDelayedDone: {},
      memoryToolStartTimes: {},
      planningToolDelayedDone: {},
      planningToolStartTimes: {},
      expandedSearchResults: {},
      expandedCodeBlocks: {},

      // Thinking model state
      thinkingStartTime: null,
      thinkingExpanded: {},
      thinkingBuffer: '',
      thinkingTimer: null,
      thinkingMsgId: null,

      // Typewriter buffer
      typewriterBuffer: '',
      typewriterTimer: null,
      typewriterMsgId: null,
      typewriterSpeed: 30,

      // Conversation history popup
      showHistoryPopup: false,
      historyConversations: [],
      isLoadingConversations: false,

      // Attachment upload
      pendingAttachments: [],
      showAttachMenu: false,

      // Model selection
      availableModels: [],
      selectedModelId: null,
      showModelMenu: false,

      // Tool mode
      toolMode: 'auto',
      enabledTools: null,
      showToolMenu: false,
      toolCatalog: null,
      toolCatalogLoading: false,

      // Space delete
      isDeletingSpace: false,
      showDeleteSpaceModal: false,
      deleteTargetSpaceId: null,
      deleteTargetSpaceName: '',

      // Space share
      showShareModeModal: false,
      showShareCodeModal: false,
      shareCode: '',
      displayShareCode: '',
      currentShareMode: 'clone',
      isGeneratingShareCode: false,
      copyBtnText: '复制分享码',

      // Mastery notification
      masteryNotifications: [],
      notificationAbort: null,
      notificationIdCounter: 0,

      // Quiz evaluation notifications
      quizEvaluationNotifications: [],
      quizNotificationIdCounter: 0,

      // Artifact completion tracking
      artifactNotifications: [],
      artifactNotificationIdCounter: 0,

      // Quiz generation polling
      isGeneratingQuiz: false,
      activeQuizId: null,
      quizPollTimer: null,
      lastChatEnterMeta: null,

      // Knowledge graph generation polling
      graphTaskId: null,
      graphGenerating: false,
      _abortGraphPoll: false,

      // Dual-sync mode
      dualSyncEnabled: false,
      annotations: [],

      // Collaborative space state
      isCollaborative: false,
      userRole: null,
      spaceMembers: [],
      selectedMemberUserId: null,
      showMemberDropdown: false,
      currentUserId: null
    }
  },
  watch: {
    dualSyncEnabled(val) {
      if (!val) {
        this.annotations = []
      }
    }
  },
  computed: {
    planningToolText() {
      return PLANNING_TOOL_TEXT
    },
    activeTabInfo() {
      return this.tabs.find(t => t.id === this.activeTab) || this.tabs[0]
    },
    currentUserTier() {
      const userStore = useUserStore()
      const tier = userStore?.user?.subscription_tier
      return typeof tier === 'string' ? tier.toUpperCase() : 'FREE'
    },
    canBrowserBack() {
      return this.browserHistoryIndex > 0
    },
    canBrowserForward() {
      return this.browserHistoryIndex < this.browserHistory.length - 1
    },
    canSend() {
      return this.spaceId && this.inputText.trim().length > 0 && !this.isSending
    },
    selectedModelName() {
      const model = this.availableModels.find(m => m.id === this.selectedModelId)
      return model ? model.display_name : 'Model'
    },
    toolModeLabel() {
      return this.toolMode === 'auto' ? '自动' : '手动'
    },
    chatInputMaxHeight() {
      const base = this.chatInputLineHeight * this.chatInputMaxLines + this.chatInputVerticalPadding
      const extra = this.chatInputExtraPerWrappedLine * Math.max(0, this.chatInputMaxLines - 1)
      return base + extra + this.chatInputMultiLineCompensation
    },
    chatInputDynamicStyle() {
      const height = Math.max(this.chatInputMinHeight, Math.min(this.chatInputHeight, this.chatInputMaxHeight))
      return {
        height: `${height}px`,
        maxHeight: `${this.chatInputMaxHeight}px`,
        overflowY: height >= this.chatInputMaxHeight ? 'auto' : 'hidden'
      }
    },
    deleteSpaceModalContent() {
      const displayName = this.deleteTargetSpaceName || this.spaceName || '当前学习空间'
      return `确定要删除「${displayName}」吗？该空间内的知识图谱、资料和测试会被永久删除。`
    },
    selectedMemberColor() {
      if (!this.selectedMemberUserId) {
        const self = this.spaceMembers.find(m => m.user_id === this.currentUserId)
        return self ? self.color : '#0088FF'
      }
      const member = this.spaceMembers.find(m => m.user_id === this.selectedMemberUserId)
      return member ? member.color : '#0088FF'
    },
    selectedMemberName() {
      if (!this.selectedMemberUserId || this.selectedMemberUserId === this.currentUserId) return '我'
      const member = this.spaceMembers.find(m => m.user_id === this.selectedMemberUserId)
      return member ? member.nickname : '我'
    }
  },
  async onLoad(options) {
    if (options.spaceId) {
      this.spaceId = options.spaceId
      if (options.graphTaskId) {
        this.graphTaskId = options.graphTaskId
        this.graphGenerating = true
      }
      await this.loadSpaceInfo()
      this.loadSpaceToolMode()
      this.initConversation()
      if (this.graphTaskId) {
        this.pollGraphTask(this.graphTaskId)
      }
    }
  },
  onUnload() {
    this.clearBrowserLoadTimeout()
  },
  mounted() {
    this._graphRefreshTimer = null
    this.loadModels()
    this.setupNotificationStream()
    const inputEl = this.getChatInputElement()
    if (inputEl && typeof inputEl.addEventListener === 'function') {
      inputEl.addEventListener('paste', this.handlePaste)
      inputEl.addEventListener('keydown', this.handleNativeChatKeydown)
    }
    this.$nextTick(() => {
      this.resetChatInputHeight()
    })
    // Listen for scroll/pan on left panel to clear stale annotations
    this._clearAnnotationsOnWheel = () => {
      if (this.annotations.length > 0) {
        this.annotations = []
      }
    }
    this._clearAnnotationsOnMousedown = () => {
      if (this.annotations.length > 0) {
        this.annotations = []
      }
    }
    const tabContentEl = document.querySelector('.tab-content-area')
    if (tabContentEl) {
      tabContentEl.addEventListener('wheel', this._clearAnnotationsOnWheel)
      tabContentEl.addEventListener('mousedown', this._clearAnnotationsOnMousedown)
    }
  },
  beforeUnmount() {
    if (this.notificationAbort) {
      this.notificationAbort()
      this.notificationAbort = null
    }
    const inputEl = this.getChatInputElement()
    if (inputEl && typeof inputEl.removeEventListener === 'function') {
      inputEl.removeEventListener('paste', this.handlePaste)
      inputEl.removeEventListener('keydown', this.handleNativeChatKeydown)
    }
    this.cleanupPendingAttachments()
    this.stopTypewriter()
    this.flushThinkingBuffer()
    this.clearQuizPollState()
    if (this._graphRefreshTimer) {
      clearTimeout(this._graphRefreshTimer)
      this._graphRefreshTimer = null
    }
    this._abortGraphPoll = true
    const tabContentEl = document.querySelector('.tab-content-area')
    if (tabContentEl) {
      if (this._clearAnnotationsOnWheel) {
        tabContentEl.removeEventListener('wheel', this._clearAnnotationsOnWheel)
      }
      if (this._clearAnnotationsOnMousedown) {
        tabContentEl.removeEventListener('mousedown', this._clearAnnotationsOnMousedown)
      }
    }
  },
  methods: {
    resolveUrl(url) {
      if (!url) return ''
      if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) return url
      return config.API_BASE_URL + url
    },

    // ==================== Mastery Notifications ====================
    setupNotificationStream() {
      this.notificationAbort = connectNotificationStream({
        onMasteryUpdate: (data) => this.onMasteryUpdate(data),
        onQuizEvaluationComplete: (data) => this.onQuizEvaluationComplete(data),
        onLearningPathExpanded: (data) => this.onLearningPathExpanded(data),
        onArtifactReady: (data) => this.onArtifactReady(data)
      })
    },

    onMasteryUpdate(data) {
      const { node_name, change, new_mastery } = data
      this.notificationIdCounter++
      const id = this.notificationIdCounter
      const index = this.masteryNotifications.length
      this.masteryNotifications = [
        ...this.masteryNotifications,
        { id, visible: true, nodeName: node_name, change, index }
      ]

      if (this.activeTab === 'graph' && this.$refs.knowledgeGraph) {
        this.$refs.knowledgeGraph.highlightNode(node_name, new_mastery, change)
      }
    },

    removeMasteryNotification(id) {
      this.masteryNotifications = this.masteryNotifications.filter(n => n.id !== id)
    },

    // ==================== Learning Path Expansion Notifications ====================
    onLearningPathExpanded(data) {
      const { space_id, new_nodes, junction_node } = data
      if (space_id !== this.spaceId) return

      const animationPath = junction_node
        ? [junction_node, ...new_nodes]
        : new_nodes
      if (animationPath.length > 0) {
        this.handleLearningPathAnimation(animationPath)
      }
    },

    // ==================== Quiz Evaluation Notifications ====================
    onQuizEvaluationComplete(data) {
      const { quiz_id, quiz_topic, score, total_score, status: evalStatus } = data
      this.quizNotificationIdCounter++
      const id = this.quizNotificationIdCounter
      const index = this.quizEvaluationNotifications.length
      this.quizEvaluationNotifications = [
        ...this.quizEvaluationNotifications,
        { id, visible: true, quizId: quiz_id, quizTopic: quiz_topic, score, totalScore: total_score, status: evalStatus, index }
      ]

      // 如果当前在 quizzes tab，自动刷新列表
      if (this.activeTab === 'quizzes' && this.$refs.quizPanel) {
        this.$refs.quizPanel.loadQuizzes()
      }
    },

    handleQuizNotificationClick(notification) {
      this.removeQuizNotification(notification.id)
      this.activeTab = 'quizzes'
      this.$nextTick(() => {
        if (this.$refs.quizPanel) {
          this.$refs.quizPanel.navigateToQuizResult(notification.quizId)
        }
      })
    },

    removeQuizNotification(id) {
      this.quizEvaluationNotifications = this.quizEvaluationNotifications.filter(n => n.id !== id)
    },

    // ==================== Artifact Notifications ====================
    onArtifactReady(data) {
      const { note_id, space_id, status, title, error_message } = data
      if (String(space_id) !== String(this.spaceId)) return

      // Directly update the toolCall's result.status in the message segments
      if (note_id) {
        this.updateArtifactToolCallStatus(note_id, status)
      }

      // Push toast notification
      this.artifactNotificationIdCounter++
      const id = this.artifactNotificationIdCounter
      const index = this.artifactNotifications.length
      this.artifactNotifications = [
        ...this.artifactNotifications,
        {
          id,
          visible: true,
          noteId: note_id,
          title: title || '交互演示',
          status: status === 'done' ? 'done' : 'failed',
          errorMessage: error_message || '',
          index
        }
      ]

      // Refresh notes panel if on notes tab
      if (status === 'done' && this.activeTab === 'notes' && this.$refs.notesPanel) {
        this.$refs.notesPanel.loadNotes()
      }
    },

    handleArtifactNotificationClick(notification) {
      this.removeArtifactNotification(notification.id)
      if (notification.noteId) {
        this.activeTab = 'notes'
        this.$nextTick(async () => {
          const notesPanel = this.$refs.notesPanel
          if (notesPanel) {
            await notesPanel.loadNotes()
            notesPanel.openNoteById(notification.noteId)
          }
        })
      }
    },

    removeArtifactNotification(id) {
      this.artifactNotifications = this.artifactNotifications.filter(n => n.id !== id)
    },

    updateArtifactToolCallStatus(noteId, newStatus) {
      for (const msg of this.messages) {
        const updateSegments = (segments) => {
          if (!Array.isArray(segments)) return false
          for (const seg of segments) {
            if (seg.type === 'tool' && seg.toolCall &&
                (seg.toolCall.tool === 'create_artifact' || seg.toolCall.tool === 'update_artifact') &&
                seg.toolCall.result?.note_id === noteId) {
              seg.toolCall = { ...seg.toolCall, result: { ...seg.toolCall.result, status: newStatus } }
              return true
            }
          }
          return false
        }
        if (updateSegments(msg.segments) || updateSegments(msg.streamSegments)) {
          break
        }
      }
      this.$forceUpdate()
    },

    handleViewArtifact({ noteId, spaceId }) {
      if (!noteId) return
      if (spaceId && String(spaceId) !== String(this.spaceId)) return
      this.activeTab = 'notes'
      this.$nextTick(() => {
        const notesPanel = this.$refs.notesPanel
        if (notesPanel) {
          notesPanel.openNoteById(noteId)
        }
      })
    },

    // ==================== Knowledge Graph Generation Polling ====================
    async pollGraphTask(taskId) {
      const maxAttempts = 150 // ~5 minutes at 2s interval
      for (let i = 0; i < maxAttempts; i++) {
        if (this._abortGraphPoll) return
        try {
          const task = await getTaskStatus(taskId)
          if (task.status === 'done') {
            await new Promise(r => setTimeout(r, 2000))
            this.graphGenerating = false
            this.graphTaskId = null
            this.$nextTick(() => {
              if (this.$refs.knowledgeGraph) {
                this.$refs.knowledgeGraph.loadAndRender()
              }
            })
            return
          }
          if (task.status === 'failed') {
            this.graphGenerating = false
            this.graphTaskId = null
            return
          }
        } catch (err) {
          // Network error — continue polling
        }
        await new Promise(r => setTimeout(r, 2000))
      }
      // Timeout
      this.graphGenerating = false
      this.graphTaskId = null
    },

    async handleGraphRetry() {
      if (this.graphGenerating || !this.spaceId) return
      this.graphGenerating = true
      try {
        const taskRes = await generateKnowledgeGraph(this.spaceId, {
          topic: this.spaceName
        })
        await this.pollGraphTask(taskRes.task_id)
      } catch (err) {
        this.graphGenerating = false
      }
    },

    // ==================== Model Selection ====================
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
        console.error('[StudyPage] Failed to load models:', err)
      }
    },

    // ==================== Tool Mode ====================
    toggleToolMenu() {
      this.showToolMenu = !this.showToolMenu
      if (this.showToolMenu && !this.toolCatalog) {
        this.loadToolCatalog()
      }
    },
    async loadToolCatalog() {
      if (this.toolCatalogLoading) return
      this.toolCatalogLoading = true
      try {
        const res = await getToolCatalog()
        this.toolCatalog = res || []
      } catch (err) {
        console.error('[StudyPage] Failed to load tool catalog:', err)
      } finally {
        this.toolCatalogLoading = false
      }
    },
    async loadSpaceToolMode() {
      if (!this.spaceId) return
      try {
        const space = await getSpace(this.spaceId)
        this.toolMode = space.tool_mode || 'auto'
        this.enabledTools = space.enabled_tools || null
      } catch (err) {
        console.error('[StudyPage] Failed to load space tool mode:', err)
      }
    },
    async selectToolMode(mode) {
      if (mode === this.toolMode) return
      let newEnabledTools = this.enabledTools
      if (mode === 'manual' && !this.enabledTools) {
        if (!this.toolCatalog) await this.loadToolCatalog()
        const allNames = (this.toolCatalog || []).flatMap(cat => cat.tools.map(t => t.name))
        newEnabledTools = allNames
      }
      this.toolMode = mode
      this.enabledTools = newEnabledTools
      this.saveToolMode()
    },
    toggleTool(toolName) {
      if (!this.enabledTools) return
      const idx = this.enabledTools.indexOf(toolName)
      if (idx >= 0) {
        this.enabledTools = this.enabledTools.filter(n => n !== toolName)
      } else {
        this.enabledTools = [...this.enabledTools, toolName]
      }
      this.saveToolMode()
    },
    isToolEnabled(toolName) {
      if (!this.enabledTools) return true
      return this.enabledTools.includes(toolName)
    },
    getCategoryEnabledCount(category) {
      if (!this.enabledTools) return category.tools.length
      return category.tools.filter(t => this.enabledTools.includes(t.name)).length
    },
    async saveToolMode() {
      if (!this.spaceId) return
      try {
        await updateSpace(this.spaceId, {
          tool_mode: this.toolMode,
          enabled_tools: this.toolMode === 'manual' ? this.enabledTools : null,
        })
      } catch (err) {
        console.error('[StudyPage] Failed to save tool mode:', err)
      }
    },

    getChatInputHostElement() {
      const ref = this.$refs.chatInput
      if (!ref) return null
      if (ref.$el && ref.$el.nodeType === 1) return ref.$el
      if (ref.nodeType === 1) return ref
      return null
    },

    getChatInputElement() {
      const host = this.getChatInputHostElement()
      if (host && typeof host.querySelector === 'function') {
        const inner = host.querySelector('textarea, .uni-textarea-textarea, input')
        if (inner) return inner
      }

      if (this.$el && typeof this.$el.querySelector === 'function') {
        const fallback = this.$el.querySelector(
          '.chat-input-textarea textarea, .chat-input-textarea .uni-textarea-textarea, textarea.chat-input-textarea'
        )
        if (fallback) return fallback
      }

      return host
    },

    handleChatInput(event) {
      const value = event?.detail?.value
      if (typeof value === 'string' && value !== this.inputText) {
        this.inputText = value
      }
      if (!this.inputText) {
        this.resetChatInputHeight()
      }
    },

    handleChatLineChange(event) {
      const rawLineCount = Number(event?.detail?.lineCount)
      if (!Number.isFinite(rawLineCount)) {
        this.recalcChatInputHeight()
        return
      }
      const lineCount = Math.max(1, Math.floor(rawLineCount))

      if (lineCount <= 1) {
        this.resetChatInputHeight()
        return
      }

      const clampedLineCount = Math.min(lineCount, this.chatInputMaxLines)
      const perLineGrowth = this.chatInputLineHeight
      const lineBasedHeight = Math.min(
        this.chatInputMaxHeight,
        this.chatInputMinHeight + (clampedLineCount - 1) * perLineGrowth + this.chatInputMultiLineCompensation
      )
      let nextHeight = lineBasedHeight
      const inputEl = this.getChatInputElement()
      if (inputEl && typeof inputEl.scrollHeight === 'number') {
        inputEl.style.height = 'auto'
        const hostEl = this.getChatInputHostElement()
        const structuralPadding = inputEl !== hostEl ? this.chatInputVerticalPadding : 0
        const measuredNeeded = Math.ceil(inputEl.scrollHeight) + structuralPadding + this.chatInputMultiLineCompensation
        nextHeight = Math.max(nextHeight, measuredNeeded)
      }
      nextHeight = Math.max(this.chatInputMinHeight, Math.min(this.chatInputMaxHeight, nextHeight))
      this.chatInputHeight = nextHeight
      this.applyChatInputDomStyle(nextHeight)
    },

    handleNativeChatKeydown(event) {
      if (!event) return
      if (event.isComposing || event.keyCode === 229) return

      const keyCodeRaw = event.keyCode ?? event?.detail?.keyCode
      const keyCode = Number.isFinite(Number(keyCodeRaw)) ? Number(keyCodeRaw) : null
      const key = typeof event.key === 'string'
        ? event.key
        : (typeof event?.detail?.key === 'string' ? event.detail.key : '')
      const isEnter = key === 'Enter' || keyCode === 13
      if (!isEnter) return

      const shiftFromEvent = event.shiftKey ?? event?.detail?.shiftKey
      const shiftFromModifier = typeof event.getModifierState === 'function'
        ? event.getModifierState('Shift')
        : false
      const shiftFromOriginalModifier = typeof event?.originalEvent?.getModifierState === 'function'
        ? event.originalEvent.getModifierState('Shift')
        : false
      const isShiftEnter = Boolean(shiftFromEvent || shiftFromModifier || shiftFromOriginalModifier) || keyCode === 10
      this.lastChatEnterMeta = { at: Date.now(), shift: isShiftEnter }
      if (isShiftEnter) {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        if (typeof event.stopPropagation === 'function') event.stopPropagation()
        this.insertChatNewlineAtCursor()
        return
      }

      if (typeof event.preventDefault === 'function') event.preventDefault()
      if (typeof event.stopPropagation === 'function') event.stopPropagation()
      this.handleSend()
    },

    insertChatNewlineAtCursor() {
      const inputEl = this.getChatInputElement()
      const currentValue = typeof this.inputText === 'string' ? this.inputText : ''
      let start = currentValue.length
      let end = currentValue.length
      if (inputEl && typeof inputEl.selectionStart === 'number' && typeof inputEl.selectionEnd === 'number') {
        start = inputEl.selectionStart
        end = inputEl.selectionEnd
      }

      this.inputText = `${currentValue.slice(0, start)}\n${currentValue.slice(end)}`
      this.$nextTick(() => {
        const latestInput = this.getChatInputElement()
        if (latestInput) {
          if (typeof latestInput.focus === 'function') latestInput.focus()
          if (typeof latestInput.setSelectionRange === 'function') {
            const cursor = start + 1
            latestInput.setSelectionRange(cursor, cursor)
          }
        }
        this.recalcChatInputHeight()
      })
    },

    handleChatConfirm() {
      const meta = this.lastChatEnterMeta
      this.lastChatEnterMeta = null
      if (meta && Date.now() - meta.at < 600) {
        if (meta.shift) {
          this.$nextTick(() => {
            const inputEl = this.getChatInputElement()
            if (inputEl && typeof inputEl.focus === 'function') {
              inputEl.focus()
            }
          })
        }
        return
      }
      this.handleSend()
    },

    handleChatKeydown(event) {
      const nativeEvent = event?.originalEvent
      if (nativeEvent) {
        this.handleNativeChatKeydown(nativeEvent)
      }
    },

    recalcChatInputHeight() {
      const minHeight = this.chatInputMinHeight
      const maxHeight = this.chatInputMaxHeight
      if (!this.inputText) {
        this.chatInputHeight = minHeight
        this.applyChatInputDomStyle(minHeight)
        return
      }

      const inputEl = this.getChatInputElement()
      if (!inputEl || typeof inputEl.scrollHeight !== 'number') {
        this.chatInputHeight = minHeight
        this.applyChatInputDomStyle(minHeight)
        return
      }

      inputEl.style.height = 'auto'
      const measured = Math.ceil(inputEl.scrollHeight || minHeight)
      const hostEl = this.getChatInputHostElement()
      const structuralPadding = inputEl !== hostEl ? this.chatInputVerticalPadding : 0
      const measuredHeight = Math.max(minHeight, measured + structuralPadding + this.chatInputMultiLineCompensation)
      const wrapTriggerHeight = minHeight + this.chatInputLineHeight * 0.7
      if (measuredHeight <= wrapTriggerHeight) {
        this.chatInputHeight = minHeight
        this.applyChatInputDomStyle(minHeight)
        return
      }

      const nextHeight = Math.min(maxHeight, measuredHeight)
      this.chatInputHeight = nextHeight
      this.applyChatInputDomStyle(nextHeight)
    },

    applyChatInputDomStyle(height) {
      const hostEl = this.getChatInputHostElement()
      const inputEl = this.getChatInputElement()
      const maxHeight = this.chatInputMaxHeight

      const frameEl = hostEl && hostEl.style ? hostEl : (inputEl && inputEl.style ? inputEl : null)
      if (!frameEl) return

      frameEl.style.height = `${height}px`
      frameEl.style.maxHeight = `${maxHeight}px`
      frameEl.style.overflowY = height >= maxHeight ? 'auto' : 'hidden'

      if (inputEl && inputEl !== frameEl && inputEl.style) {
        inputEl.style.height = '100%'
        inputEl.style.maxHeight = '100%'
        inputEl.style.overflowY = height >= maxHeight ? 'auto' : 'hidden'
      }

      if (inputEl && typeof inputEl.scrollTop === 'number' && height < maxHeight) {
        inputEl.scrollTop = 0
      }
    },

    resetChatInputHeight() {
      this.chatInputHeight = this.chatInputMinHeight
      this.applyChatInputDomStyle(this.chatInputMinHeight)
    },

    async loadSpaceInfo() {
      if (!this.spaceId) {
        this.spaceName = 'Study'
        this.isCollaborative = false
        this.userRole = null
        this.spaceMembers = []
        this.selectedMemberUserId = null
        return
      }
      try {
        const res = await getSpaces()
        const spaces = res.data || res || []
        const space = spaces.find(s => String(s.id) === String(this.spaceId))
        this.spaceName = space ? space.name : 'Study'
        this.isCollaborative = space ? !!space.is_collaborative : false
        this.userRole = space ? space.user_role : null

        // Load current user ID
        const userStore = useUserStore()
        this.currentUserId = userStore.user?.id || null

        // Load members for collaborative spaces
        if (this.isCollaborative) {
          await this.loadSpaceMembers()
        } else {
          this.spaceMembers = []
          this.selectedMemberUserId = null
        }
      } catch (error) {
        console.error('[StudyPage] Failed to load space info:', error)
      }
    },

    async loadSpaceMembers() {
      if (!this.spaceId) return
      try {
        const res = await getSpaceMembers(this.spaceId)
        this.spaceMembers = res.data || res || []
      } catch (error) {
        console.error('[StudyPage] Failed to load members:', error)
        this.spaceMembers = []
      }
    },

    selectMemberFilter(member) {
      this.selectedMemberUserId = member.user_id
      this.showMemberDropdown = false
      // loadAndRender() is triggered by the targetUserId watcher in KnowledgeGraph
    },

    handleTabChange(tabId) {
      if (this.annotations.length > 0) {
        this.annotations = []
      }
      this.activeTab = tabId
      if (tabId === 'graph' && this.graphDirty) {
        this.graphDirty = false
        this.$nextTick(() => {
          if (this.$refs.knowledgeGraph) {
            this.$refs.knowledgeGraph.loadAndRender()
          }
        })
      }
      if (tabId === 'browser' && !this.browserInitialized) {
        this.browserInitialized = true
        this.browserLoading = true
        this.browserLoadError = false
        this.browserErrorMessage = ''
        this.scheduleBrowserLoadTimeout()
      }
    },

    async handleSelectSpace(spaceId) {
      // Stop typewriter to prevent orphaned timers
      this.stopTypewriter()

      // Cancel any ongoing SSE
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }

      // Clear quiz polling state
      this.clearQuizPollState()

      // Reset chat state
      this.messages = []
      this.conversationId = null
      this.nextId = 1
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []
      this.annotations = []
      this.inputText = ''
      this.resetChatInputHeight()
      this.cleanupPendingAttachments()
      this.showDeleteSpaceModal = false
      this.deleteTargetSpaceId = null
      this.deleteTargetSpaceName = ''

      this.spaceId = spaceId
      await this.loadSpaceInfo()
      this.loadSpaceToolMode()
      this.initConversation()
    },

    handleCreateSpace() {
      uni.navigateTo({ url: '/pages/createSpace/createSpace' })
    },

    resolveDeleteSpaceError(error) {
      const detail = error?.data?.detail
      if (typeof detail === 'string') return detail
      if (typeof detail?.message === 'string') return detail.message
      if (typeof error?.message === 'string') return error.message
      return '删除失败，请重试'
    },

    handleShareSpace() {
      if (!this.spaceId || this.isGeneratingShareCode) return
      this.showShareModeModal = true
    },

    async selectShareMode(mode) {
      this.showShareModeModal = false
      this.currentShareMode = mode
      this.isGeneratingShareCode = true
      try {
        const res = await generateShareCode(this.spaceId, mode)
        this.shareCode = res.code
        this.displayShareCode = res.display_code
        this.copyBtnText = '复制分享码'
        this.showShareCodeModal = true
      } catch (err) {
        const msg = err?.data?.detail || err?.message || '生成分享码失败'
        uni.showToast({ title: msg, icon: 'none' })
      } finally {
        this.isGeneratingShareCode = false
      }
    },

    async captureArtifactToCanvas(htmlContent) {
      // Strategy: inject html2canvas INTO the temp iframe so it runs in the
      // same document context as the artifact.  The iframe captures its own
      // body and sends the base64 result back via postMessage.
      return new Promise((resolve) => {
        const iframe = document.createElement('iframe')
        iframe.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px;height:600px;border:none;opacity:0;pointer-events:none'
        iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts')

        // Build capture helper (injected before </body>).
        // Avoid literal <script in source — SFC parser treats them as real blocks.
        const SO = '<' + 'script'
        const SC = '<' + '/script>'
        const captureHelper =
          SO + ' src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js">' + SC +
          SO + '>' +
          'window.addEventListener("message",function(e){' +
            'if(e.data&&e.data.type==="__ds_cap__"){' +
              'var fn=typeof html2canvas==="function"' +
                '?html2canvas(document.body,{useCORS:true,scale:1,logging:false})' +
                ':Promise.reject("no h2c");' +
              'fn.then(function(c){' +
                'parent.postMessage({type:"__ds_res__",d:c.toDataURL("image/png")},"*")' +
              '}).catch(function(){' +
                'parent.postMessage({type:"__ds_res__",d:null},"*")' +
              '})' +
            '}' +
          '})' + SC

        let html = htmlContent
        const idx = html.lastIndexOf('</body>')
        html = idx !== -1
          ? html.slice(0, idx) + captureHelper + html.slice(idx)
          : html + captureHelper

        iframe.srcdoc = html
        document.body.appendChild(iframe)

        const cleanup = () => {
          window.removeEventListener('message', onMsg)
          try { document.body.removeChild(iframe) } catch (_) {}
        }

        const timer = setTimeout(() => {
          console.warn('[DualSync] Artifact capture timed out')
          cleanup()
          resolve(null)
        }, 12000)

        function onMsg(e) {
          if (!e.data || e.data.type !== '__ds_res__') return
          clearTimeout(timer)
          if (!e.data.d) { cleanup(); resolve(null); return }
          const img = new Image()
          img.onload = () => {
            const c = document.createElement('canvas')
            c.width = img.width
            c.height = img.height
            c.getContext('2d').drawImage(img, 0, 0)
            cleanup()
            resolve(c)
          }
          img.onerror = () => { cleanup(); resolve(null) }
          img.src = e.data.d
        }
        window.addEventListener('message', onMsg)

        iframe.onload = () => {
          // Wait for artifact scripts to execute + html2canvas CDN to load
          setTimeout(() => {
            try { iframe.contentWindow.postMessage({ type: '__ds_cap__' }, '*') }
            catch (_) { clearTimeout(timer); cleanup(); resolve(null) }
          }, 1500)
        }
      })
    },

    async capturePanelScreenshot() {
      try {
        let canvas
        if (this.activeTab === 'graph' && this.$refs.knowledgeGraph) {
          // For graph tab, get the native canvas element directly
          canvas = this.$refs.knowledgeGraph._canvasEl
          if (!canvas) return null
        } else if (this.activeTab === 'notes') {
          // For notes tab, check if viewing an interactive HTML artifact
          const note = this.$refs.notesPanel?.selectedNote
          if (note?.note_type === 'interactive_html' && note.content && typeof html2canvas === 'function') {
            canvas = await this.captureArtifactToCanvas(note.content)
          }
          // Fallback to html2canvas on .tab-content-area if artifact capture failed or not an artifact
          if (!canvas) {
            const panelEl = document.querySelector('.tab-content-area')
            if (!panelEl || typeof html2canvas !== 'function') return null
            canvas = await html2canvas(panelEl, { useCORS: true, scale: 1, logging: false })
          }
        } else {
          // For other tabs, use html2canvas
          const panelEl = document.querySelector('.tab-content-area')
          if (!panelEl || typeof html2canvas !== 'function') return null
          canvas = await html2canvas(panelEl, {
            useCORS: true,
            scale: 1,
            logging: false
          })
        }

        if (!canvas) return null

        // Resize to max 800px wide
        const maxW = 800
        const srcW = canvas.width
        const srcH = canvas.height
        const scale = srcW > maxW ? maxW / srcW : 1
        const dstW = Math.round(srcW * scale)
        const dstH = Math.round(srcH * scale)

        const offscreen = document.createElement('canvas')
        offscreen.width = dstW
        offscreen.height = dstH
        const ctx = offscreen.getContext('2d')
        ctx.drawImage(canvas, 0, 0, dstW, dstH)

        // Draw percentage grid overlay
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)'
        ctx.lineWidth = 1
        ctx.font = '10px sans-serif'
        ctx.fillStyle = 'rgba(255, 255, 255, 0.5)'
        for (let pct = 20; pct <= 80; pct += 20) {
          const x = Math.round(dstW * pct / 100)
          const y = Math.round(dstH * pct / 100)
          ctx.beginPath()
          ctx.moveTo(x, 0)
          ctx.lineTo(x, dstH)
          ctx.stroke()
          ctx.beginPath()
          ctx.moveTo(0, y)
          ctx.lineTo(dstW, y)
          ctx.stroke()
          ctx.fillText(`${pct}%`, x + 2, 12)
          ctx.fillText(`${pct}%`, 2, y - 3)
        }

        return offscreen.toDataURL('image/jpeg', 0.7)
      } catch (err) {
        console.error('[DualSync] Screenshot failed:', err)
        return null
      }
    },

    handleCopyShareCode() {
      const code = this.displayShareCode || this.shareCode
      if (navigator?.clipboard?.writeText) {
        navigator.clipboard.writeText(code).then(() => {
          this.copyBtnText = '已复制!'
          setTimeout(() => { this.copyBtnText = '复制分享码' }, 2000)
        }).catch(() => {
          this._fallbackCopy(code)
        })
      } else {
        this._fallbackCopy(code)
      }
    },

    _fallbackCopy(text) {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      this.copyBtnText = '已复制!'
      setTimeout(() => { this.copyBtnText = '复制分享码' }, 2000)
    },

    handleDeleteSpace() {
      if (!this.spaceId || this.isDeletingSpace) return

      this.deleteTargetSpaceId = this.spaceId
      this.deleteTargetSpaceName = this.spaceName || '当前学习空间'
      this.showDeleteSpaceModal = true
    },

    async confirmDeleteSpace() {
      if (!this.deleteTargetSpaceId || this.isDeletingSpace) return

      const deletingSpaceId = this.deleteTargetSpaceId
      const deletingSpaceName = this.deleteTargetSpaceName || '当前学习空间'
      this.showDeleteSpaceModal = false

      this.isDeletingSpace = true
      uni.showLoading({ title: '删除中...', mask: true })

      try {
        await deleteSpace(deletingSpaceId)

        const spacesStore = useSpacesStore()
        await spacesStore.loadSpaces(true)
        const remainingSpaces = spacesStore.spaces || []
        const nextSpace = remainingSpaces[0] || null

        uni.hideLoading()
        uni.showToast({ title: `学习空间「${deletingSpaceName}」已删除`, icon: 'success' })

        if (nextSpace) {
          this.handleSelectSpace(nextSpace.id)
        } else {
          this.handleSelectSpace(null)
        }
      } catch (error) {
        console.error('[StudyPage] Failed to delete space:', error)
        uni.hideLoading()
        uni.showToast({ title: this.resolveDeleteSpaceError(error), icon: 'none' })
      } finally {
        this.isDeletingSpace = false
        this.deleteTargetSpaceId = null
        this.deleteTargetSpaceName = ''
      }
    },

    togglePathHighlight() {
      this.isPathHighlightOn = !this.isPathHighlightOn
    },

    async handleLearningPathAnimation(pathNodeNames) {
      // Switch to graph tab if needed
      if (this.activeTab !== 'graph') {
        this.activeTab = 'graph'
      }
      // Enable path highlight so static edges/rings show after animation
      this.isPathHighlightOn = true

      await this.$nextTick()

      if (this.$refs.knowledgeGraph) {
        this.$refs.knowledgeGraph.animateLearningPath(pathNodeNames)
      }
    },

    onNodeSelected(payload) {
      // Could be used to inject context into chat
    },

    onGraphLoaded({ nodeCount, edgeCount }) {
      // Graph loaded
    },

    onQuickLearn({ node }) {
      const spaceName = this.spaceName || '学习空间'
      this.inputText = `我要学习${spaceName}下的${node.label}知识点`
      this.$nextTick(() => this.handleSend())
    },

    scheduleGraphRefresh() {
      // Skip refresh if path animation is running (it already loaded fresh data)
      if (this.$refs.knowledgeGraph && this.$refs.knowledgeGraph.pathAnimationRunning) return

      if (this.activeTab === 'graph' && this.$refs.knowledgeGraph) {
        if (this._graphRefreshTimer) clearTimeout(this._graphRefreshTimer)
        this._graphRefreshTimer = setTimeout(() => {
          this._graphRefreshTimer = null
          if (this.$refs.knowledgeGraph) {
            this.$refs.knowledgeGraph.loadAndRender()
          }
        }, 800)
      } else {
        this.graphDirty = true
      }
    },

    clearBrowserLoadTimeout() {
      if (this.browserLoadTimeoutId) {
        clearTimeout(this.browserLoadTimeoutId)
        this.browserLoadTimeoutId = null
      }
    },

    scheduleBrowserLoadTimeout() {
      this.clearBrowserLoadTimeout()
      this.browserLoadTimeoutId = setTimeout(() => {
        if (!this.browserLoading) return
        this.browserLoading = false
        this.browserLoadError = true
        this.browserErrorMessage = '该网站可能禁止嵌入显示，请尝试在新窗口打开。'
      }, BROWSER_LOAD_TIMEOUT_MS)
    },

    normalizeBrowserUrl(raw) {
      const value = typeof raw === 'string' ? raw.trim() : String(raw || '').trim()
      if (!value) return ''

      let normalized = value
      const hasScheme = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(normalized)
      if (!hasScheme) {
        normalized = `https://${normalized}`
      }

      try {
        const parsed = new URL(normalized)
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
          return ''
        }
        return parsed.toString()
      } catch (error) {
        return ''
      }
    },

    navigateBrowser(target, pushHistory = true) {
      const normalized = this.normalizeBrowserUrl(target)
      if (!normalized) return false

      this.browserCurrentUrl = normalized
      this.browserInputUrl = normalized
      this.browserLoading = true
      this.browserLoadError = false
      this.browserErrorMessage = ''
      this.browserFrameKey = this.browserFrameKey + 1

      if (pushHistory) {
        if (this.browserHistoryIndex < this.browserHistory.length - 1) {
          this.browserHistory = this.browserHistory.slice(0, this.browserHistoryIndex + 1)
        }

        const lastUrl = this.browserHistory[this.browserHistory.length - 1]
        if (lastUrl !== normalized) {
          this.browserHistory = [...this.browserHistory, normalized]
        }
        this.browserHistoryIndex = this.browserHistory.length - 1
      }

      this.scheduleBrowserLoadTimeout()
      return true
    },

    handleBrowserGo() {
      const ok = this.navigateBrowser(this.browserInputUrl, true)
      if (!ok) {
        uni.showToast({ title: '请输入有效的网址', icon: 'none' })
      }
    },

    handleBrowserBack() {
      if (!this.canBrowserBack) return

      const nextIndex = this.browserHistoryIndex - 1
      this.browserHistoryIndex = nextIndex
      this.navigateBrowser(this.browserHistory[nextIndex], false)
    },

    handleBrowserForward() {
      if (!this.canBrowserForward) return

      const nextIndex = this.browserHistoryIndex + 1
      this.browserHistoryIndex = nextIndex
      this.navigateBrowser(this.browserHistory[nextIndex], false)
    },

    handleBrowserRefresh() {
      if (!this.browserCurrentUrl) return
      this.browserLoading = true
      this.browserLoadError = false
      this.browserErrorMessage = ''
      this.browserFrameKey = this.browserFrameKey + 1
      this.scheduleBrowserLoadTimeout()
    },

    onBrowserFrameLoad() {
      this.browserLoading = false
      this.browserLoadError = false
      this.browserErrorMessage = ''
      this.clearBrowserLoadTimeout()
    },

    openBrowserInNewTab() {
      if (!this.browserCurrentUrl) return
      window.open(this.browserCurrentUrl, '_blank', 'noopener,noreferrer')
    },

    // ==================== Chat Methods ====================

    getSpaceWelcomeMessage() {
      const spaceTitle = this.spaceName || '学习空间'
      return `你好！我是你的${spaceTitle}学习助手，这些是我能帮你做的事：

📖 **知识问答** — 随时提问，我会优先从你的学习资料中查找答案
🧠 **知识图谱** — 帮你梳理知识结构，追踪每个知识点的掌握程度
🗺️ **学习路径** — 根据你的掌握情况，规划个性化的学习顺序
📝 **练习测试** — 生成选择题、判断题、简答题，检验学习效果
🔍 **联网搜索** — 查找最新资料和权威来源，补充学习内容
📅 **学习日程** — 管理你的学习计划和时间安排
💾 **学习记忆** — 记住你的学习偏好和进度，跨对话持续服务

上传学习资料（PDF、Word等）后，我还能直接从你的资料中查找答案。有什么想学的，直接问我就好！`
    },

    async initConversation() {
      // Always start with a fresh conversation
      // New conversation will be created lazily on first message send
      this.conversationId = null
      this.messages = []
      this.nextId = 1
      if (!this.spaceId) return
      this.messages.push({
        id: this.nextId++,
        role: 'ai',
        content: this.getSpaceWelcomeMessage()
      })
    },

    async loadConversationHistory() {
      if (!this.conversationId) return

      this.isLoadingHistory = true
      try {
        const result = await getConversation(this.conversationId)
        const rawMessages = result.messages || []
        this.messages = rawMessages.map((m, i) => {
          const msg = {
            id: i + 1,
            role: m.role === 'user' ? 'user' : 'ai',
            content: m.content,
            isFailed: false,
            attachments: m.attachments || [],
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
          return msg
        })
        this.nextId = this.messages.length + 1

        // Fix artifact tool calls loaded from history: if the tool call succeeded
        // but result.status is still 'generating', it means generation completed
        // after the original SSE response — mark as 'done' so the card shows success
        for (const msg of this.messages) {
          if (!msg.segments) continue
          for (const seg of msg.segments) {
            if (seg.type === 'tool' && seg.toolCall &&
                (seg.toolCall.tool === 'create_artifact' || seg.toolCall.tool === 'update_artifact') &&
                seg.toolCall.status === 'done' && seg.toolCall.success &&
                seg.toolCall.result?.status === 'generating') {
              seg.toolCall = { ...seg.toolCall, result: { ...seg.toolCall.result, status: 'done' } }
            }
          }
        }

        this.$nextTick(() => this.scrollToBottom())
      } catch (err) {
        console.error('[StudyPage] Failed to load history:', err)
      } finally {
        this.isLoadingHistory = false
      }
    },

    async handleSend() {
      const text = this.inputText.trim()
      if (!text || !this.spaceId || this.isSending) return

      if (this.pendingAttachments.some(a => a.uploading)) {
        uni.showToast({ title: '附件上传中，请稍候', icon: 'none' })
        return
      }

      this.isSending = true
      this.isAutoScrollEnabled = true
      this.inputText = ''
      this.resetChatInputHeight()

      // Collect attachment IDs and clear pending
      const attachmentIds = this.pendingAttachments
        .filter(a => a.id && !String(a.id).startsWith('temp_'))
        .map(a => a.id)
      const sentAttachments = [...this.pendingAttachments]
      this.pendingAttachments = []
      sentAttachments.forEach(a => { if (a.localPreview) URL.revokeObjectURL(a.localPreview) })

      // Add user message BEFORE conversation creation so it's visible even on failure
      const userMsgId = this.nextId++
      this.messages.push({
        id: userMsgId,
        role: 'user',
        content: text,
        isFailed: false,
        attachments: sentAttachments.map(a => ({
          id: a.id,
          attachment_type: a.type,
          file_url: a.file_url,
          thumbnail_url: a.thumbnail_url,
          original_filename: a.original_filename
        }))
      })

      this.$nextTick(() => this.scrollToBottom())

      // Create conversation if needed
      if (!this.conversationId) {
        try {
          const conv = await createConversation(this.spaceId, text.slice(0, 50))
          this.conversationId = conv.id
        } catch (err) {
          this.isSending = false
          const userMsg = this.messages.find(m => m.id === userMsgId)
          if (userMsg) userMsg.isFailed = true
          uni.showToast({ title: 'Failed to create conversation', icon: 'none' })
          return
        }
      }

      // Add AI placeholder (declare all properties upfront for reactivity)
      const aiMsgId = this.nextId++
      this.messages.push({
        id: aiMsgId,
        role: 'ai',
        content: '',
        isStreaming: true,
        isWaitingOutput: true,
        isError: false,
        segments: null,
        streamSegments: null,
        toolCalls: null,
        thinkingContent: '',
        isThinking: false,
        thinkingDuration: 0
      })

      this.$nextTick(() => this.scrollToBottom())
      this.isStreaming = true
      this.activeToolCalls = []

      const callbacks = this._buildSSECallbacks(aiMsgId, userMsgId)
      let panelScreenshot = null
      if (this.dualSyncEnabled) {
        panelScreenshot = await this.capturePanelScreenshot()
      }
      this.cancelSSE = sendMessage(this.conversationId, text, callbacks, attachmentIds.length > 0 ? attachmentIds : null, this.selectedModelId, panelScreenshot)
    },

    _buildSSECallbacks(aiMsgId, userMsgId) {
      let finalized = false
      return {
        onThinkingDelta: (content) => {
          const msg = this.messages.find(m => m.id === aiMsgId)
          if (!msg) return
          if (!msg.isThinking) {
            msg.isThinking = true
            msg.isWaitingOutput = false
            this.thinkingStartTime = Date.now()
            this.thinkingExpanded = { ...this.thinkingExpanded, [aiMsgId]: true }
          }
          this.appendThinkingText(aiMsgId, content)
        },

        onTextDelta: (content) => {
          const msg = this.messages.find(m => m.id === aiMsgId)
          if (msg && msg.isThinking) {
            this.flushThinkingBuffer()
            msg.isThinking = false
            msg.thinkingDuration = this.thinkingStartTime
              ? Math.round((Date.now() - this.thinkingStartTime) / 1000)
              : 0
            this.thinkingStartTime = null
            this.thinkingExpanded = { ...this.thinkingExpanded, [aiMsgId]: false }
          }
          this.appendToTypewriter(aiMsgId, content)
        },

        onToolCall: (data) => {
          this.handleToolCallEvent(aiMsgId, data)
        },

        onClientToolRequest: (data) => {
          this.handleClientToolRequest(aiMsgId, data)
        },

        onDone: (fullContent) => {
          if (finalized) return
          finalized = true
          this.flushThinkingBuffer()
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            if (aiMsg.isThinking) {
              aiMsg.isThinking = false
              aiMsg.thinkingDuration = this.thinkingStartTime
                ? Math.round((Date.now() - this.thinkingStartTime) / 1000)
                : 0
              this.thinkingStartTime = null
            }
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
            aiMsg.streamSegments = null
            if (this.activeToolCalls.length > 0) {
              aiMsg.toolCalls = this.activeToolCalls.map(tc => ({ ...tc }))
            }
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
          }
          this.cancelSSE = null
          this.isStreaming = false
          this.isSending = false
          this.activeToolCalls = []
          this.$nextTick(() => this.scrollToBottom())
        },

        onQuotaError: (info) => {
          if (finalized) return
          finalized = true
          this.flushThinkingBuffer()
          this.flushTypewriter()
          uni.showToast({ title: info.message || '配额已达上限', icon: 'none', duration: 3000 })
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            aiMsg.content = info.message || '配额已达上限'
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
            aiMsg.isError = true
          }
          this.cancelSSE = null
          this.isStreaming = false
          this.isSending = false
          this.activeToolCalls = []
        },

        onError: (message) => {
          if (finalized) return
          finalized = true
          this.flushThinkingBuffer()
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            aiMsg.content = aiMsg.content || 'Request failed'
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
            aiMsg.isError = true
          }
          const userMsg = this.messages.find(m => m.id === userMsgId)
          if (userMsg) userMsg.isFailed = true
          this.cancelSSE = null
          this.isStreaming = false
          this.isSending = false
          this.activeToolCalls = []
          uni.showToast({ title: message || 'Request failed', icon: 'none' })
        },

        onComplete: () => {
          if (finalized) return
          finalized = true
          this.flushThinkingBuffer()
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg && aiMsg.isStreaming) {
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
            this.activeToolCalls = []
            if (!aiMsg.content || aiMsg.content.trim() === '') {
              aiMsg.content = 'Connection interrupted. Please resend your message.'
            }
            const userMsg = this.messages.find(m => m.id === userMsgId)
            if (userMsg) userMsg.isFailed = true
          }
          this.cancelSSE = null
          this.isSending = false
          this.isStreaming = false
        }
      }
    },

    async resendMessage(msg) {
      if (this.isStreaming || this.isSending) return

      this.isSending = true
      this.isAutoScrollEnabled = true
      msg.isFailed = false

      // Remove the failed AI response that follows this message
      const msgIdx = this.messages.findIndex(m => m.id === msg.id)
      if (msgIdx >= 0 && msgIdx + 1 < this.messages.length) {
        const nextMsg = this.messages[msgIdx + 1]
        if (nextMsg.role === 'ai' && !nextMsg.isStreaming) {
          this.messages.splice(msgIdx + 1, 1)
        }
      }

      const text = msg.content
      const attachmentIds = (msg.attachments && msg.attachments.length > 0)
        ? msg.attachments.map(att => att.id).filter(Boolean)
        : []

      // Create conversation if needed
      if (!this.conversationId) {
        try {
          const conv = await createConversation(this.spaceId, text.slice(0, 50))
          this.conversationId = conv.id
        } catch {
          msg.isFailed = true
          this.isSending = false
          uni.showToast({ title: 'Failed to create conversation', icon: 'none' })
          return
        }
      }

      this.isStreaming = true

      // Add new AI placeholder
      const aiMsgId = this.nextId++
      this.messages.push({
        id: aiMsgId,
        role: 'ai',
        content: '',
        isStreaming: true,
        isWaitingOutput: true,
        isError: false,
        segments: null,
        streamSegments: null,
        toolCalls: null,
        thinkingContent: '',
        isThinking: false,
        thinkingDuration: 0
      })

      this.$nextTick(() => this.scrollToBottom())
      this.activeToolCalls = []

      const callbacks = this._buildSSECallbacks(aiMsgId, msg.id)
      let panelScreenshot = null
      if (this.dualSyncEnabled) {
        panelScreenshot = await this.capturePanelScreenshot()
      }
      this.cancelSSE = sendMessage(this.conversationId, text, callbacks, attachmentIds.length > 0 ? attachmentIds : null, this.selectedModelId, panelScreenshot)
    },

    handleToolCallEvent(aiMsgId, data) {
      const msg = this.messages.find(m => m.id === aiMsgId)
      if (!msg) return

      const { id, tool, status, success, result, arguments: args } = data

      if (status === 'running' || !status) {
        if (msg.isWaitingOutput) {
          msg.isWaitingOutput = false
        }

        const existing = this.activeToolCalls.find(tc => tc.id === id)
        if (existing) return

        // Flush typewriter buffer before saving current content to streamSegments
        this.flushThinkingBuffer()
        this.flushTypewriter()

        if (!msg.streamSegments || msg.streamSegments === null) {
          msg.streamSegments = []
        }

        if (msg.content && msg.content.length > 0) {
          msg.streamSegments.push({ type: 'text', content: msg.content })
          msg.content = ''
        }

        const toolCall = { id, tool, arguments: args, status: 'running', quizId: null }

        if (MEMORY_TOOLS.has(tool)) {
          this.memoryToolStartTimes[id] = Date.now()
        }
        if (PLANNING_TOOLS.has(tool)) {
          this.planningToolStartTimes[id] = Date.now()
        }

        msg.streamSegments.push({ type: 'tool', toolCall })
        this.activeToolCalls.push(toolCall)

      } else if (status === 'done') {
        msg.isWaitingOutput = true

        const toolCall = this.activeToolCalls.find(tc => tc.id === id)
        if (toolCall) {
          toolCall.status = 'done'
          toolCall.success = success
          toolCall.result = result
          if (args) toolCall.arguments = args

          if (MEMORY_TOOLS.has(tool)) {
            const startTime = this.memoryToolStartTimes[id]
            const elapsed = startTime ? Date.now() - startTime : 1000
            const minDisplayTime = 1000

            if (elapsed < minDisplayTime) {
              this.memoryToolDelayedDone = { ...this.memoryToolDelayedDone, [id]: true }
              setTimeout(() => {
                const { [id]: _d, ...restDelayed } = this.memoryToolDelayedDone
                this.memoryToolDelayedDone = restDelayed
                const { [id]: _s, ...restStarts } = this.memoryToolStartTimes
                this.memoryToolStartTimes = restStarts
              }, minDisplayTime - elapsed)
            } else {
              const { [id]: _, ...restStarts } = this.memoryToolStartTimes
              this.memoryToolStartTimes = restStarts
            }
          }

          if (PLANNING_TOOLS.has(tool)) {
            const startTime = this.planningToolStartTimes[id]
            const elapsed = startTime ? Date.now() - startTime : 2000
            const minDisplayTime = 2000

            if (elapsed < minDisplayTime) {
              this.planningToolDelayedDone = { ...this.planningToolDelayedDone, [id]: true }
              setTimeout(() => {
                const { [id]: _d, ...restDelayed } = this.planningToolDelayedDone
                this.planningToolDelayedDone = restDelayed
                const { [id]: _s, ...restStarts } = this.planningToolStartTimes
                this.planningToolStartTimes = restStarts
              }, minDisplayTime - elapsed)
            } else {
              const { [id]: _, ...restStarts } = this.planningToolStartTimes
              this.planningToolStartTimes = restStarts
            }
          }
        }

        if (success && GRAPH_MUTATING_TOOLS.has(tool)) {
          if ((tool === 'generate_learning_path' || tool === 'extend_learning_path') && result?.path?.length > 0) {
            this.handleLearningPathAnimation(result.path)
          } else {
            this.scheduleGraphRefresh()
          }
        }

        if (tool === 'generate_test' && success && result?.task_id) {
          this.handleGenerateTestCompletion(aiMsgId, result.task_id, id)
        }

        // Handle annotation tool results
        if (tool === 'annotate_panel' && success && result?.annotations) {
          this.annotations = result.annotations.map((a, i) => ({
            ...a, id: `ann-${Date.now()}-${i}`
          }))
        }

        if (msg.streamSegments) {
          const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === id)
          if (seg && toolCall) {
            seg.toolCall = { ...toolCall }
          }
        }
      }

      this.$forceUpdate()
      if (this.isAutoScrollEnabled) {
        this.$nextTick(() => this.scrollToBottom())
      }
    },

    handleClientToolRequest(aiMsgId, data) {
      const msg = this.messages.find(m => m.id === aiMsgId)
      if (!msg) return

      const { tool_call_id, tool, params } = data

      // Find existing entry (created by tool_call running event)
      const existing = this.activeToolCalls.find(tc => tc.id === tool_call_id)
      if (existing) {
        existing.status = 'pending_confirmation'
        existing.arguments = params

        if (msg.streamSegments) {
          const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === tool_call_id)
          if (seg) {
            seg.toolCall = { ...existing }
          }
        }
      } else {
        if (msg.isWaitingOutput) msg.isWaitingOutput = false
        this.flushThinkingBuffer()
        this.flushTypewriter()

        if (!msg.streamSegments) msg.streamSegments = []
        if (msg.content && msg.content.length > 0) {
          msg.streamSegments.push({ type: 'text', content: msg.content })
          msg.content = ''
        }

        const toolCall = {
          id: tool_call_id,
          tool,
          arguments: params,
          status: 'pending_confirmation',
          quizId: null
        }
        msg.streamSegments.push({ type: 'tool', toolCall })
        this.activeToolCalls.push(toolCall)
      }

      // Auto-execute schedule tools via backend API (web has no system calendar)
      if (SCHEDULE_TOOLS.has(tool)) {
        this.executeScheduleToolViaBackend(aiMsgId, tool_call_id, tool, params)
      }

      this.$forceUpdate()
      if (this.isAutoScrollEnabled) {
        this.$nextTick(() => this.scrollToBottom())
      }
    },

    async executeScheduleToolViaBackend(aiMsgId, toolCallId, tool, params) {
      const updateToolCallStatus = (status, success, result) => {
        const tc = this.activeToolCalls.find(t => t.id === toolCallId)
        if (tc) {
          tc.status = status
          if (success !== undefined) tc.success = success
          if (result !== undefined) tc.result = result
        }
        const msg = this.messages.find(m => m.id === aiMsgId)
        if (msg?.streamSegments) {
          const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall?.id === toolCallId)
          if (seg) seg.toolCall = { ...seg.toolCall, status, ...(success !== undefined ? { success } : {}), ...(result !== undefined ? { result } : {}) }
        }
        this.$forceUpdate()
      }

      updateToolCallStatus('running')

      try {
        let resultText = ''

        if (tool === 'get_schedule') {
          const startDate = params.start_date || new Date().toISOString().split('T')[0]
          const endDate = params.end_date || new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
          const events = await getCalendarEvents(startDate + 'T00:00:00', endDate + 'T23:59:59')
          if (!events || events.length === 0) {
            resultText = '该时间范围内没有日程安排。'
          } else {
            resultText = events.map(e => {
              const start = new Date(e.start_time).toLocaleString('zh-CN')
              const end = new Date(e.end_time).toLocaleString('zh-CN')
              return `- ${e.title}: ${start} ~ ${end}${e.details ? ' (' + e.details + ')' : ''}`
            }).join('\n')
          }
        } else if (tool === 'add_schedule') {
          const event = await createCalendarEvent({
            title: params.title,
            start_time: params.start_time || params.begin_time,
            end_time: params.end_time,
            details: params.description || params.details || null,
            source_conversation_id: this.conversationId || null
          })
          resultText = `日程已添加：${event.title}`
        } else if (tool === 'delete_schedule') {
          const eventId = params.event_id || params.id
          if (eventId) {
            await deleteCalendarEvent(eventId)
            resultText = '日程已删除。'
          } else {
            resultText = '未提供要删除的日程 ID。'
          }
        } else if (tool === 'update_schedule') {
          const eventId = params.event_id || params.id
          if (eventId) {
            const updateData = {}
            if (params.title) updateData.title = params.title
            if (params.start_time || params.begin_time) updateData.start_time = params.start_time || params.begin_time
            if (params.end_time) updateData.end_time = params.end_time
            if (params.description || params.details) updateData.details = params.description || params.details
            const event = await updateCalendarEvent(eventId, updateData)
            resultText = `日程已更新：${event.title}`
          } else {
            resultText = '未提供要更新的日程 ID。'
          }
        }

        updateToolCallStatus('done', true, { text: resultText })

        if (this.conversationId) {
          submitToolResult(this.conversationId, {
            tool_call_id: toolCallId,
            result: resultText,
            success: true
          }).catch(() => {})
        }
      } catch (err) {
        const errMsg = err.message || '日程操作失败'
        updateToolCallStatus('done', false, { text: errMsg })

        if (this.conversationId) {
          submitToolResult(this.conversationId, {
            tool_call_id: toolCallId,
            result: errMsg,
            success: false
          }).catch(() => {})
        }
      }

      if (this.isAutoScrollEnabled) {
        this.$nextTick(() => this.scrollToBottom())
      }
    },

    async handleGenerateTestCompletion(aiMsgId, taskId, toolCallId) {
      if (this.isGeneratingQuiz) return
      this.isGeneratingQuiz = true

      const maxAttempts = 150 // 150 * 2s = 5 min max
      const pollInterval = 2000
      let attempts = 0
      let consecutiveErrors = 0

      try {
        while (attempts < maxAttempts) {
          if (!this.isGeneratingQuiz) return

          try {
            const result = await getTaskStatus(taskId)
            consecutiveErrors = 0

            if (result.status === 'done' && result.quiz_id) {
              this.activeQuizId = result.quiz_id
              this.updateToolCallWithQuizId(aiMsgId, result.quiz_id, toolCallId)
              return
            }

            if (result.status === 'failed') {
              this.appendErrorToMessage(aiMsgId, `测试生成失败：${result.error_message || '未知错误'}`)
              return
            }
          } catch (error) {
            if (error.statusCode === 401 || error.statusCode === 403) {
              this.appendErrorToMessage(aiMsgId, '认证失败，请重新登录')
              return
            }
            consecutiveErrors++
            if (consecutiveErrors >= 3) {
              this.appendErrorToMessage(aiMsgId, `轮询失败：${error.message || '网络错误'}`)
              return
            }
          }

          await new Promise(resolve => {
            this.quizPollTimer = setTimeout(resolve, pollInterval)
          })
          attempts++
        }

        this.appendErrorToMessage(aiMsgId, '测试生成超时，请稍后在测试题标签页查看')
      } finally {
        this.isGeneratingQuiz = false
        this.quizPollTimer = null
      }
    },

    updateToolCallWithQuizId(aiMsgId, quizId, toolCallId) {
      const msg = this.messages.find(m => m.id === aiMsgId)
      if (!msg) return

      const updateSegments = (segments) => {
        if (!Array.isArray(segments)) return
        const seg = segments.find(s => s.type === 'tool' && s.toolCall?.id === toolCallId)
        if (seg) {
          seg.toolCall = { ...seg.toolCall, quizId }
        }
      }

      updateSegments(msg.segments)
      updateSegments(msg.streamSegments)
      this.$forceUpdate()

      if (this.isAutoScrollEnabled) {
        this.$nextTick(() => this.scrollToBottom())
      }
    },

    appendErrorToMessage(aiMsgId, errorMsg) {
      const msg = this.messages.find(m => m.id === aiMsgId)
      if (!msg) return

      const segments = msg.segments || msg.streamSegments
      if (Array.isArray(segments)) {
        const lastText = [...segments].reverse().find(s => s.type === 'text')
        if (lastText) {
          lastText.content = (lastText.content || '') + `\n\n${errorMsg}`
        } else {
          segments.push({ type: 'text', content: `\n\n${errorMsg}` })
        }
      } else if (msg.content !== undefined) {
        msg.content = (msg.content || '') + `\n\n${errorMsg}`
      } else {
        msg.content = errorMsg
      }
      this.$forceUpdate()
    },

    handleQuizEntryClick(quizId) {
      this.activeTab = 'quizzes'
      this.$nextTick(() => {
        if (this.$refs.quizPanel) {
          this.$refs.quizPanel.loadQuizzes()
        }
      })
    },

    clearQuizPollState() {
      if (this.quizPollTimer) {
        clearTimeout(this.quizPollTimer)
        this.quizPollTimer = null
      }
      this.isGeneratingQuiz = false
      this.activeQuizId = null
    },

    toggleThinking(msgId) {
      this.thinkingExpanded = { ...this.thinkingExpanded, [msgId]: !this.thinkingExpanded[msgId] }
    },

    isThinkingExpanded(msgId) {
      return !!this.thinkingExpanded[msgId]
    },

    getMessageSegments(msg) {
      if (msg.isStreaming) {
        return this.buildStreamingSegments(msg)
      }
      if (Array.isArray(msg.segments) && msg.segments.length > 0) {
        return msg.segments
      }
      if (msg.content) {
        return [{ type: 'text', content: msg.content }]
      }
      return []
    },

    buildStreamingSegments(msg) {
      const segments = []

      if (Array.isArray(msg.streamSegments) && msg.streamSegments.length > 0) {
        for (const seg of msg.streamSegments) {
          if (seg.type === 'tool') {
            const tc = this.activeToolCalls.find(t => t.id === seg.toolCall.id)
            segments.push({ type: 'tool', toolCall: tc ? { ...tc } : { ...seg.toolCall } })
          } else {
            segments.push({ ...seg })
          }
        }
      }

      if (msg.content && msg.content.length > 0) {
        segments.push({ type: 'text', content: msg.content })
      }

      return segments
    },

    getToolDisplayName(toolName) {
      return TOOL_DISPLAY_NAMES[toolName] || toolName
    },

    getToolIconSvg(toolName) {
      const category = TOOL_ICON_MAP[toolName] || 'default'
      return TOOL_ICON_SVGS[category] || TOOL_ICON_SVGS.default
    },

    getToolCardClass(toolCall) {
      if (toolCall.status === 'running') return 'tool-call-running'
      if (toolCall.status === 'done' && toolCall.success) return 'tool-call-success'
      if (toolCall.status === 'done' && !toolCall.success) return 'tool-call-failed'
      return 'tool-call-running'
    },

    getFullImageUrl(relativePath) {
      if (!relativePath) return ''
      if (relativePath.startsWith('http')) return relativePath
      return config.API_BASE_URL + relativePath
    },

    previewChartImage(imageUrl) {
      const fullUrl = this.getFullImageUrl(imageUrl)
      window.open(fullUrl, '_blank')
    },

    isMemoryTool(toolName) {
      return MEMORY_TOOLS.has(toolName)
    },

    isPlanningTool(toolName) {
      return PLANNING_TOOLS.has(toolName)
    },

    isSearchTool(toolName) {
      return ['web_search', 'academic_search', 'encyclopedia_search', 'course_search'].includes(toolName)
    },

    getVisibleSearchResults(toolCall) {
      const results = toolCall.result?.results || []
      if (this.expandedSearchResults[toolCall.id]) return results
      return results.slice(0, 5)
    },

    getFaviconUrl(url) {
      try { return new URL(url).origin + '/favicon.ico' }
      catch { return '' }
    },

    isSearchExpanded(toolCallId) {
      return !!this.expandedSearchResults[toolCallId]
    },

    toggleSearchResults(toolCallId) {
      this.expandedSearchResults = {
        ...this.expandedSearchResults,
        [toolCallId]: !this.expandedSearchResults[toolCallId]
      }
    },

    isCodeExpanded(toolCallId) {
      return !!this.expandedCodeBlocks[toolCallId]
    },

    toggleCodeExpand(toolCallId) {
      this.expandedCodeBlocks = {
        ...this.expandedCodeBlocks,
        [toolCallId]: !this.expandedCodeBlocks[toolCallId]
      }
    },

    openSearchResultUrl(url) {
      if (!url) return
      window.open(url, '_blank')
    },

    getSourceLabel(source) {
      return { academic: '学术', encyclopedia: '百科', course: 'B站', web: '网页' }[source] || source
    },

    formatDisplayUrl(url) {
      try { return new URL(url).hostname } catch { return url }
    },

    getMemoryToolText(toolName) {
      return MEMORY_TOOL_TEXT[toolName] || 'Accessing memory...'
    },

    getMemoryToolDisplayStatus(toolCall) {
      if (!toolCall) return 'running'
      if (this.memoryToolDelayedDone[toolCall.id]) return 'running'
      return toolCall.status
    },

    getPlanningToolDisplayStatus(toolCall) {
      if (!toolCall) return 'running'
      if (this.planningToolDelayedDone[toolCall.id]) return 'running'
      return toolCall.status
    },

    formatToolArgs(args) {
      if (!args) return ''
      const entries = Object.entries(args)
      if (entries.length === 0) return ''
      return entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')
    },

    // ==================== Typewriter Methods ====================

    appendToTypewriter(msgId, text) {
      const msg = this.messages.find(m => m.id === msgId)
      if (msg && msg.isWaitingOutput) {
        msg.isWaitingOutput = false
      }

      if (this.typewriterMsgId !== msgId) {
        this.stopTypewriter()
        this.typewriterMsgId = msgId
        this.typewriterBuffer = ''
      }

      this.typewriterBuffer += text

      if (!this.typewriterTimer) {
        this.startTypewriter()
      }
    },

    startTypewriter() {
      if (this.typewriterTimer) return

      this.typewriterTimer = setInterval(() => {
        if (this.typewriterBuffer.length === 0) {
          this.pauseTypewriter()
          return
        }

        const char = this.typewriterBuffer.charAt(0)
        this.typewriterBuffer = this.typewriterBuffer.slice(1)

        const msg = this.messages.find(m => m.id === this.typewriterMsgId)
        if (msg) {
          msg.content = msg.content + char
          if (this.isAutoScrollEnabled) {
            this.$nextTick(() => this.scrollToBottom())
          }
        }
      }, this.typewriterSpeed)
    },

    pauseTypewriter() {
      if (this.typewriterTimer) {
        clearInterval(this.typewriterTimer)
        this.typewriterTimer = null
      }
    },

    stopTypewriter() {
      this.pauseTypewriter()
      this.typewriterBuffer = ''
      this.typewriterMsgId = null
    },

    flushTypewriter() {
      if (this.typewriterBuffer.length > 0 && this.typewriterMsgId) {
        const msg = this.messages.find(m => m.id === this.typewriterMsgId)
        if (msg) {
          msg.content = msg.content + this.typewriterBuffer
        }
      }
      this.stopTypewriter()
    },

    // ==================== Thinking Typewriter ====================

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
          if (this.isAutoScrollEnabled) {
            this.$nextTick(() => this.scrollToBottom())
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

    scrollToBottom() {
      this.scrollTopValue = this.scrollTopValue === 99999 ? 99998 : 99999
    },

    onChatScroll(e) {
      const { scrollTop, scrollHeight, clientHeight } = e.detail || {}
      if (scrollHeight && clientHeight) {
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight
        this.isAutoScrollEnabled = distanceFromBottom < 80
      }
    },

    handleStop() {
      // Flush any buffered typewriter text before finalizing
      this.flushThinkingBuffer()
      this.flushTypewriter()

      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false

      // Finalize any streaming message and mark user message for retry
      const streamingMsg = this.messages.find(m => m.isStreaming)
      if (streamingMsg) {
        streamingMsg.isStreaming = false
        streamingMsg.isWaitingOutput = false
        if (!streamingMsg.content || streamingMsg.content.trim() === '') {
          streamingMsg.content = 'Response stopped by user.'
        }
      }
    },

    // ==================== Conversation History ====================

    openHistoryPopup() {
      if (!this.spaceId) return
      this.showHistoryPopup = true
      this.loadConversations()
    },

    async loadConversations() {
      this.isLoadingConversations = true
      try {
        const result = await getSpaceConversations(this.spaceId)
        this.historyConversations = result.conversations || result || []
      } catch (err) {
        this.historyConversations = []
        uni.showToast({ title: 'Failed to load history', icon: 'none' })
      } finally {
        this.isLoadingConversations = false
      }
    },

    selectConversation(conv) {
      if (conv.id === this.conversationId) {
        this.showHistoryPopup = false
        return
      }

      // Cancel any active streaming
      this.flushThinkingBuffer()
      this.flushTypewriter()
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []
      this.annotations = []

      // Switch to selected conversation
      this.conversationId = conv.id
      this.messages = []
      this.nextId = 1
      this.showHistoryPopup = false
      this.loadConversationHistory()
    },

    handleNewConversation() {
      if (!this.spaceId) return

      // Cancel any active streaming
      this.flushThinkingBuffer()
      this.flushTypewriter()
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []
      this.annotations = []
      this.cleanupPendingAttachments()

      // Reset to fresh state — next handleSend will create a new conversation
      this.messages = []
      this.conversationId = null
      this.nextId = 1
      this.inputText = ''
      this.resetChatInputHeight()
      this.initConversation()
    },

    formatConvDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      if (isNaN(date.getTime())) return ''

      const now = new Date()
      const isToday = date.getFullYear() === now.getFullYear()
        && date.getMonth() === now.getMonth()
        && date.getDate() === now.getDate()

      if (isToday) {
        const hh = String(date.getHours()).padStart(2, '0')
        const mm = String(date.getMinutes()).padStart(2, '0')
        return `${hh}:${mm}`
      }

      const isSameYear = date.getFullYear() === now.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')

      if (isSameYear) {
        return `${month}/${day}`
      }
      return `${date.getFullYear()}/${month}/${day}`
    },

    // ==================== Attachment Methods ====================

    toggleAttachMenu() {
      if (!this.spaceId || this.isSending) return
      this.showAttachMenu = !this.showAttachMenu
    },

    pickImage() {
      this.showAttachMenu = false
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = 'image/jpeg,image/png,image/webp,image/gif'
      input.multiple = true
      input.onchange = (e) => this.handleFileSelected(e, 'image')
      input.click()
    },

    pickFile() {
      this.showAttachMenu = false
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt'
      input.multiple = true
      input.onchange = (e) => this.handleFileSelected(e, 'file')
      input.click()
    },

    async handleFileSelected(event, type) {
      const files = Array.from(event.target.files || [])
      event.target.value = ''

      const remaining = 9 - this.pendingAttachments.length
      if (remaining <= 0) {
        uni.showToast({ title: '最多添加9个附件', icon: 'none' })
        return
      }
      const filesToUpload = files.slice(0, remaining)

      for (const file of filesToUpload) {
        if (file.size > 10 * 1024 * 1024) {
          uni.showToast({ title: `${file.name} 超过10MB限制`, icon: 'none' })
          continue
        }

        const localPreview = type === 'image' ? URL.createObjectURL(file) : null
        const tempId = 'temp_' + Date.now() + '_' + Math.random()
        const tempItem = {
          id: tempId, type, original_filename: file.name,
          file_size: file.size, localPreview, uploading: true
        }
        this.pendingAttachments = [...this.pendingAttachments, tempItem]

        try {
          const result = await uploadAttachment(file)
          const att = result.attachment
          this.pendingAttachments = this.pendingAttachments.map(a =>
            a.id === tempId
              ? { ...att, type: att.attachment_type, localPreview, uploading: false }
              : a
          )
        } catch (err) {
          this.pendingAttachments = this.pendingAttachments.filter(a => a.id !== tempId)
          if (localPreview) URL.revokeObjectURL(localPreview)
          uni.showToast({ title: err.message || '上传失败', icon: 'none' })
        }
      }
    },

    handlePaste(event) {
      const items = event.clipboardData?.items
      if (!items) return

      const imageItems = Array.from(items).filter(item => item.type.startsWith('image/'))
      if (imageItems.length === 0) return

      event.preventDefault()
      for (const item of imageItems) {
        const file = item.getAsFile()
        if (file) {
          this.handleFileSelected({ target: { files: [file] } }, 'image')
        }
      }
    },

    removeAttachment(index) {
      const att = this.pendingAttachments[index]
      if (att.localPreview) URL.revokeObjectURL(att.localPreview)
      if (att.id && !String(att.id).startsWith('temp_')) {
        deleteAttachment(att.id).catch(() => {})
      }
      this.pendingAttachments = this.pendingAttachments.filter((_, i) => i !== index)
    },

    previewImage(url) {
      uni.previewImage({ urls: [url], current: url })
    },

    openFileUrl(url) {
      window.open(this.resolveUrl(url), '_blank')
    },

    copyMessage(msg) {
      const text = msg.content || ''
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          uni.showToast({ title: 'Copied', icon: 'success' })
        }).catch(() => {
          uni.showToast({ title: 'Copy failed', icon: 'none' })
        })
      }
    },

    cleanupPendingAttachments() {
      this.pendingAttachments.forEach(a => { if (a.localPreview) URL.revokeObjectURL(a.localPreview) })
      this.pendingAttachments = []
      this.showAttachMenu = false
    }
  }
}
</script>

<style scoped>
.study-page {
  display: flex;
  flex-direction: row;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: var(--color-bg);
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 1200px;
  height: 1200px;
  background: radial-gradient(circle, rgba(59,130,246,0.32) 0%, rgba(59,130,246,0.12) 45%, transparent 75%);
  top: -25%;
  left: -10%;
  filter: blur(90px);
  animation: aurora-drift-a 12s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 850px;
  height: 850px;
  background: radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(249,115,22,0.09) 45%, transparent 75%);
  top: 10%;
  right: -10%;
  filter: blur(70px);
  animation: aurora-drift-b 10s ease-in-out infinite;
}

.aurora-blob-3 {
  width: 950px;
  height: 950px;
  background: radial-gradient(circle, rgba(79,70,229,0.20) 0%, rgba(79,70,229,0.08) 45%, transparent 75%);
  bottom: -15%;
  left: 25%;
  filter: blur(90px);
  animation: aurora-drift-c 14s ease-in-out infinite;
}

@keyframes aurora-drift-a {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(50px, 35px) scale(1.06); }
  66% { transform: translate(-25px, 15px) scale(0.97); }
}

@keyframes aurora-drift-b {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-40px, 30px) scale(1.05); }
  66% { transform: translate(20px, -25px) scale(0.98); }
}

@keyframes aurora-drift-c {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -35px) scale(1.07); }
  66% { transform: translate(-20px, 20px) scale(0.96); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
}

/* Main Content */
.study-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 1;
}

/* Header */
.study-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 28px 14px;
  flex-shrink: 0;
}

.study-header-title {
  font-size: 22px;
  font-weight: 700;
  color: #FFFFFF;
}

.study-header-actions {
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.delete-space-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.42);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.delete-space-btn:hover {
  background: rgba(239, 68, 68, 0.22);
  border-color: rgba(239, 68, 68, 0.62);
}

.delete-space-btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.delete-space-icon {
  width: 18px;
  height: 18px;
  color: #F87171;
}

.share-space-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(96, 165, 250, 0.15);
  border: 1px solid rgba(96, 165, 250, 0.42);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.share-space-btn:hover {
  background: rgba(96, 165, 250, 0.22);
  border-color: rgba(96, 165, 250, 0.62);
}

.share-space-btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.share-space-icon {
  width: 18px;
  height: 18px;
  color: #60A5FA;
}

/* Share Code Modal */
.share-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.share-modal-card {
  background: rgba(30, 32, 44, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 20px;
  padding: 32px;
  width: 380px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.share-modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
}

.share-modal-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
  line-height: 1.5;
}

.share-modal-code-box {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 16px 32px;
  margin: 8px 0;
}

.share-modal-code {
  font-size: 28px;
  font-weight: 700;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: #60A5FA;
  letter-spacing: 3px;
}

.share-modal-actions {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-top: 8px;
}

.share-modal-copy-btn {
  flex: 1;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.5), rgba(96, 165, 250, 0.4));
  border: 1px solid rgba(96, 165, 250, 0.4);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.share-modal-copy-btn:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.65), rgba(96, 165, 250, 0.55));
}

.share-modal-copy-text {
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
}

.share-modal-close-btn {
  width: 80px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.share-modal-close-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}

.share-modal-close-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

/* Share Mode Selection */
.share-mode-options {
  width: 100%;
}

.share-mode-option {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  cursor: pointer;
  border-radius: 12px;
  transition: background 0.15s ease;
}

.share-mode-option:hover {
  background: rgba(255, 255, 255, 0.06);
}

.share-mode-icon-wrap {
  width: 40px;
  height: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  margin-right: 14px;
  flex-shrink: 0;
}

.share-mode-svg-icon {
  width: 22px;
  height: 22px;
  color: rgba(255, 255, 255, 0.85);
}

.share-mode-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.share-mode-label {
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
}

.share-mode-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.share-mode-arrow {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

.share-mode-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 16px;
}

/* Two-Panel Split */
.study-panels {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: row;
  gap: 16px;
  padding: 0 28px 28px;
  min-height: 0;
}

/* Left Panel - 50% */
.panel-graph {
  flex: 1;
  min-width: 0;
}

.panel-graph-inner {
  --tab-strip: #222238;
  --tab-active: #16162a;
  --tab-hover: #1c1c34;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--tab-active);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
}

/* Chrome-style Tabs */
.chrome-tabs-bar {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  background: var(--tab-strip);
  padding: 6px 8px 0;
  flex-shrink: 0;
  gap: 2px;
}

.chrome-tab {
  padding: 8px 18px;
  border-radius: 8px 8px 0 0;
  background: transparent;
  cursor: pointer;
  position: relative;
  z-index: 0;
  transition: background 0.15s ease;
  white-space: nowrap;
}

.chrome-tab:hover:not(.chrome-tab-active) {
  background: var(--tab-hover);
}

.chrome-tab-active {
  background: var(--tab-active);
  z-index: 2;
}

.chrome-tabs-spacer {
  flex: 1;
}

.chrome-tab-label {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.4);
  transition: color 0.15s ease;
}

.chrome-tab-active .chrome-tab-label {
  color: rgba(255, 255, 255, 0.9);
}

/* Inverse rounded corners */
.chrome-tab-active::before,
.chrome-tab-active::after {
  content: '';
  position: absolute;
  bottom: 0;
  width: 8px;
  height: 8px;
  background: transparent;
}

.chrome-tab-active::before {
  left: -8px;
  border-bottom-right-radius: 8px;
  box-shadow: 2px 2px 0 var(--tab-active);
}

.chrome-tab-active::after {
  right: -8px;
  border-bottom-left-radius: 8px;
  box-shadow: -2px 2px 0 var(--tab-active);
}

/* Tab Content Area */
.tab-content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.materials-tab-panel {
  flex: 1;
  min-height: 0;
}

/* Browser Panel */
.browser-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.browser-nav {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  flex-shrink: 0;
}

.browser-nav-btn,
.browser-go-btn {
  height: 32px;
  min-width: 42px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.82);
  transition: background 0.15s ease, border-color 0.15s ease;
  box-sizing: border-box;
}

.browser-nav-btn:hover,
.browser-go-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

.browser-nav-btn-disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.browser-nav-icon,
.browser-go-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.browser-input {
  flex: 1;
  min-width: 0;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(8, 8, 20, 0.7);
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  padding: 0 10px;
  box-sizing: border-box;
}

.browser-frame-wrap {
  flex: 1;
  min-height: 0;
  position: relative;
  background: rgba(8, 8, 20, 0.45);
}

.browser-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #ffffff;
}

.browser-status-overlay,
.browser-error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
}

.browser-status-overlay {
  background: rgba(10, 10, 22, 0.45);
}

.browser-status-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.browser-error-overlay {
  background: rgba(10, 10, 22, 0.7);
}

.browser-error-card {
  width: 100%;
  max-width: 380px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.08);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
}

.browser-error-title {
  color: rgba(255, 255, 255, 0.94);
  font-size: 14px;
  font-weight: 600;
}

.browser-error-sub {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  line-height: 1.5;
}

.browser-open-external-btn {
  height: 32px;
  width: fit-content;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.browser-open-external-btn-text {
  color: rgba(255, 255, 255, 0.9);
  font-size: 12px;
}

.browser-unsupported {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.placeholder-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* Graph Actions */
.graph-actions {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 6;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-end;
  padding: 0 16px 16px;
  pointer-events: none;
}

.graph-action-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: auto;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.28);
  transition: background 0.15s ease;
}

.graph-action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.graph-action-btn-active {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.4);
}

.graph-action-btn-active .action-icon {
  color: rgba(59, 130, 246, 0.9);
}

.action-icon {
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.6);
}

.action-icon-img {
  width: 18px;
  height: 18px;
}

/* Right Panel - 50% */
.panel-chat {
  position: relative;
  flex: 1;
  min-width: 0;
}

.panel-chat-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
}

/* Chat Messages List */
.chat-messages-list {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
  width: 100%;
}

/* Custom Scrollbar — matches dark glassmorphic theme */
.chat-messages-list :deep(.uni-scroll-view)::-webkit-scrollbar {
  width: 6px;
}

.chat-messages-list :deep(.uni-scroll-view)::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.chat-messages-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Firefox */
.chat-messages-list :deep(.uni-scroll-view) {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

/* Empty State */
.chat-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
  gap: 8px;
}

.chat-empty-icon {
  margin-bottom: 8px;
}

.chat-empty-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.15);
}

.chat-empty-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.08);
}

/* Loading */
.chat-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  gap: 12px;
}

.chat-loading-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.3);
}

/* Message Rows */
.message-row {
  display: flex;
  margin-bottom: 12px;
  max-width: 100%;
  box-sizing: border-box;
}

.message-row-left {
  justify-content: flex-start;
}

.message-row-right {
  justify-content: flex-end;
}

/* User message group: images + bubble stacked */
.user-msg-group {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-width: 85%;
  margin-left: auto;
}

/* User bubble row with retry button */
.user-bubble-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.msg-retry-btn {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background-color: #FF3B30;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.2s;
}
.msg-retry-btn:hover {
  opacity: 0.8;
}

.msg-retry-icon {
  width: 14px;
  height: 14px;
  color: white;
}

/* Message Bubbles */
.message-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  word-break: break-word;
}

.bubble-user {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-bottom-right-radius: 4px;
}

.user-bubble-row .bubble-user {
  max-width: none;
}

.bubble-user .bubble-text {
  color: rgba(255, 255, 255, 0.95);
  font-size: 14px;
  line-height: 1.5;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
  user-select: text;
}

.bubble-ai {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom-left-radius: 4px;
}

/* User message actions */
.user-msg-actions {
  display: flex;
  flex-direction: row;
  gap: 8px;
  margin-top: 4px;
  justify-content: flex-end;
  padding-right: 4px;
}

.ai-msg-action-icon {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: color 0.15s ease;
}

.ai-msg-action-icon:hover {
  color: rgba(255, 255, 255, 0.5);
}

/* Segment rendering */
.segment-text {
  width: 100%;
}

.segment-tool {
  width: 100%;
  margin: 6px 0;
}

/* Tool Call Cards */
.tool-call-card {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  transition: border-color 0.2s ease, background 0.2s ease;
}

.tool-call-running {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.06);
}

.tool-call-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.tool-call-failed {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
}

.tool-call-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

/* Spinner */
.tool-call-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: rgba(59, 130, 246, 0.9);
  border-radius: 50%;
  animation: tool-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes tool-spin {
  to { transform: rotate(360deg); }
}

.tool-call-status-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.tool-status-success {
  color: rgba(34, 197, 94, 0.9);
}

.tool-status-failed {
  color: rgba(239, 68, 68, 0.9);
}

.tool-call-icon {
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.tool-call-name {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.tool-call-args {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

/* Chart preview */
.chart-image-preview {
  margin-top: 8px;
  border-radius: 8px;
  overflow: hidden;
}

.chart-preview-img {
  width: 100%;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.chart-preview-img:hover {
  opacity: 0.9;
}

.chart-saved-badge {
  margin-top: 4px;
  display: flex;
  align-items: center;
}

.chart-saved-icon {
  width: 14px;
  height: 14px;
  opacity: 0.45;
  margin-right: 3px;
  flex-shrink: 0;
}

.chart-saved-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.tool-call-result {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.tool-call-result-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
}

/* Code Execution Card */
.code-execution-card .code-block-section {
  margin-top: 8px;
}

.code-toggle-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
}

.code-toggle-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.code-toggle-text:hover {
  color: rgba(255, 255, 255, 0.6);
}

.code-toggle-chevron {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.35);
  transition: transform 0.2s ease;
}

.code-toggle-chevron-expanded {
  transform: rotate(180deg);
}

.code-block-wrapper {
  max-height: 400px;
  overflow: hidden;
  transition: max-height 0.3s ease, opacity 0.2s ease, margin-top 0.2s ease;
  opacity: 1;
  margin-top: 6px;
}

.code-block-collapsed {
  max-height: 0;
  opacity: 0;
  margin-top: 0;
}

.code-block-pre {
  margin: 0;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  overflow-x: auto;
  max-height: 380px;
  overflow-y: auto;
}

.code-block-code {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.85);
  white-space: pre;
  tab-size: 4;
}

.code-output-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.code-output-stdout {
  margin: 0;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 6px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.code-output-stderr {
  margin: 6px 0 0;
  padding: 8px 10px;
  background: rgba(220, 38, 38, 0.1);
  border-radius: 6px;
  border-left: 3px solid rgba(220, 38, 38, 0.4);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(248, 113, 113, 0.9);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

/* Memory Tool Inline */
.memory-tool-inline {
  display: inline-flex;
  align-items: center;
  padding: 2px 0;
}

.memory-tool-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}

.memory-tool-active .memory-tool-text {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.3) 0%,
    rgba(255,255,255,0.6) 50%,
    rgba(255,255,255,0.3) 100%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: memory-shimmer 1.5s ease-in-out infinite;
}

@keyframes memory-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: -100% 50%; }
}

/* Planning Tool Inline (get_tool_details) */
.planning-tool-inline {
  display: inline-flex;
  align-items: center;
  padding: 2px 0;
  overflow: hidden;
  max-height: 0;
  transition: max-height 0.4s ease, opacity 0.4s ease, margin 0.4s ease, padding 0.4s ease, line-height 0.4s ease, font-size 0.4s ease;
}

.planning-tool-active {
  max-height: 30px;
  opacity: 1;
}

.planning-tool-done {
  max-height: 0;
  opacity: 0;
  margin: 0;
  padding: 0;
  line-height: 0;
  font-size: 0;
  border: 0;
  pointer-events: none;
}

.planning-tool-text {
  font-size: 13px;
  font-style: italic;
  color: rgba(192, 199, 210, 0.5);
}

.planning-tool-active .planning-tool-text {
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
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: planning-shimmer 2s ease-in-out infinite;
}

@keyframes planning-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: -100% 50%; }
}

/* Search Result List */
.search-results-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  cursor: pointer;
  transition: background 0.15s;
}

.search-result-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.search-result-favicon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
}

.search-result-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.search-result-domain {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
  margin-left: auto;
}

.search-results-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 0;
  margin-top: 2px;
  cursor: pointer;
}

.search-results-toggle-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

/* Typing Indicator */
.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  animation: typing-bounce 1.2s ease-in-out infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* Chat Input Bar */
.chat-input-bar {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  min-width: 0;
  width: 0;
  height: 36px;
  min-height: 36px;
  padding: 7px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: #FFFFFF;
  font-size: 14px;
  line-height: 20px;
  box-sizing: border-box;
  overflow: hidden;
  outline: none;
}

.chat-input-textarea {
  resize: none;
  white-space: pre-wrap;
  word-break: break-word;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

textarea.chat-input-textarea {
  width: 100%;
  box-sizing: border-box;
}

.chat-input-textarea :deep(.uni-textarea-wrapper),
.chat-input-textarea :deep(.uni-textarea-placeholder) {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

.chat-input-textarea :deep(textarea),
.chat-input-textarea :deep(.uni-textarea-textarea) {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 0;
  margin: 0;
  line-height: 20px;
  font-size: 14px;
  color: #FFFFFF;
  background: transparent;
  border: none;
  outline: none;
}

.chat-input-textarea::-webkit-scrollbar {
  width: 6px;
}

.chat-input-textarea::-webkit-scrollbar-track {
  background: transparent;
}

.chat-input-textarea::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.chat-input-textarea::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.chat-input-textarea :deep(textarea::-webkit-scrollbar),
.chat-input-textarea :deep(.uni-textarea-textarea::-webkit-scrollbar) {
  width: 6px;
}

.chat-input-textarea :deep(textarea::-webkit-scrollbar-track),
.chat-input-textarea :deep(.uni-textarea-textarea::-webkit-scrollbar-track) {
  background: transparent;
}

.chat-input-textarea :deep(textarea::-webkit-scrollbar-thumb),
.chat-input-textarea :deep(.uni-textarea-textarea::-webkit-scrollbar-thumb) {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.chat-input-textarea :deep(textarea::-webkit-scrollbar-thumb:hover),
.chat-input-textarea :deep(.uni-textarea-textarea::-webkit-scrollbar-thumb:hover) {
  background: rgba(255, 255, 255, 0.2);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.chat-send-btn:hover {
  background: rgba(59, 130, 246, 0.25);
}

.chat-send-btn-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-icon {
  width: 16px;
  height: 16px;
  color: var(--color-accent-blue);
}

/* Stop Button */
.chat-stop-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.chat-stop-btn:hover {
  background: rgba(239, 68, 68, 0.25);
}

.stop-icon {
  width: 18px;
  height: 18px;
  color: rgba(239, 68, 68, 0.9);
}

/* Placeholder Text */
.placeholder-text {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.15);
}

.placeholder-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.08);
}

/* Chat Panel Header */
.chat-panel-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.chat-header-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.chat-header-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.chat-header-btn-disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
}

.chat-header-icon {
  width: 16px;
  height: 16px;
}

/* History button wrapper — relative anchor for popup */
.chat-header-btn-wrap {
  position: relative;
}

/* History Backdrop */
.history-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 90;
}

/* History Popup — anchored below button */
.history-popup {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: 320px;
  max-height: 420px;
  background: rgba(22, 22, 42, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
}

.history-popup-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.history-popup-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.history-popup-close {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.history-popup-close:hover {
  background: rgba(255, 255, 255, 0.08);
}

.history-popup-close-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
}

.history-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.history-list {
  flex: 1;
  min-height: 0;
  max-height: 360px;
  overflow-y: auto;
  padding: 4px 0;
}

.history-list :deep(.uni-scroll-view)::-webkit-scrollbar {
  width: 6px;
}

.history-list :deep(.uni-scroll-view)::-webkit-scrollbar-track {
  background: transparent;
}

.history-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.history-list :deep(.uni-scroll-view)::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.history-list :deep(.uni-scroll-view) {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.history-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.history-empty-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.25);
}

.history-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 16px;
  cursor: pointer;
  transition: background 0.15s ease;
  border-left: 3px solid transparent;
}

.history-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.history-item-active {
  background: rgba(59, 130, 246, 0.08);
  border-left-color: rgba(59, 130, 246, 0.7);
}

.history-item-active:hover {
  background: rgba(59, 130, 246, 0.12);
}

.history-item-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-active .history-item-title {
  color: rgba(255, 255, 255, 0.95);
}

.history-item-date {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
}

/* History popup transition */
.history-fade-enter-active,
.history-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.history-fade-enter-from,
.history-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ==================== Attachment Styles ==================== */

/* Attachment preview area */
.attach-preview-area {
  padding: 8px 16px 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.attach-preview-scroll {
  display: flex;
  flex-direction: row;
  gap: 8px;
  overflow-x: auto;
}
.attach-preview-item {
  position: relative;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.attach-preview-img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  display: block;
}
.attach-preview-file {
  width: 120px;
  height: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 8px;
  box-sizing: border-box;
}
.attach-preview-file-icon { font-size: 20px; }
.attach-preview-file-name {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attach-preview-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  line-height: 1;
}
.attach-preview-uploading {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}
.attach-upload-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: attach-spin 0.8s linear infinite;
}
@keyframes attach-spin { to { transform: rotate(360deg); } }

/* "+" button */
.attach-btn-wrap { position: relative; flex-shrink: 0; }
.attach-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease;
}
.attach-btn:hover { background: rgba(255, 255, 255, 0.1); }
.attach-btn-disabled { opacity: 0.4; pointer-events: none; }
.attach-btn-icon { width: 18px; height: 18px; color: rgba(255, 255, 255, 0.6); }

/* Attach menu popover (pops UP from bottom) */
.attach-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: rgba(30, 32, 40, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 4px;
  min-width: 120px;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}
.attach-menu-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}
.attach-menu-item:hover { background: rgba(255, 255, 255, 0.08); }
.attach-menu-icon { width: 16px; height: 16px; flex-shrink: 0; opacity: 0.92; }
.attach-menu-label { font-size: 13px; color: rgba(255, 255, 255, 0.85); }
.attach-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
}

/* Attach menu transition */
.attach-menu-fade-enter-active,
.attach-menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.attach-menu-fade-enter-from,
.attach-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

/* Message attachments (outside bubble) */
.msg-attachments-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 6px;
}

.msg-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}
.msg-attach-img {
  width: 160px;
  height: 160px;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  object-fit: cover;
}
.msg-attach-file {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  cursor: pointer;
}
.msg-attach-file-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Quiz Entry Card */
.quiz-entry-card {
  margin-top: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(99, 102, 241, 0.4);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(59, 130, 246, 0.08) 100%);
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.quiz-entry-card:hover {
  border-color: rgba(99, 102, 241, 0.6);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.18) 0%, rgba(59, 130, 246, 0.12) 100%);
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.15);
}

.quiz-entry-card:active {
  transform: scale(0.98);
}

.quiz-entry-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
}

.quiz-entry-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(99, 102, 241, 0.9);
  flex-shrink: 0;
}

.quiz-entry-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.quiz-entry-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.quiz-entry-subtitle {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.quiz-entry-arrow {
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.quiz-entry-card:hover .quiz-entry-arrow {
  transform: translateX(3px);
  color: rgba(255, 255, 255, 0.6);
}

/* ==================== Model Selector ==================== */
.model-selector-wrap {
  position: relative;
  flex-shrink: 0;
}

.model-selector-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px 3px 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.15s ease;
  height: 28px;
  box-sizing: border-box;
}

.model-selector-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.model-selector-icon {
  width: 13px;
  height: 13px;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.model-selector-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-selector-chevron {
  width: 10px;
  height: 10px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

/* Model menu dropdown (opens DOWN from header) */
.model-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: rgba(22, 22, 42, 0.96);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 4px;
  min-width: 220px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.model-menu-down {
  bottom: auto;
  top: calc(100% + 6px);
}

.model-menu-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.model-menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.model-menu-item-active {
  background: rgba(59, 130, 246, 0.12);
}

.model-menu-item-active:hover {
  background: rgba(59, 130, 246, 0.18);
}

.model-menu-item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.model-menu-item-name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.model-menu-item-active .model-menu-item-name {
  color: #60A5FA;
}

.model-menu-item-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-menu-check {
  width: 18px;
  height: 18px;
  color: #60A5FA;
  flex-shrink: 0;
  margin-left: 8px;
}

.model-menu-item-locked {
  opacity: 0.5;
}

.model-menu-item-locked .model-menu-item-name {
  color: #9CA3AF;
}

.model-menu-lock {
  width: 18px;
  height: 18px;
  color: #9CA3AF;
  flex-shrink: 0;
  margin-left: 8px;
}

.model-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
}

/* Model menu transition */
.model-menu-fade-enter-active,
.model-menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.model-menu-fade-enter-from,
.model-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ==================== Thinking Block ==================== */
.thinking-block {
  width: 100%;
  margin-bottom: 8px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  cursor: pointer;
  user-select: none;
}

.thinking-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(168, 85, 247, 0.3);
  border-top-color: rgba(168, 85, 247, 0.8);
  border-radius: 50%;
  animation: thinking-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes thinking-spin {
  to { transform: rotate(360deg); }
}

.thinking-label {
  font-size: 13px;
  color: rgba(168, 85, 247, 0.85);
  flex: 1;
}

.thinking-chevron {
  font-size: 10px;
  color: rgba(168, 85, 247, 0.6);
  flex-shrink: 0;
  transition: transform 0.2s ease;
  display: inline-block;
}

.thinking-chevron-expanded {
  transform: rotate(180deg);
}

.thinking-body {
  padding-left: 12px;
  border-left: 2px solid rgba(168, 85, 247, 0.4);
  max-height: 800px;
  opacity: 1;
  overflow: hidden;
  transition: max-height 0.35s ease-out, opacity 0.25s ease 0.05s, margin-top 0.25s ease;
  margin-top: 4px;
}

.thinking-body-collapsed {
  max-height: 0;
  opacity: 0;
  margin-top: 0;
  transition: max-height 0.2s cubic-bezier(0, 0.8, 0.3, 1), opacity 0.15s ease, margin-top 0.15s ease;
}

.thinking-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ==================== Tool Mode Selector ==================== */
.tool-selector-wrap {
  position: relative;
  flex-shrink: 0;
}

.tool-selector-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px 3px 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.15s ease;
  height: 28px;
  box-sizing: border-box;
}

.tool-selector-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tool-selector-icon {
  width: 13px;
  height: 13px;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.tool-selector-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}

.tool-selector-chevron {
  width: 10px;
  height: 10px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

/* Tool menu dropdown */
.tool-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: rgba(22, 22, 42, 0.96);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
  min-width: 260px;
  max-width: 320px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.tool-menu-down {
  bottom: auto;
  top: calc(100% + 6px);
}

.tool-menu-header {
  margin-bottom: 8px;
}

.tool-menu-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.tool-mode-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.tool-mode-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.tool-mode-option:hover {
  background: rgba(255, 255, 255, 0.06);
}

.tool-mode-option-active {
  background: rgba(59, 130, 246, 0.12);
}

.tool-mode-option-active:hover {
  background: rgba(59, 130, 246, 0.18);
}

.tool-mode-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  flex-shrink: 0;
  box-sizing: border-box;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.tool-mode-radio-checked {
  border-color: #60A5FA;
  background: #60A5FA;
  box-shadow: inset 0 0 0 3px rgba(22, 22, 42, 0.96);
}

.tool-mode-option-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tool-mode-option-name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.tool-mode-option-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

/* Tool catalog list (manual mode) */
.tool-catalog-list {
  max-height: 280px;
  overflow-y: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 8px;
}

.tool-catalog-list::-webkit-scrollbar {
  width: 4px;
}

.tool-catalog-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
}

.tool-catalog-category {
  margin-bottom: 8px;
}

.tool-catalog-category:last-child {
  margin-bottom: 0;
}

.tool-catalog-category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 4px 4px 6px;
}

.tool-catalog-category-name {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tool-catalog-category-count {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.3);
}

.tool-catalog-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.tool-catalog-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tool-catalog-checkbox {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.tool-catalog-checkbox-checked {
  background: #60A5FA;
  border-color: #60A5FA;
}

.tool-catalog-check-icon {
  width: 10px;
  height: 10px;
  color: #fff;
}

.tool-catalog-item-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-catalog-loading {
  padding: 12px 0;
  text-align: center;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  margin-top: 8px;
}

.tool-catalog-loading-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.tool-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
}

/* Dual Sync Toggle */
.dual-sync-toggle {
  display: flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: all 0.2s;
  margin-right: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.dual-sync-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
}
.dual-sync-active {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
}
.dual-sync-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}
.dual-sync-active .dual-sync-label {
  color: rgba(99, 102, 241, 0.9);
}

/* Annotation Overlay */
.annotation-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 100;
}
.ann-rect {
  position: absolute;
  border: 2.5px solid;
  border-radius: 4px;
  background: rgba(255, 107, 107, 0.08);
  animation: ann-fade-in 0.3s ease;
}
.ann-comment {
  position: absolute;
  bottom: -28px;
  left: 0;
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
@keyframes ann-fade-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* Dual-sync panel border effects — outer ring with gap via outline + offset */
.panel-graph-inner.panel-synced,
.panel-chat-inner.panel-synced {
  outline: 2px solid rgba(74, 222, 128, 0.5);
  outline-offset: 4px;
  box-shadow: 0 0 16px rgba(74, 222, 128, 0.15);
  transition: outline-color 0.4s ease, box-shadow 0.4s ease;
}

/* Dual-sync link indicator — absolutely centered, overlaps both panel borders */
.dual-sync-link-indicator {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.dual-sync-link-indicator .link-icon {
  width: 24px;
  height: 24px;
  color: rgba(74, 222, 128, 0.8);
  filter: drop-shadow(0 0 4px rgba(74, 222, 128, 0.4));
}

/* Collaborative User Filter */
.collab-user-filter {
  position: absolute;
  top: 8px;
  right: 12px;
  z-index: 20;
}
.filter-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.filter-trigger:hover {
  background: rgba(255,255,255,0.14);
}
.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.filter-label {
  font-size: 12px;
  color: rgba(255,255,255,0.8);
}
.filter-arrow {
  font-size: 10px;
  color: rgba(255,255,255,0.5);
}
.member-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 160px;
  background: #1a1a2e;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.member-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.member-item:hover {
  background: rgba(255,255,255,0.08);
}
.member-item-active {
  background: rgba(0,136,255,0.15);
}
.member-name {
  font-size: 13px;
  color: rgba(255,255,255,0.85);
}
</style>
