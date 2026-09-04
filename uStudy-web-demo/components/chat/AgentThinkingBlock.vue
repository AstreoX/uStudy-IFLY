<template>
  <view v-if="content || active" class="thinking-block" :class="{ 'thinking-active': active }">
    <view class="thinking-header" @tap="toggle">
      <view v-if="active" class="thinking-spinner"></view>
      <svg v-else class="thinking-icon" viewBox="0 0 256 256">
        <path d="M92 216h72M104 184h48M80 139c-16-14-24-32-24-53a72 72 0 0 1 144 0c0 21-8 39-24 53-10 9-16 20-16 33H96c0-13-6-24-16-33Z" fill="none" stroke="currentColor" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <text class="thinking-label">{{ label }}</text>
      <text class="thinking-chevron" :class="{ expanded }">⌄</text>
    </view>
    <view class="thinking-body" :class="{ collapsed: !expanded }">
      <text class="thinking-text">{{ content }}</text>
    </view>
  </view>
</template>

<script>
export default {
  name: 'AgentThinkingBlock',
  props: {
    content: { type: String, default: '' },
    active: { type: Boolean, default: false },
    duration: { type: Number, default: 0 }
  },
  data() {
    return { expanded: this.active }
  },
  computed: {
    label() {
      if (this.active) return '深度思考中...'
      return `已深度思考 ${Math.max(0, Number(this.duration) || 0)} 秒`
    }
  },
  watch: {
    active(next, previous) {
      if (next) this.expanded = true
      else if (previous) this.expanded = false
    }
  },
  methods: {
    toggle() {
      if (!this.content) return
      this.expanded = !this.expanded
    }
  }
}
</script>

<style scoped>
.thinking-block { width: 100%; overflow: hidden; color: rgba(255,255,255,.75); }
.thinking-header { min-height: 28px; display: flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }
.thinking-spinner { width: 12px; height: 12px; box-sizing: border-box; border: 2px solid rgba(168,85,247,.28); border-top-color: rgba(192,132,252,.9); border-radius: 50%; animation: thinking-spin .8s linear infinite; }
.thinking-icon { width: 14px; height: 14px; color: rgba(192,132,252,.74); }
.thinking-label { flex: 1; color: rgba(192,132,252,.9); font-size: 13px; }
.thinking-chevron { color: rgba(192,132,252,.58); font-size: 12px; transition: transform .2s ease; }
.thinking-chevron.expanded { transform: rotate(180deg); }
.thinking-body { max-height: 100000px; margin-top: 4px; padding: 2px 0 2px 14px; overflow: hidden; border-left: 2px solid rgba(168,85,247,.36); opacity: 1; transition: max-height .32s ease, opacity .2s ease, margin .2s ease; }
.thinking-body.collapsed { max-height: 0; margin-top: 0; opacity: 0; }
.thinking-text { display: block; color: rgba(255,255,255,.68); font-size: 12px; line-height: 1.75; white-space: pre-wrap; word-break: break-word; user-select: text; }
@keyframes thinking-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .thinking-spinner { animation-duration: 1.6s; } .thinking-body, .thinking-chevron { transition: none; } }
</style>
