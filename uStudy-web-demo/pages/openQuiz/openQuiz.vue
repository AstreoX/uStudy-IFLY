<template>
  <view class="open-quiz-page">
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-blue"></view>
      <view class="aurora-blob aurora-blob-orange"></view>
      <view class="aurora-blob aurora-blob-gold"></view>
    </view>

    <view class="content-card">
      <text class="eyebrow">uStudy 复习测试</text>
      <text class="title">{{ titleText }}</text>
      <text class="subtitle">{{ subtitleText }}</text>

      <view v-if="quizId" class="quiz-chip">
        <text class="quiz-chip-text">Quiz ID: {{ shortQuizId }}</text>
      </view>

      <view class="actions">
        <button class="action-btn action-btn-primary" @tap="handleContinueWeb">
          <text class="action-btn-text">在网页端打开测试</text>
        </button>
      </view>

      <text class="hint">{{ hintText }}</text>
    </view>
  </view>
</template>

<script>
import { getQuizDetail } from '@/api/space'
import { getTokens } from '@/utils/storage'

export default {
  data() {
    return {
      quizId: '',
      openState: 'ready'
    }
  },
  computed: {
    shortQuizId() {
      if (!this.quizId) return ''
      return this.quizId.length > 16
        ? `${this.quizId.slice(0, 8)}...${this.quizId.slice(-4)}`
        : this.quizId
    },
    titleText() {
      if (!this.quizId) return '链接无效'
      if (this.openState === 'loading') return '正在加载复习测试'
      return '打开复习测试'
    },
    subtitleText() {
      if (!this.quizId) return '这个复习测试链接缺少 quizId 参数，请联系实验管理员。'
      return '使用分配的实验账号登录后，可直接在网页中完成测试。'
    },
    hintText() {
      if (!this.quizId) return '请检查链接是否完整。'
      return '测试将在当前浏览器中打开。'
    }
  },
  onLoad(options) {
    this.quizId = String(options.quizId || '').trim()
  },
  methods: {
    async handleContinueWeb() {
      if (!this.quizId) return
      const target = `/pages/openQuiz/openQuiz?quizId=${encodeURIComponent(this.quizId)}`
      const tokens = getTokens()
      if (!tokens?.access_token) {
        uni.reLaunch({
          url: `/pages/login/login?redirect=${encodeURIComponent(target)}`
        })
        return
      }

      this.openState = 'loading'
      try {
        const quiz = await getQuizDetail(this.quizId)
        uni.reLaunch({
          url: `/pages/study/study?spaceId=${encodeURIComponent(quiz.space_id)}&quizId=${encodeURIComponent(this.quizId)}`
        })
      } catch (error) {
        this.openState = 'ready'
        uni.showToast({ title: '测试加载失败，请联系实验管理员', icon: 'none' })
      }
    }
  }
}
</script>

<style>
.open-quiz-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse 80% 60% at 20% 15%, rgba(59, 130, 246, 0.14) 0%, transparent 70%),
    radial-gradient(ellipse 70% 50% at 78% 18%, rgba(249, 115, 22, 0.12) 0%, transparent 70%),
    linear-gradient(160deg, #101523 0%, #142036 45%, #0e1829 100%);
}

.aurora-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 999px;
  filter: blur(84px);
  opacity: 0.75;
}

.aurora-blob-blue {
  width: 360px;
  height: 360px;
  top: -80px;
  left: -40px;
  background: rgba(59, 130, 246, 0.28);
}

.aurora-blob-orange {
  width: 320px;
  height: 320px;
  right: -60px;
  bottom: -40px;
  background: rgba(249, 115, 22, 0.22);
}

.aurora-blob-gold {
  width: 240px;
  height: 240px;
  top: 45%;
  left: 58%;
  background: rgba(245, 158, 11, 0.12);
}

.content-card {
  width: 100%;
  max-width: 460px;
  position: relative;
  z-index: 1;
  background: rgba(13, 18, 28, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 28px;
  padding: 32px 26px;
  box-sizing: border-box;
  backdrop-filter: blur(24px);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
}

.eyebrow {
  display: block;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.52);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  margin-bottom: 16px;
}

.title {
  display: block;
  font-size: 30px;
  line-height: 1.2;
  color: #f7f8fb;
  font-weight: 700;
}

.subtitle {
  display: block;
  margin-top: 14px;
  font-size: 15px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.74);
}

.quiz-chip {
  display: inline-flex;
  align-items: center;
  margin-top: 18px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.quiz-chip-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
  letter-spacing: 0.04em;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 28px;
}

.action-btn {
  width: 100%;
  height: 48px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
}

.action-btn::after {
  border: none;
}

.action-btn-primary {
  background: linear-gradient(135deg, #2f6eea 0%, #548cff 100%);
  box-shadow: 0 12px 24px rgba(47, 110, 234, 0.24);
}

.action-btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.action-btn-ghost {
  background: transparent;
}

.action-btn-text {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: 0.02em;
}

.action-btn-text-ghost {
  color: rgba(255, 255, 255, 0.72);
}

.hint {
  display: block;
  margin-top: 18px;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.48);
}
</style>
