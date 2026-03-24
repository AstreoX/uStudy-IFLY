<template>
  <view v-if="visible" class="u-input-modal-wrapper" :class="themeClass" @touchmove.stop.prevent>
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
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

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
    },
    themeMode: {
      type: String,
      default: ''
    }
  },

  data() {
    return {
      animationVisible: false,
      inputValue: '',
      errorMessage: '',
      localThemeMode: 'dark'
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
    },
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode || this.localThemeMode)}`
    }
  },

  watch: {
    visible: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.refreshThemeMode()
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

  created() {
    this.refreshThemeMode()
  },

  methods: {
    refreshThemeMode() {
      this.localThemeMode = getStoredThemeMode('dark')
    },

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
  --u-input-overlay: rgba(0, 0, 0, 0.6);
  --u-input-surface: rgba(20, 20, 30, 0.92);
  --u-input-surface-fallback: rgba(30, 30, 45, 0.98);
  --u-input-border: rgba(255, 255, 255, 0.15);
  --u-input-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.5);
  --u-input-highlight: rgba(255, 255, 255, 0.05);
  --u-input-title: #ffffff;
  --u-input-field-bg: rgba(255, 255, 255, 0.08);
  --u-input-field-border: rgba(255, 255, 255, 0.2);
  --u-input-field-text: #ffffff;
  --u-input-focus-border: rgba(0, 170, 255, 0.6);
  --u-input-focus-shadow: rgba(0, 170, 255, 0.15);
  --u-input-placeholder: rgba(255, 255, 255, 0.4);
  --u-input-counter: rgba(255, 255, 255, 0.4);
  --u-input-error: #EF4444;
  --u-input-divider: rgba(255, 255, 255, 0.1);
  --u-input-btn-active: rgba(255, 255, 255, 0.08);
  --u-input-cancel: rgba(255, 255, 255, 0.7);
  --u-input-confirm: #00AAFF;
  --u-input-confirm-disabled: rgba(0, 170, 255, 0.4);
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

.u-input-modal-wrapper.theme-light {
  --u-input-overlay: rgba(61, 46, 30, 0.22);
  --u-input-surface: rgba(255, 249, 241, 0.96);
  --u-input-surface-fallback: rgba(255, 249, 241, 0.99);
  --u-input-border: rgba(63, 53, 42, 0.12);
  --u-input-shadow: 0 16rpx 48rpx rgba(118, 101, 80, 0.18);
  --u-input-highlight: rgba(255, 255, 255, 0.78);
  --u-input-title: #1F1A16;
  --u-input-field-bg: rgba(255, 255, 255, 0.88);
  --u-input-field-border: rgba(63, 53, 42, 0.12);
  --u-input-field-text: #1F1A16;
  --u-input-focus-border: rgba(47, 110, 234, 0.46);
  --u-input-focus-shadow: rgba(47, 110, 234, 0.14);
  --u-input-placeholder: rgba(31, 26, 22, 0.36);
  --u-input-counter: rgba(31, 26, 22, 0.42);
  --u-input-error: #D14F4F;
  --u-input-divider: rgba(63, 53, 42, 0.1);
  --u-input-btn-active: rgba(63, 53, 42, 0.06);
  --u-input-cancel: rgba(31, 26, 22, 0.62);
  --u-input-confirm: #2F6EEA;
  --u-input-confirm-disabled: rgba(47, 110, 234, 0.38);
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
  background: var(--u-input-overlay);
}

.u-input-modal-container {
  position: relative;
  width: 600rpx;
  background: var(--u-input-surface);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid var(--u-input-border);
  border-radius: 24rpx;
  box-shadow:
    var(--u-input-shadow),
    0 0 0 1rpx var(--u-input-highlight) inset;
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
    background: var(--u-input-surface-fallback);
  }
}

.u-input-modal-title {
  padding: 40rpx 40rpx 24rpx;
  text-align: center;
}

.u-input-modal-title text {
  font-size: 36rpx;
  font-weight: 600;
  color: var(--u-input-title);
}

.u-input-modal-input-wrapper {
  margin: 0 32rpx 24rpx;
  position: relative;
}

.u-input-modal-input {
  width: 100%;
  background: var(--u-input-field-bg);
  border: 1rpx solid var(--u-input-field-border);
  border-radius: 16rpx;
  font-size: 32rpx;
  color: var(--u-input-field-text);
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
  border-color: var(--u-input-focus-border);
  box-shadow: 0 0 0 4rpx var(--u-input-focus-shadow);
}

.input-placeholder {
  color: var(--u-input-placeholder);
}

.input-counter {
  position: absolute;
  right: 24rpx;
  bottom: 24rpx;
}

.input-counter text {
  font-size: 24rpx;
  color: var(--u-input-counter);
}

.u-input-modal-error {
  margin: 0 32rpx 16rpx;
}

.u-input-modal-error text {
  font-size: 26rpx;
  color: var(--u-input-error);
}

.u-input-modal-buttons {
  display: flex;
  margin-top: 24rpx;
  border-top: 1rpx solid var(--u-input-divider);
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
  background: var(--u-input-btn-active);
}

.btn-cancel {
  color: var(--u-input-cancel);
  border-right: 1rpx solid var(--u-input-divider);
}

.btn-confirm {
  color: var(--u-input-confirm);
}

.btn-confirm.btn-disabled {
  color: var(--u-input-confirm-disabled);
}
</style>
