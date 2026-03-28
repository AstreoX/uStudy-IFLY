# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

Vue page components for the uStudy uni-app frontend. Each page lives in its own subdirectory as a single `.vue` file (`page-name/page-name.vue`). All pages use Options API (`export default {}`) — no `<script setup>`.

## Universal Page Conventions

### Custom Navigation Bar
Every page has `"navigationStyle": "custom"` in `pages.json`, so pages must build their own nav bars. The standard pattern:
```html
<view class="xxx-nav-bar">
  <view class="nav-left" @click="goBack"><image .../></view>
  <text class="nav-title">Title</text>
  <view class="nav-right" @click="openSettings"><image .../></view>
</view>
```
Use `goBack()` from `@/utils/navigation` (not `uni.navigateBack()` directly) — it applies the correct `slide-out-right` animation on APP-PLUS and falls back to `/pages/index/index` on failure.

### Theme Pattern
All pages bind `pageThemeClass` to the root element:
```html
<view class="page-container" :class="pageThemeClass">
```
```js
import { getStoredThemeMode } from '@/utils/themeMode'

data() { return { homeThemeMode: 'dark' } },
computed: {
  pageThemeClass() { return `theme-${this.homeThemeMode}` }
},
// in created/onShow:
this.homeThemeMode = getStoredThemeMode('dark')
```
CSS: dark styles are defaults; `theme-light` overrides go in the same `<style scoped>` block.

### Page Parameters
Received via the uni-app lifecycle hook `onLoad(options)`, not from `props` or Vue Router:
```js
onLoad(options) {
  this.spaceId = options.space_id
}
```

### Cleanup in `beforeDestroy`
Always cancel SSE connections, clear timers, and remove event listeners here.

## SSE Pages (quickChat, spaceChat, knowledgeBase)

Chat pages that use streaming must include the Android SSE bridge component:

**Template** (inside root view, at the bottom):
```html
<!-- #ifdef APP-PLUS -->
<sse-renderjs
  ref="sseRenderjs"
  @sse-events="onRenderjsSseEvents"
  @sse-complete="onRenderjsSseComplete"
  @sse-error="onRenderjsSseError"
/>
<!-- #endif -->
```

**Script** (imports):
```js
import { setSseEventBus, clearSseEventBus, handleSseEvents, handleSseComplete, handleSseError, connectSSE } from '@/utils/sse'
// #ifdef APP-PLUS
import SseRenderjs from '@/components/sse-renderjs/sse-renderjs.vue'
// #endif
```

**Lifecycle**:
```js
mounted() {
  // #ifdef APP-PLUS
  if (this.$refs.sseRenderjs) setSseEventBus(this.$refs.sseRenderjs)
  // #endif
},
beforeDestroy() {
  clearSseEventBus()
  // also cancel active SSE requests
}
```

**Renderjs callbacks** wire into `handleSseEvents`, `handleSseComplete`, `handleSseError` from `@/utils/sse`.

## Page Map

| Page | Purpose |
|---|---|
| `index` | Home — swiper tab layout (spaces list + account tab), notification badge, theme toggle |
| `quickChat` | Standalone AI chat with tool calling, attachments, model selection |
| `spaceChat` | Collaborative AI chat scoped to a learning space |
| `learningSpace` | Knowledge graph canvas with minimap, pinch-zoom, AI sidebar |
| `knowledgeBase` | RAG document list and chat for a space |
| `notesList` | Notes list for a space, with folder navigation |
| `quizList` | Quiz list and session entry for a space |
| `test` | Active quiz session (question rendering) |
| `testResult` | Quiz result summary |
| `artifactViewer` | WebView-based viewer for AI-generated artifacts |
| `createSpace` | Space creation wizard |
| `spaceSettings` | Space configuration |
| `spaceMembers` / `spaceLeaderboard` | Collaborative space member management / leaderboard |
| `chatHistory` / `quickChatHistory` | Conversation history lists |
| `quickChatSettings` | Quick chat model and behavior settings |
| `searchSettings` | RAG/web search configuration |
| `notifications` | Notification inbox |
| `announcementHistory` | In-app announcement log |
| `subscription` | Subscription plans and payment |
| `account` | User profile and settings |
| `login` / `register` / `emailLogin` / `forgotPassword` / `resetPassword` | Auth flow |

## index Page — Swiper Tab Layout

`index.vue` is the app shell. It uses a `<swiper>` with two items (Home tab, Account tab) driven by `swiperIndex`. Tab switching via bottom tab bar emits `swiperIndex` changes; swipe also updates the active tab. The home tab contains the space card list and the quick-create entry.

## Adding a New Page

1. Create `pages/new-name/new-name.vue`
2. Register in `pages.json` with `"navigationStyle": "custom"` and matching animation type
3. For chat/SSE pages: follow the SSE bridge pattern above
4. Always implement `pageThemeClass` and read `getStoredThemeMode()` on `created` / `onShow`
5. Use `goBack()` from `@/utils/navigation` for the back button
