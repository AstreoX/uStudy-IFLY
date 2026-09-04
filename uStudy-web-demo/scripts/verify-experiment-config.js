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
  'api/teacher.js',
  'api/teacher-presentations.js',
  'components/teacher/TeacherEChart.vue',
  'components/teacher/presentation/PresentationProjectRail.vue',
  'components/teacher/presentation/PresentationConversation.vue',
  'components/teacher/presentation/PresentationPreview.vue',
  'components/chat/AgentThinkingBlock.vue',
  'components/chat/AgentToolCard.vue',
  'utils/agent-stream-segments.js',
  'utils/teacher-echarts.js',
  'utils/teacher-chart-options.js',
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
assert(login.includes('openDefaultSpace'), 'login does not open the default course')

const register = read('pages/register/register.vue')
assert(register.includes("purpose: 'registration'"), 'registration verification flow is missing')
assert(!register.includes('@/api/invite'), 'registration must not call the disabled invite API')

const forgotPassword = read('pages/forgotPassword/forgotPassword.vue')
assert(forgotPassword.includes("purpose: 'password_reset'"), 'password recovery flow is missing')

const defaultSpace = read('utils/default-space.js')
assert(defaultSpace.includes('/pages/study/study?spaceId='), 'default course redirect is missing')

const sidebar = read('components/layout/HomeSidebar.vue')
assert(sidebar.includes("space.user_role === 'teacher'"), 'teacher navigation is not role-gated')
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

const teacherAssistant = read('pages/teacherAssistant/teacherAssistant.vue')
assert(teacherAssistant.includes('sendPresentationMessage'), 'teacher assistant SSE messaging is not wired')
assert(teacherAssistant.includes('fetchPresentationPreview'), 'teacher assistant authenticated preview is not wired')
assert(teacherAssistant.includes('confirmPublish'), 'teacher assistant explicit publish confirmation is missing')
assert(teacherAssistant.includes('restorePresentationRevision'), 'teacher assistant revision restore is not wired')
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
