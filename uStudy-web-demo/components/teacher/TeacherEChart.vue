<template>
  <view class="chart-shell" :style="shellStyle">
    <view v-if="loading" class="chart-state"><view class="chart-loader"></view><text>图表加载中…</text></view>
    <view v-else-if="empty" class="chart-state"><text>{{ emptyText }}</text></view>
    <view v-show="!loading && !empty" ref="chartRoot" class="chart-root"></view>
  </view>
</template>

<script>
import echarts from '@/utils/teacher-echarts'

// ECharts, ResizeObserver and animation handles own mutable browser state. Keep
// them outside Vue's component data so Vue never proxies or traverses them.
const chartInstances = new WeakMap()
const resizeObservers = new WeakMap()
const resizeHandlers = new WeakMap()
const pendingFrames = new WeakMap()
const renderVersions = new WeakMap()
const unmountedComponents = new WeakSet()

function cancelPendingFrame(component) {
  const pending = pendingFrames.get(component)
  if (!pending) return
  if (pending.type === 'raf' && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(pending.id)
  } else {
    clearTimeout(pending.id)
  }
  pendingFrames.delete(component)
}

export default {
  props: {
    option: { type: Object, default: () => ({}) },
    height: { type: [Number, String], default: 280 },
    minWidth: { type: [Number, String], default: 0 },
    loading: { type: Boolean, default: false },
    empty: { type: Boolean, default: false },
    emptyText: { type: String, default: '暂无足够数据' }
  },
  emits: ['chart-click'],
  computed: {
    shellStyle() {
      const height = typeof this.height === 'number' ? `${this.height}px` : this.height
      const minWidth = Number(this.minWidth) > 0 ? `${this.minWidth}px` : undefined
      return { height, minWidth }
    }
  },
  watch: {
    option() { this.scheduleRender() },
    loading(value) { if (!value) this.scheduleRender() },
    empty(value) { if (!value) this.scheduleRender() }
  },
  mounted() {
    unmountedComponents.delete(this)
    this.scheduleRender()
    this.$nextTick(() => this.bindResize())
  },
  beforeUnmount() {
    unmountedComponents.add(this)
    renderVersions.set(this, (renderVersions.get(this) || 0) + 1)
    cancelPendingFrame(this)
    const observer = resizeObservers.get(this)
    if (observer) observer.disconnect()
    resizeObservers.delete(this)
    const resizeHandler = resizeHandlers.get(this)
    if (resizeHandler && typeof window !== 'undefined') window.removeEventListener('resize', resizeHandler)
    resizeHandlers.delete(this)
    this.disposeChart()
  },
  methods: {
    rootElement() {
      const reference = this.$refs.chartRoot
      const root = reference?.$el || reference || null
      return root?.nodeType === 1 ? root : null
    },
    ensureChart() {
      const root = this.rootElement()
      if (!root || !root.isConnected || this.empty || this.loading) return null

      let chart = chartInstances.get(this)
      if (chart) {
        try {
          if (!chart.isDisposed() && chart.getDom() === root) return chart
        } catch (error) {
          // A stale third-party instance is replaced below.
        }
        this.disposeChart()
      }

      const attached = echarts.getInstanceByDom(root)
      if (attached && !attached.isDisposed()) attached.dispose()
      chart = echarts.init(root, null, { renderer: 'canvas', useDirtyRect: false })
      chart.on('click', params => this.$emit('chart-click', params))
      chartInstances.set(this, chart)
      return chart
    },
    scheduleRender() {
      const version = (renderVersions.get(this) || 0) + 1
      renderVersions.set(this, version)
      cancelPendingFrame(this)
      this.$nextTick(() => {
        if (unmountedComponents.has(this) || renderVersions.get(this) !== version) return
        const callback = () => {
          pendingFrames.delete(this)
          if (unmountedComponents.has(this) || renderVersions.get(this) !== version) return
          this.renderChart()
        }
        if (typeof requestAnimationFrame === 'function') {
          pendingFrames.set(this, { type: 'raf', id: requestAnimationFrame(callback) })
        } else {
          pendingFrames.set(this, { type: 'timeout', id: setTimeout(callback, 0) })
        }
      })
    },
    renderChart() {
      if (this.empty || this.loading) return
      const chart = this.ensureChart()
      if (!chart) return
      try {
        // Reuse component views instead of repeatedly destroying HTML tooltip
        // nodes. replaceMerge still removes series that disappeared.
        chart.setOption(this.option || {}, {
          notMerge: false,
          lazyUpdate: false,
          replaceMerge: ['series']
        })
      } catch (error) {
        this.disposeChart()
        throw error
      }
    },
    bindResize() {
      const root = this.rootElement()
      if (!root || resizeObservers.has(this) || resizeHandlers.has(this)) return
      if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(entries => {
          if (unmountedComponents.has(this)) return
          const rect = entries[0]?.contentRect
          if (!rect || rect.width <= 0 || rect.height <= 0) return
          const chart = chartInstances.get(this)
          if (chart && !chart.isDisposed()) chart.resize()
        })
        observer.observe(root)
        resizeObservers.set(this, observer)
      } else if (typeof window !== 'undefined') {
        const resizeHandler = () => {
          const chart = chartInstances.get(this)
          if (chart && !chart.isDisposed()) chart.resize()
        }
        resizeHandlers.set(this, resizeHandler)
        window.addEventListener('resize', resizeHandler)
      }
    },
    disposeChart() {
      const chart = chartInstances.get(this)
      chartInstances.delete(this)
      if (!chart) return
      try {
        chart.off()
        if (!chart.isDisposed()) chart.dispose()
      } catch (error) {
        // The component is already leaving; never let third-party cleanup
        // interrupt Vue's own unmount sequence.
      }
    },
    resize() {
      const chart = chartInstances.get(this)
      if (chart && !chart.isDisposed()) chart.resize()
    }
  }
}
</script>

<style scoped>
.chart-shell { position: relative; width: 100%; min-height: 160px; }
.chart-root { width: 100%; height: 100%; }
.chart-state { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 10px; color: #64748B; font-size: 12px; }
.chart-loader { width: 14px; height: 14px; border: 2px solid rgba(96,165,250,.18); border-top-color: #60A5FA; border-radius: 50%; animation: chart-spin .8s linear infinite; }
@keyframes chart-spin { to { transform: rotate(360deg); } }
</style>
