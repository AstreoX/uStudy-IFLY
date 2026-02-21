<template>
  <view class="quiz-list-view">
    <view class="quiz-list-toolbar">
      <text class="quiz-list-title">测验管理</text>
      <view class="toolbar-btn" @tap="$emit('refresh')">
        <image
          class="toolbar-btn-icon"
          mode="aspectFit"
          src="/static/icons/phosphor/regular/arrow-clockwise-white.svg"
        />
      </view>
    </view>

    <view v-if="loading" class="state-wrap">
      <text class="state-text">正在加载测验列表...</text>
    </view>

    <view v-else-if="loadError" class="state-wrap">
      <text class="state-text state-error">{{ loadError }}</text>
      <view class="retry-btn" @tap="$emit('refresh')">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <view v-else-if="quizzes.length === 0" class="state-wrap">
      <text class="state-text">暂无测验</text>
      <text class="state-sub">可在聊天里让 AI 先生成测试题</text>
    </view>

    <scroll-view v-else class="quiz-list-scroll" scroll-y>
      <view class="quiz-list">
        <view
          v-for="quiz in quizzes"
          :key="quiz.id"
          class="quiz-item"
        >
          <view class="quiz-main" @tap="$emit('open', quiz)">
            <view class="quiz-info">
              <text class="quiz-title">{{ quiz.title }}</text>
              <view class="quiz-meta">
                <text class="quiz-topic">{{ quiz.topic || '-' }}</text>
                <view class="quiz-difficulty">
                  <text class="quiz-difficulty-text">{{ difficultyLabel(quiz.difficulty) }}</text>
                </view>
              </view>
              <text class="quiz-date">{{ formatQuizDate(quiz.created_at) }}</text>
            </view>
            <view class="quiz-status">
              <view v-if="quiz.has_attempt" class="status-completed">
                <text class="status-score">{{ quiz.attempt_score }}/{{ quiz.attempt_total_score }}</text>
                <text class="status-tag">已作答</text>
              </view>
              <view v-else class="status-pending">
                <text class="status-tag">未作答</text>
              </view>
            </view>
          </view>

          <view class="quiz-footer">
            <text class="quiz-questions">{{ quiz.total_questions }} 道题</text>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { difficultyLabel, formatQuizDate } from '@/utils/quiz-adapter'

export default {
  name: 'QuizListView',
  props: {
    loading: {
      type: Boolean,
      default: false
    },
    loadError: {
      type: String,
      default: ''
    },
    quizzes: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    difficultyLabel,
    formatQuizDate
  }
}
</script>

<style scoped>
.quiz-list-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24rpx;
  box-sizing: border-box;
}

.quiz-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.quiz-list-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.toolbar-btn {
  width: 88rpx;
  height: 62rpx;
  border-radius: 14rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(96, 165, 250, 0.18);
  border: 1rpx solid rgba(96, 165, 250, 0.4);
}

.toolbar-btn-icon {
  width: 34rpx;
  height: 34rpx;
  opacity: 0.92;
}

.state-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
}

.state-text {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
}

.state-sub {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.45);
}

.state-error {
  color: #fca5a5;
}

.retry-btn {
  height: 64rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(96, 165, 250, 0.4);
  background: rgba(96, 165, 250, 0.16);
}

.retry-btn-text {
  font-size: 24rpx;
  color: #93c5fd;
}

.quiz-list-scroll {
  flex: 1;
  min-height: 0;
}

.quiz-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding-bottom: 10rpx;
}

.quiz-item {
  border-radius: 18rpx;
  background: rgba(20, 20, 35, 0.9);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.quiz-main {
  display: flex;
  justify-content: space-between;
  gap: 12rpx;
  padding: 22rpx;
}

.quiz-info {
  min-width: 0;
  flex: 1;
}

.quiz-title {
  display: block;
  font-size: 28rpx;
  color: #ffffff;
  font-weight: 500;
  line-height: 1.4;
}

.quiz-meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 8rpx;
}

.quiz-topic {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.62);
  max-width: 60%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quiz-difficulty {
  height: 38rpx;
  padding: 0 12rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(147, 197, 253, 0.14);
  border: 1rpx solid rgba(147, 197, 253, 0.32);
}

.quiz-difficulty-text {
  font-size: 20rpx;
  color: #93c5fd;
}

.quiz-date {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.quiz-status {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.status-completed,
.status-pending {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6rpx;
}

.status-score {
  font-size: 24rpx;
  color: #86efac;
  font-weight: 600;
}

.status-tag {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.65);
}

.quiz-footer {
  height: 66rpx;
  padding: 0 22rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.07);
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.quiz-questions {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.62);
}
</style>
