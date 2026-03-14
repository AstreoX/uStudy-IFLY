<template>
  <view class="pxc-wrap" :class="{ 'pxc-expanded': detailVisible || isCollapsing }">
    <view
      class="pxc-pill"
      :class="{
        'pxc-pill-running': isRunning,
        'pxc-pill-failed': isFailed,
        'pxc-pill-clickable': canToggle
      }"
      @click="toggleExpand"
    >
      <image
        class="pxc-pill-icon"
        src="/static/icons/phosphor-icons/SVGs/regular/code.svg"
        mode="aspectFit"
      />
      <text class="pxc-pill-text">{{ pillText }}</text>
      <view v-if="isRunning" class="pxc-pill-spinner"></view>
      <image
        v-else-if="canToggle"
        class="pxc-pill-chevron"
        :class="{ 'pxc-pill-chevron-up': isExpanded }"
        src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
        mode="aspectFit"
      />
    </view>

    <view v-if="detailVisible || isCollapsing" :class="{ 'pxc-card-leave': isCollapsing }" class="pxc-card">
      <view class="pxc-card-header">
        <view class="pxc-icon-wrap">
          <image
            class="pxc-card-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/code.svg"
            mode="aspectFit"
          />
        </view>
        <view class="pxc-title-col">
          <text class="pxc-title">{{ headerTitle }}</text>
          <text class="pxc-meta">{{ headerMeta }}</text>
        </view>
        <view
          class="pxc-status-badge"
          :class="isFailed ? 'pxc-status-badge-failed' : 'pxc-status-badge-success'"
        >
          <image
            v-if="isSuccess"
            class="pxc-status-icon pxc-status-icon-success"
            src="/static/icons/lucide/circle-check.svg"
            mode="aspectFit"
          />
          <text v-else class="pxc-status-badge-text">失败</text>
        </view>
      </view>

      <view class="pxc-divider"></view>

      <view v-if="errorMessage" class="pxc-error-banner">
        <text class="pxc-error-banner-text">{{ errorMessage }}</text>
      </view>

      <view v-if="hasCode" class="pxc-section">
        <text class="pxc-section-label">执行代码</text>
        <view class="pxc-code-block">
          <text class="pxc-code-text">{{ codeContent }}</text>
        </view>
      </view>

      <view v-if="hasStdout" class="pxc-section">
        <text class="pxc-section-label">标准输出</text>
        <view class="pxc-output-block">
          <text class="pxc-output-text">{{ stdoutContent }}</text>
        </view>
      </view>

      <view v-if="hasStderr" class="pxc-section">
        <text class="pxc-section-label">错误输出</text>
        <view class="pxc-output-block pxc-output-block-error">
          <text class="pxc-output-text pxc-output-text-error">{{ stderrContent }}</text>
        </view>
      </view>

      <view v-if="hasImage" class="pxc-section">
        <text class="pxc-section-label">生成图像</text>
        <image
          :src="fullImageUrl"
          mode="widthFix"
          class="pxc-preview-img"
          @click="previewImage"
        />
      </view>

      <view v-if="showEmptyState" class="pxc-empty-state">
        <text class="pxc-empty-state-text">代码已执行，无文本或图像输出</text>
      </view>
    </view>
  </view>
</template>

<script>
import config from '@/config/index.js'

export default {
  name: 'PythonExecutionCard',
  props: {
    toolCall: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      isExpanded: this.toolCall?.status === 'done',
      isCollapsing: false
    }
  },
  computed: {
    status() {
      return this.toolCall?.status || ''
    },
    isRunning() {
      return this.status === 'running'
    },
    isDone() {
      return this.status === 'done'
    },
    isSuccess() {
      return this.isDone && !!this.toolCall?.success
    },
    isFailed() {
      return this.isDone && !this.toolCall?.success
    },
    canToggle() {
      return this.isDone
    },
    detailVisible() {
      return this.isDone && this.isExpanded
    },
    codeContent() {
      return this.toolCall?.arguments?.code || ''
    },
    stdoutContent() {
      return this.toolCall?.result?.stdout || ''
    },
    stderrContent() {
      return this.toolCall?.result?.stderr || ''
    },
    imageUrl() {
      return this.toolCall?.result?.image_url || ''
    },
    fullImageUrl() {
      if (!this.imageUrl) return ''
      if (this.imageUrl.startsWith('http')) return this.imageUrl
      return `${config.API_BASE_URL}${this.imageUrl}`
    },
    hasCode() {
      return !!this.codeContent
    },
    hasStdout() {
      return !!this.stdoutContent
    },
    hasStderr() {
      return !!this.stderrContent
    },
    hasImage() {
      return !!this.imageUrl
    },
    hasAnyRenderableOutput() {
      return this.hasStdout || this.hasStderr || this.hasImage
    },
    showEmptyState() {
      return this.isSuccess && !this.hasAnyRenderableOutput
    },
    codeLineCount() {
      if (!this.hasCode) return 0
      return this.codeContent.split(/\r?\n/).length
    },
    headerTitle() {
      return this.toolCall?.arguments?.description || 'Python 代码执行'
    },
    headerMeta() {
      const parts = []
      if (this.codeLineCount > 0) parts.push(`${this.codeLineCount} 行代码`)
      if (this.hasStdout) parts.push('stdout')
      if (this.hasStderr) parts.push('stderr')
      if (this.hasImage) parts.push('图像')
      if (!parts.length) {
        return this.isFailed ? '执行失败' : '无输出'
      }
      return parts.join(' · ')
    },
    pillText() {
      if (this.isRunning) return '正在执行 Python…'
      if (this.isFailed) return 'Python 执行失败'
      if (this.isSuccess) {
        if (this.hasStdout && this.hasImage) return '已执行 Python · 文本与图像输出'
        if (this.hasImage) return '已执行 Python · 图像输出'
        if (this.hasStdout) return '已执行 Python · 文本输出'
        return '已执行 Python'
      }
      return '执行 Python 代码'
    },
    errorMessage() {
      if (!this.isFailed) return ''
      return this.toolCall?.result?.message || 'Python 执行失败'
    }
  },
  watch: {
    'toolCall.status'(newStatus, oldStatus) {
      if (newStatus === 'done' && oldStatus !== 'done') {
        this.isExpanded = true
      }
    },
    'toolCall.id'(newId, oldId) {
      if (newId !== oldId) {
        this.isExpanded = this.toolCall?.status === 'done'
      }
    }
  },
  methods: {
    toggleExpand() {
      if (!this.canToggle) return
      if (this.isExpanded) {
        this.isCollapsing = true
        setTimeout(() => {
          this.isExpanded = false
          this.isCollapsing = false
        }, 200)
      } else {
        this.isExpanded = true
      }
    },
    previewImage() {
      if (!this.fullImageUrl) return
      uni.previewImage({
        urls: [this.fullImageUrl],
        current: this.fullImageUrl
      })
    }
  }
}
</script>

<style scoped>
.pxc-wrap {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.pxc-expanded {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 0;
  gap: 0;
}

.pxc-expanded .pxc-pill {
  border: none;
  background: transparent;
  border-radius: 24rpx 24rpx 0 0;
  padding: 20rpx 24rpx 16rpx;
}

.pxc-expanded .pxc-card {
  border: none;
  background: transparent;
  border-radius: 0 0 24rpx 24rpx;
}

.pxc-pill {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 24rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  transition: all 0.25s ease;
}

.pxc-pill-clickable:active {
  background: rgba(255, 255, 255, 0.08);
}

.pxc-pill-running {
  border-color: rgba(74, 108, 247, 0.3);
  background: rgba(74, 108, 247, 0.06);
}

.pxc-pill-failed {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.pxc-card-leave {
  animation: pxc-card-leave 0.2s ease-in forwards;
  pointer-events: none;
}

.pxc-pill-icon {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.pxc-pill-failed .pxc-pill-icon {
  filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
}

.pxc-pill-text {
  flex: 1;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.pxc-pill-running .pxc-pill-text {
  color: rgba(255, 255, 255, 0.8);
}

.pxc-pill-spinner {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid rgba(74, 108, 247, 0.3);
  border-top-color: #4a6cf7;
  border-radius: 50%;
  animation: pxc-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.pxc-pill-chevron {
  width: 24rpx;
  height: 24rpx;
  flex-shrink: 0;
  opacity: 0.35;
  filter: brightness(0) invert(1);
  transition: transform 0.2s ease;
}

.pxc-pill-chevron-up {
  transform: rotate(180deg);
}

.pxc-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 24rpx 28rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  animation: pxc-card-enter 0.28s ease-out;
}

.pxc-card-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.pxc-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  background: rgba(74, 108, 247, 0.1);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.pxc-card-icon {
  width: 32rpx;
  height: 32rpx;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.pxc-title-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.pxc-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.3;
}

.pxc-meta {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

.pxc-status-badge {
  min-width: 64rpx;
  min-height: 64rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pxc-status-badge-success {
  min-width: 30rpx;
  min-height: 30rpx;
  padding: 0;
  background: transparent;
}

.pxc-status-badge-failed {
  background: rgba(239, 68, 68, 0.14);
}

.pxc-status-icon {
  width: 30rpx;
  height: 30rpx;
}

.pxc-status-icon-success {
  filter: brightness(0) saturate(100%) invert(61%) sepia(87%) saturate(552%) hue-rotate(87deg) brightness(93%) contrast(90%);
}

.pxc-status-badge-text {
  font-size: 20rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.82);
}

.pxc-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
}

.pxc-error-banner {
  padding: 16rpx 18rpx;
  background: rgba(239, 68, 68, 0.08);
  border: 1rpx solid rgba(239, 68, 68, 0.16);
  border-radius: 16rpx;
}

.pxc-error-banner-text {
  font-size: 24rpx;
  line-height: 1.5;
  color: rgba(248, 113, 113, 0.92);
}

.pxc-section {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.pxc-section-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.pxc-code-block,
.pxc-output-block {
  max-height: 420rpx;
  overflow: auto;
  padding: 18rpx 20rpx;
  border-radius: 16rpx;
}

.pxc-code-block {
  background: rgba(0, 0, 0, 0.35);
}

.pxc-output-block {
  background: rgba(0, 0, 0, 0.25);
}

.pxc-output-block-error {
  background: rgba(220, 38, 38, 0.1);
  border-left: 4rpx solid rgba(220, 38, 38, 0.4);
}

.pxc-code-text,
.pxc-output-text {
  font-family: 'Menlo', 'Consolas', monospace;
  font-size: 22rpx;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.84);
}

.pxc-code-text {
  white-space: pre;
}

.pxc-output-text {
  white-space: pre-wrap;
  word-break: break-all;
}

.pxc-output-text-error {
  color: rgba(248, 113, 113, 0.92);
}

.pxc-preview-img {
  width: 100%;
  border-radius: 12rpx;
}

.pxc-empty-state {
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pxc-empty-state-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.42);
}

@keyframes pxc-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pxc-card-enter {
  from {
    opacity: 0;
    transform: translateY(-8rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pxc-card-leave {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-8rpx);
  }
}
</style>
