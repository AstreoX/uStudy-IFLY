<template>
  <view class="assignment-page">
    <view class="ambient ambient-a"></view>
    <view class="ambient ambient-b"></view>
    <home-sidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" />

    <view class="workspace">
      <view class="topbar">
        <view class="title-block">
          <text class="eyebrow">TEACHING · ASSIGNMENTS</text>
          <text class="page-title">作业管理</text>
          <text class="page-subtitle">生成、发布并复核「数据结构」课程作业</text>
        </view>
        <view class="top-actions">
          <view class="quiet-button" :class="{ spinning: loading }" @tap="loadAssignments">↻</view>
          <view class="primary-button" @tap="openGenerator"><text>＋</text><text>布置作业</text></view>
        </view>
      </view>

      <scroll-view scroll-y class="content-scroll">
        <view class="content-shell">
          <view class="metric-strip">
            <view class="metric"><text>全部作业</text><strong>{{ assignments.length }}</strong></view>
            <view class="metric"><text>已发布</text><strong>{{ publishedCount }}</strong></view>
            <view class="metric"><text>待复核答卷</text><strong class="violet">{{ totalReviewRequired }}</strong></view>
            <view class="metric"><text>平均提交率</text><strong>{{ averageSubmissionRate }}%</strong></view>
          </view>

          <view class="filter-row">
            <view class="filters">
              <view v-for="item in filters" :key="item.value" class="filter" :class="{ active: filter === item.value }" @tap="filter = item.value">
                {{ item.label }} <text>{{ countByStatus(item.value) }}</text>
              </view>
            </view>
            <text class="course-note">课程 · 数据结构</text>
          </view>

          <view v-if="loading && !assignments.length" class="state-view">
            <view class="loading-line"></view><text>正在读取作业</text>
          </view>
          <view v-else-if="errorMessage && !assignments.length" class="state-view error-state">
            <text>{{ errorMessage }}</text><text class="retry-link" @tap="loadAssignments">重新加载</text>
          </view>
          <view v-else-if="!filteredAssignments.length" class="state-view">
            <text class="empty-mark">A</text><strong>{{ filter === 'all' ? '还没有作业' : '当前分类没有作业' }}</strong>
            <text>{{ filter === 'all' ? '让 AI 起草一份作业，再由你确认发布。' : '切换分类查看其他作业。' }}</text>
          </view>

          <view v-else class="assignment-list">
            <view v-for="assignment in filteredAssignments" :key="assignment.id" class="assignment-row" @tap="openAssignment(assignment)">
              <view class="row-accent"></view>
              <view class="assignment-main">
                <view class="assignment-heading">
                  <text class="assignment-title">{{ assignment.title }}</text>
                  <text class="status-chip" :class="`status-${assignment.status}`">{{ statusLabel(assignment.status) }}</text>
                </view>
                <text class="assignment-description">{{ assignment.instructions || '暂无作业说明' }}</text>
                <view class="assignment-meta">
                  <text>{{ assignment.question_count }} 题</text><text>·</text>
                  <text>{{ assignment.total_points }} 分</text><text>·</text>
                  <text>{{ difficultyLabel(assignment.difficulty) }}</text><text>·</text>
                  <text>{{ assignment.deadline ? `截止 ${formatDate(assignment.deadline)}` : '未设置截止时间' }}</text>
                </view>
              </view>
              <view class="submission-progress">
                <view class="progress-label"><text>提交进度</text><strong>{{ assignment.submitted_count }}/{{ assignment.recipient_count }}</strong></view>
                <view class="progress-track"><view :style="{ width: `${submissionRate(assignment)}%` }"></view></view>
                <text v-if="assignment.review_required_count" class="review-note">{{ assignment.review_required_count }} 份待复核</text>
                <text v-else class="review-note muted">查看详情 →</text>
              </view>
            </view>
          </view>
          <view class="bottom-space"></view>
        </view>
      </scroll-view>
    </view>

    <view v-if="panelOpen" class="panel-backdrop" @tap="closePanel"></view>
    <view class="side-panel" :class="{ open: panelOpen }">
      <view class="panel-header">
        <view><text class="eyebrow">{{ panelEyebrow }}</text><text class="panel-title">{{ panelTitle }}</text></view>
        <view class="close-button" @tap="closePanel">×</view>
      </view>

      <scroll-view scroll-y class="panel-scroll">
        <view v-if="panelMode === 'generate'" class="panel-body">
          <view v-if="generationJob" class="generation-state">
            <view class="generation-orbit"><view></view></view>
            <text class="generation-title">{{ generationJob.status === 'partial_failed' ? 'AI 起草部分完成' : 'AI 正在起草作业' }}</text>
            <text class="generation-note">正在组织题目、参考答案与评分标准。页面可保持打开，完成后会自动进入编辑。</text>
            <text class="job-status">{{ jobStatusLabel }}</text>
            <view class="generation-progress" v-if="generationProgress.total">
              <view class="progress-summary"><text>已处理 {{ generationProgress.processed }}/{{ generationProgress.total }} 题</text><strong>{{ generationProgress.percent }}%</strong></view>
              <view class="progress-track generation-track"><view :style="{ width: `${generationProgress.percent}%` }"></view></view>
              <text v-if="generationProgress.current !== null" class="progress-current">正在生成第 {{ generationProgress.current + 1 }} 题</text>
            </view>
            <view v-if="generationProgress.failed.length" class="generation-failures">
              <view v-for="failure in generationProgress.failed" :key="failure.index" class="generation-failure">
                <view><strong>第 {{ failure.index + 1 }} 题</strong><text>{{ failure.error || '生成失败' }}</text></view>
                <view class="retry-question" :class="{ disabled: retryingQuestionIndex !== null }" @tap.stop="retryGenerationQuestion(failure.index)">{{ retryingQuestionIndex === failure.index ? '重试中…' : '重试' }}</view>
              </view>
            </view>
            <view v-if="generationError" class="inline-error">{{ generationError }}</view>
            <view v-if="generationError" class="secondary-button" @tap="resetGenerator">返回修改</view>
          </view>
          <template v-else>
            <view class="form-section">
              <text class="section-title">基本信息</text>
              <label class="field"><text>作业标题</text><input v-model="generator.title" maxlength="80" placeholder="例如：线性表与栈阶段练习" /></label>
              <label class="field"><text>作业要求</text><textarea v-model="generator.instructions" maxlength="1200" placeholder="说明覆盖范围、考查重点，以及希望 AI 如何出题" /></label>
              <view class="field-grid">
                <label class="field"><text>难度</text><picker :range="difficultyOptions" range-key="label" @change="generator.difficulty = difficultyOptions[$event.detail.value].value"><view class="picker-value">{{ difficultyLabel(generator.difficulty) }}⌄</view></picker></label>
                <label class="field"><text>截止时间</text><input type="datetime-local" v-model="generator.deadlineLocal" /></label>
              </view>
            </view>
            <view class="form-section">
              <view class="section-heading"><text class="section-title">题型与分值</text><text>共 {{ generationQuestionCount }} 题 · {{ generationTotalPoints }} 分</text></view>
              <view v-for="type in availableQuestionTypes" :key="type.value" class="type-row">
                <view><strong>{{ type.label }}</strong><text>{{ type.note }}</text></view>
                <label><text>题数</text><input type="number" min="0" max="30" v-model.number="generator.counts[type.value]" /></label>
                <label><text>每题</text><input type="number" min="1" max="100" v-model.number="generator.points[type.value]" /><text>分</text></label>
              </view>
            </view>
            <view v-if="generationError" class="inline-error">{{ generationError }}</view>
          </template>
        </view>

        <view v-else-if="panelMode === 'detail'" class="panel-body">
          <view v-if="detailLoading" class="state-view compact"><view class="loading-line"></view><text>读取作业详情</text></view>
          <template v-else-if="selectedAssignment">
            <view class="assignment-summary">
              <view class="summary-field"><text>状态</text><strong>{{ statusLabel(selectedAssignment.status) }}</strong></view>
              <view class="summary-field"><text>题目</text><strong>{{ selectedAssignment.question_count }} 题 / {{ selectedAssignment.total_points }} 分</strong></view>
              <view class="summary-field"><text>截止</text><strong>{{ formatDate(selectedAssignment.deadline, true) }}</strong></view>
            </view>
            <template v-if="selectedAssignment.status === 'draft'">
              <view class="form-section editor-section">
                <text class="section-title">作业设置</text>
                <label class="field"><text>标题</text><input v-model="selectedAssignment.title" maxlength="80" /></label>
                <label class="field"><text>说明</text><textarea v-model="selectedAssignment.instructions" maxlength="1200" /></label>
                <view class="field-grid">
                  <label class="field"><text>难度</text><picker :range="difficultyOptions" range-key="label" @change="selectedAssignment.difficulty = difficultyOptions[$event.detail.value].value"><view class="picker-value">{{ difficultyLabel(selectedAssignment.difficulty) }}⌄</view></picker></label>
                  <label class="field"><text>截止时间</text><input type="datetime-local" :value="selectedDeadlineLocal" @input="setSelectedDeadline" /></label>
                </view>
              </view>
              <view class="question-editor">
                <view class="section-heading"><text class="section-title">题目编辑</text><text>{{ selectedAssignment.questions.length }} 题</text></view>
                <view v-for="(question, index) in selectedAssignment.questions" :key="question.id" class="question-block">
                  <view class="question-head"><text>第 {{ index + 1 }} 题 · {{ questionTypeLabel(question.question_type) }}</text><label><input type="number" min="1" v-model.number="question.points" /><text>分</text></label></view>
                  <label class="field"><text>题干</text><textarea v-model="question.prompt" maxlength="3000" /></label>
                  <view v-if="['single_choice','multiple_choice'].includes(question.question_type)" class="options-editor">
                    <label v-for="(_, optionIndex) in question.options" :key="optionIndex" class="option-input">
                      <text>{{ optionLetter(optionIndex) }}</text><input v-model="question.options[optionIndex]" />
                    </label>
                  </view>
                  <label v-if="question.question_type !== 'code'" class="field"><text>{{ question.question_type === 'short_answer' ? '参考答案' : '正确答案' }}</text><textarea v-if="question.question_type === 'short_answer'" v-model="question.answer" /><input v-else v-model="question.answer" placeholder="多选题用逗号分隔，如 A,C" /></label>
                  <label v-if="question.question_type === 'short_answer'" class="field"><text>评分标准</text><textarea v-model="question.rubric" placeholder="列出得分点及对应分值" /></label>
                  <template v-if="question.question_type === 'code'">
                    <label class="field"><text>题解说明（截止后向学生开放）</text><textarea v-model="question.answer" maxlength="5000" placeholder="说明算法思路、复杂度与边界情况" /></label>
                    <TeacherOjProblemEditor
                      v-if="ojEnabled"
                      :space-id="spaceId"
                      :assignment-id="selectedAssignment.id"
                      :question="question"
                      @state-change="updateOjQuestion(question, $event)"
                    />
                    <view v-else class="oj-disabled-panel"><strong>判题服务未启用</strong><text>当前仍可查看和编辑题面，但不能修改测试数据、验证参考解或发布含编程题的草稿。</text></view>
                  </template>
                </view>
              </view>
              <view v-if="selectedAssignment.generation_failures && selectedAssignment.generation_failures.length" class="generation-failures draft-failures">
                <view class="section-heading"><text class="section-title">待重试题目</text><text>{{ selectedAssignment.generation_failures.length }} 题失败</text></view>
                <view v-for="failure in selectedAssignment.generation_failures" :key="failure.index" class="generation-failure">
                  <view><strong>第 {{ Number(failure.index) + 1 }} 题生成失败</strong><text :title="failure.error">{{ failure.error || '未提供具体错误' }}</text></view>
                  <view class="retry-question" :class="{ disabled: retryingQuestionIndex !== null || !selectedAssignment.generation_job_id }" @tap.stop="retryDraftQuestion(failure.index)">{{ retryingQuestionIndex === failure.index ? '重试中…' : '重试' }}</view>
                </view>
                <view v-if="generationError" class="inline-error draft-generation-error">{{ generationError }}</view>
              </view>
            </template>
            <template v-else>
              <view class="assignment-tabs">
                <view :class="{ active: detailTab === 'overview' }" @tap="detailTab = 'overview'">概览</view>
                <view :class="{ active: detailTab === 'submissions' }" @tap="showSubmissions">学生答卷</view>
              </view>
              <view v-if="detailTab === 'overview'" class="published-overview">
                <view class="submission-hero"><strong>{{ submissionRate(selectedAssignment) }}%</strong><text>提交率 · {{ selectedAssignment.submitted_count }}/{{ selectedAssignment.recipient_count }}</text></view>
                <view class="overview-line"><text>已完成批改</text><strong>{{ selectedAssignment.graded_count }}</strong></view>
                <view class="overview-line"><text>需要教师复核</text><strong class="violet">{{ selectedAssignment.review_required_count }}</strong></view>
                <view class="overview-line"><text>发布时间</text><strong>{{ formatDate(selectedAssignment.published_at, true) }}</strong></view>
                <view v-if="selectedAssignment.status === 'published'" class="form-section published-settings">
                  <text class="section-title">发布设置</text>
                  <label class="field"><text>标题</text><input v-model="selectedAssignment.title" maxlength="80" /></label>
                  <label class="field"><text>说明</text><textarea v-model="selectedAssignment.instructions" maxlength="1200" /></label>
                  <label class="field"><text>延长截止时间</text><input type="datetime-local" :value="selectedDeadlineLocal" @input="setSelectedDeadline" /></label>
                  <text class="settings-note">发布后题目保持锁定，截止时间只能向后延长。</text>
                </view>
              </view>
              <view v-else class="submission-list">
                <view v-if="submissionsLoading" class="state-view compact"><view class="loading-line"></view></view>
                <view v-else-if="!submissions.length" class="state-view compact"><text>暂无学生记录</text></view>
                <view v-for="submission in submissions" :key="submission.id || submission.student_id" class="submission-row" :class="{ inert: !canOpenSubmission(submission) }" @tap="canOpenSubmission(submission) && openSubmission(submission)">
                  <view class="student-avatar">{{ submission.student_name.slice(0, 1) }}</view>
                  <view class="student-main"><strong>{{ submission.student_name }}</strong><text>{{ submissionStatusLabel(submission.status) }} · {{ formatDate(submission.submitted_at) }}</text></view>
                  <view class="score-cell"><strong>{{ displayScore(submission) }}</strong><text v-if="submission.review_required">待复核</text><text v-else>查看 →</text></view>
                  <view class="row-actions" @tap.stop>
                    <view v-if="['grading_failed','failed'].includes(submission.status)" @tap="regrade(submission)">重试</view>
                    <view @tap="openDeadline(submission)">延期</view>
                  </view>
                </view>
              </view>
            </template>
          </template>
        </view>

        <view v-else-if="panelMode === 'submission'" class="panel-body">
          <view v-if="submissionLoading" class="state-view compact"><view class="loading-line"></view><text>读取学生答卷</text></view>
          <template v-else-if="activeSubmission">
            <view class="student-banner"><view class="student-avatar large">{{ activeSubmission.student_name.slice(0, 1) }}</view><view><strong>{{ activeSubmission.student_name }}</strong><text>{{ submissionStatusLabel(activeSubmission.status) }} · {{ formatDate(activeSubmission.submitted_at, true) }}</text></view><view class="big-score">{{ displayScore(activeSubmission) }}</view></view>
            <view v-for="(answer, index) in activeSubmission.answers" :key="answer.id || index" class="review-block">
              <view class="review-head"><text>第 {{ index + 1 }} 题</text><label><input type="number" min="0" :max="answer.max_score || answer.max_points || answer.points" v-model.number="answer.review_score" /><text>/ {{ answer.max_score || answer.max_points || answer.points || 0 }} 分</text></label></view>
              <text class="review-prompt">{{ answer.prompt || answer.question_stem || answer.question_prompt || '题目' }}</text>
              <template v-if="answer.question_type === 'code' || answer.type === 'code'">
                <view class="submission-oj-summary"><view class="validation-dot" :class="`validation-${normalizeVerdict(answer.grader_result?.verdict || answer.status)}`"></view><strong>{{ verdictLabel(answer.grader_result?.verdict || answer.status) }}</strong><text v-if="answer.grader_result?.time_ms !== undefined">{{ answer.grader_result.time_ms }} ms</text><text v-if="answer.grader_result?.memory_kb !== undefined">{{ formatMemory(answer.grader_result.memory_kb) }}</text></view>
                <view v-if="ojGroups(answer).length" class="submission-oj-groups"><view v-for="(group, groupIndex) in ojGroups(answer)" :key="group.id || group.name || groupIndex"><view><strong>{{ group.name || `测试组 ${groupIndex + 1}` }}</strong><text>{{ verdictLabel(group.verdict || group.status) }}</text></view><strong>{{ group.score ?? 0 }}/{{ group.max_score ?? 0 }}</strong></view></view>
                <pre v-if="answer.grader_result?.compile_output" class="review-code compile-output">{{ answer.grader_result.compile_output }}</pre>
                <view class="answer-band code-band"><text>学生代码 · {{ languageLabel((answer.answer ?? answer.student_answer)?.language) }}</text><pre class="review-code">{{ (answer.answer ?? answer.student_answer)?.source || '未作答' }}</pre></view>
              </template>
              <template v-else>
                <view class="answer-band"><text>学生答案</text><strong>{{ formatAnswer(answer.answer ?? answer.student_answer) }}</strong></view>
                <view class="answer-band reference"><text>参考答案</text><strong>{{ formatAnswer(answer.correct_answer ?? answer.reference_answer) }}</strong></view>
              </template>
              <label class="field"><text>教师评语</text><textarea v-model="answer.review_comment" placeholder="可补充反馈，也可直接确认 AI 评语" /></label>
              <text v-if="answer.ai_feedback || answer.feedback" class="ai-feedback">AI：{{ answer.ai_feedback || answer.feedback }}</text>
            </view>
            <label class="field final-comment"><text>整卷评语</text><textarea v-model="activeSubmission.teacher_comment" placeholder="给学生的整体反馈（可选）" /></label>
          </template>
        </view>
      </scroll-view>

      <view class="panel-footer">
        <template v-if="panelMode === 'generate' && !generationJob"><view class="secondary-button" @tap="closePanel">取消</view><view class="primary-button wide" :class="{ disabled: submitting }" @tap="startGeneration">{{ submitting ? '正在提交…' : '交给 AI 起草' }}</view></template>
        <template v-else-if="panelMode === 'detail' && selectedAssignment?.status === 'draft'"><view class="danger-button" :class="{ disabled: submitting }" @tap="deleteAssignment">删除草稿</view><view class="secondary-button" :class="{ disabled: submitting }" @tap="saveDraft">保存草稿</view><view class="primary-button wide" :class="{ disabled: submitting }" @tap="publishAssignment">确认并发布</view></template>
        <template v-else-if="panelMode === 'detail' && selectedAssignment && !['draft','closed'].includes(selectedAssignment.status)"><view class="secondary-button" :class="{ disabled: submitting }" @tap="savePublishedSettings">保存设置</view><view class="danger-button" :class="{ disabled: submitting }" @tap="closeAssignment">提前关闭作业</view></template>
        <template v-else-if="panelMode === 'submission'"><view class="secondary-button" @tap="backToSubmissions">返回答卷列表</view><view class="primary-button wide" :class="{ disabled: submitting }" @tap="saveReview">确认最终成绩</view></template>
      </view>
    </view>

    <view v-if="deadlineModal.open" class="modal-backdrop" @tap="deadlineModal.open = false">
      <view class="modal" @tap.stop>
        <text class="eyebrow">INDIVIDUAL EXTENSION</text><text class="modal-title">为 {{ deadlineModal.student?.student_name }} 延期</text>
        <label class="field"><text>新的截止时间</text><input type="datetime-local" v-model="deadlineModal.value" /></label>
        <view class="modal-actions"><view class="secondary-button" @tap="deadlineModal.open = false">取消</view><view class="primary-button" @tap="saveDeadline">保存延期</view></view>
      </view>
    </view>
  </view>
</template>

<script>
import HomeSidebar from '@/components/layout/HomeSidebar.vue'
import TeacherOjProblemEditor from '@/components/teacher/TeacherOjProblemEditor.vue'
import { useSpacesStore } from '@/store/spaces'
import {
  listTeacherAssignments, generateTeacherAssignment, getAssignmentJob, getTeacherAssignment,
  updateTeacherAssignment, deleteTeacherAssignment, publishTeacherAssignment, closeTeacherAssignment,
  listAssignmentSubmissions, getAssignmentSubmission, reviewAssignmentSubmission,
  regradeAssignmentSubmission, extendAssignmentDeadline, retryAssignmentQuestion
} from '@/api/teacher-assignments'
import { getOjCapabilities } from '@/api/assignments'

const TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选题', note: '规则自动评分' },
  { value: 'multiple_choice', label: '多选题', note: '全对满分，正确子集半分' },
  { value: 'true_false', label: '判断题', note: '规则自动评分' },
  { value: 'short_answer', label: '简答题', note: 'AI 初评，支持教师复核' },
  { value: 'code', label: '编程题', note: '公开样例试运行，隐藏测试组计分' }
]

function localDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function makeGenerator() {
  const tomorrow = new Date(Date.now() + 7 * 86400000)
  tomorrow.setHours(23, 59, 0, 0)
  return {
    title: '', instructions: '', difficulty: 'medium', deadlineLocal: localDateTime(tomorrow),
    counts: { single_choice: 4, multiple_choice: 2, true_false: 2, short_answer: 2, code: 0 },
    points: { single_choice: 5, multiple_choice: 5, true_false: 5, short_answer: 10, code: 20 }
  }
}

export default {
  components: { HomeSidebar, TeacherOjProblemEditor },
  data() {
    return {
      sidebarCollapsed: false, spaceId: '', loading: false, errorMessage: '', assignments: [], filter: 'all',
      filters: [{ value: 'all', label: '全部' }, { value: 'draft', label: '草稿' }, { value: 'published', label: '进行中' }, { value: 'closed', label: '已关闭' }],
      questionTypes: TYPE_OPTIONS, difficultyOptions: [{ value: 'easy', label: '基础' }, { value: 'medium', label: '适中' }, { value: 'hard', label: '挑战' }],
      panelOpen: false, panelMode: 'generate', detailTab: 'overview', detailLoading: false, submissionsLoading: false, submissionLoading: false, submitting: false,
      generator: makeGenerator(), generationJob: null, generationError: '', jobTimer: null, retryingQuestionIndex: null,
      selectedAssignment: null, submissions: [], activeSubmission: null,
      deadlineModal: { open: false, student: null, value: '' },
      ojCapabilities: { enabled: false, languages: [] }, ojCapabilitiesLoaded: false
    }
  },
  computed: {
    publishedCount() { return this.assignments.filter(item => ['published', 'active'].includes(item.status)).length },
    totalReviewRequired() { return this.assignments.reduce((sum, item) => sum + item.review_required_count, 0) },
    averageSubmissionRate() {
      const published = this.assignments.filter(item => item.recipient_count > 0)
      if (!published.length) return 0
      return Math.round(published.reduce((sum, item) => sum + this.submissionRate(item), 0) / published.length)
    },
    filteredAssignments() {
      if (this.filter === 'all') return this.assignments
      if (this.filter === 'published') return this.assignments.filter(item => ['published', 'active'].includes(item.status))
      return this.assignments.filter(item => item.status === this.filter)
    },
    panelEyebrow() { return this.panelMode === 'generate' ? 'NEW ASSIGNMENT' : this.panelMode === 'submission' ? 'REVIEW SUBMISSION' : 'ASSIGNMENT DETAIL' },
    panelTitle() { return this.panelMode === 'generate' ? 'AI 起草作业' : this.panelMode === 'submission' ? (this.activeSubmission?.student_name || '答卷复核') : (this.selectedAssignment?.title || '作业详情') },
    generationQuestionCount() { return Object.values(this.generator.counts).reduce((sum, value) => sum + (Number(value) || 0), 0) },
    generationTotalPoints() { return Object.keys(this.generator.counts).reduce((sum, key) => sum + (Number(this.generator.counts[key]) || 0) * (Number(this.generator.points[key]) || 0), 0) },
    jobStatusLabel() {
      const status = this.generationJob?.status || 'queued'
      return { queued: '已进入生成队列', pending: '已进入生成队列', running: '正在生成题目', retrying: '正在重试题目', completed: '草稿已生成', partial_failed: '部分题目失败，可单题重试', failed: '生成失败' }[status] || '正在处理'
    },
    generationProgress() {
      const output = this.generationJob?.output_data || {}
      const total = Number(output.total_questions || this.generationQuestionCount || 0)
      const completed = Number(output.completed_questions || 0)
      const failed = Array.isArray(output.failed_questions) ? output.failed_questions : []
      const processed = Math.min(total, completed + failed.length)
      return { total, completed, failed, processed, current: output.current_question === null || output.current_question === undefined ? null : Number(output.current_question), percent: total ? Math.round((processed / total) * 100) : 0 }
    },
    selectedDeadlineLocal() { return localDateTime(this.selectedAssignment?.deadline) },
    ojEnabled() { return this.ojCapabilitiesLoaded && this.ojCapabilities.enabled === true },
    availableQuestionTypes() { return this.ojEnabled ? this.questionTypes : this.questionTypes.filter(type => type.value !== 'code') }
  },
  async onLoad(options) {
    this.spaceId = options?.spaceId || ''
    if (!this.spaceId) {
      const spacesStore = useSpacesStore()
      await spacesStore.loadSpaces(true)
      this.spaceId = spacesStore.spaces.find(space => space.user_role === 'teacher')?.id || ''
    }
    if (!this.spaceId) {
      uni.showToast({ title: '当前账号没有教师权限', icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 600)
      return
    }
    await Promise.all([this.loadOjCapabilities(), this.loadAssignments()])
  },
  beforeUnmount() { this.stopJobPolling() },
  methods: {
    async loadOjCapabilities() {
      try {
        const response = await getOjCapabilities()
        this.ojCapabilities = { enabled: response?.enabled === true, languages: Array.isArray(response?.languages) ? response.languages : [] }
      } catch (_) {
        this.ojCapabilities = { enabled: false, languages: [] }
      } finally {
        this.ojCapabilitiesLoaded = true
        if (!this.ojCapabilities.enabled) this.generator.counts.code = 0
      }
    },
    async loadAssignments() {
      if (this.loading || !this.spaceId) return
      this.loading = true; this.errorMessage = ''
      try {
        const assignments = await listTeacherAssignments(this.spaceId)
        const statistics = await Promise.allSettled(assignments.map(item => item.status === 'draft' ? Promise.resolve(null) : listAssignmentSubmissions(this.spaceId, item.id)))
        this.assignments = assignments.map((item, index) => {
          const payload = statistics[index].status === 'fulfilled' ? statistics[index].value : null
          if (!payload) return item
          return {
            ...item,
            recipient_count: Number(payload.recipient_count || 0),
            submitted_count: Number(payload.submitted_count || 0),
            graded_count: payload.submissions.filter(submission => ['completed', 'graded', 'reviewed'].includes(submission.status)).length,
            review_required_count: payload.submissions.filter(submission => submission.review_required).length
          }
        })
      }
      catch (error) {
        if ([403, 404].includes(error?.statusCode)) {
          uni.showToast({ title: '当前账号没有作业管理权限', icon: 'none' })
          setTimeout(() => uni.reLaunch({ url: `/pages/study/study?spaceId=${encodeURIComponent(this.spaceId)}` }), 600)
        } else this.errorMessage = error?.message || '作业加载失败，请稍后重试'
      } finally { this.loading = false }
    },
    countByStatus(status) { return status === 'all' ? this.assignments.length : status === 'published' ? this.publishedCount : this.assignments.filter(item => item.status === status).length },
    submissionRate(item) { return item.recipient_count ? Math.round((item.submitted_count / item.recipient_count) * 100) : 0 },
    statusLabel(status) { return { draft: '草稿', published: '进行中', active: '进行中', closed: '已关闭', grading: '批改中' }[status] || status },
    difficultyLabel(value) { return { easy: '基础', medium: '适中', hard: '挑战' }[value] || value || '适中' },
    questionTypeLabel(value) { return TYPE_OPTIONS.find(item => item.value === value)?.label || value },
    submissionStatusLabel(status) { return { not_submitted: '未提交', not_started: '未开始', missed: '已错过', in_progress: '作答中', draft: '作答中', pending: '等待批改', submitted: '已提交', grading: '批改中', evaluating: '批改中', completed: 'AI 初评完成', graded: 'AI 初评完成', reviewed: '教师已复核', grading_failed: '批改失败', failed: '批改失败' }[status] || status },
    canOpenSubmission(submission) { return !!submission?.id && !['not_submitted', 'not_started', 'missed', 'in_progress', 'draft'].includes(submission.status) },
    optionLetter(index) { return String.fromCharCode(65 + index) },
    formatDate(value, includeYear = false) {
      if (!value) return '暂无记录'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      return date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', ...(includeYear ? { year: 'numeric' } : {}), month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
    formatAnswer(value) {
      if (Array.isArray(value)) return value.join('、')
      if (value === true || value === false) return value ? '正确' : '错误'
      if (value && typeof value === 'object') {
        if (value.index !== undefined) return this.optionLetter(Number(value.index))
        if (Array.isArray(value.indices)) return value.indices.map(index => this.optionLetter(Number(index))).join('、')
        if (value.value !== undefined) return value.value ? '正确' : '错误'
        return value.reference || value.text || JSON.stringify(value)
      }
      return value || '未作答'
    },
    updateOjQuestion(question, state) {
      question.public_config = state.publicConfig
      question.grader_config = state.graderConfig
      question.reference_solution = state.referenceSolution
      question.oj_validation_status = state.validationStatus
      if (Number.isFinite(Number(state.assignmentVersion)) && this.selectedAssignment) this.selectedAssignment.version = Number(state.assignmentVersion)
    },
    displayScore(submission) { const score = submission.final_score ?? submission.provisional_score; return score === null || score === undefined ? '—' : `${Number(score).toFixed(1)} 分` },
    openGenerator() { this.generator = makeGenerator(); this.generationJob = null; this.generationError = ''; this.panelMode = 'generate'; this.panelOpen = true },
    resetGenerator() { this.stopJobPolling(); this.generationJob = null; this.generationError = ''; this.retryingQuestionIndex = null },
    closePanel() { this.panelOpen = false; this.stopJobPolling(); setTimeout(() => { this.selectedAssignment = null; this.activeSubmission = null }, 250) },
    validateGenerator() {
      if (!this.generator.title.trim()) return '请填写作业标题'
      if (!this.generator.instructions.trim()) return '请填写作业要求'
      if (!this.generator.deadlineLocal || new Date(this.generator.deadlineLocal).getTime() <= Date.now()) return '截止时间必须晚于当前时间'
      if (!this.generationQuestionCount) return '至少设置一道题'
      if (this.generationTotalPoints <= 0) return '作业总分必须大于 0'
      return ''
    },
    async startGeneration() {
      if (this.submitting) return
      this.generationError = this.validateGenerator()
      if (this.generationError) return
      this.submitting = true
      try {
        const payload = await generateTeacherAssignment(this.spaceId, {
          title: this.generator.title.trim(), instructions: this.generator.instructions.trim(),
          difficulty: this.generator.difficulty, due_at: new Date(this.generator.deadlineLocal).toISOString(),
          question_configs: this.availableQuestionTypes.map(type => ({
            question_type: type.value,
            count: Number(this.generator.counts[type.value]) || 0,
            score: Number(this.generator.points[type.value]) || 0
          })).filter(item => item.count > 0)
        })
        const job = payload?.job || payload
        this.generationJob = { ...job, id: String(job?.id || job?.job_id || ''), status: job?.status || 'queued' }
        if (!this.generationJob.id && (payload?.assignment_id || payload?.assignment?.id)) {
          await this.finishGeneration(payload.assignment_id || payload.assignment.id)
        } else this.pollJob()
      } catch (error) { this.generationError = error?.message || '提交生成任务失败，请稍后重试' }
      finally { this.submitting = false }
    },
    pollJob() { this.stopJobPolling(); this.checkJob(); this.jobTimer = setInterval(this.checkJob, 2000) },
    async checkJob() {
      if (!this.generationJob?.id) return
      try {
        const payload = await getAssignmentJob(this.spaceId, this.generationJob.id)
        const job = payload?.job || payload
        this.generationJob = { ...this.generationJob, ...job, id: String(job?.id || job?.job_id || this.generationJob.id) }
        if (this.selectedAssignment && String(this.generationJob.assignment_id || job?.assignment_id || job?.output_data?.assignment_id || '') === String(this.selectedAssignment.id)) {
          this.applyGenerationProgress(this.selectedAssignment, this.generationJob)
        }
        if (['completed', 'succeeded', 'success'].includes(job?.status)) {
          this.retryingQuestionIndex = null
          const assignmentId = job.assignment_id || this.generationJob.assignment_id || job.output_data?.assignment_id || job.result?.assignment_id || job.assignment?.id
          if (!assignmentId) throw new Error('任务完成但未返回作业编号')
          await this.finishGeneration(assignmentId)
        } else if (['failed', 'error', 'partial_failed'].includes(job?.status)) {
          this.stopJobPolling(); this.generationError = job.error || job.error_message || 'AI 生成失败，请修改要求后重试'; this.retryingQuestionIndex = null
        }
      } catch (error) { this.stopJobPolling(); this.retryingQuestionIndex = null; this.generationError = error?.message || '生成状态读取失败，请重新尝试' }
    },
    async retryGenerationQuestion(index) {
      const jobId = this.generationJob?.id || this.selectedAssignment?.generation_job_id
      if (this.retryingQuestionIndex !== null || !jobId) return
      this.retryingQuestionIndex = index; this.generationError = ''
      try {
        const payload = await retryAssignmentQuestion(this.spaceId, jobId, index)
        const job = payload?.job || payload
        this.generationJob = { ...(this.generationJob || {}), ...job, id: String(job?.id || job?.job_id || jobId) }
        this.pollJob()
      } catch (error) { this.generationError = error?.message || '题目重试提交失败，请稍后再试'; this.retryingQuestionIndex = null }
    },
    stopJobPolling() { if (this.jobTimer) clearInterval(this.jobTimer); this.jobTimer = null },
    async finishGeneration(assignmentId) { this.stopJobPolling(); await this.loadAssignments(); await this.openAssignment({ id: assignmentId }) },
    applyGenerationProgress(assignment, source) {
      const wrapper = source || assignment?.generation_progress || {}
      const output = wrapper.output_data || wrapper
      assignment.generation_progress = wrapper
      assignment.generation_job_id = String(wrapper.job_id || wrapper.id || assignment.generation_job_id || '') || null
      assignment.generation_failures = Array.isArray(output.failed_questions) ? output.failed_questions : []
      return assignment
    },
    async retryDraftQuestion(index) {
      if (!this.selectedAssignment?.generation_job_id) return
      this.generationJob = {
        id: this.selectedAssignment.generation_job_id,
        assignment_id: this.selectedAssignment.id,
        status: 'pending',
        output_data: this.selectedAssignment.generation_progress?.output_data || {}
      }
      await this.retryGenerationQuestion(index)
    },
    async openAssignment(assignment) {
      this.panelMode = 'detail'; this.panelOpen = true; this.detailTab = 'overview'; this.detailLoading = true; this.selectedAssignment = null; this.generationError = ''
      try {
        this.selectedAssignment = await getTeacherAssignment(this.spaceId, assignment.id)
        this.applyGenerationProgress(this.selectedAssignment, this.selectedAssignment.generation_progress)
      }
      catch (error) { uni.showToast({ title: error?.message || '作业详情加载失败', icon: 'none' }); this.closePanel() }
      finally { this.detailLoading = false }
    },
    setSelectedDeadline(event) { if (this.selectedAssignment) this.selectedAssignment.deadline = event.detail.value ? new Date(event.detail.value).toISOString() : '' },
    draftPayload() {
      const item = this.selectedAssignment
      return { title: item.title.trim(), instructions: item.instructions.trim(), difficulty: item.difficulty, due_at: item.deadline, version: item.version, questions: item.questions.map((question, index) => ({ id: question.id.startsWith('new-') ? undefined : question.id, question_type: question.question_type, question_stem: question.prompt, options: ['single_choice', 'multiple_choice'].includes(question.question_type) ? question.options : null, correct_answer: this.buildCorrectAnswer(question), rubric: question.rubric || null, max_score: Number(question.points), order_index: index, grader_type: question.question_type === 'code' ? 'oj' : question.grader_type, grader_config: question.grader_config || null, public_config: question.question_type === 'code' ? question.public_config : null })) }
    },
    buildCorrectAnswer(question) {
      const raw = String(question.answer ?? '').trim()
      const optionIndex = token => {
        const normalized = String(token).trim().toUpperCase()
        return /^[A-Z]$/.test(normalized) ? normalized.charCodeAt(0) - 65 : Number(normalized)
      }
      if (question.question_type === 'single_choice') return { index: optionIndex(raw) }
      if (question.question_type === 'multiple_choice') return { indices: raw.split(/[,，、\s]+/).filter(Boolean).map(optionIndex) }
      if (question.question_type === 'true_false') return { value: ['正确', 'true', '对', '1'].includes(raw.toLowerCase()) || ['正确', '对'].includes(raw) }
      if (question.question_type === 'code') return { explanation: raw, reference_solution: question.reference_solution || null }
      return { reference: raw }
    },
    validateDraft(requireOjValidation = false) {
      const item = this.selectedAssignment
      if (!item?.title.trim()) return '作业标题不能为空'
      if (!item.deadline || new Date(item.deadline).getTime() <= Date.now()) return '截止时间必须晚于当前时间'
      if (!item.questions.length) return '作业至少需要一道题'
      if (item.generation_failures && item.generation_failures.length) return '仍有题目生成失败，请先重试失败题目'
      if (item.question_count && item.questions.length < item.question_count) return '题目尚未生成完整，请等待生成或重试失败题目'
      for (let i = 0; i < item.questions.length; i += 1) {
        const q = item.questions[i]
        if (!q.prompt.trim() || q.answer === '' || q.answer === null || q.answer === undefined || Number(q.points) <= 0) return `请完善第 ${i + 1} 题的题干、答案和分值`
        if (q.question_type === 'single_choice') {
          const index = this.buildCorrectAnswer(q).index
          if (!Number.isInteger(index) || index < 0 || index >= q.options.length) return `第 ${i + 1} 题的正确答案不在选项范围内`
        }
        if (q.question_type === 'multiple_choice') {
          const indices = this.buildCorrectAnswer(q).indices
          if (!indices.length || indices.some(index => !Number.isInteger(index) || index < 0 || index >= q.options.length)) return `第 ${i + 1} 题的正确答案不在选项范围内`
        }
        if (q.question_type === 'true_false' && !['正确', '错误', '对', '错', 'true', 'false', '1', '0'].includes(String(q.answer).trim().toLowerCase())) return `第 ${i + 1} 题的答案应为“正确”或“错误”`
        if (q.question_type === 'short_answer' && !q.rubric.trim()) return `请填写第 ${i + 1} 题的评分标准`
        if (q.question_type === 'code' && requireOjValidation) {
          const status = String(q.oj_validation_status || q.grader_config?.validation_status || '').toLowerCase()
          if (!['validated', 'valid', 'completed', 'succeeded'].includes(status)) return `请先验证第 ${i + 1} 题的参考解与测试数据`
          const checksum = q.grader_config?.checksum
          const validatedChecksum = q.grader_config?.validated_checksum
          if (checksum && validatedChecksum && checksum !== validatedChecksum) return `第 ${i + 1} 题已修改，请重新验证参考解`
        }
      }
      return ''
    },
    deleteAssignment() {
      if (this.submitting || !this.selectedAssignment || this.selectedAssignment.status !== 'draft') return
      const assignmentId = this.selectedAssignment.id
      uni.showModal({
        title: '删除草稿',
        content: '删除后将永久移除这份作业草稿和已生成的题目，无法恢复。确定删除吗？',
        confirmText: '删除',
        confirmColor: '#ef4444',
        success: async result => {
          if (!result.confirm) return
          this.submitting = true
          try {
            await deleteTeacherAssignment(this.spaceId, assignmentId)
            uni.showToast({ title: '草稿已删除', icon: 'success' })
            this.closePanel()
            await this.loadAssignments()
          } catch (error) {
            uni.showToast({ title: error?.message || '删除失败，请稍后重试', icon: 'none' })
          } finally {
            this.submitting = false
          }
        }
      })
    },
    async saveDraft(showToast = true) {
      if (this.submitting) return false
      const error = this.validateDraft(); if (error) { uni.showToast({ title: error, icon: 'none' }); return false }
      this.submitting = true
      try { this.selectedAssignment = await updateTeacherAssignment(this.spaceId, this.selectedAssignment.id, this.draftPayload()); if (showToast) uni.showToast({ title: '草稿已保存', icon: 'success' }); await this.loadAssignments(); return true }
      catch (error) { uni.showToast({ title: error?.message || '保存失败', icon: 'none' }); return false }
      finally { this.submitting = false }
    },
    async savePublishedSettings() {
      if (this.submitting || !this.selectedAssignment) return
      if (!this.selectedAssignment.title.trim()) return uni.showToast({ title: '作业标题不能为空', icon: 'none' })
      if (!this.selectedAssignment.deadline || new Date(this.selectedAssignment.deadline).getTime() <= Date.now()) return uni.showToast({ title: '截止时间必须晚于当前时间', icon: 'none' })
      this.submitting = true
      try {
        this.selectedAssignment = await updateTeacherAssignment(this.spaceId, this.selectedAssignment.id, {
          version: this.selectedAssignment.version,
          title: this.selectedAssignment.title.trim(),
          instructions: this.selectedAssignment.instructions.trim(),
          due_at: this.selectedAssignment.deadline
        })
        uni.showToast({ title: '发布设置已保存', icon: 'success' })
        await this.loadAssignments()
      } catch (error) {
        uni.showToast({ title: error?.message || '保存失败', icon: 'none' })
      } finally { this.submitting = false }
    },
    async publishAssignment() {
      if (!this.ojEnabled && this.selectedAssignment?.questions?.some(question => question.question_type === 'code')) {
        uni.showToast({ title: '判题服务未启用，暂不能发布编程题作业', icon: 'none' })
        return
      }
      const publishError = this.validateDraft(true)
      if (publishError) { uni.showToast({ title: publishError, icon: 'none' }); return }
      if (!(await this.saveDraft(false))) return
      uni.showModal({ title: '确认发布作业', content: '发布后题目、答案与分值不可修改，并将布置给课程内全部学生。', confirmText: '确认发布', success: async result => {
        if (!result.confirm) return
        this.submitting = true
        try { await publishTeacherAssignment(this.spaceId, this.selectedAssignment.id); uni.showToast({ title: '作业已发布', icon: 'success' }); await this.loadAssignments(); await this.openAssignment(this.selectedAssignment) }
        catch (error) { uni.showToast({ title: error?.message || '发布失败', icon: 'none' }) }
        finally { this.submitting = false }
      } })
    },
    closeAssignment() {
      uni.showModal({ title: '提前关闭作业', content: '关闭后学生将无法继续提交，并会立即开放标准答案。', confirmText: '确认关闭', success: async result => {
        if (!result.confirm) return
        this.submitting = true
        try { await closeTeacherAssignment(this.spaceId, this.selectedAssignment.id); uni.showToast({ title: '作业已关闭', icon: 'success' }); await this.loadAssignments(); await this.openAssignment(this.selectedAssignment) }
        catch (error) { uni.showToast({ title: error?.message || '关闭失败', icon: 'none' }) }
        finally { this.submitting = false }
      } })
    },
    async showSubmissions() {
      this.detailTab = 'submissions'; this.submissionsLoading = true
      try {
        const payload = await listAssignmentSubmissions(this.spaceId, this.selectedAssignment.id)
        this.submissions = payload.submissions
        this.selectedAssignment.recipient_count = Number(payload.recipient_count ?? this.selectedAssignment.recipient_count)
        this.selectedAssignment.submitted_count = Number(payload.submitted_count ?? this.selectedAssignment.submitted_count)
      }
      catch (error) { uni.showToast({ title: error?.message || '答卷列表加载失败', icon: 'none' }) }
      finally { this.submissionsLoading = false }
    },
    async openSubmission(submission) {
      this.panelMode = 'submission'; this.submissionLoading = true; this.activeSubmission = null
      try {
        const detail = await getAssignmentSubmission(this.spaceId, submission.id)
        detail.student_name = detail.student_name === '学生' ? submission.student_name : detail.student_name
        detail.student_identifier = detail.student_identifier || submission.student_identifier
        detail.answers = detail.answers.map(answer => ({ ...answer, review_score: answer.final_score ?? answer.auto_score ?? answer.provisional_score ?? answer.score ?? 0, review_comment: answer.teacher_comment || answer.review_comment || '' }))
        this.activeSubmission = detail
      } catch (error) { uni.showToast({ title: error?.message || '答卷加载失败', icon: 'none' }); this.panelMode = 'detail' }
      finally { this.submissionLoading = false }
    },
    backToSubmissions() { this.panelMode = 'detail'; this.activeSubmission = null; this.showSubmissions() },
    async saveReview() {
      if (this.submitting || !this.activeSubmission) return
      this.submitting = true
      try {
        await reviewAssignmentSubmission(this.spaceId, this.activeSubmission.id, { teacher_feedback: this.activeSubmission.teacher_comment, confirm_remaining: true, answers: this.activeSubmission.answers.map(answer => ({ answer_id: answer.id, score: Number(answer.review_score), comment: answer.review_comment })) })
        uni.showToast({ title: '最终成绩已保存', icon: 'success' }); await this.loadAssignments(); this.backToSubmissions()
      } catch (error) { uni.showToast({ title: error?.message || '成绩保存失败', icon: 'none' }) }
      finally { this.submitting = false }
    },
    async regrade(submission) { try { await regradeAssignmentSubmission(this.spaceId, submission.id); uni.showToast({ title: '已重新提交批改', icon: 'success' }); await this.showSubmissions() } catch (error) { uni.showToast({ title: error?.message || '重试失败', icon: 'none' }) } },
    openDeadline(submission) { this.deadlineModal = { open: true, student: submission, value: localDateTime(submission.effective_deadline || this.selectedAssignment.deadline) } },
    async saveDeadline() {
      if (!this.deadlineModal.value) return uni.showToast({ title: '请选择新的截止时间', icon: 'none' })
      try { await extendAssignmentDeadline(this.spaceId, this.selectedAssignment.id, this.deadlineModal.student.student_id, new Date(this.deadlineModal.value).toISOString()); this.deadlineModal.open = false; uni.showToast({ title: '延期已保存', icon: 'success' }); await this.showSubmissions() }
      catch (error) { uni.showToast({ title: error?.message || '延期保存失败', icon: 'none' }) }
    },
    normalizeVerdict(value) {
      const raw = String(value || '').toLowerCase().replace(/\s+/g, '_')
      return { ac: 'accepted', wa: 'wrong_answer', ce: 'compile_error', re: 'runtime_error', tle: 'time_limit_exceeded', mle: 'memory_limit_exceeded', ole: 'output_limit_exceeded', correct: 'accepted', wrong: 'wrong_answer' }[raw] || raw
    },
    verdictLabel(value) {
      return { accepted: '通过', wrong_answer: '答案错误', compile_error: '编译错误', runtime_error: '运行错误', time_limit_exceeded: '超时', memory_limit_exceeded: '内存超限', output_limit_exceeded: '输出超限', dangerous_syscall: '危险调用', system_error: '判题服务异常' }[this.normalizeVerdict(value)] || value || '待判定'
    },
    ojGroups(answer) { const result = answer?.grader_result || {}; return Array.isArray(result.groups) ? result.groups : (Array.isArray(result.test_groups) ? result.test_groups : []) },
    languageLabel(value) { return value === 'cpp20' ? 'GNU C++20' : 'Python 3.11' },
    formatMemory(kb) { return Number(kb) >= 1024 ? `${(Number(kb) / 1024).toFixed(1)} MB` : `${Number(kb)} KB` }
  }
}
</script>

<style scoped>
.assignment-page { width: 100vw; height: 100vh; display: flex; overflow: hidden; position: relative; color: #f8fafc; background: var(--color-bg); }
.ambient { position: fixed; pointer-events: none; border-radius: 50%; will-change: transform; }
.ambient-a { width: 760px; height: 760px; left: -10%; top: -28%; background: radial-gradient(circle, rgba(59,130,246,.32) 0%, rgba(59,130,246,.12) 45%, transparent 75%); filter: blur(90px); animation: aurora-drift-a 12s ease-in-out infinite; }
.ambient-b { width: 620px; height: 620px; right: -12%; top: 8%; background: radial-gradient(circle, rgba(249,115,22,.22) 0%, rgba(249,115,22,.09) 45%, transparent 75%); filter: blur(70px); opacity: 1; animation: aurora-drift-b 10s ease-in-out infinite; }
.assignment-page::after { content: ''; position: fixed; z-index: 0; width: 700px; height: 700px; left: 28%; bottom: -34%; border-radius: 50%; background: radial-gradient(circle, rgba(79,70,229,.2) 0%, rgba(79,70,229,.08) 45%, transparent 75%); filter: blur(90px); pointer-events: none; animation: aurora-drift-c 14s ease-in-out infinite; }
.workspace { flex: 1; min-width: 0; height: 100vh; display: flex; flex-direction: column; position: relative; z-index: 1; }
.topbar { min-height: 116px; box-sizing: border-box; padding: 28px 38px 20px; display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; border-bottom: 1px solid rgba(148,163,184,.11); background: rgba(24,24,37,.34); backdrop-filter: blur(20px); }
.title-block, .panel-header > view:first-child { display: flex; flex-direction: column; }
.eyebrow { color: #a78bfa; font-size: 10px; font-weight: 750; letter-spacing: .14em; }
.page-title { margin-top: 5px; font-size: 28px; line-height: 1.2; font-weight: 700; letter-spacing: -.03em; }
.page-subtitle { margin-top: 7px; color: #7c8aa0; font-size: 13px; }
.top-actions, .panel-footer, .modal-actions { display: flex; align-items: center; gap: 10px; }
.panel-footer { flex-wrap: wrap; }
.quiet-button, .close-button { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; color: #94a3b8; border: 1px solid rgba(148,163,184,.16); border-radius: 8px; cursor: pointer; transition: .18s ease; }
.quiet-button:hover, .close-button:hover { color: #fff; border-color: rgba(167,139,250,.5); }
.primary-button, .secondary-button, .danger-button { min-height: 36px; box-sizing: border-box; padding: 0 15px; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; font-weight: 650; border-radius: 8px; cursor: pointer; transition: transform .16s ease, opacity .16s ease, border-color .16s ease; }
.primary-button { color: #fff; background: #7c3aed; box-shadow: 0 8px 24px rgba(124,58,237,.18); }
.primary-button:hover { transform: translateY(-1px); background: #8b5cf6; }
.secondary-button { color: #cbd5e1; border: 1px solid rgba(148,163,184,.18); }
.secondary-button:hover { border-color: rgba(167,139,250,.5); }
.danger-button { color: #fca5a5; border: 1px solid rgba(248,113,113,.25); }
.wide { min-width: 138px; }.disabled { opacity: .45; pointer-events: none; }
.content-scroll, .panel-scroll { flex: 1; min-height: 0; }
.content-shell { max-width: 1420px; margin: 0 auto; padding: 30px 38px 0; box-sizing: border-box; }
.metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid rgba(255,255,255,.12); border-bottom: 1px solid rgba(255,255,255,.12); background: rgba(42,42,60,.3); backdrop-filter: blur(18px); border-radius: 14px; }
.metric { min-height: 98px; padding: 18px 24px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid rgba(148,163,184,.11); }
.metric:first-child { padding-left: 0; }.metric:last-child { border-right: 0; }
.metric text { color: #64748b; font-size: 11px; }.metric strong { margin-top: 8px; font-size: 27px; line-height: 1; font-weight: 650; font-variant-numeric: tabular-nums; }.violet { color: #c4b5fd !important; }
.filter-row { min-height: 76px; display: flex; align-items: center; justify-content: space-between; gap: 24px; border-bottom: 1px solid rgba(148,163,184,.1); background: rgba(24,24,37,.24); backdrop-filter: blur(16px); }
.filters { display: flex; align-items: center; gap: 26px; }.filter { padding: 29px 0 20px; position: relative; color: #64748b; font-size: 12px; cursor: pointer; }.filter text { margin-left: 5px; color: #475569; }.filter.active { color: #e2e8f0; }.filter.active::after { content: ''; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: #8b5cf6; }.course-note { color: #536175; font-size: 11px; }
.assignment-list { animation: reveal .22s ease both; }.assignment-row { min-height: 118px; display: grid; grid-template-columns: 3px minmax(0,1fr) 220px; gap: 26px; align-items: stretch; border-bottom: 1px solid rgba(148,163,184,.09); cursor: pointer; transition: background .16s ease; }.assignment-row:hover { background: rgba(139,92,246,.04); }.row-accent { width: 3px; margin: 22px 0; border-radius: 2px; background: linear-gradient(180deg,#c4b5fd,#7c3aed); opacity: .85; }.assignment-main { padding: 22px 0; min-width: 0; }.assignment-heading { display: flex; align-items: center; gap: 10px; }.assignment-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #e9eaf1; font-size: 15px; font-weight: 650; }.status-chip { padding: 3px 7px; color: #94a3b8; font-size: 9px; border: 1px solid rgba(148,163,184,.16); border-radius: 4px; }.status-draft { color: #c4b5fd; border-color: rgba(167,139,250,.3); }.status-published,.status-active { color: #86efac; border-color: rgba(74,222,128,.25); }.assignment-description { display: block; margin-top: 8px; max-width: 760px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #778599; font-size: 12px; }.assignment-meta { margin-top: 11px; display: flex; gap: 7px; color: #536175; font-size: 10px; }.submission-progress { align-self: center; padding-right: 12px; }.progress-label { display: flex; align-items: baseline; justify-content: space-between; color: #64748b; font-size: 10px; }.progress-label strong { color: #cbd5e1; font-size: 13px; }.progress-track { height: 3px; margin-top: 9px; overflow: hidden; border-radius: 2px; background: rgba(148,163,184,.1); }.progress-track view { height: 100%; background: #8b5cf6; }.review-note { display: block; margin-top: 9px; color: #c4b5fd; font-size: 10px; text-align: right; }.review-note.muted { color: #536175; }
.state-view { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #64748b; font-size: 12px; }.state-view.compact { min-height: 180px; }.state-view strong { color: #cbd5e1; font-size: 16px; }.empty-mark { width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; color: #c4b5fd; font-size: 18px; border: 1px solid rgba(167,139,250,.3); border-radius: 50%; }.error-state,.inline-error { color: #fca5a5; }.retry-link { color: #a78bfa; cursor: pointer; }.loading-line { width: 110px; height: 2px; overflow: hidden; position: relative; background: rgba(167,139,250,.12); }.loading-line::after { content: ''; position: absolute; inset: 0; width: 44%; background: #a78bfa; animation: load 1s ease-in-out infinite; }.bottom-space { height: 48px; }
.assignment-list { background: rgba(42,42,60,.18); backdrop-filter: blur(14px); border-radius: 14px; }
.assignment-row { border-bottom-color: rgba(255,255,255,.1); }
.assignment-row:hover { background: rgba(96,165,250,.07); }
.row-accent { background: linear-gradient(180deg,#93c5fd,#3b82f6); }
.panel-backdrop,.modal-backdrop { position: fixed; inset: 0; z-index: 80; background: rgba(2,6,23,.58); backdrop-filter: blur(2px); }.side-panel { position: fixed; z-index: 90; right: 0; top: 0; bottom: 0; width: min(760px,94vw); display: flex; flex-direction: column; color: #e2e8f0; background: #0f0f19; border-left: 1px solid rgba(148,163,184,.14); transform: translateX(100%); transition: transform .25s ease; }.side-panel.open { transform: translateX(0); }.panel-header { min-height: 92px; padding: 20px 28px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(148,163,184,.1); }.panel-title { margin-top: 6px; max-width: 620px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 21px; font-weight: 650; }.close-button { border: 0; font-size: 25px; }.panel-body { padding: 26px 28px 54px; }.panel-footer { min-height: 68px; box-sizing: border-box; padding: 14px 28px; justify-content: flex-end; border-top: 1px solid rgba(148,163,184,.1); background: rgba(15,15,25,.94); }
.form-section { padding-top: 18px; border-top: 1px solid rgba(148,163,184,.13); }.form-section + .form-section { margin-top: 32px; }.section-title { color: #e2e8f0; font-size: 13px; font-weight: 650; }.section-heading { margin-bottom: 16px; display: flex; align-items: baseline; justify-content: space-between; }.section-heading > text:last-child { color: #64748b; font-size: 10px; }.field { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }.field > text { color: #64748b; font-size: 10px; }.field input,.field textarea,.picker-value { width: 100%; box-sizing: border-box; color: #e2e8f0; font-size: 12px; background: rgba(15,23,42,.45); border: 1px solid rgba(148,163,184,.14); border-radius: 7px; }.field input,.picker-value { height: 39px; padding: 0 11px; }.field textarea { height: 92px; padding: 10px 11px; line-height: 1.6; }.field input:focus,.field textarea:focus { border-color: rgba(167,139,250,.55); }.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }.picker-value { display: flex; align-items: center; justify-content: space-between; cursor: pointer; }.type-row { min-height: 64px; display: grid; grid-template-columns: minmax(0,1fr) 88px 118px; gap: 14px; align-items: center; border-bottom: 1px solid rgba(148,163,184,.08); }.type-row > view { display: flex; flex-direction: column; gap: 4px; }.type-row strong { color: #cbd5e1; font-size: 12px; }.type-row > view text,.type-row label > text { color: #536175; font-size: 9px; }.type-row label { display: flex; align-items: center; gap: 5px; }.type-row input { width: 52px; height: 31px; padding: 0 7px; color: #e2e8f0; font-size: 12px; background: rgba(15,23,42,.5); border: 1px solid rgba(148,163,184,.13); border-radius: 5px; }.inline-error { margin-top: 18px; font-size: 11px; }
.published-settings { margin-top: 24px; }.settings-note { display: block; margin-top: 12px; color: #8b94a7; font-size: 10px; line-height: 1.6; }
.generation-state { min-height: 470px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }.generation-orbit { width: 62px; height: 62px; position: relative; border: 1px solid rgba(167,139,250,.22); border-radius: 50%; animation: spin 3s linear infinite; }.generation-orbit::after { content: ''; position: absolute; width: 8px; height: 8px; right: 4px; top: 5px; border-radius: 50%; background: #a78bfa; box-shadow: 0 0 18px #8b5cf6; }.generation-orbit view { position: absolute; inset: 18px; border-radius: 50%; background: rgba(139,92,246,.22); }.generation-title { margin-top: 24px; color: #e9eaf1; font-size: 18px; font-weight: 650; }.generation-note { max-width: 360px; margin-top: 10px; color: #64748b; font-size: 11px; line-height: 1.7; }.job-status { margin-top: 18px; color: #a78bfa; font-size: 10px; letter-spacing: .06em; }.generation-progress { width: min(100%, 390px); margin-top: 24px; text-align: left; }.progress-summary { display: flex; justify-content: space-between; align-items: baseline; color: #94a3b8; font-size: 11px; }.progress-summary strong { color: #c4b5fd; font-size: 13px; }.generation-track { height: 7px; margin-top: 9px; }.generation-track view { background: linear-gradient(90deg, #8b5cf6, #c084fc); transition: width .3s ease; }.progress-current { display: block; margin-top: 8px; color: #64748b; font-size: 10px; }.generation-failures { width: min(100%, 390px); margin-top: 18px; display: flex; flex-direction: column; gap: 8px; text-align: left; }.generation-failure { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 9px 10px; border: 1px solid rgba(248,113,113,.24); border-radius: 6px; background: rgba(127,29,29,.1); }.generation-failure > view:first-child { min-width: 0; display: flex; flex-direction: column; gap: 3px; }.generation-failure strong { color: #fca5a5; font-size: 11px; }.generation-failure text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #a1a1aa; font-size: 10px; }.retry-question { flex: 0 0 auto; padding: 5px 9px; color: #ddd6fe; font-size: 10px; border: 1px solid rgba(167,139,250,.45); border-radius: 4px; cursor: pointer; }.retry-question.disabled { opacity: .5; pointer-events: none; }
.assignment-summary { display: grid; grid-template-columns: .65fr 1fr 1.45fr; border-top: 1px solid rgba(148,163,184,.13); border-bottom: 1px solid rgba(148,163,184,.13); }.summary-field { min-height: 66px; padding: 12px 14px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid rgba(148,163,184,.1); }.summary-field:first-child { padding-left: 0; }.summary-field:last-child { border-right: 0; }.summary-field text { color: #536175; font-size: 9px; }.summary-field strong { margin-top: 6px; color: #cbd5e1; font-size: 11px; }.editor-section { margin-top: 30px; }.question-editor { margin-top: 34px; }.question-block { margin-top: 15px; padding: 18px 0 25px; border-top: 1px solid rgba(167,139,250,.16); }.question-head { display: flex; justify-content: space-between; align-items: center; color: #c4b5fd; font-size: 11px; }.question-head label { display: flex; align-items: center; gap: 4px; color: #64748b; }.question-head input { width: 48px; height: 28px; padding: 0 6px; color: #e2e8f0; background: rgba(15,23,42,.5); border: 1px solid rgba(148,163,184,.13); border-radius: 5px; }.options-editor { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; }.option-input { height: 35px; display: flex; align-items: center; gap: 8px; }.option-input > text { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; color: #c4b5fd; font-size: 10px; border: 1px solid rgba(167,139,250,.2); border-radius: 50%; }.option-input input { flex: 1; height: 33px; padding: 0 9px; color: #e2e8f0; font-size: 11px; border-bottom: 1px solid rgba(148,163,184,.13); }
.assignment-tabs { margin-top: 28px; display: flex; gap: 24px; border-bottom: 1px solid rgba(148,163,184,.1); }.assignment-tabs view { padding: 10px 0; position: relative; color: #64748b; font-size: 11px; cursor: pointer; }.assignment-tabs view.active { color: #e2e8f0; }.assignment-tabs view.active::after { content: ''; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: #8b5cf6; }.published-overview { padding-top: 22px; }.submission-hero { min-height: 130px; display: flex; flex-direction: column; justify-content: center; border-bottom: 1px solid rgba(148,163,184,.1); }.submission-hero strong { color: #c4b5fd; font-size: 42px; font-weight: 600; }.submission-hero text { margin-top: 7px; color: #64748b; font-size: 10px; }.overview-line { min-height: 50px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(148,163,184,.08); }.overview-line text { color: #64748b; font-size: 11px; }.overview-line strong { color: #cbd5e1; font-size: 12px; }.submission-row { min-height: 66px; display: grid; grid-template-columns: 36px minmax(0,1fr) 82px auto; gap: 12px; align-items: center; border-bottom: 1px solid rgba(148,163,184,.08); cursor: pointer; }.submission-row:hover { background: rgba(139,92,246,.035); }.submission-row.inert { cursor: default; }.student-avatar { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; color: #ddd6fe; font-size: 11px; border-radius: 50%; background: rgba(124,58,237,.22); }.student-avatar.large { width: 42px; height: 42px; font-size: 14px; }.student-main { min-width: 0; display: flex; flex-direction: column; gap: 4px; }.student-main strong { color: #d7dce7; font-size: 11px; }.student-main text,.score-cell text { color: #536175; font-size: 9px; }.score-cell { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }.score-cell strong { color: #cbd5e1; font-size: 11px; }.score-cell text { color: #a78bfa; }.row-actions { display: flex; gap: 7px; }.row-actions view { padding: 5px 7px; color: #94a3b8; font-size: 9px; border: 1px solid rgba(148,163,184,.13); border-radius: 5px; cursor: pointer; }
.student-banner { min-height: 72px; display: grid; grid-template-columns: 48px 1fr auto; gap: 12px; align-items: center; border-bottom: 1px solid rgba(148,163,184,.12); }.student-banner > view:nth-child(2) { display: flex; flex-direction: column; gap: 5px; }.student-banner strong { color: #e2e8f0; font-size: 13px; }.student-banner text { color: #64748b; font-size: 9px; }.big-score { color: #c4b5fd; font-size: 20px; font-weight: 650; }.review-block { padding: 24px 0; border-bottom: 1px solid rgba(148,163,184,.12); }.review-head { display: flex; align-items: center; justify-content: space-between; color: #a78bfa; font-size: 10px; }.review-head label { display: flex; align-items: center; gap: 5px; color: #64748b; }.review-head input { width: 58px; height: 30px; padding: 0 7px; color: #e2e8f0; background: rgba(15,23,42,.5); border: 1px solid rgba(148,163,184,.13); border-radius: 5px; }.review-prompt { display: block; margin-top: 13px; color: #d7dce7; font-size: 12px; line-height: 1.65; }.answer-band { margin-top: 15px; padding: 11px 13px; display: flex; flex-direction: column; gap: 7px; background: rgba(15,23,42,.38); border-left: 2px solid #64748b; }.answer-band.reference { border-left-color: #8b5cf6; }.answer-band text { color: #536175; font-size: 9px; }.answer-band strong { color: #cbd5e1; font-size: 11px; line-height: 1.6; font-weight: 500; }.ai-feedback { display: block; margin-top: 11px; color: #8b98aa; font-size: 10px; line-height: 1.65; }.final-comment { margin-top: 28px; }
.modal-backdrop { z-index: 110; display: flex; align-items: center; justify-content: center; }.modal { width: min(420px,calc(100vw - 32px)); padding: 25px; box-sizing: border-box; color: #e2e8f0; background: #12121d; border: 1px solid rgba(148,163,184,.16); border-radius: 12px; box-shadow: 0 30px 80px rgba(0,0,0,.4); }.modal-title { display: block; margin-top: 7px; font-size: 18px; font-weight: 650; }.modal-actions { margin-top: 24px; justify-content: flex-end; }
.spinning { animation: spin .8s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } } @keyframes load { from { transform: translateX(-100%); } to { transform: translateX(250%); } } @keyframes reveal { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } } @keyframes aurora-drift-a { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(50px,35px) scale(1.06); } 66% { transform: translate(-25px,15px) scale(.97); } } @keyframes aurora-drift-b { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(-40px,30px) scale(1.05); } 66% { transform: translate(20px,-25px) scale(.98); } } @keyframes aurora-drift-c { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(30px,-35px) scale(1.07); } 66% { transform: translate(-20px,20px) scale(.96); } }
.submission-oj-summary { min-height: 44px; display: flex; align-items: center; gap: 9px; border-top: 1px solid rgba(148,163,184,.09); border-bottom: 1px solid rgba(148,163,184,.09); }.submission-oj-summary strong { color: #d7dce7; font-size: 10px; }.submission-oj-summary text { color: #536175; font-size: 8px; }.validation-dot.validation-accepted { background: #34d399; }.validation-dot.validation-system_error { background: #f59e0b; }.submission-oj-groups { border-bottom: 1px solid rgba(148,163,184,.09); }.submission-oj-groups > view { min-height: 42px; display: flex; align-items: center; justify-content: space-between; }.submission-oj-groups > view > view { display: flex; align-items: center; gap: 8px; }.submission-oj-groups strong { color: #cbd5e1; font-size: 9px; }.submission-oj-groups text { color: #64748b; font-size: 8px; }.code-band { align-items: stretch !important; flex-direction: column; }.review-code { width: 100%; max-height: 320px; margin: 7px 0 0; padding: 12px; overflow: auto; box-sizing: border-box; color: #cbd5e1; font: 9px/1.6 "SFMono-Regular",Consolas,monospace; white-space: pre-wrap; background: #0d0e16; border: 1px solid rgba(148,163,184,.09); border-radius: 5px; }.compile-output { color: #fda4af; border-left: 2px solid rgba(251,113,133,.5); }
.oj-disabled-panel { margin-top: 16px; padding: 13px 0; display: flex; flex-direction: column; gap: 5px; border-top: 1px solid rgba(245,158,11,.18); border-bottom: 1px solid rgba(245,158,11,.12); }.oj-disabled-panel strong { color: #fbbf24; font-size: 10px; }.oj-disabled-panel text { color: #64748b; font-size: 9px; line-height: 1.6; }
@media (max-width: 900px) { .metric-strip { grid-template-columns: 1fr 1fr; }.metric:nth-child(2) { border-right: 0; }.metric:nth-child(-n+2) { border-bottom: 1px solid rgba(148,163,184,.1); }.assignment-row { grid-template-columns: 3px minmax(0,1fr); }.submission-progress { grid-column: 2; width: 100%; padding: 0 18px 20px 0; box-sizing: border-box; }.options-editor { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .topbar { min-height: 104px; padding: 20px 18px 16px; align-items: flex-start; }.page-subtitle,.course-note { display: none; }.page-title { font-size: 23px; }.content-shell { padding: 20px 18px 0; }.metric { padding-left: 12px; min-height: 78px; }.metric strong { font-size: 22px; }.filter-row { overflow-x: auto; }.filters { gap: 20px; }.assignment-row { gap: 14px; }.field-grid { grid-template-columns: 1fr; }.type-row { grid-template-columns: 1fr 74px 105px; }.panel-header,.panel-body,.panel-footer { padding-left: 18px; padding-right: 18px; }.assignment-summary { grid-template-columns: 1fr; }.summary-field { padding-left: 0; border-right: 0; border-bottom: 1px solid rgba(148,163,184,.08); }.submission-row { grid-template-columns: 34px minmax(0,1fr) 74px; }.row-actions { grid-column: 2 / -1; padding-bottom: 10px; }.panel-footer { flex-wrap: wrap; }.primary-button.wide { flex: 1; } }
.side-panel { background: rgba(42,42,60,.78); border-left-color: rgba(255,255,255,.16); backdrop-filter: blur(24px); }
.panel-footer { background: rgba(42,42,60,.72); border-top-color: rgba(255,255,255,.12); backdrop-filter: blur(18px); }
.modal { background: rgba(42,42,60,.82); border-color: rgba(255,255,255,.16); backdrop-filter: blur(24px); }
</style>
