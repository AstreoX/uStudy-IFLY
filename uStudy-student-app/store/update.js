import { defineStore } from 'pinia'
import { fetchReleaseManifest, fetchMarkdownContent } from '@/api/release'
import {
  getUpdatePrefs,
  setUpdatePrefs,
  getAnnouncementPrefs,
  setAnnouncementPrefs
} from '@/utils/storage'
import config from '@/config'
import {
  isUpdateAvailable,
  isForceUpdate,
  getDownloadUrl,
  getBrowserDownloadUrl,
  downloadApk,
  installApk,
  openInBrowser
} from '@/utils/updater'

export const useUpdateStore = defineStore('update', {
  state: () => ({
    manifest: null,
    changelogContent: '',
    showUpdateDialog: false,
    isForced: false,
    isDownloading: false,
    downloadProgress: 0,
    downloadComplete: false,
    downloadedFilePath: '',
    downloadError: '',
    showAnnouncementDialog: false,
    currentAnnouncement: null,
    announcementContent: '',
    pendingAnnouncements: []
  }),

  actions: {
    setManifest(manifest) {
      this.manifest = manifest
    },

    async checkForUpdatesManual() {
      const manifest = await fetchReleaseManifest()
      this.manifest = manifest

      if (isUpdateAvailable(manifest)) {
        try {
          const md = await fetchMarkdownContent(manifest.latestVersion.changelog)
          this.changelogContent = md
        } catch (_) {
          this.changelogContent = ''
        }
        this.isForced = isForceUpdate(manifest)
        this.downloadProgress = 0
        this.downloadComplete = false
        this.downloadedFilePath = ''
        this.downloadError = ''
        this.isDownloading = false
        this.showUpdateDialog = true
        return true
      }
      return false
    },

    async checkForUpdates() {
      try {
        const manifest = await fetchReleaseManifest()
        this.manifest = manifest

        if (isUpdateAvailable(manifest)) {
          const prefs = getUpdatePrefs()
          const forced = isForceUpdate(manifest)
          const latestCode = manifest.latestVersion.versionCode

          // Skip if user chose to skip this version (unless forced)
          if (!forced && prefs.skippedVersionCode >= latestCode) {
            this.checkAnnouncements()
            return
          }

          // Load changelog
          try {
            const md = await fetchMarkdownContent(manifest.latestVersion.changelog)
            this.changelogContent = md
          } catch (error) {
            this.changelogContent = ''
          }

          this.isForced = forced
          this.downloadProgress = 0
          this.downloadComplete = false
          this.downloadedFilePath = ''
          this.downloadError = ''
          this.isDownloading = false
          this.showUpdateDialog = true
        } else {
          this.checkAnnouncements()
        }
      } catch (error) {
        // Silently fail — update check is non-critical
        this.checkAnnouncements()
      }
    },

    checkAnnouncements() {
      if (!this.manifest || !this.manifest.announcements) return

      const prefs = getAnnouncementPrefs()
      const now = new Date().toISOString().slice(0, 10)

      const active = this.manifest.announcements.filter(ann => {
        if (prefs.dismissedIds.includes(ann.id)) return false
        if (ann.expiresAt && ann.expiresAt < now) return false
        return true
      })

      this.pendingAnnouncements = active
      this.showNextAnnouncement()
    },

    async showNextAnnouncement() {
      if (this.pendingAnnouncements.length === 0) {
        this.showAnnouncementDialog = false
        this.currentAnnouncement = null
        this.announcementContent = ''
        return
      }

      const ann = this.pendingAnnouncements[0]
      this.currentAnnouncement = ann

      try {
        const md = await fetchMarkdownContent(ann.body)
        this.announcementContent = md
      } catch (error) {
        this.announcementContent = ''
      }

      this.showAnnouncementDialog = true
    },

    dismissAnnouncement(dontShowAgain) {
      if (dontShowAgain && this.currentAnnouncement) {
        const prefs = getAnnouncementPrefs()
        const ids = new Set(prefs.dismissedIds)
        ids.add(this.currentAnnouncement.id)
        setAnnouncementPrefs({
          ...prefs,
          dismissedIds: [...ids].slice(-100),
          versionCode: config.APP_VERSION_CODE
        })
      }

      this.showAnnouncementDialog = false
      this.pendingAnnouncements = this.pendingAnnouncements.slice(1)

      setTimeout(() => {
        this.showNextAnnouncement()
      }, 300)
    },

    skipThisVersion() {
      if (this.manifest?.latestVersion) {
        const prefs = getUpdatePrefs()
        setUpdatePrefs({
          ...prefs,
          skippedVersionCode: this.manifest.latestVersion.versionCode
        })
      }
      this.showUpdateDialog = false
      this.checkAnnouncements()
    },

    dismissUpdate() {
      this.showUpdateDialog = false
      this.checkAnnouncements()
    },

    async startDownload() {
      const url = getDownloadUrl(this.manifest)
      if (!url) {
        this.fallbackToBrowser()
        return
      }

      this.isDownloading = true
      this.downloadProgress = 0
      this.downloadComplete = false
      this.downloadError = ''

      try {
        const filePath = await downloadApk(url, (progress) => {
          this.downloadProgress = progress
        })
        this.downloadedFilePath = filePath
        this.downloadComplete = true
        this.isDownloading = false
      } catch (error) {
        this.isDownloading = false
        this.downloadError = error.message || '下载失败'
      }
    },

    async installUpdate() {
      try {
        await installApk(this.downloadedFilePath)
      } catch (error) {
        this.fallbackToBrowser()
      }
    },

    fallbackToBrowser() {
      const url = getBrowserDownloadUrl(this.manifest)
      if (url) {
        openInBrowser(url)
      }
    },

    /**
     * 直接跳转浏览器下载（不使用应用内下载）
     */
    downloadInBrowser() {
      const url = getBrowserDownloadUrl(this.manifest)
      if (url) {
        openInBrowser(url)
        // 非强制更新时，跳转浏览器后关闭对话框
        if (!this.isForced) {
          this.showUpdateDialog = false
          this.checkAnnouncements()
        }
      }
    }
  }
})
