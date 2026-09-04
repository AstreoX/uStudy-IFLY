<template>
  <view class="preview-panel">
    <view class="preview-header">
      <view>
        <text class="preview-title">课件预览</text>
        <text class="preview-note">{{ revision ? revisionMeta : '完成生成后在这里逐页检查' }}</text>
      </view>
      <view v-if="revision" class="header-actions">
        <view class="quiet-action" :class="{ disabled: busy }" @tap="!busy && $emit('restore')">恢复</view>
        <view class="quiet-action" :class="{ disabled: busy }" @tap="!busy && $emit('download')">下载</view>
        <view class="publish-action" :class="{ disabled: busy }" @tap="!busy && $emit('publish')">
          {{ revision.isPublished ? '重新发布' : '发布到课程' }}
        </view>
      </view>
    </view>

    <view class="preview-body">
      <view v-if="!revision" class="preview-empty">
        <view class="deck-outline">
          <view class="outline-title"></view>
          <view class="outline-line short"></view>
          <view class="outline-line"></view>
          <view class="outline-image"></view>
        </view>
        <text>{{ running ? '课件正在生成，完成的预览会自动出现' : '选择一个版本查看课件' }}</text>
      </view>

      <template v-else>
        <scroll-view scroll-x class="slide-strip" :scroll-into-view="`slide-tab-${selectedSlide}`" scroll-with-animation>
          <view class="slide-tabs">
            <view
              v-for="slide in slideNumbers"
              :id="`slide-tab-${slide}`"
              :key="slide"
              class="slide-tab"
              :class="{ active: slide === selectedSlide }"
              @tap="$emit('select-slide', slide)"
            >
              <text>{{ pad(slide) }}</text>
              <view class="slide-tick"></view>
            </view>
          </view>
        </scroll-view>

        <view class="canvas-zone">
          <view class="slide-canvas">
            <view v-if="previewLoading" class="preview-loading">
              <view class="loading-scan"></view>
              <text>读取第 {{ selectedSlide }} 页…</text>
            </view>
            <image v-else-if="previewUrl" class="slide-image" :src="previewUrl" mode="aspectFit" @error="$emit('preview-error')" />
            <view v-else class="preview-failed">
              <text>暂时无法读取这一页</text>
              <view @tap="$emit('retry-preview')">重试</view>
            </view>
          </view>
          <view class="canvas-caption">
            <text>第 {{ selectedSlide }} 页 / 共 {{ slideCount }} 页</text>
            <text v-if="revision.isPublished" class="published-label">课程资料库已同步</text>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    revision: { type: Object, default: null },
    selectedSlide: { type: Number, default: 1 },
    previewUrl: { type: String, default: '' },
    previewLoading: { type: Boolean, default: false },
    busy: { type: Boolean, default: false },
    running: { type: Boolean, default: false }
  },
  emits: ['select-slide', 'restore', 'download', 'publish', 'retry-preview', 'preview-error'],
  computed: {
    slideCount() {
      return Math.max(1, Number(this.revision?.slideCount || 1))
    },
    slideNumbers() {
      return Array.from({ length: this.slideCount }, (_, index) => index + 1)
    },
    revisionMeta() {
      const version = this.revision.number ? `版本 ${this.revision.number}` : '已保存版本'
      return `${version} · ${this.slideCount} 页${this.revision.isPublished ? ' · 已发布' : ''}`
    }
  },
  methods: {
    pad(value) { return String(value).padStart(2, '0') }
  }
}
</script>

<style scoped>
.preview-panel { height: 100%; min-height: 0; display: flex; flex-direction: column; color: #fff; background: rgba(42,42,60,.42); backdrop-filter: blur(20px); }
.preview-header { height: 76px; box-sizing: border-box; padding: 15px 18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid rgba(255,255,255,.07); }
.preview-title, .preview-note { display: block; }
.preview-title { font-size: 14px; font-weight: 650; }
.preview-note { margin-top: 4px; color: rgba(255,255,255,.35); font-size: 10px; }
.header-actions { display: flex; align-items: center; gap: 5px; }
.quiet-action, .publish-action { padding: 7px 9px; border-radius: 7px; font-size: 9px; white-space: nowrap; cursor: pointer; transition: background .15s ease, opacity .15s ease; }
.quiet-action { color: rgba(255,255,255,.55); }
.quiet-action:hover { background: rgba(255,255,255,.06); }
.publish-action { color: #121722; background: #e2ebfc; font-weight: 650; }
.disabled { opacity: .35; cursor: default; }
.preview-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.preview-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; color: rgba(255,255,255,.28); font-size: 10px; }
.deck-outline { position: relative; width: min(72%, 390px); aspect-ratio: 16 / 9; box-sizing: border-box; padding: 11%; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.05); box-shadow: 0 20px 50px rgba(0,0,0,.18); }
.outline-title, .outline-line, .outline-image { background: rgba(255,255,255,.06); }
.outline-title { width: 48%; height: 8%; }
.outline-line { width: 35%; height: 3%; margin-top: 5%; }
.outline-line.short { width: 22%; }
.outline-image { position: absolute; right: 10%; top: 18%; width: 36%; height: 62%; }
.slide-strip { flex-shrink: 0; height: 49px; border-bottom: 1px solid rgba(255,255,255,.06); }
.slide-tabs { height: 100%; display: inline-flex; align-items: stretch; padding: 0 10px; }
.slide-tab { position: relative; min-width: 35px; display: grid; place-items: center; color: rgba(255,255,255,.3); font-size: 9px; cursor: pointer; }
.slide-tab.active { color: #b9d0ff; }
.slide-tick { position: absolute; bottom: 0; left: 8px; right: 8px; height: 2px; background: transparent; }
.slide-tab.active .slide-tick { background: #7fa9ff; }
.canvas-zone { flex: 1; min-height: 0; padding: 22px 5% 18px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.slide-canvas { position: relative; width: 100%; max-width: 820px; aspect-ratio: 16 / 9; overflow: hidden; background: #f5f5f3; box-shadow: 0 24px 70px rgba(0,0,0,.34); }
.slide-image { width: 100%; height: 100%; }
.preview-loading, .preview-failed { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: rgba(22,22,32,.5); font-size: 10px; }
.loading-scan { width: 34%; height: 2px; overflow: hidden; background: rgba(24,24,37,.08); }
.loading-scan::after { content: ''; display: block; width: 40%; height: 100%; background: #638ee8; animation: scan 1.2s ease-in-out infinite; }
.preview-failed view { color: #3b66bd; cursor: pointer; }
.canvas-caption { width: 100%; max-width: 820px; margin-top: 10px; display: flex; justify-content: space-between; color: rgba(255,255,255,.28); font-size: 9px; }
.published-label { color: #79bd95; }
@keyframes scan { from { transform: translateX(-110%); } to { transform: translateX(250%); } }
@media (max-width: 1180px) { .preview-header { padding-left: 14px; padding-right: 14px; } .quiet-action { display: none; } }
</style>
