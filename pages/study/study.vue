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
        <text class="study-header-title">{{ spaceName }}</text>
        <view class="study-header-actions">
          <view class="settings-btn" @tap="openSettings">
            <svg viewBox="0 0 256 256" class="settings-icon">
              <rect width="256" height="256" fill="none"/>
              <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="40" y1="64" x2="216" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="40" y1="192" x2="216" y2="192" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <circle cx="128" cy="128" r="12" fill="currentColor"/>
              <circle cx="176" cy="64" r="12" fill="currentColor"/>
              <circle cx="80" cy="192" r="12" fill="currentColor"/>
            </svg>
          </view>
        </view>
      </view>

      <!-- Two-Panel Layout -->
      <view class="study-panels">
        <!-- Left Panel: Knowledge Graph -->
        <view class="panel-graph">
          <view class="panel-graph-inner">
            <!-- Chrome-style Tab Bar -->
            <view class="chrome-tabs-bar">
              <view
                v-for="tab in tabs"
                :key="tab.id"
                class="chrome-tab"
                :class="{ 'chrome-tab-active': activeTab === tab.id }"
                @tap="activeTab = tab.id"
              >
                <text class="chrome-tab-label">{{ tab.label }}</text>
              </view>
              <view class="chrome-tabs-spacer"></view>
            </view>

            <!-- Tab Content Area -->
            <view class="tab-content-area">
              <KnowledgeGraph
                v-if="activeTab === 'graph'"
                :spaceId="spaceId"
                :pathHighlight="isPathHighlightOn"
                @node-selected="onNodeSelected"
                @graph-loaded="onGraphLoaded"
              />
              <template v-else>
                <text class="placeholder-text">{{ activeTabInfo.placeholder }}</text>
                <text class="placeholder-sub">{{ activeTabInfo.sub }}</text>
              </template>
            </view>

            <!-- Bottom Action Buttons (graph tab only) -->
            <view v-if="activeTab === 'graph'" class="graph-actions">
              <view
                class="graph-action-btn"
                :class="{ 'graph-action-btn-active': isPathHighlightOn }"
                @tap="togglePathHighlight"
              >
                <svg viewBox="0 0 256 256" class="action-icon">
                  <rect width="256" height="256" fill="none"/>
                  <path d="M128,120a40,40,0,1,1-40-40A40,40,0,0,1,128,120Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M96,160v24a8,8,0,0,0,8,8h48a8,8,0,0,0,8-8V131.37" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M128,80V64a8,8,0,0,1,8-8h48a8,8,0,0,1,8,8v48a8,8,0,0,1-8,8H176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
              <view class="graph-action-btn">
                <svg viewBox="0 0 256 256" class="action-icon">
                  <rect width="256" height="256" fill="none"/>
                  <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
            </view>
          </view>
        </view>

        <!-- Right Panel: Chat -->
        <view class="panel-chat">
          <view class="panel-chat-inner">
            <!-- Messages Area (placeholder) -->
            <view class="chat-messages-area">
              <text class="placeholder-text">Chat Messages</text>
              <text class="placeholder-sub">Conversation history will appear here</text>
            </view>

            <!-- Input Bar -->
            <view class="chat-input-bar">
              <svg viewBox="0 0 256 256" class="input-search-icon">
                <rect width="256" height="256" fill="none"/>
                <circle cx="116" cy="116" r="84" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                <line x1="175.39" y1="175.39" x2="224" y2="224" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              </svg>
              <input
                class="chat-input"
                type="text"
                placeholder="Ask anything..."
                disabled
              />
              <view class="chat-send-btn">
                <svg viewBox="0 0 256 256" class="send-icon">
                  <rect width="256" height="256" fill="none"/>
                  <line x1="108" y1="148" x2="160" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M223.69,42.18a8,8,0,0,0-9.87-9.87l-192,58.22a8,8,0,0,0-1.25,14.93L108,148l42.54,87.42a8,8,0,0,0,14.93-1.25Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
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
import { getSpaces } from '@/api/space'

export default {
  components: { HomeSidebar, KnowledgeGraph },
  data() {
    return {
      sidebarCollapsed: false,
      spaceId: null,
      spaceName: 'Study',
      activeTab: 'graph',
      isPathHighlightOn: false,
      tabs: [
        { id: 'graph', label: '知识图谱', placeholder: 'Knowledge Graph', sub: 'Canvas area for nodes and edges' },
        { id: 'materials', label: '学习资料', placeholder: 'Study Materials', sub: 'Upload and manage learning resources' },
        { id: 'quizzes', label: '测试题', placeholder: 'Quizzes', sub: 'Practice tests and assessments' },
        { id: 'notes', label: '笔记', placeholder: 'Notes', sub: 'Your study notes and highlights' },
        { id: 'browser', label: '自由网页', placeholder: 'Web Browser', sub: 'Browse the web freely' }
      ]
    }
  },
  computed: {
    activeTabInfo() {
      return this.tabs.find(t => t.id === this.activeTab) || this.tabs[0]
    }
  },
  onLoad(options) {
    if (options.spaceId) {
      this.spaceId = options.spaceId
      this.loadSpaceInfo()
    }
  },
  methods: {
    async loadSpaceInfo() {
      try {
        const res = await getSpaces()
        const spaces = res.data || res || []
        const space = spaces.find(s => String(s.id) === String(this.spaceId))
        if (space) {
          this.spaceName = space.name
        }
      } catch (error) {
        console.error('[StudyPage] Failed to load space info:', error)
      }
    },
    handleSelectSpace(spaceId) {
      this.spaceId = spaceId
      this.loadSpaceInfo()
    },
    handleCreateSpace() {
      uni.showToast({ title: 'Create space coming soon', icon: 'none' })
    },
    openSettings() {
      uni.showToast({ title: 'Space settings coming soon', icon: 'none' })
    },
    togglePathHighlight() {
      this.isPathHighlightOn = !this.isPathHighlightOn
    },
    onNodeSelected(payload) {
      // Can be used to show node details in the chat panel
    },
    onGraphLoaded({ nodeCount, edgeCount }) {
      // Graph loaded successfully
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

.settings-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.settings-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.settings-icon {
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.7);
}

/* Two-Panel Split */
.study-panels {
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

/* Inverse rounded corners — CSS-Tricks box-shadow technique */
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
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 0;
}

/* Graph Actions */
.graph-actions {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
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

/* Right Panel - 50% */
.panel-chat {
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

/* Chat Messages Area */
.chat-messages-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 0;
}

/* Chat Input Bar */
.chat-input-bar {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.input-search-icon {
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: #FFFFFF;
  font-size: 14px;
  outline: none;
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

.send-icon {
  width: 16px;
  height: 16px;
  color: var(--color-accent-blue);
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
</style>
