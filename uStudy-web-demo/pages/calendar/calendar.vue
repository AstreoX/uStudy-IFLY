<template>
  <view class="calendar-page">
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
      @create-space="handleCreateSpace"
    />

    <!-- Main Content: Two-Panel Layout -->
    <view class="cal-layout">
      <!-- Left: Mini Calendar + Upcoming -->
      <view class="cal-sidebar">
        <!-- Mini Calendar Card -->
        <view class="mini-cal-card">
          <view class="mini-cal-header">
            <text class="mini-cal-title">{{ miniCalTitle }}</text>
            <view class="mini-cal-nav">
              <view class="mini-nav-btn" @tap="miniPrev">
                <svg viewBox="0 0 256 256" class="mini-nav-icon"><polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
              </view>
              <view class="mini-nav-btn" @tap="miniNext">
                <svg viewBox="0 0 256 256" class="mini-nav-icon"><polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
              </view>
            </view>
          </view>
          <view class="mini-weekdays">
            <text v-for="d in miniWeekDays" :key="d" class="mini-wd">{{ d }}</text>
          </view>
          <view class="mini-grid">
            <view
              v-for="(day, idx) in monthDays"
              :key="idx"
              class="mini-day"
              :class="{
                'mini-day-other': !day.isCurrentMonth,
                'mini-day-today': day.isToday,
                'mini-day-selected': day.dateStr === selectedDate,
                'mini-day-has-event': day.events.length > 0
              }"
              @tap="selectDay(day)"
            >
              <text class="mini-day-num">{{ day.day }}</text>
            </view>
          </view>
        </view>

        <!-- Upcoming Events -->
        <view class="upcoming-card">
          <view class="upcoming-header">
            <text class="upcoming-title">Upcoming</text>
          </view>
          <view class="upcoming-list" v-if="upcomingEvents.length > 0">
            <view
              v-for="evt in upcomingEvents"
              :key="evt.id"
              class="upcoming-item"
              @tap="openEditModal(evt)"
            >
              <view class="upcoming-accent"></view>
              <view class="upcoming-body">
                <text class="upcoming-event-title">{{ evt.title }}</text>
                <text class="upcoming-event-meta">{{ formatUpcomingDate(evt) }}</text>
              </view>
            </view>
          </view>
          <view v-else class="upcoming-empty">
            <text class="upcoming-empty-text">No upcoming events</text>
          </view>
        </view>
      </view>

      <!-- Right: Main Calendar Area -->
      <view class="cal-main">
        <!-- Header Bar -->
        <view class="cal-header">
          <view class="cal-header-left">
            <text class="cal-header-title">{{ headerTitle }}</text>
            <view class="cal-header-nav">
              <view class="cal-nav-btn" @tap="goPrev">
                <svg viewBox="0 0 256 256" class="cal-nav-icon"><polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
              </view>
              <view class="cal-nav-btn" @tap="goNext">
                <svg viewBox="0 0 256 256" class="cal-nav-icon"><polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
              </view>
              <view class="today-pill" @tap="goToday">
                <text class="today-pill-text">Today</text>
              </view>
            </view>
          </view>
          <view class="cal-header-right">
            <view class="view-switcher">
              <view class="view-sw-btn" :class="{ active: viewMode === 'month' }" @tap="viewMode = 'month'">
                <svg viewBox="0 0 256 256" class="view-sw-icon"><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="40" y1="88" x2="216" y2="88" fill="none" stroke="currentColor" stroke-width="16"/><line x1="128" y1="88" x2="128" y2="216" fill="none" stroke="currentColor" stroke-width="16"/><line x1="40" y1="152" x2="216" y2="152" fill="none" stroke="currentColor" stroke-width="16"/></svg>
              </view>
              <view class="view-sw-btn" :class="{ active: viewMode === 'week' }" @tap="viewMode = 'week'">
                <svg viewBox="0 0 256 256" class="view-sw-icon"><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="40" y1="88" x2="216" y2="88" fill="none" stroke="currentColor" stroke-width="16"/></svg>
              </view>
            </view>
            <view class="new-event-btn" @tap="openCreateModal">
              <svg viewBox="0 0 256 256" class="new-event-icon"><line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
              <text class="new-event-text">New Event</text>
            </view>
          </view>
        </view>

        <!-- ========== MONTH VIEW ========== -->
        <view v-if="viewMode === 'month'" class="month-view">
          <view class="month-weekday-row">
            <view v-for="d in weekDays" :key="d" class="month-wd-cell">
              <text class="month-wd-text">{{ d }}</text>
            </view>
          </view>
          <view class="month-grid">
            <view
              v-for="(day, idx) in monthDays"
              :key="idx"
              class="month-cell"
              :class="{
                'month-cell-other': !day.isCurrentMonth,
                'month-cell-today': day.isToday,
                'month-cell-selected': day.dateStr === selectedDate
              }"
              @tap="selectDay(day)"
            >
              <text class="month-cell-num" :class="{ 'month-cell-num-today': day.isToday }">{{ day.day }}</text>
              <!-- Event pills (max 2 + overflow) -->
              <view v-if="day.events.length > 0" class="month-cell-events">
                <view
                  v-for="(evt, ei) in day.events.slice(0, 2)"
                  :key="ei"
                  class="month-event-pill"
                  @tap.stop="openEditModal(evt)"
                >
                  <text class="month-event-pill-text">{{ evt.title }}</text>
                </view>
                <text v-if="day.events.length > 2" class="month-event-more">+{{ day.events.length - 2 }} more</text>
              </view>
            </view>
          </view>

          <!-- Selected Day Detail Drawer -->
          <transition name="drawer-slide">
            <view v-if="selectedDate && selectedDayEvents.length > 0" class="day-drawer">
              <view class="day-drawer-bar"></view>
              <view class="day-drawer-header">
                <text class="day-drawer-date">{{ formatSelectedDate }}</text>
                <text class="day-drawer-count">{{ selectedDayEvents.length }} {{ selectedDayEvents.length === 1 ? 'event' : 'events' }}</text>
              </view>
              <view class="day-drawer-list">
                <view
                  v-for="evt in selectedDayEvents"
                  :key="evt.id"
                  class="drawer-event"
                >
                  <view class="drawer-event-stripe"></view>
                  <view class="drawer-event-info">
                    <text class="drawer-event-time">{{ formatTime(evt.start_time) }} - {{ formatTime(evt.end_time) }}</text>
                    <text class="drawer-event-title">{{ evt.title }}</text>
                    <text v-if="evt.details" class="drawer-event-desc">{{ evt.details }}</text>
                  </view>
                  <view class="drawer-event-actions">
                    <view class="drawer-action" @tap="openEditModal(evt)">
                      <svg viewBox="0 0 256 256" class="drawer-action-icon"><path d="M227.31,73.37,182.63,28.68a16,16,0,0,0-22.63,0L36.69,152A15.86,15.86,0,0,0,32,163.31V208a16,16,0,0,0,16,16H92.69A15.86,15.86,0,0,0,104,219.31L227.31,96a16,16,0,0,0,0-22.63ZM92.69,208H48V163.31l88-88,44.69,44.68Z" fill="currentColor"/></svg>
                    </view>
                    <view class="drawer-action drawer-action-del" @tap="handleDeleteEvent(evt)">
                      <svg viewBox="0 0 256 256" class="drawer-action-icon"><path d="M216,48H176V40a24,24,0,0,0-24-24H104A24,24,0,0,0,80,40v8H40a8,8,0,0,0,0,16h8V208a16,16,0,0,0,16,16H192a16,16,0,0,0,16-16V64h8a8,8,0,0,0,0-16ZM96,40a8,8,0,0,1,8-8h48a8,8,0,0,1,8,8v8H96Zm96,168H64V64H192ZM112,104v64a8,8,0,0,1-16,0V104a8,8,0,0,1,16,0Zm48,0v64a8,8,0,0,1-16,0V104a8,8,0,0,1,16,0Z" fill="currentColor"/></svg>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </transition>
        </view>

        <!-- ========== WEEK VIEW ========== -->
        <view v-if="viewMode === 'week'" class="week-view">
          <view class="week-cols-header">
            <view class="week-gutter-header"></view>
            <view
              v-for="wd in weekViewDays"
              :key="wd.dateStr"
              class="week-col-header"
              :class="{ 'week-col-today': wd.isToday }"
            >
              <text class="week-col-dayname">{{ wd.dayName }}</text>
              <view class="week-col-num-wrap" :class="{ 'week-col-num-today': wd.isToday }">
                <text class="week-col-num">{{ wd.day }}</text>
              </view>
            </view>
          </view>
          <view class="week-scroll">
            <view class="week-body">
              <view class="week-time-col">
                <view v-for="h in 24" :key="h" class="week-time-row">
                  <text class="week-time-lbl">{{ (h - 1).toString().padStart(2, '0') }}:00</text>
                </view>
              </view>
              <view class="week-days-grid">
                <view
                  v-for="wd in weekViewDays"
                  :key="wd.dateStr"
                  class="week-day-col"
                >
                  <view v-for="h in 24" :key="h" class="week-hour-line"></view>
                  <!-- Current time indicator -->
                  <view v-if="wd.isToday" class="week-now-line" :style="{ top: nowLineTop + 'px' }">
                    <view class="week-now-dot"></view>
                  </view>
                  <!-- Events -->
                  <view
                    v-for="evt in wd.events"
                    :key="evt.id"
                    class="week-evt"
                    :style="getWeekEventStyle(evt)"
                    @tap="openEditModal(evt)"
                  >
                    <text class="week-evt-title">{{ evt.title }}</text>
                    <text class="week-evt-time">{{ formatTime(evt.start_time) }} - {{ formatTime(evt.end_time) }}</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Create/Edit Modal -->
    <view v-if="showModal" class="modal-wrapper" @click.self="closeModal">
      <view class="modal-panel">
        <view class="modal-top">
          <text class="modal-heading">{{ editingEvent ? 'Edit Event' : 'New Event' }}</text>
          <view class="modal-x" @click="closeModal">
            <svg viewBox="0 0 256 256" class="modal-x-icon"><line x1="200" y1="56" x2="56" y2="200" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="200" y1="200" x2="56" y2="56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
          </view>
        </view>
        <view class="modal-form">
          <view class="field">
            <text class="field-label">Title</text>
            <input class="field-input field-input-lg" v-model="formData.title" placeholder="What's happening?" maxlength="500" />
          </view>
          <view class="field-row">
            <view class="field field-half">
              <text class="field-label">Start</text>
              <view class="field-input datetime-display" @click="openDatetimePicker('start')">
                <text class="datetime-text">{{ formatDisplay(formData.startTime) }}</text>
              </view>
            </view>
            <view class="field field-half">
              <text class="field-label">End</text>
              <view class="field-input datetime-display" @click="openDatetimePicker('end')">
                <text class="datetime-text">{{ formatDisplay(formData.endTime) }}</text>
              </view>
            </view>
          </view>
          <view class="field">
            <text class="field-label">Details</text>
            <textarea class="field-textarea" v-model="formData.details" placeholder="Add notes..." maxlength="5000"></textarea>
          </view>
        </view>
        <view class="modal-actions">
          <view class="modal-act-btn modal-act-ghost" @click="closeModal">
            <text class="modal-act-text">Cancel</text>
          </view>
          <view
            class="modal-act-btn modal-act-primary"
            :class="{ 'modal-act-disabled': !formData.title || !formData.startTime || !formData.endTime || isSaving }"
            @click="saveEvent"
          >
            <text class="modal-act-text">{{ isSaving ? 'Saving...' : (editingEvent ? 'Update' : 'Create') }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Custom Datetime Picker -->
    <view v-if="showDtPicker" class="dtp-mask" @click.self="closeDtPicker">
      <view class="dtp-panel" @click.stop>
        <!-- Header -->
        <view class="dtp-header">
          <view class="dtp-nav-btn" @click="dtpPrevMonth">
            <svg viewBox="0 0 256 256" class="dtp-nav-icon"><polyline points="160 208 80 128 160 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
          </view>
          <text class="dtp-title">{{ dtpMonthTitle }}</text>
          <view class="dtp-nav-btn" @click="dtpNextMonth">
            <svg viewBox="0 0 256 256" class="dtp-nav-icon"><polyline points="96 48 176 128 96 208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
          </view>
        </view>
        <!-- Weekday labels -->
        <view class="dtp-weekdays">
          <text v-for="d in ['S','M','T','W','T','F','S']" :key="d" class="dtp-wd">{{ d }}</text>
        </view>
        <!-- Calendar grid -->
        <view class="dtp-grid">
          <view
            v-for="(day, idx) in dtpDays"
            :key="idx"
            class="dtp-day"
            :class="{
              'dtp-day-other': !day.isCur,
              'dtp-day-sel': day.isCur && day.d === dtpDay,
              'dtp-day-today': day.isToday
            }"
            @click="dtpSelectDay(day)"
          >
            <text class="dtp-day-num">{{ day.d }}</text>
          </view>
        </view>
        <!-- Time selector -->
        <view class="dtp-time-row">
          <view class="dtp-time-group">
            <view class="dtp-time-btn" @click="dtpHour = (dtpHour + 23) % 24">
              <svg viewBox="0 0 256 256" class="dtp-time-icon"><polyline points="48 160 128 80 208 160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            </view>
            <text class="dtp-time-val">{{ String(dtpHour).padStart(2,'0') }}</text>
            <view class="dtp-time-btn" @click="dtpHour = (dtpHour + 1) % 24">
              <svg viewBox="0 0 256 256" class="dtp-time-icon"><polyline points="208 96 128 176 48 96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            </view>
          </view>
          <text class="dtp-time-colon">:</text>
          <view class="dtp-time-group">
            <view class="dtp-time-btn" @click="dtpMinute = (dtpMinute + 55) % 60">
              <svg viewBox="0 0 256 256" class="dtp-time-icon"><polyline points="48 160 128 80 208 160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            </view>
            <text class="dtp-time-val">{{ String(dtpMinute).padStart(2,'0') }}</text>
            <view class="dtp-time-btn" @click="dtpMinute = (dtpMinute + 5) % 60">
              <svg viewBox="0 0 256 256" class="dtp-time-icon"><polyline points="208 96 128 176 48 96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
            </view>
          </view>
        </view>
        <!-- Actions -->
        <view class="dtp-actions">
          <view class="dtp-act-btn dtp-act-cancel" @click="closeDtPicker">
            <text class="dtp-act-text">Cancel</text>
          </view>
          <view class="dtp-act-btn dtp-act-ok" @click="confirmDtPicker">
            <text class="dtp-act-text">OK</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import { getCalendarEvents, createCalendarEvent, updateCalendarEvent, deleteCalendarEvent } from '@/api/calendar'

const WEEK_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MINI_WD = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

export default {
  components: { HomeSidebar },
  data() {
    return {
      sidebarCollapsed: false,
      viewMode: 'month',
      currentYear: new Date().getFullYear(),
      currentMonth: new Date().getMonth(),
      currentWeekStart: null,
      selectedDate: null,
      events: [],
      showModal: false,
      editingEvent: null,
      isSaving: false,
      nowLineTop: 0,
      nowTimer: null,
      formData: { title: '', startTime: '', endTime: '', details: '' },
      showDtPicker: false,
      dtpField: null,
      dtpYear: 2026,
      dtpMonth: 2,
      dtpDay: 7,
      dtpHour: 13,
      dtpMinute: 0
    }
  },
  computed: {
    weekDays() { return WEEK_DAYS },
    miniWeekDays() { return MINI_WD },
    miniCalTitle() {
      const months = ['January','February','March','April','May','June','July','August','September','October','November','December']
      return `${months[this.currentMonth]} ${this.currentYear}`
    },
    headerTitle() {
      const months = ['January','February','March','April','May','June','July','August','September','October','November','December']
      if (this.viewMode === 'week' && this.currentWeekStart) {
        const end = new Date(this.currentWeekStart)
        end.setDate(end.getDate() + 6)
        const s = this.currentWeekStart
        if (s.getMonth() === end.getMonth()) {
          return `${months[s.getMonth()]} ${s.getDate()} - ${end.getDate()}, ${s.getFullYear()}`
        }
        return `${months[s.getMonth()].substring(0,3)} ${s.getDate()} - ${months[end.getMonth()].substring(0,3)} ${end.getDate()}, ${s.getFullYear()}`
      }
      return `${months[this.currentMonth]} ${this.currentYear}`
    },
    monthDays() {
      const first = new Date(this.currentYear, this.currentMonth, 1)
      const startDay = first.getDay()
      const daysInMonth = new Date(this.currentYear, this.currentMonth + 1, 0).getDate()
      const prevMonthDays = new Date(this.currentYear, this.currentMonth, 0).getDate()
      const today = new Date()
      const todayStr = this.dateToStr(today)
      const days = []
      for (let i = startDay - 1; i >= 0; i--) {
        const d = prevMonthDays - i
        const date = new Date(this.currentYear, this.currentMonth - 1, d)
        const dateStr = this.dateToStr(date)
        days.push({ day: d, dateStr, isCurrentMonth: false, isToday: dateStr === todayStr, events: this.getEventsForDate(dateStr) })
      }
      for (let d = 1; d <= daysInMonth; d++) {
        const date = new Date(this.currentYear, this.currentMonth, d)
        const dateStr = this.dateToStr(date)
        days.push({ day: d, dateStr, isCurrentMonth: true, isToday: dateStr === todayStr, events: this.getEventsForDate(dateStr) })
      }
      const remaining = 42 - days.length
      for (let d = 1; d <= remaining; d++) {
        const date = new Date(this.currentYear, this.currentMonth + 1, d)
        const dateStr = this.dateToStr(date)
        days.push({ day: d, dateStr, isCurrentMonth: false, isToday: dateStr === todayStr, events: this.getEventsForDate(dateStr) })
      }
      return days
    },
    selectedDayEvents() {
      if (!this.selectedDate) return []
      return this.getEventsForDate(this.selectedDate).sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    },
    formatSelectedDate() {
      if (!this.selectedDate) return ''
      const d = new Date(this.selectedDate + 'T00:00:00')
      return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
    },
    upcomingEvents() {
      const now = new Date()
      return this.events
        .filter(e => new Date(e.start_time) >= now)
        .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
        .slice(0, 5)
    },
    dtpMonthTitle() {
      const m = ['January','February','March','April','May','June','July','August','September','October','November','December']
      return `${m[this.dtpMonth]} ${this.dtpYear}`
    },
    dtpDays() {
      const first = new Date(this.dtpYear, this.dtpMonth, 1)
      const startDay = first.getDay()
      const dim = new Date(this.dtpYear, this.dtpMonth + 1, 0).getDate()
      const prevDim = new Date(this.dtpYear, this.dtpMonth, 0).getDate()
      const today = new Date()
      const todayStr = `${today.getFullYear()}-${today.getMonth()}-${today.getDate()}`
      const days = []
      for (let i = startDay - 1; i >= 0; i--) {
        const d = prevDim - i
        const pm = this.dtpMonth === 0 ? 11 : this.dtpMonth - 1
        const py = this.dtpMonth === 0 ? this.dtpYear - 1 : this.dtpYear
        days.push({ d, isCur: false, isToday: `${py}-${pm}-${d}` === todayStr })
      }
      for (let d = 1; d <= dim; d++) {
        days.push({ d, isCur: true, isToday: `${this.dtpYear}-${this.dtpMonth}-${d}` === todayStr })
      }
      const rem = 42 - days.length
      for (let d = 1; d <= rem; d++) {
        const nm = this.dtpMonth === 11 ? 0 : this.dtpMonth + 1
        const ny = this.dtpMonth === 11 ? this.dtpYear + 1 : this.dtpYear
        days.push({ d, isCur: false, isToday: `${ny}-${nm}-${d}` === todayStr })
      }
      return days
    },
    weekViewDays() {
      if (!this.currentWeekStart) return []
      const days = []
      const today = new Date()
      const todayStr = this.dateToStr(today)
      for (let i = 0; i < 7; i++) {
        const d = new Date(this.currentWeekStart)
        d.setDate(d.getDate() + i)
        const dateStr = this.dateToStr(d)
        days.push({
          dateStr, day: d.getDate(), dayName: WEEK_DAYS[d.getDay()],
          isToday: dateStr === todayStr, events: this.getEventsForDate(dateStr)
        })
      }
      return days
    }
  },
  created() {
    this.initWeekStart()
    this.selectedDate = this.dateToStr(new Date())
    this.fetchEvents()
    this.updateNowLine()
    this.nowTimer = setInterval(() => this.updateNowLine(), 60000)
  },
  beforeUnmount() {
    if (this.nowTimer) clearInterval(this.nowTimer)
  },
  methods: {
    handleSelectSpace(space) {
      uni.navigateTo({ url: `/pages/study/study?id=${space.id}&name=${encodeURIComponent(space.name)}&color=${encodeURIComponent(space.color || '#3B82F6')}` })
    },
    handleCreateSpace() {
      uni.navigateTo({ url: '/pages/createSpace/createSpace' })
    },
    initWeekStart() {
      const today = new Date()
      const start = new Date(today)
      start.setDate(today.getDate() - today.getDay())
      start.setHours(0, 0, 0, 0)
      this.currentWeekStart = start
    },
    dateToStr(d) {
      return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`
    },
    getEventsForDate(dateStr) {
      return this.events.filter(e => {
        const start = e.start_time.substring(0, 10)
        const end = e.end_time.substring(0, 10)
        return dateStr >= start && dateStr <= end
      })
    },
    formatTime(isoStr) {
      const d = new Date(isoStr)
      return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
    },
    formatUpcomingDate(evt) {
      const d = new Date(evt.start_time)
      const today = new Date()
      const tomorrow = new Date(today)
      tomorrow.setDate(tomorrow.getDate() + 1)
      const dStr = this.dateToStr(d)
      if (dStr === this.dateToStr(today)) return `Today, ${this.formatTime(evt.start_time)}`
      if (dStr === this.dateToStr(tomorrow)) return `Tomorrow, ${this.formatTime(evt.start_time)}`
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' + this.formatTime(evt.start_time)
    },
    updateNowLine() {
      const now = new Date()
      this.nowLineTop = (now.getHours() * 60 + now.getMinutes()) / 60 * 56
    },
    goToday() {
      const today = new Date()
      this.currentYear = today.getFullYear()
      this.currentMonth = today.getMonth()
      this.selectedDate = this.dateToStr(today)
      this.initWeekStart()
      this.fetchEvents()
    },
    goPrev() {
      if (this.viewMode === 'month') {
        this.currentMonth === 0 ? (this.currentMonth = 11, this.currentYear--) : this.currentMonth--
      } else {
        const ws = new Date(this.currentWeekStart)
        ws.setDate(ws.getDate() - 7)
        this.currentWeekStart = ws
        this.currentYear = ws.getFullYear()
        this.currentMonth = ws.getMonth()
      }
      this.fetchEvents()
    },
    goNext() {
      if (this.viewMode === 'month') {
        this.currentMonth === 11 ? (this.currentMonth = 0, this.currentYear++) : this.currentMonth++
      } else {
        const ws = new Date(this.currentWeekStart)
        ws.setDate(ws.getDate() + 7)
        this.currentWeekStart = ws
        this.currentYear = ws.getFullYear()
        this.currentMonth = ws.getMonth()
      }
      this.fetchEvents()
    },
    miniPrev() {
      this.currentMonth === 0 ? (this.currentMonth = 11, this.currentYear--) : this.currentMonth--
      this.fetchEvents()
    },
    miniNext() {
      this.currentMonth === 11 ? (this.currentMonth = 0, this.currentYear++) : this.currentMonth++
      this.fetchEvents()
    },
    selectDay(day) { this.selectedDate = day.dateStr },
    async fetchEvents() {
      const start = new Date(this.currentYear, this.currentMonth - 1, 1)
      const end = new Date(this.currentYear, this.currentMonth + 2, 0, 23, 59, 59)
      try {
        const data = await getCalendarEvents(start.toISOString(), end.toISOString())
        this.events = (data || []).map(e => ({ ...e }))
      } catch (err) {
        console.error('Failed to fetch calendar events:', err)
      }
    },
    toLocalDatetime(d) {
      const pad = n => n.toString().padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    },
    openCreateModal() {
      this.editingEvent = null
      const now = new Date()
      now.setMinutes(0, 0, 0)
      const later = new Date(now.getTime() + 3600000)
      this.formData = { title: '', startTime: this.toLocalDatetime(now), endTime: this.toLocalDatetime(later), details: '' }
      this.showModal = true
    },
    openEditModal(evt) {
      this.editingEvent = evt
      this.formData = {
        title: evt.title,
        startTime: this.toLocalDatetime(new Date(evt.start_time)),
        endTime: this.toLocalDatetime(new Date(evt.end_time)),
        details: evt.details || ''
      }
      this.showModal = true
    },
    closeModal() { this.showModal = false; this.editingEvent = null },
    formatDisplay(val) {
      if (!val) return 'Select'
      const d = new Date(val)
      const pad = n => n.toString().padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    },
    openDatetimePicker(field) {
      this.dtpField = field
      const val = field === 'start' ? this.formData.startTime : this.formData.endTime
      if (val) {
        const d = new Date(val)
        this.dtpYear = d.getFullYear()
        this.dtpMonth = d.getMonth()
        this.dtpDay = d.getDate()
        this.dtpHour = d.getHours()
        this.dtpMinute = d.getMinutes()
      } else {
        const now = new Date()
        this.dtpYear = now.getFullYear()
        this.dtpMonth = now.getMonth()
        this.dtpDay = now.getDate()
        this.dtpHour = now.getHours()
        this.dtpMinute = 0
      }
      this.showDtPicker = true
    },
    closeDtPicker() { this.showDtPicker = false },
    dtpSelectDay(day) {
      if (day.isCur) this.dtpDay = day.d
    },
    dtpPrevMonth() {
      if (this.dtpMonth === 0) { this.dtpMonth = 11; this.dtpYear-- }
      else this.dtpMonth--
    },
    dtpNextMonth() {
      if (this.dtpMonth === 11) { this.dtpMonth = 0; this.dtpYear++ }
      else this.dtpMonth++
    },
    confirmDtPicker() {
      const pad = n => n.toString().padStart(2, '0')
      const val = `${this.dtpYear}-${pad(this.dtpMonth + 1)}-${pad(this.dtpDay)}T${pad(this.dtpHour)}:${pad(this.dtpMinute)}`
      if (this.dtpField === 'start') this.formData.startTime = val
      else this.formData.endTime = val
      this.showDtPicker = false
    },
    async saveEvent() {
      if (!this.formData.title || !this.formData.startTime || !this.formData.endTime || this.isSaving) return
      this.isSaving = true
      try {
        const payload = {
          title: this.formData.title,
          start_time: new Date(this.formData.startTime).toISOString(),
          end_time: new Date(this.formData.endTime).toISOString(),
          details: this.formData.details || null
        }
        if (this.editingEvent) await updateCalendarEvent(this.editingEvent.id, payload)
        else await createCalendarEvent(payload)
        this.closeModal()
        await this.fetchEvents()
      } catch (err) {
        console.error('Failed to save event:', err)
      } finally {
        this.isSaving = false
      }
    },
    async handleDeleteEvent(evt) {
      try {
        await deleteCalendarEvent(evt.id)
        await this.fetchEvents()
      } catch (err) {
        console.error('Failed to delete event:', err)
      }
    },
    getWeekEventStyle(evt) {
      const start = new Date(evt.start_time)
      const end = new Date(evt.end_time)
      const startMin = start.getHours() * 60 + start.getMinutes()
      const endMin = end.getHours() * 60 + end.getMinutes()
      const dur = Math.max(endMin - startMin, 30)
      return { top: (startMin / 60) * 56 + 'px', height: (dur / 60) * 56 + 'px' }
    }
  }
}
</script>

<style scoped>
/* ====================== BASE ====================== */
.calendar-page {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: #0e0e1a;
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* Aurora */
.aurora-bg { position: fixed; inset: 0; overflow: hidden; z-index: 0; pointer-events: none; }
.aurora-blob { position: absolute; border-radius: 50%; will-change: transform; }
.aurora-blob-1 {
  width: 1200px; height: 1200px;
  background: radial-gradient(circle, rgba(99,73,234,0.22) 0%, rgba(99,73,234,0.06) 50%, transparent 75%);
  top: -30%; left: -15%; filter: blur(100px);
  animation: a-a 14s ease-in-out infinite;
}
.aurora-blob-2 {
  width: 900px; height: 900px;
  background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, rgba(59,130,246,0.05) 50%, transparent 75%);
  top: 15%; right: -12%; filter: blur(80px);
  animation: a-b 11s ease-in-out infinite;
}
.aurora-blob-3 {
  width: 800px; height: 800px;
  background: radial-gradient(circle, rgba(236,72,153,0.12) 0%, rgba(236,72,153,0.04) 50%, transparent 75%);
  bottom: -20%; left: 30%; filter: blur(90px);
  animation: a-c 16s ease-in-out infinite;
}
@keyframes a-a { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(40px,30px) scale(1.04); } }
@keyframes a-b { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-35px,25px) scale(1.03); } }
@keyframes a-c { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(25px,-30px) scale(1.05); } }
@media (prefers-reduced-motion: reduce) { .aurora-blob { animation: none !important; } }

/* ====================== LAYOUT ====================== */
.cal-layout {
  flex: 1;
  display: flex;
  min-width: 0;
  position: relative;
  z-index: 1;
  gap: 0;
}

/* ---- Left Sidebar ---- */
.cal-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 16px;
  border-right: 1px solid rgba(255,255,255,0.04);
  overflow-y: auto;
}

/* Mini Calendar */
.mini-cal-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  padding: 16px;
  backdrop-filter: blur(12px);
}
.mini-cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.mini-cal-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.88);
}
.mini-cal-nav { display: flex; gap: 2px; }
.mini-nav-btn {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px; cursor: pointer;
  transition: background 0.12s;
}
.mini-nav-btn:hover { background: rgba(255,255,255,0.08); }
.mini-nav-icon { width: 14px; height: 14px; color: rgba(255,255,255,0.5); }

.mini-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); margin-bottom: 4px; }
.mini-wd {
  text-align: center; font-size: 10px; font-weight: 600;
  color: rgba(255,255,255,0.28); padding: 4px 0;
  text-transform: uppercase; letter-spacing: 0.5px;
}

.mini-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; }
.mini-day {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; cursor: pointer;
  transition: background 0.1s;
  position: relative;
}
.mini-day:hover { background: rgba(255,255,255,0.06); }
.mini-day-num { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.65); }
.mini-day-other .mini-day-num { color: rgba(255,255,255,0.18); }
.mini-day-today {
  background: #3B82F6;
  border-radius: 8px;
}
.mini-day-today .mini-day-num { color: #fff; font-weight: 700; }
.mini-day-selected { background: rgba(99,73,234,0.2); }
.mini-day-selected .mini-day-num { color: #a78bfa; font-weight: 600; }
.mini-day-today.mini-day-selected { background: #3B82F6; }
.mini-day-today.mini-day-selected .mini-day-num { color: #fff; }
.mini-day-has-event::after {
  content: '';
  position: absolute; bottom: 3px; left: 50%;
  transform: translateX(-50%);
  width: 4px; height: 4px; border-radius: 50%;
  background: #818cf8;
}
.mini-day-today.mini-day-has-event::after { background: rgba(255,255,255,0.6); }

/* Upcoming */
.upcoming-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  padding: 16px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  backdrop-filter: blur(12px);
}
.upcoming-header { margin-bottom: 12px; }
.upcoming-title {
  font-size: 13px; font-weight: 600;
  color: rgba(255,255,255,0.5);
  text-transform: uppercase; letter-spacing: 0.8px;
}
.upcoming-list { display: flex; flex-direction: column; gap: 6px; }
.upcoming-item {
  display: flex; align-items: stretch; gap: 10px;
  padding: 10px; border-radius: 10px;
  background: rgba(255,255,255,0.02);
  cursor: pointer; transition: background 0.12s;
}
.upcoming-item:hover { background: rgba(255,255,255,0.05); }
.upcoming-accent {
  width: 3px; border-radius: 3px; flex-shrink: 0;
  background: linear-gradient(180deg, #818cf8, #6366f1);
}
.upcoming-body { flex: 1; min-width: 0; }
.upcoming-event-title {
  font-size: 13px; font-weight: 500;
  color: rgba(255,255,255,0.82);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.upcoming-event-meta {
  font-size: 11px; color: rgba(255,255,255,0.35);
  margin-top: 2px;
}
.upcoming-empty { padding: 24px 0; text-align: center; }
.upcoming-empty-text { font-size: 12px; color: rgba(255,255,255,0.22); }

/* ---- Main Area ---- */
.cal-main {
  flex: 1;
  display: flex; flex-direction: column;
  min-width: 0;
  padding: 20px 24px 0;
  overflow: hidden;
}

/* Header */
.cal-header {
  display: flex; align-items: center;
  justify-content: space-between;
  padding-bottom: 20px; flex-shrink: 0;
}
.cal-header-left { display: flex; align-items: center; gap: 16px; }
.cal-header-title {
  font-size: 24px; font-weight: 700;
  color: rgba(255,255,255,0.92);
  letter-spacing: -0.3px;
}
.cal-header-nav { display: flex; align-items: center; gap: 4px; }
.cal-nav-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; cursor: pointer;
  transition: background 0.12s;
}
.cal-nav-btn:hover { background: rgba(255,255,255,0.07); }
.cal-nav-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.5); }
.today-pill {
  padding: 5px 14px; border-radius: 7px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  cursor: pointer; transition: all 0.12s;
  margin-left: 4px;
}
.today-pill:hover { background: rgba(255,255,255,0.09); border-color: rgba(255,255,255,0.14); }
.today-pill-text { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.6); }

.cal-header-right { display: flex; align-items: center; gap: 10px; }
.view-switcher {
  display: flex; gap: 2px; padding: 3px;
  border-radius: 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}
.view-sw-btn {
  width: 34px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 7px; cursor: pointer;
  transition: all 0.12s;
}
.view-sw-btn:hover { background: rgba(255,255,255,0.06); }
.view-sw-btn.active { background: rgba(99,73,234,0.22); }
.view-sw-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.45); }
.view-sw-btn.active .view-sw-icon { color: #a78bfa; }

.new-event-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 9px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(99,73,234,0.3);
}
.new-event-btn:hover { box-shadow: 0 4px 16px rgba(99,73,234,0.4); transform: translateY(-1px); }
.new-event-icon { width: 14px; height: 14px; color: #fff; }
.new-event-text { font-size: 13px; font-weight: 600; color: #fff; }

/* ====================== MONTH VIEW ====================== */
.month-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.month-weekday-row { display: grid; grid-template-columns: repeat(7, 1fr); }
.month-wd-cell { padding: 10px 0; text-align: center; }
.month-wd-text {
  font-size: 11px; font-weight: 600;
  color: rgba(255,255,255,0.3);
  text-transform: uppercase; letter-spacing: 1px;
}

.month-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  grid-template-rows: repeat(6, 1fr);
  flex: 1; min-height: 0;
  border-top: 1px solid rgba(255,255,255,0.05);
  border-left: 1px solid rgba(255,255,255,0.05);
}
.month-cell {
  border-right: 1px solid rgba(255,255,255,0.05);
  border-bottom: 1px solid rgba(255,255,255,0.05);
  padding: 4px 6px; cursor: pointer;
  display: flex; flex-direction: column;
  transition: background 0.1s;
  overflow: hidden;
}
.month-cell:hover { background: rgba(255,255,255,0.025); }
.month-cell-other { opacity: 0.35; }
.month-cell-selected { background: rgba(99,73,234,0.06); }
.month-cell-today { background: rgba(59,130,246,0.04); }

.month-cell-num {
  font-size: 12px; font-weight: 500;
  color: rgba(255,255,255,0.6);
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; margin-bottom: 2px;
  transition: background 0.1s;
}
.month-cell-num-today {
  background: #3B82F6;
  color: #fff !important; font-weight: 700;
}

.month-cell-events { display: flex; flex-direction: column; gap: 2px; flex: 1; min-height: 0; }
.month-event-pill {
  padding: 2px 6px; border-radius: 4px;
  background: rgba(99,73,234,0.15);
  border-left: 2px solid #818cf8;
  overflow: hidden; cursor: pointer;
  transition: background 0.1s;
}
.month-event-pill:hover { background: rgba(99,73,234,0.25); }
.month-event-pill-text {
  font-size: 10px; font-weight: 500;
  color: rgba(255,255,255,0.72);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.month-event-more {
  font-size: 10px; color: rgba(255,255,255,0.3);
  padding-left: 6px;
}

/* Day Drawer */
.day-drawer {
  border-top: 1px solid rgba(255,255,255,0.06);
  padding: 12px 0 8px;
  max-height: 200px; overflow-y: auto;
  flex-shrink: 0;
}
.day-drawer-bar {
  width: 36px; height: 3px; border-radius: 3px;
  background: rgba(255,255,255,0.12);
  margin: 0 auto 12px;
}
.day-drawer-header {
  display: flex; align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px; padding: 0 4px;
}
.day-drawer-date { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.82); }
.day-drawer-count { font-size: 11px; color: rgba(255,255,255,0.3); }

.day-drawer-list { display: flex; flex-direction: column; gap: 4px; }
.drawer-event {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 10px;
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.04);
  transition: background 0.1s;
}
.drawer-event:hover { background: rgba(255,255,255,0.05); }
.drawer-event-stripe {
  width: 3px; height: 100%; min-height: 32px;
  border-radius: 3px; flex-shrink: 0;
  background: linear-gradient(180deg, #818cf8, #6366f1);
}
.drawer-event-info { flex: 1; min-width: 0; }
.drawer-event-time {
  font-size: 11px; font-weight: 600;
  color: #818cf8; font-variant-numeric: tabular-nums;
}
.drawer-event-title {
  font-size: 13px; font-weight: 500;
  color: rgba(255,255,255,0.82);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.drawer-event-desc {
  font-size: 11px; color: rgba(255,255,255,0.35);
  margin-top: 1px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.drawer-event-actions {
  display: flex; gap: 2px;
  opacity: 0; transition: opacity 0.12s;
}
.drawer-event:hover .drawer-event-actions { opacity: 1; }
.drawer-action {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px; cursor: pointer; transition: background 0.1s;
}
.drawer-action:hover { background: rgba(255,255,255,0.08); }
.drawer-action-del:hover { background: rgba(239,68,68,0.12); }
.drawer-action-icon { width: 13px; height: 13px; color: rgba(255,255,255,0.4); }
.drawer-action-del .drawer-action-icon { color: rgba(239,68,68,0.6); }

.drawer-slide-enter-active { transition: all 0.2s ease-out; }
.drawer-slide-leave-active { transition: all 0.15s ease-in; }
.drawer-slide-enter-from,
.drawer-slide-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; }

/* ====================== WEEK VIEW ====================== */
.week-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.week-cols-header {
  display: flex; flex-shrink: 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.week-gutter-header { width: 52px; flex-shrink: 0; }
.week-col-header {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; padding: 8px 0 10px;
}
.week-col-dayname {
  font-size: 10px; font-weight: 600;
  color: rgba(255,255,255,0.3);
  text-transform: uppercase; letter-spacing: 0.8px;
}
.week-col-num-wrap {
  margin-top: 4px;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
}
.week-col-num {
  font-size: 16px; font-weight: 600;
  color: rgba(255,255,255,0.7);
}
.week-col-num-today {
  background: #3B82F6;
}
.week-col-num-today .week-col-num {
  color: #fff; font-weight: 700;
}
.week-col-today .week-col-dayname { color: #3B82F6; }

.week-scroll { flex: 1; overflow-y: auto; }
.week-body { display: flex; position: relative; min-height: 1344px; }
.week-time-col { width: 52px; flex-shrink: 0; }
.week-time-row { height: 56px; display: flex; align-items: flex-start; }
.week-time-lbl {
  font-size: 10px; font-weight: 500;
  color: rgba(255,255,255,0.22);
  font-variant-numeric: tabular-nums;
  width: 100%; text-align: right;
  padding-right: 10px;
  transform: translateY(-5px);
}

.week-days-grid { flex: 1; display: flex; }
.week-day-col {
  flex: 1; position: relative;
  border-left: 1px solid rgba(255,255,255,0.04);
}
.week-hour-line {
  height: 56px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

/* Current time indicator */
.week-now-line {
  position: absolute; left: 0; right: 0;
  height: 2px; z-index: 3;
  background: #ef4444;
}
.week-now-dot {
  position: absolute; left: -4px; top: -3px;
  width: 8px; height: 8px; border-radius: 50%;
  background: #ef4444;
}

/* Week events */
.week-evt {
  position: absolute;
  left: 3px; right: 3px;
  background: rgba(99,73,234,0.16);
  border-left: 3px solid #818cf8;
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer; overflow: hidden;
  transition: all 0.12s;
  z-index: 2;
  backdrop-filter: blur(8px);
}
.week-evt:hover {
  background: rgba(99,73,234,0.28);
  box-shadow: 0 2px 12px rgba(99,73,234,0.2);
}
.week-evt-title {
  font-size: 11px; font-weight: 600;
  color: rgba(255,255,255,0.85);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.week-evt-time {
  font-size: 10px; color: rgba(255,255,255,0.4);
  font-variant-numeric: tabular-nums;
}

/* ====================== MODAL ====================== */
.modal-wrapper {
  position: absolute; inset: 0;
  z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.65);
}
.modal-panel {
  position: relative;
  width: 460px; max-width: 92vw;
  background: #1e1e2e;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 24px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04) inset;
}
.modal-top {
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}
.modal-heading {
  font-size: 17px; font-weight: 600;
  color: rgba(255,255,255,0.9);
}
.modal-x {
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; cursor: pointer;
  transition: background 0.1s;
}
.modal-x:hover { background: rgba(255,255,255,0.07); }
.modal-x-icon { width: 16px; height: 16px; color: rgba(255,255,255,0.4); }

.modal-form { padding: 20px 24px; }
.field { margin-bottom: 16px; }
.field-row { display: flex; gap: 12px; }
.field-half { flex: 1; }
.field-label {
  display: block;
  font-size: 11px; font-weight: 600;
  color: rgba(255,255,255,0.35);
  margin-bottom: 6px;
  text-transform: uppercase; letter-spacing: 0.8px;
}
.field-input {
  width: 100%; height: auto; padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.85);
  font-size: 14px; outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}
.field-input:focus {
  border-color: rgba(99,73,234,0.5);
  box-shadow: 0 0 0 3px rgba(99,73,234,0.1);
}
.field-input-lg { font-size: 16px; font-weight: 500; padding: 12px 14px; }
.datetime-display {
  cursor: pointer; display: flex; align-items: center;
}
.datetime-display:hover {
  border-color: rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.07);
}
.datetime-text { color: rgba(255,255,255,0.85); font-size: 14px; }


.field-textarea {
  width: 100%; height: auto; min-height: 80px;
  padding: 10px 14px; border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.85);
  font-size: 14px; outline: none;
  resize: vertical; font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}
.field-textarea:focus {
  border-color: rgba(99,73,234,0.5);
  box-shadow: 0 0 0 3px rgba(99,73,234,0.1);
}

.modal-actions {
  display: flex; justify-content: flex-end;
  gap: 8px; padding: 0 24px 20px;
}
.modal-act-btn {
  padding: 9px 20px; border-radius: 9px;
  cursor: pointer; transition: all 0.12s;
}
.modal-act-ghost {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}
.modal-act-ghost:hover { background: rgba(255,255,255,0.09); }
.modal-act-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 2px 8px rgba(99,73,234,0.3);
}
.modal-act-primary:hover {
  box-shadow: 0 4px 16px rgba(99,73,234,0.4);
}
.modal-act-disabled { opacity: 0.4; pointer-events: none; }
.modal-act-text { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.9); }

/* ====================== DATETIME PICKER ====================== */
.dtp-mask {
  position: absolute; inset: 0;
  z-index: 2000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.5);
}
.dtp-panel {
  width: 320px; max-width: 90vw;
  background: #1a1a2e;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  padding: 20px;
}
.dtp-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}
.dtp-nav-btn {
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; cursor: pointer;
  transition: background 0.12s;
}
.dtp-nav-btn:hover { background: rgba(255,255,255,0.08); }
.dtp-nav-icon { width: 14px; height: 14px; color: rgba(255,255,255,0.5); }
.dtp-title {
  font-size: 15px; font-weight: 600;
  color: rgba(255,255,255,0.88);
}
.dtp-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); margin-bottom: 4px; }
.dtp-wd {
  text-align: center; font-size: 10px; font-weight: 600;
  color: rgba(255,255,255,0.28); padding: 4px 0;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.dtp-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 16px; }
.dtp-day {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; cursor: pointer;
  transition: background 0.1s;
}
.dtp-day:hover { background: rgba(255,255,255,0.06); }
.dtp-day-num { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.65); }
.dtp-day-other .dtp-day-num { color: rgba(255,255,255,0.18); }
.dtp-day-other { pointer-events: none; }
.dtp-day-sel {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
}
.dtp-day-sel .dtp-day-num { color: #fff; font-weight: 700; }
.dtp-day-today { border: 1px solid rgba(59,130,246,0.4); }
.dtp-day-today .dtp-day-num { color: #60a5fa; }
.dtp-day-sel.dtp-day-today { border-color: transparent; }
.dtp-day-sel.dtp-day-today .dtp-day-num { color: #fff; }

/* Time row */
.dtp-time-row {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; margin-bottom: 18px;
  padding: 12px 0;
  border-top: 1px solid rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.dtp-time-group {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.dtp-time-btn {
  width: 36px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px; cursor: pointer;
  transition: background 0.12s;
}
.dtp-time-btn:hover { background: rgba(255,255,255,0.08); }
.dtp-time-icon { width: 14px; height: 14px; color: rgba(255,255,255,0.4); }
.dtp-time-val {
  font-size: 28px; font-weight: 700;
  color: rgba(255,255,255,0.9);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.dtp-time-colon {
  font-size: 28px; font-weight: 700;
  color: rgba(255,255,255,0.4);
  line-height: 1;
  margin-top: 2px;
}

/* Actions */
.dtp-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dtp-act-btn {
  padding: 8px 18px; border-radius: 8px;
  cursor: pointer; transition: all 0.12s;
}
.dtp-act-cancel {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}
.dtp-act-cancel:hover { background: rgba(255,255,255,0.09); }
.dtp-act-ok {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 2px 8px rgba(99,73,234,0.3);
}
.dtp-act-ok:hover { box-shadow: 0 4px 16px rgba(99,73,234,0.4); }
.dtp-act-text { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.9); }

</style>

