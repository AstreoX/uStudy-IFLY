<template>
  <view
    class="agc-wrap"
    :class="[
      themeClass,
      {
        'agc-expanded': detailVisible || isCollapsing,
        'agc-expanded-success': isDone && (detailVisible || isCollapsing)
      }
    ]"
  >
    <view
      class="agc-pill"
      :class="{
        'agc-pill-generating': isGenerating,
        'agc-pill-success': isDone,
        'agc-pill-failed': isFailed
      }"
      @click="toggleExpand"
    >
      <view class="agc-pill-icon-wrapper">
        <svg viewBox="0 0 256 256" class="agc-pill-icon">
          <polyline points="64 88 16 128 64 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          <polyline points="192 88 240 128 192 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          <line x1="160" y1="40" x2="96" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        </svg>
      </view>
      <text class="agc-pill-text">{{ pillText }}</text>
      <view v-if="isGenerating" class="agc-pill-spinner"></view>
      <view v-else class="agc-pill-chevron" :class="{ 'agc-pill-chevron-up': detailVisible }">⌄</view>
    </view>

    <view v-if="detailVisible || isCollapsing" :class="{ 'agc-card-leave': isCollapsing }" class="agc-card">
      <view class="agc-card-header">
        <view class="agc-icon-wrap">
          <svg viewBox="0 0 256 256" class="agc-card-icon">
            <polyline points="64 88 16 128 64 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <polyline points="192 88 240 128 192 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <line x1="160" y1="40" x2="96" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          </svg>
        </view>
        <view class="agc-title-col">
          <text class="agc-title">{{ headerTitle }}</text>
          <text class="agc-meta">{{ headerMeta }}</text>
        </view>
        <view class="agc-status-badge">
          <view v-if="isGenerating" class="agc-status-spinner"></view>
          <svg v-else-if="isDone" viewBox="0 0 256 256" class="agc-status-icon agc-status-icon-success">
            <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          </svg>
          <svg v-else viewBox="0 0 256 256" class="agc-status-icon">
            <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          </svg>
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
            <svg viewBox="0 0 256 256" class="agc-code-nav-icon">
              <polyline points="110 72 150 112 110 152" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="140" y1="64" x2="140" y2="192" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
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
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

export default {
  name: 'ArtifactCreationCard',
  props: {
    toolCall: {
      type: Object,
      required: true
    },
    themeMode: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      isExpanded: true,
      isCollapsing: false,
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
    },
    resolvedThemeMode() {
      return normalizeThemeMode(this.themeMode || getStoredThemeMode('dark'))
    },
    themeClass() {
      return `theme-${this.resolvedThemeMode}`
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
      this.$emit('view-artifact', {
        noteId: this.result.note_id,
        spaceId: this.result.space_id || null
      })
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

.agc-expanded {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.07);
  border-radius: 20rpx;
  padding: 0;
  gap: 0;
  box-shadow: 0 6rpx 24rpx rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.agc-expanded .agc-pill {
  border: none;
  background: transparent;
  border-radius: 20rpx 20rpx 0 0;
  padding: 16rpx 20rpx 12rpx;
}

.agc-expanded .agc-card {
  border: none;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
  background: transparent;
  border-radius: 0;
  box-shadow: none;
}

.agc-pill {
  display: flex;
  align-items: center;
  gap: 14rpx;
  padding: 14rpx 20rpx;
  border-radius: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.04);
  transition: background 0.2s ease, border-color 0.2s ease;
  box-shadow: 0 3rpx 12rpx rgba(0, 0, 0, 0.18);
}

.agc-pill-generating {
  border-color: rgba(74, 108, 247, 0.28);
  background: rgba(74, 108, 247, 0.06);
}

.agc-pill-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.agc-pill-success:hover {
  border-color: rgba(34, 197, 94, 0.5);
  background: rgba(34, 197, 94, 0.1);
}

.agc-expanded-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(255, 255, 255, 0.03);
}

.agc-expanded-success .agc-pill {
  background: rgba(34, 197, 94, 0.06);
}

.agc-expanded-success .agc-card {
  border-top-color: rgba(34, 197, 94, 0.16);
  background: rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.agc-pill-success .agc-pill-icon,
.agc-expanded-success .agc-card-icon {
  filter: brightness(0) saturate(100%) invert(75%) sepia(52%) saturate(594%) hue-rotate(86deg) brightness(97%) contrast(91%);
}

.agc-pill-icon-wrapper {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
}

.agc-pill-icon,
.agc-card-icon {
  width: 100%;
  height: 100%;
  display: block;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.agc-pill-failed {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.06);
}

.agc-pill-text {
  flex: 1;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
}

.agc-pill-spinner {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid rgba(74, 108, 247, 0.3);
  border-top-color: #4A6CF7;
  border-radius: 50%;
  animation: agc-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.agc-pill-chevron {
  width: 24rpx;
  height: 24rpx;
  flex-shrink: 0;
  opacity: 0.35;
  color: rgba(255, 255, 255, 0.72);
  transition: transform 0.2s ease;
  text-align: center;
  line-height: 24rpx;
}

.agc-pill-chevron-up {
  transform: rotate(180deg);
}

.agc-card-leave {
  animation: agc-card-leave 0.2s ease-in forwards;
  pointer-events: none;
}

.agc-card {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  padding: 18rpx 22rpx 16rpx;
  border-radius: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
  animation: agc-card-enter 0.28s ease-out;
  box-shadow: 0 3rpx 12rpx rgba(0, 0, 0, 0.15);
}

.agc-card-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.agc-icon-wrap {
  width: 44rpx;
  height: 44rpx;
  border-radius: 12rpx;
  background: rgba(74, 108, 247, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agc-title-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.agc-title {
  font-size: 26rpx;
  font-weight: 500;
  line-height: 1.3;
  color: rgba(255, 255, 255, 0.85);
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
}

.agc-status-spinner {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid rgba(74, 108, 247, 0.28);
  border-top-color: #4A6CF7;
  border-radius: 50%;
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
  padding: 16rpx 18rpx 80rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.025);
  border: 1rpx solid rgba(255, 255, 255, 0.05);
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
  color: rgba(255, 255, 255, 0.8);
}

.agc-wrap.theme-light.agc-expanded {
  background: rgba(255, 250, 244, 0.94);
  border-color: rgba(63, 53, 42, 0.1);
  box-shadow: 0 14rpx 36rpx rgba(118, 101, 80, 0.14);
}

.agc-wrap.theme-light .agc-pill,
.agc-wrap.theme-light .agc-card {
  background: rgba(255, 250, 244, 0.86);
  border-color: rgba(63, 53, 42, 0.1);
}

.agc-wrap.theme-light .agc-pill-generating {
  background: rgba(47, 110, 234, 0.08);
  border-color: rgba(47, 110, 234, 0.18);
}

.agc-wrap.theme-light .agc-pill-failed {
  background: rgba(209, 79, 79, 0.06);
  border-color: rgba(209, 79, 79, 0.18);
}

.agc-wrap.theme-light .agc-pill-success {
  background: linear-gradient(rgba(34, 197, 94, 0.08), rgba(34, 197, 94, 0.08)), rgba(255, 250, 244, 0.86);
  border-color: rgba(34, 197, 94, 0.28);
}

.agc-wrap.theme-light.agc-expanded-success {
  background: rgba(255, 250, 244, 0.94);
  border-color: rgba(34, 197, 94, 0.28);
}

.agc-wrap.theme-light.agc-expanded-success .agc-card {
  background: rgba(255, 250, 244, 0.72);
  border-top-color: rgba(34, 197, 94, 0.14);
}

.agc-wrap.theme-light .agc-pill-success .agc-pill-icon,
.agc-wrap.theme-light.agc-expanded-success .agc-card-icon {
  filter: brightness(0) saturate(100%) invert(48%) sepia(83%) saturate(522%) hue-rotate(86deg) brightness(89%) contrast(92%);
}

.agc-wrap.theme-light .agc-icon-wrap {
  background: rgba(47, 110, 234, 0.1);
}

.agc-wrap.theme-light .agc-card-icon,
.agc-wrap.theme-light .agc-pill-icon {
  filter: brightness(0) saturate(100%) invert(34%) sepia(61%) saturate(1869%) hue-rotate(211deg) brightness(96%) contrast(91%);
}

.agc-wrap.theme-light .agc-pill-chevron {
  color: rgba(31, 26, 22, 0.72);
}

.agc-wrap.theme-light .agc-title,
.agc-wrap.theme-light .agc-code-text {
  color: #1F1A16;
}

.agc-wrap.theme-light .agc-pill-text,
.agc-wrap.theme-light .agc-meta,
.agc-wrap.theme-light .agc-section-label,
.agc-wrap.theme-light .agc-empty-state-text {
  color: rgba(31, 26, 22, 0.58);
}

.agc-wrap.theme-light .agc-section-meta {
  color: #2F6EEA;
}

.agc-wrap.theme-light .agc-divider {
  background: rgba(63, 53, 42, 0.08);
}

.agc-wrap.theme-light .agc-code-block {
  background: rgba(63, 53, 42, 0.08);
}

.agc-wrap.theme-light .agc-empty-state {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(63, 53, 42, 0.08);
}

@keyframes agc-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes agc-card-enter {
  from {
    opacity: 0;
    transform: translateY(-8rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes agc-card-leave {
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
