<template>
  <view class="settings-page">
    <view class="settings-bg">
      <view class="bg-mesh"></view>
      <view class="bg-glow bg-glow-blue"></view>
      <view class="bg-glow bg-glow-violet"></view>
    </view>

    <view class="settings-nav">
      <view class="nav-back" @click="goBack">
        <image class="nav-icon" :src="getIconSrc('back')" mode="aspectFit"></image>
      </view>
      <view class="nav-copy">
        <text class="nav-title">学习空间设置</text>
        <text class="nav-subtitle">{{ spaceName || '当前学习空间' }}</text>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="content-scroll" scroll-y>
      <view class="content-body">
        <view class="overview-card">
          <view class="overview-top">
            <text class="overview-title">{{ spaceName || '当前学习空间' }}</text>
            <view
              class="overview-action"
              :class="{ 'overview-action-disabled': isGeneratingShareCode }"
              @click="handleShareSpace"
            >
              <image class="overview-action-icon" :src="getIconSrc('share')" mode="aspectFit"></image>
            </view>
          </view>

          <view class="overview-progress">
            <view class="overview-progress-meta">
              <text class="overview-progress-label">学习进度</text>
              <text class="overview-progress-value">{{ spaceProgress.percent }}%</text>
            </view>
            <view class="overview-progress-track">
              <view
                class="overview-progress-fill"
                :style="{ width: `${spaceProgress.percent}%` }"
              ></view>
            </view>
          </view>

          <view class="overview-stats-panel">
            <view v-for="stat in heroStats" :key="stat.label" class="hero-stat">
              <text class="hero-stat-value">{{ stat.value }}</text>
              <text class="hero-stat-label">{{ stat.label }}</text>
            </view>
          </view>
        </view>

        <view class="settings-section">
          <text class="section-caption">学习内容</text>
          <view class="settings-card">
            <template v-for="(item, index) in learningItems" :key="item.key">
              <view
                class="settings-row settings-row-pressable"
                @click="handleSettingAction(item)"
              >
                <view class="row-icon-wrap" :class="`row-icon-wrap-${item.tone}`">
                  <image class="item-icon" :src="getIconSrc(item.icon)" mode="aspectFit"></image>
                </view>

                <view class="row-copy">
                  <text class="row-title">{{ item.label }}</text>
                  <text class="row-desc">{{ item.description }}</text>
                </view>

                <text v-if="item.value" class="row-value">{{ item.value }}</text>
                <image class="item-arrow" :src="getIconSrc('chevron-right')" mode="aspectFit"></image>
              </view>

              <view
                v-if="index !== learningItems.length - 1"
                :key="`${item.key}-divider`"
                class="settings-divider"
              ></view>
            </template>
          </view>
        </view>

        <view v-if="collaborationItems.length > 0" class="settings-section">
          <text class="section-caption">{{ collaborationGroupLabel }}</text>
          <view class="settings-card">
            <template v-for="(item, index) in collaborationItems" :key="item.key">
              <view
                class="settings-row settings-row-pressable"
                @click="handleSettingAction(item)"
              >
                <view class="row-icon-wrap" :class="`row-icon-wrap-${item.tone}`">
                  <image class="item-icon" :src="getIconSrc(item.icon)" mode="aspectFit"></image>
                </view>

                <view class="row-copy">
                  <text class="row-title">{{ item.label }}</text>
                  <text class="row-desc">{{ item.description }}</text>
                </view>

                <text v-if="item.value" class="row-value">{{ item.value }}</text>
                <image class="item-arrow" :src="getIconSrc('chevron-right')" mode="aspectFit"></image>
              </view>

              <view
                v-if="index !== collaborationItems.length - 1"
                :key="`${item.key}-divider`"
                class="settings-divider"
              ></view>
            </template>
          </view>
        </view>

        <view class="settings-section">
          <text class="section-caption">空间外观</text>
          <view class="settings-card palette-card">
            <view class="palette-copy">
              <text class="palette-title">空间主题色</text>
              <text class="palette-desc">更新学习空间首页卡片和相关高亮颜色</text>
            </view>

            <view class="color-swatches">
              <view
                v-for="scheme in colorSchemes"
                :key="scheme.hex"
                class="color-swatch"
                :class="{
                  'swatch-selected': isColorSelected(scheme.hex),
                  'swatch-loading': isUpdatingColor && pendingColor === scheme.hex
                }"
                :style="{ background: scheme.gradient }"
                @click="selectColor(scheme.hex)"
              >
                <view v-if="isColorSelected(scheme.hex)" class="swatch-check">
                  <image class="check-icon" :src="getIconSrc('check')" mode="aspectFit"></image>
                </view>
                <view
                  v-if="isUpdatingColor && pendingColor === scheme.hex"
                  class="swatch-loading-indicator"
                ></view>
              </view>
            </view>
          </view>
        </view>

        <view class="danger-group">
          <view class="danger-card" @click="handleDeleteSpace">
            <view class="danger-icon-wrap">
              <image class="danger-icon" :src="getIconSrc('trash')" mode="aspectFit"></image>
            </view>
            <text class="danger-label">删除学习空间</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <view
      v-if="showShareModePopup"
      class="share-popup-overlay"
      :class="{ 'overlay-show': shareModePopupVisible }"
      @click="closeShareModePopup"
    >
      <view class="share-popup-card" :class="{ 'dialog-show': shareModePopupVisible }" @click.stop>
        <text class="share-popup-title">选择分享方式</text>
        <text class="share-popup-hint">选择生成导入副本，或直接邀请对方加入协作学习。</text>

        <view class="share-mode-options">
          <view class="share-mode-option" @click="selectShareMode('clone')">
            <view class="share-mode-icon-wrap row-icon-wrap-violet">
              <image class="share-mode-icon" :src="getIconSrc('copy')" mode="aspectFit"></image>
            </view>
            <view class="share-mode-info">
              <text class="share-mode-label">创建副本</text>
              <text class="share-mode-desc">对方导入后获得当前学习空间的副本</text>
            </view>
            <image class="item-arrow" :src="getIconSrc('chevron-right')" mode="aspectFit"></image>
          </view>

          <view class="settings-divider settings-divider-popup"></view>

          <view class="share-mode-option" @click="selectShareMode('collaborative')">
            <view class="share-mode-icon-wrap row-icon-wrap-blue">
              <image class="share-mode-icon" :src="getIconSrc('members')" mode="aspectFit"></image>
            </view>
            <view class="share-mode-info">
              <text class="share-mode-label">共同学习</text>
              <text class="share-mode-desc">对方导入后加入此空间并一起学习</text>
            </view>
            <image class="item-arrow" :src="getIconSrc('chevron-right')" mode="aspectFit"></image>
          </view>
        </view>
      </view>
    </view>

    <view
      v-if="showSharePopup"
      class="share-popup-overlay"
      :class="{ 'overlay-show': sharePopupVisible }"
      @click="closeSharePopup"
    >
      <view class="share-popup-card share-popup-card-code" :class="{ 'dialog-show': sharePopupVisible }" @click.stop>
        <text class="share-popup-title">分享学习空间</text>
        <text class="share-popup-hint">
          {{ currentShareMode === 'collaborative'
            ? '对方导入后将加入此空间共同学习'
            : '将分享码发送给好友，对方即可导入此空间副本' }}
        </text>

        <view class="share-popup-code-box">
          <text class="share-popup-code">{{ displayShareCode }}</text>
        </view>

        <view class="share-popup-copy-btn" @click="handleCopyShareCode">
          <text class="share-popup-copy-btn-text">复制分享码</text>
        </view>
      </view>
    </view>

    <u-modal
      :visible="showDeleteModal"
      :title="dangerModalTitle"
      :content="deleteModalContent"
      :confirm-text="dangerConfirmText"
      confirm-type="danger"
      @confirm="doDeleteSpace"
      @close="showDeleteModal = false"
    />

    <u-toast
      :visible="toast.visible"
      :message="toast.message"
      :type="toast.type"
      @close="toast.visible = false"
    />
  </view>
</template>

<script>
import {
  deleteSpace,
  generateShareCode,
  getQuizzesBySpace,
  getSpace,
  getSpaceDocuments,
  getSpaceMembers,
  removeSpaceMember,
  updateSpace
} from '@/api/space'
import { getSpaceConversations } from '@/api/chat'
import { getSpaceNotes } from '@/api/note'
import UModal from '@/components/u-modal/u-modal.vue'
import UToast from '@/components/u-toast/u-toast.vue'
import { useUserStore } from '@/store/user'
import { goBack } from '@/utils/navigation'

// Temporary icon paths. Replace these with Lucide SVGs later.
const ICON_SRC = {
  back: '/static/icons/phosphor-icons/SVGs/regular/caret-left.svg',
  share: '/static/icons/lucide/user-round-plus.svg',
  chat: '/static/icons/history.svg',
  knowledge: '/static/icons/lucide/database.svg',
  quiz: '/static/icons/phosphor-icons/SVGs/regular/exam.svg',
  note: '/static/icons/lucide/notebook-pen.svg',
  leaderboard: '/static/icons/phosphor-icons/SVGs/fill/trophy-fill.svg',
  members: '/static/icons/user.svg',
  copy: '/static/icons/phosphor-icons/SVGs/regular/copy.svg',
  trash: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
  check: '/static/icons/phosphor-icons/SVGs/bold/check.svg',
  'chevron-right': '/static/icons/phosphor-icons/SVGs/regular/caret-right.svg'
}

export default {
  components: {
    UModal,
    UToast
  },

  data() {
    return {
      spaceId: '',
      spaceName: '',
      spaceDescription: '',
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
        { hex: '#0F6FFF', gradient: 'linear-gradient(135deg, #0F6FFF 0%, #69B8FF 48%, #B1DD8B 100%)' },
        { hex: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6 0%, #C084FC 52%, #F9A8D4 100%)' },
        { hex: '#F97316', gradient: 'linear-gradient(135deg, #FBC2EB 0%, #A6C1EE 100%)' },
        { hex: '#10B981', gradient: 'linear-gradient(135deg, #10B981 0%, #2DD4BF 50%, #67E8F9 100%)' },
        { hex: '#EF4444', gradient: 'linear-gradient(135deg, #b721ff 0%, #21d4fd 100%)' }
      ],
      currentColor: '',
      isUpdatingColor: false,
      pendingColor: '',
      conversationCount: null,
      documentCount: null,
      quizCount: null,
      noteCount: null,
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

    heroStats() {
      return [
        { label: '知识资料', value: this.toDisplayCount(this.documentCount) },
        { label: '对话记录', value: this.toDisplayCount(this.conversationCount) },
        { label: '学习笔记', value: this.toDisplayCount(this.noteCount) }
      ]
    },

    spaceProgress() {
      const metrics = [
        { value: this.documentCount, target: 12, weight: 0.34 },
        { value: this.conversationCount, target: 18, weight: 0.24 },
        { value: this.noteCount, target: 12, weight: 0.22 },
        { value: this.quizCount, target: 8, weight: 0.20 }
      ]

      if (metrics.every((metric) => metric.value === null || metric.value === undefined)) {
        return { percent: 0 }
      }

      const percent = Math.round(metrics.reduce((total, metric) => {
        const value = typeof metric.value === 'number' ? metric.value : 0
        return total + Math.min(value / metric.target, 1) * metric.weight
      }, 0) * 100)

      return { percent: Math.max(0, Math.min(percent, 100)) }
    },

    learningItems() {
      return [
        {
          key: 'chat',
          icon: 'chat',
          label: '对话记录',
          description: '查看所有对话记录',
          value: this.toDisplayCount(this.conversationCount),
          action: 'handleChatHistory',
          tone: 'blue'
        },
        {
          key: 'knowledge',
          icon: 'knowledge',
          label: '知识库管理',
          description: '管理 AI 所参照的文档与链接',
          value: this.toDisplayCount(this.documentCount),
          action: 'handleKnowledgeBase',
          tone: 'green'
        },
        {
          key: 'quiz',
          icon: 'quiz',
          label: '测试管理',
          description: '查看并管理测试记录',
          value: this.toDisplayCount(this.quizCount),
          action: 'handleTestManagement',
          tone: 'violet'
        },
        {
          key: 'note',
          icon: 'note',
          label: '学习笔记',
          description: '管理笔记内容',
          value: this.toDisplayCount(this.noteCount),
          action: 'handleNoteManagement',
          tone: 'amber'
        }
      ]
    },

    collaborationItems() {
      const items = []

      if (this.isCollaborative) {
        items.push({
          key: 'leaderboard',
          icon: 'leaderboard',
          label: '排行榜',
          description: '查看成员活跃度和学习表现',
          action: 'handleCollaborationLeaderboard',
          tone: 'violet'
        })

        items.push({
          key: 'members',
          icon: 'members',
          label: this.isCollaborativeMember ? '协作成员' : '成员管理',
          description: this.isCollaborativeMember
            ? '查看当前成员列表与协作权限'
            : '管理成员加入状态与协作权限',
          value: `${this.memberCount}人`,
          action: 'handleCollaborationMembers',
          tone: 'blue'
        })
      }

      return items
    },

    collaborationGroupLabel() {
      return '协作'
    },

    dangerActionLabel() {
      return this.isCollaborativeMember ? '退出该协作空间' : '删除该学习空间'
    },

    dangerDescription() {
      return this.isCollaborativeMember
        ? '退出后你将失去该空间的学习记录、资料与对话访问权限。'
        : '删除后所有资料、测试、笔记与对话记录都将被永久移除。'
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
    getIconSrc(key) {
      return ICON_SRC[key] || ''
    },

    toDisplayCount(value) {
      if (value === null || value === undefined) return '--'
      if (value > 99) return '99+'
      return String(value)
    },

    showCustomToast(message, type = 'info') {
      this.toast = { visible: true, message, type }
    },

    async loadSpaceSettings() {
      if (!this.spaceId) return

      try {
        const space = await getSpace(this.spaceId)
        // 兼容旧版hex值，映射到新值
        const legacyColorMap = {
          '#A18CD1': '#8B5CF6',
          '#FA709A': '#F97316',
          '#84FAB0': '#10B981',
          '#F43B37': '#EF4444'
        }
        const rawColor = (space.color || '#0F6FFF').toUpperCase()
        this.currentColor = legacyColorMap[rawColor] || space.color || '#0F6FFF'
        this.isCollaborative = !!space.is_collaborative
        this.userRole = space.user_role || ''
        this.spaceDescription = space.description || ''

        await Promise.all([
          this.loadMemberCount(),
          this.loadOverviewCounts()
        ])
      } catch (error) {
        this.currentColor = '#0F6FFF'
        this.spaceDescription = ''
      }
    },

    async loadOverviewCounts() {
      const [chatResult, documentResult, quizResult, noteResult] = await Promise.allSettled([
        getSpaceConversations(this.spaceId),
        getSpaceDocuments(this.spaceId),
        getQuizzesBySpace(this.spaceId),
        getSpaceNotes(this.spaceId)
      ])

      this.conversationCount = this.extractCount(chatResult, 'conversations')
      this.documentCount = this.extractCount(documentResult, 'documents')
      this.quizCount = this.extractCount(quizResult)
      this.noteCount = this.extractCount(noteResult)
    },

    extractCount(result, key) {
      if (!result || result.status !== 'fulfilled') return 0

      const value = result.value

      if (typeof value?.total === 'number') return value.total
      if (key && Array.isArray(value?.[key])) return value[key].length
      if (Array.isArray(value)) return value.length

      return 0
    },

    async loadMemberCount() {
      if (!this.isCollaborative) {
        this.memberCount = 1
        return
      }

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

    handleSettingAction(item) {
      if (!item || !item.action) return
      if (typeof this[item.action] === 'function') {
        this[item.action]()
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
  position: relative;
  min-height: 100vh;
  background-color: rgb(29, 30, 32);
  overflow: hidden;
}

.settings-bg {
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

.settings-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: calc(100vh * 0.5 / 26);
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
}

.settings-nav::before {
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
  .settings-nav::before {
    background: linear-gradient(
      to bottom,
      rgba(29, 30, 32, 0.82) 0%,
      rgba(29, 30, 32, 0.66) 50%,
      rgba(29, 30, 32, 0) 100%
    );
  }
}

.nav-back {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
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
  transition: all 0.2s ease;
  color: rgb(248, 248, 248);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-back {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-copy {
  flex: 1;
  min-width: 0;
  margin-left: 16rpx;
  margin-right: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 4rpx;
  text-align: left;
}

.nav-spacer {
  width: 80rpx;
  height: 80rpx;
  margin-left: auto;
  flex-shrink: 0;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.2;
}

.nav-subtitle {
  max-width: 100%;
  font-size: 22rpx;
  line-height: 1.25;
  color: rgba(248, 248, 248, 0.52);
}

.content-scroll {
  position: relative;
  z-index: 1;
  height: 100vh;
}

.content-body {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
  padding:
    calc(100vh * 4.2 / 26)
    calc(100vw / 24)
    calc(env(safe-area-inset-bottom) + 42rpx);
}

.overview-card,
.settings-card,
.danger-card,
.share-popup-card {
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.overview-card {
  border-radius: 40rpx;
  padding: 36rpx;
}

.overview-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.overview-title {
  flex: 1;
  min-width: 0;
  font-size: 36rpx;
  font-weight: 600;
  line-height: 1.24;
  color: rgb(248, 248, 248);
}

.overview-action {
  width: 72rpx;
  height: 72rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24rpx;
  background: rgb(46, 46, 48);
  border: 1.5rpx solid rgba(255, 255, 255, 0.08);
  box-shadow:
    inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
    0 2rpx 8rpx rgba(0, 0, 0, 0.12);
}

.overview-action-disabled {
  opacity: 0.55;
}

.overview-action:active {
  background: rgb(56, 56, 59);
}

.overview-action-icon {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(0.72) sepia(0.32) saturate(1.2) hue-rotate(195deg);
}

.overview-progress {
  margin-top: 26rpx;
}

.overview-progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.overview-progress-label {
  font-size: 22rpx;
  font-weight: 600;
  letter-spacing: 0.8rpx;
  color: #7C8598;
}

.overview-progress-value {
  font-size: 22rpx;
  font-weight: 600;
  color: #94A1FF;
}

.overview-progress-track {
  height: 8rpx;
  margin-top: 12rpx;
  border-radius: 999rpx;
  overflow: hidden;
  background: rgb(41, 41, 41);
}

.overview-progress-fill {
  height: 100%;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #7381EE 0%, #5E6AD2 100%);
  box-shadow: none;
}

.overview-stats-panel {
  margin-top: 26rpx;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20rpx;
  padding: 28rpx 24rpx;
  border-radius: 32rpx;
  background: rgb(41, 41, 41);
  border: 1.5rpx solid rgba(255, 255, 255, 0.05);
}

.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
  min-width: 0;
}

.hero-stat-value {
  display: block;
  font-size: 48rpx;
  font-weight: 600;
  letter-spacing: -0.4rpx;
  line-height: 1.05;
  color: rgb(248, 248, 248);
}

.hero-stat-label {
  display: block;
  font-size: 22rpx;
  line-height: 1.25;
  color: #7C8598;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.section-caption {
  padding-left: 6rpx;
  font-size: 22rpx;
  letter-spacing: 1rpx;
  color: rgba(248, 248, 248, 0.52);
}

.settings-card {
  overflow: hidden;
  border-radius: 36rpx;
  background: rgb(36, 36, 36);
}

.settings-row {
  display: flex;
  align-items: center;
  gap: 18rpx;
  min-height: 116rpx;
  padding: 0 28rpx;
}

.settings-row-pressable:active {
  background: rgb(41, 41, 41);
}

.row-icon-wrap {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0;
  background: transparent;
  border: 0;
}

.share-mode-icon-wrap,
.danger-icon-wrap {
  width: 60rpx;
  height: 60rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18rpx;
  background: rgb(46, 46, 48);
  border: 1.5rpx solid rgba(255, 255, 255, 0.08);
  box-shadow:
    inset 0 1rpx 0 rgba(255, 255, 255, 0.04),
    0 2rpx 8rpx rgba(0, 0, 0, 0.12);
}

.share-mode-icon-wrap.row-icon-wrap-blue {
  background: rgb(46, 46, 48);
  border-color: rgba(255, 255, 255, 0.08);
}

.share-mode-icon-wrap.row-icon-wrap-violet {
  background: rgb(46, 46, 48);
  border-color: rgba(255, 255, 255, 0.08);
}

.item-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(0.73) sepia(0.3) saturate(1.15) hue-rotate(194deg);
}

.share-mode-icon {
  width: 30rpx;
  height: 30rpx;
  filter: brightness(0) invert(0.98);
}

.row-copy {
  flex: 1;
  min-width: 0;
}

.row-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

.row-desc {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  line-height: 1.35;
  color: #7C8598;
}

.row-value {
  margin-left: 12rpx;
  font-size: 24rpx;
  font-weight: 600;
  color: rgba(248, 248, 248, 0.74);
  flex-shrink: 0;
}

.item-arrow {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(0.46);
}

.settings-divider {
  height: 1rpx;
  margin-left: 0;
  background: rgba(255, 255, 255, 0.06);
}

.palette-card {
  padding: 24rpx 22rpx;
}

.palette-copy {
  margin-bottom: 18rpx;
}

.palette-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

.palette-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  line-height: 1.5;
  color: rgba(248, 248, 248, 0.52);
}

.color-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.color-swatch {
  flex: 1;
  min-width: 96rpx;
  height: 96rpx;
  position: relative;
  border-radius: 18rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.04);
}

.color-swatch:active {
  transform: scale(0.96);
}

.swatch-selected {
  border-color: rgba(248, 248, 248, 0.7);
  box-shadow: 0 0 0 6rpx rgba(255, 255, 255, 0.04);
}

.swatch-check {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.check-icon {
  width: 30rpx;
  height: 30rpx;
  filter: brightness(0) invert(1);
}

.swatch-loading {
  opacity: 0.62;
  pointer-events: none;
}

.swatch-loading-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 34rpx;
  height: 34rpx;
  margin-left: -17rpx;
  margin-top: -17rpx;
  border: 3rpx solid rgba(255, 255, 255, 0.28);
  border-top-color: rgb(248, 248, 248);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.danger-group {
  padding-top: 2rpx;
}

.danger-card {
  display: flex;
  align-items: center;
  gap: 18rpx;
  min-height: 108rpx;
  padding: 0 28rpx;
  border-radius: 36rpx;
  border: 1rpx solid #7A4051;
  background: rgba(40, 18, 26, 0.92);
  box-shadow:
    inset 0 1rpx 0 rgba(255, 120, 146, 0.08),
    0 14rpx 34rpx rgba(0, 0, 0, 0.2);
}

.danger-card:active {
  background: rgba(40, 17, 26, 0.96);
}

.danger-icon-wrap {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 0;
}

.danger-icon {
  width: 34rpx;
  height: 34rpx;
  filter: invert(61%) sepia(48%) saturate(2052%) hue-rotate(309deg) brightness(103%) contrast(101%);
}

.danger-label {
  display: inline-block;
  font-size: 30rpx;
  font-weight: 700;
  color: #FF6F86;
}

.share-popup-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0);
  transition: background 220ms ease;
}

.share-popup-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.58);
}

.share-popup-card {
  width: 620rpx;
  max-width: calc(100vw - 48rpx);
  padding: 40rpx 32rpx 32rpx;
  border-radius: 32rpx;
  transform: translateY(36rpx) scale(0.96);
  opacity: 0;
  transition: all 280ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.share-popup-card.dialog-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

.share-popup-card-code {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.share-popup-title {
  display: block;
  text-align: center;
  font-size: 34rpx;
  font-weight: 700;
  color: rgb(248, 248, 248);
}

.share-popup-hint {
  display: block;
  margin-top: 14rpx;
  font-size: 24rpx;
  line-height: 1.6;
  text-align: center;
  color: rgba(248, 248, 248, 0.56);
}

.share-mode-options {
  margin-top: 24rpx;
  overflow: hidden;
  border-radius: 24rpx;
  background: rgb(41, 41, 41);
  border: 1.5rpx solid rgba(255, 255, 255, 0.05);
}

.share-mode-option {
  display: flex;
  align-items: center;
  gap: 14rpx;
  padding: 22rpx 20rpx;
}

.share-mode-option:active {
  background: rgb(44, 44, 44);
}

.share-mode-info {
  flex: 1;
  min-width: 0;
}

.share-mode-label {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

.share-mode-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  line-height: 1.5;
  color: rgba(248, 248, 248, 0.52);
}

.settings-divider-popup {
  margin-left: 94rpx;
}

.share-popup-code-box {
  width: 100%;
  margin-top: 28rpx;
  padding: 28rpx 20rpx;
  border-radius: 24rpx;
  background: rgb(41, 41, 41);
  border: 1.5rpx solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: center;
  align-items: center;
}

.share-popup-code {
  font-size: 52rpx;
  font-weight: 700;
  letter-spacing: 8rpx;
  color: rgb(248, 248, 248);
  font-family: 'Courier New', Courier, monospace;
}

.share-popup-copy-btn {
  width: 100%;
  height: 92rpx;
  margin-top: 28rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #4A6CF7;
  box-shadow: 0 12rpx 28rpx rgba(74, 108, 247, 0.28);
}

.share-popup-copy-btn:active {
  transform: scale(0.985);
}

.share-popup-copy-btn-text {
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
