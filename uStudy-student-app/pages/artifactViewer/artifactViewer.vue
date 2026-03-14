<template>
  <view class="artifact-viewer-page">
    <!-- Navigation Bar (H5 only; APP-PLUS web-view takes full screen) -->
    <!-- #ifndef APP-PLUS -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <image class="nav-icon" src="/static/icons/phosphor-icons/SVGs/regular/caret-left.svg" mode="aspectFit"></image>
      </view>
      <text class="nav-title">{{ title || '交互演示' }}</text>
      <view class="nav-right-placeholder"></view>
    </view>
    <!-- #endif -->

    <!-- Loading -->
    <view v-if="loading" class="loading-container">
      <text class="loading-text">正在加载演示内容...</text>
    </view>

    <!-- Generating -->
    <view v-else-if="isGenerating && !htmlContent && !loadError" class="loading-container">
      <text class="loading-text">{{ generatingText }}</text>
    </view>

    <!-- Error -->
    <view v-else-if="loadError" class="error-container">
      <image class="error-icon" src="/static/icons/phosphor-icons/SVGs/regular/warning-circle.svg" mode="aspectFit"></image>
      <text class="error-text">{{ loadError }}</text>
      <view class="retry-btn" @click="loadNote">
        <text class="retry-btn-text">重试</text>
      </view>
    </view>

    <!-- H5: iframe rendering -->
    <!-- #ifdef H5 -->
    <view v-if="!loading && !loadError && htmlContent" class="iframe-wrapper">
      <iframe
        class="artifact-iframe"
        :srcdoc="htmlContent"
        sandbox="allow-scripts"
        frameborder="0"
      ></iframe>
    </view>
    <!-- #endif -->

    <!-- APP-PLUS: web-view rendering -->
    <!-- #ifdef APP-PLUS -->
    <web-view
      v-if="!loading && !loadError && fileUrl"
      :src="fileUrl"
      class="artifact-webview"
    ></web-view>
    <!-- #endif -->
  </view>
</template>

<script>
import { getNoteDetail } from '@/api/note'
import { connectNotificationStream } from '@/api/notification'

export default {
  data() {
    return {
      spaceId: '',
      noteId: '',
      title: '',
      htmlContent: '',
      streamContent: '',
      streamCharsTotal: 0,
      fileUrl: '',
      loading: true,
      loadError: null,
      isGenerating: false,
      notificationAbort: null,
      notePollTimer: null
    }
  },

  computed: {
    generatingText() {
      if (this.streamCharsTotal > 0) {
        return `正在接收交互式笔记代码… 已接收 ${this.formatBytes(this.streamCharsTotal)}`
      }
      return '正在接收交互式笔记代码…'
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.noteId = options.noteId || ''
    this.setupNotificationStream()
    this.loadNote()
  },

  onUnload() {
    this.cleanupStreamingResources()
  },

  methods: {
    goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack({ delta: 1 })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    async loadNote({ silent = false } = {}) {
      if (!this.spaceId || !this.noteId) {
        this.loading = false
        this.loadError = '参数缺失'
        return
      }

      try {
        if (!silent) {
          this.loading = true
        }
        this.loadError = null
        const detail = await getNoteDetail(this.spaceId, this.noteId)
        this.title = detail.title || '交互演示'
        const metadata = detail.metadata_ || {}
        this.isGenerating = !!metadata.generating
        const content = detail.content || ''

        if (content.trim()) {
          this.isGenerating = false
          this.streamContent = content
          this.streamCharsTotal = Math.max(this.streamCharsTotal, content.length)
          this.stopNotePolling()

          // #ifdef H5
          this.htmlContent = content
          // #endif

          // #ifdef APP-PLUS
          this.writeAndLoadHtml(content)
          // #endif
          return
        }

        if (this.isGenerating) {
          this.scheduleNotePolling()
          return
        }

        if (!content.trim()) {
          this.loadError = '演示内容为空'
          return
        }
      } catch (error) {
        if (silent && this.isGenerating) {
          console.warn('[ArtifactViewer] silent refresh failed:', error)
          this.scheduleNotePolling()
          return
        }
        this.loadError = error.message || '加载失败'
      } finally {
        if (!silent) {
          this.loading = false
        }
      }
    },

    setupNotificationStream() {
      if (this.notificationAbort) return
      this.notificationAbort = connectNotificationStream({
        onArtifactStream: (data) => {
          this.onArtifactStream(data)
        },
        onArtifactReady: (data) => {
          this.onArtifactReady(data)
        }
      })
    },

    onArtifactStream(data) {
      if (!this.isMatchingArtifactEvent(data)) return

      this.loading = false
      this.loadError = null
      this.isGenerating = true
      if (data.title) {
        this.title = data.title
      }

      const delta = data.delta || ''
      if (!delta) return

      this.streamContent += delta
      this.streamCharsTotal = Math.max(
        Number(data.chars_total) || 0,
        this.streamContent.length
      )

      const renderable = this.extractRenderableHtml(this.streamContent)
      if (renderable) {
        this.htmlContent = renderable
      }

      this.scheduleNotePolling()
    },

    async onArtifactReady(data) {
      if (!this.isMatchingArtifactEvent(data)) return

      if (data.status === 'failed') {
        this.isGenerating = false
        this.stopNotePolling()
        this.loading = false
        this.loadError = data.error_message || '交互演示生成失败'
        return
      }

      await this.loadNote({ silent: !!this.htmlContent })
    },

    isMatchingArtifactEvent(data) {
      return (
        data &&
        String(data.space_id) === String(this.spaceId) &&
        String(data.note_id) === String(this.noteId)
      )
    },

    scheduleNotePolling() {
      if (this.notePollTimer) return
      this.notePollTimer = setTimeout(async () => {
        this.notePollTimer = null
        if (!this.isGenerating) return
        await this.loadNote({ silent: true })
      }, 2000)
    },

    stopNotePolling() {
      if (this.notePollTimer) {
        clearTimeout(this.notePollTimer)
        this.notePollTimer = null
      }
    },

    cleanupStreamingResources() {
      this.stopNotePolling()
      if (this.notificationAbort) {
        this.notificationAbort()
        this.notificationAbort = null
      }
    },

    extractRenderableHtml(content) {
      if (!content) return ''
      let normalized = String(content).trim()
      normalized = normalized.replace(/^```html?\s*/i, '')
      normalized = normalized.replace(/```$/i, '').trim()

      const doctypeIndex = normalized.search(/<!doctype/i)
      const htmlIndex = normalized.search(/<html/i)
      const startIndex = doctypeIndex >= 0
        ? doctypeIndex
        : htmlIndex >= 0
          ? htmlIndex
          : -1

      if (startIndex < 0) return ''
      return normalized.slice(startIndex)
    },

    formatBytes(bytes) {
      const value = Number(bytes) || 0
      if (value < 1024) return `${value} B`
      if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
      return `${(value / (1024 * 1024)).toFixed(1)} MB`
    },

    // APP-PLUS: write HTML to temp file, load via web-view
    writeAndLoadHtml(html) {
      // #ifdef APP-PLUS
      const fileName = `artifact_${this.noteId}_${Date.now()}.html`
      const dirPath = '_doc/artifacts'

      plus.io.resolveLocalFileSystemURL(dirPath, () => {
        this.writeHtmlFile(dirPath, fileName, html)
      }, () => {
        // Directory doesn't exist, create it
        plus.io.resolveLocalFileSystemURL('_doc/', (entry) => {
          entry.getDirectory('artifacts', { create: true }, () => {
            this.writeHtmlFile(dirPath, fileName, html)
          }, (err) => {
            this.loadError = '无法创建临时目录'
            console.error('[ArtifactViewer] mkdir error:', err)
          })
        })
      })
      // #endif
    },

    writeHtmlFile(dirPath, fileName, html) {
      // #ifdef APP-PLUS
      plus.io.resolveLocalFileSystemURL(dirPath, (dirEntry) => {
        dirEntry.getFile(fileName, { create: true }, (fileEntry) => {
          fileEntry.createWriter((writer) => {
            writer.onwrite = () => {
              this.fileUrl = fileEntry.toLocalURL()
            }
            writer.onerror = (err) => {
              this.loadError = '写入临时文件失败'
              console.error('[ArtifactViewer] write error:', err)
            }
            writer.write(html)
          })
        }, (err) => {
          this.loadError = '创建临时文件失败'
          console.error('[ArtifactViewer] getFile error:', err)
        })
      })
      // #endif
    }
  }
}
</script>

<style>
.artifact-viewer-page {
  width: 100%;
  min-height: 100vh;
  background-color: #0A0A0A;
  display: flex;
  flex-direction: column;
}

/* Navigation Bar */
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-top: calc(100vh * 1.5 / 26);
  padding-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: calc(100vw / 24);
  padding-right: calc(100vw / 24);
  background: rgba(10, 10, 10, 0.85);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  backdrop-filter: blur(24px) saturate(150%);
}

.nav-left {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.06);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.nav-right-placeholder {
  width: 72rpx;
  height: 72rpx;
}

.nav-icon {
  width: 48rpx;
  height: 48rpx;
  filter: brightness(0) invert(1);
}

.nav-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #ffffff;
  flex: 1;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Loading & Error States */
.loading-container,
.error-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: calc(100vh * 1.5 / 26 + 200rpx);
}

.loading-text {
  font-size: 30rpx;
  color: rgba(255, 255, 255, 0.6);
}

.error-icon {
  width: 100rpx;
  height: 100rpx;
  filter: brightness(0) saturate(100%) invert(44%) sepia(78%) saturate(2349%) hue-rotate(337deg) brightness(97%) contrast(93%);
  margin-bottom: 24rpx;
}

.error-text {
  font-size: 28rpx;
  color: rgba(239, 68, 68, 0.9);
  margin-bottom: 32rpx;
  text-align: center;
  max-width: 500rpx;
}

.retry-btn {
  padding: 20rpx 48rpx;
  background: rgba(0, 136, 255, 0.15);
  border: 1rpx solid rgba(0, 136, 255, 0.4);
  border-radius: 40rpx;
}

.retry-btn:active {
  background: rgba(0, 136, 255, 0.25);
}

.retry-btn-text {
  font-size: 28rpx;
  color: #0088FF;
}

/* H5 iframe wrapper */
.iframe-wrapper {
  position: fixed;
  top: calc(100vh * 1.5 / 26 + 72rpx);
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
}

.artifact-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #ffffff;
}

/* APP-PLUS web-view gets full screen by default, nav-bar overlays it */
</style>
