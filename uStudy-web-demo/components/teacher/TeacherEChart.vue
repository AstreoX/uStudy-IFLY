<template>
  <view class="chart-shell" :style="shellStyle">
    <view v-if="loading" class="chart-state"><view class="chart-loader"></view><text>图表加载中…</text></view>
    <view v-else-if="empty" class="chart-state"><text>{{ emptyText }}</text></view>
    <view v-show="!loading && !empty" ref="chartRoot" class="chart-root"></view>
  </view>
</template>

<script>
import echarts from '@/utils/teacher-echarts'

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
  data() {
    return { chart: null, resizeObserver: null, resizeHandler: null }
  },
  computed: {
    shellStyle() {
      const height = typeof this.height === 'number' ? `${this.height}px` : this.height
      const minWidth = Number(this.minWidth) > 0 ? `${this.minWidth}px` : undefined
      return { height, minWidth }
    }
  },
  watch: {
    option: { deep: true, handler() { this.renderChart() } },
    empty(value) { if (!value) this.$nextTick(() => { this.ensureChart(); this.renderChart() }) }
  },
  mounted() {
    this.$nextTick(() => {
      this.ensureChart()
      this.renderChart()
      this.bindResize()
    })
  },
  beforeUnmount() {
    if (this.resizeObserver) this.resizeObserver.disconnect()
    if (this.resizeHandler && typeof window !== 'undefined') window.removeEventListener('resize', this.resizeHandler)
    if (this.chart) {
      this.chart.off('click')
      this.chart.dispose()
      this.chart = null
    }
  },
  methods: {
    rootElement() {
      return this.$refs.chartRoot?.$el || this.$refs.chartRoot || null
    },
    ensureChart() {
      if (this.chart || this.empty) return
      const root = this.rootElement()
      if (!root) return
      this.chart = echarts.init(root, null, { renderer: 'canvas' })
      this.chart.on('click', params => this.$emit('chart-click', params))
    },
    renderChart() {
      if (this.empty || this.loading) return
      this.ensureChart()
      if (!this.chart) return
      this.chart.setOption(this.option || {}, { notMerge: true, lazyUpdate: false })
    },
    bindResize() {
      const root = this.rootElement()
      if (!root) return
      if (typeof ResizeObserver !== 'undefined') {
        this.resizeObserver = new ResizeObserver(() => this.chart?.resize())
        this.resizeObserver.observe(root)
      } else if (typeof window !== 'undefined') {
        this.resizeHandler = () => this.chart?.resize()
        window.addEventListener('resize', this.resizeHandler)
      }
    },
    resize() { this.chart?.resize() }
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
