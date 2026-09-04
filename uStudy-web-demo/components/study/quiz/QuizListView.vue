<template>
  <view class="quiz-list-view">
    <view class="quiz-list-toolbar">
      <view class="toolbar-heading">
        <text class="quiz-list-title">测试题</text>
        <text class="quiz-list-summary">教师作业与自主测试</text>
      </view>
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

    <view v-else-if="assignments.length === 0 && quizzes.length === 0" class="state-wrap">
      <text class="state-text">暂无测试题</text>
      <text class="state-sub">教师发布的作业和 AI 自主测试会显示在这里</text>
    </view>

    <scroll-view v-else class="quiz-list-scroll" scroll-y>
      <view v-if="assignments.length" class="quiz-list assignment-list">
        <view class="section-heading">
          <view class="section-heading-main">
            <view class="section-dot assignment-section-dot" />
            <text class="section-title">教师作业</text>
          </view>
          <text class="section-count">{{ assignments.length }} 项</text>
        </view>

        <view
          v-for="assignment in assignments"
          :key="`assignment-${assignment.id}`"
          class="quiz-item assignment-item"
          @tap="handleOpen(assignment)"
        >
          <view class="quiz-main">
            <view class="quiz-info">
              <view class="assignment-title-row">
                <view class="teacher-assignment-tag">
                  <view class="teacher-tag-dot" />
                  <text class="teacher-assignment-tag-text">教师作业</text>
                </view>
                <view v-if="deadlineState(assignment)" class="deadline-tag" :class="`deadline-tag-${deadlineState(assignment)}`">
                  <text class="deadline-tag-text">{{ deadlineStateLabel(assignment) }}</text>
                </view>
              </view>
              <text class="quiz-title">{{ assignment.title }}</text>
              <view class="quiz-meta">
                <text class="quiz-topic">{{ assignment.topic || '当前课程空间' }}</text>
                <view class="quiz-difficulty assignment-difficulty">
                  <text class="quiz-difficulty-text assignment-difficulty-text">{{ difficultyLabel(assignment.difficulty) }}</text>
                </view>
              </view>
              <text class="quiz-date assignment-deadline">截止：{{ formatQuizDate(assignment.due_at) }}</text>
            </view>
            <view class="quiz-status">
              <view v-if="assignment.attempt_status === 'evaluating'" class="status-evaluating">
                <view class="evaluating-dot assignment-evaluating-dot" />
                <text class="status-tag assignment-evaluating-text">批改中...</text>
              </view>
              <view v-else-if="assignment.attempt_status === 'in_progress'" class="status-in-progress">
                <text class="status-progress-count assignment-progress-count">{{ assignment.draft_answer_count || 0 }}/{{ assignment.total_questions }}</text>
                <text class="status-tag assignment-progress-text">草稿</text>
              </view>
              <view v-else-if="assignment.attempt_status === 'failed'" class="status-failed">
                <text class="status-tag status-failed-text">批改失败</text>
              </view>
              <view v-else-if="assignment.attempt_status === 'missed'" class="status-failed">
                <text class="status-tag status-missed-text">已错过</text>
              </view>
              <view v-else-if="assignment.attempt_status === 'completed'" class="status-completed">
                <text class="status-score assignment-score">{{ displayScore(assignment) }}</text>
                <text class="status-tag assignment-score-label">{{ assignment.score_label || 'AI 初评' }}</text>
              </view>
              <view v-else class="status-pending">
                <text class="status-tag">未提交</text>
              </view>
            </view>
          </view>

          <view class="quiz-footer assignment-footer">
            <text class="quiz-questions">{{ assignment.total_questions }} 道题</text>
            <text class="assignment-open-hint">{{ assignment.attempt_status === 'completed' ? '查看结果' : '打开作业' }} →</text>
          </view>
        </view>
      </view>

      <view v-if="quizzes.length" class="quiz-list" :class="{ 'quiz-list-separated': assignments.length }">
        <view class="section-heading">
          <view class="section-heading-main">
            <view class="section-dot quiz-section-dot" />
            <text class="section-title">自主测试</text>
          </view>
          <text class="section-count">{{ quizzes.length }} 项</text>
        </view>
        <view
          v-for="quiz in quizzes"
          :key="`quiz-${quiz.id}`"
          class="quiz-item"
        >
          <view class="quiz-main" :class="{ 'quiz-main-disabled': isEvaluating(quiz) }" @tap="handleOpen(quiz)">
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
              <view v-if="quiz.has_attempt && (quiz.attempt_status === 'pending' || quiz.attempt_status === 'evaluating')" class="status-evaluating">
                <view class="evaluating-dot" />
                <text class="status-tag status-evaluating-text">评估中...</text>
              </view>
              <view v-else-if="quiz.has_attempt && quiz.attempt_status === 'in_progress'" class="status-in-progress">
                <text class="status-progress-count">{{ quiz.draft_answer_count || 0 }}/{{ quiz.total_questions }}</text>
                <text class="status-tag status-progress-text">进行中</text>
              </view>
              <view v-else-if="quiz.has_attempt && quiz.attempt_status === 'failed'" class="status-failed">
                <text class="status-tag status-failed-text">评估失败</text>
              </view>
              <view v-else-if="quiz.has_attempt" class="status-completed">
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
    },
    assignments: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    handleOpen(quiz) {
      if (quiz?.item_kind !== 'assignment' && this.isEvaluating(quiz)) return
      this.$emit('open', quiz)
    },
    isEvaluating(quiz) {
      return quiz?.attempt_status === 'pending' || quiz?.attempt_status === 'evaluating'
    },
    deadlineState(assignment) {
      if (assignment?.attempt_status === 'completed') return ''
      if (['evaluating', 'failed'].includes(assignment?.attempt_status)) return ''
      if (assignment?.attempt_status === 'missed') return 'missed'
      const dueTime = new Date(assignment?.due_at || '').getTime()
      if (!Number.isFinite(dueTime)) return ''
      const remaining = dueTime - Date.now()
      if (remaining <= 0) return 'missed'
      if (remaining <= 24 * 60 * 60 * 1000) return 'urgent'
      return ''
    },
    deadlineStateLabel(assignment) {
      return this.deadlineState(assignment) === 'missed' ? '已错过' : '即将截止'
    },
    displayScore(assignment) {
      if (!Number.isFinite(assignment?.attempt_score)) return '已批改'
      if (!Number.isFinite(assignment?.attempt_total_score)) return `${assignment.attempt_score}分`
      return `${assignment.attempt_score}/${assignment.attempt_total_score}`
    },
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

.toolbar-heading {
  display: flex;
  flex-direction: column;
  gap: 3rpx;
}

.quiz-list-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #ffffff;
}

.quiz-list-summary {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.42);
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

.quiz-list-separated {
  margin-top: 28rpx;
}

.section-heading {
  min-height: 42rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4rpx;
}

.section-heading-main {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.section-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
}

.assignment-section-dot {
  background: #a78bfa;
  box-shadow: 0 0 12rpx rgba(167, 139, 250, 0.72);
}

.quiz-section-dot {
  background: #60a5fa;
  box-shadow: 0 0 12rpx rgba(96, 165, 250, 0.6);
}

.section-title {
  font-size: 24rpx;
  line-height: 1;
  color: rgba(255, 255, 255, 0.86);
  font-weight: 600;
}

.section-count {
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.4);
}

.quiz-item {
  border-radius: 18rpx;
  background: rgba(20, 20, 35, 0.9);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.assignment-item {
  position: relative;
  border-left: 6rpx solid #8b5cf6;
  background: linear-gradient(118deg, rgba(37, 27, 60, 0.94), rgba(20, 20, 35, 0.92) 58%);
  border-top-color: rgba(196, 181, 253, 0.17);
  border-right-color: rgba(196, 181, 253, 0.12);
  border-bottom-color: rgba(196, 181, 253, 0.12);
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.assignment-item:hover {
  transform: translateY(-2rpx);
  border-left-color: #c4b5fd;
  background: linear-gradient(118deg, rgba(46, 32, 76, 0.96), rgba(23, 22, 40, 0.94) 58%);
}

.assignment-item:active {
  transform: translateY(0);
}

.quiz-main {
  display: flex;
  justify-content: space-between;
  gap: 12rpx;
  padding: 22rpx;
}

.quiz-main-disabled {
  opacity: 0.72;
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

.assignment-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-bottom: 10rpx;
}

.teacher-assignment-tag {
  min-height: 36rpx;
  padding: 0 12rpx;
  border-radius: 999rpx;
  display: inline-flex;
  align-items: center;
  gap: 7rpx;
  background: linear-gradient(120deg, rgba(124, 58, 237, 0.38), rgba(168, 85, 247, 0.22));
  border: 1rpx solid rgba(196, 181, 253, 0.48);
}

.teacher-tag-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #ddd6fe;
  box-shadow: 0 0 8rpx rgba(221, 214, 254, 0.75);
}

.teacher-assignment-tag-text {
  font-size: 19rpx;
  line-height: 1;
  color: #ede9fe;
  font-weight: 600;
}

.deadline-tag {
  min-height: 34rpx;
  padding: 0 11rpx;
  border-radius: 999rpx;
  display: inline-flex;
  align-items: center;
  border: 1rpx solid transparent;
}

.deadline-tag-urgent {
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(251, 191, 36, 0.34);
}

.deadline-tag-missed {
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(252, 165, 165, 0.34);
}

.deadline-tag-text {
  font-size: 19rpx;
  color: #fbbf24;
}

.deadline-tag-missed .deadline-tag-text {
  color: #fca5a5;
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

.assignment-difficulty {
  background: rgba(167, 139, 250, 0.11);
  border-color: rgba(196, 181, 253, 0.25);
}

.assignment-difficulty-text {
  color: #c4b5fd;
}

.quiz-date {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.assignment-deadline {
  color: rgba(221, 214, 254, 0.68);
}

.quiz-status {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.status-completed,
.status-pending,
.status-in-progress,
.status-evaluating,
.status-failed {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6rpx;
}

.status-evaluating {
  flex-direction: row;
  align-items: center;
  gap: 8rpx;
}

.evaluating-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #60a5fa;
  animation: evaluatingPulse 1.2s ease-in-out infinite;
}

@keyframes evaluatingPulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.status-evaluating-text {
  color: #93c5fd;
}

.assignment-evaluating-dot {
  background: #a78bfa;
}

.assignment-evaluating-text {
  color: #c4b5fd;
}

.status-failed-text {
  color: #fca5a5;
}

.status-progress-count {
  font-size: 24rpx;
  color: #fbbf24;
  font-weight: 600;
}

.status-progress-text {
  color: #fcd34d;
}

.assignment-progress-count {
  color: #c4b5fd;
}

.assignment-progress-text {
  color: #ddd6fe;
}

.status-missed-text {
  color: #fca5a5;
}

.status-score {
  font-size: 24rpx;
  color: #86efac;
  font-weight: 600;
}

.assignment-score {
  color: #c4b5fd;
}

.assignment-score-label {
  color: rgba(221, 214, 254, 0.72);
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

.assignment-footer {
  justify-content: space-between;
  border-top-color: rgba(196, 181, 253, 0.11);
}

.assignment-open-hint {
  font-size: 21rpx;
  color: #c4b5fd;
}

.quiz-questions {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.62);
}
</style>
