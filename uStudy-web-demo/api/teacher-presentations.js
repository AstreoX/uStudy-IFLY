import { request, ensureFreshToken } from '@/utils/request'
import { connectSSE } from '@/utils/sse'
import { getTokens } from '@/utils/storage'
import config from '@/config'
import { normalizeAgentSegments } from '@/utils/agent-stream-segments'

const API_ROOT = '/api/teacher/spaces'

function valueOf(source, ...keys) {
  for (const key of keys) {
    if (source && source[key] !== undefined && source[key] !== null) return source[key]
  }
  return undefined
}

function unwrapList(payload, keys) {
  if (Array.isArray(payload)) return payload
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

export function normalizePresentationProject(project = {}) {
  return {
    ...project,
    id: String(valueOf(project, 'id', 'project_id', 'projectId') || ''),
    title: valueOf(project, 'title', 'name') || '未命名课件',
    status: valueOf(project, 'status', 'run_status', 'runStatus') || 'idle',
    createdAt: valueOf(project, 'created_at', 'createdAt') || '',
    updatedAt: valueOf(project, 'updated_at', 'updatedAt') || '',
    currentRevisionId: String(valueOf(project, 'current_revision_id', 'currentRevisionId', 'latest_revision_id') || ''),
    publishedDocumentId: String(valueOf(project, 'published_document_id', 'publishedDocumentId') || ''),
    activeRunId: String(valueOf(project, 'active_run_id', 'activeRunId', 'run_id') || ''),
    slideCount: Number(valueOf(project, 'slide_count', 'slideCount', 'slides_count') || 0)
  }
}

export function normalizePresentationRevision(revision = {}) {
  const previewManifest = valueOf(revision, 'preview_manifest', 'previewManifest') || {}
  const manifest = valueOf(revision, 'manifest') || {}
  const previewManifestCount = Array.isArray(previewManifest)
    ? previewManifest.length
    : Array.isArray(previewManifest.pages)
      ? previewManifest.pages.length
    : Array.isArray(previewManifest.slides)
      ? previewManifest.slides.length
      : (previewManifest && typeof previewManifest === 'object' ? Object.keys(previewManifest).length : 0)
  const slideCount = valueOf(revision, 'slide_count', 'slideCount', 'slides_count', 'preview_count')
    ?? valueOf(previewManifest, 'slide_count', 'slideCount', 'slides_count')
    ?? valueOf(manifest, 'slide_count', 'slideCount', 'slides_count')
    ?? (previewManifestCount || undefined)
    ?? (Array.isArray(manifest.slides) ? manifest.slides.length : 0)
  return {
    ...revision,
    id: String(valueOf(revision, 'id', 'revision_id', 'revisionId') || ''),
    number: Number(valueOf(revision, 'number', 'revision_number', 'revisionNumber', 'version') || 0),
    status: valueOf(revision, 'status', 'build_status', 'buildStatus') || 'completed',
    summary: valueOf(revision, 'summary', 'change_summary', 'changeSummary') || '',
    createdAt: valueOf(revision, 'created_at', 'createdAt') || '',
    slideCount: Number(slideCount || 0),
    publishedAt: valueOf(revision, 'published_at', 'publishedAt') || '',
    isPublished: Boolean(valueOf(revision, 'is_published', 'isPublished', 'published_at', 'publishedAt'))
  }
}

export function normalizePresentationError(event = {}) {
  const message = event.message || event.run_error || event.runError || event.detail || 'PPT Agent 执行失败'
  if (message.includes('maximum presentation-agent iterations reached') || event.error_code === 'legacy_iteration_limit') {
    return { ...event, message: '任务因旧版执行轮次限制停止，可继续执行。', error_code: 'legacy_iteration_limit', retryable: false, recoverable: true }
  }
  const dependencies = event.error_code === 'runtime_dependencies' || event.reason === 'runtime_dependencies'
  return {
    ...event,
    message,
    error_code: dependencies ? 'runtime_dependencies' : (event.error_code || event.errorCode || 'agent_execution_failed'),
    recoverable: dependencies ? false : (event.recoverable ?? (event.retryable !== false))
  }
}

export function normalizePresentationMessage(message = {}) {
  const role = valueOf(message, 'role', 'sender_role', 'senderRole') || 'assistant'
  const llmContextRaw = valueOf(message, 'llm_context', 'llmContext') || {}
  let llmContext = llmContextRaw
  if (typeof llmContextRaw === 'string') {
    try { llmContext = JSON.parse(llmContextRaw) } catch { llmContext = {} }
  }
  const content = valueOf(message, 'content', 'text', 'message') || ''
  const toolCalls = valueOf(message, 'tool_calls', 'toolCalls') || llmContext.tool_calls || []
  const rawSegments = valueOf(message, 'segments', 'presentation_segments')
    || llmContext.segments
    || llmContext.presentation_segments
    || []
  const segments = normalizeAgentSegments(rawSegments, content, toolCalls)
  const error = normalizePresentationError(message)
  return {
    ...message,
    id: String(valueOf(message, 'id', 'message_id', 'messageId') || `${role}-${Date.now()}-${Math.random()}`),
    role: role === 'ai' ? 'assistant' : role,
    content,
    createdAt: valueOf(message, 'created_at', 'createdAt') || '',
    activities: toolCalls,
    toolCalls,
    segments,
    segmentsContainCurrentText: Array.isArray(segments) && segments.some(segment => segment?.type === 'text'),
    thinkingContent: valueOf(message, 'thinking_content', 'thinkingContent', 'reasoning_content')
      || llmContext.thinking_content
      || llmContext.reasoning_content
      || '',
    thinkingDuration: Number(valueOf(message, 'thinking_duration', 'thinkingDuration')
      ?? llmContext.thinking_duration
      ?? 0),
    runId: String(valueOf(message, 'run_id', 'runId') || llmContext.run_id || ''),
    runStatus: valueOf(message, 'run_status', 'runStatus') || llmContext.run_status || '',
    streamSequence: Number(valueOf(message, 'stream_sequence', 'streamSequence')
      ?? llmContext.stream_sequence
      ?? 0),
    recoverable: Boolean(error.recoverable),
    errorCode: error.error_code,
    runError: valueOf(message, 'run_error', 'runError') ? error.message : '',
    isThinking: Boolean(valueOf(message, 'streaming', 'is_streaming', 'isStreaming')),
    isStreaming: Boolean(valueOf(message, 'streaming', 'is_streaming', 'isStreaming')),
    streaming: Boolean(valueOf(message, 'streaming', 'is_streaming', 'isStreaming'))
  }
}

export function normalizePresentationSource(source = {}) {
  return {
    ...source,
    id: String(valueOf(source, 'id', 'source_id', 'sourceId', 'asset_id') || ''),
    name: valueOf(source, 'name', 'file_name', 'filename', 'original_filename') || '附件',
    kind: valueOf(source, 'kind', 'source_type', 'sourceType', 'file_type') || 'document',
    status: valueOf(source, 'status', 'processing_status', 'processingStatus') || 'ready'
  }
}

export async function listPresentationProjects(spaceId) {
  const payload = await request({ url: `${API_ROOT}/${spaceId}/presentations`, method: 'GET' })
  return unwrapList(payload, ['projects', 'items', 'presentations']).map(normalizePresentationProject)
}

export async function createPresentationProject(spaceId, data = {}) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations`,
    method: 'POST',
    data
  })
  return normalizePresentationProject(payload?.project || payload)
}

export async function getPresentationProject(spaceId, projectId) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}`,
    method: 'GET'
  })
  return normalizePresentationProject(payload?.project || payload)
}

export async function getPresentationMessages(spaceId, projectId) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/messages`,
    method: 'GET'
  })
  return unwrapList(payload, ['messages', 'items']).map(normalizePresentationMessage)
}

export async function listPresentationRevisions(spaceId, projectId) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/revisions`,
    method: 'GET'
  })
  return unwrapList(payload, ['revisions', 'items', 'versions']).map(normalizePresentationRevision)
}

async function authenticatedFetch(path, options = {}, retry = true) {
  const token = getTokens()?.access_token
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`

  let response = await fetch(`${config.API_BASE_URL}${path}`, { ...options, headers })
  if (response.status === 401 && retry) {
    const freshToken = await ensureFreshToken()
    response = await fetch(`${config.API_BASE_URL}${path}`, {
      ...options,
      headers: { ...headers, Authorization: `Bearer ${freshToken}` }
    })
  }
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const payload = await response.json()
      message = payload?.detail?.message || payload?.detail || payload?.message || message
    } catch {}
    throw new Error(message)
  }
  return response
}

export async function uploadPresentationSource(spaceId, projectId, file, kind = '') {
  const formData = new FormData()
  formData.append('file', file)
  if (kind) formData.append('kind', kind)
  const response = await authenticatedFetch(
    `${API_ROOT}/${spaceId}/presentations/${projectId}/sources`,
    { method: 'POST', body: formData }
  )
  const payload = await response.json()
  return normalizePresentationSource(payload?.source || payload?.asset || payload)
}

export async function listPresentationSources(spaceId, projectId) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/sources`,
    method: 'GET'
  })
  return unwrapList(payload, ['sources', 'items', 'assets']).map(normalizePresentationSource)
}

export function deletePresentationSource(spaceId, projectId, sourceId) {
  return request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/sources/${sourceId}`,
    method: 'DELETE'
  })
}

function connectPresentationEvents(options, callbacks = {}) {
  let connectionFailed = false
  return connectSSE({
    ...options,
    onEvent: (eventType, payload) => {
      callbacks.onEvent?.(eventType, payload)
      switch (eventType) {
        case 'thinking':
        case 'thinking_delta': callbacks.onThinkingDelta?.(payload.content || payload.text || payload.delta || payload.reasoning_content || '', payload); break
        case 'content':
        case 'text_delta': callbacks.onTextDelta?.(payload.content || payload.text || payload.delta || '', payload); break
        case 'tool_call_start': callbacks.onToolCall?.({ ...payload, status: 'running' }); break
        case 'tool_call_end': callbacks.onToolCall?.({ ...payload, status: payload.status || 'done' }); break
        case 'tool_call': callbacks.onToolCall?.(payload); break
        case 'presentation_progress':
        case 'heartbeat':
        case 'attempt_failed':
        case 'recovery_started': callbacks.onProgress?.({ ...payload, stage: payload.stage || eventType }); break
        case 'presentation_revision': callbacks.onRevision?.(payload); break
        case 'presentation_ready': callbacks.onReady?.(payload); break
        case 'done': callbacks.onDone?.(payload); break
        case 'error': {
          const error = normalizePresentationError(payload)
          callbacks.onError?.(error.message, error)
          break
        }
      }
    },
    onComplete: () => {
      if (!connectionFailed) callbacks.onComplete?.()
    },
    onConnectionError: (error) => {
      const rawMessage = String(error?.message || error || '')
      const match = rawMessage.match(/^HTTP\s+(\d+):\s*([\s\S]*)$/i)
      if (match) {
        connectionFailed = true
        const statusCode = Number(match[1])
        let detail = match[2] || `请求失败 (${statusCode})`
        try {
          const payload = JSON.parse(detail)
          detail = payload?.detail?.message || payload?.detail || payload?.message || detail
        } catch (_) {}
        callbacks.onError?.(String(detail), {
          retryable: false,
          status_code: statusCode,
          error_type: 'http_error'
        })
        return
      }
      connectionFailed = true
      callbacks.onConnectionError?.(error)
    }
  })
}

export function sendPresentationMessage(spaceId, projectId, data, callbacks = {}) {
  return connectPresentationEvents({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/messages`,
    method: 'POST',
    data
  }, callbacks)
}

export function resumePresentationRun(spaceId, projectId, runId, after = 0, callbacks = {}) {
  return connectPresentationEvents({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/runs/${runId}/events?after=${Number(after) || 0}`,
    method: 'GET'
  }, callbacks)
}

export function cancelPresentationRun(spaceId, projectId, runId) {
  return request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/runs/${runId}/cancel`,
    method: 'POST'
  })
}

export async function restartPresentationRun(spaceId, projectId, runId) {
  const payload = await request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/runs/${runId}/resume`,
    method: 'POST'
  })
  return {
    ...payload,
    lastSequence: Number(valueOf(payload, 'last_sequence', 'lastSequence') || 0),
    status: valueOf(payload, 'status') || 'recovering'
  }
}

export function restorePresentationRevision(spaceId, projectId, revisionId) {
  return request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/revisions/${revisionId}/restore`,
    method: 'POST'
  })
}

export async function fetchPresentationPreview(spaceId, projectId, revisionId, slideNumber) {
  const response = await authenticatedFetch(
    `${API_ROOT}/${spaceId}/presentations/${projectId}/revisions/${revisionId}/previews/${slideNumber}`,
    { method: 'GET' }
  )
  return response.blob()
}

export async function fetchPresentationDownload(spaceId, projectId, revisionId) {
  const response = await authenticatedFetch(
    `${API_ROOT}/${spaceId}/presentations/${projectId}/revisions/${revisionId}/download`,
    { method: 'GET' }
  )
  const disposition = response.headers.get('content-disposition') || ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return {
    blob: await response.blob(),
    filename: encodedName ? decodeURIComponent(encodedName) : plainName || '教学课件.pptx'
  }
}

export function publishPresentationRevision(spaceId, projectId, revisionId, title) {
  return request({
    url: `${API_ROOT}/${spaceId}/presentations/${projectId}/revisions/${revisionId}/publish`,
    method: 'POST',
    data: { confirmed: true, title }
  })
}
