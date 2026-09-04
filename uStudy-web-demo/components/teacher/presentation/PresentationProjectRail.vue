<template>
  <view class="project-rail">
    <view class="rail-header">
      <view>
        <text class="rail-eyebrow">数据结构</text>
        <text class="rail-title">课件项目</text>
      </view>
      <view class="new-button" :class="{ disabled: creating }" @tap="!creating && $emit('create')">
        <text>＋</text>
        <text>新建</text>
      </view>
    </view>

    <scroll-view scroll-y class="rail-scroll">
      <view v-if="loading && !projects.length" class="rail-empty">正在读取项目…</view>
      <view v-else-if="!projects.length" class="rail-empty">
        <text class="empty-title">还没有课件</text>
        <text class="empty-copy">新建项目后粘贴教案，助教会在隔离工作区内完成制作。</text>
      </view>
      <view v-else class="project-list">
        <view
          v-for="project in projects"
          :key="project.id"
          class="project-row"
          :class="{ selected: project.id === selectedProjectId }"
          @tap="$emit('select-project', project.id)"
        >
          <view class="project-marker"></view>
          <view class="project-copy">
            <text class="project-title">{{ project.title }}</text>
            <text class="project-meta">{{ projectMeta(project) }}</text>
          </view>
          <view v-if="isBusy(project.status)" class="status-pulse"></view>
        </view>
      </view>

      <view v-if="selectedProjectId" class="revision-section">
        <view class="section-heading">
          <text>版本</text>
          <text>{{ revisions.length }}</text>
        </view>
        <view v-if="!revisions.length" class="revision-empty">完成首次生成后会留下可恢复版本</view>
        <view
          v-for="revision in revisions"
          :key="revision.id"
          class="revision-row"
          :class="{ selected: revision.id === selectedRevisionId }"
          @tap="$emit('select-revision', revision.id)"
        >
          <view class="revision-index">{{ revisionLabel(revision) }}</view>
          <view class="revision-copy">
            <text class="revision-summary">{{ revision.summary || '课件生成完成' }}</text>
            <text class="revision-time">{{ formatTime(revision.createdAt) }} · {{ revision.slideCount || '—' }} 页</text>
          </view>
          <text v-if="revision.isPublished" class="published-dot">已发布</text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script>
export default {
  props: {
    projects: { type: Array, default: () => [] },
    revisions: { type: Array, default: () => [] },
    selectedProjectId: { type: String, default: '' },
    selectedRevisionId: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    creating: { type: Boolean, default: false }
  },
  emits: ['create', 'select-project', 'select-revision'],
  methods: {
    isBusy(status) {
      return ['queued', 'running', 'building', 'rendering'].includes(String(status || '').toLowerCase())
    },
    projectMeta(project) {
      if (this.isBusy(project.status)) return '正在生成'
      const time = this.formatTime(project.updatedAt || project.createdAt)
      return `${project.slideCount || '—'} 页${time ? ` · ${time}` : ''}`
    },
    revisionLabel(revision) {
      return revision.number ? `v${revision.number}` : `v${this.revisions.length - this.revisions.indexOf(revision)}`
    },
    formatTime(value) {
      if (!value) return ''
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return ''
      return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }
  }
}
</script>

<style scoped>
.project-rail { height: 100%; min-height: 0; display: flex; flex-direction: column; color: #fff; background: rgba(42,42,60,.42); backdrop-filter: blur(20px); }
.rail-header { height: 76px; box-sizing: border-box; padding: 16px 16px 14px 18px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,.07); }
.rail-eyebrow { display: block; color: rgba(255,255,255,.4); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; }
.rail-title { display: block; margin-top: 3px; font-size: 17px; font-weight: 650; }
.new-button { display: flex; align-items: center; gap: 4px; padding: 7px 10px; border-radius: 8px; background: #e7f0ff; color: #121722; font-size: 12px; font-weight: 650; cursor: pointer; transition: transform .16s ease, opacity .16s ease; }
.new-button:hover { transform: translateY(-1px); }
.new-button.disabled { opacity: .45; cursor: default; }
.rail-scroll { flex: 1; min-height: 0; }
.rail-empty { padding: 30px 18px; display: flex; flex-direction: column; gap: 8px; color: rgba(255,255,255,.42); font-size: 12px; line-height: 1.6; }
.empty-title { color: rgba(255,255,255,.8); font-size: 14px; font-weight: 600; }
.project-list { padding: 9px 8px 6px; }
.project-row { position: relative; display: flex; align-items: center; gap: 10px; min-height: 54px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background .16s ease; }
.project-row:hover { background: rgba(255,255,255,.045); }
.project-row.selected { background: rgba(96,165,250,.16); }
.project-marker { width: 3px; height: 24px; border-radius: 2px; background: rgba(255,255,255,.1); transition: background .16s ease; }
.project-row.selected .project-marker { background: #74a3ff; }
.project-copy, .revision-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.project-title, .revision-summary { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.project-title { color: rgba(255,255,255,.83); font-size: 13px; font-weight: 550; }
.project-meta, .revision-time { color: rgba(255,255,255,.34); font-size: 10px; }
.status-pulse { width: 7px; height: 7px; border-radius: 50%; background: #74a3ff; box-shadow: 0 0 0 0 rgba(116,163,255,.4); animation: pulse 1.8s infinite; }
.revision-section { margin: 10px 10px 0; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.07); }
.section-heading { padding: 0 8px 8px; display: flex; justify-content: space-between; color: rgba(255,255,255,.38); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.revision-empty { padding: 12px 8px; color: rgba(255,255,255,.28); font-size: 11px; line-height: 1.5; }
.revision-row { display: flex; align-items: center; gap: 9px; padding: 8px; border-radius: 8px; cursor: pointer; transition: background .16s ease; }
.revision-row:hover, .revision-row.selected { background: rgba(255,255,255,.045); }
.revision-index { width: 26px; color: rgba(255,255,255,.48); font-size: 11px; font-variant-numeric: tabular-nums; }
.revision-summary { font-size: 11px; color: rgba(255,255,255,.68); }
.published-dot { color: #8fcea9; font-size: 9px; white-space: nowrap; }
@keyframes pulse { 70% { box-shadow: 0 0 0 6px rgba(116,163,255,0); } 100% { box-shadow: 0 0 0 0 rgba(116,163,255,0); } }
</style>
