const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const scope = {}
vm.createContext(scope)
vm.runInContext(fs.readFileSync(path.join(__dirname, '../utils/agent-stream-segments.js'), 'utf8')
  .replace(/^export /gm, ''), scope)

// Reproduce history hydration: normalized segments plus raw authoritative tools.
for (const status of ['success', 'completed', 'done', 'error', 'failed']) {
  const raw = { id: 'command-1', name: 'execute_command', status, result: { stdout: 'result retained' } }
  const message = { isStreaming: false, segments: scope.normalizeAgentSegments([], '', [raw]) }
  const card = scope.getAgentMessageSegments(message, [raw])[0].toolCall
  assert.equal(card.status, 'done', `${status} must not display a spinner`)
  assert.equal(card.success, !['error', 'failed'].includes(status))
  assert.equal(card.result.stdout, 'result retained')
  assert.equal(raw.status, status, 'display mapping must not mutate source records')
}

// The live and replay path must agree with history, while pending calls keep spinning.
let message = scope.createStreamingAgentMessage('message-1')
message = scope.applyAgentStreamEvent(message, 'tool_call', { id: 'command-1', name: 'execute_command', status: 'running', sequence: 1 })
assert.equal(scope.getAgentMessageSegments(message, message.toolCalls)[0].toolCall.status, 'running')
message = scope.applyAgentStreamEvent(message, 'tool_call', { id: 'command-1', name: 'execute_command', status: 'success', sequence: 2 })
assert.equal(scope.getAgentMessageSegments(message, message.toolCalls)[0].toolCall.status, 'done')
message = scope.applyAgentStreamEvent(message, 'tool_call', { id: 'command-1', status: 'running', sequence: 1 })
assert.equal(scope.getAgentMessageSegments(message, message.toolCalls)[0].toolCall.status, 'done')
console.log('Tool cards: history, live completion, replay, failures and pending states passed.')
