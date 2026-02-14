<template>
  <view v-if="visible" class="image-source-picker-wrapper" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="picker-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleClose"
    ></view>

    <!-- Sheet Container -->
    <view class="picker-container" :class="{ 'container-show': animationVisible }">
      <!-- Options -->
      <view class="picker-options">
        <view class="picker-option" @click="handleCamera">
          <image
            class="option-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/camera.svg"
            mode="aspectFit"
          ></image>
          <text class="option-text">拍照</text>
        </view>
        <view class="option-divider"></view>
        <view class="picker-option" @click="handleAlbum">
          <image
            class="option-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/images.svg"
            mode="aspectFit"
          ></image>
          <text class="option-text">从相册选择</text>
        </view>
      </view>

      <!-- Cancel Button -->
      <view class="picker-cancel" @click="handleClose">
        <text>取消</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ImageSourcePicker',
  props: {
    visible: {
      type: Boolean,
      default: false
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
    handleCamera() {
      this.close(() => {
        this.$emit('camera')
      })
    },

    handleAlbum() {
      this.close(() => {
        this.$emit('album')
      })
    },

    handleClose() {
      this.close(() => {
        this.$emit('close')
      })
    },

    close(callback) {
      this.animationVisible = false
      setTimeout(() => {
        if (callback) callback()
      }, 200)
    }
  }
}
</script>

<style scoped>
.image-source-picker-wrapper {
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

.picker-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 200ms ease;
}

.picker-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.picker-container {
  position: relative;
  padding: 0 24rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  transform: translateY(100%);
  transition: transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.picker-container.container-show {
  transform: translateY(0);
}

.picker-options {
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 28rpx;
  overflow: hidden;
  box-shadow:
    0 -8rpx 32rpx rgba(0, 0, 0, 0.4),
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08);
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .picker-options {
    background: rgba(30, 30, 45, 0.98);
  }
}

.picker-option {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 112rpx;
  transition: background 150ms ease;
}

.picker-option:active {
  background: rgba(255, 255, 255, 0.1);
}

.option-divider {
  height: 1rpx;
  background: rgba(255, 255, 255, 0.08);
  margin: 0 32rpx;
}

.option-icon {
  width: 44rpx;
  height: 44rpx;
  margin-right: 20rpx;
  filter: brightness(0) invert(1);
  opacity: 0.9;
}

.option-text {
  font-size: 32rpx;
  color: #ffffff;
  font-weight: 500;
}

.picker-cancel {
  margin-top: 16rpx;
  height: 112rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  backdrop-filter: blur(40px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 -8rpx 32rpx rgba(0, 0, 0, 0.4),
    inset 0 1rpx 2rpx rgba(255, 255, 255, 0.08);
  transition: background 150ms ease;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .picker-cancel {
    background: rgba(30, 30, 45, 0.98);
  }
}

.picker-cancel:active {
  background: rgba(255, 255, 255, 0.1);
}

.picker-cancel text {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}
</style>
