# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The uStudy mobile app frontend — a uni-app / Vue project targeting iOS, Android, H5, and 小程序 from a single codebase. **There is no CLI build.** All builds and device runs go through **HBuilderX IDE**.

## Build & Run

- Open this folder (`uni-app-trial/`) in HBuilderX
- **Run to device/browser**: Run → Run to Browser (H5) or Run to Device (mobile)
- **Production build**: 发行 → 网站-H5 (for H5), or 发行 → App (for APK/IPA)
- **H5 deploy to server**: `scp -r unpackage/dist/build/web/* root@47.76.51.198:/var/www/ustudy-app/`

**Toggle server vs local**: `config/index.js` → set `USE_PRODUCTION = true/false`

## Version Management

All version fields live in `config/index.js`:
- `APP_VERSION_NAME` / `APP_VERSION_CODE` — bump for every release (WGT or APK)
- `NATIVE_VERSION_CODE` — bump only when releasing a new APK (not for WGT hot-patches)

## Critical Architecture Patterns

### Platform Conditional Compilation

Use `// #ifdef PLATFORM` / `// #ifndef PLATFORM` and `<!-- #ifdef -->` in templates. Common targets: `APP-PLUS` (native app), `H5`, `MP-WEIXIN`. All platform branches must compile independently.

### Vue API Style

**All pages and components use Options API (`export default {}`)** — no `<script setup>`, no Composition API. `main.js` bootstraps both Vue 2 (with `PiniaVuePlugin`) and Vue 3 (with `createSSRApp`) via conditional compilation to support all uni-app targets.

### SSE Streaming (Cross-Platform)

SSE is the most complex subsystem. Platform dispatch lives in `utils/sse.js`:
- **H5**: `fetch` + `ReadableStream`
- **Android (preferred)**: `renderjs` bridge via `sse-renderjs` component — requires `setSseEventBus()` in page `mounted` and `clearSseEventBus()` in `beforeDestroy`
- **Android (fallback)**: `plus.net.XMLHttpRequest` + `onprogress`
- **iOS**: `uni.request` + `onChunkReceived`
- **小程序**: full response, no streaming

Chat pages that use SSE must include the `sse-renderjs` component (inside `<!-- #ifdef APP-PLUS -->`) and wire up `handleSseEvents`/`handleSseComplete`/`handleSseError`. See `pages/CLAUDE.md` for the exact setup pattern.

### Theme System

Dark mode is the default. All pages and components bind a `theme-dark` / `theme-light` CSS class to their root element using `getStoredThemeMode()` from `utils/themeMode`. Light theme styles are overrides under `.theme-light` in the same `<style scoped>` block. Global CSS variables are declared in `App.vue`; light overrides are in `styles/light-theme-pages.css`.

### Custom Navigation Bars

Every page has `"navigationStyle": "custom"` in `pages.json` and builds its own nav bar. Use `goBack()` from `utils/navigation` — not `uni.navigateBack()` directly — to get the correct APP-PLUS animation and fallback behavior.

### Page Parameters

Pages receive params from `onLoad(options)` (uni-app lifecycle), not Vue Router props.

## App Lifecycle (App.vue)

On launch (`APP-PLUS` only):
1. Clears WebView cache if `APP_VERSION_CODE` changed
2. Sets up push notification listener → `resolveNotificationTarget` → `navigateToTarget`
3. Sets up Android `newintent` listener for URL scheme re-entry
4. Triggers OTA update check via `useUpdateStore().checkForUpdates()` after 2s

## Directory Guide

Each major directory has its own `CLAUDE.md` with patterns and rules — read those before editing files in that directory:

| Directory | CLAUDE.md covers |
|-----------|-----------------|
| `api/` | HTTP client modules, SSE, file upload, auth skip patterns |
| `components/` | overlay animation pattern, theme pattern, `sse-renderjs` renderjs bridge, `markdown-render` platform split |
| `pages/` | page conventions, SSE bridge setup, page map |
| `store/` | Pinia store patterns, persistence, update/announcement flow |
| `utils/` | `sse.js`, `request.js`, `storage.js`, `deepLink.js`, all utility modules |

## Key Dependencies

- `marked` — Markdown parsing
- `highlight.js` — Code syntax highlighting (APP-PLUS only, via renderjs)
- `katex` — Math rendering (logic layer, passes HTML to renderer)
- `pinia` — State management (Vue 2 mode uses `PiniaVuePlugin`)
