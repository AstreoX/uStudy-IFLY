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
                <view v-if="msg.role === 'user'" class="message-bubble bubble-user">
                  <text class="bubble-text">{{ msg.content }}</text>
                </view>

                <!-- AI message -->
                <view v-else class="message-bubble bubble-ai">
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

            <!-- Input Bar -->
            <view class="chat-input-bar">
              <input
                class="chat-input"
                type="text"
                placeholder="Ask anything..."
                :disabled="!spaceId"
                v-model="inputText"
                @confirm="handleSend"
              />
              <!-- Stop button during streaming -->
              <view v-if="isStreaming" class="chat-stop-btn" @tap="handleStop">
                <svg viewBox="0 0 256 256" class="stop-icon">
                  <rect x="88" y="88" width="80" height="80" rx="8" fill="currentColor"/>
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
import { getSpaces } from '@/api/space'
import { createConversation, getSpaceConversations, getConversation, sendMessage } from '@/api/chat'

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
  mark_review_completed: 'Mark Reviewed'
}

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
  default: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-width="16"/><path d="M128,48a80,80,0,0,1,80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M48,128a80,80,0,0,1,80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M208,128a80,80,0,0,1-80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M128,208a80,80,0,0,1-80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>'
}

// Map tool names to icon categories
const TOOL_ICON_MAP = {
  get_graph_overview: 'graph', add_node: 'graph', add_edge: 'graph',
  delete_node: 'graph', delete_edge: 'graph', update_mastery: 'graph',
  get_child_nodes: 'graph', get_parent_nodes: 'graph', get_sibling_nodes: 'graph',
  generate_learning_path: 'graph', get_learning_paths: 'graph',
  delete_all_learning_paths: 'graph', get_postorder_traversal: 'graph',
  get_schedule: 'calendar', add_schedule: 'calendar',
  delete_schedule: 'calendar', update_schedule: 'calendar',
  generate_test: 'default',
  web_search: 'search', web_fetch: 'search', search_documents: 'search',
  write_to_long_term_memory: 'memory', delete_from_long_term_memory: 'memory',
  write_to_space_memory: 'memory', delete_from_space_memory: 'memory',
  get_review_events: 'review', mark_review_completed: 'review'
}

export default {
  components: { HomeSidebar, KnowledgeGraph, MarkdownRender },
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
      ],

      // Chat state
      messages: [],
      conversationId: null,
      inputText: '',
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

      // Typewriter buffer
      typewriterBuffer: '',
      typewriterTimer: null,
      typewriterMsgId: null,
      typewriterSpeed: 30
    }
  },
  computed: {
    activeTabInfo() {
      return this.tabs.find(t => t.id === this.activeTab) || this.tabs[0]
    },
    canSend() {
      return this.spaceId && this.inputText.trim().length > 0 && !this.isSending
    }
  },
  onLoad(options) {
    if (options.spaceId) {
      this.spaceId = options.spaceId
      this.loadSpaceInfo()
      this.initConversation()
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
      // Stop typewriter to prevent orphaned timers
      this.stopTypewriter()

      // Cancel any ongoing SSE
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }

      // Reset chat state
      this.messages = []
      this.conversationId = null
      this.nextId = 1
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []
      this.inputText = ''

      this.spaceId = spaceId
      this.loadSpaceInfo()
      this.initConversation()
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
      // Could be used to inject context into chat
    },

    onGraphLoaded({ nodeCount, edgeCount }) {
      // Graph loaded
    },

    // ==================== Chat Methods ====================

    async initConversation() {
      if (!this.spaceId) return

      try {
        const result = await getSpaceConversations(this.spaceId)
        const conversations = result.conversations || result || []
        if (conversations.length > 0) {
          // Use the most recent conversation
          this.conversationId = conversations[0].id
          await this.loadConversationHistory()
        }
      } catch (err) {
        console.error('[StudyPage] Failed to load conversations:', err)
      }
    },

    async loadConversationHistory() {
      if (!this.conversationId) return

      this.isLoadingHistory = true
      try {
        const result = await getConversation(this.conversationId)
        const rawMessages = result.messages || []
        this.messages = rawMessages.map((m, i) => ({
          id: i + 1,
          role: m.role === 'user' ? 'user' : 'ai',
          content: m.content,
          created_at: m.created_at
        }))
        this.nextId = this.messages.length + 1
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

      this.isSending = true
      this.isAutoScrollEnabled = true
      this.inputText = ''

      // Create conversation if needed
      if (!this.conversationId) {
        try {
          const conv = await createConversation(this.spaceId, text.slice(0, 50))
          this.conversationId = conv.id
        } catch (err) {
          this.isSending = false
          uni.showToast({ title: 'Failed to create conversation', icon: 'none' })
          return
        }
      }

      // Add user message
      const userMsgId = this.nextId++
      this.messages.push({ id: userMsgId, role: 'user', content: text })

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
        toolCalls: null
      })

      this.$nextTick(() => this.scrollToBottom())
      this.isStreaming = true
      this.activeToolCalls = []

      this.cancelSSE = sendMessage(this.conversationId, text, {
        onTextDelta: (content) => {
          this.appendToTypewriter(aiMsgId, content)
        },

        onToolCall: (data) => {
          this.handleToolCallEvent(aiMsgId, data)
        },

        onDone: (fullContent) => {
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            // Finalize segments
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
          this.isStreaming = false
          this.isSending = false
          this.activeToolCalls = []
          this.$nextTick(() => this.scrollToBottom())
        },

        onError: (message) => {
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg) {
            aiMsg.content = aiMsg.content || 'Request failed'
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
            aiMsg.isError = true
          }
          this.isStreaming = false
          uni.showToast({ title: message || 'Request failed', icon: 'none' })
        },

        onComplete: () => {
          this.flushTypewriter()
          const aiMsg = this.messages.find(m => m.id === aiMsgId)
          if (aiMsg && aiMsg.isStreaming) {
            aiMsg.isWaitingOutput = false
            aiMsg.isStreaming = false
            this.activeToolCalls = []
            if (!aiMsg.content || aiMsg.content.trim() === '') {
              aiMsg.content = 'Connection interrupted. Please resend your message.'
            }
          }
          this.cancelSSE = null
          this.isSending = false
          this.isStreaming = false
        }
      })
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
        this.flushTypewriter()

        if (!msg.streamSegments || msg.streamSegments === null) {
          msg.streamSegments = []
        }

        if (msg.content && msg.content.length > 0) {
          msg.streamSegments.push({ type: 'text', content: msg.content })
          msg.content = ''
        }

        const toolCall = { id, tool, arguments: args, status: 'running' }

        if (MEMORY_TOOLS.has(tool)) {
          this.memoryToolStartTimes[id] = Date.now()
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

    isMemoryTool(toolName) {
      return MEMORY_TOOLS.has(toolName)
    },

    getMemoryToolText(toolName) {
      return MEMORY_TOOL_TEXT[toolName] || 'Accessing memory...'
    },

    getMemoryToolDisplayStatus(toolCall) {
      if (!toolCall) return 'running'
      if (this.memoryToolDelayedDone[toolCall.id]) return 'running'
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
      this.flushTypewriter()

      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false

      // Finalize any streaming message
      const streamingMsg = this.messages.find(m => m.isStreaming)
      if (streamingMsg) {
        streamingMsg.isStreaming = false
        streamingMsg.isWaitingOutput = false
        if (!streamingMsg.content || streamingMsg.content.trim() === '') {
          streamingMsg.content = 'Response stopped by user.'
        }
      }
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

.bubble-user .bubble-text {
  color: rgba(255, 255, 255, 0.95);
  font-size: 14px;
  line-height: 1.5;
}

.bubble-ai {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom-left-radius: 4px;
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
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
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
  width: 16px;
  height: 16px;
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
</style>
