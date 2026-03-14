<template>
  <view class="agc-wrap">
    <view
      class="agc-pill"
      :class="{
        'agc-pill-generating': isGenerating,
        'agc-pill-done': isDone,
        'agc-pill-failed': isFailed,
        'agc-pill-expanded': detailVisible
      }"
      @click="toggleExpand"
    >
      <image
        class="agc-pill-icon"
        src="/static/icons/phosphor-icons/SVGs/regular/code.svg"
        mode="aspectFit"
      />
      <text class="agc-pill-text">{{ pillText }}</text>
      <view v-if="isGenerating" class="agc-pill-spinner"></view>
      <image
        class="agc-pill-chevron"
        :class="{ 'agc-pill-chevron-up': detailVisible }"
        src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
        mode="aspectFit"
      />
    </view>

    <view v-if="detailVisible" class="agc-card">
      <view class="agc-card-header">
        <view class="agc-icon-wrap">
          <image
            class="agc-card-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/code.svg"
            mode="aspectFit"
          />
        </view>
        <view class="agc-title-col">
          <text class="agc-title">{{ headerTitle }}</text>
          <text class="agc-meta">{{ headerMeta }}</text>
        </view>
        <view class="agc-status-badge">
          <view v-if="isGenerating" class="agc-status-spinner"></view>
          <image
            v-else-if="isDone"
            class="agc-status-icon agc-status-icon-success"
            src="/static/icons/lucide/circle-check.svg"
            mode="aspectFit"
          />
          <image
            v-else
            class="agc-status-icon"
            src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
            mode="aspectFit"
          />
        </view>
      </view>

      <view class="agc-divider"></view>

      <view v-if="errorMessage" class="agc-error-banner">
        <text class="agc-error-banner-text">{{ errorMessage }}</text>
      </view>

      <view v-if="hasCode" class="agc-section">
        <view class="agc-section-head">
          <text class="agc-section-label">生成代码</text>
          <text v-if="isGenerating" class="agc-section-meta">实时生成中</text>
        </view>
        <view class="agc-code-block-wrap">
          <scroll-view
            scroll-y
            class="agc-code-block"
            :scroll-top="codeScrollTop"
            @scroll="handleCodeScroll"
          >
            <text class="agc-code-text">{{ codeSnapshot }}</text>
          </scroll-view>
          <view
            v-if="isDone && hasViewer"
            class="agc-code-nav"
            @click.stop="emitView"
          >
            <image
              class="agc-code-nav-icon"
              src="/static/icons/phosphor-icons/SVGs/fill/arrow-fat-right-fill.svg"
              mode="aspectFit"
            />
          </view>
        </view>
      </view>

      <view v-else-if="isGenerating" class="agc-empty-state">
        <text class="agc-empty-state-text">正在接收交互式笔记代码…</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ArtifactGenerationCard',
  props: {
    toolCall: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      isExpanded: true,
      codeScrollTop: 0,
      suppressAutoScrollUntil: 0,
      ignoreScrollEventsUntil: 0,
      autoScrollResumeTimer: null
    }
  },
  computed: {
    result() {
      return this.toolCall?.result || {}
    },
    artifactState() {
      if (this.toolCall?.status === 'running') return 'streaming'
      if (this.result.artifact_progress_status) return this.result.artifact_progress_status
      if (this.result.status) return this.result.status
      if (this.toolCall?.status === 'done' && !this.toolCall?.success) return 'failed'
      if (this.toolCall?.status === 'done') return 'done'
      return 'streaming'
    },
    isGenerating() {
      return this.artifactState === 'generating' || this.artifactState === 'streaming'
    },
    isDone() {
      return this.artifactState === 'done'
    },
    isFailed() {
      return this.artifactState === 'failed'
    },
    detailVisible() {
      return this.isExpanded
    },
    codeSnapshot() {
      return this.result.code_snapshot || ''
    },
    hasCode() {
      return !!this.codeSnapshot
    },
    codeLineCount() {
      if (!this.codeSnapshot) return 0
      return this.codeSnapshot.split(/\r?\n/).length
    },
    headerTitle() {
      return this.result.artifact_title || this.result.title || this.toolCall?.arguments?.title || '交互演示'
    },
    headerMeta() {
      const parts = []
      if (this.codeLineCount > 0) {
        parts.push(`${this.codeLineCount} 行代码`)
      }
      if (this.isGenerating) {
        parts.push('生成中')
      } else if (this.isDone && this.result.html_size) {
        parts.push(`${this.formatBytes(this.result.html_size)}`)
      } else if (this.isFailed) {
        parts.push('生成失败')
      }
      return parts.join(' · ') || '交互式 HTML'
    },
    pillText() {
      if (this.isGenerating) return '正在生成交互演示…'
      if (this.isFailed) return '交互演示生成失败'
      if (this.isDone) return '已生成交互演示'
      return '交互演示'
    },
    errorMessage() {
      if (!this.isFailed) return ''
      return this.result.message || '交互演示生成失败'
    },
    hasViewer() {
      return !!this.result.note_id
    }
  },
  watch: {
    artifactState(newState, oldState) {
      if (
        (newState === 'done' || newState === 'failed') &&
        newState !== oldState
      ) {
        this.isExpanded = true
        this.$nextTick(() => {
          this.scrollCodeToBottom(true)
        })
      }
    },
    codeSnapshot(newValue, oldValue) {
      if (newValue === oldValue || !this.detailVisible) return
      this.$nextTick(() => {
        this.scrollCodeToBottom()
      })
    },
    detailVisible(visible) {
      if (visible) {
        this.$nextTick(() => {
          this.scrollCodeToBottom(true)
        })
      }
    },
    'toolCall.id'(newId, oldId) {
      if (newId !== oldId) {
        this.isExpanded = true
        this.codeScrollTop = 0
        this.suppressAutoScrollUntil = 0
        this.ignoreScrollEventsUntil = 0
        this.clearAutoScrollTimer()
      }
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.scrollCodeToBottom(true)
    })
  },
  beforeDestroy() {
    this.clearAutoScrollTimer()
  },
  methods: {
    toggleExpand() {
      this.isExpanded = !this.isExpanded
    },
    handleCodeScroll() {
      const now = Date.now()
      if (now < this.ignoreScrollEventsUntil) return

      this.suppressAutoScrollUntil = now + 3000
      this.clearAutoScrollTimer()
      this.autoScrollResumeTimer = setTimeout(() => {
        this.suppressAutoScrollUntil = 0
        if (this.isGenerating && this.detailVisible) {
          this.scrollCodeToBottom(true)
        }
      }, 3000)
    },
    scrollCodeToBottom(force = false) {
      if (!this.hasCode || !this.detailVisible) return
      if (!force && Date.now() < this.suppressAutoScrollUntil) return

      this.ignoreScrollEventsUntil = Date.now() + 400
      this.codeScrollTop += 100000
    },
    clearAutoScrollTimer() {
      if (this.autoScrollResumeTimer) {
        clearTimeout(this.autoScrollResumeTimer)
        this.autoScrollResumeTimer = null
      }
    },
    emitView() {
      if (!this.hasViewer) return
      this.$emit('view')
    },
    formatBytes(bytes) {
      const value = Number(bytes)
      if (!value) return ''
      if (value < 1024) return `${value} B`
      if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
      return `${(value / (1024 * 1024)).toFixed(1)} MB`
    }
  }
}
</script>

<style scoped>
.agc-wrap {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.agc-pill {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 24rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  transition: all 0.25s ease;
}

.agc-pill-generating {
  border-color: rgba(74, 108, 247, 0.28);
  background: rgba(74, 108, 247, 0.06);
}

.agc-pill-done,
.agc-pill-expanded {
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
}

.agc-pill-failed {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.06);
}

.agc-pill-icon {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.agc-pill-failed .agc-pill-icon {
  filter: invert(34%) sepia(92%) saturate(1478%) hue-rotate(336deg) brightness(94%) contrast(94%);
}

.agc-pill-text {
  flex: 1;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
}

.agc-pill-spinner,
.agc-status-spinner {
  border-radius: 50%;
  animation: agc-spin 0.8s linear infinite;
}

.agc-pill-spinner {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
  border: 2rpx solid rgba(74, 108, 247, 0.3);
  border-top-color: #4a6cf7;
}

.agc-pill-chevron {
  width: 24rpx;
  height: 24rpx;
  flex-shrink: 0;
  opacity: 0.35;
  filter: brightness(0) invert(1);
  transition: transform 0.2s ease;
}

.agc-pill-chevron-up {
  transform: rotate(180deg);
}

.agc-card {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  padding: 24rpx 28rpx 20rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  animation: agc-card-enter 0.28s ease-out;
}

.agc-card-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.agc-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  border-radius: 16rpx;
  background: rgba(74, 108, 247, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agc-card-icon {
  width: 32rpx;
  height: 32rpx;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.agc-title-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.agc-title {
  font-size: 28rpx;
  font-weight: 600;
  line-height: 1.3;
  color: rgba(255, 255, 255, 0.95);
}

.agc-meta {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.42);
}

.agc-status-badge {
  min-width: 30rpx;
  min-height: 30rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: transparent;
}

.agc-status-spinner {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid rgba(74, 108, 247, 0.28);
  border-top-color: #4a6cf7;
}

.agc-status-icon {
  width: 30rpx;
  height: 30rpx;
}

.agc-status-icon-success {
  filter: brightness(0) saturate(100%) invert(61%) sepia(87%) saturate(552%) hue-rotate(87deg) brightness(93%) contrast(90%);
}

.agc-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
}

.agc-error-banner {
  padding: 16rpx 18rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(239, 68, 68, 0.16);
  background: rgba(239, 68, 68, 0.08);
}

.agc-error-banner-text {
  font-size: 24rpx;
  line-height: 1.5;
  color: rgba(248, 113, 113, 0.92);
}

.agc-section {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.agc-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.agc-section-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.45);
}

.agc-section-meta {
  font-size: 20rpx;
  color: rgba(74, 108, 247, 0.78);
}

.agc-code-block {
  height: 520rpx;
  padding: 18rpx 20rpx 88rpx;
  border-radius: 16rpx;
  background: rgba(0, 0, 0, 0.35);
  box-sizing: border-box;
}

.agc-code-block-wrap {
  position: relative;
}

.agc-code-text {
  font-family: 'Menlo', 'Consolas', monospace;
  font-size: 22rpx;
  line-height: 1.55;
  white-space: pre;
  color: rgba(255, 255, 255, 0.84);
}

.agc-empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20rpx;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.agc-empty-state-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.42);
}

.agc-code-nav {
  position: absolute;
  right: 20rpx;
  bottom: 20rpx;
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agc-code-nav-icon {
  width: 36rpx;
  height: 36rpx;
  filter: brightness(0) invert(1);
}

@keyframes agc-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes agc-card-enter {
  from {
    opacity: 0;
    transform: translateY(8rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
