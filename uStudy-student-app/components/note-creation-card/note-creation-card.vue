<template>
  <view class="note-creation-card" :class="cardClass">
    <!-- Header -->
    <view class="ncc-header">
      <view v-if="isPending" class="ncc-pending-icon">
        <image class="ncc-header-icon" src="/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg" mode="aspectFit" />
      </view>
      <view v-else-if="toolCall.status === 'running'" class="ncc-spinner"></view>
      <image
        v-else-if="toolCall.status === 'done' && toolCall.success"
        class="ncc-header-icon ncc-status-success"
        src="/static/icons/phosphor-icons/SVGs/fill/check-circle-fill.svg"
        mode="aspectFit"
      />
      <image
        v-else-if="toolCall.status === 'done' && !toolCall.success"
        class="ncc-header-icon ncc-status-failed"
        src="/static/icons/phosphor-icons/SVGs/fill/x-circle-fill.svg"
        mode="aspectFit"
      />
      <image class="ncc-header-icon" src="/static/icons/phosphor-icons/SVGs/regular/notebook.svg" mode="aspectFit" />
      <text class="ncc-title-text">{{ headerText }}</text>
    </view>

    <!-- ======== Confirmation mode ======== -->
    <template v-if="isPending">
      <!-- Node label picker -->
      <view class="ncc-field-row">
        <text class="ncc-field-label">挂载节点</text>
        <picker
          mode="selector"
          :range="nodeOptionLabels"
          :value="selectedNodeIndex"
          @change="onNodePickerChange"
        >
          <view class="ncc-node-picker">
            <text class="ncc-node-picker-text">{{ currentNodeLabel }}</text>
            <image class="ncc-node-picker-arrow" src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg" mode="aspectFit" />
          </view>
        </picker>
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
            <text
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'code' }"
              @click="editMode = 'code'"
            >编辑</text>
            <text
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'preview' }"
              @click="editMode = 'preview'"
            >预览</text>
          </view>
          <view class="ncc-action-group">
            <text
              class="ncc-cancel-btn"
              :class="{ 'ncc-cancel-btn-disabled': isSubmitting }"
              @click="handleCancel"
            >取消</text>
            <text
              class="ncc-confirm-btn"
              :class="{ 'ncc-confirm-btn-disabled': isSubmitting }"
              @click="handleConfirm"
            >{{ isSubmitting ? '提交中...' : '确认创建' }}</text>
          </view>
        </view>
        <textarea
          v-if="editMode === 'code'"
          class="ncc-textarea"
          v-model="editContent"
          placeholder="笔记内容 (支持 Markdown)"
          :auto-height="false"
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
        <text class="ncc-node-tag">{{ nodeLabel }}</text>
      </view>

      <!-- Running state -->
      <view v-if="!hasContent" class="ncc-loading-hint">
        <text class="ncc-loading-text">正在创建笔记...</text>
      </view>
      <!-- Done state -->
      <template v-else>
        <text class="ncc-note-title">{{ displayTitle }}</text>
        <view class="ncc-content-area">
          <view v-if="canEdit" class="ncc-edit-btn" @click="enterEditMode">
            <image class="ncc-edit-icon" src="/static/icons/phosphor-icons/SVGs/regular/pencil-simple.svg" mode="aspectFit" />
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
            <text
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'code' }"
              @click="editMode = 'code'"
            >编辑</text>
            <text
              class="ncc-tab"
              :class="{ 'ncc-tab-active': editMode === 'preview' }"
              @click="editMode = 'preview'"
            >预览</text>
          </view>
          <view class="ncc-action-group">
            <text
              class="ncc-cancel-btn"
              :class="{ 'ncc-cancel-btn-disabled': isSaving }"
              @click="cancelEdit"
            >取消</text>
            <text
              class="ncc-confirm-btn"
              :class="{ 'ncc-confirm-btn-disabled': isSaving }"
              @click="saveEdit"
            >{{ isSaving ? '保存中...' : '确认' }}</text>
          </view>
        </view>
        <textarea
          v-if="editMode === 'code'"
          class="ncc-textarea"
          v-model="editContent"
          placeholder="笔记内容 (支持 Markdown)"
          :auto-height="false"
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
import { getNoteDetail, updateNote } from '@/api/note'
import { getSpaceGraph } from '@/api/space'
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
    nodeOptionLabels() {
      return this.nodeOptions.map(opt => opt.label)
    },
    selectedNodeIndex() {
      const idx = this.nodeOptions.findIndex(opt => opt.value === this.editNodeLabel)
      return idx >= 0 ? idx : 0
    },
    currentNodeLabel() {
      const opt = this.nodeOptions.find(o => o.value === this.editNodeLabel)
      return opt ? opt.label : '自由笔记'
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
    onNodePickerChange(e) {
      const idx = e.detail.value
      this.editNodeLabel = this.nodeOptions[idx]?.value || 'FREE'
    },

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
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
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
  flex-shrink: 0;
}

.ncc-header-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  filter: brightness(0) invert(1);
}

.ncc-status-success {
  filter: brightness(0) saturate(100%) invert(85%) sepia(27%) saturate(541%) hue-rotate(67deg) brightness(95%) contrast(87%);
}

.ncc-status-failed {
  filter: brightness(0) saturate(100%) invert(54%) sepia(98%) saturate(1834%) hue-rotate(331deg) brightness(99%) contrast(89%);
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

.ncc-title-text {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

/* Node picker */
.ncc-field-row {
  margin-top: 10px;
}

.ncc-field-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 4px;
}

.ncc-node-picker {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
}

.ncc-node-picker-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}

.ncc-node-picker-arrow {
  width: 12px;
  height: 12px;
  opacity: 0.4;
  filter: brightness(0) invert(1);
}

/* Tag row */
.ncc-tag-row {
  margin-top: 8px;
}

.ncc-node-tag {
  display: inline-block;
  font-size: 11px;
  color: rgba(129, 140, 248, 0.9);
  padding: 2px 8px;
  background: rgba(129, 140, 248, 0.12);
  border-radius: 4px;
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
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-top: 10px;
  line-height: 1.4;
}

/* Content area */
.ncc-content-area {
  position: relative;
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.ncc-edit-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  z-index: 1;
}

.ncc-edit-icon {
  width: 12px;
  height: 12px;
  opacity: 0.5;
  filter: brightness(0) invert(1);
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
  border-radius: 6px;
  box-sizing: border-box;
}

.ncc-edit-area {
  margin-top: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  overflow: hidden;
}

.ncc-edit-toolbar {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.ncc-tab-group {
  display: flex;
  flex-direction: row;
  gap: 2px;
}

.ncc-tab {
  padding: 3px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  border-radius: 4px;
}

.ncc-tab-active {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.ncc-action-group {
  display: flex;
  flex-direction: row;
  gap: 6px;
}

.ncc-cancel-btn {
  padding: 3px 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
}

.ncc-cancel-btn-disabled {
  opacity: 0.4;
}

.ncc-confirm-btn {
  padding: 3px 10px;
  font-size: 11px;
  color: #ffffff;
  background: rgba(59, 130, 246, 0.7);
  border-radius: 4px;
}

.ncc-confirm-btn-disabled {
  opacity: 0.5;
}

.ncc-textarea {
  width: 100%;
  min-height: 200px;
  padding: 10px 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(0, 0, 0, 0.2);
  border: none;
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
  padding: 6px 12px;
  font-size: 11px;
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.08);
  border-top: 1px solid rgba(239, 68, 68, 0.15);
}
</style>
