<template>
  <view class="artifact-renderer">
    <!-- Loading state -->
    <view v-if="isGenerating" class="artifact-loading">
      <view class="artifact-loading-spinner"></view>
      <text class="artifact-loading-text">正在生成交互演示...</text>
    </view>

    <!-- Error state -->
    <view v-else-if="errorMessage" class="artifact-error">
      <text class="artifact-error-text">{{ errorMessage }}</text>
    </view>

    <!-- Rendered artifact -->
    <template v-else-if="htmlContent">
      <view class="artifact-toolbar">
        <text class="artifact-title">{{ title || '交互演示' }}</text>
        <view class="artifact-toolbar-actions">
          <view class="artifact-btn" @click="toggleFullscreen">
            <text class="artifact-btn-text">{{ isFullscreen ? '退出全屏' : '全屏' }}</text>
          </view>
        </view>
      </view>
      <!-- #ifdef H5 -->
      <iframe
        ref="artifactFrame"
        class="artifact-iframe"
        :class="{ 'artifact-iframe-fullscreen': isFullscreen }"
        :srcdoc="sanitizedHtml"
        sandbox="allow-scripts"
        referrerpolicy="no-referrer"
        loading="lazy"
      ></iframe>
      <!-- #endif -->
    </template>

    <!-- Empty -->
    <view v-else class="artifact-empty">
      <text class="artifact-empty-text">暂无内容</text>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ArtifactRenderer',
  props: {
    html: {
      type: String,
      default: ''
    },
    title: {
      type: String,
      default: ''
    },
    metadata: {
      type: Object,
      default: () => null
    }
  },
  data() {
    return {
      isFullscreen: false
    }
  },
  computed: {
    isGenerating() {
      return this.metadata && this.metadata.generating === true
    },
    errorMessage() {
      return this.metadata?.error || ''
    },
    htmlContent() {
      return this.html || ''
    },
    sanitizedHtml() {
      const html = this.htmlContent
      if (!html) return ''
      // Reject content that doesn't look like a valid HTML document
      const stripped = html.trim().toLowerCase()
      if (!stripped.startsWith('<!doctype') && !stripped.startsWith('<html')) {
        return '<html><body style="background:#1a1a2e;color:#f87171;padding:20px;font-family:sans-serif"><p>无效的演示内容</p></body></html>'
      }
      return html
    }
  },
  methods: {
    toggleFullscreen() {
      this.isFullscreen = !this.isFullscreen
    }
  }
}
</script>

<style scoped>
.artifact-renderer {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 300px;
}

.artifact-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.artifact-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.artifact-toolbar-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.artifact-btn {
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: background 0.15s;
}
.artifact-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}

.artifact-btn-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.artifact-iframe {
  flex: 1;
  width: 100%;
  min-height: 400px;
  border: none;
  background: #1a1a2e;
  border-radius: 0 0 8px 8px;
}

.artifact-iframe-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  border-radius: 0;
  min-height: unset;
}

.artifact-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 16px;
}

.artifact-loading-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(138, 180, 248, 0.7);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.artifact-loading-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

.artifact-error {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.artifact-error-text {
  font-size: 13px;
  color: #f87171;
}

.artifact-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.artifact-empty-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.3);
}
</style>
