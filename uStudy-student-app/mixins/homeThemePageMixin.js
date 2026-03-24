import { getStoredThemeMode } from '@/utils/themeMode'
import { syncThemeSystemUi } from '@/utils/themeSystemUi'

export default {
  data() {
    return {
      homeThemeMode: 'dark'
    }
  },

  computed: {
    isLightTheme() {
      return this.homeThemeMode === 'light'
    },

    pageThemeClass() {
      return this.isLightTheme ? 'theme-light' : 'theme-dark'
    }
  },

  methods: {
    restoreThemeMode(uiOptions) {
      this.homeThemeMode = getStoredThemeMode('dark')
      syncThemeSystemUi(this.homeThemeMode, uiOptions)
      return this.homeThemeMode
    }
  }
}
