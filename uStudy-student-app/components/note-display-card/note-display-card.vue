<template>
  <!-- list_notes：笔记列表 -->
  <view v-if="toolName === 'list_notes' && isSuccess" class="ndc-card">
    <view class="ndc-card-header">
      <view class="ndc-icon-wrap">
        <image class="ndc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook.svg" mode="aspectFit" />
      </view>
      <view class="ndc-title-col">
        <text class="ndc-title">笔记列表</text>
        <text class="ndc-meta">共 {{ noteList.length }} 篇笔记</text>
      </view>
    </view>
    <view class="ndc-divider"></view>
    <view v-if="noteList.length" class="ndc-note-list">
      <view v-for="note in noteList" :key="note.note_id" class="ndc-note-item">
        <text class="ndc-note-item-title">{{ note.title }}</text>
        <text class="ndc-note-item-meta">{{ formatNoteDate(note.created_at) }}{{ note.attachment_count ? ' · ' + note.attachment_count + ' 个附件' : '' }}</text>
        <text v-if="note.content_preview" class="ndc-note-item-preview">{{ note.content_preview }}</text>
      </view>
    </view>
    <view v-else class="ndc-empty">
      <text class="ndc-empty-text">暂无笔记</text>
    </view>
  </view>

  <!-- view_note_detail：笔记详情 -->
  <view v-else-if="toolName === 'view_note_detail' && isSuccess" class="ndc-card">
    <view class="ndc-card-header">
      <view class="ndc-icon-wrap">
        <image class="ndc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/file-text.svg" mode="aspectFit" />
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
        <view v-for="att in attachments" :key="att.id" class="ndc-attachment-pill">
          <image class="ndc-attachment-icon" src="/static/icons/phosphor-icons/SVGs/regular/link.svg" mode="aspectFit" />
          <text class="ndc-attachment-name">{{ att.file_name }}</text>
        </view>
      </view>
    </view>
  </view>

  <!-- update_note：更新笔记 -->
  <view v-else-if="toolName === 'update_note' && isSuccess" class="ndc-card">
    <view class="ndc-card-header">
      <view class="ndc-icon-wrap">
        <image class="ndc-file-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
      </view>
      <view class="ndc-title-col">
        <text class="ndc-title">{{ noteData.title || '未命名笔记' }}</text>
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
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'

export default {
  name: 'NoteDisplayCard',
  components: { MarkdownRender },
  props: {
    toolCall: {
      type: Object,
      required: true
    }
  },
  computed: {
    toolName() {
      return this.toolCall.tool
    },
    isSuccess() {
      return this.toolCall.status === 'done' && this.toolCall.success
    },
    noteData() {
      return this.toolCall.result || {}
    },
    noteList() {
      return this.noteData.notes || []
    },
    attachments() {
      return this.noteData.attachments || []
    },
    displayContent() {
      const raw = this.noteData.numbered_content || ''
      return this.stripNumberedContent(raw)
    },
    contentMeta() {
      const content = this.displayContent
      if (!content) return ''
      const headings = (content.match(/^#{1,3}\s+/gm) || []).length
      const chineseChars = (content.match(/[\u4e00-\u9fff]/g) || []).length
      const englishWords = content.replace(/[\u4e00-\u9fff]/g, '').split(/\s+/).filter(w => w.length > 0).length
      const totalChars = chineseChars + englishWords
      const parts = []
      if (headings > 0) parts.push(headings + ' 个章节')
      if (totalChars > 0) parts.push(totalChars.toLocaleString() + ' 字')
      return parts.join(' · ') || ''
    },
    // update_note: 仅展示被更新的行
    isPartialUpdate() {
      const args = this.toolCall.arguments || {}
      return args.line_start != null
    },
    updateDisplayContent() {
      if (this.isPartialUpdate) {
        return this.toolCall.arguments?.new_content || ''
      }
      return this.displayContent
    },
    updateMeta() {
      const args = this.toolCall.arguments || {}
      if (this.isPartialUpdate) {
        const start = args.line_start
        const end = args.line_end || start
        if (start === end) {
          return '更新了第 ' + start + ' 行'
        }
        return '更新了第 ' + start + '-' + end + ' 行'
      }
      return '整篇替换 · ' + this.contentMeta
    }
  },
  methods: {
    stripNumberedContent(str) {
      if (!str) return ''
      return str
        .split('\n')
        .map(line => {
          const tabIndex = line.indexOf('\t')
          if (tabIndex >= 0 && /^\d+$/.test(line.substring(0, tabIndex))) {
            return line.substring(tabIndex + 1)
          }
          return line
        })
        .join('\n')
    },
    formatNoteDate(dateStr) {
      if (!dateStr) return ''
      try {
        const d = new Date(dateStr)
        const year = d.getFullYear()
        const month = String(d.getMonth() + 1).padStart(2, '0')
        const day = String(d.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
      } catch {
        return dateStr
      }
    }
  }
}
</script>

<style scoped>
/* 卡片容器 */
.ndc-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 24rpx 28rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

/* Header 行 */
.ndc-card-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
}

.ndc-icon-wrap {
  width: 64rpx;
  height: 64rpx;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ndc-file-icon {
  width: 32rpx;
  height: 32rpx;
  filter: brightness(0) invert(1);
  opacity: 0.6;
}

.ndc-title-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.ndc-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.3;
}

.ndc-meta {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

/* 分割线 */
.ndc-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
}

/* 内容预览 */
.ndc-content-preview {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
  word-break: break-word;
}

/* ===== list_notes：笔记列表 ===== */
.ndc-note-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.ndc-note-item {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  padding: 16rpx 20rpx;
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
}

.ndc-note-item-title {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.4;
}

.ndc-note-item-meta {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.35);
}

.ndc-note-item-preview {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 空状态 */
.ndc-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32rpx 0;
}

.ndc-empty-text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.3);
}

/* ===== view_note_detail：附件 ===== */
.ndc-attachments-section {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.ndc-attachments-label {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.4);
}

.ndc-attachments-row {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 10rpx;
}

.ndc-attachment-pill {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6rpx;
  padding: 8rpx 16rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 100rpx;
}

.ndc-attachment-icon {
  width: 24rpx;
  height: 24rpx;
  filter: brightness(0) invert(1);
  opacity: 0.5;
}

.ndc-attachment-name {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.7);
  max-width: 300rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== update_note：已更新标签 ===== */
.ndc-updated-badge {
  display: flex;
  align-items: center;
  padding: 6rpx 14rpx;
  background: rgba(74, 222, 128, 0.12);
  border-radius: 100rpx;
  flex-shrink: 0;
}

.ndc-updated-badge-text {
  font-size: 20rpx;
  font-weight: 500;
  color: rgba(74, 222, 128, 0.9);
}
</style>
