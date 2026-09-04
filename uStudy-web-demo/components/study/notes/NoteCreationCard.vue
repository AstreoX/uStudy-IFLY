<template>
  <view class="note-creation-card" :class="cardClass">
    <!-- Header -->
    <view class="ncc-header">
      <view v-if="isPending" class="ncc-pending-icon">
        <svg viewBox="0 0 256 256" width="14" height="14">
          <circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
          <polyline points="128 72 128 128 184 128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        </svg>
      </view>
      <view v-else-if="toolCall.status === 'running'" class="ncc-spinner"></view>
      <svg v-else-if="toolCall.status === 'done' && toolCall.success" viewBox="0 0 256 256" class="ncc-status-icon ncc-status-success">
        <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <svg v-else-if="toolCall.status === 'done' && !toolCall.success" viewBox="0 0 256 256" class="ncc-status-icon ncc-status-failed">
        <line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
        <line x1="160" y1="160" x2="96" y2="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
      </svg>
      <view class="ncc-icon" v-html="noteIconSvg"></view>
      <text class="ncc-title-text">{{ headerText }}</text>
    </view>

    <!-- ======== Confirmation mode ======== -->
    <template v-if="isPending">
      <!-- Node label dropdown -->
      <view class="ncc-field-row">
        <text class="ncc-field-label">挂载节点</text>
        <select
          class="ncc-node-select"
          :value="editNodeLabel"
          @change="editNodeLabel = $event.target.value"
        >
          <option v-for="opt in nodeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </view>

      <!-- Title input -->
      <view class="ncc-edit-title-row">
        <text class="ncc-field-label">标题</text>
        <input
          class="ncc-title-input"
          v-model="editTitle"
          placeholder="笔记标题"
          maxlength="200"
        />
      </view>

      <!-- Content editor -->
      <view class="ncc-edit-area">
        <view class="ncc-edit-toolbar">
          <view class="ncc-tab-group">
            <view
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'code' }"
              @click="editMode = 'code'"
            >编辑</view>
            <view
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'preview' }"
              @click="editMode = 'preview'"
            >预览</view>
          </view>
          <view class="ncc-action-group">
            <view
              class="ncc-cancel-btn"
              :class="{ 'ncc-cancel-btn-disabled': isSubmitting }"
              @click="handleCancel"
            >取消</view>
            <view
              class="ncc-confirm-btn"
              :class="{ 'ncc-confirm-btn-disabled': isSubmitting }"
              @click="handleConfirm"
            >{{ isSubmitting ? '提交中...' : '确认创建' }}</view>
          </view>
        </view>
        <textarea
          v-if="editMode === 'code'"
          class="ncc-textarea"
          v-model="editContent"
          placeholder="笔记内容 (支持 Markdown)"
        ></textarea>
        <view v-else class="ncc-preview-wrap">
          <MarkdownRender :content="editContent" />
        </view>
      </view>
      <text v-if="submitError" class="ncc-save-error">{{ submitError }}</text>
    </template>

    <!-- ======== View mode (done or running) ======== -->
    <template v-else-if="!isEditing">
      <!-- Knowledge point tag -->
      <view v-if="nodeLabel" class="ncc-tag-row">
        <view class="ncc-node-tag">{{ nodeLabel }}</view>
      </view>

      <!-- Running state: no content yet -->
      <view v-if="!hasContent" class="ncc-loading-hint">
        <text class="ncc-loading-text">正在创建笔记...</text>
      </view>
      <!-- Done state: show full content -->
      <template v-else>
        <text class="ncc-note-title">{{ displayTitle }}</text>
        <view class="ncc-content-area">
          <view
            v-if="canEdit"
            class="ncc-edit-btn"
            @click="enterEditMode"
          >
            <svg viewBox="0 0 256 256" class="ncc-edit-icon">
              <path d="M92.69,216H48a8,8,0,0,1-8-8V163.31a8,8,0,0,1,2.34-5.65L165.66,34.34a8,8,0,0,1,11.31,0L220.69,78a8,8,0,0,1,0,11.31L97.37,212.69A8,8,0,0,1,92.69,216Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
              <line x1="136" y1="64" x2="192" y2="120" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
            </svg>
            <text class="ncc-edit-label">编辑</text>
          </view>
          <view class="ncc-markdown-wrap">
            <MarkdownRender :content="displayContent" />
          </view>
        </view>
      </template>
    </template>

    <!-- ======== Post-creation edit mode ======== -->
    <template v-else>
      <view class="ncc-edit-title-row">
        <input
          class="ncc-title-input"
          v-model="editTitle"
          placeholder="笔记标题"
          maxlength="200"
        />
      </view>
      <view class="ncc-edit-area">
        <view class="ncc-edit-toolbar">
          <view class="ncc-tab-group">
            <view
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'code' }"
              @click="editMode = 'code'"
            >编辑</view>
            <view
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'preview' }"
              @click="editMode = 'preview'"
            >预览</view>
          </view>
          <view class="ncc-action-group">
            <view
              class="ncc-cancel-btn"
              :class="{ 'ncc-cancel-btn-disabled': isSaving }"
              @click="cancelEdit"
            >取消</view>
            <view
              class="ncc-confirm-btn"
              :class="{ 'ncc-confirm-btn-disabled': isSaving }"
              @click="saveEdit"
            >{{ isSaving ? '保存中...' : '确认' }}</view>
          </view>
        </view>
        <textarea
          v-if="editMode === 'code'"
          class="ncc-textarea"
          v-model="editContent"
          placeholder="笔记内容 (支持 Markdown)"
        ></textarea>
        <view v-else class="ncc-preview-wrap">
          <MarkdownRender :content="editContent" />
        </view>
        <text v-if="saveError" class="ncc-save-error">{{ saveError }}</text>
      </view>
    </template>
  </view>
</template>

<script>
import MarkdownRender from '@/components/markdown-render/markdown-render.vue'
import { getNoteDetail, updateNote, getSpaceGraph } from '@/api/space'
import { submitToolResult } from '@/api/chat'

export default {
  name: 'NoteCreationCard',
  components: { MarkdownRender },
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
  data() {
    return {
      isEditing: false,
      editMode: 'code',
      editContent: '',
      editTitle: '',
      editNodeLabel: '',
      isSaving: false,
      isSubmitting: false,
      saveError: '',
      submitError: '',
      savedContent: null,
      savedTitle: null,
      graphNodes: []
    }
  },
  computed: {
    isPending() {
      return this.toolCall.status === 'pending_confirmation'
    },
    cardClass() {
      if (this.isPending) return 'ncc-pending'
      if (this.toolCall.status === 'running') return 'ncc-running'
      if (this.toolCall.status === 'done' && this.toolCall.success) return 'ncc-success'
      if (this.toolCall.status === 'done' && !this.toolCall.success) return 'ncc-failed'
      return 'ncc-running'
    },
    headerText() {
      if (this.isPending) return '创建笔记 — 待确认'
      return '创建笔记'
    },
    nodeLabel() {
      const label = this.toolCall.arguments?.node_label
      if (!label || label === 'FREE') return ''
      return label
    },
    nodeOptions() {
      const options = [{ value: 'FREE', label: '自由笔记' }]
      for (const node of this.graphNodes) {
        if (node.label) {
          options.push({ value: node.label, label: node.label })
        }
      }
      return options
    },
    displayTitle() {
      if (this.savedTitle !== null) return this.savedTitle
      return this.toolCall.arguments?.title || '未命名笔记'
    },
    displayContent() {
      if (this.savedContent !== null) return this.savedContent
      return this.toolCall.arguments?.content || ''
    },
    noteId() {
      return this.toolCall.result?.note_id
    },
    hasContent() {
      return this.savedContent !== null ||
        !!(this.toolCall.arguments?.content || this.toolCall.arguments?.title)
    },
    canEdit() {
      return this.toolCall.status === 'done' && this.toolCall.success && this.noteId
    },
    noteIconSvg() {
      return '<svg viewBox="0 0 256 256" width="14" height="14"><path d="M200,32H56A16,16,0,0,0,40,48V208a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V48A16,16,0,0,0,200,32ZM80,80h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h96a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Zm0,40h64a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Z" fill="currentColor"/></svg>'
    }
  },
  watch: {
    'toolCall.status'(newStatus) {
      if (newStatus === 'pending_confirmation') {
        this.initConfirmationMode()
      }
    }
  },
  mounted() {
    if (this.isPending) {
      this.initConfirmationMode()
    }
  },
  methods: {
    async initConfirmationMode() {
      this.editTitle = this.toolCall.arguments?.title || ''
      this.editContent = this.toolCall.arguments?.content || ''
      this.editNodeLabel = this.toolCall.arguments?.node_label || 'FREE'
      this.editMode = 'code'
      this.submitError = ''

      if (this.spaceId) {
        try {
          const { nodes } = await getSpaceGraph(this.spaceId)
          this.graphNodes = nodes || []
        } catch {
          this.graphNodes = []
        }
      }
    },

    async handleConfirm() {
      if (this.isSubmitting) return
      this.isSubmitting = true
      this.submitError = ''

      try {
        await submitToolResult(this.conversationId, {
          tool_call_id: this.toolCall.id,
          success: true,
          result: {
            arguments: {
              title: this.editTitle,
              content: this.editContent,
              node_label: this.editNodeLabel
            }
          }
        })
        // Keep isSubmitting=true to prevent double-submit; card will transition on SSE done event
      } catch (error) {
        this.submitError = error?.message || '提交失败，请重试'
        this.isSubmitting = false
      }
    },

    async handleCancel() {
      if (this.isSubmitting) return
      this.isSubmitting = true
      this.submitError = ''

      try {
        await submitToolResult(this.conversationId, {
          tool_call_id: this.toolCall.id,
          success: false,
          error: '用户取消了笔记创建'
        })
        // Keep isSubmitting=true; card will transition on SSE done event
      } catch (error) {
        this.submitError = error?.message || '提交失败，请重试'
        this.isSubmitting = false
      }
    },

    async enterEditMode() {
      if (this.isEditing) return
      this.isEditing = true
      this.saveError = ''
      this.editMode = 'code'

      if (this.spaceId && this.noteId) {
        try {
          const detail = await getNoteDetail(this.spaceId, this.noteId)
          this.editContent = detail.content || ''
          this.editTitle = detail.title || ''
        } catch {
          this.editContent = this.displayContent
          this.editTitle = this.displayTitle
        }
      } else {
        this.editContent = this.displayContent
        this.editTitle = this.displayTitle
      }
    },
    cancelEdit() {
      if (this.isSaving) return
      this.isEditing = false
      this.editContent = ''
      this.editTitle = ''
      this.saveError = ''
    },
    async saveEdit() {
      if (this.isSaving) return
      if (!this.spaceId || !this.noteId) {
        this.saveError = '无法保存：缺少笔记信息'
        return
      }

      this.isSaving = true
      this.saveError = ''

      try {
        await updateNote(this.spaceId, this.noteId, {
          title: this.editTitle,
          content: this.editContent
        })
        this.savedContent = this.editContent
        this.savedTitle = this.editTitle
        this.isEditing = false
      } catch (error) {
        this.saveError = error?.message || '保存失败，请重试'
      } finally {
        this.isSaving = false
      }
    }
  }
}
</script>

<style scoped>
.note-creation-card {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.04);
  transition: border-color 0.2s ease, background 0.2s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.16);
}

.ncc-pending {
  border-color: rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.06);
}

.ncc-running {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.06);
}

.ncc-success {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.ncc-failed {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
}

/* Header */
.ncc-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.ncc-pending-icon {
  display: flex;
  align-items: center;
  color: rgba(251, 191, 36, 0.9);
  flex-shrink: 0;
}

.ncc-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: rgba(59, 130, 246, 0.9);
  border-radius: 50%;
  animation: ncc-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes ncc-spin {
  to { transform: rotate(360deg); }
}

.ncc-status-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.ncc-status-success {
  color: rgba(34, 197, 94, 0.9);
}

.ncc-status-failed {
  color: rgba(239, 68, 68, 0.9);
}

.ncc-icon {
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.ncc-success .ncc-icon {
  color: rgba(74, 222, 128, 0.95);
}

.ncc-title-text {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.78);
}

/* Field row (for node dropdown) */
.ncc-field-row {
  margin-top: 10px;
}

.ncc-field-label {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 4px;
}

.ncc-node-select {
  width: 100%;
  padding: 6px 10px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  box-sizing: border-box;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.4)' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  padding-right: 28px;
}

.ncc-node-select:focus {
  border-color: rgba(251, 191, 36, 0.5);
}
.ncc-node-select::-webkit-scrollbar {
  width: 6px;
}
.ncc-node-select::-webkit-scrollbar-track {
  background: #1e1e2e;
}
.ncc-node-select::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.ncc-node-select::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.ncc-node-select option {
  background: #1e1e2e;
  color: rgba(255, 255, 255, 0.85);
}

/* Tag row */
.ncc-tag-row {
  margin-top: 8px;
}

.ncc-node-tag {
  display: inline-block;
  font-size: 11px;
  color: rgba(129, 140, 248, 0.9);
  padding: 3px 9px;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 999px;
}

/* Loading state */
.ncc-loading-hint {
  margin-top: 6px;
  padding: 6px 0;
}

.ncc-loading-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
}

/* Note title (view mode) */
.ncc-note-title {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  margin-top: 8px;
  line-height: 1.4;
}

/* Content area */
.ncc-content-area {
  position: relative;
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.025);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ncc-edit-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: background 0.15s ease;
  z-index: 1;
}

.ncc-edit-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.ncc-edit-icon {
  width: 12px;
  height: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.ncc-edit-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.ncc-markdown-wrap {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.7;
  word-break: break-word;
}

/* Edit mode */
.ncc-edit-title-row {
  margin-top: 10px;
}

.ncc-title-input {
  width: 100%;
  height: 40px;
  line-height: 40px;
  padding: 0 14px;
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  outline: none;
  box-sizing: border-box;
  cursor: text;
}

.ncc-title-input:focus {
  border-color: rgba(59, 130, 246, 0.5);
}

.ncc-edit-area {
  margin-top: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  overflow: hidden;
}

.ncc-edit-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.ncc-tab-group {
  display: flex;
  gap: 2px;
}

.ncc-tab {
  padding: 3px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.ncc-tab:hover {
  color: rgba(255, 255, 255, 0.7);
}

.ncc-tab-active {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.ncc-action-group {
  display: flex;
  gap: 6px;
}

.ncc-cancel-btn {
  padding: 3px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.ncc-cancel-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.ncc-cancel-btn-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ncc-confirm-btn {
  padding: 3px 10px;
  font-size: 11px;
  color: #ffffff;
  background: rgba(59, 130, 246, 0.7);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.ncc-confirm-btn:hover {
  background: rgba(59, 130, 246, 0.85);
}

.ncc-confirm-btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ncc-textarea {
  width: 100%;
  min-height: 200px;
  padding: 10px 12px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(0, 0, 0, 0.24);
  border: none;
  outline: none;
  resize: vertical;
  line-height: 1.6;
  box-sizing: border-box;
}

.ncc-preview-wrap {
  padding: 10px 12px;
  min-height: 200px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.7;
  word-break: break-word;
}

.ncc-save-error {
  display: block;
  padding: 6px 12px;
  font-size: 11px;
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.08);
  border-top: 1px solid rgba(239, 68, 68, 0.15);
}
</style>
