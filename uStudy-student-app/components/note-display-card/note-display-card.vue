<template>
  <view class="ndc-wrap" :class="{ 'ndc-expanded': showDetail || isCollapsing }">
    <!-- ======== Pill 指示器（始终可见） ======== -->
    <view class="ndc-pill"
      :class="{
        'ndc-pill-running': isRunning,
        'ndc-pill-failed': isDoneFailed
      }"
      @click="handlePillClick"
    >
      <image class="ndc-pill-icon" :src="pillIcon" mode="aspectFit" />
      <text class="ndc-pill-text">{{ pillText }}</text>
      <view v-if="isRunning" class="ndc-pill-spinner"></view>
      <template v-else-if="isDoneSuccess">
        <image v-if="isDeleteNote"
          class="ndc-pill-status-icon"
          src="/static/icons/lucide/circle-check.svg" mode="aspectFit" />
        <image v-else
          class="ndc-pill-chevron"
          :class="{ 'ndc-pill-chevron-up': isExpanded }"
          src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
      </template>
      <image v-else-if="isDoneFailed"
        class="ndc-pill-status-icon ndc-pill-status-failed"
        src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg" mode="aspectFit" />
    </view>

    <!-- ======== 详情卡片 ======== -->
    <view v-if="showDetail || isCollapsing"
      :class="{ 'ndc-card-leave': isCollapsing }"
      class="ndc-detail-wrap">

      <!-- list_notes：笔记列表 -->
      <view v-if="toolName === 'list_notes' && isDoneSuccess" class="ndc-card">
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
      <view v-else-if="toolName === 'view_note_detail' && isDoneSuccess" class="ndc-card">
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
      <view v-else-if="toolName === 'update_note' && isDoneSuccess" class="ndc-card">
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
    </view>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'

const PILL_ICONS = {
  list_notes: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
  view_note_detail: '/static/icons/phosphor-icons/SVGs/regular/notebook.svg',
  update_note: '/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg',
  delete_note: '/static/icons/phosphor-icons/SVGs/regular/trash.svg'
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
    isDeleteNote() {
      return this.toolName === 'delete_note'
    },
    hasExpandableDetail() {
      return !this.isDeleteNote
    },
    showDetail() {
      if (!this.hasExpandableDetail) return false
      return this.isDoneSuccess && this.isExpanded
    },
    pillIcon() {
      return PILL_ICONS[this.toolName] || '/static/icons/phosphor-icons/SVGs/regular/notebook.svg'
    },
    pillText() {
      const tool = this.toolName
      if (tool === 'list_notes') {
        if (this.isRunning) return '正在查看笔记列表…'
        if (this.isDoneSuccess) {
          const count = this.toolCall.result?.notes?.length || 0
          return '已查看笔记 · ' + count + ' 篇'
        }
        if (this.isDoneFailed) return '查看笔记失败'
        return '查看笔记'
      }
      if (tool === 'view_note_detail') {
        if (this.isRunning) return '正在查看笔记…'
        if (this.isDoneSuccess) return '已查看笔记详情'
        if (this.isDoneFailed) return '查看笔记失败'
        return '查看笔记'
      }
      if (tool === 'update_note') {
        if (this.isRunning) return '正在更新笔记…'
        if (this.isDoneSuccess) return '已更新笔记'
        if (this.isDoneFailed) return '更新笔记失败'
        return '更新笔记'
      }
      if (tool === 'delete_note') {
        if (this.isRunning) return '正在删除笔记…'
        if (this.isDoneSuccess) return '已删除笔记'
        if (this.isDoneFailed) return '删除笔记失败'
        return '删除笔记'
      }
      return tool
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
    handlePillClick() {
      if (!this.isDoneSuccess || !this.hasExpandableDetail) return
      this.toggleExpand()
    },

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
/* ========== Wrap 容器 ========== */
.ndc-wrap {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ndc-expanded {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 0;
  gap: 0;
}

/* ========== Pill 指示器 ========== */
.ndc-pill {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 24rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  transition: all 0.25s ease;
}

.ndc-expanded .ndc-pill {
  border: none;
  background: transparent;
  border-radius: 24rpx 24rpx 0 0;
  padding: 20rpx 24rpx 16rpx;
}

.ndc-pill-running {
  border-color: rgba(74, 108, 247, 0.3);
  background: rgba(74, 108, 247, 0.06);
}

.ndc-pill-failed {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.ndc-pill-icon {
  width: 32rpx;
  height: 32rpx;
  flex-shrink: 0;
  filter: invert(38%) sepia(78%) saturate(2567%) hue-rotate(221deg) brightness(101%) contrast(94%);
}

.ndc-pill-text {
  flex: 1;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ndc-pill-running .ndc-pill-text {
  color: rgba(255, 255, 255, 0.8);
}

.ndc-pill-spinner {
  width: 22rpx;
  height: 22rpx;
  border: 2rpx solid rgba(74, 108, 247, 0.3);
  border-top-color: #4A6CF7;
  border-radius: 50%;
  animation: ndc-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.ndc-pill-status-icon {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
  filter: invert(48%) sepia(30%) saturate(900%) hue-rotate(100deg) brightness(85%) contrast(90%);
}

.ndc-pill-status-failed {
  filter: invert(40%) sepia(90%) saturate(2000%) hue-rotate(345deg) brightness(90%) contrast(95%);
}

.ndc-pill-chevron {
  width: 24rpx;
  height: 24rpx;
  flex-shrink: 0;
  opacity: 0.35;
  filter: brightness(0) invert(1);
  transition: transform 0.2s ease;
}

.ndc-pill-chevron-up {
  transform: rotate(180deg);
}

@keyframes ndc-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ========== 详情卡片包裹 ========== */
.ndc-detail-wrap {
  animation: ndc-card-enter 0.28s ease-out;
}

.ndc-card-leave {
  animation: ndc-card-leave 0.2s ease-in forwards;
  pointer-events: none;
}

@keyframes ndc-card-enter {
  from {
    opacity: 0;
    transform: translateY(-8rpx);
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
    transform: translateY(-8rpx);
  }
}

/* ========== Card 内容样式 ========== */
.ndc-card {
  border: none;
  background: transparent;
  border-radius: 0 0 24rpx 24rpx;
  padding: 20rpx 24rpx 14rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

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

.ndc-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
}

.ndc-content-preview {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
  word-break: break-word;
}

/* ===== list_notes ===== */
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

/* ===== view_note_detail ===== */
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

/* ===== update_note ===== */
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
