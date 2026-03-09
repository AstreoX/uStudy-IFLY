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
      <view v-if="isCollaborative" class="collab-section">
        <view class="collab-card">
          <view class="collab-flag">
            <image class="collab-flag-icon" src="/static/icons/user.svg" mode="aspectFit"></image>
            <text class="collab-flag-text">协作空间</text>
          </view>
          <view class="collab-main">
            <view class="collab-copy">
              <text class="collab-title">{{ collaborationRoleLabel }}</text>
              <text class="collab-desc">{{ collaborationRoleHint }}</text>
            </view>
            <view class="collab-pill">
              <text class="collab-pill-text">{{ memberCount }} 人</text>
            </view>
          </view>
        </view>
      </view>

      <!-- Settings Section -->
      <view class="settings-section">
        <view class="settings-card">
          <view class="settings-item">
            <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/regular/brain.svg" mode="aspectFit"></image>
            <text class="item-label">记忆共享</text>
            <switch class="item-switch" :checked="memorySharing" :disabled="isUpdatingMemorySharing" @change="onMemorySharingChange" color="#22C55E" />
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

          <template v-if="isCollaborative">
            <view class="settings-divider"></view>

            <view class="settings-item" @click="handleCollaborationLeaderboard">
              <image class="item-icon" src="/static/icons/phosphor-icons/SVGs/fill/trophy-fill.svg" mode="aspectFit"></image>
              <text class="item-label">排行榜</text>
              <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
            </view>

            <view class="settings-divider"></view>

            <view class="settings-item" @click="handleCollaborationMembers">
              <image class="item-icon" src="/static/icons/user.svg" mode="aspectFit"></image>
              <text class="item-label">{{ isCollaborativeMember ? '协作成员' : '成员管理' }}</text>
              <text class="item-value">{{ memberCount }}人</text>
              <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
            </view>
          </template>

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
          <text class="danger-label">{{ dangerActionLabel }}</text>
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
              <image class="share-mode-icon" src="/static/icons/user.svg" mode="aspectFit"></image>
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
      :title="dangerModalTitle"
      :content="deleteModalContent"
      :confirm-text="dangerConfirmText"
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
import { deleteSpace, getSpace, getSpaceMembers, removeSpaceMember, updateSpace, generateShareCode } from '@/api/space'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import { useUserStore } from '@/store/user'
import { goBack } from '@/utils/navigation'

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
      isUpdatingMemorySharing: false,
      showDeleteModal: false,
      isDeleting: false,
      userRole: '',
      isCollaborative: false,
      memberCount: 1,
      currentUserId: '',
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
    isCollaborativeMember() {
      return this.isCollaborative && this.userRole && this.userRole !== 'owner'
    },

    collaborationRoleLabel() {
      if (this.isCollaborativeMember) {
        return '你正在参与一个协作学习空间'
      }
      if (this.isCollaborative) {
        return '你正在管理一个协作学习空间'
      }
      return ''
    },

    collaborationRoleHint() {
      if (this.isCollaborativeMember) {
        return '排行榜和成员列表已经迁到这里，你也可以在这里直接退出当前协作空间。'
      }
      if (this.isCollaborative) {
        return '排行榜和成员管理都已经收拢到设置页，方便在 app 端快速管理协作学习。'
      }
      return ''
    },

    dangerActionLabel() {
      return this.isCollaborativeMember ? '退出该协作空间' : '删除该学习空间'
    },

    dangerModalTitle() {
      return this.isCollaborativeMember ? '退出协作空间' : '删除学习空间'
    },

    dangerConfirmText() {
      return this.isCollaborativeMember ? '退出' : '删除'
    },

    deleteModalContent() {
      if (this.isCollaborativeMember) {
        return `确定要退出「${this.spaceName}」吗？退出后你将失去该协作空间的学习记录、资料和对话访问权限。`
      }
      return `确定要删除「${this.spaceName}」吗？此操作不可恢复，所有学习记录、知识图谱和对话记录将被永久删除。`
    }
  },

  onLoad(options) {
    this.spaceId = options.id || ''
    this.spaceName = options.name ? decodeURIComponent(options.name) : '该学习空间'
    this.currentColor = options.color ? decodeURIComponent(options.color) : ''
    const userStore = useUserStore()
    this.currentUserId = userStore.user?.id || ''
    this.loadSpaceSettings()
  },

  onShow() {
    if (this.spaceId) {
      this.loadSpaceSettings()
    }
  },

  methods: {
    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    async loadSpaceSettings() {
      try {
        const space = await getSpace(this.spaceId)
        this.currentColor = space.color || '#0F6FFF'
        this.memorySharing = !!space.memory_sharing_enabled
        this.isCollaborative = !!space.is_collaborative
        this.userRole = space.user_role || ''
        if (this.isCollaborative) {
          await this.loadMemberCount()
        } else {
          this.memberCount = 1
        }
      } catch (error) {
        this.currentColor = '#0F6FFF'
      }
    },

    async loadMemberCount() {
      try {
        const members = await getSpaceMembers(this.spaceId)
        const memberList = members?.data || members || []
        this.memberCount = Array.isArray(memberList) && memberList.length > 0 ? memberList.length : 1
      } catch (error) {
        this.memberCount = 1
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
      goBack()
    },

    async onMemorySharingChange(e) {
      if (!this.spaceId || this.isUpdatingMemorySharing) return

      const nextValue = !!e.detail.value
      const previousValue = this.memorySharing
      this.memorySharing = nextValue
      this.isUpdatingMemorySharing = true

      try {
        await updateSpace(this.spaceId, { memory_sharing_enabled: nextValue })
        this.showCustomToast(nextValue ? '已开启记忆共享' : '已关闭记忆共享', 'success')
      } catch (error) {
        this.memorySharing = previousValue
        this.showCustomToast(error.message || '更新失败，请重试', 'error')
      } finally {
        this.isUpdatingMemorySharing = false
      }
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

    handleCollaborationLeaderboard() {
      uni.navigateTo({
        url: `/pages/spaceLeaderboard/spaceLeaderboard?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
      })
    },

    handleCollaborationMembers() {
      uni.navigateTo({
        url: `/pages/spaceMembers/spaceMembers?spaceId=${this.spaceId}&spaceName=${encodeURIComponent(this.spaceName)}`
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
        if (this.isCollaborativeMember) {
          if (!this.currentUserId) {
            throw new Error('当前用户信息缺失，无法退出协作空间')
          }
          await removeSpaceMember(this.spaceId, this.currentUserId)
        } else {
          await deleteSpace(this.spaceId)
        }
        this.showDeleteModal = false
        this.showCustomToast(this.isCollaborativeMember ? '已退出协作空间' : '学习空间已删除', 'success')

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
  padding-bottom: calc(100vh * 0.5 / 26);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.settings-nav-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: -70rpx;
  z-index: -1;
  background: linear-gradient(
    to bottom,
    rgba(10, 10, 10, 0.6) 0%,
    rgba(10, 10, 10, 0.45) 50%,
    rgba(10, 10, 10, 0) 100%
  );
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 0%, black 50%, transparent 100%);
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
  .settings-nav-bar::before {
    background: linear-gradient(
      to bottom,
      rgba(10, 10, 10, 0.95) 0%,
      rgba(10, 10, 10, 0.8) 50%,
      rgba(10, 10, 10, 0) 100%
    );
  }

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

.collab-section {
  margin: 0 calc(100vw / 24) 24rpx;
}

.collab-card {
  padding: 28rpx;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.16) 0%, rgba(132, 250, 176, 0.08) 100%);
  border: 1rpx solid rgba(91, 140, 255, 0.18);
  border-radius: 28rpx;
  -webkit-backdrop-filter: blur(22px);
  backdrop-filter: blur(22px);
  box-shadow: 0 18rpx 48rpx rgba(0, 0, 0, 0.14);
}

.collab-flag {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  height: 52rpx;
  padding: 0 18rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.08);
}

.collab-flag-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
}

.collab-flag-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.78);
}

.collab-main {
  margin-top: 18rpx;
  display: flex;
  align-items: flex-start;
  gap: 18rpx;
}

.collab-copy {
  flex: 1;
}

.collab-title {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
}

.collab-desc {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.58);
}

.collab-pill {
  min-width: 104rpx;
  height: 56rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(91, 140, 255, 0.16);
  border: 1rpx solid rgba(91, 140, 255, 0.22);
}

.collab-pill-text {
  font-size: 24rpx;
  color: #b8cbff;
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

.item-value {
  margin-right: 12rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.42);
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
