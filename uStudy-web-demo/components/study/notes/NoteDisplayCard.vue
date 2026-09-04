<template>
  <view class="ndc-wrap" :class="{ 'ndc-expanded': showDetail || isCollapsing }">
    <view
      class="ndc-pill"
      :class="{
        'ndc-pill-running': isRunning,
        'ndc-pill-success': isDoneSuccess,
        'ndc-pill-failed': isDoneFailed
      }"
      @click="handlePillClick"
    >
      <view class="ndc-pill-icon ndc-icon-svg" v-html="pillIconSvg"></view>
      <text class="ndc-pill-text">{{ pillText }}</text>
      <view v-if="isRunning" class="ndc-pill-spinner"></view>
      <text v-else-if="isDoneSuccess && hasExpandableDetail" class="ndc-pill-chevron" :class="{ 'ndc-pill-chevron-up': isExpanded }">⌄</text>
      <svg v-else-if="isDoneSuccess" viewBox="0 0 256 256" class="ndc-pill-status-icon ndc-pill-status-success">
        <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <svg v-else-if="isDoneFailed" viewBox="0 0 256 256" class="ndc-pill-status-icon ndc-pill-status-failed">
        <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
    </view>

    <view v-if="showDetail || isCollapsing" class="ndc-detail-wrap" :class="{ 'ndc-card-leave': isCollapsing }">
      <view v-if="toolName === 'list_notes' && isDoneSuccess" class="ndc-card">
        <view class="ndc-card-header">
          <view class="ndc-icon-wrap">
            <view class="ndc-file-icon ndc-icon-svg" v-html="headerIconSvg"></view>
          </view>
          <view class="ndc-title-col">
            <text class="ndc-title">笔记列表</text>
            <text class="ndc-meta">共 {{ noteList.length }} 篇笔记</text>
          </view>
        </view>
        <view class="ndc-divider"></view>
        <view v-if="noteList.length" class="ndc-note-list">
          <view v-for="note in noteList" :key="note.note_id || note.id || note.title" class="ndc-note-item">
            <text class="ndc-note-item-title">{{ note.title || '未命名笔记' }}</text>
            <text class="ndc-note-item-meta">{{ formatNoteDate(note.created_at || note.updated_at) }}{{ note.attachment_count ? ' · ' + note.attachment_count + ' 个附件' : '' }}</text>
            <text v-if="note.content_preview" class="ndc-note-item-preview">{{ note.content_preview }}</text>
          </view>
        </view>
        <view v-else class="ndc-empty">
          <text class="ndc-empty-text">暂无笔记</text>
        </view>
      </view>

      <view v-else-if="toolName === 'view_note_detail' && isDoneSuccess" class="ndc-card">
        <view class="ndc-card-header">
          <view class="ndc-icon-wrap">
            <view class="ndc-file-icon ndc-icon-svg" v-html="headerIconSvg"></view>
          </view>
          <view class="ndc-title-col">
            <text class="ndc-title">{{ noteData.title || '未命名笔记' }}</text>
            <text class="ndc-meta">{{ contentMeta }}</text>
          </view>
        </view>
        <view class="ndc-divider"></view>
        <view class="ndc-content-preview">
          <MarkdownRender :content="displayContent" />
        </view>
        <view v-if="attachments.length" class="ndc-attachments-section">
          <text class="ndc-attachments-label">附件 ({{ attachments.length }})</text>
          <view class="ndc-attachments-row">
            <view v-for="att in attachments" :key="att.id || att.file_name" class="ndc-attachment-pill">
              <view class="ndc-attachment-icon ndc-icon-svg" v-html="linkIconSvg"></view>
              <text class="ndc-attachment-name">{{ att.file_name || att.original_filename || att.name }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-else-if="toolName === 'update_note' && isDoneSuccess" class="ndc-card">
        <view class="ndc-card-header">
          <view class="ndc-icon-wrap">
            <view class="ndc-file-icon ndc-icon-svg" v-html="headerIconSvg"></view>
          </view>
          <view class="ndc-title-col">
            <text class="ndc-title">{{ noteData.title || toolCall.arguments?.title || '未命名笔记' }}</text>
            <text class="ndc-meta">{{ updateMeta }}</text>
          </view>
          <view class="ndc-updated-badge">
            <text class="ndc-updated-badge-text">已更新</text>
          </view>
        </view>
        <view class="ndc-divider"></view>
        <view class="ndc-content-preview">
          <MarkdownRender :content="updateDisplayContent" />
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'

const NOTE_ICON = '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M200,32H56A16,16,0,0,0,40,48V208a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32ZM80,80h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h64a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Z" fill="currentColor"/></svg>'
const FILE_ICON = '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M48,40H160l48,48V208a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V48A8,8,0,0,1,48,40Z" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/><polyline points="160 40 160 88 208 88" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/></svg>'
const PENCIL_ICON = '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M92.7,179.3,40,192l12.7-52.7a8.1,8.1,0,0,1,2.1-3.8L156.7,33.7a16,16,0,0,1,22.6,0l43,43a16,16,0,0,1,0,22.6L120.5,201.2A8.1,8.1,0,0,1,116.7,203.3Z" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/><line x1="136" y1="56" x2="200" y2="120" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/></svg>'
const TRASH_ICON = '<svg viewBox="0 0 256 256" width="14" height="14"><polyline points="216 56 40 56" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><path d="M96,24h64a8,8,0,0,1,8,8V56H88V32A8,8,0,0,1,96,24Z" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/><path d="M56,56l8,144a8,8,0,0,0,8,8H184a8,8,0,0,0,8-8l8-144" fill="none" stroke="currentColor" stroke-width="16" stroke-linejoin="round"/><line x1="104" y1="104" x2="104" y2="168" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/><line x1="152" y1="104" x2="152" y2="168" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/></svg>'
const LINK_ICON = '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M144.3,111.7l-32.6,32.6a32,32,0,0,1-45.3-45.3L99,66.3a32,32,0,0,1,45.3,0" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/><path d="M111.7,144.3l32.6-32.6a32,32,0,0,1,45.3,45.3L157,189.7a32,32,0,0,1-45.3,0" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/></svg>'

const PILL_ICONS = {
  list_notes: NOTE_ICON,
  view_note_detail: NOTE_ICON,
  update_note: PENCIL_ICON,
  delete_note: TRASH_ICON
}

const HEADER_ICONS = {
  list_notes: NOTE_ICON,
  view_note_detail: FILE_ICON,
  update_note: PENCIL_ICON
}

export default {
  name: 'NoteDisplayCard',
  components: { MarkdownRender },
  props: {
    toolCall: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      isExpanded: true,
      isCollapsing: false
    }
  },
  computed: {
    toolName() {
      return this.toolCall.tool
    },
    isRunning() {
      return this.toolCall.status === 'running'
    },
    isDoneSuccess() {
      return this.toolCall.status === 'done' && this.toolCall.success
    },
    isDoneFailed() {
      return this.toolCall.status === 'done' && !this.toolCall.success
    },
    hasExpandableDetail() {
      return this.toolName !== 'delete_note'
    },
    showDetail() {
      return this.isDoneSuccess && this.hasExpandableDetail && this.isExpanded
    },
    pillIconSvg() {
      return PILL_ICONS[this.toolName] || NOTE_ICON
    },
    headerIconSvg() {
      return HEADER_ICONS[this.toolName] || NOTE_ICON
    },
    linkIconSvg() {
      return LINK_ICON
    },
    noteData() {
      return this.toolCall.result?.data || this.toolCall.result || {}
    },
    noteList() {
      return Array.isArray(this.noteData.notes) ? this.noteData.notes : []
    },
    attachments() {
      return Array.isArray(this.noteData.attachments) ? this.noteData.attachments : []
    },
    displayContent() {
      const raw = this.noteData.numbered_content || this.noteData.content || this.noteData.preview || ''
      return this.stripNumberedContent(raw)
    },
    contentMeta() {
      const content = this.displayContent
      if (!content) return ''
      const headings = (content.match(/^#{1,3}\s+/gm) || []).length
      const chineseChars = (content.match(/[\u4e00-\u9fff]/g) || []).length
      const englishWords = content.replace(/[\u4e00-\u9fff]/g, ' ').split(/\s+/).filter(Boolean).length
      const totalChars = chineseChars + englishWords
      const parts = []
      if (headings > 0) parts.push(`${headings} 个章节`)
      if (totalChars > 0) parts.push(`${totalChars.toLocaleString()} 字`)
      return parts.join(' · ')
    },
    isPartialUpdate() {
      return this.toolCall.arguments?.line_start != null
    },
    updateDisplayContent() {
      if (this.isPartialUpdate) return this.toolCall.arguments?.new_content || ''
      return this.displayContent
    },
    updateMeta() {
      const args = this.toolCall.arguments || {}
      if (this.isPartialUpdate) {
        const start = args.line_start
        const end = args.line_end || start
        return start === end ? `更新了第 ${start} 行` : `更新了第 ${start}-${end} 行`
      }
      return this.contentMeta ? `整篇替换 · ${this.contentMeta}` : '整篇替换'
    },
    pillText() {
      if (this.toolName === 'list_notes') {
        if (this.isRunning) return '正在查看笔记列表…'
        if (this.isDoneSuccess) return `已查看笔记 · ${this.noteList.length} 篇`
        if (this.isDoneFailed) return '查看笔记失败'
        return '查看笔记'
      }
      if (this.toolName === 'view_note_detail') {
        if (this.isRunning) return '正在查看笔记…'
        if (this.isDoneSuccess) return '已查看笔记详情'
        if (this.isDoneFailed) return '查看笔记失败'
        return '查看笔记'
      }
      if (this.toolName === 'update_note') {
        if (this.isRunning) return '正在更新笔记…'
        if (this.isDoneSuccess) return '已更新笔记'
        if (this.isDoneFailed) return '更新笔记失败'
        return '更新笔记'
      }
      if (this.toolName === 'delete_note') {
        if (this.isRunning) return '正在删除笔记…'
        if (this.isDoneSuccess) return '已删除笔记'
        if (this.isDoneFailed) return '删除笔记失败'
        return '删除笔记'
      }
      return this.toolName
    }
  },
  methods: {
    handlePillClick() {
      if (!this.isDoneSuccess || !this.hasExpandableDetail) return
      if (this.isExpanded) {
        this.isCollapsing = true
        setTimeout(() => {
          this.isExpanded = false
          this.isCollapsing = false
        }, 200)
        return
      }
      this.isExpanded = true
    },
    stripNumberedContent(content) {
      if (!content) return ''
      return String(content)
        .split('\n')
        .map((line) => {
          const tabIndex = line.indexOf('\t')
          if (tabIndex >= 0 && /^\d+$/.test(line.slice(0, tabIndex))) {
            return line.slice(tabIndex + 1)
          }
          return line
        })
        .join('\n')
    },
    formatNoteDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      if (Number.isNaN(date.getTime())) return dateStr
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }
  }
}
</script>

<style scoped>
.ndc-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ndc-expanded {
  gap: 0;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(34, 197, 94, 0.35);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.ndc-pill {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.ndc-expanded .ndc-pill {
  border: none;
  background: rgba(34, 197, 94, 0.06);
  border-radius: 8px 8px 0 0;
  padding: 8px 12px 6px;
  box-shadow: none;
}

.ndc-pill-running {
  border-color: rgba(74, 108, 247, 0.3);
  background: rgba(74, 108, 247, 0.06);
}

.ndc-pill-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.ndc-pill-success:hover {
  border-color: rgba(34, 197, 94, 0.5);
  background: rgba(34, 197, 94, 0.1);
}

.ndc-pill-failed {
  border-color: rgba(248, 113, 113, 0.2);
  background: rgba(248, 113, 113, 0.05);
}

.ndc-pill-icon,
.ndc-file-icon,
.ndc-attachment-icon {
  width: 16px;
  height: 16px;
  color: rgba(96, 165, 250, 0.95);
  flex-shrink: 0;
}

.ndc-pill-success .ndc-pill-icon {
  color: rgba(74, 222, 128, 0.95);
}

.ndc-icon-svg :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

.ndc-pill-text {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ndc-pill-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(74, 108, 247, 0.3);
  border-top-color: #4A6CF7;
  border-radius: 50%;
  animation: ndc-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.ndc-pill-chevron,
.ndc-pill-status-icon {
  flex-shrink: 0;
}

.ndc-pill-chevron {
  font-size: 14px;
  line-height: 1;
  color: rgba(255, 255, 255, 0.36);
  transition: transform 0.2s ease;
}

.ndc-pill-chevron-up {
  transform: rotate(180deg);
}

.ndc-pill-status-icon {
  width: 16px;
  height: 16px;
}

.ndc-pill-status-success {
  color: rgba(94, 194, 105, 0.96);
}

.ndc-pill-status-failed {
  color: rgba(248, 113, 113, 0.92);
}

.ndc-detail-wrap {
  animation: ndc-card-enter 0.28s ease-out;
}

.ndc-card-leave {
  animation: ndc-card-leave 0.2s ease-in forwards;
  pointer-events: none;
}

.ndc-card {
  padding: 12px 14px;
  border: none;
  border-top: 1px solid rgba(34, 197, 94, 0.16);
  background: rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.ndc-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ndc-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: rgba(74, 108, 247, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ndc-title-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ndc-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
}

.ndc-meta,
.ndc-note-item-meta,
.ndc-empty-text,
.ndc-attachments-label,
.ndc-note-item-preview {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.ndc-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 10px 0;
}

.ndc-note-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ndc-note-item {
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.ndc-note-item-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.82);
}

.ndc-note-item-meta {
  display: block;
  margin-top: 4px;
}

.ndc-note-item-preview {
  display: block;
  margin-top: 6px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ndc-content-preview {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  padding: 12px;
}

.ndc-content-preview :deep(.markdown-container) {
  background: transparent;
}

.ndc-content-preview :deep(.markdown-content) {
  color: rgba(255, 255, 255, 0.82);
}

.ndc-attachments-section {
  margin-top: 12px;
}

.ndc-attachments-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.ndc-attachment-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.ndc-attachment-name {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.ndc-updated-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(74, 222, 128, 0.12);
  flex-shrink: 0;
}

.ndc-updated-badge-text {
  font-size: 11px;
  font-weight: 600;
  color: rgba(74, 222, 128, 0.94);
}

.ndc-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 0 4px;
}

@keyframes ndc-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes ndc-card-enter {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes ndc-card-leave {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-8px);
  }
}
</style>
