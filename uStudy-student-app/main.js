import App from './App'
import 'katex/dist/katex.min.css'

// Polyfill for runtimes (e.g. app-plus on some Android engines) without requestAnimationFrame
const rafGlobal = typeof globalThis !== 'undefined'
  ? globalThis
  : (typeof window !== 'undefined'
    ? window
    : (typeof global !== 'undefined' ? global : null))

if (rafGlobal && typeof rafGlobal.requestAnimationFrame !== 'function') {
  rafGlobal.requestAnimationFrame = function (callback) {
    return setTimeout(function () {
      if (typeof callback === 'function') callback(Date.now())
    }, 16)
  }
}

if (rafGlobal && typeof rafGlobal.cancelAnimationFrame !== 'function') {
  rafGlobal.cancelAnimationFrame = function (id) {
    clearTimeout(id)
  }
}

// 启动阶段全局错误捕获：如果 JS 初始化过程中抛错，强制关闭 splash 防止卡死
if (rafGlobal) {
  rafGlobal.onerror = function (message, source, lineno) {
    try {
      // #ifdef APP-PLUS
      if (typeof plus !== 'undefined' && plus.navigator) {
        plus.navigator.closeSplashscreen()
      }
      // #endif
      try {
        uni.setStorageSync('__last_runtime_error__', String(message) + ' at ' + String(source) + ':' + lineno)
      } catch (e) {}
    } catch (e) {}
    return false
  }
}

// #ifndef VUE3
import Vue from 'vue'
import './uni.promisify.adaptor'
import { PiniaVuePlugin } from 'pinia'
import pinia from './store'
Vue.config.productionTip = false
Vue.use(PiniaVuePlugin)
App.mpType = 'app'
const app = new Vue({
  ...App,
  pinia
})
app.$mount()
// #endif

// #ifdef VUE3
import { createSSRApp } from 'vue'
import pinia from './store'
export function createApp() {
  const app = createSSRApp(App)
  app.use(pinia)
  return {
    app
  }
}
// #endif
