<template>
  <view class="home-page">
    <!-- Aurora Background -->
    <view class="aurora-bg">
      <view class="aurora-blob aurora-blob-1"></view>
      <view class="aurora-blob aurora-blob-2"></view>
      <view class="aurora-blob aurora-blob-3"></view>
    </view>

    <!-- Sidebar -->
    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @navigate="handleNavigate"
      @select-space="handleSelectSpace"
      @create-space="handleCreateSpace"
    />

    <!-- Main Content -->
    <view class="main-content">
      <!-- Header + Daily Quote Bar -->
      <DailyQuoteBar>
        <template #left>
          <text class="header-title">Home</text>
        </template>
        <template #right>
          <view class="header-actions">
            <view
              v-if="editMode"
              class="add-btn"
              @tap="showPicker = !showPicker"
            >
              <text class="add-btn-text">+</text>
            </view>
            <view
              class="tools-btn"
              :class="{ active: editMode }"
              @tap="toggleEditMode"
            >
              <template v-if="editMode">
                <text class="tools-btn-text">Done</text>
              </template>
              <template v-else>
                <image
                  class="tools-pencil-icon"
                  src="/static/icons/phosphor/regular/pencil-white.svg"
                  mode="aspectFit"
                />
                <text class="tools-btn-label">编辑</text>
              </template>
            </view>
          </view>
        </template>
      </DailyQuoteBar>

      <!-- Widget Picker Dropdown -->
      <view v-if="showPicker" class="picker-backdrop" @tap="showPicker = false"></view>
      <view v-if="showPicker" class="picker-panel" @tap.stop>
        <text class="picker-title">Add Widget</text>
        <view class="picker-list">
          <view
            v-for="item in catalog"
            :key="item.type + item.variant"
            class="picker-item"
            @tap="handleAddWidget(item)"
          >
            <text class="picker-icon">{{ item.icon }}</text>
            <view class="picker-item-info">
              <text class="picker-item-label">{{ item.label }}</text>
              <text class="picker-item-desc">{{ item.desc }}</text>
            </view>
            <text class="picker-item-size">{{ item.w }}&times;{{ item.h }}</text>
          </view>
        </view>
      </view>

      <!-- Widget Grid Area -->
      <view class="grid-area">
        <WidgetGrid
          :widgets="widgetStore.widgets"
          :editMode="editMode"
          @update:widgets="handleWidgetUpdate"
          @remove:widget="handleWidgetRemove"
          @resize:widget="handleWidgetResize"
        />
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import WidgetGrid from '@/components/widgets/WidgetGrid.vue'
import DailyQuoteBar from '@/components/widgets/DailyQuoteBar.vue'
import { useWidgetStore, WIDGET_CATALOG } from '@/store/widgets'

export default {
  components: {
    HomeSidebar,
    WidgetGrid,
    DailyQuoteBar
  },
  data() {
    return {
      sidebarCollapsed: false,
      selectedSpaceId: null,
      editMode: false,
      showPicker: false,
      widgetStore: useWidgetStore(),
      catalog: WIDGET_CATALOG
    }
  },
  methods: {
    toggleEditMode() {
      this.editMode = !this.editMode
      if (!this.editMode) {
        this.showPicker = false
      }
    },
    handleWidgetUpdate({ id, col, row }) {
      this.widgetStore.updateWidgetPosition(id, col, row)
    },
    handleWidgetRemove(id) {
      this.widgetStore.removeWidget(id)
    },
    handleWidgetResize({ id, w, h }) {
      this.widgetStore.updateWidgetSize(id, w, h)
    },
    handleAddWidget(catalogItem) {
      const added = this.widgetStore.addWidget(catalogItem)
      if (!added) {
        uni.showToast({ title: 'No space available', icon: 'none' })
        return
      }
      this.showPicker = false
    },
    handleNavigate(id) {
      const routes = {
        home: '/pages/index/index',
        direct: '/pages/index/index',
        setting: '/pages/index/index'
      }
      const url = routes[id]
      if (url) {
        uni.reLaunch({ url })
      }
    },
    handleSelectSpace(spaceId) {
      this.selectedSpaceId = spaceId
      uni.navigateTo({
        url: `/pages/study/study?spaceId=${spaceId}`
      })
    },
    handleCreateSpace() {
      uni.navigateTo({ url: '/pages/createSpace/createSpace' })
    }
  }
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: row;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: var(--color-bg);
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-1 {
  width: 1200px;
  height: 1200px;
  background: radial-gradient(circle, rgba(59,130,246,0.32) 0%, rgba(59,130,246,0.12) 45%, transparent 75%);
  top: -25%;
  left: -10%;
  filter: blur(90px);
  animation: aurora-drift-a 12s ease-in-out infinite;
}

.aurora-blob-2 {
  width: 850px;
  height: 850px;
  background: radial-gradient(circle, rgba(249,115,22,0.22) 0%, rgba(249,115,22,0.09) 45%, transparent 75%);
  top: 10%;
  right: -10%;
  filter: blur(70px);
  animation: aurora-drift-b 10s ease-in-out infinite;
}

.aurora-blob-3 {
  width: 950px;
  height: 950px;
  background: radial-gradient(circle, rgba(79,70,229,0.20) 0%, rgba(79,70,229,0.08) 45%, transparent 75%);
  bottom: -15%;
  left: 25%;
  filter: blur(90px);
  animation: aurora-drift-c 14s ease-in-out infinite;
}

@keyframes aurora-drift-a {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(50px, 35px) scale(1.06); }
  66% { transform: translate(-25px, 15px) scale(0.97); }
}

@keyframes aurora-drift-b {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-40px, 30px) scale(1.05); }
  66% { transform: translate(20px, -25px) scale(0.98); }
}

@keyframes aurora-drift-c {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -35px) scale(1.07); }
  66% { transform: translate(-20px, 20px) scale(0.96); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none !important; }
}

/* Main Content */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  z-index: 1;
  padding-top: 18px;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: #FFFFFF;
}

.header-actions {
  display: flex;
  flex-direction: row;
  gap: 8px;
}

/* Add Widget Button */
.add-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.add-btn:hover {
  background: rgba(59, 130, 246, 0.25);
}

.add-btn-text {
  font-size: 20px;
  font-weight: 400;
  color: var(--color-accent-blue);
  line-height: 1;
}

/* Tools Button */
.tools-btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.tools-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tools-btn.active {
  padding: 0 18px;
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}

.tools-btn-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-accent-blue);
}

/* Pencil Icon + Label */
.tools-pencil-icon {
  width: 16px;
  height: 16px;
  opacity: 0.8;
  transition: opacity 0.15s ease;
}

.tools-btn:hover .tools-pencil-icon {
  opacity: 1;
}

.tools-btn-label {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  margin-left: 5px;
  transition: color 0.15s ease;
}

.tools-btn:hover .tools-btn-label {
  color: rgba(255, 255, 255, 1);
}

/* Widget Picker */
.picker-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
}

.picker-panel {
  position: absolute;
  top: 56px;
  right: 28px;
  z-index: 51;
  width: 260px;
  background: rgba(20, 20, 35, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  padding: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.picker-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 8px;
  padding: 0 4px;
}

.picker-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.picker-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.picker-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.picker-icon {
  font-size: 20px;
  width: 32px;
  text-align: center;
  flex-shrink: 0;
}

.picker-item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.picker-item-label {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.3;
}

.picker-item-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1.3;
}

.picker-item-size {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  font-weight: 500;
  flex-shrink: 0;
}

.grid-area {
  flex: 1;
  padding: 14px 28px 28px;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.grid-area::-webkit-scrollbar {
  width: 6px;
}

.grid-area::-webkit-scrollbar-track {
  background: transparent;
}

.grid-area::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.grid-area::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
