const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..')

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const pages = JSON.parse(read('pages.json')).pages.map((page) => page.path)
assert(pages[0] === 'pages/login/login', 'login must be the H5 entry route')
const forbiddenPages = [
  'pages/activation/activation',
  'pages/payment-result/payment-result',
  'pages/quickChat/quickChat',
  'pages/createSpace/createSpace'
]
for (const page of forbiddenPages) {
  assert(!pages.includes(page), `forbidden experiment route is registered: ${page}`)
}
for (const page of ['pages/register/register', 'pages/forgotPassword/forgotPassword']) {
  assert(pages.includes(page), `required email-auth route is missing: ${page}`)
}
assert(
  pages.includes('pages/teacherDashboard/teacherDashboard'),
  'teacher dashboard route is missing'
)
assert(
  pages.includes('pages/teacherAssistant/teacherAssistant'),
  'teacher presentation assistant route is missing'
)

const config = read('config/index.js')
assert(
  config.includes("const PRODUCTION_BASE_URL = ''"),
  'production API base must be same-origin'
)
assert(config.includes("const TOKEN_KEY = 'ustudy_dev_tokens'"), 'token storage is not isolated')
assert(config.includes("const USER_KEY = 'ustudy_dev_user'"), 'user storage is not isolated')

const activeFiles = [
  'config/index.js',
  'pages.json',
  'pages/login/login.vue',
  'pages/register/register.vue',
  'pages/forgotPassword/forgotPassword.vue',
  'pages/index/index.vue',
  'pages/study/study.vue',
  'pages/searchSettings/searchSettings.vue',
  'pages/calendar/calendar.vue',
  'pages/openQuiz/openQuiz.vue',
  'pages/teacherDashboard/teacherDashboard.vue',
  'pages/teacherAssistant/teacherAssistant.vue',
  'pages/teacherAssignments/teacherAssignments.vue',
  'api/teacher.js',
  'api/teacher-presentations.js',
  'components/teacher/TeacherEChart.vue',
  'components/teacher/TeacherSpaceSelector.vue',
  'components/teacher/presentation/PresentationProjectRail.vue',
  'components/teacher/presentation/PresentationConversation.vue',
  'components/teacher/presentation/PresentationPreview.vue',
  'components/chat/AgentThinkingBlock.vue',
  'components/chat/AgentToolCard.vue',
  'utils/agent-stream-segments.js',
  'utils/teacher-echarts.js',
  'utils/teacher-chart-options.js',
  'utils/teacher-space-selection.js',
  'components/layout/HomeSidebar.vue',
  'components/study/StudyMaterialsPanel.vue'
]
const forbiddenRuntimeRefs = [
  'api.ustudy.cc',
  'download.ustudy.cc',
  'app.ustudy.cc',
  '/pages/activation/activation',
  '@/store/wallet',
  '@/store/invite',
  '@/api/payment',
  '@/api/invite'
  ,'/api/quick-chat'
  ,'/pages/quickChat/quickChat'
  ,'/pages/createSpace/createSpace'
]
for (const relativePath of activeFiles) {
  const source = read(relativePath)
  for (const forbidden of forbiddenRuntimeRefs) {
    assert(!source.includes(forbidden), `${relativePath} contains forbidden runtime reference: ${forbidden}`)
  }
}

const login = read('pages/login/login.vue')
assert(login.includes('identifier: this.form.identifier'), 'login does not submit identifier')
assert(login.includes('handleGoRegister'), 'login does not expose email registration')
assert(login.includes('handleForgotPassword'), 'login does not expose password recovery')
assert(login.includes("'/pages/index/index'"), 'login does not return to the home page')
assert(!login.includes('openDefaultSpace'), 'login still forces the default course')
assert(login.includes('登录教师示例账户'), 'teacher example login shortcut is missing')
assert(login.includes('登录学生示例账户'), 'student example login shortcut is missing')
assert(login.includes("loginAsExample('teacher')"), 'teacher example shortcut is not wired')
assert(login.includes("loginAsExample('student')"), 'student example shortcut is not wired')
assert(login.includes('exampleLoginEnabled'), 'example login shortcuts are not environment-gated')
assert(login.includes('EXAMPLE_LOGIN_ENABLED = true'), 'experiment build must enable example login shortcuts')

const register = read('pages/register/register.vue')
assert(register.includes("purpose: 'registration'"), 'registration verification flow is missing')
assert(!register.includes('@/api/invite'), 'registration must not call the disabled invite API')
assert(register.includes("'/pages/index/index'"), 'registration does not return to the home page')
assert(!register.includes('openDefaultSpace'), 'registration still forces the default course')

const forgotPassword = read('pages/forgotPassword/forgotPassword.vue')
assert(forgotPassword.includes("purpose: 'password_reset'"), 'password recovery flow is missing')

const sidebar = read('components/layout/HomeSidebar.vue')
assert(sidebar.includes("space.user_role === 'teacher'"), 'teacher navigation is not role-gated')
assert(sidebar.includes("label: '学习空间'"), 'learning-space navigation label was not restored')
assert(sidebar.includes('studyExpanded: true'), 'learning-space navigation is not expanded by default')
assert(!sidebar.includes("matchedItem.id !== 'study'"), 'route sync still collapses learning spaces on entry')
assert(!sidebar.includes('?spaceId=${encodeURIComponent(this.teacherSpace.id)}'), 'teacher navigation still forces the first course space')
assert(sidebar.includes("id: 'teacher-assistant'"), 'teacher assistant navigation is missing')
assert(
  sidebar.includes('/pages/teacherAssistant/teacherAssistant'),
  'teacher assistant navigation route is not wired'
)
const teacherDashboard = read('pages/teacherDashboard/teacherDashboard.vue')
assert(teacherDashboard.includes('getTeacherOverview'), 'teacher overview is not wired')
assert(teacherDashboard.includes('activity_calendar'), '90-day teacher activity calendar is not wired')
assert(teacherDashboard.includes('TeacherEChart'), 'teacher dashboard is not using the ECharts host')
assert(!teacherDashboard.includes('email'), 'teacher dashboard must not render student email')
assert(!teacherDashboard.includes('user_answers_raw'), 'teacher dashboard must not render raw answers')
assert(teacherDashboard.includes('TeacherSpaceSelector'), 'teacher dashboard course-space selector is missing')
assert(teacherDashboard.includes('TEACHER_SPACE_TOOLS.DASHBOARD'), 'teacher dashboard selection is not independently persisted')
assert(!teacherDashboard.includes('数据结构 · 教师视图'), 'teacher dashboard still hardcodes the default course')

const teacherAssistant = read('pages/teacherAssistant/teacherAssistant.vue')
assert(teacherAssistant.includes('sendPresentationMessage'), 'teacher assistant SSE messaging is not wired')
assert(teacherAssistant.includes('fetchPresentationPreview'), 'teacher assistant authenticated preview is not wired')
assert(teacherAssistant.includes('confirmPublish'), 'teacher assistant explicit publish confirmation is missing')
assert(teacherAssistant.includes('restorePresentationRevision'), 'teacher assistant revision restore is not wired')
assert(teacherAssistant.includes('TeacherSpaceSelector'), 'teacher assistant course-space selector is missing')
assert(teacherAssistant.includes('TEACHER_SPACE_TOOLS.PRESENTATIONS'), 'teacher assistant selection is not independently persisted')
assert(!teacherAssistant.includes('“数据结构”资料库'), 'teacher assistant publish confirmation still hardcodes the default course')
const teacherAssignments = read('pages/teacherAssignments/teacherAssignments.vue')
assert(teacherAssignments.includes('TeacherSpaceSelector'), 'teacher assignments course-space selector is missing')
assert(teacherAssignments.includes('TEACHER_SPACE_TOOLS.ASSIGNMENTS'), 'teacher assignments selection is not independently persisted')
assert(!teacherAssignments.includes('课程 · 数据结构'), 'teacher assignments still hardcodes the default course')
assert(teacherAssignments.includes('resumeActiveGeneration'), 'teacher assignments cannot resume a background generation job')
assert(teacherAssignments.includes('setTimeout(run, 2000)'), 'teacher assignment polling is not serialized')
assert(!teacherAssignments.includes('setInterval(this.checkJob'), 'teacher assignment polling can overlap requests')
assert(teacherAssignments.includes('.assignment-page :deep(.sidebar) { display: none; }'), 'teacher assignments mobile layout still keeps the fixed sidebar')
assert(teacherAssistant.includes('revisionRequestVersion'), 'teacher assistant revision responses are not guarded across context switches')
assert(teacherDashboard.includes('.teacher-page :deep(.sidebar) { display: none; }'), 'teacher dashboard mobile layout still keeps the fixed sidebar')
const teacherSpaceSelector = read('components/teacher/TeacherSpaceSelector.vue')
assert(teacherSpaceSelector.includes('课程空间'), 'teacher selector label is incorrect')
const teacherSpaceSelection = read('utils/teacher-space-selection.js')
for (const tool of ['dashboard', 'assignments', 'presentations']) {
  assert(teacherSpaceSelection.includes(`'${tool}'`), `teacher selection namespace is missing: ${tool}`)
}
const teacherPresentationsApi = read('api/teacher-presentations.js')
assert(teacherPresentationsApi.includes('connectSSE'), 'presentation API must use the shared SSE client')
assert(teacherPresentationsApi.includes('deletePresentationSource'), 'uploaded presentation sources must be removable')
assert(teacherPresentationsApi.includes('confirmed: true'), 'presentation publishing must send explicit confirmation')
assert(teacherPresentationsApi.includes('ensureFreshToken'), 'authenticated presentation blobs must support token refresh')
assert(teacherPresentationsApi.includes("case 'thinking_delta'"), 'presentation API must forward Qwen thinking deltas')
assert(teacherPresentationsApi.includes("case 'text_delta'"), 'presentation API must forward text deltas')
assert(teacherPresentationsApi.includes('callbacks.onConnectionError'), 'presentation API must distinguish transport disconnects from agent errors')

const presentationConversation = read('components/teacher/presentation/PresentationConversation.vue')
assert(presentationConversation.includes('AgentThinkingBlock'), 'presentation chat must use the shared thinking block')
assert(presentationConversation.includes('AgentToolCard'), 'presentation chat must use the shared tool card')
assert(presentationConversation.includes('messageSegments(message)'), 'presentation chat must render an ordered segment timeline')
const agentSegments = read('utils/agent-stream-segments.js')
assert(agentSegments.includes('appendAgentText'), 'shared agent segment text reducer is missing')
assert(agentSegments.includes('upsertAgentTool'), 'shared agent segment tool reducer is missing')
assert(agentSegments.includes('streamSequence'), 'shared agent segment reducer must deduplicate resumed events')
assert(agentSegments.includes('segmentsContainCurrentText'), 'shared agent segment renderer must prevent duplicate streamed text')
assert(teacherAssistant.includes('message.streamSequence || 0'), 'presentation reconnect must resume after the last rendered event')
assert(teacherAssistant.includes('scheduleRunReconnect'), 'presentation chat must reconnect without replacing the streaming message')
const studyPage = read('pages/study/study.vue')
assert(studyPage.includes('getAgentMessageSegments'), 'main chat must reuse the shared segment renderer')
assert(studyPage.includes('AgentThinkingBlock'), 'main chat must reuse the shared thinking block')
assert(studyPage.includes('AgentToolCard'), 'main chat generic tools must reuse the shared tool card')

const teacherEcharts = read('utils/teacher-echarts.js')
assert(teacherEcharts.includes("from 'echarts/core'"), 'ECharts must use the modular core import')
assert(!teacherEcharts.includes("from 'echarts'"), 'full ECharts bundle import is forbidden')
for (const required of ['HeatmapChart', 'CalendarComponent', 'CanvasRenderer']) {
  assert(teacherEcharts.includes(required), `teacher ECharts runtime is missing ${required}`)
}
const teacherChartHost = read('components/teacher/TeacherEChart.vue')
assert(teacherChartHost.includes('ResizeObserver'), 'teacher chart host must resize with its container')
assert(teacherChartHost.includes('.dispose()'), 'teacher chart host must dispose its ECharts instance')

console.log(`Experiment frontend verification passed (${activeFiles.length} active files checked).`)
