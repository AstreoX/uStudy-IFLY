const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')

let connection
const scope = {
  normalizeAgentSegments: () => [],
  connectSSE: (options) => { connection = options; return () => {} }
}
vm.createContext(scope)
const source = fs.readFileSync(path.join(__dirname, '../api/teacher-presentations.js'), 'utf8')
  .replace(/^import .*$/gm, '').replace(/^export /gm, '')
vm.runInContext(source, scope)
const legacy = { message: 'maximum presentation-agent iterations reached', retryable: false }
const error = scope.normalizePresentationError(legacy)
assert.equal(error.recoverable, true)
assert.equal(error.retryable, false)
assert.equal(error.error_code, 'legacy_iteration_limit')
const historical = scope.normalizePresentationMessage({ run_error: legacy.message, recoverable: false, run_status: 'failed' })
assert.equal(historical.runError, error.message)
assert.equal(historical.recoverable, true)
assert.equal(historical.errorCode, error.error_code)
let received
scope.sendPresentationMessage('space', 'project', {}, { onError: (message, event) => { received = { message, event } } })
connection.onEvent('error', legacy)
assert.equal(received.message, historical.runError)
assert.equal(received.event.recoverable, historical.recoverable)
scope.resumePresentationRun('space', 'project', 'run', 60, { onError: (message, event) => { received = { message, event } } })
connection.onEvent('error', legacy)
assert.equal(received.message, historical.runError)
assert.equal(scope.normalizePresentationError({ reason: 'runtime_dependencies' }).recoverable, false)
assert.equal(scope.normalizePresentationError({ message: 'upstream error', retryable: false, recoverable: true }).recoverable, true)
assert.equal(scope.normalizePresentationError({ message: 'unknown' }).error_code, 'agent_execution_failed')
console.log('Presentation live, replay and historical error mapping passed.')
