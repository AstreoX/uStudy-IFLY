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
                v-for="tab in visibleTabs"
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
                :isForeignGraphView="isForeignGraphView"
                :canEditGraph="canEditGraph"
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
              <!-- Leaderboard Tab (collaborative spaces) -->
              <view v-else-if="activeTab === 'leaderboard'" class="leaderboard-panel">
                <view v-if="leaderboardLoading" class="leaderboard-loading">
                  <view class="typing-indicator">
                    <view class="typing-dot"></view>
                    <view class="typing-dot"></view>
                    <view class="typing-dot"></view>
                  </view>
                </view>
                <view v-else-if="leaderboardData.length === 0" class="leaderboard-empty">
                  <text class="placeholder-text">暂无排行数据</text>
                  <text class="placeholder-sub">成员开始学习后将显示排行</text>
                </view>
                <scroll-view v-else class="leaderboard-scroll" scroll-y>
                  <!-- Podium: Top 3 -->
                  <view v-if="leaderboardData.length >= 3" class="leaderboard-podium">
                    <!-- 2nd place -->
                    <view class="podium-item podium-2nd">
                      <view class="podium-avatar" :style="{ borderColor: leaderboardData[1].color || '#C0C0C0' }">
                        <text class="podium-avatar-text">{{ (leaderboardData[1].nickname || '?')[0] }}</text>
                      </view>
                      <text class="podium-name">{{ leaderboardData[1].nickname }}</text>
                      <text class="podium-score">{{ leaderboardData[1].composite_score }}</text>
                      <view class="podium-bar podium-bar-2nd">
                        <text class="podium-rank">2</text>
                      </view>
                    </view>
                    <!-- 1st place -->
                    <view class="podium-item podium-1st">
                      <view class="podium-crown">&#x1F451;</view>
                      <view class="podium-avatar podium-avatar-1st" :style="{ borderColor: leaderboardData[0].color || '#FFD700' }">
                        <text class="podium-avatar-text">{{ (leaderboardData[0].nickname || '?')[0] }}</text>
                      </view>
                      <text class="podium-name podium-name-1st">{{ leaderboardData[0].nickname }}</text>
                      <text class="podium-score podium-score-1st">{{ leaderboardData[0].composite_score }}</text>
                      <view class="podium-bar podium-bar-1st">
                        <text class="podium-rank">1</text>
                      </view>
                    </view>
                    <!-- 3rd place -->
                    <view class="podium-item podium-3rd">
                      <view class="podium-avatar" :style="{ borderColor: leaderboardData[2].color || '#CD7F32' }">
                        <text class="podium-avatar-text">{{ (leaderboardData[2].nickname || '?')[0] }}</text>
                      </view>
                      <text class="podium-name">{{ leaderboardData[2].nickname }}</text>
                      <text class="podium-score">{{ leaderboardData[2].composite_score }}</text>
                      <view class="podium-bar podium-bar-3rd">
                        <text class="podium-rank">3</text>
                      </view>
                    </view>
                  </view>

                  <!-- Score breakdown header -->
                  <view class="leaderboard-header-row">
                    <text class="lb-header-rank">#</text>
                    <text class="lb-header-name">成员</text>
                    <text class="lb-header-metric">掌握度</text>
                    <text class="lb-header-metric">测试</text>
                    <text class="lb-header-metric">笔记</text>
                    <text class="lb-header-metric">综合分</text>
                  </view>

                  <!-- Full list -->
                  <view
                    v-for="entry in leaderboardData"
                    :key="entry.user_id"
                    class="leaderboard-row"
                    :class="{ 'leaderboard-row-self': entry.user_id === currentUserId }"
                  >
                    <view class="lb-rank-cell">
                      <text v-if="entry.rank === 1" class="lb-rank-medal">&#x1F947;</text>
                      <text v-else-if="entry.rank === 2" class="lb-rank-medal">&#x1F948;</text>
                      <text v-else-if="entry.rank === 3" class="lb-rank-medal">&#x1F949;</text>
                      <text v-else class="lb-rank-num">{{ entry.rank }}</text>
                    </view>
                    <view class="lb-name-cell">
                      <view class="lb-color-dot" :style="{ background: entry.color || '#0088FF' }"></view>
                      <text class="lb-name">{{ entry.nickname }}</text>
                      <text v-if="entry.role === 'owner'" class="lb-owner-badge">管理员</text>
                    </view>
                    <view class="lb-metric-cell">
                      <text class="lb-metric-value">{{ entry.avg_mastery }}%</text>
                      <view class="lb-metric-bar">
                        <view class="lb-metric-bar-fill lb-bar-mastery" :style="{ width: entry.avg_mastery + '%' }"></view>
                      </view>
                    </view>
                    <view class="lb-metric-cell">
                      <text class="lb-metric-value">{{ entry.avg_quiz_score }}%</text>
                      <view class="lb-metric-bar">
                        <view class="lb-metric-bar-fill lb-bar-quiz" :style="{ width: entry.avg_quiz_score + '%' }"></view>
                      </view>
                    </view>
                    <view class="lb-metric-cell">
                      <text class="lb-metric-value">{{ entry.notes_count }}</text>
                    </view>
                    <view class="lb-metric-cell lb-composite-cell">
                      <text class="lb-composite-score">{{ entry.composite_score }}</text>
                    </view>
                  </view>

                  <!-- Legend -->
                  <view class="leaderboard-legend">
                    <text class="leaderboard-legend-text">综合分 = 掌握度×50% + 测试×30% + 活跃度×20%</text>
                  </view>
                </scroll-view>
              </view>
              <!-- Member Management Tab (owner only) -->
              <view v-else-if="activeTab === 'manage'" class="manage-panel">
                <view class="manage-panel-list">
                  <view v-for="m in spaceMembers" :key="m.user_id" class="manage-member-item">
                    <view class="manage-member-info">
                      <view class="manage-color-dot" :style="{ background: m.color || '#0088FF' }"></view>
                      <text class="manage-member-name">{{ m.nickname }}</text>
                      <text v-if="m.role === 'owner'" class="manage-owner-badge">管理员</text>
                    </view>
                    <view v-if="m.role !== 'owner'" class="manage-member-actions">
                      <view class="manage-toggle-row">
                        <text class="manage-toggle-text">可修改图谱</text>
                        <switch
                          :checked="m.can_edit_graph"
                          @change="handleToggleGraphEdit(m, $event)"
                          class="manage-toggle"
                        />
                      </view>
                      <view class="manage-remove-btn" @tap="handleRemoveMember(m)">
                        移除
                      </view>
                    </view>
                  </view>
                </view>
              </view>
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

        <!-- Right Panel: Chat or DocKG Generation -->
        <view class="panel-chat">
          <!-- Document KG generation mode: streaming panel -->
          <DocKgGenPanel
            v-if="docKgMode && !docKgCompleted"
            :spaceId="spaceId"
            :documentIds="docKgDocIds"
            @kg-node="handleDocKgNode"
            @kg-edge="handleDocKgEdge"
            @done="handleDocKgDone"
            @error="handleDocKgError"
          />

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
          <view v-show="!docKgMode || docKgCompleted" class="panel-chat-inner" :class="{ 'panel-synced': dualSyncEnabled }">
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
                        <text class="model-menu-item-desc">{{ m.locked ? '实验账号权限异常' : m.description }}</text>
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
                <view v-else class="message-bubble bubble-ai" :class="{ 'bubble-ai-tools-only': isToolOnlyMessage(msg) }">
                  <!-- Thinking block -->
                  <AgentThinkingBlock
                    v-if="msg.thinkingContent || msg.isThinking"
                    :content="msg.thinkingContent || ''"
                    :active="Boolean(msg.isThinking)"
                    :duration="msg.thinkingDuration || 0"
                  />

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

                      <!-- Review tools -->
                      <view
                        v-else-if="isReviewTool(seg.toolCall.tool)"
                        class="review-tool-wrap"
                        :class="{ 'review-expanded-container': seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id)) }"
                      >
                        <view
                          class="graph-tool-pill"
                          :class="{
                            'graph-tool-running': seg.toolCall.status === 'running',
                            'graph-tool-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                          @click="toggleToolCardIfAllowed(seg.toolCall)"
                        >
                          <view class="graph-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="graph-tool-pill-text">{{ getReviewToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                        <view
                          v-if="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && getReviewDisplayItems(seg.toolCall).length && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="review-card"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <view v-for="(item, idx) in getReviewDisplayItems(seg.toolCall)" :key="idx" class="review-event-item">
                            <view class="review-event-header">
                              <text class="review-event-label">{{ item.activity_title || item.title || '待复习内容' }}</text>
                              <text v-if="item.study_depth" class="review-event-depth">{{ item.study_depth }}</text>
                            </view>
                            <view class="review-event-meta">
                              <text class="review-event-round">第{{ item.review_number || 0 }}次复习</text>
                              <view class="review-event-urgency-badge" :class="{ 'urgency-overdue': item.overdue_days > 0 }">
                                <text class="review-event-urgency-text" :class="{ 'urgency-overdue-text': item.overdue_days > 0 }">
                                  {{ item.urgency || '待复习' }}
                                </text>
                              </view>
                            </view>
                          </view>
                          <view class="review-card-footer">
                            <text class="review-card-count">共 {{ getReviewDisplayItems(seg.toolCall).length }} 条待复习</text>
                          </view>
                        </view>

                        <view
                          v-else-if="seg.toolCall.tool === 'get_review_events' && seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="review-card review-card-empty"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <text class="review-empty-text">当前没有待复习项</text>
                        </view>
                      </view>

                      <!-- Graph overview -->
                      <view
                        v-else-if="isGraphOverviewTool(seg.toolCall.tool)"
                        class="graph-overview-wrap"
                      >
                        <view
                          class="graph-tool-pill"
                          :class="{
                            'graph-tool-running': seg.toolCall.status === 'running',
                            'graph-tool-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                        >
                          <view class="graph-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                      </view>

                      <!-- Graph mutation/query/path tools -->
                      <view
                        v-else-if="isGraphDetailTool(seg.toolCall.tool)"
                        class="gm-wrap"
                      >
                        <view
                          class="graph-tool-pill"
                          :class="{
                            'graph-tool-running': seg.toolCall.status === 'running',
                            'graph-tool-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                        >
                          <view class="graph-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="graph-tool-pill-text">{{ getGraphToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                      </view>

                      <!-- Schedule tools -->
                      <view
                        v-else-if="isScheduleTool(seg.toolCall.tool)"
                        class="schedule-view-wrap"
                        :class="{ 'schedule-expanded-container': isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id)) }"
                      >
                        <view
                          class="graph-tool-pill"
                          :class="{
                            'graph-tool-running': seg.toolCall.status === 'running',
                            'graph-tool-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                          @click="toggleToolCardIfAllowed(seg.toolCall)"
                        >
                          <view class="graph-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="graph-tool-pill-text">{{ getScheduleToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                        <view
                          v-if="isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && getScheduleDisplayEvents(seg.toolCall).length && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="schedule-card"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <template v-for="(group, idx) in groupScheduleByDate(getScheduleDisplayEvents(seg.toolCall))" :key="group.date + '-' + idx">
                            <view class="schedule-date-header">
                              <view class="schedule-date-dot" :class="{ 'schedule-date-dot-today': group.isToday }"></view>
                              <text class="schedule-date-text" :class="{ 'schedule-date-text-today': group.isToday }">{{ group.label }}</text>
                            </view>
                            <view v-for="(event, eventIdx) in group.events" :key="group.date + '-' + eventIdx" class="schedule-event-row">
                              <view class="schedule-event-time">
                                <text class="schedule-event-time-start">{{ event.startShort }}</text>
                                <text class="schedule-event-time-end">{{ event.endShort }}</text>
                              </view>
                              <view class="schedule-event-bar" :style="{ background: event.barColor }"></view>
                              <view class="schedule-event-info">
                                <text class="schedule-event-title">{{ event.title }}</text>
                                <text v-if="event.details" class="schedule-event-desc">{{ event.details }}</text>
                              </view>
                            </view>
                          </template>
                          <view v-if="seg.toolCall.tool === 'get_schedule'" class="schedule-card-footer">
                            <text class="schedule-card-count">共 {{ getScheduleDisplayEvents(seg.toolCall).length }} 个日程</text>
                          </view>
                        </view>

                        <view
                          v-else-if="isScheduleDetailTool(seg.toolCall.tool) && seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="schedule-card schedule-card-empty"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <text class="schedule-empty-text">该时间范围内没有日程安排</text>
                        </view>
                      </view>

                      <!-- Search tools -->
                      <view
                        v-else-if="isSearchTool(seg.toolCall.tool)"
                        class="search-tool-wrap"
                      >
                        <view
                          class="search-indicator"
                          :class="{
                            'search-indicator-running': seg.toolCall.status === 'running',
                            'search-indicator-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'search-indicator-failed': seg.toolCall.status === 'done' && !seg.toolCall.success,
                            'search-indicator-expanded': seg.toolCall.status === 'done' && seg.toolCall.success && isSearchExpanded(seg.toolCall.id),
                            'search-indicator-collapsed': seg.toolCall.status === 'done' && seg.toolCall.success && !isSearchExpanded(seg.toolCall.id)
                          }"
                          @click="seg.toolCall.status !== 'running' && toggleSearchResults(seg.toolCall.id)"
                        >
                          <view class="search-indicator-globe graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="search-indicator-text">{{ getSearchToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="search-indicator-spinner"></view>
                          <text v-else class="search-indicator-chevron" :class="{ 'search-chevron-up': isSearchExpanded(seg.toolCall.id) }">⌄</text>
                        </view>

                        <scroll-view
                          v-if="seg.toolCall.status === 'done' && seg.toolCall.success && getSearchToolResults(seg.toolCall).length && isSearchExpanded(seg.toolCall.id)"
                          class="search-sources-scroll"
                          scroll-x
                          :show-scrollbar="false"
                        >
                          <view class="search-sources-row">
                            <view v-for="(item, idx) in getSearchToolResults(seg.toolCall)" :key="idx" class="search-source-card" @click="openSearchResultUrl(item.url)">
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

                        <view v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" class="search-tool-empty">
                          <text class="search-tool-empty-text">{{ seg.toolCall.result?.message || '未找到相关结果' }}</text>
                        </view>

                        <view v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" class="search-tool-error">
                          <text class="search-tool-error-text">{{ seg.toolCall.result?.message || '搜索失败' }}</text>
                        </view>
                      </view>

                      <!-- Quiz result/detail tools -->
                      <view
                        v-else-if="isQuizResultTool(seg.toolCall.tool)"
                        class="quiz-tool-wrap"
                        :class="{ 'quiz-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id)) }"
                      >
                        <view
                          class="quiz-tool-pill"
                          :class="{
                            'quiz-tool-running': seg.toolCall.status === 'running',
                            'quiz-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'quiz-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                          @click="toggleToolCardIfAllowed(seg.toolCall)"
                        >
                          <view class="quiz-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="quiz-tool-pill-text">{{ getQuizToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="quiz-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                        <view
                          v-if="seg.toolCall.tool === 'view_quiz_results' && seg.toolCall.status === 'done' && seg.toolCall.success && getQuizResultList(seg.toolCall).length && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="quiz-tool-results-card"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <view
                            v-for="(quiz, idx) in getQuizResultList(seg.toolCall)"
                            :key="quiz.id || idx"
                            class="quiz-result-item"
                            :class="{
                              'quiz-result-clickable': getQuizClickAction(quiz) !== 'disabled',
                              'quiz-result-evaluating': quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating'
                            }"
                            @click="onQuizItemClick(quiz)"
                          >
                            <view class="quiz-result-row">
                              <text class="quiz-result-title">{{ quiz.title || '未命名测验' }}</text>
                              <text v-if="quiz.difficulty" class="quiz-result-difficulty" :class="'difficulty-' + quiz.difficulty">{{ getDifficultyLabel(quiz.difficulty) }}</text>
                            </view>
                            <view class="quiz-result-meta">
                              <text v-if="quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating'" class="quiz-result-evaluating-text">评估中</text>
                              <text v-else-if="quiz.attempt_status === 'in_progress'" class="quiz-result-evaluating-text">进行中</text>
                              <text v-else-if="quiz.has_attempt" class="quiz-result-score">{{ quiz.score }}/{{ quiz.total_score }}</text>
                              <text v-else class="quiz-result-no-attempt">未作答</text>
                              <text class="quiz-result-date">{{ quiz.created_at || '' }}</text>
                              <text v-if="getQuizClickAction(quiz) !== 'disabled'" class="quiz-result-arrow">›</text>
                            </view>
                          </view>
                        </view>

                        <view
                          v-else-if="seg.toolCall.tool === 'view_quiz_results' && seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="quiz-tool-empty"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <text class="quiz-tool-empty-text">{{ seg.toolCall.result?.message || '当前学习空间没有测验' }}</text>
                        </view>

                        <view
                          v-else-if="seg.toolCall.tool === 'view_quiz_attempt_detail' && seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="quiz-tool-detail-card quiz-tool-detail-clickable"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                          @click="navigateToResult(seg.toolCall.arguments?.quiz_id || seg.toolCall.result?.quiz_id)"
                        >
                          <view class="quiz-detail-score-section">
                            <view class="quiz-detail-score-header">
                              <text class="quiz-detail-score-label">得分</text>
                            </view>
                            <view class="quiz-detail-score-row">
                              <text class="quiz-detail-score-value">{{ seg.toolCall.result.score }}/{{ seg.toolCall.result.total_score }}</text>
                              <text class="quiz-detail-score-percent">({{ seg.toolCall.result.percentage }}%)</text>
                            </view>
                            <view class="quiz-detail-score-bar-bg">
                              <view class="quiz-detail-score-bar-fill" :style="{ width: (seg.toolCall.result.percentage || 0) + '%' }" :class="getScoreBarClass(seg.toolCall.result.percentage)"></view>
                            </view>
                          </view>

                          <view v-if="seg.toolCall.result.strengths?.length || seg.toolCall.result.weaknesses?.length" class="quiz-detail-analysis-section">
                            <view class="quiz-detail-analysis-header">
                              <text class="quiz-detail-section-title">分析</text>
                            </view>

                            <view v-if="seg.toolCall.result.strengths?.length" class="quiz-detail-subsection">
                              <text class="quiz-detail-subsection-title">优势</text>
                              <view v-for="(item, idx) in seg.toolCall.result.strengths" :key="'s-' + idx" class="quiz-detail-tag-item">
                                <view class="quiz-detail-dot strength-dot"></view>
                                <text class="quiz-detail-tag-text">{{ item }}</text>
                              </view>
                            </view>

                            <view v-if="seg.toolCall.result.weaknesses?.length" class="quiz-detail-subsection">
                              <text class="quiz-detail-subsection-title">不足</text>
                              <view v-for="(item, idx) in seg.toolCall.result.weaknesses" :key="'w-' + idx" class="quiz-detail-tag-item">
                                <view class="quiz-detail-dot weakness-dot"></view>
                                <text class="quiz-detail-tag-text">{{ item }}</text>
                              </view>
                            </view>
                          </view>

                          <view v-if="seg.toolCall.result.questions?.length" class="quiz-detail-questions-section">
                            <view class="quiz-detail-questions-header">
                              <text class="quiz-detail-section-title">题目详情</text>
                              <text class="quiz-detail-questions-count">{{ seg.toolCall.result.questions.length }} 题</text>
                            </view>
                            <view v-for="(question, idx) in seg.toolCall.result.questions" :key="'q-' + idx" class="quiz-detail-q-row">
                              <text class="quiz-detail-q-order">{{ question.order }}</text>
                              <view class="quiz-detail-q-status-dot" :class="'status-dot-' + question.status"></view>
                              <text class="quiz-detail-q-title">{{ question.title }}</text>
                              <text class="quiz-detail-q-score">{{ question.score }}</text>
                            </view>
                          </view>

                          <view class="quiz-detail-footer">
                            <text class="quiz-detail-footer-text">查看完整评估结果</text>
                            <text class="quiz-detail-footer-arrow">›</text>
                          </view>
                        </view>

                        <view
                          v-else-if="seg.toolCall.tool === 'view_quiz_attempt_detail' && seg.toolCall.status === 'done' && !seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="quiz-tool-empty"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <text class="quiz-tool-empty-text">{{ seg.toolCall.result?.message || '获取测验详情失败' }}</text>
                        </view>
                      </view>

                      <!-- Quiz generation -->
                      <view
                        v-else-if="seg.toolCall.tool === 'generate_test'"
                        class="quiz-tool-wrap"
                        :class="{ 'quiz-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id)) }"
                      >
                        <view
                          class="quiz-tool-pill"
                          :class="{
                            'quiz-tool-running': seg.toolCall.status === 'running',
                            'quiz-tool-done': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'quiz-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                          @click="toggleToolCardIfAllowed(seg.toolCall)"
                        >
                          <view class="quiz-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="quiz-tool-pill-text">{{ getQuizToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="quiz-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                        <view
                          v-if="seg.toolCall.status === 'done' && seg.toolCall.success && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <view
                            v-if="seg.toolCall.quizId"
                            class="quiz-entry-card"
                            @click="handleQuizEntryClick(seg.toolCall.quizId)"
                          >
                            <view class="quiz-entry-content">
                              <view class="quiz-entry-icon-wrap">
                                <view class="quiz-entry-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                              </view>
                              <view class="quiz-entry-text-col">
                                <text class="quiz-entry-title">测试题已生成</text>
                                <text class="quiz-entry-meta">点击进入测试</text>
                              </view>
                              <text class="quiz-entry-chevron">›</text>
                            </view>
                          </view>
                          <view v-else class="quiz-tool-empty">
                            <text class="quiz-tool-empty-text">{{ seg.toolCall.result?.message || '测试题生成完成' }}</text>
                          </view>
                        </view>
                      </view>

                      <!-- Note creation: rich card -->
                      <NoteCreationCard
                        v-else-if="seg.toolCall.tool === 'create_note'"
                        :tool-call="seg.toolCall"
                        :space-id="spaceId"
                        :conversation-id="conversationId"
                      />

                      <NoteDisplayCard
                        v-else-if="isNoteDisplayTool(seg.toolCall.tool)"
                        :tool-call="seg.toolCall"
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
                        class="chart-tool-wrap"
                        :class="{ 'chart-expanded-container': seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.image_url && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id)) }"
                      >
                        <view
                          class="graph-tool-pill"
                          :class="{
                            'graph-tool-running': seg.toolCall.status === 'running',
                            'graph-tool-success': seg.toolCall.status === 'done' && seg.toolCall.success,
                            'graph-tool-failed': seg.toolCall.status === 'done' && !seg.toolCall.success
                          }"
                          @click="toggleToolCardIfAllowed(seg.toolCall)"
                        >
                          <view class="graph-tool-pill-icon graph-tool-pill-icon-svg" v-html="getToolIconSvg(seg.toolCall.tool)"></view>
                          <text class="graph-tool-pill-text">{{ getChartToolText(seg.toolCall) }}</text>
                          <view v-if="seg.toolCall.status === 'running'" class="graph-tool-spinner"></view>
                          <text v-else-if="canToggleToolCard(seg.toolCall)" class="graph-tool-chevron" :class="{ 'graph-tool-chevron-up': isToolCardExpanded(seg.toolCall.id) }">⌄</text>
                          <svg v-else-if="seg.toolCall.status === 'done' && seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-success">
                            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                          <svg v-else-if="seg.toolCall.status === 'done' && !seg.toolCall.success" viewBox="0 0 256 256" class="graph-tool-status-icon tool-status-failed">
                            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
                        </view>

                        <view
                          v-if="seg.toolCall.status === 'done' && seg.toolCall.success && seg.toolCall.result?.image_url && (isToolCardExpanded(seg.toolCall.id) || isToolCardCollapsing(seg.toolCall.id))"
                          class="chart-detail-card"
                          :class="{ 'tool-card-leave': isToolCardCollapsing(seg.toolCall.id) }"
                        >
                          <view class="chart-image-preview">
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

                      <!-- Remaining tools -->
                      <AgentToolCard v-else :tool-call="withDefaultToolLabel(seg.toolCall)" />
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
              <view v-else class="chat-send-btn" :class="{ 'chat-send-btn-disabled': !canSend }" @tap="queueSendMessage">
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
import DocKgGenPanel from '@/components/study/DocKgGenPanel.vue'
import QuizPanel from '@/components/study/quiz/QuizPanel.vue'
import NotesPanel from '@/components/study/notes/NotesPanel.vue'
import NoteCreationCard from '@/components/study/notes/NoteCreationCard.vue'
import NoteDisplayCard from '@/components/study/notes/NoteDisplayCard.vue'
import ArtifactCreationCard from '@/components/study/notes/ArtifactCreationCard.vue'
import AgentThinkingBlock from '@/components/chat/AgentThinkingBlock.vue'
import AgentToolCard from '@/components/chat/AgentToolCard.vue'
import UModal from '@/components/u-modal/u-modal.vue'
import UMasteryToast from '@/components/u-mastery-toast/u-mastery-toast.vue'
import UQuizNotification from '@/components/u-quiz-notification/u-quiz-notification.vue'
import UArtifactNotification from '@/components/u-artifact-notification/u-artifact-notification.vue'
import { connectNotificationStream } from '@/api/notification'
import { getSpaces, deleteSpace, getTaskStatus, generateKnowledgeGraph, getToolCatalog, updateSpace, getSpace, generateShareCode, getSpaceMembers, removeSpaceMember, updateMemberPermission, getSpaceLeaderboard } from '@/api/space'
import { createConversation, getSpaceConversations, getConversation, sendMessage, submitToolResult, uploadAttachment, deleteAttachment, getModels } from '@/api/chat'
import { getCalendarEvents, createCalendarEvent, updateCalendarEvent, deleteCalendarEvent } from '@/api/calendar'
import { useUserStore } from '@/store/user'
import { useSpacesStore } from '@/store/spaces'
import config from '@/config'
import { getAgentMessageSegments } from '@/utils/agent-stream-segments'

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
  get_current_time: 'Get Current Time',
  get_schedule: 'View Schedule',
  add_schedule: 'Add Schedule',
  delete_schedule: 'Delete Schedule',
  update_schedule: 'Update Schedule',
  web_search: 'Web Search',
  web_fetch: 'Fetch Page',
  web_crawl: 'Deep Crawl',
  search_documents: 'Search Documents',
  generate_test: 'Generate Test',
  view_quiz_results: 'View Quiz Results',
  view_quiz_attempt_detail: 'View Quiz Analysis',
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
  save_to_knowledge_base: 'Save to Knowledge Base',
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

const GRAPH_QUERY_TOOLS = new Set(['get_child_nodes', 'get_parent_nodes', 'get_sibling_nodes'])
const LEARNING_PATH_TOOLS = new Set(['generate_learning_path', 'extend_learning_path', 'get_learning_paths', 'delete_all_learning_paths'])
const GRAPH_TOOLS = new Set([
  'get_graph_overview',
  ...GRAPH_MUTATING_TOOLS,
  ...GRAPH_QUERY_TOOLS,
  ...LEARNING_PATH_TOOLS,
  'get_postorder_traversal'
])

// Schedule/time tools (auto-executed on web)
const SCHEDULE_TOOLS = new Set(['get_current_time', 'get_schedule', 'add_schedule', 'delete_schedule', 'update_schedule'])
const REVIEW_TOOLS = new Set(['get_review_events', 'mark_review_completed'])
const DOC_RETRIEVAL_TOOLS = new Set(['search_documents', 'web_fetch'])
const SEARCH_TOOLS = new Set(['web_search', 'academic_search', 'encyclopedia_search', 'course_search', 'web_crawl'])
const NOTE_DISPLAY_TOOLS = new Set(['list_notes', 'view_note_detail', 'update_note', 'delete_note'])

const GRAPH_TOOL_TEXT = {
  get_graph_overview: { running: '正在查看知识图谱…', done: '已获取知识图谱', failed: '获取知识图谱失败' },
  add_node: { running: '正在添加节点…', done: '已添加节点', failed: '添加节点失败' },
  add_edge: { running: '正在连接节点…', done: '已连接节点', failed: '连接节点失败' },
  delete_node: { running: '正在删除节点…', done: '已删除节点', failed: '删除节点失败' },
  delete_edge: { running: '正在移除连接…', done: '已移除连接', failed: '移除连接失败' },
  update_mastery: { running: '正在更新掌握度…', done: '已更新掌握度', failed: '更新掌握度失败' },
  get_child_nodes: { running: '正在查找子节点…', done: '已找到子节点', failed: '查找子节点失败' },
  get_parent_nodes: { running: '正在查找父节点…', done: '已找到父节点', failed: '查找父节点失败' },
  get_sibling_nodes: { running: '正在查找兄弟节点…', done: '已找到兄弟节点', failed: '查找兄弟节点失败' },
  generate_learning_path: { running: '正在生成学习路径…', done: '已生成学习路径', failed: '生成学习路径失败' },
  extend_learning_path: { running: '正在延伸学习路径…', done: '已延伸学习路径', failed: '延伸学习路径失败' },
  get_learning_paths: { running: '正在读取学习路径…', done: '已读取学习路径', failed: '读取学习路径失败' },
  delete_all_learning_paths: { running: '正在清理学习路径…', done: '已清理学习路径', failed: '清理学习路径失败' },
  get_postorder_traversal: { running: '正在生成后序遍历…', done: '已生成后序遍历', failed: '生成后序遍历失败' }
}

const SCHEDULE_TOOL_TEXT = {
  get_current_time: { running: '正在获取当前时间…', done: '已获取当前时间', failed: '获取时间失败' },
  get_schedule: { running: '正在查看日程…', done: '已获取日程', failed: '获取日程失败' },
  add_schedule: { running: '正在添加日程…', done: '已添加日程', failed: '添加日程失败' },
  update_schedule: { running: '正在更新日程…', done: '已更新日程', failed: '更新日程失败' },
  delete_schedule: { running: '正在删除日程…', done: '已删除日程', failed: '删除日程失败' }
}

const REVIEW_TOOL_TEXT = {
  get_review_events: { running: '正在查看复习事项…', done: '已获取复习事项', failed: '获取复习事项失败' },
  mark_review_completed: { running: '正在标记已复习…', done: '已标记完成复习', failed: '标记复习失败' }
}

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
  time: '<svg viewBox="0 0 256 256" width="14" height="14"><polyline points="24 56 24 104 72 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M34.3,152A96,96,0,1,0,64,56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="128 80 128 128 160 144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  review: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-width="16"/><polyline points="128 80 128 128 168 152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  quiz: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M216,48H40A8,8,0,0,0,32,56V216a8,8,0,0,0,8,8H216a8,8,0,0,0,8-8V56A8,8,0,0,0,216,48ZM88,176a8,8,0,0,1-11.31,0l-24-24a8,8,0,0,1,11.31-11.31L88,164.69l40-40a8,8,0,0,1,11.31,11.31Zm0-64a8,8,0,0,1-11.31,0l-24-24a8,8,0,0,1,11.31-11.31L88,100.69l40-40a8,8,0,0,1,11.31,11.31Z" fill="currentColor"/></svg>',
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
  get_current_time: 'time',
  get_schedule: 'calendar', add_schedule: 'calendar',
  delete_schedule: 'calendar', update_schedule: 'calendar',
  generate_test: 'quiz',
  view_quiz_results: 'quiz',
  view_quiz_attempt_detail: 'quiz',
  web_search: 'search', web_fetch: 'search', web_crawl: 'search', search_documents: 'search',
  write_to_long_term_memory: 'memory', delete_from_long_term_memory: 'memory',
  write_to_space_memory: 'memory', delete_from_space_memory: 'memory',
  get_review_events: 'review', mark_review_completed: 'review',
  create_note: 'note', list_notes: 'note', view_note_detail: 'note',
  update_note: 'note', delete_note: 'note',
  generate_chart: 'image', save_to_knowledge_base: 'note',
  annotate_panel: 'default',
  run_python_code: 'code'
}

const DEFAULT_BROWSER_URL = 'https://www.wikipedia.org'
const BROWSER_LOAD_TIMEOUT_MS = 8000

export default {
  components: { HomeSidebar, KnowledgeGraph, MarkdownRender, StudyMaterialsPanel, DocKgGenPanel, QuizPanel, NotesPanel, NoteCreationCard, NoteDisplayCard, ArtifactCreationCard, AgentThinkingBlock, AgentToolCard, UModal, UMasteryToast, UQuizNotification, UArtifactNotification },
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
      latestInputValue: '',
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
      expandedToolCards: {},
      collapsingToolCards: {},

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
      isPendingSendFlush: false,
      chatInputResizeFrame: null,

      // Knowledge graph generation polling
      graphTaskId: null,
      graphGenerating: false,
      _abortGraphPoll: false,

      // Document-based KG generation mode
      docKgMode: false,
      docKgDocIds: [],
      docKgCompleted: false,

      // Dual-sync mode
      dualSyncEnabled: false,
      annotations: [],

      // Collaborative space state
      isCollaborative: false,
      userRole: null,
      spaceMembers: [],
      selectedMemberUserId: null,
      showMemberDropdown: false,
      currentUserId: null,
      leaderboardData: [],
      leaderboardLoading: false
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
      return this.visibleTabs.find(t => t.id === this.activeTab) || this.tabs[0]
    },
    visibleTabs() {
      if (this.isCollaborative) {
        const extra = [{ id: 'leaderboard', label: '排行榜' }]
        if (this.userRole === 'owner') {
          extra.push({ id: 'manage', label: '成员管理' })
        }
        return [...this.tabs, ...extra]
      }
      return this.tabs
    },
    currentUserTier() {
      return 'ALPHA'
    },
    canBrowserBack() {
      return this.browserHistoryIndex > 0
    },
    canBrowserForward() {
      return this.browserHistoryIndex < this.browserHistory.length - 1
    },
    canSend() {
      return this.spaceId && this.getCurrentInputValue().trim().length > 0 && !this.isSending && !this.isPendingSendFlush
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
    canEditGraph() {
      if (!this.isCollaborative || this.userRole === 'owner') return true
      const self = this.spaceMembers.find(
        m => String(m.user_id) === String(this.currentUserId || '')
      )
      return !!self?.can_edit_graph
    },
    isForeignGraphView() {
      return !!this.selectedMemberUserId && String(this.selectedMemberUserId) !== String(this.currentUserId || '')
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
      // Document-based KG generation mode
      if (options.docKgMode === '1' && options.docKgDocIds) {
        this.docKgMode = true
        this.docKgDocIds = options.docKgDocIds.split(',')
        this.graphGenerating = true
      }
      await this.loadSpaceInfo()
      this.loadSpaceToolMode()
      this.initConversation()
      if (options.quizId) {
        this.activeTab = 'quizzes'
        this.$nextTick(() => this.handleQuizEntryClick(options.quizId))
      }
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
    this.latestInputValue = this.inputText
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
    this.clearPendingChatInputResize()
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
        onAssignmentGraded: (data) => this.onAssignmentGradeNotification(data),
        onAssignmentGradeUpdated: (data) => this.onAssignmentGradeNotification(data),
        onLearningPathExpanded: (data) => this.onLearningPathExpanded(data),
        onArtifactStream: (data) => this.onArtifactStream(data),
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

    onAssignmentGradeNotification(data) {
      const assignmentId = data.assignment_id || data.id
      if (!assignmentId) return
      const score = data.final_score ?? data.provisional_score ?? data.score ?? 0
      const totalScore = data.total_score ?? 0
      this.quizNotificationIdCounter++
      const id = this.quizNotificationIdCounter
      const index = this.quizEvaluationNotifications.length
      this.quizEvaluationNotifications = [
        ...this.quizEvaluationNotifications,
        {
          id,
          visible: true,
          itemKind: 'assignment',
          assignmentId,
          quizTopic: data.title || data.assignment_title || '教师作业',
          score: Number(score),
          totalScore: Number(totalScore),
          status: data.status || 'completed',
          index
        }
      ]

      if (this.activeTab === 'quizzes' && this.$refs.quizPanel) {
        this.$refs.quizPanel.loadQuizzes()
      }
    },

    handleQuizNotificationClick(notification) {
      this.removeQuizNotification(notification.id)
      this.activeTab = 'quizzes'
      this.$nextTick(() => {
        if (this.$refs.quizPanel) {
          if (notification.itemKind === 'assignment') {
            this.$refs.quizPanel.navigateToAssignmentResult(notification.assignmentId)
          } else {
            this.$refs.quizPanel.navigateToQuizResult(notification.quizId)
          }
        }
      })
    },

    removeQuizNotification(id) {
      this.quizEvaluationNotifications = this.quizEvaluationNotifications.filter(n => n.id !== id)
    },

    // ==================== Artifact Notifications ====================
    walkArtifactToolCalls(visitor) {
      for (const msg of this.messages) {
        for (const segmentKey of ['segments', 'streamSegments']) {
          const segments = msg[segmentKey]
          if (!Array.isArray(segments)) continue
          for (let index = 0; index < segments.length; index++) {
            const seg = segments[index]
            if (seg?.type === 'tool' && (seg.toolCall?.tool === 'create_artifact' || seg.toolCall?.tool === 'update_artifact')) {
              if (visitor(seg, msg, segmentKey, index)) return true
            }
          }
        }
      }
      return false
    },

    applyArtifactSnapshot(payload, { appendDelta = false } = {}) {
      const { taskId, noteId, title, status, delta, codeSnapshot, htmlSize, errorMessage } = payload
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
          if (!nextResult.title) nextResult.title = title
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
        if (typeof htmlSize === 'number') nextResult.html_size = htmlSize
        if (errorMessage) nextResult.message = errorMessage

        seg.toolCall = { ...seg.toolCall, result: nextResult }
        updated = true
        return true
      })

      if (updated) this.$forceUpdate()
      return updated
    },

    async refreshArtifactTaskSnapshot(taskId) {
      if (!taskId) return null
      try {
        const taskResult = await getTaskStatus(taskId)
        if (taskResult.task_type !== 'generate_artifact') return taskResult
        const resolvedStatus = taskResult.artifact_progress_status
          || (taskResult.status === 'failed' ? 'failed' : taskResult.status === 'done' ? 'done' : 'streaming')
        this.applyArtifactSnapshot({
          taskId,
          noteId: taskResult.note_id,
          title: taskResult.artifact_title,
          status: resolvedStatus,
          codeSnapshot: typeof taskResult.code_snapshot === 'string' ? taskResult.code_snapshot : undefined,
          htmlSize: typeof taskResult.html_size === 'number' ? taskResult.html_size : undefined,
          errorMessage: taskResult.error_message || ''
        })
        return taskResult
      } catch (error) {
        return null
      }
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
      const { note_id, space_id, task_id, status, title, error_message } = data
      if (String(space_id) !== String(this.spaceId)) return

      // Try to get final snapshot from backend (includes full code)
      const refreshed = task_id ? await this.refreshArtifactTaskSnapshot(task_id) : null
      if (!refreshed) {
        this.applyArtifactSnapshot({
          taskId: task_id,
          noteId: note_id,
          title,
          status,
          errorMessage: error_message || ''
        })
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

    // ==================== Document KG Generation Events ====================
    handleDocKgNode(nodeData) {
      if (this.$refs.knowledgeGraph) {
        this.$refs.knowledgeGraph.addIncrementalNode(nodeData)
      }
    },
    handleDocKgEdge(edgeData) {
      if (this.$refs.knowledgeGraph) {
        this.$refs.knowledgeGraph.addIncrementalEdge(edgeData)
      }
    },
    handleDocKgDone({ nodeCount, edgeCount }) {
      this.graphGenerating = false
      this.docKgCompleted = true
      // Reload the full graph from DB after persistence
      setTimeout(() => {
        if (this.$refs.knowledgeGraph) {
          this.$refs.knowledgeGraph.loadAndRender()
        }
      }, 1500)
    },
    handleDocKgError(message) {
      this.graphGenerating = false
      this.docKgCompleted = true
    },

    // ==================== Model Selection ====================
    toggleModelMenu() {
      this.showModelMenu = !this.showModelMenu
    },
    selectModel(id) {
      const model = this.availableModels.find(m => m.id === id)
      if (model?.locked) {
        uni.showToast({ title: '实验账号权限异常，请联系管理员', icon: 'none' })
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

    getCurrentInputValue() {
      return typeof this.latestInputValue === 'string'
        ? this.latestInputValue
        : (typeof this.inputText === 'string' ? this.inputText : '')
    },

    syncTextareaValueFromDom() {
      const inputEl = this.getChatInputElement()
      const domValue = inputEl && typeof inputEl.value === 'string'
        ? inputEl.value
        : null
      const nextValue = typeof domValue === 'string'
        ? domValue
        : (typeof this.inputText === 'string' ? this.inputText : '')
      if (nextValue !== this.inputText) {
        this.inputText = nextValue
      }
      this.latestInputValue = nextValue
      return nextValue
    },

    clearPendingChatInputResize() {
      if (
        this.chatInputResizeFrame &&
        typeof window !== 'undefined' &&
        typeof window.cancelAnimationFrame === 'function'
      ) {
        window.cancelAnimationFrame(this.chatInputResizeFrame)
      }
      this.chatInputResizeFrame = null
    },

    scheduleChatInputHeightUpdate() {
      this.clearPendingChatInputResize()
      if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
        this.$nextTick(() => this.recalcChatInputHeight())
        return
      }
      this.chatInputResizeFrame = window.requestAnimationFrame(() => {
        this.chatInputResizeFrame = null
        this.recalcChatInputHeight()
      })
    },

    applyResolvedChatInputHeight(height, force = false) {
      const nextHeight = Math.max(this.chatInputMinHeight, Math.min(height, this.chatInputMaxHeight))
      if (!force && this.chatInputHeight === nextHeight) {
        return
      }
      this.chatInputHeight = nextHeight
      this.applyChatInputDomStyle(nextHeight)
    },

    handleChatInput(event) {
      const nextValue = typeof event?.detail?.value === 'string' ? event.detail.value : ''
      if (nextValue !== this.inputText) {
        this.inputText = nextValue
      }
      this.latestInputValue = nextValue
      if (!nextValue) {
        this.resetChatInputHeight()
      }
    },

    handleChatLineChange(event) {
      const rawLineCount = Number(event?.detail?.lineCount)
      if (!Number.isFinite(rawLineCount)) {
        this.scheduleChatInputHeightUpdate()
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
        inputEl.style.setProperty('height', 'auto', 'important')
        const hostEl = this.getChatInputHostElement()
        const structuralPadding = inputEl !== hostEl ? this.chatInputVerticalPadding : 0
        const measuredNeeded = Math.ceil(inputEl.scrollHeight) + structuralPadding + this.chatInputMultiLineCompensation
        inputEl.style.removeProperty('height')
        nextHeight = Math.max(nextHeight, measuredNeeded)
      }
      this.applyResolvedChatInputHeight(nextHeight)
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
      this.queueSendMessage()
    },

    insertChatNewlineAtCursor() {
      const inputEl = this.getChatInputElement()
      const currentValue = this.syncTextareaValueFromDom()
      let start = currentValue.length
      let end = currentValue.length
      if (inputEl && typeof inputEl.selectionStart === 'number' && typeof inputEl.selectionEnd === 'number') {
        start = inputEl.selectionStart
        end = inputEl.selectionEnd
      }

      const nextValue = `${currentValue.slice(0, start)}\n${currentValue.slice(end)}`
      this.inputText = nextValue
      this.latestInputValue = nextValue
      this.$nextTick(() => {
        const latestInput = this.getChatInputElement()
        if (latestInput) {
          if (typeof latestInput.focus === 'function') latestInput.focus()
          if (typeof latestInput.setSelectionRange === 'function') {
            const cursor = start + 1
            latestInput.setSelectionRange(cursor, cursor)
          }
        }
        this.scheduleChatInputHeightUpdate()
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
      this.queueSendMessage()
    },

    handleChatKeydown(event) {
      const nativeEvent = event?.originalEvent
      if (nativeEvent) {
        this.handleNativeChatKeydown(nativeEvent)
      }
    },

    recalcChatInputHeight() {
      this.clearPendingChatInputResize()
      const minHeight = this.chatInputMinHeight
      const maxHeight = this.chatInputMaxHeight
      if (!this.getCurrentInputValue()) {
        this.applyResolvedChatInputHeight(minHeight)
        return
      }

      const inputEl = this.getChatInputElement()
      if (!inputEl || typeof inputEl.scrollHeight !== 'number') {
        this.applyResolvedChatInputHeight(minHeight)
        return
      }

      inputEl.style.setProperty('height', 'auto', 'important')
      const measured = Math.ceil(inputEl.scrollHeight || minHeight)
      inputEl.style.removeProperty('height')
      const hostEl = this.getChatInputHostElement()
      const structuralPadding = inputEl !== hostEl ? this.chatInputVerticalPadding : 0
      const measuredHeight = Math.max(minHeight, measured + structuralPadding + this.chatInputMultiLineCompensation)
      const wrapTriggerHeight = minHeight + this.chatInputLineHeight * 0.7
      if (measuredHeight <= wrapTriggerHeight) {
        this.applyResolvedChatInputHeight(minHeight)
        return
      }

      this.applyResolvedChatInputHeight(Math.min(maxHeight, measuredHeight))
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
        inputEl.style.setProperty('overflow-y', height >= maxHeight ? 'auto' : 'hidden', 'important')
      }

      if (inputEl && typeof inputEl.scrollTop === 'number' && height < maxHeight) {
        inputEl.scrollTop = 0
      }
    },

    resetChatInputHeight() {
      this.clearPendingChatInputResize()
      this.applyResolvedChatInputHeight(this.chatInputMinHeight)
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
          this.leaderboardData = []
          if (this.activeTab === 'manage' || this.activeTab === 'leaderboard') {
            this.activeTab = 'graph'
          }
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

    async loadLeaderboard() {
      if (!this.spaceId || this.leaderboardLoading) return
      this.leaderboardLoading = true
      try {
        const res = await getSpaceLeaderboard(this.spaceId)
        this.leaderboardData = res.data || res || []
      } catch (e) {
        console.error('Failed to load leaderboard:', e)
        this.leaderboardData = []
      } finally {
        this.leaderboardLoading = false
      }
    },

    selectMemberFilter(member) {
      this.selectedMemberUserId = member.user_id
      this.showMemberDropdown = false
      // loadAndRender() is triggered by the targetUserId watcher in KnowledgeGraph
    },

    async handleToggleGraphEdit(member, event) {
      const newVal = event.detail.value
      try {
        await updateMemberPermission(this.spaceId, member.user_id, { can_edit_graph: newVal })
        member.can_edit_graph = newVal
      } catch (e) {
        member.can_edit_graph = !newVal
      }
    },

    async handleRemoveMember(member) {
      if (!confirm(`确定要移除 ${member.nickname} 吗？`)) return
      try {
        await removeSpaceMember(this.spaceId, member.user_id)
        this.spaceMembers = this.spaceMembers.filter(m => m.user_id !== member.user_id)
      } catch (e) {
        console.error('Failed to remove member:', e)
      }
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
      if (tabId === 'leaderboard') {
        this.loadLeaderboard()
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
      this.latestInputValue = ''
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
      // 没有学习路径时，弹窗引导生成
      const graphRef = this.$refs.knowledgeGraph
      const hasPath = graphRef && graphRef.learningPath && graphRef.learningPath.length > 0
      if (!this.isPathHighlightOn && !hasPath) {
        uni.showModal({
          title: '提示',
          content: '暂无学习路径，是否需要生成学习路径？',
          confirmText: '确认',
          cancelText: '取消',
          success: (res) => {
            if (res.confirm) {
              this.inputText = '结合我的学习资料，学习偏好，以及学习目标，为我规划一条符合我需求的学习路径'
              this.latestInputValue = this.inputText
              this.$nextTick(() => this.queueSendMessage())
            }
          }
        })
        return
      }
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
      this.latestInputValue = this.inputText
      this.$nextTick(() => this.queueSendMessage())
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

    async queueSendMessage(event) {
      if (typeof event?.preventDefault === 'function') {
        event.preventDefault()
      }
      if (typeof event?.stopPropagation === 'function') {
        event.stopPropagation()
      }
      if (this.isPendingSendFlush || this.isSending) return

      this.isPendingSendFlush = true
      try {
        await new Promise(resolve => this.$nextTick(resolve))
        if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
          await new Promise(resolve => window.requestAnimationFrame(() => resolve()))
        }
        this.syncTextareaValueFromDom()
        await this.performSendMessage()
      } finally {
        this.isPendingSendFlush = false
      }
    },

    async handleSend(event) {
      return this.queueSendMessage(event)
    },

    async performSendMessage() {
      const text = this.getCurrentInputValue().trim()
      if (!text || !this.spaceId || this.isSending) return

      if (this.pendingAttachments.some(a => a.uploading)) {
        uni.showToast({ title: '附件上传中，请稍候', icon: 'none' })
        return
      }

      this.isSending = true
      this.isAutoScrollEnabled = true
      this.inputText = ''
      this.latestInputValue = ''
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
          const shortText = info.code === 'DAILY_MESSAGE_QUOTA_EXCEEDED' ? '今日消息已用完' : '配额已达上限'
          uni.showModal({
            title: '配额已达上限',
            content: info.message || '实验账号权限异常，请联系管理员',
            confirmText: '知道了',
            showCancel: false
          })
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            aiMsg.content = shortText
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
        let localResult = null

        if (tool === 'get_current_time') {
          const now = new Date()
          const pad = (value) => String(value).padStart(2, '0')
          const weekdayMap = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
          localResult = {
            current_time: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`,
            weekday: weekdayMap[now.getDay()],
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
          }
        } else if (tool === 'get_schedule') {
          const startDate = params.start_date || new Date().toISOString().split('T')[0]
          const endDate = params.end_date || new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
          const events = await getCalendarEvents(startDate + 'T00:00:00', endDate + 'T23:59:59')
          localResult = {
            events: Array.isArray(events) ? events : [],
            date_range: `${startDate} ~ ${endDate}`,
            message: (!events || events.length === 0) ? '该时间范围内没有日程安排。' : ''
          }
        } else if (tool === 'add_schedule') {
          const event = await createCalendarEvent({
            title: params.title,
            start_time: params.start_time || params.begin_time,
            end_time: params.end_time,
            details: params.description || params.details || null,
            source_conversation_id: this.conversationId || null
          })
          localResult = {
            ...event,
            message: `日程已添加：${event.title}`
          }
        } else if (tool === 'delete_schedule') {
          const eventId = params.event_id || params.id
          if (eventId) {
            await deleteCalendarEvent(eventId)
            localResult = {
              deleted_id: eventId,
              title: params.title || '',
              message: '日程已删除。'
            }
          } else {
            throw new Error('未提供要删除的日程 ID。')
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
            localResult = {
              ...event,
              message: `日程已更新：${event.title}`
            }
          } else {
            throw new Error('未提供要更新的日程 ID。')
          }
        }

        updateToolCallStatus('done', true, localResult)

        if (this.conversationId) {
          submitToolResult(this.conversationId, {
            tool_call_id: toolCallId,
            result: localResult,
            success: true
          }).catch(() => {})
        }
      } catch (err) {
        const errMsg = err.message || '日程操作失败'
        updateToolCallStatus('done', false, { message: errMsg })

        if (this.conversationId) {
          submitToolResult(this.conversationId, {
            tool_call_id: toolCallId,
            success: false,
            error: errMsg
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
        if (!this.$refs.quizPanel) return
        if (quizId && typeof this.$refs.quizPanel.handleOpenQuiz === 'function') {
          this.$refs.quizPanel.handleOpenQuiz({
            id: quizId,
            has_attempt: false,
            attempt_status: 'not_started'
          })
          return
        }
        if (typeof this.$refs.quizPanel.loadQuizzes === 'function') {
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
      return getAgentMessageSegments(msg, this.activeToolCalls)
    },

    buildStreamingSegments(msg) {
      return getAgentMessageSegments({ ...msg, isStreaming: true }, this.activeToolCalls)
    },

    withDefaultToolLabel(toolCall) {
      const label = this.isDocRetrievalTool(toolCall.tool)
        ? this.getDocRetrievalToolText(toolCall)
        : toolCall.tool === 'save_to_knowledge_base'
          ? this.getKBToolText(toolCall)
          : this.getToolDisplayName(toolCall.tool)
      return { ...toolCall, label }
    },

    getToolDisplayName(toolName) {
      return TOOL_DISPLAY_NAMES[toolName] || toolName
    },

    getToolIconSvg(toolName) {
      const category = TOOL_ICON_MAP[toolName] || 'default'
      return TOOL_ICON_SVGS[category] || TOOL_ICON_SVGS.default
    },

    getToolIconBgClass(toolName) {
      if (toolName === 'delete_node' || toolName === 'delete_edge') return 'gm-icon-delete'
      if (toolName === 'update_mastery') return 'gm-icon-update'
      if (toolName === 'get_child_nodes' || toolName === 'get_parent_nodes' || toolName === 'get_sibling_nodes') return 'gm-icon-query'
      if (toolName === 'generate_learning_path') return 'gm-icon-path-generate'
      if (toolName === 'extend_learning_path' || toolName === 'get_learning_paths' || toolName === 'delete_all_learning_paths') return 'gm-icon-path-modify'
      if (toolName === 'get_postorder_traversal') return 'gm-icon-postorder'
      return 'gm-icon-add'
    },

    getToolCardClass(toolCall) {
      if (toolCall.status === 'running') return 'tool-call-running'
      if (toolCall.status === 'done' && toolCall.success) return 'tool-call-success'
      if (toolCall.status === 'done' && !toolCall.success) return 'tool-call-failed'
      return 'tool-call-running'
    },

    isToolOnlyMessage(msg) {
      if (!msg || msg.thinkingContent) return false
      const segments = this.getMessageSegments(msg)
      if (!segments.length) return false
      return !segments.some(seg => seg.type === 'text' && seg.content && seg.content.trim())
    },

    isGraphTool(toolName) {
      return GRAPH_TOOLS.has(toolName)
    },

    isGraphOverviewTool(toolName) {
      return toolName === 'get_graph_overview'
    },

    isGraphDetailTool(toolName) {
      return GRAPH_MUTATING_TOOLS.has(toolName)
        || GRAPH_QUERY_TOOLS.has(toolName)
        || LEARNING_PATH_TOOLS.has(toolName)
        || toolName === 'get_postorder_traversal'
    },

    getGraphToolText(toolCall) {
      const texts = GRAPH_TOOL_TEXT[toolCall.tool]
      if (!texts) return this.getToolDisplayName(toolCall.tool)
      if (toolCall.status === 'running') return texts.running
      if (toolCall.status === 'done' && toolCall.success) return texts.done
      return texts.failed
    },

    getGraphStats() {
      const graphRef = this.$refs.knowledgeGraph
      const nodes = Array.isArray(graphRef?.nodes) ? graphRef.nodes.length : 0
      const edges = Array.isArray(graphRef?.edges) ? graphRef.edges.length : 0
      return { nodes, edges }
    },

    getGraphOverviewTitle(toolCall) {
      if (toolCall.result?.title) return toolCall.result.title
      return '当前知识图谱'
    },

    getGraphOverviewMeta() {
      const { nodes, edges } = this.getGraphStats()
      if (nodes || edges) return `${nodes} 个节点 · ${edges} 条连接`
      return '已同步到左侧知识图谱'
    },

    getGraphOverviewLines(toolCall) {
      const { nodes, edges } = this.getGraphStats()
      const lines = []
      if (nodes || edges) {
        lines.push(`知识图谱当前包含 ${nodes} 个知识点与 ${edges} 条连接。`)
      } else {
        lines.push('知识图谱已同步到左侧画布，可直接查看最新结构。')
      }
      if (toolCall.result?.message) lines.push(toolCall.result.message)
      lines.push('继续在聊天中追问节点、路径或掌握度变化。')
      return lines.slice(0, 3)
    },

    getGraphCardTitle(toolCall) {
      const args = toolCall.arguments || {}
      const result = toolCall.result || {}
      switch (toolCall.tool) {
        case 'add_node':
          return `已添加节点: ${result.label || args.label || args.node_name || '未命名节点'}`
        case 'add_edge':
          return `已连接: ${result.from_node || args.from_node || args.source || '节点'} → ${result.to_node || args.to_node || args.target || '节点'}`
        case 'delete_node':
          return `已删除节点: ${result.deleted_node_name || args.node_name || '目标节点'}`
        case 'delete_edge':
          return `已移除连接: ${result.from_node || args.from_node || '节点'} ↔ ${result.to_node || args.to_node || '节点'}`
        case 'update_mastery':
          return `${result.node_name || args.node_name || '节点'} 掌握度已更新`
        case 'get_child_nodes':
          return `${args.node_name || '目标节点'} 的子节点`
        case 'get_parent_nodes':
          return `${args.node_name || '目标节点'} 的父节点`
        case 'get_sibling_nodes':
          return `${args.node_name || '目标节点'} 的兄弟节点`
        case 'generate_learning_path':
          return '已生成学习路径'
        case 'extend_learning_path':
          return '已延伸学习路径'
        case 'get_learning_paths':
          return '已读取学习路径'
        case 'delete_all_learning_paths':
          return '已清理学习路径'
        case 'get_postorder_traversal':
          return `${args.node_name || '目标节点'} 的后序遍历`
        default:
          return this.getToolDisplayName(toolCall.tool)
      }
    },

    getGraphCardMeta() {
      const { nodes, edges } = this.getGraphStats()
      if (nodes || edges) return `${nodes} 个节点 · ${edges} 条连接`
      return '知识图谱已更新'
    },

    getGraphToolHighlights(toolCall) {
      const args = toolCall.arguments || {}
      const result = toolCall.result || {}
      const candidates = []
      switch (toolCall.tool) {
        case 'add_node':
          candidates.push(result.label, args.label, args.node_name)
          break
        case 'add_edge':
        case 'delete_edge':
          candidates.push(result.from_node, result.to_node, args.from_node, args.to_node, args.source, args.target)
          break
        case 'delete_node':
          candidates.push(result.deleted_node_name, args.node_name)
          break
        case 'update_mastery':
          candidates.push(result.node_name, args.node_name)
          break
        case 'get_child_nodes':
        case 'get_parent_nodes':
        case 'get_sibling_nodes':
          candidates.push(args.node_name)
          if (Array.isArray(result.nodes)) {
            candidates.push(...result.nodes.map(item => item?.label || item?.name || item))
          }
          break
        case 'generate_learning_path':
        case 'extend_learning_path':
        case 'get_learning_paths':
        case 'delete_all_learning_paths':
          if (Array.isArray(result.path)) candidates.push(...result.path)
          if (Array.isArray(args.node_sequence)) candidates.push(...args.node_sequence)
          break
        case 'get_postorder_traversal':
          candidates.push(args.node_name)
          if (typeof result === 'string') candidates.push(...result.split('->'))
          break
      }
      return [...new Set(candidates.filter(item => typeof item === 'string' && item.trim()))].slice(0, 6)
    },

    getGraphCardBody(toolCall) {
      const result = toolCall.result || {}
      if (toolCall.tool === 'get_postorder_traversal' && typeof result === 'string' && result.trim()) {
        const items = result.split('->').filter(Boolean)
        return items.length ? `遍历顺序：${items.join(' → ')}` : '后序遍历已完成。'
      }
      if (toolCall.tool === 'get_learning_paths' && Array.isArray(result.paths)) {
        return result.paths.length ? `共读取 ${result.paths.length} 条学习路径。` : '当前没有可用学习路径。'
      }
      if (toolCall.tool === 'delete_all_learning_paths') {
        return result.message || '所有学习路径已从图谱中移除。'
      }
      if (typeof result?.message === 'string' && result.message.trim()) return result.message
      return '左侧知识图谱已经同步更新。'
    },

    isScheduleTool(toolName) {
      return SCHEDULE_TOOLS.has(toolName)
    },

    isScheduleDetailTool(toolName) {
      return toolName === 'get_schedule' || toolName === 'add_schedule' || toolName === 'update_schedule'
    },

    getScheduleToolText(toolCall) {
      const texts = SCHEDULE_TOOL_TEXT[toolCall.tool]
      if (!texts) return this.getToolDisplayName(toolCall.tool)
      if (toolCall.status === 'running') return texts.running
      if (toolCall.status === 'done' && toolCall.success) {
        if (toolCall.tool === 'get_current_time' && toolCall.result?.current_time) {
          const timestamp = String(toolCall.result.current_time)
          const shortText = timestamp.length >= 16 ? timestamp.slice(5, 16) : timestamp
          const weekday = toolCall.result.weekday || ''
          return `${texts.done} · ${shortText}${weekday ? ' ' + weekday : ''}`
        }
        if (toolCall.tool === 'get_schedule') {
          const count = this.getScheduleDisplayEvents(toolCall).length
          return count ? `${texts.done} · ${count} 个日程` : texts.done
        }
        return texts.done
      }
      return texts.failed
    },

    getScheduleDisplayEvents(toolCall) {
      const result = toolCall.result
      if (!result) return []
      if (Array.isArray(result.events)) return result.events
      if (Array.isArray(result?.data?.events)) return result.data.events
      if (result.start_time) {
        return [{
          id: result.id || result.updated_id || '',
          title: result.title || '未命名日程',
          start_time: result.start_time,
          end_time: result.end_time || result.start_time,
          details: result.details || ''
        }]
      }
      return []
    },

    groupScheduleByDate(events) {
      if (!events || !events.length) return []
      const today = new Date()
      const todayText = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
      const weekdayMap = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
      const barColors = ['rgba(74, 108, 247, 0.8)', 'rgba(232, 168, 56, 0.82)', 'rgba(94, 194, 105, 0.82)', 'rgba(129, 140, 248, 0.82)']
      const groups = new Map()
      let colorIndex = 0

      for (const event of events) {
        const dateKey = event?.start_time ? String(event.start_time).slice(0, 10) : 'unknown'
        if (!groups.has(dateKey)) {
          const dateObj = dateKey === 'unknown' ? new Date() : new Date(dateKey.replace(/-/g, '/'))
          const month = dateObj.getMonth() + 1
          const day = dateObj.getDate()
          const weekday = weekdayMap[dateObj.getDay()]
          const isToday = dateKey === todayText
          groups.set(dateKey, {
            date: dateKey,
            label: `${month}月${day}日 ${weekday}${isToday ? ' · 今天' : ''}`,
            isToday,
            events: []
          })
        }
        groups.get(dateKey).events.push({
          ...event,
          startShort: event?.start_time ? String(event.start_time).slice(11, 16) : '--:--',
          endShort: event?.end_time ? String(event.end_time).slice(11, 16) : '--:--',
          barColor: barColors[colorIndex % barColors.length]
        })
        colorIndex += 1
      }

      return [...groups.values()].sort((a, b) => a.date.localeCompare(b.date))
    },

    isReviewTool(toolName) {
      return REVIEW_TOOLS.has(toolName)
    },

    getReviewToolText(toolCall) {
      const texts = REVIEW_TOOL_TEXT[toolCall.tool]
      if (!texts) return this.getToolDisplayName(toolCall.tool)
      if (toolCall.status === 'running') return texts.running
      if (toolCall.status === 'done' && toolCall.success) {
        if (toolCall.tool === 'get_review_events') {
          const total = this.getReviewDisplayItems(toolCall).length
          return total ? `${texts.done} · ${total} 条待复习` : texts.done
        }
        return texts.done
      }
      return texts.failed
    },

    getReviewDisplayItems(toolCall) {
      if (!toolCall?.result) return []
      return Array.isArray(toolCall.result.items) ? toolCall.result.items : []
    },

    isSearchTool(toolName) {
      return SEARCH_TOOLS.has(toolName)
    },

    getSearchToolResults(toolCall) {
      if (Array.isArray(toolCall?.result?.results)) return toolCall.result.results
      if (Array.isArray(toolCall?.result?.pages)) return toolCall.result.pages
      return []
    },

    getSearchToolText(toolCall) {
      if (toolCall.status === 'running') return `${this.getToolDisplayName(toolCall.tool)}...`
      const count = this.getSearchToolResults(toolCall).length
      if (toolCall.status === 'done' && toolCall.success) return `已搜索 ${count} 个来源`
      return toolCall.result?.message || `${this.getToolDisplayName(toolCall.tool)} 失败`
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

    getVisibleSearchResults(toolCall) {
      const results = this.getSearchToolResults(toolCall)
      if (this.expandedSearchResults[toolCall.id]) return results
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

    isDocRetrievalTool(toolName) {
      return DOC_RETRIEVAL_TOOLS.has(toolName)
    },

    isNoteDisplayTool(toolName) {
      return NOTE_DISPLAY_TOOLS.has(toolName)
    },

    isQuizResultTool(toolName) {
      return toolName === 'view_quiz_results' || toolName === 'view_quiz_attempt_detail'
    },

    getDocRetrievalToolText(toolCall) {
      if (toolCall.status === 'running') return '正在检索学习资料…'
      if (toolCall.status === 'done' && toolCall.success) return '已完成资料检索'
      return '资料检索失败'
    },

    getKBToolText(toolCall) {
      if (toolCall.status === 'running') return '正在保存到知识库…'
      if (toolCall.status === 'done' && toolCall.success) {
        const title = toolCall.result?.data?.title || toolCall.arguments?.title
        return title ? `已保存「${title}」` : '已保存到知识库'
      }
      return '保存到知识库失败'
    },

    getChartToolText(toolCall) {
      if (toolCall.status === 'running') return '正在生成图表…'
      if (toolCall.status === 'done' && toolCall.success) {
        return toolCall.result?.auto_saved ? '图表已生成并保存' : '图表已生成'
      }
      return '图表生成失败'
    },

    getQuizToolText(toolCall) {
      if (toolCall.tool === 'view_quiz_results') {
        if (toolCall.status === 'running') return '正在查询测验成绩…'
        if (toolCall.status === 'done' && toolCall.success) {
          return `已查询 ${this.getQuizResultList(toolCall).length} 份测验`
        }
        return toolCall.result?.message || '查询测验成绩失败'
      }
      if (toolCall.tool === 'view_quiz_attempt_detail') {
        if (toolCall.status === 'running') return '正在分析测验详情…'
        if (toolCall.status === 'done' && toolCall.success) return '测验分析完成'
        return toolCall.result?.message || '测验分析失败'
      }
      if (toolCall.status === 'running') return '正在生成测试题…'
      if (toolCall.status === 'done' && toolCall.success) {
        return toolCall.quizId ? '测试题已生成' : (toolCall.result?.message || '测试题生成完成')
      }
      return toolCall.result?.message || '测试题生成失败'
    },

    getQuizResultList(toolCall) {
      if (Array.isArray(toolCall?.result?.quizzes)) return toolCall.result.quizzes
      if (Array.isArray(toolCall?.result?.data?.quizzes)) return toolCall.result.data.quizzes
      return []
    },

    getDifficultyLabel(difficulty) {
      return { easy: '简单', medium: '中等', hard: '困难' }[difficulty] || difficulty || '未知'
    },

    getQuizClickAction(quiz) {
      if (!quiz) return 'disabled'
      if (quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating') return 'disabled'
      if (quiz.attempt_status === 'in_progress') return 'take_quiz'
      if (quiz.has_attempt) return 'view_result'
      return 'take_quiz'
    },

    onQuizItemClick(quiz) {
      const action = this.getQuizClickAction(quiz)
      if (action === 'disabled') return
      this.activeTab = 'quizzes'
      this.$nextTick(() => {
        if (!this.$refs.quizPanel || typeof this.$refs.quizPanel.handleOpenQuiz !== 'function') return
        this.$refs.quizPanel.handleOpenQuiz(quiz)
      })
    },

    getScoreBarClass(percentage) {
      if (percentage >= 80) return 'score-bar-high'
      if (percentage >= 50) return 'score-bar-mid'
      return 'score-bar-low'
    },

    canToggleToolCard(toolCall) {
      if (!toolCall || toolCall.status !== 'done' || !toolCall.success) return false
      if (this.isScheduleDetailTool(toolCall.tool)) return true
      if (toolCall.tool === 'get_review_events') return true
      if (toolCall.tool === 'generate_chart') return !!toolCall.result?.image_url
      if (toolCall.tool === 'generate_test') return !!(toolCall.quizId || toolCall.result?.message)
      if (toolCall.tool === 'view_quiz_results') return true
      if (toolCall.tool === 'view_quiz_attempt_detail') return true
      return false
    },

    isToolCardExpanded(toolCallId) {
      return this.expandedToolCards[toolCallId] !== false
    },

    isToolCardCollapsing(toolCallId) {
      return !!this.collapsingToolCards[toolCallId]
    },

    toggleToolCard(toolCallId) {
      const expanded = this.expandedToolCards[toolCallId] !== false
      if (expanded) {
        this.collapsingToolCards = { ...this.collapsingToolCards, [toolCallId]: true }
        setTimeout(() => {
          this.expandedToolCards = { ...this.expandedToolCards, [toolCallId]: false }
          const { [toolCallId]: _removed, ...rest } = this.collapsingToolCards
          this.collapsingToolCards = rest
        }, 200)
        return
      }
      this.expandedToolCards = { ...this.expandedToolCards, [toolCallId]: true }
    },

    toggleToolCardIfAllowed(toolCall) {
      if (this.canToggleToolCard(toolCall)) this.toggleToolCard(toolCall.id)
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

    navigateToResult(quizId) {
      if (!quizId) return
      this.activeTab = 'quizzes'
      this.$nextTick(() => {
        if (!this.$refs.quizPanel || typeof this.$refs.quizPanel.navigateToQuizResult !== 'function') return
        this.$refs.quizPanel.navigateToQuizResult(quizId)
      })
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
      this.latestInputValue = ''
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
  height: 100dvh;
  min-height: 0;
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
  min-height: 0;
  overflow: hidden;
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

/* Member Management Tab */
.manage-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.manage-panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.manage-member-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  transition: background 0.12s ease;
}

.manage-member-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.manage-member-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.manage-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.manage-member-name {
  font-size: 13px;
  color: #CBD5E1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.manage-owner-badge {
  font-size: 11px;
  color: #A855F7;
  background: rgba(168, 85, 247, 0.15);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.manage-member-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.manage-toggle-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.manage-toggle-text {
  font-size: 12px;
  color: #94A3B8;
  white-space: nowrap;
}

.manage-toggle {
  transform: scale(0.7);
}

.manage-remove-btn {
  font-size: 12px;
  color: #F87171;
  cursor: pointer;
  padding: 3px 8px;
  border-radius: 4px;
  transition: background 0.12s ease;
  white-space: nowrap;
}

.manage-remove-btn:hover {
  background: rgba(239, 68, 68, 0.15);
}

/* ---- Leaderboard Panel ---- */
.leaderboard-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.leaderboard-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 0 16px;
}

.leaderboard-panel ::-webkit-scrollbar,
.leaderboard-scroll ::-webkit-scrollbar {
  width: 4px;
}

.leaderboard-panel ::-webkit-scrollbar-track,
.leaderboard-scroll ::-webkit-scrollbar-track {
  background: transparent;
}

.leaderboard-panel ::-webkit-scrollbar-thumb,
.leaderboard-scroll ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 2px;
}

.leaderboard-panel ::-webkit-scrollbar-thumb:hover,
.leaderboard-scroll ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.leaderboard-loading,
.leaderboard-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* Podium (Top 3) */
.leaderboard-podium {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 24px 16px 0;
  gap: 8px;
}

.podium-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  max-width: 120px;
}

.podium-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid;
  background: rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.podium-avatar-1st {
  width: 48px;
  height: 48px;
  border-width: 3px;
}

.podium-avatar-text {
  font-size: 16px;
  color: #E2E8F0;
  font-weight: 600;
}

.podium-crown {
  font-size: 20px;
  margin-bottom: -4px;
}

.podium-name {
  font-size: 12px;
  color: #CBD5E1;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

.podium-name-1st {
  color: #FFD700;
  font-weight: 600;
}

.podium-score {
  font-size: 14px;
  color: #94A3B8;
  font-weight: 600;
}

.podium-score-1st {
  color: #FFD700;
  font-size: 16px;
}

.podium-bar {
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border-radius: 6px 6px 0 0;
  margin-top: 4px;
}

.podium-rank {
  font-size: 18px;
  font-weight: 700;
  padding: 8px 0;
}

.podium-bar-1st {
  height: 80px;
  background: linear-gradient(180deg, rgba(255, 215, 0, 0.3) 0%, rgba(255, 215, 0, 0.08) 100%);
  color: #FFD700;
}

.podium-bar-2nd {
  height: 60px;
  background: linear-gradient(180deg, rgba(192, 192, 192, 0.25) 0%, rgba(192, 192, 192, 0.06) 100%);
  color: #C0C0C0;
}

.podium-bar-3rd {
  height: 44px;
  background: linear-gradient(180deg, rgba(205, 127, 50, 0.25) 0%, rgba(205, 127, 50, 0.06) 100%);
  color: #CD7F32;
}

/* List header row */
.leaderboard-header-row {
  display: flex;
  align-items: center;
  padding: 12px 16px 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-top: 16px;
}

.lb-header-rank {
  width: 32px;
  font-size: 11px;
  color: #64748B;
}

.lb-header-name {
  flex: 1.5;
  font-size: 11px;
  color: #64748B;
}

.lb-header-metric {
  flex: 1;
  font-size: 11px;
  color: #64748B;
  text-align: center;
}

/* List rows */
.leaderboard-row {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  transition: background 0.12s ease;
}

.leaderboard-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.leaderboard-row-self {
  background: rgba(96, 165, 250, 0.08);
  border-left: 2px solid #60A5FA;
}

.lb-rank-cell {
  width: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lb-rank-medal {
  font-size: 16px;
}

.lb-rank-num {
  font-size: 13px;
  color: #64748B;
  font-weight: 500;
}

.lb-name-cell {
  flex: 1.5;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.lb-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.lb-name {
  font-size: 13px;
  color: #CBD5E1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lb-owner-badge {
  font-size: 10px;
  color: #A855F7;
  background: rgba(168, 85, 247, 0.15);
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.lb-metric-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.lb-metric-value {
  font-size: 12px;
  color: #94A3B8;
}

.lb-metric-bar {
  width: 80%;
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.lb-metric-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.lb-bar-mastery {
  background: #60A5FA;
}

.lb-bar-quiz {
  background: #60A5FA;
}

.lb-composite-score {
  font-size: 15px;
  font-weight: 700;
  color: #E2E8F0;
}

.leaderboard-legend {
  padding: 16px;
  text-align: center;
}

.leaderboard-legend-text {
  font-size: 11px;
  color: #475569;
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
  overflow: hidden;
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
  min-height: 0;
}

.panel-chat-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
}

/* Chat Messages List */
.chat-messages-list {
  flex: 1;
  height: 0;
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

/* Tool cards aligned with app dark theme */
.bubble-ai-tools-only {
  background: transparent;
  border-color: transparent;
  padding: 0;
  max-width: 100%;
}

.tool-call-card {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.tool-call-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.tool-call-header {
  gap: 6px;
}

.tool-call-status-icon {
  width: 14px;
  height: 14px;
}

.tool-call-icon {
  color: rgba(96, 165, 250, 0.92);
}

.tool-call-success .tool-call-icon {
  color: rgba(74, 222, 128, 0.95);
}

.code-execution-card.tool-call-success {
  overflow: hidden;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.code-execution-card.tool-call-success .tool-call-header {
  margin: -8px -12px 0;
  padding: 8px 12px 6px;
  background: rgba(34, 197, 94, 0.06);
  border-bottom: 1px solid rgba(34, 197, 94, 0.16);
}

.tool-call-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.78);
}

.tool-call-args {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.42);
  margin-top: 4px;
}

.tool-call-args-inline {
  margin-top: 0;
  padding: 0 2px;
}

.default-tool-wrap,
.review-tool-wrap,
.graph-overview-wrap,
.gm-wrap,
.schedule-view-wrap,
.search-tool-wrap,
.chart-tool-wrap,
.quiz-tool-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.graph-tool-pill,
.quiz-tool-pill,
.search-indicator {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  transition: border-color 0.2s ease, background 0.2s ease;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
}

.graph-tool-pill:hover,
.quiz-tool-pill:hover,
.search-indicator:hover {
  border-color: rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.07);
}

.graph-tool-running,
.search-indicator-running,
.quiz-tool-running {
  border-color: rgba(74, 108, 247, 0.35);
  background: rgba(74, 108, 247, 0.1);
}

.graph-tool-success,
.search-indicator-success,
.quiz-tool-done {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.graph-tool-failed,
.search-indicator-failed,
.quiz-tool-failed {
  border-color: rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.08);
}

.graph-tool-success:hover,
.search-indicator-success:hover,
.quiz-tool-done:hover {
  border-color: rgba(34, 197, 94, 0.5);
  background: rgba(34, 197, 94, 0.1);
}

.graph-tool-pill:active,
.quiz-tool-pill:active,
.search-indicator:active {
  background: rgba(255, 255, 255, 0.03);
}

.graph-tool-success:active,
.search-indicator-success:active,
.quiz-tool-done:active {
  background: rgba(34, 197, 94, 0.05);
}

.graph-tool-pill-icon,
.quiz-tool-pill-icon,
.search-indicator-globe {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.graph-overview-icon-img,
.gm-card-icon-img,
.quiz-entry-icon {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.graph-tool-pill-icon-svg :deep(svg),
.search-indicator-globe :deep(svg),
.graph-overview-icon-img :deep(svg),
.gm-card-icon-img :deep(svg),
.quiz-entry-icon :deep(svg) {
  width: 16px;
  height: 16px;
  display: block;
}

.graph-tool-success .graph-tool-pill-icon,
.search-indicator-success .search-indicator-globe,
.quiz-tool-done .quiz-tool-pill-icon {
  background: rgba(34, 197, 94, 0.12);
  color: rgba(74, 222, 128, 0.95);
}

.graph-tool-pill-text,
.quiz-tool-pill-text,
.search-indicator-text {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.82);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: 0.1px;
  line-height: 1.3;
}

.graph-tool-running .graph-tool-pill-text,
.quiz-tool-running .quiz-tool-pill-text,
.search-indicator-running .search-indicator-text {
  color: rgba(255, 255, 255, 0.96);
}

.graph-tool-spinner,
.quiz-tool-spinner,
.search-indicator-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(74, 108, 247, 0.3);
  border-top-color: #4A6CF7;
  border-radius: 50%;
  animation: tool-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.graph-tool-status-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.graph-tool-chevron,
.search-indicator-chevron,
.quiz-entry-chevron {
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.4);
  transition: transform 0.2s ease, color 0.2s ease;
  font-size: 13px;
  line-height: 1;
}

.graph-tool-chevron-up,
.search-chevron-up {
  transform: rotate(180deg);
}

.gm-expanded-container,
.schedule-expanded-container,
.review-expanded-container,
.chart-expanded-container,
.quiz-expanded-container {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(34, 197, 94, 0.35);
  border-radius: 8px;
  overflow: hidden;
  gap: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.gm-expanded-container .graph-tool-pill,
.schedule-expanded-container .graph-tool-pill,
.review-expanded-container .graph-tool-pill,
.chart-expanded-container .graph-tool-pill,
.quiz-expanded-container .quiz-tool-pill {
  border: none;
  background: rgba(34, 197, 94, 0.06);
  border-radius: 8px 8px 0 0;
  padding: 8px 12px 6px;
  box-shadow: none;
}

.graph-overview-card,
.gm-card,
.schedule-card,
.review-card,
.chart-detail-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 14px;
  box-sizing: border-box;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.gm-expanded-container .graph-overview-card,
.gm-expanded-container .gm-card,
.schedule-expanded-container .schedule-card,
.review-expanded-container .review-card,
.chart-expanded-container .chart-detail-card,
.quiz-expanded-container .quiz-tool-empty {
  border: none;
  border-top: 1px solid rgba(34, 197, 94, 0.16);
  background: rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-radius: 0;
  box-shadow: none;
}

.graph-overview-header,
.gm-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.graph-overview-icon-wrap,
.gm-card-icon-wrap,
.quiz-entry-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: rgba(74, 108, 247, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.gm-icon-delete {
  background: rgba(239, 68, 68, 0.12);
}

.gm-icon-update {
  background: rgba(73, 255, 170, 0.12);
}

.gm-icon-query {
  background: rgba(129, 140, 248, 0.12);
}

.gm-icon-path-generate {
  background: rgba(0, 136, 255, 0.12);
}

.gm-icon-path-modify {
  background: rgba(255, 217, 61, 0.12);
}

.gm-icon-postorder {
  background: rgba(74, 108, 247, 0.12);
}

.graph-overview-title-col,
.gm-card-title-col,
.quiz-entry-text-col {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.graph-overview-title,
.gm-card-title,
.quiz-entry-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quiz-entry-card {
  margin-top: 0;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.quiz-entry-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: none;
}

.quiz-entry-card:active {
  transform: scale(0.98);
}

.quiz-entry-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.graph-overview-meta,
.gm-card-meta,
.chart-saved-text,
.schedule-date-text,
.schedule-event-desc,
.schedule-card-count,
.schedule-empty-text,
.review-empty-text,
.review-card-count,
.review-event-round,
.quiz-entry-meta,
.quiz-tool-empty-text,
.search-source-site,
.search-tool-empty-text,
.tool-call-result-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.graph-overview-divider,
.gm-card-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.07);
  margin: 10px 0;
}

.graph-overview-preview,
.gm-card-preview,
.chart-image-preview {
  position: relative;
  background: rgba(255, 255, 255, 0.025);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow: hidden;
  padding: 12px;
}

.graph-overview-hint {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 1;
}

.graph-overview-hint-text {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
}

.graph-overview-preview-copy,
.gm-card-preview {
  padding: 12px;
}

.graph-overview-preview-line,
.gm-card-preview-text {
  display: block;
  font-size: 12px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.55);
}

.graph-overview-preview-line + .graph-overview-preview-line,
.gm-card-chip-row + .gm-card-preview-text {
  margin-top: 6px;
}

.gm-card-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.gm-card-chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.gm-card-chip-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.schedule-date-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0 8px;
}

.schedule-date-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.24);
  flex-shrink: 0;
}

.schedule-date-dot-today {
  background: rgba(74, 108, 247, 0.85);
}

.schedule-date-text-today {
  color: rgba(255, 255, 255, 0.66);
}

.schedule-event-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  margin-top: 6px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.schedule-event-time {
  width: 58px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.schedule-event-time-start {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.82);
}

.schedule-event-time-end {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.36);
}

.schedule-event-bar {
  width: 3px;
  align-self: stretch;
  border-radius: 999px;
  min-height: 42px;
  flex-shrink: 0;
}

.schedule-event-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.schedule-event-title {
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.86);
}

.schedule-card-footer,
.review-card-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
}

.schedule-card-empty,
.review-card-empty {
  align-items: center;
}

.review-event-item {
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.review-event-item + .review-event-item {
  margin-top: 8px;
}

.review-event-header,
.review-event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-event-header {
  margin-bottom: 8px;
}

.review-event-label {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.review-event-depth {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(129, 140, 248, 0.12);
  color: rgba(129, 140, 248, 0.9);
  font-size: 11px;
}

.review-event-urgency-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(94, 194, 105, 0.1);
}

.review-event-urgency-badge.urgency-overdue {
  background: rgba(232, 168, 56, 0.12);
}

.review-event-urgency-text {
  font-size: 11px;
  color: rgba(94, 194, 105, 0.9);
}

.review-event-urgency-text.urgency-overdue-text {
  color: rgba(232, 168, 56, 0.92);
}

.search-indicator-expanded {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.5);
}

.search-indicator-collapsed {
  background: rgba(34, 197, 94, 0.06);
  border-color: rgba(34, 197, 94, 0.35);
}

.search-sources-scroll {
  margin-top: 4px;
  white-space: nowrap;
}

.search-sources-row {
  display: inline-flex;
  gap: 10px;
}

.search-source-card {
  display: inline-flex;
  flex-direction: column;
  gap: 10px;
  width: 220px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  cursor: pointer;
  white-space: normal;
  box-sizing: border-box;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.55);
}

.search-source-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.16);
  transform: translateY(-2px);
  box-shadow: 0 24px 45px rgba(0, 0, 0, 0.55);
}

.search-source-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
}

.search-source-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-source-num {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: rgba(74, 108, 247, 0.14);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-source-num-text {
  font-size: 11px;
  font-weight: 600;
  color: #60A5FA;
}

.search-source-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.86);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.search-tool-empty,
.search-tool-error,
.quiz-tool-empty {
  padding: 18px 22px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 22px 45px rgba(0, 0, 0, 0.55);
  text-align: center;
}

.search-tool-error-text {
  font-size: 12px;
  color: rgba(248, 113, 113, 0.86);
}

.quiz-tool-results-card,
.quiz-tool-detail-card {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 18px 20px;
  box-shadow: 0 24px 50px rgba(0, 0, 0, 0.55);
}

.quiz-expanded-container .quiz-tool-results-card,
.quiz-expanded-container .quiz-tool-detail-card {
  border: none;
  border-top: 1px solid rgba(34, 197, 94, 0.16);
  background: rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-radius: 0 0 16px 16px;
}

.quiz-tool-results-card {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quiz-result-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.quiz-result-clickable {
  cursor: pointer;
}

.quiz-result-clickable:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
}

.quiz-result-clickable:active,
.quiz-tool-detail-clickable:active {
  transform: scale(0.99);
}

.quiz-result-evaluating {
  opacity: 0.58;
}

.quiz-result-row,
.quiz-result-meta,
.quiz-detail-questions-header,
.quiz-detail-footer {
  display: flex;
  align-items: center;
}

.quiz-result-row {
  gap: 8px;
}

.quiz-result-title {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.quiz-result-difficulty {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
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
  color: rgba(248, 113, 113, 0.92);
  background: rgba(248, 113, 113, 0.16);
}

.quiz-result-meta {
  gap: 10px;
  margin-top: 8px;
}

.quiz-result-score {
  font-size: 12px;
  font-weight: 600;
  color: rgba(96, 165, 250, 0.96);
}

.quiz-result-evaluating-text {
  font-size: 12px;
  font-weight: 600;
  color: rgba(251, 191, 36, 0.9);
}

.quiz-result-no-attempt,
.quiz-result-date,
.quiz-detail-score-label,
.quiz-detail-score-percent,
.quiz-detail-section-title,
.quiz-detail-subsection-title,
.quiz-detail-questions-count,
.quiz-detail-q-order,
.quiz-detail-q-score {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.quiz-result-date {
  flex: 1;
}

.quiz-result-arrow,
.quiz-detail-footer-arrow {
  font-size: 18px;
  line-height: 1;
  color: rgba(255, 255, 255, 0.34);
  flex-shrink: 0;
}

.quiz-tool-detail-card {
  overflow: hidden;
}

.quiz-detail-score-section,
.quiz-detail-analysis-section,
.quiz-detail-questions-section {
  padding: 12px 14px;
}

.quiz-detail-score-header,
.quiz-detail-analysis-header {
  margin-bottom: 8px;
}

.quiz-detail-score-label,
.quiz-detail-section-title {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.quiz-detail-score-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}

.quiz-detail-score-value {
  font-size: 24px;
  font-weight: 700;
  color: rgba(96, 165, 250, 0.96);
}

.quiz-detail-score-bar-bg {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}

.quiz-detail-score-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.score-bar-high {
  background: rgba(34, 197, 94, 0.85);
}

.score-bar-mid {
  background: rgba(251, 191, 36, 0.85);
}

.score-bar-low {
  background: rgba(248, 113, 113, 0.88);
}

.quiz-detail-analysis-section,
.quiz-detail-questions-section,
.quiz-detail-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.quiz-detail-subsection + .quiz-detail-subsection {
  margin-top: 12px;
}

.quiz-detail-subsection-title {
  margin-bottom: 8px;
  font-weight: 600;
}

.quiz-detail-tag-item,
.quiz-detail-q-row {
  display: flex;
  gap: 10px;
}

.quiz-detail-tag-item {
  align-items: flex-start;
  padding: 4px 0;
}

.quiz-detail-dot,
.quiz-detail-q-status-dot {
  border-radius: 999px;
  flex-shrink: 0;
}

.quiz-detail-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
}

.strength-dot {
  background: rgba(34, 197, 94, 0.9);
}

.weakness-dot {
  background: rgba(248, 113, 113, 0.9);
}

.quiz-detail-tag-text,
.quiz-detail-q-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.82);
}

.quiz-detail-q-row {
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
}

.quiz-detail-q-row + .quiz-detail-q-row {
  margin-top: 8px;
}

.quiz-detail-q-status-dot {
  width: 10px;
  height: 10px;
}

.status-dot-correct {
  background: rgba(34, 197, 94, 0.9);
}

.status-dot-wrong {
  background: rgba(248, 113, 113, 0.9);
}

.status-dot-partial {
  background: rgba(251, 191, 36, 0.9);
}

.quiz-detail-footer {
  justify-content: center;
  gap: 8px;
  padding: 14px 16px 16px;
  cursor: pointer;
}

.quiz-detail-footer-text {
  font-size: 13px;
  font-weight: 600;
  color: rgba(96, 165, 250, 0.92);
}

.chart-image-preview {
  margin-top: 0;
}

.chart-preview-img {
  width: 100%;
  display: block;
  border-radius: 14px;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.chart-preview-img:hover {
  opacity: 0.92;
}

.chart-saved-badge {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.chart-saved-icon {
  width: 14px;
  height: 14px;
  opacity: 0.5;
  flex-shrink: 0;
}

.code-execution-card .code-block-section {
  margin-top: 10px;
}

.code-toggle-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.46);
}

.code-toggle-text:hover {
  color: rgba(255, 255, 255, 0.66);
}

.code-block-wrapper {
  margin-top: 8px;
}

.code-block-pre {
  padding: 12px 14px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 10px;
}

.code-output-section {
  margin-top: 10px;
  padding-top: 10px;
}

.code-output-stdout,
.code-output-stderr {
  padding: 10px 12px;
  border-radius: 10px;
}

.code-output-stderr {
  margin-top: 8px;
}

.tool-card-leave {
  animation: tool-card-leave 0.2s ease-in forwards;
  pointer-events: none;
}

@keyframes tool-card-leave {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-8px); }
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
  height: 100% !important;
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

.chat-input-textarea :deep(textarea),
.chat-input-textarea :deep(.uni-textarea-textarea) {
  width: 100%;
  height: 100% !important;
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
  max-height: 100000px;
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
