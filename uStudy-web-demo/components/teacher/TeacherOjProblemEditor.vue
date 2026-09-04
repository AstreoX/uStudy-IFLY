<template>
  <view class="oj-authoring">
    <view class="oj-authoring-bar">
      <view>
        <view class="validation-dot" :class="`validation-${validationStatus}`"></view>
        <strong>{{ validationLabel }}</strong>
        <text v-if="problem.checksum">校验 {{ shortChecksum }}</text>
      </view>
      <view class="oj-actions">
        <view class="ghost-action" :class="{ disabled: busy }" @tap="chooseZip">导入 Hydro ZIP</view>
        <view class="ghost-action" :class="{ disabled: busy }" @tap="saveProblem(false)">保存测试数据</view>
        <view class="validate-action" :class="{ disabled: busy }" @tap="startValidation">{{ validating ? '验证中…' : '验证参考解' }}</view>
      </view>
    </view>

    <view v-if="errorMessage" class="oj-error">{{ errorMessage }}</view>
    <view v-if="loading" class="oj-loading">读取 OJ 私有配置…</view>
    <template v-else>
      <view class="authoring-columns">
        <view class="oj-main-fields">
          <view class="field-row two">
            <label><text>允许语言</text><view class="language-checks"><view v-for="language in languageOptions" :key="language.value" :class="{ active: problem.public_config.allowed_languages.includes(language.value) }" @tap="toggleLanguage(language.value)">{{ language.label }}</view></view></label>
            <label><text>默认语言</text><picker :range="allowedLanguageOptions" range-key="label" @change="problem.public_config.default_language = allowedLanguageOptions[$event.detail.value]?.value"><view class="picker-value">{{ languageLabel(problem.public_config.default_language) }}⌄</view></picker></label>
          </view>
          <view class="field-row two">
            <label><text>输入说明</text><textarea v-model="problem.public_config.input_description" maxlength="1200" /></label>
            <label><text>输出说明</text><textarea v-model="problem.public_config.output_description" maxlength="1200" /></label>
          </view>
          <view class="field-row two">
            <label><text>Python 3.11 模板</text><textarea class="code-input" v-model="problem.public_config.starter_code.python3" /></label>
            <label><text>GNU C++20 模板</text><textarea class="code-input" v-model="problem.public_config.starter_code.cpp20" /></label>
          </view>
          <view class="field-row two">
            <label><text>参考解语言</text><picker :range="allowedLanguageOptions" range-key="label" @change="problem.reference_solution.language = allowedLanguageOptions[$event.detail.value]?.value"><view class="picker-value">{{ languageLabel(problem.reference_solution.language) }}⌄</view></picker></label>
            <label><text>输出比较</text><picker :range="compareOptions" range-key="label" @change="problem.public_config.compare_mode = compareOptions[$event.detail.value]?.value"><view class="picker-value">{{ compareLabel }}⌄</view></picker></label>
          </view>
          <label class="wide-label"><text>参考实现（仅教师可见）</text><textarea class="code-input reference-code" v-model="problem.reference_solution.source" /></label>
          <view class="limits-grid">
            <label><text>时间 ms</text><input type="number" min="100" max="10000" v-model.number="problem.public_config.time_limit_ms" /></label>
            <label><text>内存 MB</text><input type="number" min="64" max="512" v-model.number="problem.public_config.memory_limit_mb" /></label>
            <label><text>输出 KB</text><input type="number" min="1" max="64" v-model.number="problem.public_config.output_limit_kb" /></label>
            <label v-if="problem.public_config.compare_mode === 'float'"><text>绝对误差</text><input type="number" step="0.000001" min="0" v-model.number="problem.public_config.float_absolute_tolerance" /></label>
            <label v-if="problem.public_config.compare_mode === 'float'"><text>相对误差</text><input type="number" step="0.000001" min="0" v-model.number="problem.public_config.float_relative_tolerance" /></label>
          </view>
        </view>

        <view class="test-inspector">
          <view class="inspector-heading"><view><strong>公开样例</strong><text>{{ problem.public_config.samples.length }} 组 · 学生可见</text></view><view class="add-group" @tap="addPublicSample">+ 样例</view></view>
          <view v-for="(sample, sampleIndex) in problem.public_config.samples" :key="`sample-${sampleIndex}`" class="test-case public-case">
            <view class="case-title"><text>样例 {{ sampleIndex + 1 }}</text><view @tap="removePublicSample(sampleIndex)">删除</view></view>
            <textarea v-model="sample.input" placeholder="样例输入" />
            <textarea v-model="sample.output" placeholder="样例输出" />
          </view>
          <view class="inspector-heading hidden-heading"><view><strong>隐藏测试组</strong><text>{{ totalCases }} 个测试点 · 权重 {{ totalWeight }}%</text></view><view class="add-group" @tap="addGroup">+ 测试组</view></view>
          <view v-if="!problem.hidden_groups.length" class="empty-tests">还没有隐藏测试组，可手动添加或导入 ZIP。</view>
          <view v-for="(group, groupIndex) in problem.hidden_groups" :key="group.id || groupIndex" class="test-group">
            <view class="group-head">
              <input v-model="group.name" placeholder="测试组名称" />
              <label><input type="number" min="0" max="100" v-model.number="group.weight" /><text>%</text></label>
              <view class="remove-link" @tap="removeGroup(groupIndex)">移除</view>
            </view>
            <view v-for="(testCase, caseIndex) in group.cases" :key="testCase.id || caseIndex" class="test-case">
              <view class="case-title"><text>#{{ caseIndex + 1 }}</text><view @tap="removeCase(groupIndex, caseIndex)">删除</view></view>
              <textarea v-model="testCase.input" placeholder="标准输入" />
              <textarea v-model="testCase.expected_output" placeholder="期望输出；留空时由参考解生成" />
            </view>
            <view class="add-case" @tap="addCase(groupIndex)">+ 添加测试点</view>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import { getAssignmentJob, getOjProblem, importOjProblemZip, updateOjProblem, validateOjProblem } from '@/api/teacher-assignments'

function defaultProblem(question = {}) {
  const config = question.public_config || question.publicConfig || {}
  const answer = question.correct_answer || {}
  return {
    draft_id: question.grader_config?.problem_draft_id || '',
    checksum: question.grader_config?.checksum || '',
    validated_checksum: question.grader_config?.validated_checksum || '',
    validation_status: question.oj_validation_status || question.grader_config?.validation_status || 'unvalidated',
    public_config: {
      allowed_languages: config.allowed_languages || ['python3', 'cpp20'],
      default_language: config.default_language || 'python3',
      starter_code: { python3: config.starter_code?.python3 || '', cpp20: config.starter_code?.cpp20 || '' },
      input_description: config.input_description || '', output_description: config.output_description || '',
      samples: Array.isArray(config.samples) ? config.samples : [],
      time_limit_ms: Number(config.time_limit_ms || 2000), memory_limit_mb: Number(config.memory_limit_mb || 256), output_limit_kb: Number(config.output_limit_kb || 64),
      compare_mode: config.compare_mode || 'standard',
      float_absolute_tolerance: Number(config.float_absolute_tolerance ?? config.float_tolerance ?? 0.000001),
      float_relative_tolerance: Number(config.float_relative_tolerance ?? config.float_tolerance ?? 0.000001)
    },
    reference_solution: answer.reference_solution || question.reference_solution || { language: config.default_language || 'python3', source: answer.reference_code || '' },
    hidden_groups: []
  }
}

export default {
  name: 'TeacherOjProblemEditor',
  props: { spaceId: { type: [String, Number], required: true }, assignmentId: { type: [String, Number], required: true }, question: { type: Object, required: true } },
  emits: ['state-change'],
  data() {
    return { loading: true, saving: false, validating: false, errorMessage: '', problem: defaultProblem(this.question), pollTimer: null, validationJobId: '', languageOptions: [{ value: 'python3', label: 'Python 3.11' }, { value: 'cpp20', label: 'GNU C++20' }], compareOptions: [{ value: 'standard', label: '标准文本' }, { value: 'float', label: '浮点数' }] }
  },
  computed: {
    busy() { return this.loading || this.saving || this.validating },
    validationStatus() { return this.problem.validation_status || 'unvalidated' },
    validationLabel() { return { validated: '参考解已验证', valid: '参考解已验证', validating: '正在验证参考解', queued: '等待验证', failed: '验证失败', invalid: '验证失败', stale: '题目已修改，需重新验证', unvalidated: '尚未验证' }[this.validationStatus] || '尚未验证' },
    shortChecksum() { return String(this.problem.checksum || '').slice(0, 10) },
    allowedLanguageOptions() { return this.languageOptions.filter(item => this.problem.public_config.allowed_languages.includes(item.value)) },
    compareLabel() { return this.compareOptions.find(item => item.value === this.problem.public_config.compare_mode)?.label || '标准文本' },
    totalWeight() { return this.problem.hidden_groups.reduce((sum, group) => sum + (Number(group.weight) || 0), 0) },
    totalCases() { return this.problem.hidden_groups.reduce((sum, group) => sum + (Array.isArray(group.cases) ? group.cases.length : 0), 0) }
  },
  async mounted() { await this.loadProblem() },
  beforeUnmount() { this.clearPoll() },
  methods: {
    normalizeProblem(payload) {
      const source = payload?.problem || payload || {}
      const base = defaultProblem(this.question)
      return {
        ...base, ...source,
        public_config: { ...base.public_config, ...(source.public_config || {}), starter_code: { ...base.public_config.starter_code, ...(source.public_config?.starter_code || {}) } },
        reference_solution: { ...base.reference_solution, ...(source.reference_solution || {}) },
        assignment_version: source.assignment_version ?? payload?.assignment_version,
        hidden_groups: (source.hidden_groups || source.test_groups || []).map((group, groupIndex) => ({
          ...group,
          id: group.id || `group-${groupIndex}`,
          weight: Number(group.weight ?? group.score ?? 0),
          cases: (group.cases || []).map((item, index) => ({
            ...item,
            id: item.id || `case-${groupIndex}-${index}`,
            input: item.input || '',
            expected_output: item.expected_output ?? item.output ?? ''
          }))
        }))
      }
    },
    async loadProblem() {
      this.loading = true; this.errorMessage = ''
      try { this.problem = this.normalizeProblem(await getOjProblem(this.spaceId, this.assignmentId, this.question.id)); this.emitState() }
      catch (error) { this.errorMessage = error?.data?.detail?.message || error?.data?.detail || error?.message || 'OJ 配置读取失败' }
      finally { this.loading = false }
    },
    emitState() {
      this.$emit('state-change', { publicConfig: this.problem.public_config, graderConfig: { ...(this.question.grader_config || {}), problem_draft_id: this.problem.draft_id, checksum: this.problem.checksum, validated_checksum: this.problem.validated_checksum, validation_status: this.problem.validation_status }, validationStatus: this.problem.validation_status, checksum: this.problem.checksum, validatedChecksum: this.problem.validated_checksum, referenceSolution: this.problem.reference_solution, assignmentVersion: this.problem.assignment_version })
    },
    validateLocal() {
      if (!this.problem.public_config.allowed_languages.length) return '至少允许一种语言'
      if (!this.problem.reference_solution.source?.trim()) return '请填写参考实现'
      if (!this.problem.public_config.samples.length || this.problem.public_config.samples.some(item => !String(item.input ?? '').trim() || !String(item.output ?? '').trim())) return '请至少填写一组完整的公开样例'
      if (!this.problem.hidden_groups.length || !this.totalCases) return '至少添加一个隐藏测试点'
      if (Math.abs(this.totalWeight - 100) > 0.001) return '隐藏测试组权重必须合计 100%'
      if (this.problem.hidden_groups.length > 20 || this.totalCases > 100) return '最多支持 20 个测试组和 100 个测试点'
      if (new Set(this.problem.hidden_groups.map(group => group.name?.trim())).size !== this.problem.hidden_groups.length) return '隐藏测试组名称不能重复'
      if (this.problem.hidden_groups.some(group => !group.name?.trim() || Number(group.weight) <= 0 || !group.cases?.length || group.cases.some(item => !String(item.input ?? '').trim()))) return '请完善测试组名称、正权重和标准输入'
      if (this.problem.public_config.compare_mode === 'float' && (Number(this.problem.public_config.float_absolute_tolerance) <= 0 || Number(this.problem.public_config.float_relative_tolerance) <= 0)) return '浮点绝对误差和相对误差必须大于 0'
      return ''
    },
    async saveProblem(showToast = true) {
      if (this.busy) return false
      const localError = this.validateLocal(); if (localError) { this.errorMessage = localError; return false }
      this.saving = true; this.errorMessage = ''
      try {
        this.problem = this.normalizeProblem(await updateOjProblem(this.spaceId, this.assignmentId, this.question.id, { public_config: this.problem.public_config, reference_solution: this.problem.reference_solution, hidden_groups: this.problem.hidden_groups.map(group => ({ id: String(group.id).startsWith('group-') ? undefined : group.id, name: group.name.trim(), weight: Number(group.weight), cases: group.cases.map(item => ({ id: String(item.id).startsWith('case-') ? undefined : item.id, input: item.input, expected_output: item.expected_output || null })) })) }))
        this.emitState(); if (showToast) uni.showToast({ title: '测试数据已保存', icon: 'success' }); return true
      } catch (error) { this.errorMessage = error?.data?.detail?.message || error?.data?.detail || error?.message || 'OJ 配置保存失败'; return false }
      finally { this.saving = false }
    },
    async startValidation() {
      if (!(await this.saveProblem(false))) return
      this.validating = true; this.errorMessage = ''
      try {
        const response = await validateOjProblem(this.spaceId, this.assignmentId, this.question.id)
        const job = response?.job || response
        this.validationJobId = String(job?.job_id || job?.id || '')
        this.problem.validation_status = job?.status || 'queued'; this.emitState()
        if (!this.validationJobId) await this.loadProblem()
        else this.schedulePoll(500)
      } catch (error) { this.validating = false; this.errorMessage = error?.data?.detail?.message || error?.data?.detail || error?.message || '参考解验证提交失败' }
    },
    schedulePoll(delay = 1200) { this.clearPoll(); this.pollTimer = setTimeout(() => { this.pollTimer = null; this.pollValidation() }, delay) },
    async pollValidation() {
      try {
        const response = await getAssignmentJob(this.spaceId, this.validationJobId); const job = response?.job || response; const status = String(job?.status || '').toLowerCase()
        this.problem.validation_status = status; this.emitState()
        if (['completed', 'succeeded', 'success'].includes(status)) { this.validating = false; await this.loadProblem(); uni.showToast({ title: '参考解验证通过', icon: 'success' }) }
        else if (['failed', 'error'].includes(status)) { this.validating = false; this.problem.validation_status = 'failed'; this.errorMessage = job?.error_message || job?.error || '参考解未通过测试'; this.emitState() }
        else this.schedulePoll()
      } catch (error) { this.validating = false; this.errorMessage = error?.message || '验证状态读取失败' }
    },
    chooseZip() {
      if (this.busy) return
      uni.chooseFile({ count: 1, extension: ['zip'], success: result => { const path = result.tempFilePaths?.[0] || result.tempFiles?.[0]?.path; if (path) this.importZip(path) }, fail: error => { if (!String(error?.errMsg || '').includes('cancel')) this.errorMessage = '无法读取所选 ZIP' } })
    },
    async importZip(path) {
      this.saving = true; this.errorMessage = ''
      try { this.problem = this.normalizeProblem(await importOjProblemZip(this.spaceId, this.assignmentId, this.question.id, path)); this.emitState(); uni.showToast({ title: '测试数据已导入', icon: 'success' }) }
      catch (error) { this.errorMessage = error?.data?.detail?.message || error?.data?.detail || error?.message || 'ZIP 导入失败' }
      finally { this.saving = false }
    },
    toggleLanguage(language) {
      const list = this.problem.public_config.allowed_languages
      if (list.includes(language) && list.length > 1) this.problem.public_config.allowed_languages = list.filter(item => item !== language)
      else if (!list.includes(language)) this.problem.public_config.allowed_languages = [...list, language]
      if (!this.problem.public_config.allowed_languages.includes(this.problem.public_config.default_language)) this.problem.public_config.default_language = this.problem.public_config.allowed_languages[0]
    },
    addGroup() { if (this.problem.hidden_groups.length < 20) this.problem.hidden_groups.push({ id: `group-${Date.now()}`, name: `测试组 ${this.problem.hidden_groups.length + 1}`, weight: this.problem.hidden_groups.length ? 1 : 100, cases: [{ id: `case-${Date.now()}`, input: '', expected_output: '' }] }) },
    addPublicSample() { if (this.problem.public_config.samples.length < 20) this.problem.public_config.samples.push({ input: '', output: '' }) },
    removePublicSample(index) { this.problem.public_config.samples.splice(index, 1) },
    removeGroup(index) { this.problem.hidden_groups.splice(index, 1) },
    addCase(groupIndex) { if (this.totalCases < 100) this.problem.hidden_groups[groupIndex].cases.push({ id: `case-${Date.now()}`, input: '', expected_output: '' }) },
    removeCase(groupIndex, caseIndex) { this.problem.hidden_groups[groupIndex].cases.splice(caseIndex, 1) },
    languageLabel(value) { return value === 'cpp20' ? 'GNU C++20' : 'Python 3.11' },
    clearPoll() { if (this.pollTimer) clearTimeout(this.pollTimer); this.pollTimer = null }
  }
}
</script>

<style scoped>
.oj-authoring { margin-top: 18px; border-top: 1px solid rgba(167,139,250,.18); }.oj-authoring-bar { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid rgba(148,163,184,.09); }.oj-authoring-bar > view:first-child { display: flex; align-items: center; gap: 8px; }.oj-authoring-bar strong { color: #cbd5e1; font-size: 10px; }.oj-authoring-bar text { color: #536175; font-size: 8px; }.validation-dot { width: 6px; height: 6px; border-radius: 50%; background: #f59e0b; }.validation-validated,.validation-valid { background: #34d399; }.validation-failed,.validation-invalid { background: #fb7185; }.validation-validating,.validation-running { background: #8b5cf6; animation: validationPulse 1.1s ease infinite; }
.oj-actions { display: flex; align-items: center; gap: 7px; }.ghost-action,.validate-action,.add-group { padding: 7px 9px; color: #94a3b8; font-size: 8px; border: 1px solid rgba(148,163,184,.15); border-radius: 5px; cursor: pointer; }.validate-action { color: #ddd6fe; border-color: rgba(167,139,250,.34); }.disabled { opacity: .4; pointer-events: none; }.oj-error { padding: 9px 0; color: #fb7185; font-size: 9px; }.oj-loading,.empty-tests { padding: 18px 0; color: #64748b; font-size: 9px; }
.authoring-columns { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(280px,.8fr); gap: 24px; padding-top: 15px; }.oj-main-fields { min-width: 0; padding-right: 24px; border-right: 1px solid rgba(148,163,184,.09); }.field-row { display: grid; gap: 12px; margin-bottom: 12px; }.field-row.two { grid-template-columns: 1fr 1fr; }.field-row label,.wide-label,.limits-grid label { min-width: 0; display: flex; flex-direction: column; gap: 6px; }.field-row label > text,.wide-label > text,.limits-grid label > text { color: #64748b; font-size: 8px; }.field-row textarea,.wide-label textarea,.limits-grid input { width: 100%; box-sizing: border-box; padding: 8px; color: #d7dce7; font-size: 9px; background: rgba(15,23,42,.42); border: 1px solid rgba(148,163,184,.12); border-radius: 5px; }.field-row textarea { min-height: 62px; }.code-input { min-height: 120px !important; font: 9px/1.5 "SFMono-Regular",Consolas,monospace !important; }.reference-code { min-height: 180px !important; }.picker-value { min-height: 31px; display: flex; align-items: center; padding: 0 8px; color: #cbd5e1; font-size: 9px; border-bottom: 1px solid rgba(148,163,184,.14); }.language-checks { display: flex; gap: 6px; }.language-checks view { padding: 7px 8px; color: #64748b; font-size: 8px; border: 1px solid rgba(148,163,184,.13); border-radius: 4px; cursor: pointer; }.language-checks view.active { color: #ddd6fe; border-color: rgba(167,139,250,.32); background: rgba(139,92,246,.08); }.limits-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; margin-top: 12px; }.limits-grid input { height: 31px; }
.test-inspector { min-width: 0; }.inspector-heading { min-height: 44px; display: flex; align-items: flex-start; justify-content: space-between; }.inspector-heading.hidden-heading { margin-top: 18px; padding-top: 12px; border-top: 1px solid rgba(167,139,250,.16); }.inspector-heading > view:first-child { display: flex; flex-direction: column; gap: 4px; }.inspector-heading strong { color: #cbd5e1; font-size: 10px; }.inspector-heading text { color: #536175; font-size: 8px; }.test-group { padding: 12px 0 15px; border-top: 1px solid rgba(148,163,184,.09); }.group-head { display: grid; grid-template-columns: minmax(0,1fr) 58px auto; align-items: center; gap: 8px; }.group-head > input { min-width: 0; height: 29px; color: #cbd5e1; font-size: 9px; border: 0; border-bottom: 1px solid rgba(148,163,184,.13); }.group-head label { display: flex; align-items: center; }.group-head label input { width: 39px; height: 27px; color: #ddd6fe; font-size: 9px; border: 0; border-bottom: 1px solid rgba(167,139,250,.22); }.group-head label text,.remove-link { color: #64748b; font-size: 8px; }.remove-link { cursor: pointer; }.test-case { margin-top: 10px; padding-left: 9px; border-left: 2px solid rgba(139,92,246,.28); }.test-case.public-case { border-left-color: rgba(52,211,153,.32); }.case-title { display: flex; justify-content: space-between; color: #64748b; font-size: 8px; }.case-title view { cursor: pointer; }.test-case textarea { width: 100%; min-height: 48px; margin-top: 6px; padding: 7px; box-sizing: border-box; color: #cbd5e1; font: 8px/1.45 "SFMono-Regular",Consolas,monospace; background: #0d0e16; border: 1px solid rgba(148,163,184,.09); border-radius: 4px; }.add-case { margin-top: 9px; color: #a78bfa; font-size: 8px; cursor: pointer; }
@keyframes validationPulse { 50% { opacity: .35; transform: scale(.75); } }
@media (max-width: 980px) { .authoring-columns { grid-template-columns: 1fr; }.oj-main-fields { padding-right: 0; border-right: 0; }.limits-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 680px) { .oj-authoring-bar { align-items: flex-start; flex-direction: column; padding: 10px 0; }.oj-actions { flex-wrap: wrap; }.field-row.two { grid-template-columns: 1fr; } }
</style>
