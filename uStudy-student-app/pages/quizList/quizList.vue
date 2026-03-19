<template>
  <view class="quiz-list-page">
    <view class="page-bg">
      <view class="bg-mesh"></view>
      <view class="bg-glow bg-glow-blue"></view>
      <view class="bg-glow bg-glow-violet"></view>
    </view>

    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-back" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <view class="nav-copy">
        <text class="nav-title">测验管理</text>
        <text v-if="spaceName" class="nav-subtitle">{{ spaceName }}</text>
      </view>
      <view class="nav-action" @click="showCreateFolderDialog">
        <image class="nav-icon" src="/static/icons/lucide/folder-plus.svg" mode="aspectFit"></image>
      </view>
    </view>

    <!-- Loading State -->
    <view v-if="loading" class="state-container">
      <text class="state-text">正在加载测验列表...</text>
    </view>

    <!-- Error State -->
    <view v-else-if="loadError" class="state-container">
      <image class="state-icon state-icon-error" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="state-text state-text-error">{{ loadError }}</text>
      <view class="retry-btn" @click="loadQuizzes">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- Empty State -->
    <view v-else-if="quizzes.length === 0 && currentFolders.length === 0" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/clipboard-text.svg" mode="aspectFit"></image>
      <text class="state-text">暂无测验</text>
    </view>

    <!-- Quiz List -->
    <scroll-view v-else class="content-scroll" :scroll-y="!isSwiping" @scroll="onListScroll">
      <view class="content-body">
        <!-- Breadcrumb -->
        <view v-if="breadcrumbs.length > 0" class="breadcrumb-bar">
          <view class="breadcrumb-item" @click="navigateToFolder(null)">
            <text class="breadcrumb-text breadcrumb-link">全部</text>
          </view>
          <template v-for="(crumb, idx) in breadcrumbs" :key="crumb.id">
            <text class="breadcrumb-sep">/</text>
            <view class="breadcrumb-item" @click="navigateToFolder(crumb.id)">
              <text class="breadcrumb-text" :class="{ 'breadcrumb-link': idx < breadcrumbs.length - 1 }">{{ crumb.name }}</text>
            </view>
          </template>
        </view>

        <!-- Folders -->
        <view v-if="currentFolders.length > 0" class="folder-section">
          <view
            v-for="folder in currentFolders"
            :key="folder.id"
            class="folder-card"
            @click="navigateToFolder(folder.id)"
            @longpress="showFolderActions(folder)"
          >
            <image class="folder-icon" src="/static/icons/lucide/folder.svg" mode="aspectFit"></image>
            <view class="folder-info">
              <text class="folder-name">{{ folder.name }}</text>
              <text class="folder-count">{{ folder.items_count }} 份测验</text>
            </view>
            <image class="folder-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
          </view>
        </view>

        <view v-if="quizzes.length === 0 && currentFolders.length === 0" class="no-results">
          <text class="state-text">当前文件夹为空</text>
        </view>

        <view v-if="quizzes.length > 0" class="list-section">
          <text class="section-caption">{{ quizzes.length }} 份测验</text>
          <view
            v-for="quiz in quizzes"
            :key="quiz.id"
            class="swipe-quiz-wrapper"
          >
            <!-- Swipe Action Buttons (behind content) -->
            <view class="swipe-actions">
              <view class="swipe-action-btn swipe-action-move" @click.stop="onSwipeActionMove(quiz)">
                <image class="swipe-action-icon" src="/static/icons/lucide/folder-input.svg" mode="aspectFit" />
                <text class="swipe-action-text">移动</text>
              </view>
              <view class="swipe-action-btn swipe-action-delete" @click.stop="onSwipeActionDelete(quiz)">
                <image class="swipe-action-icon" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit" />
                <text class="swipe-action-text">删除</text>
              </view>
            </view>
            <!-- Slidable Content -->
            <view
              class="quiz-item"
              :style="quizSwipeStyle(quiz.id)"
              @click="handleQuizItemClick(quiz)"
              @touchstart="onSwipeTouchStart($event, quiz)"
              @touchmove="onSwipeTouchMove($event, quiz)"
              @touchend="onSwipeTouchEnd($event, quiz)"
            >
              <!-- Score Badge -->
              <view class="score-badge" :class="scoreBadgeClass(quiz)">
                <text class="score-badge-text">{{ scoreBadgeText(quiz) }}</text>
              </view>

              <!-- Content -->
              <view class="quiz-content">
                <text class="quiz-title">{{ quiz.title }}</text>
                <view class="quiz-meta">
                  <text class="meta-item">{{ quiz.total_questions }} 道题</text>
                  <text class="meta-sep">·</text>
                  <text class="meta-item">{{ formatDate(quiz.created_at) }}</text>
                  <text class="meta-sep">·</text>
                  <view class="difficulty-tag" :class="'difficulty-' + quiz.difficulty">
                    <text class="difficulty-text">{{ difficultyLabel(quiz.difficulty) }}</text>
                  </view>
                </view>
              </view>

              <!-- Arrow -->
              <image class="item-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- Create Folder Dialog -->
    <view v-if="showCreateFolder" class="folder-dialog-mask" @click="showCreateFolder = false">
      <view class="folder-dialog" @click.stop>
        <text class="folder-dialog-title">新建文件夹</text>
        <input
          class="folder-dialog-input"
          v-model="newFolderName"
          type="text"
          placeholder="文件夹名称"
          maxlength="100"
          placeholder-style="color: #5C5B59"
        />
        <view class="folder-dialog-actions">
          <view class="folder-dialog-btn folder-dialog-btn-cancel" @click="showCreateFolder = false">
            <text class="folder-dialog-btn-text">取消</text>
          </view>
          <view class="folder-dialog-btn folder-dialog-btn-confirm" @click="doCreateFolder">
            <text class="folder-dialog-btn-text folder-dialog-btn-text-confirm">创建</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Move Quiz to Folder Picker -->
    <view v-if="showMovePicker" class="folder-dialog-mask" @click="showMovePicker = false">
      <view class="folder-picker-popup" @click.stop>
        <view class="folder-picker-header">
          <text class="folder-picker-title">移动到文件夹</text>
          <view class="folder-picker-close" @click="showMovePicker = false">
            <image class="folder-picker-close-icon" src="/static/icons/phosphor-icons/SVGs/regular/x.svg" mode="aspectFit"></image>
          </view>
        </view>
        <scroll-view class="folder-picker-list" scroll-y>
          <view
            class="folder-picker-item"
            :class="{ 'folder-picker-item-active': !moveTargetFolderId }"
            @click="selectMoveTarget(null)"
          >
            <image class="folder-picker-item-icon" src="/static/icons/phosphor-icons/SVGs/regular/house.svg" mode="aspectFit"></image>
            <text class="folder-picker-item-text">根目录（未分类）</text>
          </view>
          <view
            v-for="folder in allFolders"
            :key="folder.id"
            class="folder-picker-item"
            :class="{ 'folder-picker-item-active': moveTargetFolderId === folder.id }"
            @click="selectMoveTarget(folder.id)"
          >
            <image class="folder-picker-item-icon" src="/static/icons/lucide/folder.svg" mode="aspectFit"></image>
            <text class="folder-picker-item-text">{{ folder.name }}</text>
          </view>
        </scroll-view>
        <view class="folder-picker-footer">
          <view class="folder-dialog-btn folder-dialog-btn-confirm" @click="doMoveQuiz">
            <text class="folder-dialog-btn-text folder-dialog-btn-text-confirm">确定移动</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Folder Actions (rename/delete) -->
    <view v-if="showFolderActionMenu" class="folder-dialog-mask" @click="showFolderActionMenu = false">
      <view class="folder-action-popup" @click.stop>
        <view class="folder-action-item" @click="startRenameFolder">
          <image class="folder-action-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit"></image>
          <text class="folder-action-text">重命名</text>
        </view>
        <view class="folder-action-item folder-action-item-danger" @click="doDeleteFolder">
          <image class="folder-action-icon folder-action-icon-danger" src="/static/icons/phosphor-icons/SVGs/regular/trash.svg" mode="aspectFit"></image>
          <text class="folder-action-text folder-action-text-danger">删除文件夹</text>
        </view>
      </view>
    </view>

    <!-- Rename Folder Dialog -->
    <view v-if="showRenameFolder" class="folder-dialog-mask" @click="showRenameFolder = false">
      <view class="folder-dialog" @click.stop>
        <text class="folder-dialog-title">重命名文件夹</text>
        <input
          class="folder-dialog-input"
          v-model="renameFolderName"
          type="text"
          placeholder="新名称"
          maxlength="100"
          placeholder-style="color: #5C5B59"
        />
        <view class="folder-dialog-actions">
          <view class="folder-dialog-btn folder-dialog-btn-cancel" @click="showRenameFolder = false">
            <text class="folder-dialog-btn-text">取消</text>
          </view>
          <view class="folder-dialog-btn folder-dialog-btn-confirm" @click="doRenameFolder">
            <text class="folder-dialog-btn-text folder-dialog-btn-text-confirm">确定</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Delete Confirmation Modal -->
    <u-modal
      :visible="showDeleteModal"
      title="删除测验"
      :content="deleteModalContent"
      confirm-text="删除"
      confirm-type="danger"
      @confirm="doDeleteQuiz"
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
import { getQuizzesBySpace, deleteQuiz } from '@/api/space'
import { getFolders, createFolder, updateFolder, deleteFolder as deleteFolderApi, moveQuizzes } from '@/api/folder'
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
      loading: true,
      loadError: null,
      quizzes: [],
      showDeleteModal: false,
      quizToDelete: null,
      isDeleting: false,
      toast: {
        visible: false,
        message: '',
        type: 'info'
      },
      // Folder state
      allFolders: [],
      currentFolderId: null,
      breadcrumbs: [],
      showCreateFolder: false,
      newFolderName: '',
      showMovePicker: false,
      moveQuizId: null,
      moveTargetFolderId: null,
      showFolderActionMenu: false,
      activeFolderForAction: null,
      showRenameFolder: false,
      renameFolderName: '',
      // Swipe state
      swipedQuizId: null,
      swipeTouchStartX: 0,
      swipeTouchStartY: 0,
      swipeStartOffsetX: 0,
      swipeCurrentOffsetX: 0,
      swipeDirection: null,
      isSwiping: false,
      actionsWidthPx: 0
    }
  },

  computed: {
    deleteModalContent() {
      if (!this.quizToDelete) return ''
      return `确定要删除「${this.quizToDelete.title}」吗？此操作不可恢复。`
    },

    currentFolders() {
      return this.allFolders.filter(f => {
        const parentMatch = this.currentFolderId
          ? f.parent_id === this.currentFolderId
          : !f.parent_id
        return parentMatch
      })
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
    const sysInfo = uni.getSystemInfoSync()
    this.actionsWidthPx = 320 * sysInfo.windowWidth / 750
    this.loadFolders()
    this.loadQuizzes()
  },

  onShow() {
    if (this.spaceId && !this.loading) {
      this.loadQuizzes()
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

    async loadQuizzes() {
      if (!this.spaceId) {
        this.loading = false
        return
      }

      try {
        this.loading = true
        this.loadError = null
        const opts = {}
        if (this.currentFolderId) {
          opts.folderId = this.currentFolderId
        }
        const response = await getQuizzesBySpace(this.spaceId, opts)
        this.quizzes = response || []
      } catch (error) {
        this.loadError = error.message || '加载失败，请检查网络后重试'
        this.quizzes = []
      } finally {
        this.loading = false
      }
    },

    difficultyLabel(difficulty) {
      const labels = {
        easy: '简单',
        medium: '中等',
        hard: '困难'
      }
      return labels[difficulty] || difficulty
    },

    formatDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      const month = date.getMonth() + 1
      const day = date.getDate()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${month}月${day}日 ${hours}:${minutes}`
    },

    scoreBadgeClass(quiz) {
      if (!quiz.has_attempt) return 'score-badge-pending'
      const pct = quiz.attempt_total_score > 0
        ? Math.round(quiz.attempt_score / quiz.attempt_total_score * 100)
        : 0
      if (pct >= 80) return 'score-badge-green'
      if (pct >= 60) return 'score-badge-blue'
      if (pct >= 40) return 'score-badge-amber'
      return 'score-badge-red'
    },

    scoreBadgeText(quiz) {
      if (!quiz.has_attempt) return '—'
      const pct = quiz.attempt_total_score > 0
        ? Math.round(quiz.attempt_score / quiz.attempt_total_score * 100)
        : 0
      return String(pct)
    },

    handleQuizClick(quiz) {
      if (quiz.has_attempt) {
        uni.navigateTo({
          url: `/pages/testResult/testResult?quizId=${quiz.id}&fromList=true`
        })
      } else {
        uni.navigateTo({
          url: `/pages/test/test?quizId=${quiz.id}`
        })
      }
    },

    // ============ Swipe-to-Reveal Actions ============

    quizSwipeStyle(quizId) {
      if (this.isSwiping && this.swipedQuizId === quizId) {
        return {
          transform: `translateX(${this.swipeCurrentOffsetX}px)`,
          transition: 'none'
        }
      }
      if (this.swipedQuizId === quizId && !this.isSwiping) {
        return {
          transform: `translateX(${-this.actionsWidthPx}px)`,
          transition: 'transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
        }
      }
      return {
        transform: 'translateX(0)',
        transition: 'transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
      }
    },

    onSwipeTouchStart(e, quiz) {
      if (this.swipedQuizId && this.swipedQuizId !== quiz.id) {
        this.closeSwipe()
      }
      this.swipeTouchStartX = e.touches[0].clientX
      this.swipeTouchStartY = e.touches[0].clientY
      this.swipeDirection = null
      this.isSwiping = false
      this.swipeStartOffsetX = this.swipedQuizId === quiz.id ? -this.actionsWidthPx : 0
      this.swipeCurrentOffsetX = this.swipeStartOffsetX
    },

    onSwipeTouchMove(e, quiz) {
      const currentX = e.touches[0].clientX
      const currentY = e.touches[0].clientY

      if (!this.swipeDirection) {
        const deltaX = Math.abs(currentX - this.swipeTouchStartX)
        const deltaY = Math.abs(currentY - this.swipeTouchStartY)
        if (deltaX > 10 || deltaY > 10) {
          this.swipeDirection = deltaX > deltaY ? 'horizontal' : 'vertical'
          if (this.swipeDirection === 'horizontal') {
            this.isSwiping = true
            this.swipedQuizId = quiz.id
          }
        }
        return
      }

      if (this.swipeDirection === 'vertical') return

      const deltaX = currentX - this.swipeTouchStartX
      let newOffset = this.swipeStartOffsetX + deltaX
      newOffset = Math.min(0, Math.max(-(this.actionsWidthPx + 40), newOffset))
      this.swipeCurrentOffsetX = newOffset
    },

    onSwipeTouchEnd(e, quiz) {
      if (this.swipeDirection !== 'horizontal' || !this.isSwiping) {
        this.isSwiping = false
        this.swipeDirection = null
        return
      }

      this.isSwiping = false
      this.swipeDirection = null

      const snapThreshold = -this.actionsWidthPx * 0.35
      if (this.swipeCurrentOffsetX < snapThreshold) {
        this.swipeCurrentOffsetX = -this.actionsWidthPx
        this.swipedQuizId = quiz.id
      } else {
        this.swipeCurrentOffsetX = 0
        this.swipedQuizId = null
      }
    },

    closeSwipe() {
      this.swipedQuizId = null
      this.swipeStartOffsetX = 0
      this.swipeCurrentOffsetX = 0
      this.isSwiping = false
      this.swipeDirection = null
    },

    handleQuizItemClick(quiz) {
      if (this.swipedQuizId) {
        this.closeSwipe()
        return
      }
      this.handleQuizClick(quiz)
    },

    onSwipeActionMove(quiz) {
      this.closeSwipe()
      this.moveQuizId = quiz.id
      this.moveTargetFolderId = quiz.folder_id || null
      this.showMovePicker = true
    },

    onSwipeActionDelete(quiz) {
      this.closeSwipe()
      this.quizToDelete = quiz
      this.showDeleteModal = true
    },

    onListScroll() {
      if (this.swipedQuizId) {
        this.closeSwipe()
      }
    },

    async doDeleteQuiz() {
      if (this.isDeleting || !this.quizToDelete) return
      this.isDeleting = true

      try {
        await deleteQuiz(this.quizToDelete.id)
        this.showDeleteModal = false
        this.showCustomToast('测验已删除', 'success')
        this.quizzes = this.quizzes.filter(q => q.id !== this.quizToDelete.id)
        this.quizToDelete = null
      } catch (error) {
        this.showCustomToast(error.message || '删除失败，请重试', 'error')
      } finally {
        this.isDeleting = false
      }
    },

    // ============ Folder Methods ============

    async loadFolders() {
      if (!this.spaceId) return
      try {
        const folders = await getFolders(this.spaceId, 'quizzes')
        this.allFolders = Array.isArray(folders) ? folders : []
      } catch (e) {
        this.allFolders = []
      }
    },

    navigateToFolder(folderId) {
      this.currentFolderId = folderId
      this.buildBreadcrumbs()
      this.loadQuizzes()
    },

    buildBreadcrumbs() {
      const crumbs = []
      let currentId = this.currentFolderId
      while (currentId) {
        const folder = this.allFolders.find(f => f.id === currentId)
        if (!folder) break
        crumbs.unshift({ id: folder.id, name: folder.name })
        currentId = folder.parent_id
      }
      this.breadcrumbs = crumbs
    },

    showCreateFolderDialog() {
      this.newFolderName = ''
      this.showCreateFolder = true
    },

    async doCreateFolder() {
      const name = this.newFolderName.trim()
      if (!name) return
      try {
        await createFolder(this.spaceId, {
          name,
          content_type: 'quizzes',
          parent_id: this.currentFolderId || undefined
        })
        this.showCreateFolder = false
        this.showCustomToast('文件夹已创建', 'success')
        await this.loadFolders()
      } catch (e) {
        this.showCustomToast(e?.message || '创建失败', 'error')
      }
    },

    showFolderActions(folder) {
      this.activeFolderForAction = folder
      this.showFolderActionMenu = true
    },

    startRenameFolder() {
      this.showFolderActionMenu = false
      this.renameFolderName = this.activeFolderForAction?.name || ''
      this.showRenameFolder = true
    },

    async doRenameFolder() {
      const name = this.renameFolderName.trim()
      if (!name || !this.activeFolderForAction) return
      try {
        await updateFolder(this.spaceId, this.activeFolderForAction.id, { name })
        this.showRenameFolder = false
        this.showCustomToast('已重命名', 'success')
        await this.loadFolders()
        this.buildBreadcrumbs()
      } catch (e) {
        this.showCustomToast(e?.message || '重命名失败', 'error')
      }
    },

    async doDeleteFolder() {
      if (!this.activeFolderForAction) return
      try {
        await deleteFolderApi(this.spaceId, this.activeFolderForAction.id)
        this.showFolderActionMenu = false
        this.showCustomToast('文件夹已删除', 'success')
        if (this.currentFolderId === this.activeFolderForAction.id) {
          this.currentFolderId = this.activeFolderForAction.parent_id || null
        }
        await this.loadFolders()
        this.buildBreadcrumbs()
        this.loadQuizzes()
      } catch (e) {
        this.showCustomToast(e?.message || '删除失败', 'error')
      }
    },

    selectMoveTarget(folderId) {
      this.moveTargetFolderId = folderId
    },

    async doMoveQuiz() {
      if (!this.moveQuizId) return
      try {
        await moveQuizzes(this.spaceId, {
          item_ids: [this.moveQuizId],
          target_folder_id: this.moveTargetFolderId
        })
        this.showMovePicker = false
        this.showCustomToast('已移动', 'success')
        await this.loadFolders()
        this.loadQuizzes()
      } catch (e) {
        this.showCustomToast(e?.message || '移动失败', 'error')
      }
    }
  }
}
</script>

<style>
.quiz-list-page {
  position: relative;
  min-height: 100vh;
  background-color: rgb(29, 30, 32);
  overflow: hidden;
}

/* Background */
.page-bg {
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
    radial-gradient(circle at 82% 14%, rgba(74, 108, 247, 0.07) 0%, rgba(74, 108, 247, 0) 32%),
    radial-gradient(circle at 12% 100%, rgba(99, 102, 241, 0.04) 0%, rgba(99, 102, 241, 0) 36%);
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
  background: rgba(74, 108, 247, 0.10);
}

.bg-glow-violet {
  bottom: 180rpx;
  left: -90rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(123, 97, 255, 0.07);
}

/* Navigation Bar */
.nav-bar {
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
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .nav-back {
    background: rgba(80, 80, 95, 0.65);
  }
}

.nav-back:active {
  background: rgba(255, 255, 255, 0.10);
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
}

.nav-spacer {
  width: 72rpx;
  height: 72rpx;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* State Containers */
.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
  padding-bottom: 60rpx;
}

.state-icon {
  width: 100rpx;
  height: 100rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  margin-bottom: 32rpx;
}

.state-icon-error {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  opacity: 1;
}

.state-text {
  font-size: 30rpx;
  color: rgba(248, 248, 248, 0.52);
}

.state-text-error {
  color: rgba(239, 68, 68, 0.9);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 500rpx;
  line-height: 1.5;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(74, 108, 247, 0.15);
  border: 1rpx solid rgba(74, 108, 247, 0.4);
  border-radius: 40rpx;
}

.retry-btn:active {
  background: rgba(74, 108, 247, 0.25);
}

.retry-btn-text {
  font-size: 28rpx;
  color: #4A6CF7;
}

/* Content Scroll */
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

/* List Section */
.list-section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.section-caption {
  padding-left: 6rpx;
  margin-bottom: 4rpx;
  font-size: 22rpx;
  letter-spacing: 1rpx;
  color: rgba(248, 248, 248, 0.52);
}

/* Swipe Wrapper */
.swipe-quiz-wrapper {
  position: relative;
  overflow: hidden;
  border-radius: 36rpx;
}

.swipe-actions {
  position: absolute;
  top: 2rpx;
  right: 2rpx;
  bottom: 2rpx;
  display: flex;
  align-items: stretch;
  border-radius: 34rpx;
  overflow: hidden;
}

.swipe-action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 160rpx;
  gap: 8rpx;
}

.swipe-action-move {
  background: rgba(74, 108, 247, 0.9);
}

.swipe-action-delete {
  background: rgba(239, 68, 68, 0.9);
}

.swipe-action-icon {
  width: 40rpx;
  height: 40rpx;
  filter: brightness(0) invert(1);
}

.swipe-action-text {
  font-size: 22rpx;
  font-weight: 500;
  color: rgb(248, 248, 248);
}

/* Quiz Item */
.quiz-item {
  display: flex;
  align-items: center;
  gap: 24rpx;
  min-height: 116rpx;
  padding: 24rpx 28rpx;
  border-radius: 36rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
  position: relative;
  z-index: 1;
  will-change: transform;
}

.quiz-item:active {
  background: rgb(41, 41, 41);
}

/* Score Badge */
.score-badge {
  width: 80rpx;
  height: 80rpx;
  flex-shrink: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-badge-text {
  font-size: 26rpx;
  font-weight: 700;
  letter-spacing: -0.5rpx;
  color: rgb(248, 248, 248);
}

.score-badge-green {
  background: rgba(16, 185, 129, 0.22);
  border: 1.5rpx solid rgba(16, 185, 129, 0.45);
}

.score-badge-green .score-badge-text {
  color: #34D399;
}

.score-badge-blue {
  background: rgba(74, 108, 247, 0.22);
  border: 1.5rpx solid rgba(74, 108, 247, 0.45);
}

.score-badge-blue .score-badge-text {
  color: #7C93FF;
}

.score-badge-amber {
  background: rgba(245, 158, 11, 0.22);
  border: 1.5rpx solid rgba(245, 158, 11, 0.45);
}

.score-badge-amber .score-badge-text {
  color: #FBBF24;
}

.score-badge-red {
  background: rgba(239, 68, 68, 0.22);
  border: 1.5rpx solid rgba(239, 68, 68, 0.45);
}

.score-badge-red .score-badge-text {
  color: #F87171;
}

.score-badge-pending {
  background: rgba(255, 255, 255, 0.06);
  border: 1.5rpx solid rgba(255, 255, 255, 0.12);
}

.score-badge-pending .score-badge-text {
  font-size: 30rpx;
  font-weight: 400;
  color: rgba(248, 248, 248, 0.35);
}

/* Quiz Content */
.quiz-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.quiz-title {
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quiz-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8rpx;
}

.meta-item {
  font-size: 22rpx;
  color: #7C8598;
}

.meta-sep {
  font-size: 22rpx;
  color: rgba(248, 248, 248, 0.2);
}

/* Difficulty Tag */
.difficulty-tag {
  display: inline-flex;
  align-items: center;
  padding: 2rpx 14rpx;
  border-radius: 8rpx;
}

.difficulty-text {
  font-size: 20rpx;
  font-weight: 500;
}

.difficulty-easy {
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

.difficulty-easy .difficulty-text {
  color: #34D399;
}

.difficulty-medium {
  background: rgba(245, 158, 11, 0.15);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}

.difficulty-medium .difficulty-text {
  color: #FBBF24;
}

.difficulty-hard {
  background: rgba(239, 68, 68, 0.15);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
}

.difficulty-hard .difficulty-text {
  color: #F87171;
}

/* Arrow */
.item-arrow {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(0.46);
}

/* ============ Nav Action Button ============ */
.nav-action {
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
  box-shadow:
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08),
    0 2rpx 12rpx rgba(0, 0, 0, 0.25);
}

.nav-action:active {
  background: rgba(255, 255, 255, 0.10);
}

/* ============ No Results ============ */
.no-results {
  padding: 60rpx 0;
  display: flex;
  justify-content: center;
}

/* ============ Breadcrumb ============ */
.breadcrumb-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6rpx;
  padding: 0 6rpx;
  margin-bottom: 8rpx;
}

.breadcrumb-item {
  display: flex;
  align-items: center;
}

.breadcrumb-text {
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.52);
}

.breadcrumb-link {
  color: #4A6CF7;
}

.breadcrumb-sep {
  font-size: 24rpx;
  color: rgba(248, 248, 248, 0.25);
  margin: 0 4rpx;
}

/* ============ Folder Cards ============ */
.folder-section {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.folder-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 22rpx 28rpx;
  border-radius: 30rpx;
  background: rgb(36, 36, 36);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.18);
}

.folder-card:active {
  background: rgb(41, 41, 41);
}

.folder-icon {
  width: 44rpx;
  height: 44rpx;
  flex-shrink: 0;
  filter: brightness(0) saturate(100%) invert(51%) sepia(82%) saturate(1600%) hue-rotate(207deg) brightness(102%) contrast(94%);
}

.folder-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.folder-name {
  font-size: 30rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-count {
  font-size: 22rpx;
  color: #7C8598;
}

.folder-arrow {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
  filter: brightness(0) invert(0.46);
}

/* ============ Folder Dialog ============ */
.folder-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
}

.folder-dialog {
  width: 560rpx;
  background: rgb(42, 42, 44);
  border-radius: 32rpx;
  padding: 40rpx 36rpx 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.folder-dialog-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
  margin-bottom: 28rpx;
  text-align: center;
}

.folder-dialog-input {
  width: 100%;
  height: 80rpx;
  padding: 0 24rpx;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  color: rgb(248, 248, 248);
  font-size: 28rpx;
  margin-bottom: 28rpx;
  box-sizing: border-box;
}

.folder-dialog-actions {
  display: flex;
  gap: 16rpx;
}

.folder-dialog-btn {
  flex: 1;
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
}

.folder-dialog-btn-cancel {
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.folder-dialog-btn-confirm {
  background: rgba(74, 108, 247, 0.2);
  border: 1rpx solid rgba(74, 108, 247, 0.4);
}

.folder-dialog-btn-text {
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.7);
}

.folder-dialog-btn-text-confirm {
  color: #4A6CF7;
  font-weight: 600;
}

/* ============ Folder Picker (Move) ============ */
.folder-picker-popup {
  width: 600rpx;
  max-height: 700rpx;
  background: rgb(42, 42, 44);
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
}

.folder-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx 16rpx;
}

.folder-picker-title {
  font-size: 32rpx;
  font-weight: 600;
  color: rgb(248, 248, 248);
}

.folder-picker-close {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
}

.folder-picker-close-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(0.7);
}

.folder-picker-list {
  flex: 1;
  max-height: 480rpx;
  padding: 0 16rpx;
  box-sizing: border-box;
}

.folder-picker-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 20rpx 16rpx;
  border-radius: 16rpx;
  margin-bottom: 4rpx;
}

.folder-picker-item:active,
.folder-picker-item-active {
  background: rgba(74, 108, 247, 0.12);
}

.folder-picker-item-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(0.6);
}

.folder-picker-item-text {
  flex: 1;
  font-size: 28rpx;
  color: rgba(248, 248, 248, 0.8);
}

.folder-picker-item-active .folder-picker-item-text {
  color: #4A6CF7;
}

.folder-picker-footer {
  padding: 16rpx 32rpx 28rpx;
}

/* ============ Folder Action Menu ============ */
.folder-action-popup {
  width: 500rpx;
  background: rgb(42, 42, 44);
  border-radius: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  padding: 12rpx 0;
}

.folder-action-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 24rpx 32rpx;
}

.folder-action-item:active {
  background: rgba(255, 255, 255, 0.06);
}

.folder-action-icon {
  width: 40rpx;
  height: 40rpx;
  filter: brightness(0) invert(0.7);
}

.folder-action-icon-danger {
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
}

.folder-action-text {
  font-size: 30rpx;
  color: rgba(248, 248, 248, 0.85);
}

.folder-action-text-danger {
  color: rgba(239, 68, 68, 0.9);
}
</style>
