import App from './App'

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
