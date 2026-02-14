<template>
  <view v-if="visible" class="u-input-modal-wrapper" @touchmove.stop.prevent>
    <!-- Overlay -->
    <view
      class="u-input-modal-overlay"
      :class="{ 'overlay-show': animationVisible }"
      @click="handleCancel"
    ></view>

    <!-- Modal Container -->
    <view class="u-input-modal-container" :class="{ 'modal-show': animationVisible }">
      <!-- Title -->
      <view class="u-input-modal-title">
        <text>{{ title }}</text>
      </view>

      <!-- Input Field -->
      <view class="u-input-modal-input-wrapper">
        <textarea
          v-if="multiline"
          class="u-input-modal-input"
          :value="inputValue"
          :placeholder="placeholder"
          :maxlength="maxLength"
          :focus="animationVisible"
          placeholder-class="input-placeholder"
          auto-height
          :show-confirm-bar="false"
          @input="onInput"
        />
        <input
          v-else
          class="u-input-modal-input"
          type="text"
          :value="inputValue"
          :placeholder="placeholder"
          :maxlength="maxLength"
          :focus="animationVisible"
          placeholder-class="input-placeholder"
          @input="onInput"
        />
        <view v-if="maxLength > 0" class="input-counter">
          <text>{{ inputValue.length }}/{{ maxLength }}</text>
        </view>
      </view>

      <!-- Error Message -->
      <view v-if="errorMessage" class="u-input-modal-error">
        <text>{{ errorMessage }}</text>
      </view>

      <!-- Buttons -->
      <view class="u-input-modal-buttons">
        <button class="u-input-modal-btn btn-cancel" @click="handleCancel">
          取消
        </button>
        <button
          class="u-input-modal-btn btn-confirm"
          :class="{ 'btn-disabled': !isValid }"
          @click="handleConfirm"
        >
          确定
        </button>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'UInputModal',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    title: {
      type: String,
      default: ''
    },
    placeholder: {
      type: String,
      default: '请输入内容'
    },
    value: {
      type: String,
      default: ''
    },
    maxLength: {
      type: Number,
      default: 0
    },
    minLength: {
      type: Number,
      default: 0
    },
    multiline: {
      type: Boolean,
      default: true
    }
  },

  data() {
    return {
      animationVisible: false,
      inputValue: '',
      errorMessage: ''
    }
  },

  computed: {
    isValid() {
      const len = this.inputValue.trim().length
      if (this.minLength > 0 && len < this.minLength) {
        return false
      }
      if (this.maxLength > 0 && len > this.maxLength) {
        return false
      }
      return len > 0
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.inputValue = this.value
          this.errorMessage = ''
          this.$nextTick(() => {
            setTimeout(() => {
              this.animationVisible = true
            }, 10)
          })
        } else {
          this.animationVisible = false
        }
      }
    },
    value: {
      immediate: true,
      handler(newVal) {
        this.inputValue = newVal
      }
    }
  },

  methods: {
    onInput(e) {
      this.inputValue = e.detail.value
      this.errorMessage = ''
      this.$emit('input', this.inputValue)
      this.$emit('update:value', this.inputValue)
    },

    handleCancel() {
      this.$emit('cancel')
      this.close()
    },

    handleConfirm() {
      const trimmedValue = this.inputValue.trim()

      // Validation
      if (trimmedValue.length === 0) {
        this.errorMessage = '内容不能为空'
        return
      }

      if (this.minLength > 0 && trimmedValue.length < this.minLength) {
        this.errorMessage = `至少输入 ${this.minLength} 个字符`
        return
      }

      this.$emit('confirm', trimmedValue)
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
.u-input-modal-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.u-input-modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  transition: background 200ms ease;
}

.u-input-modal-overlay.overlay-show {
  background: rgba(0, 0, 0, 0.6);
}

.u-input-modal-container {
  position: relative;
  width: 600rpx;
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  box-shadow:
    0 16rpx 48rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  overflow: hidden;
  transform: translateY(40rpx) scale(0.95);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.u-input-modal-container.modal-show {
  transform: translateY(0) scale(1);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .u-input-modal-container {
    background: rgba(30, 30, 45, 0.98);
  }
}

.u-input-modal-title {
  padding: 40rpx 40rpx 24rpx;
  text-align: center;
}

.u-input-modal-title text {
  font-size: 36rpx;
  font-weight: 600;
  color: #ffffff;
}

.u-input-modal-input-wrapper {
  margin: 0 32rpx 24rpx;
  position: relative;
}

.u-input-modal-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 16rpx;
  font-size: 32rpx;
  color: #ffffff;
  box-sizing: border-box;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

/* Single-line input styles */
input.u-input-modal-input {
  height: 96rpx;
  padding: 0 24rpx;
  padding-right: 100rpx;
}

/* Multi-line textarea styles */
textarea.u-input-modal-input {
  min-height: 280rpx;
  max-height: 480rpx;
  padding: 24rpx;
  padding-bottom: 60rpx;
  line-height: 1.5;
}

.u-input-modal-input:focus {
  border-color: rgba(0, 170, 255, 0.6);
  box-shadow: 0 0 0 4rpx rgba(0, 170, 255, 0.15);
}

.input-placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.input-counter {
  position: absolute;
  right: 24rpx;
  bottom: 24rpx;
}

.input-counter text {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.4);
}

.u-input-modal-error {
  margin: 0 32rpx 16rpx;
}

.u-input-modal-error text {
  font-size: 26rpx;
  color: #EF4444;
}

.u-input-modal-buttons {
  display: flex;
  margin-top: 24rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
}

.u-input-modal-btn {
  flex: 1;
  height: 100rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  font-weight: 500;
  background: transparent;
  border: none;
  border-radius: 0;
  transition: background 150ms ease;
}

.u-input-modal-btn::after {
  border: none;
}

.u-input-modal-btn:active {
  background: rgba(255, 255, 255, 0.08);
}

.btn-cancel {
  color: rgba(255, 255, 255, 0.7);
  border-right: 1rpx solid rgba(255, 255, 255, 0.1);
}

.btn-confirm {
  color: #00AAFF;
}

.btn-confirm.btn-disabled {
  color: rgba(0, 170, 255, 0.4);
}
</style>
