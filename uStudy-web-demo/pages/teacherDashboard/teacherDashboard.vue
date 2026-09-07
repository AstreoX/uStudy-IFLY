<template>
  <view class="teacher-page">
    <view class="ambient ambient-a"></view>
    <view class="ambient ambient-b"></view>

    <HomeSidebar
      :collapsed="sidebarCollapsed"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
      @select-space="openStudySpace"
    />

    <view class="workspace">
      <view class="topbar">
        <view class="title-block">
          <text class="eyebrow">{{ selectedSpaceName }} · 教师视图</text>
          <text class="page-title">教学复盘</text>
          <text class="page-subtitle">按真实学习记录观察参与、覆盖和理解变化</text>
        </view>
        <view class="topbar-controls">
          <TeacherSpaceSelector
            :spaces="teacherSpaces"
            :space-id="spaceId"
            @change="handleTeacherSpaceChange"
          />
          <view class="range-switch" aria-label="统计周期">
            <view
              v-for="option in dayOptions"
              :key="option"
              class="range-option"
              :class="{ active: days === option }"
              @tap="changeDays(option)"
            >{{ formatDayOption(option) }}</view>
          </view>
          <view class="refresh-button" :class="{ spinning: loading }" @tap="refreshCurrent">↻</view>
        </view>
      </view>

      <view class="section-tabs">
        <view
          v-for="tab in tabs"
          :key="tab.id"
          class="section-tab"
          :class="{ active: activeTab === tab.id }"
          @tap="switchTab(tab.id)"
        >{{ tab.label }}</view>
      </view>

      <scroll-view scroll-y class="content-scroll">
        <view v-if="errorMessage" class="state-message error-state">
          <text>{{ errorMessage }}</text>
          <view class="retry-link" @tap="refreshCurrent">重新加载</view>
        </view>
        <view v-else-if="loading && !activeData" class="state-message">
          <view class="loading-line"></view>
          <text>正在汇总教学数据…</text>
        </view>

        <view v-else-if="activeTab === 'overview' && overview" class="view-content reveal">
          <view class="metric-strip">
            <view class="metric-cell">
              <text class="metric-label">活跃学生</text>
              <text class="metric-value">{{ overview.active_students }}<text class="metric-denominator"> / {{ overview.students_total }}</text></text>
              <text class="metric-context">{{ metric(overview.active_rate) }} · {{ compareText(overview.active_rate, overview.active_rate_previous) }}</text>
            </view>
            <view class="metric-cell">
              <text class="metric-label">知识覆盖率</text>
              <text class="metric-value">{{ metric(overview.knowledge_coverage) }}</text>
              <text class="metric-context">{{ overview.assessed_pairs }} 个学生-知识点记录</text>
            </view>
            <view class="metric-cell">
              <text class="metric-label">已评估平均掌握度</text>
              <text class="metric-value">{{ metric(overview.avg_mastery) }}</text>
              <text class="metric-context">缺失记录不按 0 分计算</text>
            </view>
            <view class="metric-cell">
              <text class="metric-label">测验正确率</text>
              <text class="metric-value">{{ metric(overview.quiz_accuracy) }}</text>
              <text class="metric-context">{{ overview.quiz_participants }} 人 · {{ overview.quiz_attempts }} 次完成</text>
            </view>
          </view>

          <view class="analysis-panel calendar-panel">
            <view class="panel-heading calendar-heading">
              <view>
                <text class="panel-title">最近 90 天学习活跃日历</text>
                <text class="panel-note">固定 90 天窗口 · 颜色可切换班级参与率或活动总量 · 点击日期固定详情</text>
              </view>
              <view class="chart-toggle">
                <view class="chart-toggle-option" :class="{ active: heatmapMetric === 'active_rate' }" @tap="heatmapMetric = 'active_rate'">活跃学生率</view>
                <view class="chart-toggle-option" :class="{ active: heatmapMetric === 'activity_count' }" @tap="heatmapMetric = 'activity_count'">活动次数</view>
              </view>
            </view>
            <scroll-view scroll-x class="calendar-scroll">
              <TeacherEChart
                :option="calendarOption"
                :empty="overview.students_total === 0"
                empty-text="当前课程暂无学生"
                :height="250"
                :min-width="780"
                @chart-click="handleCalendarClick"
              />
            </scroll-view>
            <view v-if="selectedCalendarPoint" class="calendar-inspector">
              <view class="calendar-inspector-date">
                <text>{{ selectedCalendarPoint.date }}</text>
                <text>已固定</text>
              </view>
              <view><text>活跃学生</text><strong>{{ selectedCalendarPoint.active_students }} / {{ overview.students_total }}</strong></view>
              <view><text>活跃学生率</text><strong>{{ metric(selectedCalendarPoint.active_rate) }}</strong></view>
              <view><text>活动次数</text><strong>{{ selectedCalendarPoint.activity_count }}</strong></view>
              <view class="calendar-inspector-mix"><text>活动类型</text><strong>{{ calendarMixText(selectedCalendarPoint) }}</strong></view>
            </view>
          </view>

          <view class="analysis-grid">
            <view class="analysis-panel wide-panel">
              <view class="panel-heading">
                <view>
                  <text class="panel-title">每日学习活动</text>
                  <text class="panel-note">柱高表示活动次数，悬停可查看活跃人数</text>
                </view>
                <text class="period-label">{{ periodLabel(overview.period) }}</text>
              </view>
              <TeacherEChart
                :option="activityTrendOption"
                :empty="!hasDailyActivity"
                empty-text="本周期暂无学习活动"
                :height="270"
              />
            </view>
            <view class="analysis-panel">
              <view class="panel-heading">
                <view>
                  <text class="panel-title">活动构成</text>
                  <text class="panel-note">按学习记录类型汇总</text>
                </view>
              </view>
              <TeacherEChart
                :option="activityDonutOption"
                :empty="overview.activity_mix.length === 0"
                empty-text="本周期暂无活动构成"
                :height="270"
              />
            </view>
          </view>

          <view class="comparison-band">
            <view class="comparison-copy">
              <text class="panel-title">本周知识状态</text>
              <text class="panel-note">历史从教师看板上线时的基线开始，基线前不推测变化</text>
            </view>
            <view class="comparison-item">
              <text class="comparison-label">覆盖率</text>
              <text class="comparison-value">{{ metric(overview.knowledge_coverage) }}</text>
              <text class="comparison-delta">{{ compareText(overview.knowledge_coverage, overview.knowledge_coverage_previous) }}</text>
            </view>
            <view class="comparison-item">
              <text class="comparison-label">平均掌握度</text>
              <text class="comparison-value">{{ metric(overview.avg_mastery) }}</text>
              <text class="comparison-delta">{{ compareText(overview.avg_mastery, overview.avg_mastery_previous) }}</text>
            </view>
          </view>
        </view>

        <view v-else-if="activeTab === 'knowledge' && knowledge" class="view-content reveal">
          <view v-if="days >= 30" class="analysis-grid trend-grid">
            <view class="analysis-panel">
              <view class="panel-heading"><view><text class="panel-title">掌握度趋势</text><text class="panel-note">仅统计已有评估记录</text></view></view>
              <TeacherEChart :option="masteryTrendOption" :empty="!hasMasteryTrend" :height="220" empty-text="暂无足够数据形成趋势" />
            </view>
            <view class="analysis-panel">
              <view class="panel-heading"><view><text class="panel-title">覆盖率趋势</text><text class="panel-note">已评估学生-知识点记录占全部组合</text></view></view>
              <TeacherEChart :option="coverageTrendOption" :empty="!hasCoverageTrend" :height="220" empty-text="暂无足够数据形成趋势" />
            </view>
          </view>

          <view class="analysis-panel knowledge-landscape-panel">
            <view class="panel-heading">
              <view><text class="panel-title">知识点分布</text><text class="panel-note">{{ knowledgeLandscape.mode === 'scatter' ? '覆盖率 × 掌握度，点大小表示已评估人数' : '有效节点不足 8 个，已自动降级为掌握度条形图' }}</text></view>
              <text class="period-label">{{ knowledgeLandscape.mode === 'scatter' ? '关系视图' : '稀疏数据模式' }}</text>
            </view>
            <TeacherEChart :option="knowledgeLandscape.option" :empty="knowledgeLandscape.empty" :height="340" empty-text="暂无已评估知识点" />
          </view>

          <view class="table-section">
            <view class="panel-heading"><view><text class="panel-title">全部知识点</text><text class="panel-note">共 {{ knowledge.nodes.length }} 个固定节点，暂无评估与 0 分严格区分</text></view></view>
            <scroll-view scroll-x class="table-scroll">
              <view class="data-table knowledge-table">
                <view class="table-row table-head">
                  <text>知识点</text><text>章节</text><text>已评估</text><text>覆盖率</text><text>平均掌握度</text><text>掌握人数</text>
                </view>
                <view v-for="node in knowledge.nodes" :key="node.node_id" class="table-row">
                  <text class="primary-cell">{{ node.label }}</text><text>{{ node.chapter }}</text><text>{{ node.assessed_students }} 人</text><text>{{ metric(node.coverage_rate) }}</text><text>{{ metric(node.avg_mastery) }}</text><text>{{ node.mastered_students }} 人</text>
                </view>
              </view>
            </scroll-view>
          </view>
        </view>

        <view v-else-if="activeTab === 'students' && students" class="view-content reveal">
          <view class="student-tools">
            <view class="search-box">
              <text class="search-icon">⌕</text>
              <input :value="studentSearch" placeholder="搜索学生昵称" confirm-type="search" @input="handleSearchInput" @confirm="loadStudents(true)" />
            </view>
            <picker :range="sortLabels" :value="sortIndex" @change="changeSort">
              <view class="sort-picker">排序：{{ sortLabels[sortIndex] }}⌄</view>
            </picker>
          </view>
          <view class="table-section student-table-section">
            <scroll-view scroll-x class="table-scroll">
              <view class="data-table student-table">
                <view class="table-row table-head">
                  <text>学生</text><text>最后活跃</text><text>活跃天数</text><text>知识覆盖</text><text>平均掌握度</text><text>测验正确率</text><text></text>
                </view>
                <view v-for="student in students.items" :key="student.user_id" class="table-row clickable-row" @tap="openStudent(student)">
                  <text class="primary-cell">{{ student.nickname }}</text><text>{{ dateTime(student.last_active_at) }}</text><text>{{ student.active_days }} 天</text><text>{{ metric(student.coverage_rate) }} · {{ student.assessed_node_count }} 节点</text><text>{{ metric(student.avg_mastery) }}</text><text>{{ metric(student.quiz_accuracy) }}</text><text class="row-action">查看 →</text>
                </view>
                <view v-if="students.items.length === 0" class="table-empty">没有符合条件的学生</view>
              </view>
            </scroll-view>
          </view>
          <view class="pagination">
            <view class="page-button" :class="{ disabled: students.page <= 1 }" @tap="changePage(-1)">上一页</view>
            <text>第 {{ students.page }} 页 · 共 {{ students.total }} 人</text>
            <view class="page-button" :class="{ disabled: students.page * students.page_size >= students.total }" @tap="changePage(1)">下一页</view>
          </view>
        </view>
        <view class="bottom-space"></view>
      </scroll-view>
    </view>

    <view v-if="detailOpen" class="drawer-backdrop" @tap="closeDetail"></view>
    <view class="detail-drawer" :class="{ open: detailOpen }">
      <view class="drawer-header">
        <view><text class="eyebrow">学生学习详情</text><text class="drawer-title">{{ studentDetail?.student?.nickname || selectedStudent?.nickname || '加载中' }}</text></view>
        <view class="drawer-close" @tap="closeDetail">×</view>
      </view>
      <scroll-view scroll-y class="drawer-scroll">
        <view v-if="detailLoading" class="state-message"><text>正在读取学生记录…</text></view>
        <view v-else-if="studentDetail" class="drawer-content">
          <view class="detail-metrics">
            <view><text>知识覆盖</text><strong>{{ metric(studentDetail.student.coverage_rate) }}</strong></view>
            <view><text>平均掌握度</text><strong>{{ metric(studentDetail.student.avg_mastery) }}</strong></view>
            <view><text>活跃天数</text><strong>{{ studentDetail.student.active_days }}</strong></view>
          </view>
          <view class="drawer-section">
            <text class="drawer-section-title">掌握度趋势</text>
            <TeacherEChart :option="studentTrendOption" :empty="!hasStudentTrend" :height="210" empty-text="暂无足够数据形成趋势" />
          </view>
          <view class="drawer-section">
            <text class="drawer-section-title">近期学习摘要</text>
            <view v-if="studentDetail.learning_summaries.length === 0" class="drawer-empty">本周期暂无学习摘要</view>
            <view v-for="summary in studentDetail.learning_summaries" :key="summary.id" class="summary-item">
              <view class="summary-top"><text class="summary-type">{{ summary.activity_type }}</text><text>{{ dateTime(summary.activity_time) }}</text></view>
              <text class="summary-title">{{ summary.title }}</text>
              <text class="summary-body">{{ summary.summary }}</text>
              <text v-if="summary.related_node_labels.length" class="summary-nodes">{{ summary.related_node_labels.join(' · ') }}</text>
            </view>
          </view>
          <view class="drawer-section">
            <text class="drawer-section-title">近期测验概况</text>
            <view v-if="studentDetail.recent_quizzes.length === 0" class="drawer-empty">本周期暂无已完成测验</view>
            <view v-for="quiz in studentDetail.recent_quizzes" :key="quiz.quiz_id" class="quiz-item">
              <view class="summary-top"><text class="summary-title">{{ quiz.title }}</text><strong>{{ metric(quiz.score_percent) }}</strong></view>
              <text v-if="quiz.weaknesses.length" class="quiz-note">薄弱点：{{ quiz.weaknesses.join('；') }}</text>
              <text v-if="quiz.suggestions.length" class="quiz-note">建议：{{ quiz.suggestions.join('；') }}</text>
            </view>
          </view>
          <view class="drawer-section">
            <text class="drawer-section-title">章节掌握度</text>
            <TeacherEChart :option="studentChapterChart.option" :empty="studentChapterChart.empty" :height="260" empty-text="暂无章节掌握度数据" />
          </view>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import TeacherEChart from '@/components/teacher/TeacherEChart.vue'
import TeacherSpaceSelector from '@/components/teacher/TeacherSpaceSelector.vue'
import { getTeacherKnowledge, getTeacherOverview, getTeacherStudentDetail, getTeacherStudents } from '@/api/teacher'
import { useSpacesStore } from '@/store/spaces'
import {
  getTeacherSpaces,
  resolveTeacherSpace,
  rememberTeacherSpace,
  TEACHER_SPACE_TOOLS
} from '@/utils/teacher-space-selection'
import {
  buildActivityDonutOption,
  buildActivityTrendOption,
  buildCalendarHeatmapOption,
  buildKnowledgeLandscape,
  buildStudentChapterOption,
  buildTrendOption
} from '@/utils/teacher-chart-options'

const TEACHER_ROUTE = '/pages/teacherDashboard/teacherDashboard'

export default {
  components: { HomeSidebar, TeacherEChart, TeacherSpaceSelector },
  data() {
    return {
      sidebarCollapsed: false,
      spacesStore: useSpacesStore(),
      spaceId: '',
      days: 7,
      heatmapMetric: 'active_rate',
      selectedCalendarDate: null,
      dayOptions: [7, 30, 90, 365],
      tabs: [
        { id: 'overview', label: '班级概览' },
        { id: 'knowledge', label: '知识点' },
        { id: 'students', label: '学生' }
      ],
      activeTab: 'overview',
      overview: null,
      knowledge: null,
      students: null,
      loading: false,
      errorMessage: '',
      requestVersion: 0,
      detailRequestVersion: 0,
      studentSearch: '',
      studentPage: 1,
      sortKeys: ['last_active', 'coverage', 'mastery', 'quiz_accuracy'],
      sortLabels: ['最后活跃', '知识覆盖', '平均掌握度', '测验正确率'],
      sortIndex: 0,
      detailOpen: false,
      detailLoading: false,
      selectedStudent: null,
      studentDetail: null
    }
  },
  computed: {
    teacherSpaces() {
      return getTeacherSpaces(this.spacesStore.spaces)
    },
    selectedSpace() {
      return this.teacherSpaces.find(space => String(space.id) === String(this.spaceId)) || null
    },
    selectedSpaceName() {
      return this.selectedSpace?.name || '课程空间'
    },
    activeData() {
      return this.activeTab === 'overview' ? this.overview : this.activeTab === 'knowledge' ? this.knowledge : this.students
    },
    calendarOption() {
      return buildCalendarHeatmapOption(
        this.overview?.activity_calendar || [],
        this.heatmapMetric,
        this.selectedCalendarDate,
        this.overview?.students_total || 0
      )
    },
    selectedCalendarPoint() {
      if (!this.selectedCalendarDate || !this.overview) return null
      return this.overview.activity_calendar.find(item => item.date === this.selectedCalendarDate) || null
    },
    hasDailyActivity() {
      return !!this.overview?.daily_activity?.some(item => Number(item.activity_count) > 0)
    },
    activityTrendOption() {
      return buildActivityTrendOption(this.overview?.daily_activity || [])
    },
    activityDonutOption() {
      return buildActivityDonutOption(this.overview?.activity_mix || [])
    },
    masteryTrendOption() {
      return buildTrendOption(this.knowledge?.trend || [], 'avg_mastery')
    },
    coverageTrendOption() {
      return buildTrendOption(this.knowledge?.trend || [], 'coverage_rate')
    },
    hasMasteryTrend() {
      return (this.knowledge?.trend || []).filter(item => item.avg_mastery != null).length >= 2
    },
    hasCoverageTrend() {
      return (this.knowledge?.trend || []).filter(item => item.coverage_rate != null).length >= 2
    },
    knowledgeLandscape() {
      return buildKnowledgeLandscape(this.knowledge?.nodes || [])
    },
    studentTrendOption() {
      return buildTrendOption(this.studentDetail?.mastery_trend || [], 'avg_mastery')
    },
    hasStudentTrend() {
      return (this.studentDetail?.mastery_trend || []).filter(item => item.avg_mastery != null).length >= 2
    },
    studentChapterChart() {
      return buildStudentChapterOption(this.studentDetail?.knowledge_nodes || [])
    }
  },
  async onLoad(options) {
    await this.spacesStore.loadSpaces(true)
    const resolved = resolveTeacherSpace({
      spaces: this.spacesStore.spaces,
      requestedSpaceId: options?.spaceId,
      tool: TEACHER_SPACE_TOOLS.DASHBOARD
    })
    if (resolved.invalidRequested) {
      uni.showToast({ title: '指定课程空间无效或已无权限', icon: 'none' })
    }
    if (!resolved.space) {
      uni.showToast({ title: '当前账号没有可管理的课程空间', icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
      return
    }
    this.spaceId = String(resolved.space.id)
    if (resolved.shouldCanonicalize) {
      uni.reLaunch({ url: `${TEACHER_ROUTE}?spaceId=${encodeURIComponent(this.spaceId)}` })
      return
    }
    this.loadActive()
  },
  beforeUnmount() {
    this.requestVersion += 1
    this.detailRequestVersion += 1
  },
  methods: {
    handleTeacherSpaceChange(space) {
      if (!space?.id || String(space.id) === String(this.spaceId)) return
      this.requestVersion += 1
      this.detailRequestVersion += 1
      this.detailOpen = false
      this.studentDetail = null
      this.selectedStudent = null
      this.selectedCalendarDate = null
      this.studentPage = 1
      this.studentSearch = ''
      this.spaceId = String(space.id)
      rememberTeacherSpace(TEACHER_SPACE_TOOLS.DASHBOARD, space.id)
      this.replaceRouteSpaceId(this.spaceId)

      // Keep the currently visible dataset in place until its replacement
      // arrives. This avoids tearing down every ECharts instance while the
      // native picker is still completing its close animation.
      if (this.activeTab !== 'overview') this.overview = null
      if (this.activeTab !== 'knowledge') this.knowledge = null
      if (this.activeTab !== 'students') this.students = null
      this.loadActive()
    },
    replaceRouteSpaceId(spaceId) {
      if (typeof window === 'undefined' || !window.history?.replaceState) return
      const url = new URL(window.location.href)
      url.hash = `${TEACHER_ROUTE}?spaceId=${encodeURIComponent(spaceId)}`
      window.history.replaceState(window.history.state, '', url.toString())
    },
    formatDayOption(days) {
      return days === 365 ? '近 1 年' : `${days} 天`
    },
    metric(value) {
      return value === null || value === undefined ? '暂无数据' : `${Number(value).toFixed(1)}%`
    },
    compareText(current, previous) {
      if (current === null || current === undefined || previous === null || previous === undefined) return '无可比基线'
      const delta = Number(current) - Number(previous)
      if (Math.abs(delta) < 0.05) return '与上期持平'
      return `${delta > 0 ? '较上期 +' : '较上期 '}${delta.toFixed(1)} 个百分点`
    },
    periodLabel(period) {
      return period ? `${period.start_date} — ${period.end_date}` : ''
    },
    calendarMixText(point) {
      const mix = point?.activity_mix || []
      return mix.length ? mix.map(item => `${item.activity_type} ${item.count}`).join(' · ') : '无活动'
    },
    handleCalendarClick(params) {
      const date = Array.isArray(params?.data?.value) ? params.data.value[0] : params?.value?.[0]
      if (!date) return
      this.selectedCalendarDate = this.selectedCalendarDate === date ? null : date
    },
    dateTime(value) {
      if (!value) return '暂无记录'
      const date = new Date(value)
      return date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
    async runRequest(loader) {
      const version = ++this.requestVersion
      this.loading = true
      this.errorMessage = ''
      try {
        const data = await loader()
        if (version === this.requestVersion) return data
      } catch (error) {
        if (version !== this.requestVersion) return null
        if (error?.statusCode === 403 || error?.statusCode === 404) {
          uni.showToast({ title: '当前账号没有教师看板权限', icon: 'none' })
          setTimeout(() => uni.reLaunch({ url: `/pages/study/study?spaceId=${encodeURIComponent(this.spaceId)}` }), 600)
          return null
        }
        this.errorMessage = typeof error?.message === 'string' ? error.message : '教学数据加载失败，请稍后重试'
        return null
      } finally {
        if (version === this.requestVersion) this.loading = false
      }
    },
    async loadOverview() {
      const data = await this.runRequest(() => getTeacherOverview(this.spaceId, this.days))
      if (data) {
        this.overview = data
        if (this.selectedCalendarDate && !data.activity_calendar.some(item => item.date === this.selectedCalendarDate)) {
          this.selectedCalendarDate = null
        }
      }
    },
    async loadKnowledge() {
      const data = await this.runRequest(() => getTeacherKnowledge(this.spaceId, this.days))
      if (data) this.knowledge = data
    },
    async loadStudents(resetPage = false) {
      if (resetPage) this.studentPage = 1
      const data = await this.runRequest(() => getTeacherStudents(this.spaceId, {
        days: this.days,
        search: this.studentSearch.trim() || undefined,
        page: this.studentPage,
        page_size: 25,
        sort: this.sortKeys[this.sortIndex]
      }))
      if (data) this.students = data
    },
    loadActive() {
      if (this.activeTab === 'overview') return this.loadOverview()
      if (this.activeTab === 'knowledge') return this.loadKnowledge()
      return this.loadStudents()
    },
    switchTab(tab) {
      if (this.activeTab === tab) return
      this.activeTab = tab
      this.errorMessage = ''
      if (!this.activeData) this.loadActive()
    },
    changeDays(days) {
      if (this.days === days) return
      this.days = days
      if (this.activeTab !== 'overview') this.overview = null
      if (this.activeTab !== 'knowledge') this.knowledge = null
      if (this.activeTab !== 'students') this.students = null
      this.studentPage = 1
      this.loadActive()
      if (this.detailOpen && this.selectedStudent) this.loadStudentDetail(this.selectedStudent.user_id)
    },
    refreshCurrent() {
      if (this.loading) return
      this.loadActive()
    },
    handleSearchInput(event) {
      this.studentSearch = event.detail.value
    },
    changeSort(event) {
      this.sortIndex = Number(event.detail.value)
      this.loadStudents(true)
    },
    changePage(delta) {
      if (!this.students) return
      const next = this.studentPage + delta
      if (next < 1 || (delta > 0 && this.studentPage * this.students.page_size >= this.students.total)) return
      this.studentPage = next
      this.loadStudents()
    },
    openStudySpace(spaceId) {
      uni.reLaunch({ url: `/pages/study/study?spaceId=${spaceId}` })
    },
    openStudent(student) {
      this.selectedStudent = student
      this.studentDetail = null
      this.detailOpen = true
      this.loadStudentDetail(student.user_id)
    },
    async loadStudentDetail(studentId) {
      const version = ++this.detailRequestVersion
      const requestedSpaceId = this.spaceId
      this.detailLoading = true
      try {
        const detail = await getTeacherStudentDetail(requestedSpaceId, studentId, this.days)
        if (version === this.detailRequestVersion && requestedSpaceId === this.spaceId) {
          this.studentDetail = detail
        }
      } catch (_) {
        if (version === this.detailRequestVersion) {
          uni.showToast({ title: '学生详情加载失败', icon: 'none' })
        }
      } finally {
        if (version === this.detailRequestVersion) this.detailLoading = false
      }
    },
    closeDetail() {
      this.detailOpen = false
      this.detailRequestVersion += 1
    }
  }
}
</script>

<style scoped>
.teacher-page { width: 100vw; height: 100vh; display: flex; overflow: hidden; position: relative; background: var(--color-bg); color: #f8fafc; }
.ambient { position: fixed; border-radius: 50%; pointer-events: none; will-change: transform; }
.ambient-a { width: 760px; height: 760px; left: -10%; top: -28%; background: radial-gradient(circle, rgba(59,130,246,.32) 0%, rgba(59,130,246,.12) 45%, transparent 75%); filter: blur(90px); animation: aurora-drift-a 12s ease-in-out infinite; }
.ambient-b { width: 620px; height: 620px; right: -12%; top: 8%; background: radial-gradient(circle, rgba(249,115,22,.22) 0%, rgba(249,115,22,.09) 45%, transparent 75%); filter: blur(70px); opacity: 1; animation: aurora-drift-b 10s ease-in-out infinite; }
.teacher-page::after { content: ''; position: fixed; z-index: 0; width: 700px; height: 700px; left: 28%; bottom: -34%; border-radius: 50%; background: radial-gradient(circle, rgba(79,70,229,.2) 0%, rgba(79,70,229,.08) 45%, transparent 75%); filter: blur(90px); pointer-events: none; animation: aurora-drift-c 14s ease-in-out infinite; }
.workspace { flex: 1; min-width: 0; height: 100vh; display: flex; flex-direction: column; position: relative; z-index: 1; }
.topbar { min-height: 116px; padding: 28px 38px 20px; display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; border-bottom: 1px solid rgba(148,163,184,.11); background: rgba(24,24,37,.34); backdrop-filter: blur(20px); }
.title-block { display: flex; flex-direction: column; }
.eyebrow { color: #60a5fa; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.page-title { margin-top: 5px; font-size: 28px; line-height: 1.2; font-weight: 700; letter-spacing: -.03em; }
.page-subtitle { margin-top: 7px; color: #7c8aa0; font-size: 13px; }
.topbar-controls { display: flex; align-items: center; gap: 12px; }
.range-switch { display: flex; padding: 3px; background: rgba(15,23,42,.68); border: 1px solid rgba(148,163,184,.13); border-radius: 9px; }
.range-option { min-width: 52px; padding: 7px 10px; text-align: center; color: #7c8aa0; font-size: 12px; border-radius: 6px; cursor: pointer; transition: .18s ease; }
.range-option.active { color: #eff6ff; background: rgba(59,130,246,.24); }
.refresh-button { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; color: #94a3b8; border: 1px solid rgba(148,163,184,.16); border-radius: 8px; cursor: pointer; }
.refresh-button:hover { color: #fff; border-color: rgba(96,165,250,.45); }
.refresh-button.spinning { animation: spin .8s linear infinite; }
.section-tabs { display: flex; gap: 28px; padding: 0 38px; border-bottom: 1px solid rgba(148,163,184,.1); background: rgba(24,24,37,.26); backdrop-filter: blur(18px); }
.section-tab { position: relative; padding: 15px 0 14px; color: #64748b; font-size: 13px; cursor: pointer; }
.section-tab.active { color: #e2e8f0; }
.section-tab.active::after { content: ''; position: absolute; height: 2px; left: 0; right: 0; bottom: -1px; background: #60a5fa; }
.content-scroll { flex: 1; min-height: 0; }
.view-content { padding: 30px 38px 0; max-width: 1480px; margin: 0 auto; box-sizing: border-box; }
.metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid rgba(255,255,255,.12); border-bottom: 1px solid rgba(255,255,255,.12); background: rgba(42,42,60,.3); backdrop-filter: blur(18px); border-radius: 14px; }
.metric-cell { min-height: 116px; padding: 20px 24px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid rgba(148,163,184,.13); }
.metric-cell:first-child { padding-left: 0; }
.metric-cell:last-child { border-right: 0; }
.metric-label, .comparison-label { color: #7c8aa0; font-size: 11px; letter-spacing: .03em; }
.metric-value { margin-top: 8px; font-size: 30px; line-height: 1; font-weight: 650; letter-spacing: -.035em; font-variant-numeric: tabular-nums; }
.metric-denominator { color: #64748b; font-size: 16px; font-weight: 500; }
.metric-context { margin-top: 10px; color: #64748b; font-size: 11px; }
.analysis-grid { margin-top: 34px; display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(280px, .75fr); gap: 38px; }
.analysis-panel { min-width: 0; padding-top: 18px; border-top: 1px solid rgba(255,255,255,.15); background: rgba(42,42,60,.22); backdrop-filter: blur(16px); border-radius: 14px; box-shadow: inset 0 1px 0 rgba(255,255,255,.035); }
.calendar-panel { margin-top: 36px; padding-top: 20px; }
.calendar-heading { align-items: center; }
.calendar-scroll { width: 100%; }
.chart-toggle { display: flex; padding: 3px; flex: 0 0 auto; border: 1px solid rgba(148,163,184,.14); border-radius: 8px; background: rgba(15,23,42,.54); }
.chart-toggle-option { min-width: 76px; padding: 7px 10px; color: #64748B; font-size: 10px; text-align: center; border-radius: 5px; cursor: pointer; transition: color .18s ease, background .18s ease; }
.chart-toggle-option.active { color: #EFF6FF; background: rgba(37,99,235,.28); }
.calendar-inspector { margin-top: 14px; min-height: 54px; display: grid; grid-template-columns: 1.15fr .8fr .8fr .65fr 1.6fr; align-items: center; gap: 20px; padding: 12px 14px; border-top: 1px solid rgba(246,200,95,.22); border-bottom: 1px solid rgba(148,163,184,.1); animation: reveal .22s ease both; }
.calendar-inspector > view { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.calendar-inspector text { color: #64748B; font-size: 9px; }
.calendar-inspector strong { color: #E2E8F0; font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.calendar-inspector-date text:first-child { color: #F6C85F; font-size: 13px; font-weight: 650; }
.calendar-inspector-date text:last-child { color: #64748B; font-size: 9px; }
.panel-heading { min-height: 45px; display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 16px; }
.panel-heading > view { display: flex; flex-direction: column; }
.panel-title, .drawer-section-title { color: #e2e8f0; font-size: 14px; font-weight: 650; }
.panel-note { margin-top: 5px; color: #64748b; font-size: 11px; }
.period-label { color: #64748b; font-size: 10px; white-space: nowrap; }
.comparison-band { margin-top: 38px; padding: 22px 18px; display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 54px; border-top: 1px solid rgba(255,255,255,.14); border-bottom: 1px solid rgba(255,255,255,.14); background: rgba(42,42,60,.22); backdrop-filter: blur(16px); border-radius: 14px; }
.comparison-copy { display: flex; flex-direction: column; }
.comparison-item { min-width: 155px; display: grid; grid-template-columns: 1fr auto; gap: 5px 18px; }
.comparison-value { font-size: 22px; font-weight: 650; font-variant-numeric: tabular-nums; }
.comparison-delta { grid-column: 1 / -1; color: #64748b; font-size: 10px; }
.trend-grid { grid-template-columns: 1fr 1fr; }
.knowledge-landscape-panel { margin-top: 36px; }
.table-section { margin-top: 40px; padding-top: 18px; border-top: 1px solid rgba(255,255,255,.15); background: rgba(42,42,60,.22); backdrop-filter: blur(16px); border-radius: 14px; }
.table-scroll { width: 100%; }
.data-table { min-width: 980px; }
.table-row { min-height: 48px; display: grid; align-items: center; gap: 18px; padding: 0 12px; border-bottom: 1px solid rgba(148,163,184,.08); color: #94a3b8; font-size: 12px; }
.knowledge-table .table-row { grid-template-columns: 1.35fr 1.1fr .6fr .65fr .8fr .6fr; }
.student-table .table-row { grid-template-columns: 1.1fr .9fr .55fr 1.05fr .75fr .75fr .45fr; }
.table-head { min-height: 38px; color: #536175; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
.primary-cell { color: #e2e8f0; font-weight: 550; }
.clickable-row { cursor: pointer; transition: background .15s ease; }
.clickable-row:hover { background: rgba(96,165,250,.055); }
.row-action { color: #60a5fa; text-align: right; }
.table-empty { min-height: 160px; display: flex; align-items: center; justify-content: center; color: #64748b; }
.student-tools { display: flex; justify-content: space-between; gap: 16px; }
.search-box { width: 320px; height: 38px; padding: 0 12px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid rgba(148,163,184,.25); }
.search-box input { flex: 1; color: #e2e8f0; font-size: 13px; }
.search-icon { color: #64748b; font-size: 18px; }
.sort-picker { height: 38px; display: flex; align-items: center; color: #94a3b8; font-size: 12px; cursor: pointer; }
.student-table-section { margin-top: 20px; }
.pagination { padding: 22px 0; display: flex; justify-content: flex-end; align-items: center; gap: 16px; color: #64748b; font-size: 11px; }
.page-button { padding: 7px 10px; color: #94a3b8; border: 1px solid rgba(148,163,184,.14); border-radius: 6px; cursor: pointer; }
.page-button.disabled { opacity: .35; cursor: default; }
.state-message { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; color: #64748b; font-size: 13px; }
.error-state { color: #fca5a5; }
.retry-link { color: #60a5fa; cursor: pointer; }
.loading-line { width: 120px; height: 2px; position: relative; overflow: hidden; background: rgba(96,165,250,.15); }
.loading-line::after { content: ''; position: absolute; inset: 0; width: 45%; background: #60a5fa; animation: load 1s ease-in-out infinite; }
.bottom-space { height: 48px; }
.drawer-backdrop { position: fixed; inset: 0; z-index: 90; background: rgba(3,7,18,.54); backdrop-filter: blur(2px); }
.detail-drawer { position: fixed; z-index: 100; right: 0; top: 0; bottom: 0; width: min(620px, 92vw); display: flex; flex-direction: column; background: rgba(42,42,60,.78); border-left: 1px solid rgba(255,255,255,.16); backdrop-filter: blur(24px); transform: translateX(100%); transition: transform .24s ease; }
.detail-drawer.open { transform: translateX(0); }
.drawer-header { min-height: 92px; padding: 22px 28px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(148,163,184,.1); }
.drawer-header > view:first-child { display: flex; flex-direction: column; }
.drawer-title { margin-top: 5px; color: #f8fafc; font-size: 22px; font-weight: 650; }
.drawer-close { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 24px; cursor: pointer; }
.drawer-scroll { flex: 1; min-height: 0; }
.drawer-content { padding: 26px 28px 60px; }
.detail-metrics { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid rgba(148,163,184,.13); border-bottom: 1px solid rgba(148,163,184,.13); }
.detail-metrics > view { padding: 16px 12px; display: flex; flex-direction: column; border-right: 1px solid rgba(148,163,184,.1); }
.detail-metrics > view:last-child { border-right: 0; }
.detail-metrics text { color: #64748b; font-size: 10px; }
.detail-metrics strong { margin-top: 7px; color: #e2e8f0; font-size: 20px; }
.drawer-section { margin-top: 30px; padding-top: 16px; border-top: 1px solid rgba(148,163,184,.12); }
.drawer-section-title { display: block; margin-bottom: 14px; }
.summary-item, .quiz-item { padding: 14px 0; border-bottom: 1px solid rgba(148,163,184,.08); }
.summary-top { display: flex; justify-content: space-between; gap: 16px; color: #64748b; font-size: 10px; }
.summary-type { color: #60a5fa; }
.summary-title { display: block; margin-top: 7px; color: #e2e8f0; font-size: 13px; font-weight: 600; }
.summary-body, .quiz-note { display: block; margin-top: 7px; color: #94a3b8; font-size: 12px; line-height: 1.65; }
.summary-nodes { display: block; margin-top: 8px; color: #64748b; font-size: 10px; }
.drawer-empty { min-height: 90px; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 12px; }
.reveal { animation: reveal .24s ease both; }
@keyframes reveal { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
@keyframes load { from { transform: translateX(-100%); } to { transform: translateX(250%); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes aurora-drift-a { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(50px,35px) scale(1.06); } 66% { transform: translate(-25px,15px) scale(.97); } }
@keyframes aurora-drift-b { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(-40px,30px) scale(1.05); } 66% { transform: translate(20px,-25px) scale(.98); } }
@keyframes aurora-drift-c { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(30px,-35px) scale(1.07); } 66% { transform: translate(-20px,20px) scale(.96); } }
@media (max-width: 1000px) {
  .teacher-page :deep(.sidebar) { display: none; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .topbar-controls { width: 100%; flex-wrap: wrap; }
  .metric-strip { grid-template-columns: 1fr 1fr; }
  .metric-cell:nth-child(2) { border-right: 0; }
  .metric-cell:nth-child(-n+2) { border-bottom: 1px solid rgba(148,163,184,.13); }
  .analysis-grid, .trend-grid { grid-template-columns: 1fr; }
  .calendar-inspector { grid-template-columns: repeat(2, 1fr); }
  .calendar-inspector-mix { grid-column: 1 / -1; }
  .comparison-band { grid-template-columns: 1fr 1fr; gap: 24px; }
  .comparison-copy { grid-column: 1 / -1; }
}
@media (max-width: 720px) {
  .topbar { padding: 20px 18px 16px; align-items: flex-start; flex-direction: column; }
  .page-subtitle { display: none; }
  .topbar-controls { width: 100%; flex-wrap: wrap; justify-content: space-between; }
  .topbar-controls :deep(.teacher-space-selector) { width: 100%; }
  .section-tabs { padding: 0 18px; gap: 22px; }
  .view-content { padding: 22px 18px 0; }
  .calendar-heading { align-items: flex-start; flex-direction: column; }
  .chart-toggle { width: 100%; box-sizing: border-box; }
  .chart-toggle-option { flex: 1; }
  .metric-strip { grid-template-columns: 1fr; }
  .metric-cell { padding-left: 0; border-right: 0; border-bottom: 1px solid rgba(148,163,184,.13); }
  .metric-cell:last-child { border-bottom: 0; }
  .comparison-band { grid-template-columns: 1fr; }
  .student-tools { align-items: stretch; flex-direction: column; }
  .search-box { width: auto; }
  .detail-metrics { grid-template-columns: 1fr; }
  .detail-metrics > view { border-right: 0; border-bottom: 1px solid rgba(148,163,184,.08); }
}
</style>
