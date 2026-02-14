<template>
  <view class="quiz-list-page">
    <!-- Navigation Bar -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">测验管理</text>
      <view class="nav-right-placeholder"></view>
    </view>

    <!-- Loading State -->
    <view v-if="loading" class="loading-container">
      <text class="loading-text">正在加载测验列表...</text>
    </view>

    <!-- Error State -->
    <view v-else-if="loadError" class="error-container">
      <image class="error-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="error-text">{{ loadError }}</text>
      <view class="retry-btn" @click="loadQuizzes">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- Empty State -->
    <view v-else-if="quizzes.length === 0" class="empty-container">
      <image class="empty-icon" src="/static/icons/phosphor-icons/SVGs/regular/clipboard-text.svg" mode="aspectFit"></image>
      <text class="empty-text">暂无测验</text>
    </view>

    <!-- Quiz List -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="quiz-list">
        <view
          v-for="quiz in quizzes"
          :key="quiz.id"
          class="quiz-item"
          @click="handleQuizClick(quiz)"
          @longpress="showDeleteConfirm(quiz)"
        >
          <view class="quiz-main">
            <view class="quiz-info">
              <text class="quiz-title">{{ quiz.title }}</text>
              <view class="quiz-meta">
                <text class="quiz-topic">{{ quiz.topic }}</text>
                <view class="quiz-difficulty" :class="'difficulty-' + quiz.difficulty">
                  {{ difficultyLabel(quiz.difficulty) }}
                </view>
              </view>
              <text class="quiz-date">{{ formatDate(quiz.created_at) }}</text>
            </view>
            <view class="quiz-status">
              <view v-if="quiz.has_attempt" class="status-completed">
                <text class="score-text">{{ quiz.attempt_score }}/{{ quiz.attempt_total_score }}</text>
                <image class="status-icon" src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg" mode="aspectFit"></image>
              </view>
              <view v-else class="status-pending">
                <text class="pending-text">未作答</text>
                <image class="arrow-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-right.svg" mode="aspectFit"></image>
              </view>
            </view>
          </view>
          <view class="quiz-questions">
            <text class="questions-count">{{ quiz.total_questions }} 道题</text>
          </view>
        </view>
      </view>
    </scroll-view>

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
      }
    }
  },

  computed: {
    deleteModalContent() {
      if (!this.quizToDelete) return ''
      return `确定要删除「${this.quizToDelete.title}」吗？此操作不可恢复。`
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.spaceName = options.spaceName ? decodeURIComponent(options.spaceName) : ''
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
        const response = await getQuizzesBySpace(this.spaceId)
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

    showDeleteConfirm(quiz) {
      this.quizToDelete = quiz
      this.showDeleteModal = true
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
    }
  }
}
</script>

<style>
.quiz-list-page {
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
  padding-bottom: 16rpx;
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

/* Loading, Error & Empty States */
.loading-container,
.error-container,
.empty-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
}

.loading-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.6);
}

.error-icon {
  width: 100rpx;
  height: 100rpx;
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  margin-bottom: 24rpx;
}

.error-text {
  font-size: 28rpx;
  color: rgba(239, 68, 68, 0.9);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 500rpx;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(0, 136, 255, 0.15);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
  border-radius: 40rpx;
}

.retry-btn:active {
  background: rgba(0, 136, 255, 0.25);
}

.retry-btn-text {
  font-size: 28rpx;
  color: #0088FF;
}

.empty-icon {
  width: 120rpx;
  height: 120rpx;
  filter: brightness(0) invert(1);
  opacity: 0.3;
  margin-bottom: 32rpx;
}

.empty-text {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.6);
}

/* Content Scroll */
.content-scroll {
  flex: 1;
  padding: calc(100vh * 1.5 / 26 + 100rpx) calc(100vw / 24) 60rpx;
  box-sizing: border-box;
}

/* Quiz List */
.quiz-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.quiz-item {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 28rpx;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  transition: all 0.2s ease;
}

.quiz-item:active {
  background: rgba(255, 255, 255, 0.08);
}

.quiz-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.quiz-info {
  flex: 1;
  min-width: 0;
}

.quiz-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 12rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quiz-meta {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 8rpx;
}

.quiz-topic {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300rpx;
}

.quiz-difficulty {
  font-size: 20rpx;
  font-weight: 500;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
}

.difficulty-easy {
  background: rgba(16, 185, 129, 0.2);
  color: #10B981;
}

.difficulty-medium {
  background: rgba(245, 158, 11, 0.2);
  color: #F59E0B;
}

.difficulty-hard {
  background: rgba(239, 68, 68, 0.2);
  color: #EF4444;
}

.quiz-date {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
}

.quiz-status {
  flex-shrink: 0;
  margin-left: 16rpx;
}

.status-completed {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.score-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #86D07D;
}

.status-icon {
  width: 40rpx;
  height: 40rpx;
  filter: brightness(0) saturate(100%) invert(85%) sepia(25%) saturate(556%) hue-rotate(85deg) brightness(96%) contrast(92%);
}

.status-pending {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.pending-text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.5);
}

.arrow-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.4;
}

.quiz-questions {
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
}

.questions-count {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
}
</style>
