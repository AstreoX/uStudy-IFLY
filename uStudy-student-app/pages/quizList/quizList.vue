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
      <view class="nav-spacer"></view>
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
    <view v-else-if="quizzes.length === 0" class="state-container">
      <image class="state-icon" src="/static/icons/phosphor-icons/SVGs/regular/clipboard-text.svg" mode="aspectFit"></image>
      <text class="state-text">暂无测验</text>
    </view>

    <!-- Quiz List -->
    <scroll-view v-else class="content-scroll" scroll-y>
      <view class="content-body">
        <view class="list-section">
          <text class="section-caption">{{ quizzes.length }} 份测验</text>
          <view
            v-for="quiz in quizzes"
            :key="quiz.id"
            class="quiz-item"
            @click="handleQuizClick(quiz)"
            @longpress="showDeleteConfirm(quiz)"
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
</style>
