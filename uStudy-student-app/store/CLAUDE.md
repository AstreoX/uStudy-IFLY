# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This directory contains all Pinia stores for the uni-app mobile frontend. State is options-style (`defineStore` with `state`/`actions`/`getters`), not composition API.

## Stores

### `user.js` — `useUserStore`
- Holds the authenticated user object (loaded from `utils/storage` on init)
- `setUser(user)` persists to storage and starts app usage tracking (`utils/appUsageTracker`)
- `clear()` stops tracking, nulls user, and calls `clearAuth()` from storage
- All mutations use spread (`{ ...this.user, field }`) — never mutate `this.user` directly

### `update.js` — `useUpdateStore`
- Manages the full OTA update + announcement flow
- `updateType`: `'wgt'` (hot-patch, no reinstall) or `'apk'` (full install) — auto-determined by `_determineUpdateType()` via `canUseWgtUpdate()` from `utils/updater`
- Update flow: `checkForUpdates()` → sets `showUpdateDialog` → user calls `startUpdate()` → `installUpdate()`
- WGT path: `startWgtDownload()` → `installWgt()`; APK path: `downloadInBrowser()` (opens browser, no in-app download for APK)
- Falls back to browser if WGT install fails, sets `updateType = 'apk'`
- After update dismissed/skipped, always calls `checkAnnouncements()` to show queued announcements
- User prefs (skipped version, dismissed announcement IDs) are persisted via `utils/storage` using `getUpdatePrefs/setUpdatePrefs` and `getAnnouncementPrefs/setAnnouncementPrefs`
- Announcements capped at 100 dismissed IDs to prevent unbounded storage growth

### `notification.js` — `useNotificationStore`
- In-memory only (not persisted) unread notification badge count
- Simple counter: `setUnreadCount`, `increment`, `decrement`, `clearUnread`

### `index.js`
- Creates and exports the Pinia instance; imported once in `main.js`

## Key Patterns

- **Persistence**: Only `user.js` and `update.js` persist state via `utils/storage`. `notification.js` is ephemeral.
- **Side effects in actions**: `user.js` starts/stops `appUsageTracker` as a side effect of login/logout. Keep tracking calls paired with `setUser`/`clear`.
- **Manifest shape**: `update.js` expects `manifest.latestVersion.{ versionCode, fileSizeMB, wgtFileSizeMB, changelog }` and `manifest.announcements[].{ id, body, expiresAt }` — sourced from `api/release.fetchReleaseManifest()`.
