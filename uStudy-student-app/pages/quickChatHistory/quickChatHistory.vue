<template>
  <view class="chat-history-page">
    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">快速对话记录</text>
      <view class="nav-right-placeholder"></view>
    </view>

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
        >
          <view class="conv-content">
            <text class="conv-title">{{ conv.title }}</text>
            <text class="conv-time">{{ formatTime(conv.updated_at) }}</text>
          </view>
          <view class="conv-delete" @click.stop="showDeleteOption(conv)">
            <image class="conv-delete-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>
    </scroll-view>

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
import { getQuickChatConversations, deleteConversation } from '@/api/chat'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'

export default {
  components: {
    UModal,
    UToast
  },

  data() {
    return {
      conversations: [],
      isLoading: true,
      showDeleteModal: false,
      selectedConvId: null,
      isDeleting: false,
      scrollTop: 0,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  onLoad() {
    this.loadConversations()
  },

  onShow() {
    if (!this.isLoading) {
      this.loadConversations()
    }
  },

  methods: {
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

    showDeleteOption(conv) {
      this.selectedConvId = conv.id
      this.showDeleteModal = true
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
        return date.toLocaleDateString('zh-CN', {
          month: 'numeric',
          day: 'numeric'
        })
      }
    }
  }
}
</script>

<style>
.chat-history-page {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A0A;
  position: relative;
  overflow: hidden;
}

/* Navigation Bar */
.nav-bar {
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

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
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
  color: rgba(255, 255, 255, 0.6);
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
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.empty-hint {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.4);
}

.empty-action {
  margin-top: 32rpx;
  padding: 20rpx 48rpx;
  background: rgba(255, 255, 255, 0.1);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 48rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

.empty-action:active {
  background: rgba(255, 255, 255, 0.15);
}

.empty-action-text {
  font-size: 28rpx;
  color: #ffffff;
  font-weight: 500;
}

/* Conversation List */
.conversation-list {
  position: absolute;
  top: calc(100vh * 3.5 / 26);
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
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.conv-delete {
  width: 44px;
  height: 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
  margin-left: 8rpx;
}

.conv-delete-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  transition: opacity 0.15s ease;
}
</style>
