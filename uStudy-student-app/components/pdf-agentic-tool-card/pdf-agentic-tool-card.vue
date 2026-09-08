<template>
  <view class="pdf-tool-card" :class="[themeClass, statusClass]">
    <view
      class="pdf-tool-pill"
      :class="{ 'pdf-tool-pill-expandable': expandable }"
      @click="togglePreview"
    >
      <image class="pdf-tool-icon" :src="toolIcon" mode="aspectFit" />
      <text class="pdf-tool-label">{{ displayLabel }}</text>
      <view v-if="running" class="pdf-tool-spinner"></view>
      <image
        v-else-if="expandable"
        class="pdf-tool-chevron"
        :class="{ 'pdf-tool-chevron-up': expanded }"
        src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
        mode="aspectFit"
      />
      <image
        v-else-if="succeeded"
        class="pdf-tool-status-icon"
        src="/static/icons/lucide/circle-check.svg"
        mode="aspectFit"
      />
      <image
        v-else
        class="pdf-tool-status-icon pdf-tool-status-failed"
        src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
        mode="aspectFit"
      />
    </view>

    <view v-if="expanded && expandable" class="pdf-preview-panel">
      <view class="pdf-preview-heading">
        <text class="pdf-preview-title">{{ previewTitle }}</text>
        <text class="pdf-preview-range">{{ previewRangeLabel }}</text>
      </view>

      <view v-if="previewLoading" class="pdf-preview-state">
        <view class="pdf-preview-spinner"></view>
        <text class="pdf-preview-state-text">正在加载 AI 查看过的页面…</text>
      </view>

      <view v-else-if="previewError" class="pdf-preview-state pdf-preview-error">
        <text class="pdf-preview-state-text">{{ previewError }}</text>
        <text class="pdf-preview-retry" @click.stop="retryPreview">重试</text>
      </view>

      <scroll-view v-else-if="previewPages.length" class="pdf-preview-list" scroll-y>
        <view
          v-for="(page, index) in previewPages"
          :key="`${page.physical_page_start}-${page.physical_page_end}`"
          class="pdf-preview-item"
        >
          <image
            class="pdf-preview-image"
            :src="page.image_data_url"
            mode="widthFix"
            @click.stop="previewImage(index)"
          />
          <text class="pdf-preview-page-label">{{ pageLabel(page) }}</text>
        </view>
      </scroll-view>

      <view v-else class="pdf-preview-state">
        <text class="pdf-preview-state-text">暂无可用页面图片</text>
      </view>

      <text v-if="previewMissingRanges.length" class="pdf-preview-missing">
        部分页面暂不可用：{{ previewMissingRanges.join('、') }}
      </text>
    </view>
  </view>
</template>

<script>
import { getPdfPagePreviews } from '@/api/space'
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

const TOOL_LABELS = {
  search_keywords: { running: '正在检索文档关键词…', done: '已检索文档关键词', failed: '文档关键词检索失败' },
  search_regex: { running: '正在进行文档正则检索…', done: '已完成文档正则检索', failed: '文档正则检索失败' },
  list_documents: { running: '正在读取资料列表…', done: '已读取资料列表', failed: '资料列表读取失败' },
  read_document: { running: '正在阅读课程资料…', done: '已阅读课程资料', failed: '课程资料读取失败' },
  get_document_outline: { running: '正在读取 PDF 目录…', done: '已读取 PDF 目录', failed: 'PDF 目录读取失败' },
  view_document_pages: { running: '正在查看 PDF 页面…', done: '已查看 PDF 页面', failed: 'PDF 页面查看失败' },
  view_document_page: { running: '正在查看 PDF 页面…', done: '已查看 PDF 页面', failed: 'PDF 页面查看失败' }
}

const PREVIEW_TOOL_NAMES = new Set(['view_document_pages', 'view_document_page'])

export default {
  name: 'PdfAgenticToolCard',
  props: {
    toolCall: { type: Object, required: true },
    spaceId: { type: [String, Number], default: null },
    themeMode: { type: String, default: '' }
  },
  data() {
    return {
      expanded: false,
      previewLoading: false,
      previewError: '',
      previewPages: [],
      loadedPreviewTitle: '',
      previewMissingRanges: [],
      previewRequestKey: '',
      localThemeMode: 'dark',
      previewLoadVersion: 0
    }
  },
  computed: {
    running() {
      return this.toolCall.status !== 'done' && this.toolCall.status !== 'failed'
    },
    succeeded() {
      return !this.running && this.toolCall.success !== false && this.toolCall.status !== 'failed'
    },
    statusClass() {
      return this.running ? 'pdf-tool-running' : this.succeeded ? 'pdf-tool-succeeded' : 'pdf-tool-failed'
    },
    labels() {
      return TOOL_LABELS[this.toolCall.tool] || {
        running: '正在读取课程资料…',
        done: '已读取课程资料',
        failed: '课程资料读取失败'
      }
    },
    displayLabel() {
      if (this.running) return this.labels.running
      return this.succeeded ? this.labels.done : this.labels.failed
    },
    previewTool() {
      return PREVIEW_TOOL_NAMES.has(this.toolCall.tool)
    },
    resultData() {
      const value = this.toolCall.result
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
    },
    argumentData() {
      const value = this.toolCall.arguments || this.toolCall.params
      if (value && typeof value === 'object' && !Array.isArray(value)) return value
      if (typeof value === 'string') {
        try {
          const parsed = JSON.parse(value)
          return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
        } catch (_) {}
      }
      return {}
    },
    previewRanges() {
      const ranges = []
      const assets = Array.isArray(this.resultData.assets) ? this.resultData.assets : []
      assets.forEach(asset => {
        const start = Number(asset && asset.physical_page_start)
        const rawEnd = asset && asset.physical_page_end !== undefined
          ? asset.physical_page_end
          : asset && asset.physical_page_start
        const end = Number(rawEnd)
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return
        if (!ranges.some(range => range.start === start && range.end === end)) {
          ranges.push({ start, end })
        }
      })

      if (!ranges.length && this.toolCall.tool === 'view_document_page') {
        const page = Number(this.resultData.page_number || this.argumentData.page_number)
        if (Number.isInteger(page) && page > 0) ranges.push({ start: page, end: page })
      }
      return ranges.slice(0, 4)
    },
    previewPageQuery() {
      return this.previewRanges
        .map(range => range.start === range.end ? String(range.start) : `${range.start}-${range.end}`)
        .join(',')
    },
    previewDocumentId() {
      return this.resultData.document_id || this.argumentData.document_id || ''
    },
    previewRangeLabel() {
      return this.previewRanges
        .map(range => range.start === range.end ? `第 ${range.start} 页` : `第 ${range.start}-${range.end} 页`)
        .join('、')
    },
    previewTitle() {
      return this.loadedPreviewTitle || this.resultData.title || 'PDF 页面预览'
    },
    previewKey() {
      return [
        this.toolCall.id || this.toolCall.tool || '',
        this.toolCall.status || '',
        this.previewDocumentId,
        this.previewPageQuery,
        this.resultData.generation || ''
      ].join('|')
    },
    expandable() {
      return this.previewTool && !this.running && this.succeeded && Boolean(this.previewPageQuery)
    },
    resolvedThemeMode() {
      return normalizeThemeMode(this.themeMode || this.localThemeMode)
    },
    themeClass() {
      return `pdf-tool-theme-${this.resolvedThemeMode}`
    },
    toolIcon() {
      if (this.previewTool) return '/static/icons/phosphor-icons/SVGs/regular/eye.svg'
      if (this.toolCall.tool === 'list_documents') return '/static/icons/phosphor-icons/SVGs/regular/books.svg'
      if (this.toolCall.tool === 'read_document') return '/static/icons/phosphor-icons/SVGs/regular/file-text.svg'
      if (this.toolCall.tool === 'get_document_outline') return '/static/icons/phosphor-icons/SVGs/regular/file-pdf.svg'
      return '/static/icons/phosphor-icons/SVGs/regular/file-magnifying-glass.svg'
    }
  },
  watch: {
    previewKey() {
      this.previewLoadVersion += 1
      this.expanded = false
      this.previewLoading = false
      this.previewError = ''
      this.previewPages = []
      this.loadedPreviewTitle = ''
      this.previewMissingRanges = []
      this.previewRequestKey = ''
    },
    themeMode() {
      this.refreshThemeMode()
    }
  },
  created() {
    this.refreshThemeMode()
  },
  beforeDestroy() {
    this.previewLoadVersion += 1
  },
  methods: {
    refreshThemeMode() {
      this.localThemeMode = getStoredThemeMode('dark')
    },
    pageLabel(page) {
      const start = page && page.physical_page_start
      const end = page && page.physical_page_end
      return start === end ? `第 ${start} 页` : `第 ${start}-${end} 页`
    },
    async togglePreview() {
      if (!this.expandable) return
      this.expanded = !this.expanded
      if (this.expanded) await this.loadPreviews()
    },
    async loadPreviews(force = false) {
      const requestKey = `${this.spaceId || ''}|${this.previewDocumentId}|${this.previewPageQuery}`
      if (!this.spaceId || !this.previewDocumentId || !this.previewPageQuery) {
        this.previewError = '缺少页面预览所需的文档信息'
        return
      }
      if (!force && this.previewRequestKey === requestKey && (this.previewPages.length || this.previewError)) return

      const loadVersion = ++this.previewLoadVersion
      this.previewRequestKey = requestKey
      this.previewLoading = true
      this.previewError = ''
      try {
        const data = await getPdfPagePreviews(this.spaceId, this.previewDocumentId, this.previewPageQuery)
        if (loadVersion !== this.previewLoadVersion) return
        this.loadedPreviewTitle = (data && data.title) || this.resultData.title || 'PDF 页面预览'
        this.previewPages = data && Array.isArray(data.pages) ? data.pages : []
        this.previewMissingRanges = data && Array.isArray(data.missing_ranges) ? data.missing_ranges : []
      } catch (error) {
        if (loadVersion !== this.previewLoadVersion) return
        this.previewError = (error && error.message) || 'PDF 页面图片加载失败'
      } finally {
        if (loadVersion === this.previewLoadVersion) this.previewLoading = false
      }
    },
    retryPreview() {
      this.loadPreviews(true)
    },
    previewImage(index) {
      const urls = this.previewPages.map(page => page.image_data_url).filter(Boolean)
      if (!urls.length) return
      uni.previewImage({ current: urls[index] || urls[0], urls })
    }
  }
}
</script>

<style scoped>
.pdf-tool-card {
  width: 100%;
}

.pdf-tool-pill {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 16rpx 24rpx;
  box-sizing: border-box;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.04);
  gap: 16rpx;
}

.pdf-tool-pill-expandable:active {
  background: rgba(255, 255, 255, 0.09);
}

.pdf-tool-icon,
.pdf-tool-status-icon,
.pdf-tool-chevron {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
}

.pdf-tool-icon,
.pdf-tool-chevron {
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.pdf-tool-label {
  flex: 1;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.7);
  font-size: 26rpx;
  font-weight: 500;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-tool-spinner,
.pdf-preview-spinner {
  width: 24rpx;
  height: 24rpx;
  box-sizing: border-box;
  border: 3rpx solid rgba(126, 168, 255, 0.25);
  border-top-color: #8fb3ff;
  border-radius: 50%;
  animation: pdf-tool-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.pdf-tool-chevron {
  transition: transform 0.2s ease;
}

.pdf-tool-chevron-up {
  transform: rotate(180deg);
}

.pdf-tool-status-icon {
  width: 28rpx;
  height: 28rpx;
  filter: invert(48%) sepia(30%) saturate(900%) hue-rotate(100deg) brightness(85%) contrast(90%);
}

.pdf-tool-status-failed {
  filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
}

.pdf-tool-running .pdf-tool-pill {
  border-color: rgba(126, 168, 255, 0.2);
  background: rgba(126, 168, 255, 0.055);
}

.pdf-tool-succeeded .pdf-tool-pill {
  border-color: rgba(110, 194, 145, 0.16);
}

.pdf-tool-failed .pdf-tool-pill {
  border-color: rgba(239, 68, 68, 0.2);
}

.pdf-preview-panel {
  margin: 10rpx 0 0 38rpx;
  padding: 18rpx;
  border-left: 2rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 0 18rpx 18rpx 0;
  background: rgba(0, 0, 0, 0.12);
  animation: pdf-panel-in 0.18s ease-out;
}

.pdf-preview-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 14rpx;
}

.pdf-preview-title {
  min-width: 0;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.72);
  font-size: 22rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-preview-range {
  color: rgba(255, 255, 255, 0.38);
  font-size: 19rpx;
  flex-shrink: 0;
}

.pdf-preview-list {
  max-height: 720rpx;
}

.pdf-preview-item {
  padding-bottom: 16rpx;
}

.pdf-preview-item + .pdf-preview-item {
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.07);
}

.pdf-preview-image {
  display: block;
  width: 100%;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.06);
}

.pdf-preview-page-label {
  display: block;
  margin-top: 8rpx;
  color: rgba(255, 255, 255, 0.42);
  font-size: 19rpx;
  text-align: center;
}

.pdf-preview-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 112rpx;
  gap: 12rpx;
}

.pdf-preview-state-text {
  color: rgba(255, 255, 255, 0.46);
  font-size: 21rpx;
}

.pdf-preview-error .pdf-preview-state-text {
  color: rgba(255, 158, 158, 0.82);
}

.pdf-preview-retry {
  color: #9dbbff;
  font-size: 21rpx;
}

.pdf-preview-missing {
  display: block;
  margin-top: 10rpx;
  color: rgba(255, 196, 128, 0.76);
  font-size: 19rpx;
  line-height: 1.45;
}

.pdf-tool-theme-light .pdf-tool-pill {
  border-color: rgba(15, 23, 42, 0.09);
  background: rgba(15, 23, 42, 0.045);
}

.pdf-tool-theme-light .pdf-tool-pill-expandable:active {
  background: rgba(15, 23, 42, 0.085);
}

.pdf-tool-theme-light .pdf-tool-icon,
.pdf-tool-theme-light .pdf-tool-chevron {
  filter: brightness(0) saturate(100%) invert(34%) sepia(61%) saturate(1869%) hue-rotate(211deg) brightness(96%) contrast(91%);
}

.pdf-tool-theme-light .pdf-tool-label,
.pdf-tool-theme-light .pdf-preview-title {
  color: rgba(15, 23, 42, 0.72);
}

.pdf-tool-theme-light .pdf-preview-range,
.pdf-tool-theme-light .pdf-preview-page-label,
.pdf-tool-theme-light .pdf-preview-state-text {
  color: rgba(15, 23, 42, 0.46);
}

.pdf-tool-theme-light .pdf-preview-panel {
  border-left-color: rgba(15, 23, 42, 0.1);
  background: rgba(15, 23, 42, 0.035);
}

.pdf-tool-theme-light .pdf-preview-image {
  border-color: rgba(15, 23, 42, 0.1);
  background: rgba(15, 23, 42, 0.04);
}

.pdf-tool-theme-light .pdf-tool-status-icon {
  filter: brightness(0) saturate(100%) invert(37%) sepia(26%) saturate(1030%) hue-rotate(105deg) brightness(92%) contrast(88%);
}

.pdf-tool-theme-light .pdf-tool-status-failed {
  filter: brightness(0) saturate(100%) invert(39%) sepia(31%) saturate(2143%) hue-rotate(329deg) brightness(96%) contrast(86%);
}

@keyframes pdf-tool-spin {
  to { transform: rotate(360deg); }
}

@keyframes pdf-panel-in {
  from { opacity: 0; transform: translateY(-6rpx); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
