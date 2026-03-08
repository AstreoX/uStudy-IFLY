<template>
  <view class="settings-page">
    <!-- Navigation Bar -->
    <view class="settings-nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">学习空间设置</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Content -->
    <view class="content-area">
      <!-- Settings Section -->
      <view class="settings-section">
        <view class="settings-card">
          <view class="settings-item">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit"></image>
            <text class="item-label">记忆共享</text>
            <switch class="item-switch" :checked="memorySharing" @change="onMemorySharingChange" color="#22C55E" />
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleChatHistory">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/chats.svg" mode="aspectFit"></image>
            <text class="item-label">对话记录</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleKnowledgeBase">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/books.svg" mode="aspectFit"></image>
            <text class="item-label">知识库管理</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleTestManagement">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/exam.svg" mode="aspectFit"></image>
            <text class="item-label">测试管理</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleNoteManagement">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook.svg" mode="aspectFit"></image>
            <text class="item-label">笔记管理</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>

          <view class="settings-divider"></view>

          <view class="settings-item" @click="handleShareSpace">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/upload-simple.svg" mode="aspectFit"></image>
            <text class="item-label">分享空间</text>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>

      <!-- Color Scheme Section -->
      <view class="color-section">
        <text class="section-label">卡片配色</text>
        <view class="color-picker-card">
          <view class="color-swatches">
            <view
              v-for="scheme in colorSchemes"
              :key="scheme.hex"
              class="color-swatch"
              :class="{ 'swatch-selected': isColorSelected(scheme.hex), 'swatch-loading': isUpdatingColor && pendingColor === scheme.hex }"
              :style="{ background: scheme.gradient }"
              @click="selectColor(scheme.hex)"
            >
              <view v-if="isColorSelected(scheme.hex)" class="swatch-check">
                <image class="check-icon" src="/static/icons/phosphor-icons/SVGs/bold/check.svg" mode="aspectFit"></image>
              </view>
              <view v-if="isUpdatingColor && pendingColor === scheme.hex" class="swatch-loading-indicator"></view>
            </view>
          </view>
        </view>
      </view>

      <!-- Danger Zone -->
      <view class="danger-section">
        <view class="danger-card" @click="handleDeleteSpace">
          <image class="danger-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
          <text class="danger-label">删除该学习空间</text>
        </view>
      </view>
    </view>

    <!-- 分享模式选择弹窗 -->
    <view
      v-if="showShareModePopup"
      class="share-popup-overlay"
      :class="{ 'overlay-show': shareModePopupVisible }"
      @click="closeShareModePopup"
    >
      <view
        class="share-popup-card"
        :class="{ 'dialog-show': shareModePopupVisible }"
        @click.stop
      >
        <text class="share-popup-title">选择分享方式</text>
        <view class="share-mode-options">
          <view class="share-mode-option" @click="selectShareMode('clone')">
            <view class="share-mode-icon-wrap">
              <image class="share-mode-icon" src="/static/icons/phosphor-icons/SVGs/regular/copy.svg" mode="aspectFit"></image>
            </view>
            <view class="share-mode-info">
              <text class="share-mode-label">创建副本</text>
              <text class="share-mode-desc">对方导入后获得此空间的副本</text>
            </view>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
          <view class="settings-divider"></view>
          <view class="share-mode-option" @click="selectShareMode('collaborative')">
            <view class="share-mode-icon-wrap">
              <image class="share-mode-icon" src="/static/icons/phosphor-icons/SVGs/regular/users.svg" mode="aspectFit"></image>
            </view>
            <view class="share-mode-info">
              <text class="share-mode-label">共同学习</text>
              <text class="share-mode-desc">对方导入后加入此空间一起学习</text>
            </view>
            <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>
      </view>
    </view>

    <!-- 分享码弹窗 -->
    <view
      v-if="showSharePopup"
      class="share-popup-overlay"
      :class="{ 'overlay-show': sharePopupVisible }"
      @click="closeSharePopup"
    >
      <view
        class="share-popup-card"
        :class="{ 'dialog-show': sharePopupVisible }"
        @click.stop
      >
        <text class="share-popup-title">分享学习空间</text>
        <text class="share-popup-hint">{{ currentShareMode === 'collaborative' ? '对方导入后将加入此空间共同学习' : '将分享码发送给好友，即可导入此空间' }}</text>
        <view class="share-popup-code-box">
          <text class="share-popup-code">{{ displayShareCode }}</text>
        </view>
        <view class="share-popup-copy-btn" @click="handleCopyShareCode">
          <text class="share-popup-copy-btn-text">复制分享码</text>
        </view>
      </view>
    </view>

    <!-- Delete Confirmation Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除学习空间"
      :content="deleteModalContent"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteSpace"
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
import { deleteSpace, getSpace, updateSpace, generateShareCode } from '@/api/space'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'

export default {
  components: {
    UModal,
    UToast
  },

  data() {
    return {
      spaceId: '',
      spaceName: '',
      memorySharing: false,
      showDeleteModal: false,
      isDeleting: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      },
      colorSchemes: [
        { hex: '#0F6FFF', gradient: 'linear-gradient(to bottom right, #0F6FFF 0%, #B1DD8B 100%)' },
        { hex: '#A18CD1', gradient: 'linear-gradient(to bottom right, #A18CD1 0%, #FBC2EB 100%)' },
        { hex: '#FA709A', gradient: 'linear-gradient(to bottom right, #FA709A 0%, #FEE140 100%)' },
        { hex: '#84FAB0', gradient: 'linear-gradient(to bottom right, #84FAB0 0%, #38F9D7 100%)' },
        { hex: '#F43B37', gradient: 'linear-gradient(to bottom right, #F43B37 0%, #453A94 100%)' }
      ],
      currentColor: '',
      isUpdatingColor: false,
      pendingColor: '',
      // 分享弹窗
      showShareModePopup: false,
      shareModePopupVisible: false,
      showSharePopup: false,
      sharePopupVisible: false,
      displayShareCode: '',
      currentShareMode: 'clone',
      isGeneratingShareCode: false
    }
  },

  computed: {
    deleteModalContent() {
      return `确定要删除「${this.spaceName}」吗？此操作不可恢复，所有学习记录、知识图谱和对话记录将被永久删除。`
    }
  },

  onLoad(options) {
    this.spaceId = options.id || ''
    this.spaceName = options.name ? decodeURIComponent(options.name) : '该学习空间'
    this.currentColor = options.color ? decodeURIComponent(options.color) : ''

    if (!this.currentColor && this.spaceId) {
      this.loadSpaceColor()
    }
  },

  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    async loadSpaceColor() {
      try {
        const space = await getSpace(this.spaceId)
        this.currentColor = space.color || '#0F6FFF'
      } catch (error) {
        this.currentColor = '#0F6FFF'
      }
    },

    isColorSelected(hex) {
      return this.currentColor.toUpperCase() === hex.toUpperCase()
    },

    async selectColor(hex) {
      if (!this.spaceId || this.isColorSelected(hex) || this.isUpdatingColor) return

      this.isUpdatingColor = true
      this.pendingColor = hex

      try {
        await updateSpace(this.spaceId, { color: hex })
        this.currentColor = hex
        this.showCustomToast('配色已更新', 'success')
      } catch (error) {
        this.showCustomToast(error.message || '更新失败，请重试', 'error')
      } finally {
        this.isUpdatingColor = false
        this.pendingColor = ''
      }
    },

    goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack({ delta: 1 })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    onMemorySharingChange(e) {
      this.memorySharing = e.detail.value
    },

    handleChatHistory() {
      uni.navigateTo({
        url: `/pages/chatHistory/chatHistory?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
      })
    },

    handleKnowledgeBase() {
      uni.navigateTo({
        url: `/pages/knowledgeBase/knowledgeBase?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
      })
    },

    handleTestManagement() {
      uni.navigateTo({
        url: `/pages/quizList/quizList?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
      })
    },

    handleNoteManagement() {
      uni.navigateTo({
        url: `/pages/notesList/notesList?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
      })
    },

    handleShareSpace() {
      if (this.isGeneratingShareCode || !this.spaceId) return
      // Show mode selection popup first
      this.showShareModePopup = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.shareModePopupVisible = true
        }, 10)
      })
    },

    closeShareModePopup() {
      this.shareModePopupVisible = false
      setTimeout(() => {
        this.showShareModePopup = false
      }, 250)
    },

    async selectShareMode(mode) {
      this.closeShareModePopup()
      this.currentShareMode = mode
      this.isGeneratingShareCode = true
      try {
        const res = await generateShareCode(this.spaceId, mode)
        this.displayShareCode = res.display_code
        this.showSharePopup = true
        this.$nextTick(() => {
          setTimeout(() => {
            this.sharePopupVisible = true
          }, 10)
        })
      } catch (err) {
        this.showCustomToast('生成分享码失败', 'error')
      } finally {
        this.isGeneratingShareCode = false
      }
    },

    closeSharePopup() {
      this.sharePopupVisible = false
      setTimeout(() => {
        this.showSharePopup = false
      }, 250)
    },

    handleCopyShareCode() {
      uni.setClipboardData({
        data: this.displayShareCode,
        success: () => {
          this.showCustomToast('已复制分享码', 'success')
        }
      })
    },

    handleDeleteSpace() {
      this.showDeleteModal = true
    },

    async doDeleteSpace() {
      if (this.isDeleting) return
      this.isDeleting = true

      try {
        await deleteSpace(this.spaceId)
        this.showDeleteModal = false
        this.showCustomToast('学习空间已删除', 'success')

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
  background-color: rgb(24, 24, 24);
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

.item-switch {
  transform: scale(0.85);
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

/* Color Scheme Section */
.color-section {
  margin: 32rpx calc(100vw / 24) 0;
}

.section-label {
  display: block;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 16rpx;
  padding-left: 8rpx;
}

.color-picker-card {
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  padding: 24rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .color-picker-card {
    background: rgba(80, 80, 95, 0.65);
  }
}

.color-swatches {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
}

.color-swatch {
  flex: 1;
  aspect-ratio: 1;
  border-radius: 16rpx;
  position: relative;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 3rpx solid transparent;
}

.color-swatch:active {
  transform: scale(0.95);
}

.swatch-selected {
  border-color: rgba(255, 255, 255, 0.8);
  box-shadow: 0 0 20rpx rgba(255, 255, 255, 0.3);
}

.swatch-check {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40rpx;
  height: 40rpx;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.check-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
}

.swatch-loading {
  opacity: 0.6;
  pointer-events: none;
}

.swatch-loading-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 32rpx;
  height: 32rpx;
  border: 3rpx solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 分享模式选择 */
.share-mode-options {
  width: 100%;
}

.share-mode-option {
  display: flex;
  align-items: center;
  padding: 28rpx 24rpx;
}

.share-mode-option:active {
  background: rgba(255, 255, 255, 0.05);
}

.share-mode-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
}

.share-mode-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
}

.share-mode-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.share-mode-label {
  font-size: 30rpx;
  font-weight: 500;
  color: #ffffff;
}

.share-mode-desc {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.45);
}

/* 分享码弹窗 */
.share-popup-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 200ms ease;
}

.share-popup-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.share-popup-card {
  width: 560rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  box-shadow:
    0 16rpx 48rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  overflow: hidden;
  transform: translateY(40rpx) scale(0.95);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
  padding: 48rpx 40rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.share-popup-card.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .share-popup-card {
    background: rgba(30, 30, 45, 0.98);
  }
}

.share-popup-title {
  font-size: 36rpx;
  font-weight: 600;
  color: #ffffff;
  text-align: center;
  margin-bottom: 16rpx;
}

.share-popup-hint {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
  margin-bottom: 40rpx;
}

.share-popup-code-box {
  width: 100%;
  padding: 32rpx 0;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 16rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 32rpx;
}

.share-popup-code {
  font-size: 56rpx;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 8rpx;
  font-family: 'Courier New', Courier, monospace;
}

.share-popup-copy-btn {
  width: 100%;
  height: 88rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, rgba(0, 136, 255, 0.6) 0%, rgba(139, 92, 246, 0.5) 100%);
  border: 2rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 44rpx;
  box-shadow: 0 8rpx 32rpx rgba(0, 136, 255, 0.3);
}

.share-popup-copy-btn-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}
</style>
