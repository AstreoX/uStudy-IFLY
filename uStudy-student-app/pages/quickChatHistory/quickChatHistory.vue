<template>
  <view class="chat-history-page" :class="pageThemeClass">
    <view class="history-bg">
      <view class="bg-mesh"></view>
      <view class="bg-glow bg-glow-blue"></view>
      <view class="bg-glow bg-glow-violet"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="nav-bar">
      <template v-if="!isSearching">
        <view class="nav-main">
          <view class="nav-left" @click="goBack">
            <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
          </view>
          <view class="nav-title-wrap">
            <text class="nav-title-main">快速对话记录</text>
            <text class="nav-title-sub">快速对话</text>
          </view>
        </view>
        <view class="nav-right" @click="handleSearch">
          <image class="nav-icon nav-icon-search" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
        </view>
      </template>
      <template v-else>
        <view class="search-bar">
          <image class="search-bar-icon" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
          <input
            class="search-input"
            v-model="searchQuery"
            placeholder="搜索对话..."
            placeholder-class="search-placeholder"
            focus
            confirm-type="search"
            @input="onSearchInput"
            @confirm="doSearch"
          />
          <view v-if="searchQuery" class="search-clear" @click="clearSearchQuery">
            <image class="search-clear-icon" src="/static/icons/phosphor-icons/SVGs/regular/x-circle.svg" mode="aspectFit"></image>
          </view>
        </view>
        <view class="search-cancel" @click="cancelSearch">
          <text class="search-cancel-text">取消</text>
        </view>
      </template>
    </view>

    <!-- Search Results -->
    <template v-if="isSearching">
      <view v-if="isSearchLoading" class="loading-container">
        <view class="loading-spinner"></view>
        <text class="loading-text">搜索中...</text>
      </view>
      <view v-else-if="searchQuery && searchResults.length === 0 && hasSearched" class="empty-container">
        <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/magnifying-glass.svg" mode="aspectFit"></image>
        <text class="empty-text">未找到相关对话</text>
        <text class="empty-hint">试试其他关键词</text>
      </view>
      <scroll-view v-else-if="searchResults.length > 0" class="conversation-list" scroll-y>
        <view class="list-content">
          <view
            v-for="item in searchResults"
            :key="item.id"
            class="conversation-item search-result-item"
            @click="openConversation(item)"
          >
            <view class="conv-content search-result-content">
              <view class="search-result-header">
                <text class="conv-title">{{ item.title }}</text>
                <text class="conv-time">{{ formatTime(item.updated_at) }}</text>
              </view>
              <view v-if="item.matching_messages && item.matching_messages.length > 0" class="search-snippets">
                <view
                  v-for="(msg, idx) in item.matching_messages.slice(0, 3)"
                  :key="msg.id || idx"
                  class="search-snippet"
                >
                  <text class="snippet-role">{{ msg.role === 'user' ? '你' : 'AI' }}:</text>
                  <text class="snippet-text">{{ msg.snippet }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>
      </scroll-view>
    </template>

    <!-- Normal List -->
    <template v-else>
      <!-- Loading State -->
      <view v-if="isLoading" class="loading-container">
        <view class="loading-spinner"></view>
        <text class="loading-text">加载中...</text>
      </view>

      <!-- Empty State -->
      <view v-else-if="conversations.length === 0" class="empty-container">
        <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/chats.svg" mode="aspectFit"></image>
        <text class="empty-text">暂无对话记录</text>
        <text class="empty-hint">点击下方按钮开始新对话</text>
        <view class="empty-action" @click="createNewConversation">
          <text class="empty-action-text">开始新对话</text>
        </view>
      </view>

      <!-- Conversation List -->
      <scroll-view v-else class="conversation-list" scroll-y :scroll-top="scrollTop" @scrolltoupper="onScrollToUpper">
        <view class="list-content">
          <view
            v-for="conv in conversations"
            :key="conv.id"
            class="conversation-item"
            @click="openConversation(conv)"
            @longpress.stop="showConvActions(conv)"
          >
            <view class="conv-content">
              <text class="conv-title">{{ conv.title }}</text>
              <text class="conv-time">{{ formatTime(conv.updated_at) }}</text>
            </view>
          </view>
        </view>
      </scroll-view>
    </template>

    <!-- Conversation Action Sheet -->
    <u-action-sheet
      :visible="showActionSheet"
      :items="actionSheetItems"
      @select="onActionSelect"
      @close="showActionSheet = false"
    />

    <!-- Rename Modal -->
    <u-input-modal
      :visible="showRenameModal"
      title="重命名对话"
      :value="renameTitle"
      placeholder="输入新标题"
      :max-length="200"
      :min-length="1"
      :multiline="false"
      @confirm="doRenameConversation"
      @close="showRenameModal = false"
    />

    <!-- Delete Confirmation Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除对话"
      content="确定要删除这个对话吗？此操作不可恢复。"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteConversation"
      @close="showDeleteModal = false"
    />

    <!-- Toast -->
    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import { getQuickChatConversations, deleteConversation, updateConversation, searchQuickChatConversations } from '@/api/chat'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import UActionSheet from '@/components/u-action-sheet/u-action-sheet.vue'
import UInputModal from '@/components/u-input-modal/u-input-modal.vue'
import { getStoredThemeMode } from '@/utils/themeMode'

export default {
  components: {
    UModal,
    UToast,
    UActionSheet,
    UInputModal
  },

  data() {
    return {
      conversations: [],
      homeThemeMode: 'dark',
      isLoading: true,
      showDeleteModal: false,
      selectedConvId: null,
      isDeleting: false,
      showActionSheet: false,
      actionSheetItems: [
        { text: '重命名', icon: 'pencil-simple' },
        { text: '删除', icon: 'trash', danger: true }
      ],
      selectedConv: null,
      showRenameModal: false,
      renameTitle: '',
      isRenaming: false,
      scrollTop: 0,
      isSearching: false,
      searchQuery: '',
      searchResults: [],
      isSearchLoading: false,
      hasSearched: false,
      searchTimer: null,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  onLoad() {
    this.restoreThemeMode()
    this.loadConversations()
  },

  onShow() {
    this.restoreThemeMode()
    if (!this.isLoading) {
      this.loadConversations()
    }
  },

  computed: {
    isLightTheme() {
      return this.homeThemeMode === 'light'
    },
    pageThemeClass() {
      return this.isLightTheme ? 'theme-light' : 'theme-dark'
    }
  },

  methods: {
    restoreThemeMode() {
      this.homeThemeMode = getStoredThemeMode('dark')
      this.syncThemeSystemUi(this.homeThemeMode)
    },

    syncThemeSystemUi(mode) {
      const isLight = mode === 'light'
      // #ifdef APP-PLUS
      plus.navigator.setStatusBarStyle(isLight ? 'dark' : 'light')
      plus.navigator.setStatusBarBackground(isLight ? '#F3EDE3' : '#1D1E20')
      // #endif
    },

    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack({ delta: 1 })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    async loadConversations() {
      this.isLoading = true
      try {
        const result = await getQuickChatConversations()
        this.conversations = result.conversations || []
      } catch (err) {
        this.showCustomToast(err.message || '加载失败', 'error')
      } finally {
        this.isLoading = false
      }
    },

    createNewConversation() {
      uni.navigateTo({
        url: '/pages/quickChat/quickChat'
      })
    },

    openConversation(conv) {
      uni.navigateTo({
        url: `/pages/quickChat/quickChat?conversationId=${conv.id}`
      })
    },

    showConvActions(conv) {
      this.selectedConv = conv
      this.selectedConvId = conv.id
      this.showActionSheet = true
    },

    onActionSelect(index) {
      this.showActionSheet = false
      if (index === 0) {
        this.renameTitle = this.selectedConv?.title || ''
        this.showRenameModal = true
      } else if (index === 1) {
        this.showDeleteModal = true
      }
    },

    async doRenameConversation(newTitle) {
      if (this.isRenaming || !this.selectedConv) return
      this.isRenaming = true

      try {
        await updateConversation(this.selectedConv.id, { title: newTitle })
        const conv = this.conversations.find(c => c.id === this.selectedConv.id)
        if (conv) {
          conv.title = newTitle
        }
        this.showRenameModal = false
        this.showCustomToast('已重命名', 'success')
      } catch (err) {
        this.showCustomToast(err.message || '重命名失败', 'error')
      } finally {
        this.isRenaming = false
      }
    },

    handleSearch() {
      this.isSearching = true
      this.searchQuery = ''
      this.searchResults = []
      this.hasSearched = false
    },

    cancelSearch() {
      this.isSearching = false
      this.searchQuery = ''
      this.searchResults = []
      this.hasSearched = false
      this.isSearchLoading = false
      if (this.searchTimer) {
        clearTimeout(this.searchTimer)
        this.searchTimer = null
      }
    },

    clearSearchQuery() {
      this.searchQuery = ''
      this.searchResults = []
      this.hasSearched = false
    },

    onSearchInput() {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer)
      }
      if (!this.searchQuery.trim()) {
        this.searchResults = []
        this.hasSearched = false
        return
      }
      this.searchTimer = setTimeout(() => {
        this.doSearch()
      }, 300)
    },

    async doSearch() {
      const query = this.searchQuery.trim()
      if (!query) return

      this.isSearchLoading = true
      try {
        const result = await searchQuickChatConversations(query)
        this.searchResults = result.items || []
      } catch (err) {
        this.showCustomToast(err.message || '搜索失败', 'error')
        this.searchResults = []
      } finally {
        this.isSearchLoading = false
        this.hasSearched = true
      }
    },

    async doDeleteConversation() {
      if (this.isDeleting || !this.selectedConvId) return
      this.isDeleting = true

      try {
        await deleteConversation(this.selectedConvId)
        this.conversations = this.conversations.filter(c => c && c.id !== this.selectedConvId)
        this.showDeleteModal = false
        this.showCustomToast('已删除', 'success')
      } catch (err) {
        this.showCustomToast(err.message || '删除失败', 'error')
      } finally {
        this.isDeleting = false
      }
    },

    onScrollToUpper() {
      // Pull-to-refresh could be implemented here
    },

    formatTime(dateStr) {
      if (!dateStr) return ''

      const date = new Date(dateStr)
      if (Number.isNaN(date.getTime())) return ''
      const now = new Date()
      const diffMs = now - date
      const diffMins = Math.floor(diffMs / (1000 * 60))
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

      if (diffMins < 1) {
        return '刚刚'
      } else if (diffMins < 60) {
        return `${diffMins}分钟前`
      } else if (diffHours < 24) {
        return `${diffHours}小时前`
      } else if (diffDays === 1) {
        return '昨天'
      } else if (diffDays < 7) {
        return `${diffDays}天前`
      } else {
        const year = date.getFullYear()
        const month = date.getMonth() + 1
        const day = date.getDate()

        if (year !== now.getFullYear()) {
          return `${year}年${month}月${day}日`
        }

        return `${month}月${day}日`
      }
    }
  }
}
</script>

<style scoped>
.chat-history-page {
  width: 100%;
  min-height: 100vh;
  background-color: rgb(29, 30, 32);
  position: relative;
  overflow: hidden;
}

.history-bg {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  pointer-events: none;
}

.bg-mesh {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background:
    radial-gradient(circle at 82% 14%, rgba(74, 108, 247, 0.08) 0%, rgba(74, 108, 247, 0) 32%),
    radial-gradient(circle at 12% 100%, rgba(99, 102, 241, 0.05) 0%, rgba(99, 102, 241, 0) 36%);
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(130rpx);
  opacity: 0.2;
}

.bg-glow-blue {
  top: 120rpx;
  right: -90rpx;
  width: 320rpx;
  height: 320rpx;
  background: rgba(74, 108, 247, 0.12);
}

.bg-glow-violet {
  bottom: 180rpx;
  left: -90rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(123, 97, 255, 0.08);
}

/* Navigation Bar */
.nav-bar {
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

.nav-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: -70rpx;
  z-index: -1;
  background: linear-gradient(
    to bottom,
    rgba(29, 30, 32, 0.56) 0%,
    rgba(29, 30, 32, 0.4) 50%,
    rgba(29, 30, 32, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(29, 30, 32, 0.82) 0%,
      rgba(29, 30, 32, 0.66) 50%,
      rgba(29, 30, 32, 0) 100%
    );
  }
}

.nav-main {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-width: 0;
  flex: 1;
}

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
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
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  outline: 1rpx solid rgba(255, 255, 255, 0.04);
  outline-offset: 1rpx;
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
  flex-shrink: 0;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-right {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-title-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-icon-search {
  filter: brightness(0) invert(1);
}

.nav-title-main {
  font-size: 34rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.2;
}

.nav-title-sub {
  max-width: 100%;
  font-size: 22rpx;
  line-height: 1.25;
  color: rgba(248, 248, 248, 0.52);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Loading State */
.loading-container {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
}

.loading-spinner {
  width: 64rpx;
  height: 64rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.1);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.56);
}

/* Empty State */
.empty-container {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 0 64rpx;
}

.empty-icon {
  width: 120rpx;
  height: 120rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  margin-bottom: 16rpx;
}

.empty-text {
  font-size: 32rpx;
  color: rgb(248, 248, 248);
  font-weight: 500;
}

.empty-hint {
  font-size: 26rpx;
  color: rgba(248, 248, 248, 0.46);
}

.empty-action {
  margin-top: 32rpx;
  padding: 20rpx 48rpx;
  background: rgb(46, 46, 48);
  border: 1.5rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 48rpx;
  box-shadow:
    inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
    0 2rpx 8rpx rgba(0, 0, 0, 0.12);
}

.empty-action:active {
  background: rgb(56, 56, 59);
}

.empty-action-text {
  font-size: 28rpx;
  color: rgb(248, 248, 248);
  font-weight: 500;
}

/* Conversation List */
.conversation-list {
  position: absolute;
  top: calc(100vh * 4.2 / 26);
  left: 0;
  right: 0;
  bottom: 0;
}

.list-content {
  padding-bottom: env(safe-area-inset-bottom);
}

.conversation-item {
  display: flex;
  align-items: center;
  padding: 20rpx 32rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
  transition: background-color 0.15s ease;
}

.conversation-item:active {
  background: rgba(255, 255, 255, 0.04);
}

.conversation-item:last-child {
  border-bottom: none;
}

.conv-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  overflow: hidden;
}

.conv-title {
  flex: 1;
  font-size: 30rpx;
  color: rgb(248, 248, 248);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

/* Search Bar */
.search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12rpx;
  height: 72rpx;
  padding: 0 20rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 36rpx;
}

.search-bar-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
  color: rgb(248, 248, 248);
  background: transparent;
}

.search-placeholder {
  color: rgba(248, 248, 248, 0.36);
}

.search-clear {
  width: 40rpx;
  height: 40rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}

.search-clear-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
}

.search-cancel {
  flex-shrink: 0;
  padding: 0 16rpx;
  height: 72rpx;
  display: flex;
  align-items: center;
}

.search-cancel-text {
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.7);
}

/* Search Results */
.search-result-item {
  flex-direction: column;
  align-items: stretch;
}

.search-result-content {
  flex-direction: column;
  align-items: stretch;
  gap: 12rpx;
}

.search-result-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.search-snippets {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  padding-left: 4rpx;
}

.search-snippet {
  display: flex;
  flex-direction: row;
  gap: 8rpx;
  overflow: hidden;
}

.snippet-role {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
  font-weight: 500;
}

.snippet-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.36);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.chat-history-page.theme-light {
  background-color: #F3EDE3;
}

.chat-history-page.theme-light .bg-mesh {
  background:
    radial-gradient(circle at 82% 14%, rgba(47, 110, 234, 0.1) 0%, rgba(47, 110, 234, 0) 32%),
    radial-gradient(circle at 12% 100%, rgba(199, 119, 22, 0.08) 0%, rgba(199, 119, 22, 0) 36%);
}

.chat-history-page.theme-light .bg-glow-blue {
  background: rgba(47, 110, 234, 0.14);
}

.chat-history-page.theme-light .bg-glow-violet {
  background: rgba(199, 119, 22, 0.1);
}

.chat-history-page.theme-light .nav-bar::before {
  background: linear-gradient(
    to bottom,
    rgba(243, 237, 227, 0.92) 0%,
    rgba(243, 237, 227, 0.64) 50%,
    rgba(243, 237, 227, 0) 100%
  );
}

.chat-history-page.theme-light .nav-left,
.chat-history-page.theme-light .nav-right,
.chat-history-page.theme-light .search-bar,
.chat-history-page.theme-light .empty-action {
  background: rgba(255, 250, 244, 0.82);
  border-color: rgba(63, 53, 42, 0.1);
  outline-color: rgba(255, 255, 255, 0.72);
  box-shadow: 0 14rpx 36rpx rgba(118, 101, 80, 0.14);
}

.chat-history-page.theme-light .nav-icon,
.chat-history-page.theme-light .nav-icon-search,
.chat-history-page.theme-light .search-bar-icon,
.chat-history-page.theme-light .search-clear-icon,
.chat-history-page.theme-light .empty-icon {
  filter: brightness(0) saturate(100%);
}

.chat-history-page.theme-light .nav-title-main,
.chat-history-page.theme-light .empty-text,
.chat-history-page.theme-light .empty-action-text,
.chat-history-page.theme-light .conv-title {
  color: #1F1A16;
}

.chat-history-page.theme-light .nav-title-sub,
.chat-history-page.theme-light .loading-text,
.chat-history-page.theme-light .empty-hint,
.chat-history-page.theme-light .conv-time,
.chat-history-page.theme-light .search-cancel-text,
.chat-history-page.theme-light .snippet-role {
  color: rgba(31, 26, 22, 0.58);
}

.chat-history-page.theme-light .search-input {
  color: #1F1A16;
}

.chat-history-page.theme-light .search-placeholder,
.chat-history-page.theme-light .snippet-text {
  color: rgba(31, 26, 22, 0.42);
}

.chat-history-page.theme-light .loading-spinner {
  border-color: rgba(63, 53, 42, 0.12);
  border-top-color: #2F6EEA;
}

.chat-history-page.theme-light .conversation-item {
  border-bottom-color: rgba(63, 53, 42, 0.1);
}

.chat-history-page.theme-light .conversation-item:active {
  background: rgba(63, 53, 42, 0.05);
}
</style>
