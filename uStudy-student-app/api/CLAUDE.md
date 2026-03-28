# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

The `api/` directory is the HTTP client layer for the uStudy uni-app frontend. Each file is a thin module that maps directly to one backend domain. All functions are named exports (no default exports).

## Request Patterns

### Standard requests
All standard API calls use `request()` from `@/utils/request`, which handles JWT auth, auto token refresh, and error normalization:

```js
import { request } from '@/utils/request'
export function getSomething(id) {
  return request({ url: `/api/resource/${id}`, method: 'GET' })
}
```

`skipAuth: true` + `skipRefresh: true` must be set on auth endpoints (login, register, token refresh) to prevent circular refresh loops.

### File uploads
File uploads bypass `request()` and use `uni.uploadFile()` directly — see `attachment.js` and `user.js` for the pattern. The auth header must be set manually. `user.js` implements a 401-retry-with-fresh-token pattern inline.

### SSE streaming
Chat messages use `connectSSE` or `connectSSEWithResume` from `@/utils/sse`. Both functions return an abort/cancel function. Use `connectSSEWithResume` (the default) to enable reconnect-and-resume after network drops. `notification.js` implements its own reconnect loop on top of `connectSSE`.

### Release channel
`release.js` fetches from Gitee raw content (configured via `config.GITEE_RAW_BASE`) — not the backend API. Uses raw `uni.request()` directly.

## Module Map

| File | Backend routes | Notes |
|---|---|---|
| `auth.js` | `/api/auth/*` | All endpoints are `skipAuth`/`skipRefresh` |
| `chat.js` | `/api/conversations/*`, `/api/quick-chat/*`, `/api/models`, `/api/feedback/*` | SSE streaming, quota error parsing |
| `space.js` | `/api/spaces/*`, `/api/agents/*`, `/api/quizzes/*`, `/api/rag/*` | Largest module; covers KG, quiz, RAG, sharing, members |
| `note.js` | `/api/spaces/:id/notes/*` | CRUD |
| `folder.js` | `/api/spaces/:id/folders/*` | content_type: `'notes'` or `'quizzes'` |
| `attachment.js` | `/api/attachments/*` | Upload + URL resolution helper |
| `user.js` | `/api/upload/avatar` | Avatar upload only |
| `auth.js` | `/api/auth/*` | Auth and account |
| `quota.js` | `/api/quota/status` | Single endpoint |
| `payment.js` | `/api/payment/orders/*` | Create order + paid notification |
| `notification.js` | `/api/notifications/stream` | SSE with built-in reconnect backoff |
| `notificationCenter.js` | `/api/notifications/*` | Inbox CRUD |
| `activity.js` | `/api/activity/*` | Learning activity |
| `assessment.js` | `/api/assessment/*` | Assessment/mastery |
| `review.js` | `/api/review/due` | Spaced repetition due items |
| `calendarEvents.js` | `/api/calendar-events/*` | Calendar |
| `searchSettings.js` | `/api/search-settings/*` | Search config |
| `release.js` | Gitee raw CDN | App version manifest + markdown |

## index.js

`index.js` is **not** a complete barrel. It re-exports only `authApi` and `chatApi`. All other modules are imported directly by consumers.

## SSE Event Types

`chat.js` handles: `text_delta`, `thinking_delta`, `tool_call`, `client_tool_request`, `title`, `done`, `error`

`notification.js` handles: `mastery_update`, `artifact_stream`, `artifact_ready`, `new_notification`, `_heartbeat`

## Adding a New Endpoint

1. Add to the appropriate existing module (same domain → same file).
2. Create a new file only when it maps to a genuinely new backend module.
3. Match the JSDoc style of surrounding functions.
4. For endpoints that should work while logged out, add `skipAuth: true, skipRefresh: true`.
