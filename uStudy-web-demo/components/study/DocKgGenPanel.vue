<template>
  <view class="dkg-panel">
    <!-- Phase Indicator -->
    <view class="dkg-phases">
      <view
        v-for="(step, idx) in phases"
        :key="step.id"
        class="dkg-phase"
        :class="{
          'dkg-phase--active': currentPhaseIdx === idx,
          'dkg-phase--done': currentPhaseIdx > idx,
        }"
      >
        <view class="dkg-phase-dot">
          <text v-if="currentPhaseIdx > idx" class="dkg-phase-check">&#10003;</text>
          <text v-else class="dkg-phase-num">{{ idx + 1 }}</text>
        </view>
        <text class="dkg-phase-label">{{ step.label }}</text>
      </view>
    </view>

    <!-- Streaming Content Area -->
    <scroll-view
      ref="contentScroll"
      class="dkg-content"
      scroll-y
      :scroll-top="scrollTop"
    >
      <!-- Phase 1: Extraction Progress -->
      <view v-if="currentPhaseIdx === 0" class="dkg-extraction">
        <view class="dkg-progress-bar-wrap">
          <view class="dkg-progress-bar" :style="{ width: progressPercent + '%' }"></view>
        </view>
        <text class="dkg-progress-text">
          {{ extractionText }}
        </text>
      </view>

      <!-- Phase 2: Streaming KG Text -->
      <view v-if="currentPhaseIdx >= 1" class="dkg-stream">
        <view class="dkg-stream-block">
          <text class="dkg-stream-text">{{ streamText || '正在生成知识图谱...' }}</text>
          <text v-if="currentPhaseIdx === 1" class="dkg-cursor">|</text>
        </view>
      </view>

      <!-- Done -->
      <view v-if="isDone" class="dkg-done">
        <view class="dkg-done-icon">&#10003;</view>
        <text class="dkg-done-text">
          知识图谱生成完成：{{ nodeCount }} 个节点，{{ edgeCount }} 条关系
        </text>
      </view>

      <!-- Error -->
      <view v-if="errorMsg" class="dkg-error">
        <text class="dkg-error-text">{{ errorMsg }}</text>
      </view>
    </scroll-view>
  </view>
</template>

<script>
import { streamKnowledgeGraphFromDocuments } from '@/api/space'

export default {
  props: {
    spaceId: { type: String, required: true },
    documentIds: { type: Array, required: true },
    userPreference: { type: String, default: null },
  },

  data() {
    return {
      phases: [
        { id: 'extraction', label: '分析文档' },
        { id: 'consolidation', label: '生成图谱' },
        { id: 'done', label: '完成' },
      ],
      currentPhaseIdx: 0,
      completed: 0,
      totalChunks: 0,
      streamText: '',
      nodeCount: 0,
      edgeCount: 0,
      isDone: false,
      errorMsg: null,
      scrollTop: 0,
      _cancelSSE: null,
    }
  },

  computed: {
    progressPercent() {
      if (this.totalChunks === 0) return 0
      return Math.round((this.completed / this.totalChunks) * 100)
    },
    extractionText() {
      if (this.totalChunks === 0) return '正在准备...'
      return `正在分析文档片段... (${this.completed}/${this.totalChunks})`
    },
  },

  mounted() {
    this.startGeneration()
  },

  beforeDestroy() {
    if (this._cancelSSE) {
      this._cancelSSE()
      this._cancelSSE = null
    }
  },

  methods: {
    startGeneration() {
      this._cancelSSE = streamKnowledgeGraphFromDocuments(
        this.spaceId,
        {
          document_ids: this.documentIds,
          user_preference: this.userPreference || undefined,
        },
        {
          onEvent: (eventType, data) => this.handleSSEEvent(eventType, data),
          onComplete: () => this.handleSSEComplete(),
          onConnectionError: (err) => this.handleSSEError(err),
        }
      )
    },

    handleSSEEvent(eventType, data) {
      switch (eventType) {
        case 'phase':
          if (data.phase === 'extraction') {
            this.currentPhaseIdx = 0
            this.totalChunks = data.total_chunks || 0
          } else if (data.phase === 'consolidation') {
            this.currentPhaseIdx = 1
          }
          break

        case 'progress':
          this.completed = data.completed || 0
          this.totalChunks = data.total || this.totalChunks
          break

        case 'kg_delta':
          this.streamText += data.content || ''
          this.$nextTick(() => {
            this.scrollTop = 99999
          })
          break

        case 'kg_node':
          this.$emit('kg-node', data)
          break

        case 'kg_edge':
          this.$emit('kg-edge', data)
          break

        case 'done':
          this.currentPhaseIdx = 2
          this.isDone = true
          this.nodeCount = data.node_count || 0
          this.edgeCount = data.edge_count || 0
          this.$emit('done', {
            nodeCount: this.nodeCount,
            edgeCount: this.edgeCount,
          })
          break

        case 'error':
          this.errorMsg = data.message || '生成失败'
          this.$emit('error', this.errorMsg)
          break
      }
    },

    handleSSEComplete() {
      if (!this.isDone && !this.errorMsg) {
        // SSE 连接关闭但未收到 done/error
        // 可能是网络中断
      }
    },

    handleSSEError(err) {
      if (!this.isDone) {
        this.errorMsg = '连接中断，请刷新重试'
        this.$emit('error', this.errorMsg)
      }
    },
  },
}
</script>

<style scoped>
.dkg-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(15, 15, 25, 0.6);
  border-left: 1px solid rgba(255, 255, 255, 0.08);
}

/* Phase Indicator */
.dkg-phases {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.dkg-phase {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.4;
  transition: opacity 0.3s ease;
}

.dkg-phase--active {
  opacity: 1;
}

.dkg-phase--done {
  opacity: 0.7;
}

.dkg-phase-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s ease;
}

.dkg-phase--active .dkg-phase-dot {
  background: rgba(0, 136, 255, 0.3);
  border-color: rgba(0, 136, 255, 0.6);
  box-shadow: 0 0 8px rgba(0, 136, 255, 0.3);
}

.dkg-phase--done .dkg-phase-dot {
  background: rgba(16, 185, 129, 0.3);
  border-color: rgba(16, 185, 129, 0.6);
}

.dkg-phase-num,
.dkg-phase-check {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.dkg-phase-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.dkg-phase--active .dkg-phase-label {
  color: #ffffff;
  font-weight: 500;
}

/* Content Area */
.dkg-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* Extraction Progress */
.dkg-extraction {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 0;
}

.dkg-progress-bar-wrap {
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.dkg-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0088FF, #8B5CF6);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.dkg-progress-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
}

/* Streaming Text */
.dkg-stream {
  padding: 8px 0;
}

.dkg-stream-block {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 16px;
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
}

.dkg-stream-text {
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
  word-break: break-word;
}

.dkg-cursor {
  color: #0088FF;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* Done */
.dkg-done {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 16px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 8px;
}

.dkg-done-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(16, 185, 129, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #10B981;
  font-size: 14px;
}

.dkg-done-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

/* Error */
.dkg-error {
  margin-top: 16px;
  padding: 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
}

.dkg-error-text {
  font-size: 14px;
  color: #EF4444;
}
</style>
