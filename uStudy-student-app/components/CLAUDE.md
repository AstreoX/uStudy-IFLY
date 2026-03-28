# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

Custom Vue 3 (Options API) components for the uStudy uni-app frontend. Each component lives in its own subdirectory as a single `.vue` file (`component-name/component-name.vue`). No Composition API `<script setup>` — all components use Options API `export default {}`.

## Component Categories

| Prefix/Group | Components | Purpose |
|---|---|---|
| `u-` prefix | `u-modal`, `u-toast`, `u-snackbar`, `u-action-sheet`, `u-input-modal`, `u-capsule-toast` | Generic UI primitives (overlays, feedback) |
| Feature overlays | `payment-modal`, `continuity-drawer`, `announcement-dialog`, `update-dialog`, `image-source-picker` | Domain-specific overlays |
| Data visualization | `knowledge-tree-mini`, `learning-radar`, `learning-timeline`, `activity-calendar` | Charts and graphs |
| AI/Content cards | `markdown-render`, `artifact-generation-card`, `python-execution-card`, `pre-knowledge-card`, `note-creation-card`, `note-display-card` | AI output display |
| Special | `sse-renderjs` | renderjs SSE bridge (Android only) |

## Critical Patterns

### Overlay Animation: `visible` + `animationVisible`

All overlay components use a two-variable pattern. `visible` controls DOM presence (`v-if`); `animationVisible` is set after a `$nextTick` + 10ms delay to trigger CSS transitions:

```js
watch: {
  visible: {
    immediate: true,
    handler(newVal) {
      if (newVal) {
        this.$nextTick(() => {
          setTimeout(() => { this.animationVisible = true }, 10)
        })
      } else {
        this.animationVisible = false
      }
    }
  }
}
```

On close, `animationVisible` is set to `false` first, then `$emit('close')` fires after a 200ms delay to let the CSS transition finish before the parent removes the DOM.

### Theme Mode Pattern

Components accept an optional `themeMode` prop but fall back to `getStoredThemeMode()` from `@/utils/themeMode`:

```js
import { getStoredThemeMode, normalizeThemeMode } from '@/utils/themeMode'

// data
localThemeMode: 'dark'

// computed
themeClass() {
  return `theme-${normalizeThemeMode(this.themeMode || this.localThemeMode)}`
},

// created + on visible
refreshThemeMode() {
  this.localThemeMode = getStoredThemeMode('dark')
}
```

CSS theming uses custom properties defined on the root wrapper class (dark defaults), with `theme-light` overrides in the same `<style scoped>` block.

### `sse-renderjs` — Android SSE Bridge

This is a **renderjs** component — it has two `<script>` blocks. The invisible `<view>` passes data from the logic layer to the renderjs layer via `:change:` attribute bindings; the renderjs layer calls back via `$ownerInstance.callMethod()`.

**Logic layer → renderjs:** Modify `trigger` data (JSON string) to start a fetch; modify `abortTrigger` to cancel.

**renderjs → logic layer:** `onSseEvents`, `onSseComplete`, `onSseError` methods called via `$ownerInstance.callMethod()`. `onSseComplete` fires twice (200ms retry) because the first call sometimes drops if the component re-renders.

Do not add new logic to this component — coordinate via the existing `startSSE(options)` / `abortSSE(requestId)` public API.

### `markdown-render` — Platform-Split Rendering

Uses `<!-- #ifdef APP-PLUS -->` / `<!-- #ifndef APP-PLUS -->` conditional compilation:
- **APP-PLUS**: renderjs module renders HTML via WebView DOM manipulation (supports `highlight.js`, full CSS)
- **Other platforms**: `<rich-text :nodes="parsedHtml">` (limited styling support)

KaTeX math rendering happens in the logic layer before passing to either renderer.

### `knowledge-tree-mini` — Canvas Touch Overlay

uni-app canvas elements do not reliably receive touch events, so a transparent `<view class="touch-overlay">` is layered on top of the canvas in interactive mode. Touch events are handled on the overlay and translated to canvas coordinates manually.

## Adding a New Component

1. Create `components/new-name/new-name.vue`
2. For overlays: follow the `visible` + `animationVisible` pattern above
3. For themed components: accept `themeMode` prop (String, default `''`) and use `getStoredThemeMode` fallback
4. Always clean up timers/listeners in `beforeDestroy`
5. Use `@touchmove.stop.prevent` on modal wrappers to prevent background scroll
