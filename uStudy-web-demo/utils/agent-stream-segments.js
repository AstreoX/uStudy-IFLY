function valueOf(source, ...keys) {
  for (const key of keys) {
    if (source && source[key] !== undefined && source[key] !== null) return source[key]
  }
  return undefined
}

function asObject(value) {
  if (!value) return {}
  if (typeof value === 'object') return value
  try { return JSON.parse(value) } catch (_) { return {} }
}

export function normalizeAgentToolCall(raw = {}) {
  const statusValue = String(valueOf(raw, 'status', 'state') || 'running').toLowerCase()
  const done = ['done', 'completed', 'complete', 'success', 'failed', 'error'].includes(statusValue)
  const successValue = valueOf(raw, 'success', 'ok')
  const success = successValue === undefined
    ? !['failed', 'error'].includes(statusValue)
    : Boolean(successValue)
  return {
    ...raw,
    id: String(valueOf(raw, 'id', 'tool_call_id', 'toolCallId') || ''),
    tool: valueOf(raw, 'tool', 'name', 'tool_name', 'toolName') || 'tool',
    arguments: asObject(valueOf(raw, 'arguments', 'args', 'params', 'input')),
    result: valueOf(raw, 'result', 'output', 'data'),
    status: done ? 'done' : 'running',
    success
  }
}

export function normalizeAgentSegments(rawSegments, fallbackContent = '', rawToolCalls = []) {
  const source = Array.isArray(rawSegments) ? rawSegments : []
  const segments = []
  for (const raw of source) {
    if (!raw || typeof raw !== 'object') continue
    const type = String(valueOf(raw, 'type', 'kind') || '').toLowerCase()
    if (type === 'text' || type === 'content') {
      const content = String(valueOf(raw, 'content', 'text', 'delta') || '')
      if (content) segments.push({ type: 'text', content })
    } else if (type === 'tool' || type === 'tool_call') {
      const toolCall = normalizeAgentToolCall(valueOf(raw, 'toolCall', 'tool_call') || raw)
      if (toolCall.id || toolCall.tool) segments.push({ type: 'tool', toolCall })
    }
  }
  if (!segments.length && Array.isArray(rawToolCalls) && rawToolCalls.length) {
    rawToolCalls.forEach(tool => segments.push({ type: 'tool', toolCall: normalizeAgentToolCall(tool) }))
  }
  if (!segments.length && fallbackContent) segments.push({ type: 'text', content: String(fallbackContent) })
  return segments
}

export function getAgentMessageSegments(message, activeToolCalls = []) {
  if (!message) return []
  const source = message.isStreaming && Array.isArray(message.streamSegments)
    ? message.streamSegments
    : Array.isArray(message.segments) ? message.segments : []
  const segments = source.map(segment => {
    if (segment?.type !== 'tool') return { ...segment }
    const id = segment.toolCall?.id
    const active = activeToolCalls.find(tool => String(tool.id) === String(id))
    return { type: 'tool', toolCall: { ...(active || segment.toolCall) } }
  })
  if (message.isStreaming && message.content && !message.segmentsContainCurrentText) {
    segments.push({ type: 'text', content: message.content })
  }
  if (!segments.length && message.content) segments.push({ type: 'text', content: message.content })
  return segments
}

export function createStreamingAgentMessage(id, overrides = {}) {
  return {
    id,
    role: 'assistant',
    content: '',
    segments: [],
    streamSegments: [],
    toolCalls: [],
    thinkingContent: '',
    thinkingDuration: 0,
    thinkingStartedAt: 0,
    isThinking: false,
    isStreaming: true,
    streaming: true,
    streamSequence: 0,
    segmentsContainCurrentText: true,
    ...overrides
  }
}

function withSegments(message, mutate) {
  const segments = normalizeAgentSegments(message.streamSegments || message.segments)
  mutate(segments)
  return { ...message, streamSegments: segments, segments }
}

export function appendAgentThinking(message, content, now = Date.now()) {
  if (!content) return message
  return {
    ...message,
    thinkingContent: `${message.thinkingContent || ''}${content}`,
    thinkingStartedAt: message.thinkingStartedAt || now,
    isThinking: true
  }
}

export function finishAgentThinking(message, now = Date.now()) {
  if (!message?.isThinking) return message
  const startedAt = Number(message.thinkingStartedAt || now)
  return {
    ...message,
    isThinking: false,
    thinkingDuration: Math.max(0, Math.round((now - startedAt) / 1000))
  }
}

export function appendAgentText(message, content, now = Date.now()) {
  if (!content) return message
  let next = finishAgentThinking(message, now)
  next = withSegments(next, segments => {
    const last = segments[segments.length - 1]
    if (last?.type === 'text') last.content = `${last.content || ''}${content}`
    else segments.push({ type: 'text', content: String(content) })
  })
  return { ...next, content: `${next.content || ''}${content}` }
}

export function upsertAgentTool(message, rawTool, now = Date.now()) {
  const toolCall = normalizeAgentToolCall(rawTool)
  let next = finishAgentThinking(message, now)
  next = withSegments(next, segments => {
    const existing = segments.find(segment => segment.type === 'tool' && String(segment.toolCall?.id) === toolCall.id)
    if (existing) existing.toolCall = { ...existing.toolCall, ...toolCall }
    else segments.push({ type: 'tool', toolCall })
  })
  const toolCalls = next.streamSegments.filter(segment => segment.type === 'tool').map(segment => ({ ...segment.toolCall }))
  return { ...next, toolCalls }
}

export function applyAgentStreamEvent(message, type, payload = {}, now = Date.now()) {
  const sequence = Number(valueOf(payload, 'sequence', 'seq', 'event_sequence') || 0)
  if (sequence && sequence <= Number(message.streamSequence || 0)) return message
  let next = message
  if (type === 'thinking_delta') {
    next = appendAgentThinking(next, valueOf(payload, 'content', 'text', 'delta', 'reasoning_content') || '', now)
  } else if (type === 'text_delta') {
    next = appendAgentText(next, valueOf(payload, 'content', 'text', 'delta') || '', now)
  } else if (type === 'tool_call') {
    next = upsertAgentTool(next, payload, now)
  }
  return sequence ? { ...next, streamSequence: sequence } : next
}

export function finalizeAgentMessage(message, payload = {}, now = Date.now()) {
  let next = finishAgentThinking(message, now)
  const terminalContent = valueOf(payload, 'content', 'message', 'text')
  if (!next.content && terminalContent) next = appendAgentText(next, terminalContent, now)
  const terminalStatus = String(valueOf(payload, 'status', 'state') || '').toLowerCase()
  const terminalError = valueOf(payload, 'error', 'message', 'detail') || '任务中断'
  const segments = normalizeAgentSegments(next.streamSegments || next.segments, next.content, next.toolCalls)
    .map(segment => {
      if (
        segment.type !== 'tool'
        || segment.toolCall?.status !== 'running'
        || !['failed', 'cancelled', 'stopped', 'error'].includes(terminalStatus)
      ) return segment
      return {
        ...segment,
        toolCall: normalizeAgentToolCall({
          ...segment.toolCall,
          status: 'error',
          success: false,
          error: terminalError
        })
      }
    })
  return {
    ...next,
    content: next.content || String(terminalContent || ''),
    segments,
    streamSegments: null,
    toolCalls: segments.filter(segment => segment.type === 'tool').map(segment => ({ ...segment.toolCall })),
    isThinking: false,
    isStreaming: false,
    streaming: false
  }
}
