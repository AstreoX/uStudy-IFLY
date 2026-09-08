const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const root = path.resolve(__dirname, '..')
const failures = []

function read(relativePath) {
  const filePath = path.join(root, relativePath)
  try {
    return fs.readFileSync(filePath, 'utf8')
  } catch (error) {
    failures.push(`missing file: ${relativePath}`)
    return ''
  }
}

function assert(condition, message) {
  if (!condition) failures.push(message)
}

function assertVueScriptParses(relativePath) {
  const source = read(relativePath)
  const match = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)
  if (!match) {
    failures.push(`missing script block: ${relativePath}`)
    return
  }
  const script = match[1]
    .replace(/^\s*import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '')
    .replace(/^\s*export\s+default\s+/m, 'return ')
  try {
    // Syntax-only check. Runtime globals such as uni are intentionally not invoked.
    new Function(script)
  } catch (error) {
    failures.push(`invalid Vue script in ${relativePath}: ${error.message}`)
  }
}

function assertModuleParses(relativePath) {
  const source = read(relativePath)
    .replace(/^\s*import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '')
    .replace(/^\s*export\s+(?=(async\s+)?function|const|let|class)/gm, '')
  try {
    new Function(source)
  } catch (error) {
    failures.push(`invalid module syntax in ${relativePath}: ${error.message}`)
  }
}

const manifest = read('manifest.json')
const manifestHash = crypto.createHash('sha256').update(manifest).digest('hex').toUpperCase()
assert(
  manifest.includes('"compatible"') && manifest.includes('"ignoreVersion" : true'),
  'manifest.json missing the APP-PLUS runtime compatibility fallback'
)

const pagesText = read('pages.json')
let pages = null
try {
  pages = JSON.parse(pagesText)
} catch (error) {
  failures.push('pages.json is not valid JSON')
}
const pagePaths = (pages?.pages || []).map(page => page.path)
for (const forbidden of [
  'pages/createSpace/createSpace',
  'pages/quickChat/quickChat',
  'pages/quickChatSettings/quickChatSettings',
  'pages/quickChatHistory/quickChatHistory',
  'pages/subscription/subscription',
  'pages/payment-result/payment-result'
]) {
  assert(!pagePaths.includes(forbidden), `forbidden route remains: ${forbidden}`)
}
for (const required of [
  'pages/login/login',
  'pages/index/index',
  'pages/learningSpace/learningSpace',
  'pages/spaceChat/spaceChat',
  'pages/knowledgeBase/knowledgeBase',
  'pages/notesList/notesList',
  'pages/quizList/quizList',
  'pages/test/test',
  'pages/testResult/testResult',
  'pages/account/account'
]) {
  assert(pagePaths.includes(required), `required student route missing: ${required}`)
}

const index = read('pages/index/index.vue')
assert(!index.includes('/pages/createSpace'), 'index still links to createSpace')
assert(!/cardType\s*===\s*['"]add['"]/.test(index), 'index still renders an add-space card')
assert(index.includes('尚未分配课程'), 'index empty state no longer explains course assignment')
assert(!index.includes('/pages/quickChat/quickChat'), 'index still links to removed Quick Chat page')

const config = read('config/index.js')
assert(config.includes('https://ustudy.top'), 'production API base is not ustudy.top')
for (const forbidden of ['api.ustudy.cc', 'gitee.com', '10.0.2.2', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.']) {
  assert(!config.includes(forbidden), `stale or hard-coded host remains in config: ${forbidden}`)
}

const auth = read('api/auth.js')
assert(auth.includes('identifier'), 'login adapter does not send canonical identifier')
const loginPage = read('pages/login/login.vue')
assert(loginPage.includes('handleStudentExampleLogin'), 'login page is missing the student example shortcut')
assert(loginPage.includes('example@experiment.invalid'), 'student example identifier is missing from login shortcut')
assert(loginPage.includes('Student@123'), 'student example password is missing from login shortcut')
assert(loginPage.includes('setTokens'), 'student example shortcut does not persist login tokens')
const spaceApi = read('api/space.js')
assert(spaceApi.includes('/documents'), 'space API no longer exposes document endpoints')
assert(spaceApi.includes('/pdf-page-previews?pages='), 'space API is missing PDF page preview support')
const notesApi = read('api/note.js')
const foldersApi = read('api/folder.js')
assert(notesApi.includes('/notes'), 'note API endpoints are missing')
assert(foldersApi.includes('/folders'), 'folder API endpoints are missing')
const notesPage = read('pages/notesList/notesList.vue')
assert(notesPage.includes('note.visibility'), 'notes page does not render visibility compatibility')
const knowledgeBase = read('pages/knowledgeBase/knowledgeBase.vue')
assert(knowledgeBase.includes('processed_pages'), 'knowledge-base processing fields are not backward-compatible')

const chatApi = read('api/chat.js')
assert(!/url:\s*['"]\/api\/quick-chat/.test(chatApi), 'active Quick Chat API request remains')
assert(!index.includes('checkForUpdates'), 'index still starts the old update flow')
assert(!read('App.vue').includes('checkForUpdates'), 'App still starts the old OTA update flow')
assert(!read('pages/account/account.vue').includes('checkForUpdates'), 'account page still exposes update checks')
assert(!read('pages/account/account.vue').includes('/pages/subscription/subscription'), 'account page still links to subscription')
assert(!read('components/account-profile/account-profile.vue').includes('api/wallet'), 'account profile still imports wallet API')
assert(!read('components/account-profile/account-profile.vue').includes('api/invite'), 'account profile still imports invite API')

const assignmentsApi = read('api/assignments.js')
for (const requiredPath of [
  '/api/assignments?space_id=',
  '/draft',
  '/submit',
  '/submission'
]) {
  assert(assignmentsApi.includes(requiredPath), `teacher-assignment API endpoint missing: ${requiredPath}`)
}
const assignmentAdapter = read('utils/assignment-adapter.js')
assert(assignmentAdapter.includes('rawDraftAnswers'), 'assignment adapter does not preserve opaque OJ drafts')
assert(assignmentAdapter.includes('question.isOj'), 'assignment adapter does not distinguish OJ questions')

const quizList = read('pages/quizList/quizList.vue')
assert(quizList.includes('教师布置'), 'quiz list does not render teacher assignments')
assert(quizList.includes('handleAssignmentClick'), 'quiz list cannot open teacher assignments')
assert(quizList.includes('Promise.allSettled'), 'quiz list does not isolate independent list failures')
const testPage = read('pages/test/test.vue')
assert(testPage.includes("currentQuestion.type === 'code'"), 'test page does not render an OJ question branch')
assert(testPage.includes('请前往网页端作答'), 'test page does not guide OJ answers to the web client')
assert(!testPage.includes('OjCodeEditor'), 'test page must not render a code editor')
assert(testPage.includes('hasOjQuestion'), 'test page does not block APP final submission for OJ assignments')
const resultPage = read('pages/testResult/testResult.vue')
assert(resultPage.includes('mapAssignmentSubmission'), 'result page does not support teacher-assignment results')
assert(resultPage.includes('网页端查看代码'), 'result page exposes OJ code details instead of the web hint')
const deepLink = read('utils/deepLink.js')
assert(deepLink.includes('assignment_graded'), 'assignment grade notifications are not routed')
assert(deepLink.includes('buildAssignmentResultTarget'), 'assignment result navigation is missing')

const spaceChat = read('pages/spaceChat/spaceChat.vue')
const pdfAgenticToolCard = read('components/pdf-agentic-tool-card/pdf-agentic-tool-card.vue')
for (const toolName of [
  'search_keywords',
  'search_regex',
  'list_documents',
  'read_document',
  'get_document_outline',
  'view_document_pages',
  'view_document_page'
]) {
  assert(spaceChat.includes(`'${toolName}'`), `Agentic RAG tool is not routed to the mobile card: ${toolName}`)
  assert(pdfAgenticToolCard.includes(`${toolName}:`) || pdfAgenticToolCard.includes(`'${toolName}'`), `Agentic RAG card is missing Chinese copy for: ${toolName}`)
}
assert(spaceChat.includes('<PdfAgenticToolCard'), 'space chat does not render the Agentic RAG card')
assert(pdfAgenticToolCard.includes("new Set(['view_document_pages', 'view_document_page'])"), 'PDF expansion is not limited to the two page-view tools')
assert(pdfAgenticToolCard.includes('getPdfPagePreviews'), 'PDF page-view cards do not load the pages seen by AI')
assert(pdfAgenticToolCard.includes('uni.previewImage'), 'PDF page images cannot be opened in the native preview')

for (const vueFile of [
  'pages/quizList/quizList.vue',
  'pages/test/test.vue',
  'pages/testResult/testResult.vue',
  'components/pdf-agentic-tool-card/pdf-agentic-tool-card.vue'
]) assertVueScriptParses(vueFile)
for (const moduleFile of [
  'api/assignments.js',
  'utils/assignment-adapter.js',
  'utils/deepLink.js'
]) assertModuleParses(moduleFile)

// The source-only legacy modules are intentionally retained for a low-risk copy,
// but no mounted student page may navigate to removed commercial/Quick Chat APIs.
const activeStudentFiles = [
  'App.vue',
  'pages/index/index.vue',
  'pages/account/account.vue',
  'components/account-profile/account-profile.vue',
  'pages/knowledgeBase/knowledgeBase.vue',
  'pages/notesList/notesList.vue',
  'pages/spaceChat/spaceChat.vue'
].map(read).join('\n')
for (const forbidden of [
  '/pages/subscription/subscription',
  '/pages/payment-result/payment-result',
  '/pages/quickChat/quickChat',
  '/pages/quickChatSettings/quickChatSettings',
  '/api/payment',
  '/api/wallet',
  '/api/invites'
]) {
  assert(!activeStudentFiles.includes(forbidden), `active student page still references removed flow: ${forbidden}`)
}

if (failures.length) {
  console.error('Student app verification failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`Student app verification passed (${pagePaths.length} routes, manifest ${manifestHash.slice(0, 12)}...)`)
