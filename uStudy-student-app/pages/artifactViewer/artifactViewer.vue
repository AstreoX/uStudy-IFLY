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

export default {
  data() {
    return {
      spaceId: '',
      noteId: '',
      title: '',
      htmlContent: '',
      fileUrl: '',
      loading: true,
      loadError: null
    }
  },

  onLoad(options) {
    this.spaceId = options.spaceId || ''
    this.noteId = options.noteId || ''
    this.loadNote()
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

    async loadNote() {
      if (!this.spaceId || !this.noteId) {
        this.loading = false
        this.loadError = '参数缺失'
        return
      }

      try {
        this.loading = true
        this.loadError = null
        const detail = await getNoteDetail(this.spaceId, this.noteId)
        this.title = detail.title || '交互演示'
        const content = detail.content || ''

        if (!content.trim()) {
          this.loadError = '演示内容为空'
          return
        }

        // #ifdef H5
        this.htmlContent = content
        // #endif

        // #ifdef APP-PLUS
        this.writeAndLoadHtml(content)
        // #endif
      } catch (error) {
        this.loadError = error.message || '加载失败'
      } finally {
        this.loading = false
      }
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
