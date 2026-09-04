<template>
  <view class="oj-workspace">
    <view class="oj-spec-line">
      <view class="language-tabs" aria-label="编程语言">
        <view
          v-for="language in allowedLanguages"
          :key="language"
          class="language-tab"
          :class="{ active: activeLanguage === language }"
          @tap="selectLanguage(language)"
        >{{ languageLabel(language) }}</view>
      </view>
      <view class="limit-line">
        <text>{{ displayTimeLimit }}</text><text>{{ displayMemoryLimit }}</text><text>源码 ≤ 64 KB</text>
      </view>
    </view>

    <view v-if="publicConfig.input_description || publicConfig.output_description" class="io-description">
      <view v-if="publicConfig.input_description"><text>输入</text><strong>{{ publicConfig.input_description }}</strong></view>
      <view v-if="publicConfig.output_description"><text>输出</text><strong>{{ publicConfig.output_description }}</strong></view>
    </view>

    <view class="editor-shell" :class="{ disabled }">
      <!-- #ifdef H5 -->
      <div ref="editorHost" class="editor-host"></div>
      <!-- #endif -->
      <!-- #ifndef H5 -->
      <textarea class="editor-fallback" :value="currentSource" :disabled="disabled" maxlength="65536" @input="onFallbackInput" />
      <!-- #endif -->
    </view>

    <view class="sample-actions">
      <view>
        <strong>公开样例</strong>
        <text>仅运行题面中公开的数据，不会消耗最终提交机会</text>
      </view>
      <view class="run-button" :class="{ disabled: disabled || running || !hasSource || !ojEnabled, running }" @tap="runSamples">
        <text>{{ runButtonLabel }}</text>
      </view>
    </view>

    <view v-if="!capabilityLoading && !ojEnabled" class="service-disabled-note">判题服务未启用，仍可编辑并暂存代码；样例运行暂不可用。</view>
    <view v-if="runError" class="run-error">{{ runError }}</view>
    <view v-if="runResult" class="run-result">
      <view class="run-summary">
        <view class="verdict-mark" :class="`verdict-${normalizedVerdict}`"></view>
        <strong>{{ verdictLabel(normalizedVerdict) }}</strong>
        <text v-if="runResult.time_ms !== undefined">{{ runResult.time_ms }} ms</text>
        <text v-if="runResult.memory_kb !== undefined">{{ formatMemory(runResult.memory_kb) }}</text>
      </view>
      <pre v-if="runResult.compile_output" class="console-output error-output">{{ runResult.compile_output }}</pre>
      <view v-for="(sample, index) in sampleResults" :key="sample.id || index" class="sample-result-row">
        <view class="sample-result-head"><strong>样例 {{ index + 1 }}</strong><text :class="`text-${normalizeVerdict(sample.verdict || sample.status)}`">{{ verdictLabel(normalizeVerdict(sample.verdict || sample.status)) }}</text></view>
        <view class="sample-columns">
          <view><text>输入</text><pre>{{ sample.input ?? publicSamples[index]?.input ?? '' }}</pre></view>
          <view><text>期望输出</text><pre>{{ sample.expected_output ?? sample.output ?? publicSamples[index]?.output ?? '' }}</pre></view>
          <view><text>实际输出</text><pre>{{ sample.stdout ?? sample.actual_output ?? '' }}</pre></view>
        </view>
        <pre v-if="sample.stderr" class="console-output error-output">{{ sample.stderr }}</pre>
      </view>
      <pre v-if="!sampleResults.length && runResult.stdout" class="console-output">{{ runResult.stdout }}</pre>
      <pre v-if="!sampleResults.length && runResult.stderr" class="console-output error-output">{{ runResult.stderr }}</pre>
    </view>
  </view>
</template>

<script>
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { cpp } from '@codemirror/lang-cpp'
import { oneDark } from '@codemirror/theme-one-dark'
import { createAssignmentSampleRun, getAssignmentSampleRun, getOjCapabilities } from '@/api/assignments'

const TERMINAL_STATUSES = new Set(['completed', 'succeeded', 'success', 'accepted', 'failed', 'compile_error', 'wrong_answer', 'runtime_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'output_limit_exceeded', 'dangerous_syscall', 'system_error'])

export default {
  name: 'OjCodeEditor',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    assignmentId: { type: [String, Number], default: '' },
    question: { type: Object, default: () => ({}) },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      editor: null,
      activeLanguage: 'python3',
      languageBuffers: {},
      updatingFromProp: false,
      runId: '',
      running: false,
      runResult: null,
      runError: '',
      pollTimer: null,
      pollAttempts: 0,
      capabilityLoading: true,
      ojEnabled: false,
      capabilityLanguages: []
    }
  },
  computed: {
    publicConfig() { return this.question?.publicConfig || this.question?.public_config || {} },
    allowedLanguages() {
      const languages = this.publicConfig.allowed_languages || this.publicConfig.languages || ['python3', 'cpp20']
      return languages.filter(item => ['python3', 'cpp20'].includes(item)).length ? languages.filter(item => ['python3', 'cpp20'].includes(item)) : ['python3', 'cpp20']
    },
    starterCode() { return this.publicConfig.starter_code || this.publicConfig.starter_codes || {} },
    currentSource() { return this.languageBuffers[this.activeLanguage] || '' },
    hasSource() { return this.currentSource.trim().length > 0 },
    publicSamples() { return Array.isArray(this.publicConfig.samples) ? this.publicConfig.samples : (Array.isArray(this.publicConfig.public_samples) ? this.publicConfig.public_samples : []) },
    sampleResults() { return Array.isArray(this.runResult?.samples) ? this.runResult.samples : (Array.isArray(this.runResult?.results) ? this.runResult.results : []) },
    normalizedVerdict() { return this.normalizeVerdict(this.runResult?.verdict || this.runResult?.status) },
    displayTimeLimit() {
      const value = Number(this.publicConfig.time_limit_ms || 2000)
      const multiplier = this.activeLanguage === 'python3' ? Number(this.publicConfig.python_time_multiplier || 2) : 1
      return `时间 ${(value * multiplier / 1000).toFixed(value * multiplier % 1000 ? 1 : 0)} s`
    },
    displayMemoryLimit() { return `内存 ${Number(this.publicConfig.memory_limit_mb || 256)} MB` },
    runButtonLabel() {
      if (this.capabilityLoading) return '检查判题服务…'
      if (!this.ojEnabled) return '判题服务未启用'
      return this.running ? '运行中…' : '运行样例'
    }
  },
  watch: {
    modelValue: {
      deep: true,
      handler(value) {
        const language = value?.language || this.publicConfig.default_language || this.allowedLanguages[0] || 'python3'
        const source = typeof value?.source === 'string' ? value.source : ''
        if (language !== this.activeLanguage || source !== this.currentSource) {
          this.activeLanguage = language
          this.languageBuffers = { ...this.languageBuffers, [language]: source || this.starterFor(language) }
          this.replaceEditorDocument(this.languageBuffers[language])
        }
      }
    },
    disabled() { this.rebuildEditor() },
    question: { deep: false, handler() { this.initializeValue(); this.rebuildEditor() } }
  },
  mounted() {
    this.initializeValue()
    this.$nextTick(() => this.createEditor())
    this.loadCapabilities()
  },
  beforeUnmount() {
    this.clearPoll()
    if (this.editor) this.editor.destroy()
  },
  methods: {
    starterFor(language) {
      if (typeof this.starterCode === 'string') return this.starterCode
      return this.starterCode?.[language] || (language === 'cpp20' ? '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    return 0;\n}\n' : 'def solve():\n    pass\n\nif __name__ == "__main__":\n    solve()\n')
    },
    initializeValue() {
      const preferred = this.modelValue?.language || this.publicConfig.default_language || this.allowedLanguages[0] || 'python3'
      this.activeLanguage = this.allowedLanguages.includes(preferred) ? preferred : this.allowedLanguages[0]
      const source = typeof this.modelValue?.source === 'string' && this.modelValue.source ? this.modelValue.source : this.starterFor(this.activeLanguage)
      this.languageBuffers = { ...this.languageBuffers, [this.activeLanguage]: source }
      if (!this.modelValue?.source) this.emitValue()
    },
    languageExtension(language) { return language === 'cpp20' ? cpp() : python() },
    createEditor() {
      if (!this.$refs.editorHost || this.editor) return
      const component = this
      const state = EditorState.create({
        doc: this.currentSource,
        extensions: [
          lineNumbers(), highlightActiveLine(), highlightActiveLineGutter(), history(),
          keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
          this.languageExtension(this.activeLanguage), oneDark,
          EditorState.readOnly.of(this.disabled), EditorView.editable.of(!this.disabled),
          EditorView.lineWrapping,
          EditorView.updateListener.of((update) => {
            if (!update.docChanged || component.updatingFromProp) return
            component.languageBuffers = { ...component.languageBuffers, [component.activeLanguage]: update.state.doc.toString() }
            component.emitValue()
          })
        ]
      })
      this.editor = new EditorView({ state, parent: this.$refs.editorHost })
    },
    rebuildEditor() {
      this.$nextTick(() => {
        if (this.editor) { this.editor.destroy(); this.editor = null }
        this.createEditor()
      })
    },
    replaceEditorDocument(source) {
      if (!this.editor) return
      this.updatingFromProp = true
      this.editor.dispatch({ changes: { from: 0, to: this.editor.state.doc.length, insert: source || '' } })
      this.updatingFromProp = false
    },
    emitValue() { this.$emit('update:modelValue', { language: this.activeLanguage, source: this.currentSource }) },
    selectLanguage(language) {
      if (this.disabled || language === this.activeLanguage) return
      this.activeLanguage = language
      if (this.languageBuffers[language] === undefined) this.languageBuffers = { ...this.languageBuffers, [language]: this.starterFor(language) }
      this.runResult = null; this.runError = ''
      this.rebuildEditor(); this.emitValue()
    },
    onFallbackInput(event) {
      if (this.disabled) return
      this.languageBuffers = { ...this.languageBuffers, [this.activeLanguage]: event?.detail?.value || '' }
      this.emitValue()
    },
    async runSamples() {
      if (this.disabled || this.running || !this.hasSource || !this.ojEnabled || !this.assignmentId || !this.question?.id) return
      this.clearPoll(); this.running = true; this.runResult = null; this.runError = ''; this.pollAttempts = 0
      try {
        const response = await createAssignmentSampleRun(this.assignmentId, this.question.id, { language: this.activeLanguage, source: this.currentSource })
        this.runId = String(response?.run_id || response?.id || '')
        if (!this.runId) throw new Error('服务端未返回运行编号')
        if (TERMINAL_STATUSES.has(String(response?.status || '').toLowerCase())) this.finishRun(response)
        else this.schedulePoll(300)
      } catch (error) {
        this.running = false
        this.runError = error?.statusCode === 429 ? '样例运行过于频繁，请稍后再试' : (error?.data?.detail?.message || error?.data?.detail || error?.message || '样例运行提交失败')
      }
    },
    schedulePoll(delay = 900) { this.pollTimer = setTimeout(() => { this.pollTimer = null; this.pollRun() }, delay) },
    async pollRun() {
      if (!this.runId) return
      try {
        const response = await getAssignmentSampleRun(this.assignmentId, this.runId)
        const status = String(response?.status || '').toLowerCase()
        if (TERMINAL_STATUSES.has(status) || response?.verdict) this.finishRun(response)
        else if (++this.pollAttempts < 70) this.schedulePoll()
        else throw new Error('样例运行超时，请稍后重试')
      } catch (error) {
        this.running = false
        this.runError = error?.data?.detail?.message || error?.data?.detail || error?.message || '运行状态读取失败'
      }
    },
    finishRun(response) { this.running = false; this.runResult = response?.result || response; this.clearPoll() },
    clearPoll() { if (this.pollTimer) clearTimeout(this.pollTimer); this.pollTimer = null },
    normalizeVerdict(value) {
      const raw = String(value || '').toLowerCase().replace(/\s+/g, '_')
      const aliases = { ac: 'accepted', wa: 'wrong_answer', ce: 'compile_error', re: 'runtime_error', tle: 'time_limit_exceeded', mle: 'memory_limit_exceeded', ole: 'output_limit_exceeded', completed: 'accepted', succeeded: 'accepted', success: 'accepted', failed: 'system_error' }
      return aliases[raw] || raw || 'system_error'
    },
    verdictLabel(value) {
      return { accepted: '通过', wrong_answer: '答案错误', compile_error: '编译错误', runtime_error: '运行错误', time_limit_exceeded: '超出时间限制', memory_limit_exceeded: '超出内存限制', output_limit_exceeded: '输出超限', dangerous_syscall: '检测到危险调用', system_error: '判题服务异常', queued: '排队中', running: '运行中' }[value] || value
    },
    languageLabel(value) { return value === 'cpp20' ? 'GNU C++20' : 'Python 3.11' },
    formatMemory(kb) { return Number(kb) >= 1024 ? `${(Number(kb) / 1024).toFixed(1)} MB` : `${Number(kb)} KB` },
    async loadCapabilities() {
      this.capabilityLoading = true
      try {
        const response = await getOjCapabilities()
        this.ojEnabled = response?.enabled === true
        this.capabilityLanguages = Array.isArray(response?.languages) ? response.languages : []
      } catch (_) {
        this.ojEnabled = false
      } finally {
        this.capabilityLoading = false
      }
    }
  }
}
</script>

<style scoped>
.oj-workspace { margin-top: 18px; border-top: 1px solid rgba(167,139,250,.16); }
.oj-spec-line { min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid rgba(148,163,184,.09); }
.language-tabs { height: 48px; display: flex; align-items: stretch; gap: 20px; }
.language-tab { display: flex; align-items: center; position: relative; color: #64748b; font-size: 11px; cursor: pointer; transition: color .16s ease; }
.language-tab.active { color: #ddd6fe; }
.language-tab.active::after { content: ''; position: absolute; height: 2px; left: 0; right: 0; bottom: 0; background: #8b5cf6; }
.limit-line { display: flex; gap: 13px; color: #536175; font-size: 9px; }
.io-description { display: grid; grid-template-columns: 1fr 1fr; border-bottom: 1px solid rgba(148,163,184,.08); }
.io-description > view { min-height: 46px; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; border-right: 1px solid rgba(148,163,184,.08); box-sizing: border-box; }
.io-description > view:last-child { border-right: 0; }
.io-description text { color: #8b5cf6; font-size: 9px; text-transform: uppercase; }.io-description strong { color: #94a3b8; font-size: 10px; font-weight: 400; line-height: 1.5; white-space: pre-wrap; }
.editor-shell { min-height: 340px; overflow: hidden; background: #0d0e16; border-bottom: 1px solid rgba(148,163,184,.1); }.editor-shell.disabled { opacity: .72; }
.editor-host { min-height: 340px; }
.editor-fallback { width: 100%; min-height: 340px; padding: 14px; box-sizing: border-box; color: #d6d8e1; font: 12px/1.65 "SFMono-Regular",Consolas,monospace; background: #0d0e16; border: 0; }
.editor-host :deep(.cm-editor) { min-height: 340px; max-height: 480px; background: #0d0e16; color: #d6d8e1; font-size: 12px; }
.editor-host :deep(.cm-scroller) { overflow: auto; font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; line-height: 1.65; }
.editor-host :deep(.cm-gutters) { background: #0d0e16; color: #465268; border-right-color: rgba(148,163,184,.08); }
.editor-host :deep(.cm-activeLine),.editor-host :deep(.cm-activeLineGutter) { background: rgba(139,92,246,.06); }
.editor-host :deep(.cm-focused) { outline: none; }
.sample-actions { min-height: 62px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid rgba(148,163,184,.09); }
.sample-actions > view:first-child { display: flex; flex-direction: column; gap: 5px; }.sample-actions strong { color: #cbd5e1; font-size: 11px; }.sample-actions text { color: #5d6b80; font-size: 9px; }
.run-button { padding: 8px 13px; color: #ddd6fe; border: 1px solid rgba(167,139,250,.32); border-radius: 5px; cursor: pointer; transition: background .15s ease; }.run-button:hover { background: rgba(139,92,246,.12); }.run-button.disabled { opacity: .4; cursor: default; }
.run-button.running { animation: runPulse 1.1s ease-in-out infinite; }
.run-error { padding: 12px 0; color: #fb7185; font-size: 10px; }
.service-disabled-note { padding: 11px 0; color: #fbbf24; font-size: 9px; border-bottom: 1px solid rgba(245,158,11,.14); }
.run-result { animation: ojReveal .18s ease both; }.run-summary { height: 48px; display: flex; align-items: center; gap: 9px; border-bottom: 1px solid rgba(148,163,184,.08); }.run-summary strong { color: #d7dce7; font-size: 11px; }.run-summary text { color: #536175; font-size: 9px; }.verdict-mark { width: 6px; height: 6px; border-radius: 50%; background: #fb7185; }.verdict-accepted { background: #34d399; }.verdict-system_error { background: #f59e0b; }
.sample-result-row { padding: 14px 0 18px; border-bottom: 1px solid rgba(148,163,184,.08); }.sample-result-head { display: flex; justify-content: space-between; margin-bottom: 10px; }.sample-result-head strong,.sample-result-head text { font-size: 10px; }.sample-result-head strong { color: #94a3b8; }.text-accepted { color: #34d399; }.text-wrong_answer,.text-compile_error,.text-runtime_error,.text-time_limit_exceeded,.text-memory_limit_exceeded,.text-output_limit_exceeded { color: #fb7185; }
.sample-columns { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 1px; background: rgba(148,163,184,.08); }.sample-columns > view { min-width: 0; padding: 9px; background: #10111a; }.sample-columns text { color: #64748b; font-size: 8px; }.sample-columns pre,.console-output { margin: 7px 0 0; color: #c4cad6; font: 10px/1.55 "SFMono-Regular",Consolas,monospace; white-space: pre-wrap; word-break: break-all; }.console-output { padding: 10px; background: rgba(15,23,42,.45); }.error-output { color: #fda4af; }
@keyframes ojReveal { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@keyframes runPulse { 50% { border-color: rgba(167,139,250,.7); background: rgba(139,92,246,.12); } }
@media (max-width: 720px) { .oj-spec-line { align-items: flex-start; flex-direction: column; padding-bottom: 10px; }.limit-line { flex-wrap: wrap; }.io-description,.sample-columns { grid-template-columns: 1fr; }.editor-shell,.editor-host,.editor-host :deep(.cm-editor) { min-height: 280px; } }
@media (prefers-reduced-motion: reduce) { .run-button.running,.run-result { animation: none; } }
</style>
