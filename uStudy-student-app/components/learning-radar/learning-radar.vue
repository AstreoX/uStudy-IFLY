<template>
  <view class="radar-container" :class="themeClass">
    <view class="radar-canvas-wrapper" :style="{ width: canvasSize + 'px', height: canvasSize + 'px' }">
      <canvas
        :id="canvasId"
        :canvas-id="canvasId"
        class="radar-canvas"
        :style="{ width: canvasSize + 'px', height: canvasSize + 'px' }"
      />
      <!-- Transparent tap targets over each label -->
      <view
        v-for="anchor in labelAnchors"
        :key="anchor.index"
        class="label-tap-target"
        :style="tapTargetStyle(anchor)"
        @click.stop="onLabelTap(anchor)"
      />
    </view>
    <view class="radar-legend">
      <view class="legend-item">
        <view class="legend-dot legend-dot--current" />
        <text class="legend-text">本周</text>
      </view>
      <view v-if="lastWeekValues" class="legend-item">
        <view class="legend-dot legend-dot--last" />
        <text class="legend-text">上周</text>
      </view>
    </view>
  </view>
</template>

<script>
import { normalizeThemeMode } from '@/utils/themeMode'

const DIMENSIONS = ['连续性', '专注度', '深入程度', '理解程度', '知识结构', '复习情况']
const CURRENT_DEFAULTS = [0, 0, 0, 0, 0, 0]
const GRID_LEVELS = [20, 40, 60, 80, 100]

const TAP_TARGET_SIZE = 40

const DARK_COLORS = {
  grid: 'rgba(255, 255, 255, 0.08)',
  axis: 'rgba(255, 255, 255, 0.06)',
  current: {
    fill: 'rgba(52, 211, 153, 0.15)',
    stroke: 'rgba(52, 211, 153, 0.65)',
    score: 'rgba(52, 211, 153, 0.9)'
  },
  lastWeek: {
    fill: 'rgba(251, 191, 36, 0.10)',
    stroke: 'rgba(251, 191, 36, 0.40)'
  },
  label: 'rgba(255, 255, 255, 0.65)'
}

const LIGHT_COLORS = {
  grid: 'rgba(63, 53, 42, 0.12)',
  axis: 'rgba(63, 53, 42, 0.1)',
  current: {
    fill: 'rgba(47, 143, 98, 0.12)',
    stroke: 'rgba(47, 143, 98, 0.72)',
    score: 'rgba(47, 143, 98, 0.9)'
  },
  lastWeek: {
    fill: 'rgba(192, 122, 24, 0.08)',
    stroke: 'rgba(192, 122, 24, 0.48)'
  },
  label: 'rgba(31, 26, 22, 0.62)'
}

export default {
  name: 'LearningRadar',

  props: {
    themeMode: {
      type: String,
      default: 'dark'
    },
    currentValues: {
      type: Array,
      default: () => CURRENT_DEFAULTS
    },
    lastWeekValues: {
      type: Array,
      default: () => null
    },
    labels: {
      type: Array,
      default: () => DIMENSIONS
    }
  },

  computed: {
    themeClass() {
      return `theme-${normalizeThemeMode(this.themeMode)}`
    },

    themeColors() {
      return normalizeThemeMode(this.themeMode) === 'light' ? LIGHT_COLORS : DARK_COLORS
    }
  },

  data() {
    return {
      canvasId: `learningRadar_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      ctx: null,
      canvasSize: 0,
      isDestroyed: false,
      _initRetryTimer: null,
      labelAnchors: []
    }
  },

  watch: {
    currentValues: {
      handler() {
        this.drawRadar()
      },
      deep: true
    },
    lastWeekValues: {
      handler() {
        this.drawRadar()
      },
      deep: true
    },
    themeMode() {
      this.drawRadar()
    }
  },

  mounted() {
    this.calculateSize()
    // Canvas DOM needs extra time to be ready inside scroll-view
    setTimeout(() => {
      this.initCanvas()
    }, 300)
  },

  beforeDestroy() {
    this.isDestroyed = true
    if (this._initRetryTimer) {
      clearTimeout(this._initRetryTimer)
      this._initRetryTimer = null
    }
    this.ctx = null
  },

  methods: {
    calculateSize() {
      const systemInfo = uni.getSystemInfoSync()
      this.canvasSize = Math.min(Math.floor(systemInfo.windowWidth * 0.52), 240)
    },

    tapTargetStyle(anchor) {
      const half = TAP_TARGET_SIZE / 2
      return {
        left: (anchor.x - half) + 'px',
        top: (anchor.y - half) + 'px',
        width: TAP_TARGET_SIZE + 'px',
        height: TAP_TARGET_SIZE + 'px'
      }
    },

    onLabelTap(anchor) {
      this.$emit('dimension-click', { index: anchor.index, label: anchor.label })
    },

    initCanvas(retryCount = 0) {
      if (this.isDestroyed) return

      try {
        this.ctx = uni.createCanvasContext(this.canvasId, this)
      } catch (_e) {
        this.ctx = null
      }

      if (!this.ctx) {
        if (retryCount < 8) {
          this._initRetryTimer = setTimeout(() => this.initCanvas(retryCount + 1), 200)
        }
        return
      }

      // Delay first draw to ensure canvas element is fully ready
      setTimeout(() => {
        if (!this.isDestroyed) this.drawRadar()
      }, 100)
    },

    drawRadar() {
      if (!this.ctx || this.isDestroyed) return

      const ctx = this.ctx
      const colors = this.themeColors
      const size = this.canvasSize
      const cx = size / 2
      const cy = size / 2
      const maxRadius = size * 0.25
      const sides = this.labels.length

      try {
        ctx.clearRect(0, 0, size, size)

        this.drawHexGridLines(ctx, cx, cy, maxRadius, sides, colors)
        this.drawAxisLines(ctx, cx, cy, maxRadius, sides, colors)
        if (this.lastWeekValues) {
          this.drawDataPolygon(ctx, cx, cy, maxRadius, sides, this.lastWeekValues, colors.lastWeek, false)
        }
        this.drawDataPolygon(ctx, cx, cy, maxRadius, sides, this.currentValues, colors.current, true)
        this.drawLabels(ctx, cx, cy, maxRadius, sides, colors)
      } catch (_e) {
        // Ensure draw is still called even if drawing operations fail
      }

      ctx.draw()
    },

    getHexPoint(cx, cy, radius, index, total) {
      const angle = (Math.PI * 2 / total) * index - Math.PI / 2
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle)
      }
    },

    drawHexGridLines(ctx, cx, cy, maxRadius, sides, colors) {
      GRID_LEVELS.forEach(level => {
        const radius = (level / 100) * maxRadius

        ctx.beginPath()
        for (let i = 0; i <= sides; i++) {
          const point = this.getHexPoint(cx, cy, radius, i % sides, sides)
          if (i === 0) {
            ctx.moveTo(point.x, point.y)
          } else {
            ctx.lineTo(point.x, point.y)
          }
        }
        ctx.closePath()
        ctx.setStrokeStyle(colors.grid)
        ctx.setLineWidth(1)
        ctx.stroke()
      })
    },

    drawAxisLines(ctx, cx, cy, maxRadius, sides, colors) {
      for (let i = 0; i < sides; i++) {
        const point = this.getHexPoint(cx, cy, maxRadius, i, sides)

        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(point.x, point.y)
        ctx.setStrokeStyle(colors.axis)
        ctx.setLineWidth(1)
        ctx.stroke()
      }
    },

    normalizeValues(values, sides) {
      const arr = Array.isArray(values) ? values : []
      if (arr.length >= sides) return arr.slice(0, sides)
      return [...arr, ...Array(sides - arr.length).fill(0)]
    },

    trySetLineDash(ctx, pattern) {
      try {
        if (typeof ctx.setLineDash === 'function') {
          ctx.setLineDash(pattern)
        }
      } catch (_e) {
        // setLineDash not supported on this platform
      }
    },

    drawPolygonPath(ctx, points) {
      ctx.beginPath()
      for (let i = 0; i < points.length; i++) {
        if (i === 0) {
          ctx.moveTo(points[i].x, points[i].y)
        } else {
          ctx.lineTo(points[i].x, points[i].y)
        }
      }
      ctx.closePath()
    },

    drawDataPolygon(ctx, cx, cy, maxRadius, sides, values, colors, isCurrentWeek) {
      const dataValues = this.normalizeValues(values, sides)

      const points = dataValues.map((val, i) => {
        const clamped = Math.min(100, Math.max(0, Number(val) || 0))
        const radius = (clamped / 100) * maxRadius
        return this.getHexPoint(cx, cy, radius, i, sides)
      })

      // Fill
      this.drawPolygonPath(ctx, points)
      ctx.setFillStyle(colors.fill)
      ctx.fill()

      // Stroke
      this.drawPolygonPath(ctx, points)

      if (!isCurrentWeek) {
        this.trySetLineDash(ctx, [4, 4])
      }

      ctx.setStrokeStyle(colors.stroke)
      ctx.setLineWidth(isCurrentWeek ? 2 : 1.5)
      ctx.stroke()

      if (!isCurrentWeek) {
        this.trySetLineDash(ctx, [])
      }

    },

    drawLabels(ctx, cx, cy, maxRadius, sides, colors) {
      const values = this.normalizeValues(this.currentValues, sides)
      const scoreFontSize = Math.max(10, Math.min(12, this.canvasSize / 16))
      const labelFontSize = Math.max(9, Math.min(11, this.canvasSize / 18))
      const anchorRadius = maxRadius + 12
      const gap = 1

      const anchors = []

      const setHAlign = (point) => {
        if (typeof ctx.setTextAlign === 'function') {
          if (Math.abs(point.x - cx) < 2) ctx.setTextAlign('center')
          else if (point.x < cx) ctx.setTextAlign('right')
          else ctx.setTextAlign('left')
        }
      }

      this.labels.forEach((label, i) => {
        const point = this.getHexPoint(cx, cy, anchorRadius, i, sides)
        anchors.push({ x: point.x, y: point.y, index: i, label })
        setHAlign(point)

        // Score on top
        ctx.setFontSize(scoreFontSize)
        ctx.setFillStyle(colors.current.score)
        if (typeof ctx.setTextBaseline === 'function') ctx.setTextBaseline('bottom')
        ctx.fillText(String(Math.round(values[i])), point.x, point.y - gap)

        // Label below
        ctx.setFontSize(labelFontSize)
        ctx.setFillStyle(colors.label)
        if (typeof ctx.setTextBaseline === 'function') ctx.setTextBaseline('top')
        ctx.fillText(label, point.x, point.y + gap)
      })

      this.labelAnchors = anchors
    }
  }
}
</script>

<style scoped>
.radar-container {
  --radar-legend-text: rgba(255, 255, 255, 0.6);
  --radar-dot-current: #34D399;
  --radar-dot-current-shadow: rgba(52, 211, 153, 0.5);
  --radar-dot-last: #FBBF24;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 12rpx 0;
}

.radar-container.theme-light {
  --radar-legend-text: rgba(31, 26, 22, 0.58);
  --radar-dot-current: #2F8F62;
  --radar-dot-current-shadow: rgba(47, 143, 98, 0.28);
  --radar-dot-last: #C07A18;
}

.radar-canvas-wrapper {
  position: relative;
}

.radar-canvas {
  display: block;
}

.label-tap-target {
  position: absolute;
  z-index: 1;
  /* background: rgba(255,0,0,0.15); */ /* uncomment to debug hit areas */
}

.radar-legend {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  margin-top: 4rpx;
}

.legend-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6rpx;
}

.legend-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
}

.legend-dot--current {
  background-color: var(--radar-dot-current);
  box-shadow: 0 0 6rpx var(--radar-dot-current-shadow);
}

.legend-dot--last {
  background-color: var(--radar-dot-last);
  opacity: 0.7;
}

.legend-text {
  font-size: 18rpx;
  color: var(--radar-legend-text);
}
</style>
