<template>
  <view class="settings-page">
    <!-- Navigation Bar -->
    <view class="settings-nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">快速对话设置</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <!-- Settings Section -->
      <view class="settings-section">
        <view class="settings-card">
          <view class="settings-item" @click="handleChatHistory">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg" mode="aspectFit"></image>
            <text class="item-label">对话记录</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleBindSpace">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit"></image>
            <text class="item-label">绑定到学习空间</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>

      <!-- Danger Zone -->
      <view class="danger-section">
        <view class="danger-card" @click="handleDeleteChat">
          <image class="danger-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
          <text class="danger-label">删除对话</text>
        </view>
      </view>
    </view>

    <!-- Space Selector ActionSheet -->
    <u-action-sheet
      :visible="showSpaceSelector"
      :items="spaceSelectItems"
      @select="onSpaceSelect"
      @close="showSpaceSelector = false"
    />

    <!-- Delete Confirmation Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除对话"
      content="确定要删除这条对话吗？删除后无法恢复。"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteChat"
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
import UActionSheet from '@/components/u-action-sheet/u-action-sheet.vue'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import { getSpaces } from '@/api/space'
import { updateConversation, deleteConversation } from '@/api/chat'
import { goBack } from '@/utils/navigation'

export default {
  components: {
    UActionSheet,
    UModal,
    UToast
  },

  data() {
    return {
      chatId: '',
      conversationId: '',
      showDeleteModal: false,
      showSpaceSelector: false,
      availableSpaces: [],
      spaceSelectItems: [],
      isDeleting: false,
      isLoading: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      }
    }
  },

  async onLoad(options) {
    this.chatId = options.chatId || ''
    this.conversationId = options.conversationId || ''
    await this.loadSpaces()
  },

  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    goBack() {
      goBack()
    },

    async loadSpaces() {
      try {
        const result = await getSpaces()
        this.availableSpaces = result.spaces || result || []
      } catch (err) {
        this.showCustomToast(err.message || '加载学习空间失败', 'error')
      }
    },

    handleChatHistory() {
      uni.navigateTo({
        url: '/pages/quickChatHistory/quickChatHistory'
      })
    },

    handleBindSpace() {
      this.spaceSelectItems = this.availableSpaces.map(space => ({
        key: space.id,
        text: space.name,
        icon: 'books'
      }))
      this.spaceSelectItems.push({
        key: 'create',
        text: '创建新学习空间',
        icon: 'plus'
      })
      this.showSpaceSelector = true
    },

    async onSpaceSelect(index) {
      const item = this.spaceSelectItems[index]
      if (item.key === 'create') {
        uni.navigateTo({ url: '/pages/createSpace/createSpace' })
        return
      }

      if (!this.conversationId) {
        this.showCustomToast('当前对话未保存，请先发送消息', 'info')
        return
      }

      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      if (!uuidRegex.test(item.key)) {
        this.showCustomToast('无效的学习空间', 'error')
        return
      }

      if (this.isLoading) return
      this.isLoading = true

      try {
        await updateConversation(this.conversationId, { space_id: item.key })
        this.showCustomToast(`已绑定到「${item.text}」`, 'success')

        setTimeout(() => {
          uni.redirectTo({
            url: `/pages/spaceChat/spaceChat?id=${item.key}&name=${encodeURIComponent(item.text)}&conversationId=${this.conversationId}`
          })
        }, 1000)
      } catch (err) {
        this.showCustomToast(err.message || '绑定失败', 'error')
      } finally {
        this.isLoading = false
      }
    },

    handleDeleteChat() {
      if (!this.conversationId) {
        this.showCustomToast('当前对话未保存，无需删除', 'info')
        return
      }
      this.showDeleteModal = true
    },

    async doDeleteChat() {
      if (this.isDeleting || !this.conversationId) return
      this.isDeleting = true

      try {
        await deleteConversation(this.conversationId)
        this.showDeleteModal = false
        this.showCustomToast('对话已删除', 'success')

        setTimeout(() => {
          uni.reLaunch({ url: '/pages/index/index' })
        }, 1000)
      } catch (error) {
        this.showCustomToast(error.message || '删除失败，请重试', 'error')
      } finally {
        this.isDeleting = false
      }
    }
  }
}
</script>

<style>
.settings-page {
  width: 100%;
  min-height: 100vh;
  background-color: rgb(10, 10, 10);
  position: relative;
  overflow: hidden;
}

/* Navigation Bar */
.settings-nav-bar {
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

/* Content Area */
.content-area {
  position: relative;
  z-index: 1;
  width: 100%;
  padding-top: calc(100vh * 3.5 / 26);
  padding-bottom: env(safe-area-inset-bottom);
}

/* Settings Section */
.settings-section {
  margin: 0 calc(100vw / 24);
}

.settings-card {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  overflow: hidden;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .settings-card {
    background: rgba(80, 80, 95, 0.65);
  }
}

.settings-item {
  display: flex;
  align-items: center;
  padding: 32rpx;
}

.settings-item:active {
  background: rgba(255, 255, 255, 0.05);
}

.item-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 24rpx;
  filter: brightness(0) invert(1);
}

.item-label {
  flex: 1;
  font-size: 32rpx;
  color: #ffffff;
}

.item-arrow {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
}

.settings-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.1);
  margin-left: 100rpx;
}

/* Danger Section */
.danger-section {
  margin: 48rpx calc(100vw / 24) 0;
}

.danger-card {
  display: flex;
  align-items: center;
  padding: 32rpx;
  background: rgba(239, 68, 68, 0.15);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
  border-radius: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .danger-card {
    background: rgba(239, 68, 68, 0.25);
  }
}

.danger-card:active {
  background: rgba(239, 68, 68, 0.25);
}

.danger-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 24rpx;
  filter: invert(47%) sepia(82%) saturate(2476%) hue-rotate(332deg) brightness(97%) contrast(92%);
}

.danger-label {
  flex: 1;
  font-size: 32rpx;
  color: #EF4444;
  font-weight: 500;
}
</style>
