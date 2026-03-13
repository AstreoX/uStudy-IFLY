<template>
  <view v-if="visible" class="u-action-sheet-wrapper">
    <!-- Overlay -->
    <view
      class="u-action-sheet-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleCancel"
      @touchmove.stop.prevent
    ></view>

    <!-- Sheet Container -->
    <view class="u-action-sheet-container" :class="{ 'sheet-show': animationVisible }">
      <!-- Items -->
      <scroll-view class="u-action-sheet-items" scroll-y>
        <view
          v-for="(item, index) in items"
          :key="index"
          class="u-action-sheet-item"
          :class="{ 'item-danger': item.danger }"
          @click="handleSelect(index)"
        >
          <image
            v-if="item.icon"
            class="item-icon"
            :class="{ 'icon-danger': item.danger }"
            :src="getIconPath(item.icon)"
            mode="aspectFit"
          ></image>
          <text class="item-text">{{ item.text }}</text>
        </view>
      </scroll-view>

      <!-- Cancel Button -->
      <view class="u-action-sheet-cancel" @click="handleCancel">
        <text>{{ cancelText }}</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'UActionSheet',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    items: {
      type: Array,
      default: () => []
    },
    cancelText: {
      type: String,
      default: '取消'
    }
  },

  data() {
    return {
      animationVisible: false
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.$nextTick(() => {
            setTimeout(() => {
              this.animationVisible = true
            }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    }
  },

  methods: {
    getIconPath(iconName) {
      const iconMap = {
        image: '/static/icons/phosphor-icons/SVGs/regular/image.svg',
        camera: '/static/icons/phosphor-icons/SVGs/regular/camera.svg',
        'clock-counter-clockwise': '/static/icons/phosphor-icons/SVGs/regular/clock-counter-clockwise.svg',
        link: '/static/icons/phosphor-icons/SVGs/regular/link.svg',
        trash: '/static/icons/phosphor-icons/SVGs/regular/trash.svg',
        books: '/static/icons/phosphor-icons/SVGs/regular/books.svg',
        plus: '/static/icons/phosphor-icons/SVGs/regular/plus.svg'
      }
      return iconMap[iconName] || ''
    },

    handleSelect(index) {
      this.$emit('select', index)
      this.close()
    },

    handleCancel() {
      this.$emit('cancel')
      this.close()
    },

    close() {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close')
      }, 200)
    }
  }
}
</script>

<style scoped>
.u-action-sheet-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.u-action-sheet-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 200ms ease;
}

.u-action-sheet-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.u-action-sheet-container {
  position: relative;
  padding: 0 24rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  transform: translateY(100%);
  transition: transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-action-sheet-container.sheet-show {
  transform: translateY(0);
}

.u-action-sheet-items {
  max-height: 60vh;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow:
    0 -8rpx 32rpx rgba(0, 0, 0, 0.3),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-action-sheet-items {
    background: rgba(30, 30, 45, 0.98);
  }
}

.u-action-sheet-item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 112rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
  transition: background 150ms ease;
}

.u-action-sheet-item:last-child {
  border-bottom: none;
}

.u-action-sheet-item:active {
  background: rgba(255, 255, 255, 0.1);
}

.item-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 16rpx;
  filter: brightness(0) invert(1);
  opacity: 0.9;
}

.item-text {
  font-size: 32rpx;
  color: #ffffff;
  font-weight: 500;
}

/* Danger item styles */
.item-danger .item-text {
  color: #EF4444;
}

.icon-danger {
  filter: invert(47%) sepia(82%) saturate(2476%) hue-rotate(332deg) brightness(97%) contrast(92%) !important;
}

.u-action-sheet-cancel {
  margin-top: 16rpx;
  height: 112rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 -8rpx 32rpx rgba(0, 0, 0, 0.3),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  transition: background 150ms ease;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-action-sheet-cancel {
    background: rgba(30, 30, 45, 0.98);
  }
}

.u-action-sheet-cancel:active {
  background: rgba(255, 255, 255, 0.1);
}

.u-action-sheet-cancel text {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}
</style>
