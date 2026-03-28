# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Directory Purpose

Cross-platform utility layer for the uni-app mobile frontend (iOS / Android / H5 / 小程序). All modules use `uni.*` APIs and conditional compilation (`// #ifdef`) to branch per platform.

## Critical: SSE Architecture (`sse.js`)

The most architecturally complex file. Four platform implementations under one `connectSSE()` API:

| Platform | Mechanism | Notes |
|----------|-----------|-------|
| H5 | `fetch` + `ReadableStream` | `AbortController` for cancellation |
| Android (preferred) | `renderjs` event bus | Requires `setSseEventBus()` in page `mounted`, `clearSseEventBus()` in `beforeDestroy` |
| Android (fallback) | `plus.net.XMLHttpRequest` + `onprogress` | Used when `sseEventBus` is null |
| iOS / App | `uni.request` + `onChunkReceived` | Falls back to `replayEventsGradually()` if no chunks arrive |
| 小程序 | `uni.request` (no streaming) | Parses full response after completion |

**Two public connection functions:**
- `connectSSE(options)` — single connection with 401 auto-refresh retry
- `connectSSEWithResume(options)` — adds exponential-backoff reconnect + resume-from-offset (calls backend `/resume-stream?offset=N`)

Both return a cancel function. The `connectSSEWithResume` requires `getStreamingStatus` callback and `conversationId`.

**SSE Event types:** `text_delta`, `thinking_delta`, `tool_call`, `client_tool_request`, `title`, `done`, `error`

**renderjs bridge setup** (Android streaming):
```javascript
// In page component
import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError } from '@/utils/sse'

onMounted(() => setSseEventBus(this.$refs.sseRenderjs))
onBeforeDestroy(() => clearSseEventBus())
// renderjs component calls back via handleSseEvents / handleSseComplete / handleSseError
```

## Request Layer (`request.js`)

- `request(options)` — wraps `uni.request`, auto-attaches JWT, handles 401 → refresh → retry
- `ensureFreshToken()` — exported for SSE's own 401 handling; **shares the same refresh lock** as `request()` so parallel refreshes collapse into one
- Token refresh hits `/api/auth/refresh` with `refresh_token`; on failure calls `redirectToLogin({ saveCurrentPage: true })`

## Storage Layer (`storage.js`)

All storage keys come from `@/config`. Key groups:
- **Auth**: `getTokens/setTokens/removeTokens`, `getUser/setUser`, `clearAuth()` (removes both)
- **Preferences**: `getSelectedModelId`, `getThinkingMode` (defaults to `true`), `getUpdatePrefs`, `getAnnouncementPrefs`
- **Chat**: `getCardOrder/setCardOrder`, `getQuizEvaluationResult`

`getAnnouncementPrefs` auto-resets `dismissedIds` when `APP_VERSION_CODE` advances.

## Deep Link & Navigation (`deepLink.js`)

Handles push notifications, URL schemes, and pending navigation after login:

- **Pending navigation**: stored with 30-minute TTL; `savePendingNavigation` → user logs in → `consumePendingNavigation` → `navigateToTarget`
- `resolveAppLaunchTarget(options)` — resolves `launchOptions`, `runtimeArguments` (push notification JSON), and URL schemes into internal route targets
- `resolveNotificationTarget(payload)` — maps `type`/`action` fields to routes (quiz, quiz_result, space_chat, quick_chat, announcement)
- Duplicate launch guard via `lastLaunchSignature` (module-level singleton)
- `redirectToLogin({ saveCurrentPage: true })` — saves current page to pending navigation before redirect

## Updater (`updater.js`)

Manifest-driven OTA update from Gitee:
- APK download: `plus.downloader` → `plus.runtime.install` → `plus.runtime.restart`
- WGT (hot patch): only if `getNativeVersionCode() >= manifest.latestVersion.minNativeVersionCode`
- iOS: `isUpdateAvailable` always returns `false`
- `isForceUpdate` checks both `forceUpdate: true` and `forceUpdateBelow` (version code threshold)

## Background Chat Monitor (`backgroundChatMonitor.js`)

App-level singleton. Polls after user navigates away during streaming:
- Fast poll: every 3s for first 30s; slow poll: every 8s thereafter; stops after 5min
- Primary: Redis `getStreamingStatus` API; fallback: DB `checkReplyStatus`
- On completion: `plus.push.createMessage()` system notification with JSON payload
- Call `stopBackgroundMonitor()` when returning to the chat page

## Other Utilities

| File | Key exports | Notes |
|------|------------|-------|
| `preKnowledgeParser.js` | `PreKnowledgeTagParser` class | State-machine parser for `<PreKnowledge>` and `<Highlight>` tags in streaming text; handles cross-chunk splits; call `flush()` at stream end |
| `permission.js` | `ensureAlbumWritePermission`, `ensureCameraPermission`, `ensureNotificationPermission`, `guideToSettings` | Android 13+ uses `READ_MEDIA_IMAGES`; guides denied users to system settings |
| `filePicker.js` | `chooseLocalFiles`, `isPickerCancel` | Tries `uni.chooseMessageFile` → `uni.chooseFile` → native Android `Intent.ACTION_GET_CONTENT`; normalizes result to `{ path, name, size }` |
| `messageDraft.js` | `savePendingMessage`, `getPendingMessages`, `removePendingMessage`, `clearPendingMessages`, `savePendingMessagesFromArray` | Per-conversation draft persistence; max 10 messages; keyed `pending_messages_{conversationId}` |
| `radar-snapshot.js` | `saveRadarSnapshot`, `getLastWeekSnapshot` | Weekly radar data; auto-rotates on Monday; returns `null` if last-week data is stale |
| `calendar.js` + `calendarSync.js` | Calendar event management | Android-only bridge via `plus.android.importClass(CalendarContract)`; no native plugin needed |
| `themeMode.js` | `getStoredThemeMode`, `persistThemeMode` | Normalizes to `'light'` or `'dark'`; defaults to `'dark'` |
| `themeSystemUi.js` | `syncThemeSystemUi(mode, options)` | APP-PLUS only: updates status bar style/color |
| `navigation.js` | `goBack(options)` | APP-PLUS uses `slide-out-right` animation; falls back to `uni.reLaunch` on failure |
| `quizEvaluationBus.js` | `setPendingEvaluation`, `consumeAllPending` | Buffers quiz eval results across the page lifecycle race; emits `uni.$emit('quizEvaluationDone', ...)` |
| `appUsageTracker.js` | `startTracking`, `stopTracking` | 60s heartbeat to `/api/usage/heartbeat`; accumulates time on failure (capped 120s); idempotent |
