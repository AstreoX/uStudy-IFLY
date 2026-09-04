<template>
  <view class="teacher-space-selector" :class="{ disabled: selectorDisabled }">
    <text class="selector-label">课程空间</text>
    <picker
      class="selector-picker"
      :range="spaces"
      range-key="name"
      :value="selectedIndex"
      :disabled="selectorDisabled"
      @change="handleChange"
    >
      <view class="selector-control" :title="selectedSpace?.name || '暂无课程空间'">
        <view class="selector-dot" :style="{ background: selectedSpace?.color || '#60A5FA' }"></view>
        <text class="selector-name">{{ selectedSpace?.name || '暂无课程空间' }}</text>
        <svg v-if="spaces.length > 1" viewBox="0 0 256 256" class="selector-chevron" aria-hidden="true">
          <polyline points="48 96 128 176 208 96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="18"/>
        </svg>
      </view>
    </picker>
  </view>
</template>

<script>
export default {
  props: {
    spaces: { type: Array, default: () => [] },
    spaceId: { type: [String, Number], default: '' },
    disabled: { type: Boolean, default: false }
  },
  emits: ['change'],
  computed: {
    selectedIndex() {
      const index = this.spaces.findIndex(space => String(space.id) === String(this.spaceId))
      return index >= 0 ? index : 0
    },
    selectedSpace() {
      return this.spaces[this.selectedIndex] || null
    },
    selectorDisabled() {
      return this.disabled || this.spaces.length < 2
    }
  },
  methods: {
    handleChange(event) {
      const target = this.spaces[Number(event.detail.value)]
      if (!target || String(target.id) === String(this.spaceId)) return
      this.$emit('change', target)
    }
  }
}
</script>

<style scoped>
.teacher-space-selector {
  min-width: 190px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.selector-label {
  color: #64748b;
  font-size: 9px;
  font-weight: 650;
  letter-spacing: .1em;
}
.selector-picker { width: 100%; }
.selector-control {
  height: 36px;
  padding: 0 11px;
  display: flex;
  align-items: center;
  gap: 8px;
  box-sizing: border-box;
  color: #dbe7ff;
  background: rgba(15,23,42,.58);
  border: 1px solid rgba(148,163,184,.16);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color .16s ease, background .16s ease;
}
.selector-control:hover {
  border-color: rgba(96,165,250,.42);
  background: rgba(30,41,59,.64);
}
.selector-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  box-shadow: 0 0 9px rgba(96,165,250,.28);
}
.selector-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 550;
}
.selector-chevron {
  width: 13px;
  height: 13px;
  flex: 0 0 auto;
  color: #64748b;
}
.teacher-space-selector.disabled .selector-control {
  cursor: default;
}
@media (max-width: 720px) {
  .teacher-space-selector { min-width: 0; width: min(100%, 240px); }
}
</style>
