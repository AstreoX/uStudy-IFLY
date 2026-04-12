<template>
  <view class="artifact-card" :class="cardClass">
    <!-- Header -->
    <view class="ac-header">
      <view v-if="isGenerating" class="ac-spinner"></view>
      <svg v-else-if="isSuccess" viewBox="0 0 256 256" class="ac-status-icon ac-status-success">
        <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <svg v-else-if="isDone && !isSuccess" viewBox="0 0 256 256" class="ac-status-icon ac-status-failed">
        <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <!-- Code icon -->
      <svg viewBox="0 0 256 256" class="ac-icon">
        <polyline points="64 88 16 128 64 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        <polyline points="192 88 240 128 192 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        <line x1="160" y1="40" x2="96" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <text class="ac-title-text">{{ headerText }}</text>
    </view>

    <!-- Body -->
    <view class="ac-body">
      <!-- Generating -->
      <template v-if="isGenerating">
        <text class="ac-status-text">正在生成交互演示，完成后会通知你...</text>
        <view class="ac-progress-bar">
          <view class="ac-progress-fill"></view>
        </view>
      </template>

      <!-- Done -->
      <template v-else-if="isSuccess">
        <text class="ac-status-text ac-done-text">交互演示已生成</text>
        <view class="ac-view-btn" @click="handleViewArtifact">
          <text class="ac-view-btn-text">在笔记面板查看</text>
        </view>
      </template>

      <!-- Failed -->
      <template v-else-if="isDone && !isSuccess">
        <text class="ac-status-text ac-error-text">{{ toolCall.result?.message || '生成失败' }}</text>
      </template>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ArtifactCreationCard',
  props: {
    toolCall: {
      type: Object,
      required: true
    },
    spaceId: {
      type: [String, Number],
      default: ''
    },
    conversationId: {
      type: [String, Number],
      default: ''
    }
  },
  computed: {
    isGenerating() {
      return this.toolCall.status === 'running' ||
        (this.toolCall.status === 'done' && this.toolCall.success && this.toolCall.result?.status === 'generating')
    },
    isDone() {
      return this.toolCall.status === 'done'
    },
    isSuccess() {
      return this.isDone && this.toolCall.success && this.toolCall.result?.status !== 'generating'
    },
    artifactTitle() {
      return this.toolCall.arguments?.title || this.toolCall.result?.title || '交互演示'
    },
    headerText() {
      const tool = this.toolCall.tool
      if (tool === 'update_artifact') {
        return `更新演示「${this.artifactTitle}」`
      }
      return `创建演示「${this.artifactTitle}」`
    },
    cardClass() {
      if (this.isGenerating) return 'ac-generating'
      if (this.isSuccess) return 'ac-success'
      if (this.isDone && !this.isSuccess) return 'ac-failed'
      return ''
    }
  },
  methods: {
    handleViewArtifact() {
      this.$emit('view-artifact', {
        noteId: this.toolCall.result?.note_id,
        spaceId: this.spaceId
      })
    }
  }
}
</script>

<style scoped>
.artifact-card {
  margin: 8px 0;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
  overflow: hidden;
  transition: border-color 0.2s;
}
.ac-generating {
  border-color: rgba(99, 102, 241, 0.25);
}
.ac-success {
  border-color: rgba(52, 211, 153, 0.2);
  background: rgba(52, 211, 153, 0.06);
}
.ac-failed {
  border-color: rgba(248, 113, 113, 0.2);
  background: rgba(248, 113, 113, 0.06);
}

.ac-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px 6px;
}

.ac-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(138, 180, 248, 0.7);
  border-radius: 50%;
  animation: ac-spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes ac-spin {
  to { transform: rotate(360deg); }
}

.ac-status-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
.ac-status-success {
  color: #34d399;
}
.ac-status-failed {
  color: #f87171;
}

.ac-icon {
  width: 14px;
  height: 14px;
  color: rgba(99, 102, 241, 0.7);
  flex-shrink: 0;
}

.ac-title-text {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ac-body {
  padding: 6px 14px 12px;
}

.ac-status-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.ac-done-text {
  color: rgba(52, 211, 153, 0.7);
}
.ac-error-text {
  color: rgba(248, 113, 113, 0.7);
}

.ac-progress-bar {
  margin-top: 8px;
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}
.ac-progress-fill {
  height: 100%;
  width: 40%;
  border-radius: 2px;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.5), rgba(138, 180, 248, 0.6));
  animation: ac-progress 1.5s ease-in-out infinite;
}
@keyframes ac-progress {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

.ac-view-btn {
  display: inline-flex;
  margin-top: 8px;
  padding: 5px 12px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  cursor: pointer;
  transition: background 0.15s;
}
.ac-view-btn:hover {
  background: rgba(99, 102, 241, 0.25);
}
.ac-view-btn-text {
  font-size: 12px;
  color: rgba(138, 180, 248, 0.9);
}
</style>
