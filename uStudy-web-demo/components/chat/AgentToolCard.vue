<template>
  <view class="tool-wrap" :class="[statusClass, { compact }]">
    <view class="tool-pill" :class="{ 'tool-pill-expandable': expandable }" @tap="toggle">
      <view class="tool-icon" v-html="iconSvg"></view>
      <view class="tool-copy">
        <text class="tool-name">{{ displayLabel }}</text>
        <text v-if="detail" class="tool-detail">{{ detail }}</text>
      </view>
      <view v-if="running" class="tool-spinner"></view>
      <text v-else-if="expandable" class="tool-chevron" :class="{ expanded }">⌄</text>
      <svg v-else-if="succeeded" viewBox="0 0 256 256" class="tool-status success">
        <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="18"/>
      </svg>
      <svg v-else viewBox="0 0 256 256" class="tool-status failed">
        <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="18"/>
        <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="18"/>
      </svg>
    </view>
    <view v-if="expanded && expandable" class="tool-panel">
      <template v-if="previewTool">
        <view class="preview-heading">
          <text class="preview-title">{{ previewTitle || resultData.title || 'PDF 页面预览' }}</text>
          <text class="preview-range">{{ previewRangeLabel }}</text>
        </view>
        <view v-if="previewLoading" class="preview-state">正在加载页面缩略图…</view>
        <view v-else-if="previewError" class="preview-state preview-error">
          <text>{{ previewError }}</text>
          <text class="preview-retry" @tap.stop="retryPreview">重试</text>
        </view>
        <scroll-view v-else-if="previewPages.length" scroll-y class="preview-list">
          <view v-for="page in previewPages" :key="`${page.physical_page_start}-${page.physical_page_end}`" class="preview-item">
            <image class="preview-image" :src="page.image_data_url" mode="widthFix" />
            <text class="preview-page-label">{{ pageLabel(page) }}</text>
          </view>
        </scroll-view>
        <view v-else class="preview-state">暂无可用页面缩略图</view>
        <text v-if="previewMissingRanges.length" class="preview-missing">
          部分页面暂不可用：{{ previewMissingRanges.join('、') }}
        </text>
      </template>
      <template v-else>
        <view v-if="argumentText" class="tool-section">
          <text class="section-label">参数</text>
          <text class="section-value">{{ argumentText }}</text>
        </view>
        <view v-if="resultText" class="tool-section">
          <text class="section-label">{{ succeeded ? '结果' : '错误' }}</text>
          <text class="section-value" :class="{ error: !succeeded }">{{ resultText }}</text>
        </view>
      </template>
    </view>
  </view>
</template>

<script>
import { getPdfPagePreviews } from '@/api/space'

const TOOL_LABELS = {
  get_course_graph_overview: ['读取课程知识图谱', '已读取课程知识图谱', '课程知识图谱读取失败'],
  list_documents: ['读取课程资料列表', '已读取课程资料列表', '课程资料列表读取失败'],
  search_keywords: ['检索课程资料', '已检索课程资料', '课程资料检索失败'],
  read_document: ['阅读课程资料', '已阅读课程资料', '课程资料读取失败'],
  view_document_page: ['查看资料页面', '已查看资料页面', '资料页面读取失败'],
  get_class_knowledge_summary: ['分析班级学情', '已分析班级学情', '班级学情分析失败'],
  generate_image: ['生成课件配图', '已生成课件配图', '课件配图生成失败'],
  publish_presentation_to_space: ['准备发布课件', '课件已发布', '课件发布失败'],
  get_tool_details: ['读取课件工具说明', '已读取课件工具说明', '课件工具说明读取失败'],
  read_skill_resource: ['读取课件技能资料', '已读取课件技能资料', '课件技能资料读取失败'],
  load_workspace_dependencies: ['准备课件运行环境', '已准备课件运行环境', '课件运行环境准备失败'],
  read_file: ['读取课件工作文件', '已读取课件工作文件', '课件工作文件读取失败'],
  write_file: ['编写课件构建脚本', '已编写课件构建脚本', '课件构建脚本编写失败'],
  apply_patch: ['修改课件构建脚本', '已修改课件构建脚本', '课件构建脚本修改失败'],
  view_image: ['检查课件页面', '已检查课件页面', '课件页面检查失败'],
  execute_command: ['执行课件构建命令', '已执行课件构建命令', '课件构建命令失败'],
  run_command: ['执行课件构建命令', '已执行课件构建命令', '课件构建命令失败'],
  shell: ['执行课件构建命令', '已执行课件构建命令', '课件构建命令失败']
}

const COMPACT_TOOL_LABELS = {
  search_keywords: ['正在检索关键词', '已检索关键词', '关键词检索失败'],
  search_regex: ['正在进行正则检索', '已完成正则检索', '正则检索失败'],
  list_documents: ['正在读取资料列表', '已读取资料列表', '资料列表读取失败'],
  read_document: ['正在读取资料', '已读取资料', '资料读取失败'],
  get_document_outline: ['正在读取文档目录', '已读取文档目录', '文档目录读取失败'],
  view_document_pages: ['正在查看资料页面', '已查看资料页面', '资料页面查看失败'],
  view_document_page: ['正在查看资料页面', '已查看资料页面', '资料页面查看失败'],
  get_context_memories: ['正在召回相关记忆', '已召回相关记忆', '召回相关记忆失败'],
  get_context_documents: ['正在检索相关资料', '已检索相关资料', '资料检索失败'],
  get_previous_context: ['正在召回临时记忆', '已召回临时记忆', '召回临时记忆失败']
}

const COMPACT_TOOL_NAMES = new Set(Object.keys(COMPACT_TOOL_LABELS))
const PDF_PREVIEW_TOOL_NAMES = new Set(['view_document_pages', 'view_document_page'])

function redact(value, depth = 0) {
  if (depth > 4) return '…'
  if (value === null || value === undefined) return value
  if (typeof value === 'string') {
    if (/^data:[^;]+;base64,/i.test(value) || value.length > 3000) return `[已省略 ${value.length} 字符]`
    return value
  }
  if (Array.isArray(value)) return value.slice(0, 12).map(item => redact(item, depth + 1))
  if (typeof value === 'object') {
    const next = {}
    Object.keys(value).slice(0, 24).forEach(key => {
      if (/(token|secret|authorization|api[_-]?key)/i.test(key)) next[key] = '[已隐藏]'
      else next[key] = redact(value[key], depth + 1)
    })
    return next
  }
  return value
}

function format(value) {
  if (value === undefined || value === null || value === '') return ''
  if (typeof value === 'string') return value.slice(0, 1800)
  try { return JSON.stringify(redact(value), null, 2).slice(0, 1800) } catch (_) { return String(value).slice(0, 1800) }
}

export default {
  name: 'AgentToolCard',
  props: {
    toolCall: { type: Object, required: true },
    spaceId: { type: [String, Number], default: null }
  },
  data() {
    return {
      expanded: false,
      previewLoading: false,
      previewError: '',
      previewPages: [],
      previewTitle: '',
      previewMissingRanges: [],
      previewRequestKey: ''
    }
  },
  computed: {
    running() { return this.toolCall.status !== 'done' && this.toolCall.status !== 'failed' },
    succeeded() { return !this.running && this.toolCall.success !== false && this.toolCall.status !== 'failed' },
    statusClass() { return this.running ? 'running' : this.succeeded ? 'succeeded' : 'failed' },
    compact() { return COMPACT_TOOL_NAMES.has(this.toolCall.tool) },
    previewTool() { return PDF_PREVIEW_TOOL_NAMES.has(this.toolCall.tool) },
    compactLabels() { return COMPACT_TOOL_LABELS[this.toolCall.tool] || this.labels },
    labels() { return TOOL_LABELS[this.toolCall.tool] || [`正在调用 ${this.toolCall.tool || '工具'}`, `已完成 ${this.toolCall.tool || '工具'}`, `${this.toolCall.tool || '工具'}调用失败`] },
    displayLabel() {
      if (this.toolCall.tool === 'publish_presentation_to_space' && this.toolCall.result?.requires_confirmation) {
        return '等待教师确认发布'
      }
      if (this.compact) return this.running ? this.compactLabels[0] : this.succeeded ? this.compactLabels[1] : this.compactLabels[2]
      return this.toolCall.label || this.toolCall.display_name || (this.running ? this.labels[0] : this.succeeded ? this.labels[1] : this.labels[2])
    },
    detail() { return this.compact ? '' : String(this.toolCall.detail || this.toolCall.message || '').slice(0, 120) },
    argumentText() { return format(this.toolCall.arguments || this.toolCall.params) },
    resultText() { return format(this.toolCall.result || this.toolCall.error) },
    resultData() {
      const result = this.toolCall.result
      return result && typeof result === 'object' && !Array.isArray(result) ? result : {}
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
        const start = Number(asset?.physical_page_start)
        const end = Number(asset?.physical_page_end ?? asset?.physical_page_start)
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return
        if (!ranges.some(range => range.start === start && range.end === end)) ranges.push({ start, end })
      })
      if (!ranges.length && this.toolCall.tool === 'view_document_page') {
        const page = Number(this.resultData.page_number || this.argumentData.page_number)
        if (Number.isInteger(page) && page > 0) ranges.push({ start: page, end: page })
      }
      return ranges.slice(0, 4)
    },
    previewPageQuery() {
      return this.previewRanges.map(range => range.start === range.end ? String(range.start) : `${range.start}-${range.end}`).join(',')
    },
    previewDocumentId() {
      return this.resultData.document_id || this.argumentData.document_id || ''
    },
    previewRangeLabel() {
      return this.previewRanges.map(range => range.start === range.end ? `第 ${range.start} 页` : `第 ${range.start}-${range.end} 页`).join('、')
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
      if (this.previewTool) return !this.running && this.succeeded && Boolean(this.previewPageQuery)
      return !this.compact && Boolean(this.argumentText || this.resultText)
    },
    iconSvg() {
      if (/image/i.test(this.toolCall.tool || '')) return '<svg viewBox="0 0 256 256"><rect x="40" y="40" width="176" height="176" rx="12" fill="none" stroke="currentColor" stroke-width="16"/><circle cx="96" cy="92" r="16" fill="none" stroke="currentColor" stroke-width="16"/><path d="m48 184 56-56 32 32 32-40 40 48" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      if (/graph|document|keyword|knowledge/i.test(this.toolCall.tool || '')) return '<svg viewBox="0 0 256 256"><circle cx="72" cy="128" r="24" fill="none" stroke="currentColor" stroke-width="16"/><circle cx="184" cy="72" r="24" fill="none" stroke="currentColor" stroke-width="16"/><circle cx="184" cy="184" r="24" fill="none" stroke="currentColor" stroke-width="16"/><path d="m94 117 68-34M94 139l68 34" fill="none" stroke="currentColor" stroke-width="16"/></svg>'
      return '<svg viewBox="0 0 256 256"><path d="M80 40h96l40 40v136H40V40h40Z" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/><path d="M96 112h64M96 152h64" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/></svg>'
    }
  },
  watch: {
    previewKey() {
      this.expanded = false
      this.previewLoading = false
      this.previewError = ''
      this.previewPages = []
      this.previewTitle = ''
      this.previewMissingRanges = []
      this.previewRequestKey = ''
    }
  },
  methods: {
    pageLabel(page) {
      const start = page?.physical_page_start
      const end = page?.physical_page_end
      return start === end ? `第 ${start} 页` : `第 ${start}-${end} 页`
    },
    async toggle() {
      if (!this.expandable) return
      this.expanded = !this.expanded
      if (this.expanded && this.previewTool) await this.loadPreviews()
    },
    async loadPreviews(force = false) {
      const requestKey = `${this.spaceId || ''}|${this.previewDocumentId}|${this.previewPageQuery}`
      if (!this.spaceId || !this.previewDocumentId || !this.previewPageQuery) {
        this.previewError = '缺少页面预览所需的文档信息'
        return
      }
      if (!force && this.previewRequestKey === requestKey && (this.previewPages.length || this.previewError)) return
      this.previewRequestKey = requestKey
      this.previewLoading = true
      this.previewError = ''
      try {
        const data = await getPdfPagePreviews(this.spaceId, this.previewDocumentId, this.previewPageQuery)
        this.previewTitle = data?.title || this.resultData.title || 'PDF 页面预览'
        this.previewPages = Array.isArray(data?.pages) ? data.pages : []
        this.previewMissingRanges = Array.isArray(data?.missing_ranges) ? data.missing_ranges : []
      } catch (error) {
        this.previewError = error?.message || '页面缩略图加载失败'
      } finally {
        this.previewLoading = false
      }
    },
    retryPreview() {
      this.loadPreviews(true)
    }
  }
}
</script>

<style scoped>
.tool-wrap { width: min(100%, 560px); }
.tool-pill { min-height: 40px; display: flex; align-items: center; gap: 9px; padding: 7px 11px; box-sizing: border-box; border: 1px solid rgba(255,255,255,.09); border-radius: 11px; background: rgba(255,255,255,.045); cursor: pointer; transition: border-color .2s ease, background .2s ease; }
.tool-wrap.compact .tool-pill { min-height: 32px; gap: 7px; padding: 5px 9px; border-radius: 9px; cursor: default; }
.tool-wrap.compact .tool-pill-expandable { cursor: pointer; }
.tool-wrap.running .tool-pill { border-color: rgba(126,168,255,.2); background: rgba(126,168,255,.055); }
.tool-wrap.succeeded .tool-pill { border-color: rgba(110,194,145,.15); }
.tool-wrap.failed .tool-pill { border-color: rgba(239,68,68,.18); }
.tool-icon { width: 18px; height: 18px; display: grid; place-items: center; color: rgba(255,255,255,.57); flex-shrink: 0; }
.tool-icon :deep(svg) { width: 16px; height: 16px; }
.tool-wrap.compact .tool-icon { width: 16px; height: 16px; }
.tool-wrap.compact .tool-icon :deep(svg) { width: 14px; height: 14px; }
.tool-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 1px; }
.tool-name { color: rgba(255,255,255,.76); font-size: 12px; line-height: 1.4; }
.tool-wrap.compact .tool-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; line-height: 1.25; }
.tool-detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(255,255,255,.34); font-size: 10px; }
.tool-spinner { width: 13px; height: 13px; box-sizing: border-box; border: 2px solid rgba(126,168,255,.23); border-top-color: #8fb3ff; border-radius: 50%; animation: tool-spin .8s linear infinite; }
.tool-wrap.compact .tool-spinner { width: 11px; height: 11px; }
.tool-chevron { width: 18px; text-align: center; color: rgba(255,255,255,.38); transition: transform .2s ease; }
.tool-chevron.expanded { transform: rotate(180deg); }
.tool-status { width: 17px; height: 17px; flex-shrink: 0; }
.tool-wrap.compact .tool-status { width: 15px; height: 15px; }
.tool-status.success { color: #79c99b; }
.tool-status.failed { color: #ff8f8f; }
.tool-panel { margin: 5px 0 0 27px; padding: 9px 11px; border-left: 1px solid rgba(255,255,255,.1); background: rgba(0,0,0,.11); animation: panel-in .18s ease-out; }
.tool-wrap.compact .tool-panel { margin-left: 23px; padding: 8px 9px; }
.tool-section + .tool-section { margin-top: 9px; }
.section-label { display: block; margin-bottom: 4px; color: rgba(255,255,255,.3); font-size: 9px; letter-spacing: .08em; }
.section-value { display: block; max-height: 210px; overflow: auto; color: rgba(255,255,255,.58); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; user-select: text; }
.section-value.error { color: rgba(255,158,158,.76); }
.preview-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 7px; }
.preview-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(255,255,255,.7); font-size: 10px; }
.preview-range { flex-shrink: 0; color: rgba(255,255,255,.35); font-size: 9px; }
.preview-list { max-height: 300px; overflow: hidden; }
.preview-item { padding: 0 0 8px; }
.preview-item + .preview-item { padding-top: 8px; border-top: 1px solid rgba(255,255,255,.07); }
.preview-image { display: block; width: 100%; max-height: 250px; object-fit: contain; border: 1px solid rgba(255,255,255,.1); border-radius: 5px; background: rgba(255,255,255,.06); }
.preview-page-label { display: block; margin-top: 4px; color: rgba(255,255,255,.42); font-size: 9px; text-align: center; }
.preview-state { padding: 18px 4px; color: rgba(255,255,255,.42); font-size: 10px; text-align: center; }
.preview-error { color: rgba(255,158,158,.76); }
.preview-retry { margin-left: 8px; color: #9dbbff; cursor: pointer; }
.preview-missing { display: block; margin-top: 6px; color: rgba(255,196,128,.72); font-size: 9px; line-height: 1.4; }
@keyframes tool-spin { to { transform: rotate(360deg); } }
@keyframes panel-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) { .tool-spinner { animation-duration: 1.6s; } .tool-chevron, .tool-panel { transition: none; animation: none; } }
</style>
