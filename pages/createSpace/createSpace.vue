<template>
  <view class="create-space-page">
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
      @select-space="handleSelectSpace"
      @create-space="() => {}"
    />

    <!-- Main Content -->
    <view class="create-space-main">
      <view class="create-space-content">
        <!-- Page Title -->
        <text class="page-title">新建学习空间</text>

        <!-- Topic Name Input -->
        <view class="input-wrapper">
          <input
            class="topic-input"
            type="text"
            v-model="topicName"
            placeholder="输入你想学习的内容..."
            placeholder-class="input-placeholder"
            :focus="inputFocused"
            @focus="inputFocused = true"
            @blur="inputFocused = false"
            @confirm="handleCreate"
          />
        </view>

        <!-- Preferences Section -->
        <view class="preferences-section">
          <!-- Custom Preference Input -->
          <view class="custom-preference-wrapper">
            <input
              class="custom-preference-input"
              type="text"
              v-model="customPreference"
              placeholder="自定义学习偏好（可选）"
              placeholder-class="input-placeholder"
              @focus="handlePreferenceFocus"
            />
          </view>

          <!-- Preference Tags (horizontal scroll with mouse drag + auto-scroll) -->
          <view
            v-if="showPreferenceTags"
            ref="prefsScroll"
            class="preferences-scroll-container"
            @mousedown.prevent="handleMouseDown"
            @touchstart="handleScrollTouchStart"
            @touchend="handleScrollTouchEnd"
            @touchcancel="handleScrollTouchCancel"
          >
            <view class="preferences-tags">
              <view
                v-for="option in displayPreferenceOptions"
                :key="option.uniqueKey"
                class="preference-tag"
                :class="{ 'preference-tag-selected': selectedPreferences.includes(option.id) }"
                @click="handleTagClick(option.id)"
              >
                <text class="tag-emoji">{{ option.emoji }}</text>
                <text class="tag-text">{{ option.label }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Create Button -->
        <view class="create-btn-wrapper">
          <view
            class="create-btn"
            :class="{ 'create-btn-disabled': !canCreate }"
            @click="handleCreate"
          >
            <text class="create-btn-text">{{ isCreating ? '创建中...' : '开始学习' }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import { createSpace, generateKnowledgeGraph } from '@/api/space'
import { useSpacesStore } from '@/store/spaces'

const ENABLE_AUTO_SCROLL = true
const AUTO_SPEED_PX_PER_SEC = 24
const AUTO_TICK_MS = 16
const RESUME_DELAY_MS = 1200

const COLOR_MAP = {
  blueGreen: '#0F6FFF',
  purplePink: '#A18CD1',
  pinkYellow: '#FA709A',
  mintCyan: '#84FAB0',
  redPurple: '#F43B37'
}

const COLOR_OPTIONS = Object.keys(COLOR_MAP)

export default {
  components: { HomeSidebar },

  data() {
    return {
      sidebarCollapsed: false,
      topicName: '',
      customPreference: '',
      selectedPreferences: [],
      inputFocused: false,
      isCreating: false,
      showPreferenceTags: false,
      preferenceOptions: [
        { id: 'university', label: '大学课程', emoji: '\u{1F393}' },
        { id: 'quick', label: '快速掌握', emoji: '\u26A1' },
        { id: 'solid', label: '扎实学习', emoji: '\u{1F4DA}' },
        { id: 'hobby', label: '业余自学', emoji: '\u{1F3A8}' },
        { id: 'exam', label: '应对考试', emoji: '\u{1F4DD}' },
        { id: 'work', label: '职场技能', emoji: '\u{1F4BC}' },
        { id: 'research', label: '学术研究', emoji: '\u{1F52C}' },
        { id: 'practice', label: '实践项目', emoji: '\u{1F6E0}\uFE0F' }
      ],
      // Loop scroll state
      loopUnitWidth: 0,
      autoTickTimer: null,
      resumeTimer: null,
      isInteracting: false,
      lastTickTs: 0,
      // Mouse drag state (desktop)
      mouseDragActive: false,
      mouseDragStartX: 0,
      mouseDragStartScrollLeft: 0,
      mouseDragDistance: 0
    }
  },

  computed: {
    canCreate() {
      return this.topicName.trim().length > 0 && !this.isCreating
    },
    displayPreferenceOptions() {
      return [
        ...this.preferenceOptions.map((opt, idx) => ({
          ...opt,
          uniqueKey: `first-${opt.id}-${idx}`
        })),
        ...this.preferenceOptions.map((opt, idx) => ({
          ...opt,
          uniqueKey: `middle-${opt.id}-${idx}`
        })),
        ...this.preferenceOptions.map((opt, idx) => ({
          ...opt,
          uniqueKey: `last-${opt.id}-${idx}`
        }))
      ]
    }
  },

  onReady() {
    this.inputFocused = true
  },

  onShow() {
    if (!this.showPreferenceTags) return
    if (this.loopUnitWidth > 0) {
      this.startAutoScroll()
      return
    }
    this.$nextTick(() => {
      this.initializeLoopScroll()
    })
  },

  onHide() {
    this.teardownLoopScroll()
  },

  onUnload() {
    this.teardownLoopScroll()
  },

  beforeUnmount() {
    this.teardownLoopScroll()
    this.removeMouseListeners()
  },

  methods: {
    handleSelectSpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${spaceId}` })
    },

    togglePreference(id) {
      if (this.selectedPreferences.includes(id)) {
        this.selectedPreferences = this.selectedPreferences.filter(p => p !== id)
      } else {
        this.selectedPreferences = [...this.selectedPreferences, id]
      }
    },

    handlePreferenceFocus() {
      if (!this.showPreferenceTags) {
        this.showPreferenceTags = true
        this.$nextTick(() => {
          this.initializeLoopScroll()
        })
        return
      }
      if (this.loopUnitWidth > 0) {
        this.startAutoScroll()
      } else {
        this.$nextTick(() => {
          this.initializeLoopScroll()
        })
      }
    },

    // ==================== Scroll Helpers ====================

    getScrollEl() {
      const ref = this.$refs.prefsScroll
      if (!ref) return null
      return ref.$el || ref
    },

    measureTagsWidth() {
      return new Promise((resolve) => {
        const query = uni.createSelectorQuery().in(this)
        query.select('.preferences-tags').boundingClientRect(rect => {
          if (!rect || !Number.isFinite(rect.width) || rect.width <= 0) {
            resolve(0)
            return
          }
          resolve(rect.width)
        }).exec()
      })
    },

    async initializeLoopScroll() {
      const fullWidth = await this.measureTagsWidth()
      if (!Number.isFinite(fullWidth) || fullWidth <= 0) {
        this.stopAutoScroll()
        return
      }

      const unitWidth = fullWidth / 3
      if (!Number.isFinite(unitWidth) || unitWidth <= 0) {
        this.stopAutoScroll()
        return
      }

      this.loopUnitWidth = unitWidth

      // Start from the middle copy
      const el = this.getScrollEl()
      if (el) el.scrollLeft = unitWidth

      this.lastTickTs = Date.now()
      this.startAutoScroll()
    },

    normalizeScroll() {
      if (this.loopUnitWidth <= 0) return
      const el = this.getScrollEl()
      if (!el) return

      let pos = el.scrollLeft
      const unit = this.loopUnitWidth

      // Wrap around: keep within [unit, unit*2)
      if (pos >= unit * 2) {
        pos -= unit
        el.scrollLeft = pos
      } else if (pos <= 0) {
        pos += unit
        el.scrollLeft = pos
      }
    },

    startAutoScroll() {
      if (!ENABLE_AUTO_SCROLL) return
      if (this.autoTickTimer) return
      if (!this.showPreferenceTags) return
      if (this.loopUnitWidth <= 0) return

      this.lastTickTs = Date.now()
      this.autoTickTimer = setInterval(() => {
        if (this.isInteracting) {
          this.lastTickTs = Date.now()
          return
        }

        const el = this.getScrollEl()
        if (!el) return

        const now = Date.now()
        const dt = Math.min((now - this.lastTickTs) / 1000, 0.05)
        this.lastTickTs = now

        if (!Number.isFinite(dt) || dt <= 0) return

        el.scrollLeft += AUTO_SPEED_PX_PER_SEC * dt
        this.normalizeScroll()
      }, AUTO_TICK_MS)
    },

    stopAutoScroll() {
      if (this.autoTickTimer) {
        clearInterval(this.autoTickTimer)
        this.autoTickTimer = null
      }
    },

    clearResumeTimer() {
      if (this.resumeTimer) {
        clearTimeout(this.resumeTimer)
        this.resumeTimer = null
      }
    },

    scheduleAutoResume() {
      this.clearResumeTimer()
      this.resumeTimer = setTimeout(() => {
        this.isInteracting = false
        this.lastTickTs = Date.now()
        this.resumeTimer = null
        this.normalizeScroll()
      }, RESUME_DELAY_MS)
    },

    teardownLoopScroll() {
      this.stopAutoScroll()
      this.clearResumeTimer()
      this.removeMouseListeners()
      this.isInteracting = false
      this.lastTickTs = 0
    },

    // ==================== Touch (mobile) ====================

    handleScrollTouchStart() {
      this.isInteracting = true
      this.clearResumeTimer()
    },

    handleScrollTouchEnd() {
      this.scheduleAutoResume()
    },

    handleScrollTouchCancel() {
      this.scheduleAutoResume()
    },

    // ==================== Mouse Drag (Desktop) ====================

    handleMouseDown(e) {
      const scrollEl = this.getScrollEl()
      if (!scrollEl) return

      this.mouseDragActive = true
      this.mouseDragStartX = e.clientX
      this.mouseDragStartScrollLeft = scrollEl.scrollLeft
      this.mouseDragDistance = 0

      this.isInteracting = true
      this.clearResumeTimer()

      document.addEventListener('mousemove', this.handleMouseMove)
      document.addEventListener('mouseup', this.handleMouseUp)
    },

    handleMouseMove(e) {
      if (!this.mouseDragActive) return
      const dx = e.clientX - this.mouseDragStartX
      this.mouseDragDistance = Math.abs(dx)

      const scrollEl = this.getScrollEl()
      if (!scrollEl) return

      scrollEl.scrollLeft = this.mouseDragStartScrollLeft - dx
    },

    handleMouseUp() {
      const wasDragging = this.mouseDragActive
      this.mouseDragActive = false
      this.removeMouseListeners()
      if (wasDragging) {
        this.normalizeScroll()
        this.scheduleAutoResume()
      }
    },

    removeMouseListeners() {
      document.removeEventListener('mousemove', this.handleMouseMove)
      document.removeEventListener('mouseup', this.handleMouseUp)
    },

    handleTagClick(id) {
      if (this.mouseDragDistance > 5) {
        this.mouseDragDistance = 0
        return
      }
      this.togglePreference(id)
    },

    // ==================== Create Space ====================

    async handleCreate() {
      if (!this.canCreate || this.isCreating) return

      const randomColor = COLOR_OPTIONS[Math.floor(Math.random() * COLOR_OPTIONS.length)]

      const preferenceLabels = this.selectedPreferences.map(id => {
        const opt = this.preferenceOptions.find(o => o.id === id)
        return opt ? opt.label : null
      }).filter(Boolean)

      if (this.customPreference.trim()) {
        preferenceLabels.push(this.customPreference.trim())
      }

      this.isCreating = true
      let spaceRes = null

      const learningPreferences = {
        preset_preferences: this.selectedPreferences,
        custom_preference: this.customPreference.trim() || null
      }
      const hasPreferences =
        learningPreferences.preset_preferences.length > 0 ||
        learningPreferences.custom_preference !== null

      try {
        spaceRes = await createSpace({
          name: this.topicName.trim(),
          color: COLOR_MAP[randomColor],
          ...(hasPreferences && { learning_preferences: learningPreferences })
        })
      } catch (err) {
        const errorMsg = err?.data?.detail?.message || err?.data?.message || '创建失败，请重试'
        uni.showToast({ title: errorMsg, icon: 'none' })
        this.isCreating = false
        return
      }

      // Invalidate spaces store so sidebar refreshes
      const spacesStore = useSpacesStore()
      spacesStore.invalidate()

      // Trigger knowledge graph generation
      try {
        await generateKnowledgeGraph(spaceRes.id, {
          topic: this.topicName.trim(),
          user_preference: preferenceLabels.length > 0 ? preferenceLabels.join('、') : null
        })
      } catch (err) {
        // Space was created, still navigate even if KG generation fails
      }

      this.isCreating = false
      uni.reLaunch({
        url: `/pages/study/study?spaceId=${spaceRes.id}`
      })
    }
  }
}
</script>

<style scoped>
.create-space-page {
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

/* Main Content Area */
.create-space-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  position: relative;
  z-index: 1;
  padding: 40px;
}

.create-space-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 600px;
}

/* Page Title */
.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 32px;
  text-align: center;
  background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 50%, #ffffff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Capsule Input Wrapper */
.input-wrapper {
  width: 100%;
  background: rgba(255, 255, 255, 0.08);
  border: 2px solid rgba(255, 255, 255, 0.20);
  border-radius: 50px;
  padding: 14px 24px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  margin-bottom: 20px;
  transition: border-color 0.2s ease;
}

.input-wrapper:focus-within {
  border-color: rgba(59, 130, 246, 0.5);
}

.topic-input {
  width: 100%;
  font-size: 15px;
  color: #ffffff;
  background-color: transparent;
  text-align: center;
  border: none;
  outline: none;
}

.input-placeholder {
  color: rgba(255, 255, 255, 0.45);
}

/* Preferences Section */
.preferences-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.custom-preference-wrapper {
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 50px;
  padding: 14px 24px;
  margin-bottom: 16px;
  transition: border-color 0.2s ease;
}

.custom-preference-wrapper:focus-within {
  border-color: rgba(59, 130, 246, 0.4);
}

.custom-preference-input {
  width: 100%;
  font-size: 15px;
  color: #ffffff;
  background-color: transparent;
  text-align: center;
  border: none;
  outline: none;
}

/* Preference Tags Scroll */
.preferences-scroll-container {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  scrollbar-width: none;
  -ms-overflow-style: none;
  cursor: grab;
}

.preferences-scroll-container:active {
  cursor: grabbing;
}

.preferences-scroll-container::-webkit-scrollbar {
  display: none;
  height: 0;
}

.preferences-tags {
  display: inline-flex;
  gap: 8px;
  padding: 0 10px 12px;
  user-select: none;
  -webkit-user-select: none;
}

.preference-tag {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.08);
  border: 2px solid rgba(255, 255, 255, 0.15);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.preference-tag:hover {
  background: rgba(255, 255, 255, 0.12);
}

.preference-tag-selected {
  background: rgba(0, 136, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.35);
  box-shadow: 0 0 8px rgba(0, 136, 255, 0.3);
}

.preference-tag-selected:hover {
  background: rgba(0, 136, 255, 0.3);
}

.tag-emoji {
  font-size: 14px;
}

.tag-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
}

.preference-tag-selected .tag-text {
  color: #ffffff;
}

/* Create Button */
.create-btn-wrapper {
  width: 100%;
  margin-top: 36px;
}

.create-btn {
  width: 100%;
  height: 48px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg,
    rgba(0, 136, 255, 0.6) 0%,
    rgba(139, 92, 246, 0.5) 100%
  );
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow:
    0 4px 20px rgba(0, 136, 255, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.create-btn:hover {
  box-shadow:
    0 6px 28px rgba(0, 136, 255, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.create-btn-disabled {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: none;
  cursor: not-allowed;
}

.create-btn-disabled:hover {
  box-shadow: none;
  transform: none;
}

.create-btn-text {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
}

.create-btn-disabled .create-btn-text {
  color: rgba(255, 255, 255, 0.4);
}
</style>
