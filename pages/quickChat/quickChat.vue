<template>
  <view class="quick-chat-page">
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
    <view class="quick-chat-main">
      <!-- Header Bar -->
      <view class="quick-chat-header">
        <view class="header-left">
          <view class="header-back-btn" @tap="navigateToIndex">
            <svg viewBox="0 0 256 256" class="header-back-icon">
              <polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
          </view>
          <text class="header-title">Quick Chat</text>
        </view>
        <view class="header-actions">
          <view class="chat-header-btn-wrap">
            <view class="chat-header-btn" @tap="openHistoryPopup">
              <svg viewBox="0 0 256 256" class="chat-header-icon">
                <circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                <polyline points="128 80 128 128 168 152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              </svg>
            </view>

            <!-- History popup -->
            <transition name="history-fade">
              <view v-if="showHistoryPopup" class="history-popup">
                <view class="history-popup-header">
                  <text class="history-popup-title">Chat History</text>
                  <view class="history-popup-close" @tap="showHistoryPopup = false">
                    <text class="history-popup-close-text">&times;</text>
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
                    <text class="history-empty-text">No conversations yet</text>
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

          <view class="chat-header-btn" @tap="handleNewConversation">
            <svg viewBox="0 0 256 256" class="chat-header-icon">
              <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
          </view>
        </view>
      </view>

      <!-- Chat Messages Container (centered, max-width 800px) -->
      <view class="chat-messages-container">
        <scroll-view
          class="chat-messages-list"
          scroll-y
          :scroll-top="scrollTopValue"
          @scroll="onChatScroll"
        >
          <!-- Empty state -->
          <view v-if="messages.length === 0 && !isLoadingHistory" class="chat-empty-state">
            <svg viewBox="0 0 256 256" width="48" height="48" class="chat-empty-icon">
              <rect width="256" height="256" fill="none"/>
              <path d="M128,24A104,104,0,0,0,36.18,176.88L24.83,210.93a8,8,0,0,0,10.24,10.24l34.05-11.35A104,104,0,1,0,128,24Z" fill="none" stroke="rgba(255,255,255,0.15)" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
            <text class="chat-empty-title">Start a quick conversation</text>
            <text class="chat-empty-sub">Ask anything - study questions, space management, and more</text>
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
            <view v-if="msg.role === 'user'" class="user-bubble-row">
              <view v-if="msg.isFailed" class="msg-retry-btn" @tap="resendMessage(msg)">
                <svg viewBox="0 0 256 256" class="msg-retry-icon">
                  <polyline points="176.17 99.71 224.17 99.71 224.17 51.71" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                  <path d="M65.78,65.78a88,88,0,0,1,124.44,0l34,33.93" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                  <polyline points="79.83 156.29 31.83 156.29 31.83 204.29" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                  <path d="M190.22,190.22a88,88,0,0,1-124.44,0l-34-33.93" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                </svg>
              </view>
              <view class="message-bubble bubble-user">
                <view v-if="msg.attachments && msg.attachments.length > 0" class="msg-attachments">
                  <template v-for="att in msg.attachments" :key="att.id">
                    <image
                      v-if="att.attachment_type === 'image'"
                      class="msg-attach-img"
                      :src="att.thumbnail_url || att.file_url"
                      mode="aspectFit"
                      @tap="previewImage(att.file_url)"
                    />
                    <view v-else class="msg-attach-file" @tap="openFileUrl(att.file_url)">
                      <text class="msg-attach-file-name">{{ att.original_filename }}</text>
                    </view>
                  </template>
                </view>
                <text class="bubble-text">{{ msg.content }}</text>
              </view>
            </view>

            <!-- AI message -->
            <template v-else>
              <view class="message-bubble bubble-ai">
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
                        <svg v-else-if="seg.toolCall.status === 'pending_confirmation'" viewBox="0 0 256 256" class="tool-call-status-icon tool-status-pending">
                          <circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          <line x1="128" y1="80" x2="128" y2="136" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          <circle cx="128" cy="172" r="10" fill="currentColor"/>
                        </svg>
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
                        <text class="tool-call-name">{{ seg.toolCall.display_name || getToolDisplayName(seg.toolCall.tool) }}</text>
                      </view>

                      <!-- Confirmation area -->
                      <view v-if="seg.toolCall.status === 'pending_confirmation'" class="tool-confirm-actions">
                        <view class="tool-confirm-info">
                          <text class="tool-confirm-text">{{ getConfirmationText(seg.toolCall) }}</text>
                        </view>
                        <view class="tool-confirm-buttons">
                          <view class="tool-btn tool-btn-cancel" @tap="handleToolReject(msg.id, seg.toolCall)">
                            <text class="tool-btn-text">Cancel</text>
                          </view>
                          <view class="tool-btn tool-btn-confirm" @tap="handleToolConfirm(msg.id, seg.toolCall)">
                            <text class="tool-btn-text">Confirm</text>
                          </view>
                        </view>
                      </view>

                      <!-- Result message -->
                      <view v-if="seg.toolCall.status === 'done' && seg.toolCall.message" class="tool-call-result">
                        <text class="tool-call-result-text">{{ seg.toolCall.message }}</text>
                      </view>

                      <!-- view_learning_spaces result list -->
                      <view v-if="seg.toolCall.tool === 'view_learning_spaces' && seg.toolCall.status === 'done' && seg.toolCall.result && seg.toolCall.result.spaces" class="tool-spaces-list">
                        <view
                          v-for="space in seg.toolCall.result.spaces"
                          :key="space.id"
                          class="tool-space-item"
                          @tap="handleSpaceClick(space)"
                        >
                          <view class="tool-space-color" :style="{ backgroundColor: space.color || '#3B82F6' }"></view>
                          <text class="tool-space-name">{{ space.name }}</text>
                          <svg viewBox="0 0 256 256" class="tool-space-arrow">
                            <polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                          </svg>
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

              <!-- AI message actions (after streaming completes) -->
              <view v-if="msg.role === 'ai' && !msg.isStreaming && !msg.isWelcome" class="ai-msg-actions">
                <svg viewBox="0 0 256 256" class="ai-msg-action-icon" @tap="copyMessage(msg)">
                  <rect x="32" y="80" width="128" height="144" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                  <path d="M96,80V40a8,8,0,0,1,8-8h112a8,8,0,0,1,8,8V176a8,8,0,0,1-8,8H160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                </svg>
              </view>
            </template>
          </view>

          <!-- Bottom padding -->
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
                <text class="attach-preview-file-name">{{ att.original_filename }}</text>
              </view>
              <view class="attach-preview-remove" @tap="removeAttachment(idx)">&times;</view>
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
              :class="{ 'attach-btn-disabled': isSending }"
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
                  <text class="attach-menu-icon">&#x1F5BC;</text>
                  <text class="attach-menu-label">Image</text>
                </view>
                <view class="attach-menu-item" @tap="pickFile">
                  <text class="attach-menu-icon">&#x1F4CE;</text>
                  <text class="attach-menu-label">File</text>
                </view>
              </view>
            </transition>
          </view>

          <input
            ref="chatInput"
            class="chat-input"
            type="text"
            placeholder="Ask anything..."
            v-model="inputText"
            @confirm="handleSend"
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

      <!-- History popup backdrop -->
      <view v-if="showHistoryPopup" class="history-backdrop" @tap="showHistoryPopup = false"></view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import {
  createQuickChatConversation,
  getQuickChatConversations,
  sendQuickChatMessage,
  confirmToolExecution,
  getConversation,
  uploadAttachment,
  deleteAttachment
} from '@/api/chat'

// Quick chat tool display names
const TOOL_DISPLAY_NAMES = {
  view_learning_spaces: 'View Learning Spaces',
  rebind_to_learning_space: 'Bind to Space',
  create_learning_space: 'Create Space',
  write_to_long_term_memory: 'Update Memory',
  delete_from_long_term_memory: 'Delete Memory',
  write_to_space_memory: 'Update Space Memory',
  delete_from_space_memory: 'Delete Space Memory'
}

// Tool icon SVGs
const TOOL_ICON_SVGS = {
  view_learning_spaces: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-width="16"/></svg>',
  rebind_to_learning_space: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M122.33,71.39a48,48,0,0,1,62.28,62.28" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M71.39,122.33a48,48,0,0,0,62.28,62.28" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
  create_learning_space: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-width="16"/><line x1="88" y1="128" x2="168" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><line x1="128" y1="88" x2="128" y2="168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>',
  memory: '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M128,24A96,96,0,0,0,64,184V224h128V184A96,96,0,0,0,128,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="112" y1="224" x2="112" y2="192" fill="none" stroke="currentColor" stroke-width="16"/><line x1="144" y1="224" x2="144" y2="192" fill="none" stroke="currentColor" stroke-width="16"/></svg>',
  default: '<svg viewBox="0 0 256 256" width="14" height="14"><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-width="16"/><path d="M128,48a80,80,0,0,1,80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M48,128a80,80,0,0,1,80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M208,128a80,80,0,0,1-80,80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/><path d="M128,208a80,80,0,0,1-80-80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="16"/></svg>'
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

export default {
  components: { HomeSidebar, MarkdownRender },
  data() {
    return {
      sidebarCollapsed: false,

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
      typewriterSpeed: 30,

      // Conversation history popup
      showHistoryPopup: false,
      historyConversations: [],
      isLoadingConversations: false,

      // Attachment upload
      pendingAttachments: [],
      showAttachMenu: false
    }
  },
  computed: {
    canSend() {
      return this.inputText.trim().length > 0 && !this.isSending
    }
  },
  onLoad() {
    // Show welcome message on fresh load
    this.messages.push({
      id: this.nextId++,
      role: 'ai',
      content: `Hi! I'm your learning assistant. Here's what I can help with:

**Chat freely** - Ask me any study-related question
**Learning Spaces** - View, create, or jump into a learning space
**Remember preferences** - I'll remember your habits for next time

For deeper learning (knowledge graphs, quizzes, document search), enter a specific learning space. What would you like to ask?`,
      isWelcome: true
    })
  },
  mounted() {
    const inputEl = this.$refs.chatInput?.$el?.querySelector('input')
    if (inputEl) {
      inputEl.addEventListener('paste', this.handlePaste)
    }
  },
  beforeUnmount() {
    const inputEl = this.$refs.chatInput?.$el?.querySelector('input')
    if (inputEl) {
      inputEl.removeEventListener('paste', this.handlePaste)
    }
    this.cleanupPendingAttachments()
    this.stopTypewriter()
    if (this.cancelSSE) {
      this.cancelSSE()
      this.cancelSSE = null
    }
  },
  methods: {
    navigateToIndex() {
      uni.reLaunch({ url: '/pages/index/index' })
    },

    handleSelectSpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${spaceId}` })
    },

    handleCreateSpace() {
      uni.showToast({ title: 'Create space coming soon', icon: 'none' })
    },

    // ==================== Chat Methods ====================

    async handleSend() {
      const text = this.inputText.trim()
      if (!text || this.isSending) return

      if (this.pendingAttachments.some(a => a.uploading)) {
        uni.showToast({ title: 'Uploading, please wait...', icon: 'none' })
        return
      }

      this.isSending = true
      this.isAutoScrollEnabled = true
      this.inputText = ''

      // Collect attachment IDs and clear pending
      const attachmentIds = this.pendingAttachments
        .filter(a => a.id && !String(a.id).startsWith('temp_'))
        .map(a => a.id)
      const sentAttachments = [...this.pendingAttachments]
      this.pendingAttachments = []
      sentAttachments.forEach(a => { if (a.localPreview) URL.revokeObjectURL(a.localPreview) })

      // Add user message
      const userMsgId = this.nextId++
      this.messages = [...this.messages, {
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
      }]

      this.$nextTick(() => this.scrollToBottom())

      // Create conversation if needed
      if (!this.conversationId) {
        try {
          const conv = await createQuickChatConversation(text.slice(0, 50))
          this.conversationId = conv.id
        } catch (err) {
          this.isSending = false
          const msgs = [...this.messages]
          const userMsg = msgs.find(m => m.id === userMsgId)
          if (userMsg) userMsg.isFailed = true
          this.messages = msgs
          uni.showToast({ title: 'Failed to create conversation', icon: 'none' })
          return
        }
      }

      // Add AI placeholder
      const aiMsgId = this.nextId++
      this.messages = [...this.messages, {
        id: aiMsgId,
        role: 'ai',
        content: '',
        isStreaming: true,
        isWaitingOutput: true,
        isError: false,
        segments: null,
        streamSegments: null,
        toolCalls: null
      }]

      this.$nextTick(() => this.scrollToBottom())
      this.isStreaming = true
      this.activeToolCalls = []

      const callbacks = this._buildSSECallbacks(aiMsgId, userMsgId)
      this.cancelSSE = sendQuickChatMessage(
        this.conversationId, text, callbacks,
        attachmentIds.length > 0 ? attachmentIds : null
      )
    },

    _buildSSECallbacks(aiMsgId, userMsgId) {
      let finalized = false
      return {
        onTextDelta: (content) => {
          this.appendToTypewriter(aiMsgId, content)
        },

        onToolCall: (data) => {
          this.handleToolCallEvent(aiMsgId, data)
        },

        onDone: (fullContent) => {
          if (finalized) return
          finalized = true
          this.flushTypewriter()
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

        onError: (message) => {
          if (finalized) return
          finalized = true
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

    // ==================== Tool Call Handling ====================

    handleToolCallEvent(aiMsgId, data) {
      const msg = this.messages.find(m => m.id === aiMsgId)
      if (!msg) return

      const { id, tool, status, success, result, arguments: args, display_name, requires_confirmation, message } = data

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

        const toolCall = { id, tool, arguments: args, status: 'running', display_name, requires_confirmation }

        if (MEMORY_TOOLS.has(tool)) {
          this.memoryToolStartTimes = { ...this.memoryToolStartTimes, [id]: Date.now() }
        }

        msg.streamSegments.push({ type: 'tool', toolCall })
        this.activeToolCalls.push(toolCall)

      } else if (status === 'pending_confirmation') {
        const toolCall = this.activeToolCalls.find(tc => tc.id === id)
        if (toolCall) {
          toolCall.status = 'pending_confirmation'
          toolCall.arguments = args
          toolCall.display_name = display_name
          toolCall.requires_confirmation = true
        }

        if (msg.streamSegments) {
          const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === id)
          if (seg && toolCall) {
            seg.toolCall = { ...toolCall }
          }
        }

      } else if (status === 'done') {
        msg.isWaitingOutput = true

        const toolCall = this.activeToolCalls.find(tc => tc.id === id)
        if (toolCall) {
          toolCall.status = 'done'
          toolCall.success = success
          toolCall.result = result
          toolCall.message = message

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

    async handleToolConfirm(msgId, toolCall) {
      try {
        const result = await confirmToolExecution(this.conversationId, toolCall.id, {
          tool_name: toolCall.tool,
          arguments: toolCall.arguments,
          confirmed: true
        })

        toolCall.status = 'done'
        toolCall.success = result.success
        toolCall.message = result.message
        toolCall.result = result.data

        const msg = this.messages.find(m => m.id === msgId)
        if (msg && msg.streamSegments) {
          const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
          if (seg) {
            seg.toolCall = { ...toolCall }
          }
        }
        if (msg && msg.segments) {
          const seg = msg.segments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
          if (seg) {
            seg.toolCall = { ...toolCall }
          }
        }

        this.$forceUpdate()

        if (result.data?.action === 'navigate_to_space_chat') {
          setTimeout(() => {
            uni.reLaunch({ url: `/pages/study/study?spaceId=${result.data.space_id}` })
          }, 1200)
        }
      } catch (err) {
        uni.showToast({ title: err.message || 'Operation failed', icon: 'none' })
        toolCall.status = 'done'
        toolCall.success = false
        toolCall.message = 'Operation failed'
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
        // Ignore rejection errors
      }

      toolCall.status = 'done'
      toolCall.success = false
      toolCall.message = 'User cancelled the operation'

      const msg = this.messages.find(m => m.id === msgId)
      if (msg && msg.streamSegments) {
        const seg = msg.streamSegments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
        if (seg) {
          seg.toolCall = { ...toolCall }
        }
      }
      if (msg && msg.segments) {
        const seg = msg.segments.find(s => s.type === 'tool' && s.toolCall && s.toolCall.id === toolCall.id)
        if (seg) {
          seg.toolCall = { ...toolCall }
        }
      }

      this.$forceUpdate()
    },

    handleSpaceClick(space) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${space.id}` })
    },

    // ==================== Message Segments ====================

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
      if (TOOL_ICON_SVGS[toolName]) return TOOL_ICON_SVGS[toolName]
      if (MEMORY_TOOLS.has(toolName)) return TOOL_ICON_SVGS.memory
      return TOOL_ICON_SVGS.default
    },

    getToolCardClass(toolCall) {
      if (toolCall.status === 'running') return 'tool-call-running'
      if (toolCall.status === 'pending_confirmation') return 'tool-call-pending'
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

    getConfirmationText(toolCall) {
      if (toolCall.tool === 'rebind_to_learning_space') {
        return `Bind conversation to "${toolCall.arguments?.space_name || 'learning space'}"?`
      }
      if (toolCall.tool === 'create_learning_space') {
        return `Create learning space "${toolCall.arguments?.name || 'new space'}"?`
      }
      return 'Confirm this operation?'
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

    // ==================== Scroll ====================

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
      this.flushTypewriter()

      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false

      const streamingMsg = this.messages.find(m => m.isStreaming)
      if (streamingMsg) {
        streamingMsg.isStreaming = false
        streamingMsg.isWaitingOutput = false
        if (!streamingMsg.content || streamingMsg.content.trim() === '') {
          streamingMsg.content = 'Response stopped by user.'
        }
        const streamIdx = this.messages.indexOf(streamingMsg)
        if (streamIdx > 0) {
          const prevMsg = this.messages[streamIdx - 1]
          if (prevMsg.role === 'user') {
            prevMsg.isFailed = true
          }
        }
      }
    },

    // ==================== Resend ====================

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
          this.messages = this.messages.filter((_, i) => i !== msgIdx + 1)
        }
      }

      const text = msg.content
      const attachmentIds = (msg.attachments && msg.attachments.length > 0)
        ? msg.attachments.map(att => att.id).filter(Boolean)
        : []

      // Create conversation if needed
      if (!this.conversationId) {
        try {
          const conv = await createQuickChatConversation(text.slice(0, 50))
          this.conversationId = conv.id
        } catch {
          msg.isFailed = true
          this.isSending = false
          uni.showToast({ title: 'Failed to create conversation', icon: 'none' })
          return
        }
      }

      this.isStreaming = true

      const aiMsgId = this.nextId++
      this.messages = [...this.messages, {
        id: aiMsgId,
        role: 'ai',
        content: '',
        isStreaming: true,
        isWaitingOutput: true,
        isError: false,
        segments: null,
        streamSegments: null,
        toolCalls: null
      }]

      this.$nextTick(() => this.scrollToBottom())
      this.activeToolCalls = []

      const callbacks = this._buildSSECallbacks(aiMsgId, msg.id)
      this.cancelSSE = sendQuickChatMessage(
        this.conversationId, text, callbacks,
        attachmentIds.length > 0 ? attachmentIds : null
      )
    },

    // ==================== Conversation History ====================

    openHistoryPopup() {
      this.showHistoryPopup = true
      this.loadConversations()
    },

    async loadConversations() {
      this.isLoadingConversations = true
      try {
        const result = await getQuickChatConversations()
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

      this.flushTypewriter()
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []

      this.conversationId = conv.id
      this.messages = []
      this.nextId = 1
      this.showHistoryPopup = false
      this.loadConversationHistory()
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
          isFailed: false,
          attachments: m.attachments || [],
          created_at: m.created_at
        }))
        this.nextId = this.messages.length + 1
        this.$nextTick(() => this.scrollToBottom())
      } catch (err) {
        uni.showToast({ title: 'Failed to load history', icon: 'none' })
      } finally {
        this.isLoadingHistory = false
      }
    },

    handleNewConversation() {
      this.flushTypewriter()
      if (this.cancelSSE) {
        this.cancelSSE()
        this.cancelSSE = null
      }
      this.isStreaming = false
      this.isSending = false
      this.activeToolCalls = []
      this.cleanupPendingAttachments()

      this.messages = []
      this.conversationId = null
      this.nextId = 1
      this.inputText = ''

      // Re-add welcome message
      this.messages = [{
        id: this.nextId++,
        role: 'ai',
        content: `Hi! I'm your learning assistant. Here's what I can help with:

**Chat freely** - Ask me any study-related question
**Learning Spaces** - View, create, or jump into a learning space
**Remember preferences** - I'll remember your habits for next time

For deeper learning (knowledge graphs, quizzes, document search), enter a specific learning space. What would you like to ask?`,
        isWelcome: true
      }]
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
      if (this.isSending) return
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
        uni.showToast({ title: 'Max 9 attachments', icon: 'none' })
        return
      }

      const filesToUpload = files.slice(0, remaining)

      for (const file of filesToUpload) {
        if (file.size > 10 * 1024 * 1024) {
          uni.showToast({ title: `${file.name} exceeds 10MB limit`, icon: 'none' })
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
          uni.showToast({ title: err.message || 'Upload failed', icon: 'none' })
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

    cleanupPendingAttachments() {
      this.pendingAttachments.forEach(a => { if (a.localPreview) URL.revokeObjectURL(a.localPreview) })
      this.pendingAttachments = []
      this.showAttachMenu = false
    },

    // ==================== Utility ====================

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

    previewImage(url) {
      uni.previewImage({ urls: [url], current: url })
    },

    openFileUrl(url) {
      window.open(url, '_blank')
    }
  }
}
</script>

<style scoped>
.quick-chat-page {
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
.quick-chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 1;
}

/* Header */
.quick-chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-back-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.header-back-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.header-back-icon {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.7);
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: #FFFFFF;
}

.header-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

/* Chat Messages Container (centered) */
.chat-messages-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 95%;
  width: 95%;
  margin: 0 auto;
  min-height: 0;
  padding: 0 28px 28px;
  box-sizing: border-box;
}

/* Chat Messages List */
.chat-messages-list {
  flex: 1;
  min-height: 0;
  padding: 16px 0;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
  width: 100%;
}

/* Custom Scrollbar */
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
  flex-direction: column;
  margin-bottom: 12px;
  max-width: 100%;
  box-sizing: border-box;
}

.message-row-left {
  align-items: flex-start;
}

.message-row-right {
  align-items: flex-end;
}

/* User bubble row with retry button */
.user-bubble-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  max-width: 85%;
  margin-left: auto;
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
}

.bubble-ai {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom-left-radius: 4px;
}

/* User message attachments */
.msg-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.msg-attach-img {
  width: 120px;
  height: 90px;
  border-radius: 8px;
  cursor: pointer;
}

.msg-attach-file {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  cursor: pointer;
}

.msg-attach-file-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
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

.tool-call-pending {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.08);
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

.tool-status-pending {
  color: rgba(245, 158, 11, 0.9);
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

/* Tool confirmation */
.tool-confirm-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.tool-confirm-info {
  margin-bottom: 8px;
}

.tool-confirm-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.4;
}

.tool-confirm-buttons {
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.tool-btn {
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.tool-btn-text {
  font-size: 12px;
  font-weight: 500;
}

.tool-btn-cancel {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.tool-btn-cancel:hover {
  background: rgba(255, 255, 255, 0.12);
}

.tool-btn-cancel .tool-btn-text {
  color: rgba(255, 255, 255, 0.7);
}

.tool-btn-confirm {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.35);
}

.tool-btn-confirm:hover {
  background: rgba(59, 130, 246, 0.3);
}

.tool-btn-confirm .tool-btn-text {
  color: rgba(59, 130, 246, 0.95);
}

/* Tool result */
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

/* Tool spaces list */
.tool-spaces-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-space-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.tool-space-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.tool-space-color {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tool-space-name {
  flex: 1;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-space-arrow {
  width: 12px;
  height: 12px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
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

/* AI message actions */
.ai-msg-actions {
  display: flex;
  flex-direction: row;
  gap: 8px;
  margin-top: 4px;
  padding-left: 4px;
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
  padding: 10px 0;
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

/* Chat Header Buttons */
.chat-header-btn-wrap {
  position: relative;
}

.chat-header-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.chat-header-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.chat-header-icon {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.6);
}

/* History Backdrop */
.history-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 90;
}

/* History Popup */
.history-popup {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
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
  padding: 8px 0 4px;
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
.attach-menu-icon { font-size: 16px; }
.attach-menu-label { font-size: 13px; color: rgba(255, 255, 255, 0.85); }

.attach-menu-fade-enter-active,
.attach-menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.attach-menu-fade-enter-from,
.attach-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

/* Attach menu backdrop */
.attach-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
}
</style>
