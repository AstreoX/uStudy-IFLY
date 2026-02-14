<template>
  <view v-if="visible" class="preknowledge-card-wrapper">
    <view
      class="preknowledge-card"
      :class="{ 'card-show': animationVisible }"
    >
      <!-- 头部 -->
      <view class="card-header">
        <text class="card-title">前置知识</text>
        <view class="card-close" @click="handleClose">
          <image
            class="card-close-icon"
            src="/static/icons/phosphor-icons/SVGs/regular/x.svg"
            mode="aspectFit"
          />
        </view>
      </view>

      <!-- Canvas 绘制区域 -->
      <view class="card-content">
        <canvas
          v-if="hasData"
          :canvas-id="canvasId"
          class="knowledge-canvas"
          :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
        />
        <view v-else class="loading-state">
          <view class="loading-dots">
            <view class="dot"></view>
            <view class="dot"></view>
            <view class="dot"></view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
// 掌握度颜色渐变端点 (0-100 分段插值)
const MASTERY_COLOR_START = { r: 255, g: 50, b: 66 }   // #FF3242 (mastery=0, 珊瑚红)
const MASTERY_COLOR_MID = { r: 255, g: 217, b: 61 }    // #FFD93D (mastery=50, 浅黄色)
const MASTERY_COLOR_END = { r: 73, g: 255, b: 170 }    // #49FFAA (mastery=100, 薄荷绿)

/**
 * 根据掌握度 (0-100) 计算分段渐变 RGB 值
 */
function interpolateMasteryRGB(mastery) {
  const clampedMastery = Math.max(0, Math.min(100, mastery ?? 0))

  let r, g, b

  if (clampedMastery <= 50) {
    const t = clampedMastery / 50
    r = Math.round(MASTERY_COLOR_START.r + (MASTERY_COLOR_MID.r - MASTERY_COLOR_START.r) * t)
    g = Math.round(MASTERY_COLOR_START.g + (MASTERY_COLOR_MID.g - MASTERY_COLOR_START.g) * t)
    b = Math.round(MASTERY_COLOR_START.b + (MASTERY_COLOR_MID.b - MASTERY_COLOR_START.b) * t)
  } else {
    const t = (clampedMastery - 50) / 50
    r = Math.round(MASTERY_COLOR_MID.r + (MASTERY_COLOR_END.r - MASTERY_COLOR_MID.r) * t)
    g = Math.round(MASTERY_COLOR_MID.g + (MASTERY_COLOR_END.g - MASTERY_COLOR_MID.g) * t)
    b = Math.round(MASTERY_COLOR_MID.b + (MASTERY_COLOR_END.b - MASTERY_COLOR_MID.b) * t)
  }

  return { r, g, b }
}

/**
 * 根据掌握度计算颜色 (Hex)
 */
function getMasteryColor(mastery) {
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

/**
 * 根据掌握度计算发光颜色 (RGBA)
 */
function getMasteryGlowColor(mastery, opacity = 0.5) {
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}

export default {
  name: 'PreKnowledgeCard',

  props: {
    visible: {
      type: Boolean,
      default: false
    },
    mainNode: {
      type: Object,
      default: null
      // { id, label, mastery }
    },
    childNodes: {
      type: Array,
      default: () => []
      // [{ id, label, mastery }, ...]
    },
    highlightedLabels: {
      type: Array,
      default: () => []
    }
  },

  emits: ['close'],

  data() {
    return {
      animationVisible: false,
      ctx: null,
      canvasWidth: 300,
      canvasHeight: 150,
      isDestroyed: false,
      highlightAnimationTimer: null,
      highlightPhase: 0
    }
  },

  computed: {
    canvasId() {
      return `preknowledge_canvas_${Date.now()}`
    },

    hasData() {
      return this.mainNode != null
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
              this.initCanvas()
            }, 10)
          })
        } else {
          this.animationVisible = false
          this.stopHighlightAnimation()
        }
      }
    },

    mainNode: {
      handler() {
        if (this.visible && this.ctx) {
          this.calculateCanvasSize()
          this.$nextTick(() => {
            this.draw()
          })
        }
      },
      deep: true
    },

    childNodes: {
      handler() {
        if (this.visible && this.ctx) {
          this.calculateCanvasSize()
          this.$nextTick(() => {
            this.draw()
          })
        }
      },
      deep: true
    },

    highlightedLabels: {
      handler() {
        if (this.visible && this.ctx) {
          this.draw()
          this.startHighlightAnimation()
        }
      },
      deep: true
    }
  },

  mounted() {
    this.calculateCanvasSize()
  },

  beforeDestroy() {
    this.isDestroyed = true
    this.stopHighlightAnimation()
    this.ctx = null
  },

  methods: {
    handleClose() {
      this.animationVisible = false
      setTimeout(() => {
        this.$emit('close')
      }, 200)
    },

    calculateCanvasSize() {
      // 根据子节点数量计算画布高度
      const childCount = Math.max(1, this.childNodes.length)
      const rowHeight = 50  // 每个子节点行高
      const padding = 40    // 上下 padding

      this.canvasHeight = Math.min(280, childCount * rowHeight + padding)
      this.canvasWidth = 320
    },

    initCanvas(retryCount = 0) {
      if (this.isDestroyed) return

      const maxRetries = 5
      this.ctx = uni.createCanvasContext(this.canvasId, this)

      if (!this.ctx) {
        if (retryCount < maxRetries) {
          setTimeout(() => this.initCanvas(retryCount + 1), 100)
        }
        return
      }

      this.draw()
    },

    draw() {
      if (!this.ctx || !this.hasData) return

      const ctx = this.ctx
      const width = this.canvasWidth
      const height = this.canvasHeight

      // 清空画布
      ctx.clearRect(0, 0, width, height)

      // 布局计算
      const mainNodeX = width * 0.75  // 主节点在右侧 75% 位置
      const mainNodeY = height / 2
      const mainRadius = 16

      const childNodeX = width * 0.25  // 子节点在左侧 25% 位置
      const childCount = this.childNodes.length
      const childRadius = 10
      const childSpacing = Math.min(45, (height - 40) / Math.max(1, childCount))
      const childStartY = height / 2 - (childCount - 1) * childSpacing / 2

      // 绘制连线
      this.childNodes.forEach((child, index) => {
        const childY = childStartY + index * childSpacing
        this.drawEdge(ctx, childNodeX, childY, mainNodeX, mainNodeY)
      })

      // 绘制子节点（前置知识）
      this.childNodes.forEach((child, index) => {
        const childY = childStartY + index * childSpacing
        const isHighlighted = this.highlightedLabels.includes(child.label)
        this.drawNode(ctx, childNodeX, childY, childRadius, child, isHighlighted, false)
      })

      // 绘制主节点
      const mainHighlighted = this.highlightedLabels.includes(this.mainNode.label)
      this.drawNode(ctx, mainNodeX, mainNodeY, mainRadius, this.mainNode, mainHighlighted, true)

      ctx.draw()
    },

    drawEdge(ctx, x1, y1, x2, y2) {
      ctx.beginPath()
      ctx.setStrokeStyle('rgba(255, 255, 255, 0.2)')
      ctx.setLineWidth(1.5)

      // 使用贝塞尔曲线绘制平滑连线
      const controlX = (x1 + x2) / 2
      ctx.moveTo(x1, y1)
      ctx.bezierCurveTo(controlX, y1, controlX, y2, x2, y2)
      ctx.stroke()
    },

    drawNode(ctx, x, y, radius, node, isHighlighted, isMain) {
      const isUnmastered = node.mastery == null
      const glowSize = isHighlighted ? 12 + Math.sin(this.highlightPhase) * 4 : 8
      const outlineSize = isMain ? 4 : 2

      if (isUnmastered) {
        const grayColor = '#6B7280'
        const glowColor = isHighlighted ? 'rgba(96, 165, 250, 0.6)' : 'rgba(107, 114, 128, 0.4)'
        const outlineColor = isHighlighted ? 'rgba(96, 165, 250, 0.3)' : 'rgba(107, 114, 128, 0.2)'

        // 发光效果
        ctx.setShadow(0, 0, glowSize, glowColor)

        // 外圈
        ctx.beginPath()
        ctx.arc(x, y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        // 主圆
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(grayColor)
        ctx.fill()
      } else {
        const color = getMasteryColor(node.mastery)
        const glowColor = isHighlighted
          ? 'rgba(96, 165, 250, 0.6)'
          : getMasteryGlowColor(node.mastery, 0.4)
        const outlineColor = isHighlighted
          ? 'rgba(96, 165, 250, 0.3)'
          : getMasteryGlowColor(node.mastery, 0.2)

        // 发光效果
        ctx.setShadow(0, 0, glowSize, glowColor)

        // 外圈
        ctx.beginPath()
        ctx.arc(x, y, radius + outlineSize, 0, Math.PI * 2)
        ctx.setFillStyle(outlineColor)
        ctx.fill()

        // 主圆
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.setFillStyle(color)
        ctx.fill()
      }

      // 重置阴影
      ctx.setShadow(0, 0, 0, 'transparent')

      // 绘制标签
      this.drawLabel(ctx, x, y, radius, node.label, isHighlighted, isMain)
    },

    drawLabel(ctx, x, y, radius, label, isHighlighted, isMain) {
      const fontSize = isMain ? 12 : 10
      const maxWidth = isMain ? 80 : 70
      const labelY = y + radius + 12

      // 截断标签
      let displayLabel = label
      if (label.length > 8) {
        displayLabel = label.slice(0, 7) + '...'
      }

      ctx.setFontSize(fontSize)
      ctx.setFillStyle(isHighlighted ? '#60A5FA' : 'rgba(255, 255, 255, 0.85)')

      if (typeof ctx.setTextAlign === 'function') {
        ctx.setTextAlign('center')
      }
      if (typeof ctx.setTextBaseline === 'function') {
        ctx.setTextBaseline('top')
      }

      // 文字阴影
      if (typeof ctx.setShadow === 'function') {
        ctx.setShadow(0, 1, 2, 'rgba(0, 0, 0, 0.5)')
      }

      ctx.fillText(displayLabel, x, labelY)

      // 重置阴影
      if (typeof ctx.setShadow === 'function') {
        ctx.setShadow(0, 0, 0, 'transparent')
      }
    },

    startHighlightAnimation() {
      if (this.highlightAnimationTimer) return
      if (this.highlightedLabels.length === 0) return

      this.highlightAnimationTimer = setInterval(() => {
        this.highlightPhase += 0.2
        if (this.ctx && this.hasData) {
          this.draw()
        }
      }, 50)
    },

    stopHighlightAnimation() {
      if (this.highlightAnimationTimer) {
        clearInterval(this.highlightAnimationTimer)
        this.highlightAnimationTimer = null
      }
      this.highlightPhase = 0
    }
  }
}
</script>

<style scoped>
.preknowledge-card-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 150;
  padding-top: calc(var(--status-bar-height, 44px) + 88rpx + 20rpx);
  padding-left: 24rpx;
  padding-right: 24rpx;
  pointer-events: none;
}

.preknowledge-card {
  background: rgba(20, 20, 30, 0.92);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 24rpx;
  box-shadow:
    0 16rpx 48rpx rgba(0, 0, 0, 0.5),
    0 0 0 1rpx rgba(255, 255, 255, 0.05) inset;
  overflow: hidden;
  pointer-events: auto;

  /* 进入动画 */
  transform: translateY(-40rpx);
  opacity: 0;
  transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.preknowledge-card.card-show {
  transform: translateY(0);
  opacity: 1;
}

@supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .preknowledge-card {
    background: rgba(30, 30, 45, 0.98);
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 28rpx 16rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}

.card-title {
  font-size: 28rpx;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.card-close {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 150ms ease;
}

.card-close:active {
  background: rgba(255, 255, 255, 0.1);
}

.card-close-icon {
  width: 32rpx;
  height: 32rpx;
  opacity: 0.6;
}

.card-content {
  padding: 16rpx 20rpx 20rpx;
  display: flex;
  justify-content: center;
  align-items: center;
}

.knowledge-canvas {
  display: block;
}

.loading-state {
  padding: 60rpx 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.loading-dots {
  display: flex;
  gap: 12rpx;
}

.dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  animation: loading-bounce 1.4s ease-in-out infinite;
}

.dot:nth-child(1) {
  animation-delay: 0s;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes loading-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-8rpx);
    opacity: 1;
  }
}
</style>
