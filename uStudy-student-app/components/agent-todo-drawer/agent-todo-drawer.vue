<template>
  <view class="agent-todo-drawer" :class="[themeClass, { 'drawer-expanded': expanded }]">
    <view class="drawer-shell">
      <view class="drawer-header" @click="handleToggle">
        <view class="drawer-title-wrap">
          <text class="drawer-title">Agent Todo</text>
        </view>
        <view class="drawer-actions">
          <text class="drawer-count-text">{{ completedCount }}/{{ items.length }}</text>
          <image
            class="drawer-chevron"
            :class="{ 'drawer-chevron-expanded': expanded }"
            src="/static/icons/phosphor-icons/SVGs/regular/caret-down.svg"
            mode="aspectFit"
          />
        </view>
      </view>

      <view v-if="expanded" class="drawer-body">
        <view
          v-for="item in items"
          :key="item.task_id"
          class="drawer-item"
          :class="{ 'drawer-item-completed': item.status === 'completed' }"
        >
          <view class="drawer-item-icon-wrap">
            <view
              class="drawer-item-toggle"
              :class="{ 'drawer-item-toggle-loading': isItemLoading(item.task_id) }"
              @click.stop="handleToggleItem(item)"
            >
              <view v-if="isItemLoading(item.task_id)" class="drawer-item-spinner"></view>
              <svg
                v-else-if="item.status !== 'completed'"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="drawer-item-icon drawer-item-icon-pending"
              >
                <circle cx="12" cy="12" r="10" />
              </svg>
              <svg
                v-else
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="drawer-item-icon drawer-item-icon-completed"
              >
                <path d="M21.801 10A10 10 0 1 1 17 3.335" />
                <path d="m9 11 3 3L22 4" />
              </svg>
            </view>
          </view>
          <view class="drawer-item-content">
            <view class="drawer-item-head">
              <text class="drawer-item-id">{{ formatTodoIndex(item.task_id) }}</text>
              <text class="drawer-item-title">{{ item.title }}</text>
            </view>
            <text v-if="item.details" class="drawer-item-details">{{ item.details }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'AgentTodoDrawer',

  props: {
    themeMode: {
      type: String,
      default: 'dark'
    },
    items: {
      type: Array,
      default: () => []
    },
    expanded: {
      type: Boolean,
      default: false
    },
    loadingTaskIds: {
      type: Array,
      default: () => []
    }
  },

  emits: ['toggle', 'toggle-item'],

  computed: {
    themeClass() {
      return this.themeMode === 'light' ? 'theme-light' : 'theme-dark'
    },
    completedCount() {
      return this.items.filter(item => item?.status === 'completed').length
    }
  },

  methods: {
    handleToggle() {
      this.$emit('toggle')
    },
    isItemLoading(taskId) {
      return this.loadingTaskIds.includes(taskId)
    },
    handleToggleItem(item) {
      if (!item?.task_id || this.isItemLoading(item.task_id)) return
      this.$emit('toggle-item', {
        taskId: item.task_id,
        completed: item.status === 'completed'
      })
    },
    formatTodoIndex(taskId) {
      const match = String(taskId || '').match(/(\d+)$/)
      if (!match) return String(taskId || '')
      return String(parseInt(match[1], 10))
    }
  }
}
</script>

<style scoped>
.agent-todo-drawer {
  width: 100%;
  position: relative;
}

.drawer-shell {
  position: relative;
  border-radius: 34rpx 34rpx 30rpx 30rpx;
  padding: 12rpx 24rpx 42rpx;
  overflow: hidden;
  transition: box-shadow 220ms ease, transform 220ms ease, border-color 220ms ease;
}

.drawer-shell::before {
  content: '';
  position: absolute;
  left: 22rpx;
  right: 22rpx;
  top: 0;
  height: 2rpx;
  border-radius: 999rpx;
  opacity: 0.7;
}

.drawer-shell::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 72rpx;
  pointer-events: none;
}

.theme-dark .drawer-shell {
  background: linear-gradient(180deg, rgba(35, 37, 40, 0.98), rgba(24, 25, 27, 0.96));
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  box-shadow:
    0 18rpx 32rpx rgba(0, 0, 0, 0.18),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.04);
}

.theme-dark .drawer-shell::before {
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
}

.theme-dark .drawer-shell::after {
  background: linear-gradient(180deg, rgba(23, 24, 26, 0), rgba(18, 19, 21, 0.88));
}

.theme-light .drawer-shell {
  background: linear-gradient(180deg, rgba(251, 247, 239, 0.98), rgba(243, 236, 226, 0.98));
  border: 1rpx solid rgba(154, 126, 91, 0.12);
  box-shadow:
    0 14rpx 28rpx rgba(142, 120, 92, 0.08),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.72);
}

.theme-light .drawer-shell::before {
  background: linear-gradient(90deg, transparent, rgba(154, 126, 91, 0.12), transparent);
}

.theme-light .drawer-shell::after {
  background: linear-gradient(180deg, rgba(244, 237, 227, 0), rgba(240, 232, 220, 0.92));
}

.drawer-header {
  min-height: 72rpx;
  padding: 0 2rpx 8rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.drawer-title-wrap {
  min-width: 0;
}

.drawer-title {
  font-size: 27rpx;
  font-weight: 700;
  letter-spacing: 0.4rpx;
}

.theme-dark .drawer-title {
  color: #f2ede3;
}

.theme-light .drawer-title {
  color: #4e4030;
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-shrink: 0;
}

.drawer-count-text {
  font-size: 21rpx;
  font-weight: 600;
  line-height: 1;
}

.theme-dark .drawer-count-text {
  color: rgba(255, 240, 214, 0.76);
}

.theme-light .drawer-count-text {
  color: rgba(88, 69, 45, 0.74);
}

.drawer-chevron {
  width: 26rpx;
  height: 26rpx;
  transition: transform 220ms ease;
}

.theme-dark .drawer-chevron {
  filter: brightness(0) saturate(100%) invert(94%) sepia(14%) saturate(396%) hue-rotate(331deg) brightness(103%) contrast(93%);
}

.theme-light .drawer-chevron {
  filter: brightness(0) saturate(100%) invert(24%) sepia(15%) saturate(793%) hue-rotate(352deg) brightness(98%) contrast(87%);
}

.drawer-chevron-expanded {
  transform: rotate(180deg);
}

.drawer-body {
  display: flex;
  flex-direction: column;
  padding: 2rpx 0 0;
}

.drawer-item {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  padding: 18rpx 2rpx;
  transition: opacity 220ms ease;
  border-top: 1rpx solid transparent;
}

.theme-dark .drawer-item {
  border-top-color: rgba(255, 255, 255, 0.055);
}

.theme-light .drawer-item {
  border-top-color: rgba(154, 126, 91, 0.11);
}

.drawer-item-completed {
  opacity: 0.56;
}

.drawer-item-icon-wrap {
  width: 52rpx;
  height: 52rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: -2rpx;
  flex-shrink: 0;
}

.drawer-item-toggle {
  width: 52rpx;
  height: 52rpx;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 160ms ease, background 160ms ease;
}

.drawer-item-toggle:active {
  transform: scale(0.96);
}

.theme-dark .drawer-item-toggle {
  background: rgba(255, 255, 255, 0.03);
}

.theme-dark .drawer-item-toggle:active {
  background: rgba(255, 255, 255, 0.06);
}

.theme-light .drawer-item-toggle {
  background: rgba(154, 126, 91, 0.06);
}

.theme-light .drawer-item-toggle:active {
  background: rgba(154, 126, 91, 0.1);
}

.drawer-item-toggle-loading {
  pointer-events: none;
}

.drawer-item-spinner {
  width: 22rpx;
  height: 22rpx;
  border-radius: 50%;
  border: 3rpx solid transparent;
  animation: drawer-spin 0.7s linear infinite;
}

.theme-dark .drawer-item-spinner {
  border-color: rgba(240, 201, 104, 0.22);
  border-top-color: rgba(247, 208, 110, 0.95);
}

.theme-light .drawer-item-spinner {
  border-color: rgba(188, 135, 54, 0.18);
  border-top-color: rgba(195, 138, 50, 0.95);
}

.drawer-item-icon {
  width: 24rpx;
  height: 24rpx;
}

.theme-dark .drawer-item-icon-pending {
  color: rgba(240, 201, 104, 0.82);
}

.theme-light .drawer-item-icon-pending {
  color: rgba(188, 135, 54, 0.74);
}

.theme-dark .drawer-item-icon-completed {
  color: rgba(247, 208, 110, 0.98);
}

.theme-light .drawer-item-icon-completed {
  color: rgba(195, 138, 50, 0.96);
}

.drawer-item-content {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.drawer-item-head {
  display: flex;
  align-items: center;
  min-height: 36rpx;
  gap: 10rpx;
  flex-wrap: wrap;
}

.drawer-item-id {
  font-size: 20rpx;
  font-weight: 700;
  letter-spacing: 0.6rpx;
  line-height: 1.2;
  text-transform: uppercase;
}

.theme-dark .drawer-item-id {
  color: rgba(245, 208, 116, 0.92);
}

.theme-light .drawer-item-id {
  color: rgba(189, 133, 44, 0.92);
}

.drawer-item-title {
  font-size: 25rpx;
  line-height: 1.32;
  font-weight: 600;
  word-break: break-word;
}

.theme-dark .drawer-item-title {
  color: rgba(248, 245, 238, 0.94);
}

.theme-light .drawer-item-title {
  color: #4c3d2f;
}

.drawer-item-completed .drawer-item-title,
.drawer-item-completed .drawer-item-details {
  text-decoration: line-through;
}

.drawer-item-details {
  font-size: 22rpx;
  line-height: 1.48;
  word-break: break-word;
}

.theme-dark .drawer-item-details {
  color: rgba(214, 214, 214, 0.72);
}

.theme-light .drawer-item-details {
  color: rgba(95, 77, 55, 0.72);
}

.drawer-expanded .drawer-shell {
  transform: translateY(0);
}

@keyframes drawer-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
