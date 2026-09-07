const COLORS = {
  text: '#E2E8F0',
  muted: '#64748B',
  faint: '#3D4A5F',
  grid: 'rgba(148, 163, 184, 0.13)',
  blue: '#60A5FA',
  blueDark: '#2563EB',
  gold: '#F6C85F',
  surface: '#10101A'
}

const CATEGORY_COLORS = ['#60A5FA', '#F6C85F', '#A78BFA', '#38BDF8', '#94A3B8']

function html(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function shortDate(value) {
  const parts = String(value || '').split('-')
  return parts.length === 3 ? `${Number(parts[1])}/${Number(parts[2])}` : value
}

function tooltipShell(title, rows) {
  return `<div style="min-width:180px;padding:4px 2px;color:${COLORS.text};font-size:12px;line-height:1.7">
    <div style="font-weight:700;margin-bottom:5px">${html(title)}</div>${rows.join('')}
  </div>`
}

function tooltipRow(label, value, color = COLORS.blue) {
  return `<div style="display:flex;justify-content:space-between;gap:20px">
    <span style="color:${COLORS.muted}"><i style="display:inline-block;width:7px;height:7px;border-radius:2px;background:${color};margin-right:7px"></i>${html(label)}</span>
    <strong style="color:${COLORS.text}">${html(value)}</strong>
  </div>`
}

function baseTooltip() {
  return {
    trigger: 'item',
    // The formatter returns HTML; force the DOM tooltip instead of canvas rich text.
    renderMode: 'html',
    transitionDuration: 0,
    hideDelay: 0,
    backgroundColor: 'rgba(10, 10, 18, 0.96)',
    borderColor: 'rgba(96, 165, 250, 0.28)',
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { color: COLORS.text, fontSize: 12 },
    extraCssText: 'box-shadow:0 16px 50px rgba(0,0,0,.38);border-radius:8px;'
  }
}

function baseAxis() {
  return {
    axisLine: { lineStyle: { color: COLORS.grid } },
    axisTick: { show: false },
    axisLabel: { color: COLORS.muted, fontSize: 10 },
    splitLine: { lineStyle: { color: COLORS.grid } }
  }
}

export function buildCalendarHeatmapOption(points, metric, selectedDate, studentsTotal) {
  const lookup = new Map(points.map(item => [item.date, item]))
  const values = points.map(item => {
    const raw = metric === 'active_rate' ? item.active_rate : item.activity_count
    return {
      value: [item.date, raw ?? 0],
      itemStyle: item.date === selectedDate
        ? { borderColor: COLORS.gold, borderWidth: 2.5 }
        : { borderColor: 'transparent', borderWidth: 0 }
    }
  })
  const maxValue = metric === 'active_rate'
    ? 100
    : Math.max(1, ...points.map(item => Number(item.activity_count) || 0))
  const label = metric === 'active_rate' ? '活跃学生率' : '活动次数'
  const unit = metric === 'active_rate' ? '%' : ' 次'

  return {
    animationDuration: 360,
    animationDurationUpdate: 360,
    animationEasingUpdate: 'cubicOut',
    aria: { enabled: true, decal: { show: false }, description: `最近90天${label}日历热力图` },
    tooltip: {
      ...baseTooltip(),
      formatter(params) {
        const date = params.value?.[0]
        const item = lookup.get(date)
        if (!item) return ''
        const mixRows = (item.activity_mix || []).slice(0, 4).map((entry, index) =>
          tooltipRow(entry.activity_type, `${entry.count} 次`, CATEGORY_COLORS[index % CATEGORY_COLORS.length])
        )
        return tooltipShell(date, [
          tooltipRow('活跃学生', `${item.active_students} / ${studentsTotal} 人`),
          tooltipRow('活跃学生率', item.active_rate == null ? '暂无数据' : `${Number(item.active_rate).toFixed(1)}%`, COLORS.gold),
          tooltipRow('活动次数', `${item.activity_count} 次`, '#A78BFA'),
          ...mixRows
        ])
      }
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: false,
      orient: 'horizontal',
      left: 42,
      bottom: 0,
      itemWidth: 15,
      itemHeight: 160,
      text: [`高 ${maxValue}${unit}`, `低 0${unit}`],
      textGap: 10,
      textStyle: { color: COLORS.muted, fontSize: 10 },
      inRange: { color: ['#171A27', '#1D4ED8', '#60A5FA', '#F6C85F'] }
    },
    calendar: {
      top: 28,
      left: 42,
      right: 24,
      bottom: 50,
      range: points.length ? [points[0].date, points[points.length - 1].date] : undefined,
      cellSize: ['auto', 18],
      splitLine: { show: false },
      itemStyle: { color: '#171A27', borderColor: 'transparent', borderWidth: 0 },
      yearLabel: { show: false },
      monthLabel: { color: COLORS.muted, fontSize: 10, margin: 10 },
      dayLabel: {
        firstDay: 1,
        color: COLORS.muted,
        fontSize: 9,
        nameMap: ['日', '一', '二', '三', '四', '五', '六']
      }
    },
    series: [{
      id: 'activity-calendar',
      name: label,
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: values,
      emphasis: { itemStyle: { borderColor: '#F8FAFC', borderWidth: 2 } }
    }]
  }
}

export function buildActivityTrendOption(points) {
  const types = []
  points.forEach(point => (point.activity_mix || []).forEach(entry => {
    if (!types.includes(entry.activity_type)) types.push(entry.activity_type)
  }))
  const lookup = new Map(points.map(item => [item.date, item]))
  const dataZoom = points.length > 31
    ? [
        { type: 'inside', start: 55, end: 100 },
        { type: 'slider', start: 55, end: 100, height: 12, bottom: 0, borderColor: 'transparent', backgroundColor: '#171A27', fillerColor: 'rgba(96,165,250,.18)', handleStyle: { color: COLORS.blue } }
      ]
    : []
  return {
    animationDuration: 420,
    animationEasing: 'cubicOut',
    aria: { enabled: true, description: '按类型堆叠的每日学习活动次数' },
    color: CATEGORY_COLORS,
    tooltip: {
      ...baseTooltip(),
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(96,165,250,.06)' } },
      formatter(params) {
        const date = params?.[0]?.axisValue
        const item = lookup.get(date)
        const rows = (params || []).map(entry => tooltipRow(entry.seriesName, `${entry.value} 次`, entry.color))
        if (item) rows.push(tooltipRow('活跃学生率', item.active_rate == null ? '暂无数据' : `${Number(item.active_rate).toFixed(1)}%`, COLORS.gold))
        return tooltipShell(date, rows)
      }
    },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 9, itemHeight: 9, textStyle: { color: COLORS.muted, fontSize: 10 } },
    grid: { top: types.length ? 40 : 18, left: 36, right: 14, bottom: points.length > 31 ? 34 : 24, containLabel: true },
    xAxis: { ...baseAxis(), type: 'category', data: points.map(item => item.date), axisLabel: { color: COLORS.muted, fontSize: 9, formatter: shortDate, hideOverlap: true }, splitLine: { show: false } },
    yAxis: { ...baseAxis(), type: 'value', min: 0, minInterval: 1, name: '活动次数', nameTextStyle: { color: COLORS.muted, fontSize: 9, padding: [0, 0, 0, 8] } },
    dataZoom,
    series: types.map((type, index) => ({
      id: `activity-${type}`,
      name: type,
      type: 'bar',
      stack: 'activities',
      barMaxWidth: 24,
      data: points.map(item => item.activity_mix?.find(entry => entry.activity_type === type)?.count || 0),
      itemStyle: { borderRadius: index === types.length - 1 ? [3, 3, 0, 0] : 0 },
      emphasis: { focus: 'series' }
    }))
  }
}

export function buildActivityDonutOption(items) {
  const total = items.reduce((sum, item) => sum + Number(item.count || 0), 0)
  return {
    animationDuration: 420,
    animationEasing: 'cubicOut',
    aria: { enabled: true, description: '当前周期学习活动类型构成' },
    color: CATEGORY_COLORS,
    title: {
      text: String(total),
      subtext: '次活动',
      left: 'center',
      top: '35%',
      textStyle: { color: COLORS.text, fontSize: 24, fontWeight: 650 },
      subtextStyle: { color: COLORS.muted, fontSize: 10, lineHeight: 18 }
    },
    tooltip: {
      ...baseTooltip(),
      formatter(params) {
        return tooltipShell('活动构成', [tooltipRow(params.name, `${params.value} 次 · ${params.percent}%`, params.color)])
      }
    },
    legend: { bottom: 0, left: 'center', icon: 'roundRect', itemWidth: 8, itemHeight: 8, textStyle: { color: COLORS.muted, fontSize: 10 } },
    series: [{
      id: 'activity-mix',
      type: 'pie',
      radius: ['58%', '76%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: true,
      minAngle: 4,
      label: { show: false },
      itemStyle: { borderColor: COLORS.surface, borderWidth: 3, borderRadius: 3 },
      data: items.map(item => ({ name: item.activity_type, value: item.count })),
      emphasis: { scaleSize: 5 }
    }]
  }
}

export function buildTrendOption(points, valueKey, suffix = '%') {
  return {
    animationDuration: 420,
    animationEasing: 'cubicOut',
    aria: { enabled: true, description: `${valueKey}时间趋势` },
    tooltip: {
      ...baseTooltip(),
      trigger: 'axis',
      formatter(params) {
        const entry = params?.[0]
        const value = entry?.value
        return tooltipShell(entry?.axisValue || '', [tooltipRow('数值', value == null ? '暂无数据' : `${Number(value).toFixed(1)}${suffix}`, COLORS.blue)])
      }
    },
    grid: { top: 16, left: 36, right: 16, bottom: 26, containLabel: true },
    xAxis: { ...baseAxis(), type: 'category', boundaryGap: false, data: points.map(item => item.date), axisLabel: { color: COLORS.muted, fontSize: 9, formatter: shortDate, hideOverlap: true }, splitLine: { show: false } },
    yAxis: { ...baseAxis(), type: 'value', min: 0, max: 100, axisLabel: { color: COLORS.muted, fontSize: 9, formatter: `{value}${suffix}` } },
    series: [{
      id: `trend-${valueKey}`,
      type: 'line',
      data: points.map(item => item[valueKey]),
      connectNulls: false,
      smooth: 0.22,
      showSymbol: points.length <= 30,
      symbolSize: 5,
      lineStyle: { width: 2.5, color: COLORS.blue },
      itemStyle: { color: COLORS.surface, borderColor: '#93C5FD', borderWidth: 2 },
      areaStyle: { color: 'rgba(96, 165, 250, 0.08)' }
    }]
  }
}

export function buildKnowledgeLandscape(nodes) {
  const valid = nodes.filter(item => item.coverage_rate != null && item.avg_mastery != null)
  if (valid.length < 8) {
    const bars = [...valid].sort((a, b) => a.avg_mastery - b.avg_mastery).slice(0, 10)
    return {
      mode: 'bar',
      empty: bars.length === 0,
      option: buildHorizontalBarOption(bars, 'label', 'avg_mastery', '%', '掌握度')
    }
  }

  const chapters = [...new Set(valid.map(item => item.chapter))]
  return {
    mode: 'scatter',
    empty: false,
    option: {
      animationDuration: 480,
      animationEasing: 'cubicOut',
      aria: { enabled: true, description: '知识点覆盖率与平均掌握度关系散点图' },
      color: CATEGORY_COLORS,
      tooltip: {
        ...baseTooltip(),
        formatter(params) {
          const [coverage, mastery, assessed, label] = params.value
          return tooltipShell(label, [
            tooltipRow('覆盖率', `${Number(coverage).toFixed(1)}%`, params.color),
            tooltipRow('平均掌握度', `${Number(mastery).toFixed(1)}%`, COLORS.gold),
            tooltipRow('已评估', `${assessed} 人`, '#A78BFA')
          ])
        }
      },
      legend: { top: 0, left: 0, type: 'scroll', icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: COLORS.muted, fontSize: 9 } },
      grid: { top: 42, left: 44, right: 22, bottom: 34, containLabel: true },
      xAxis: { ...baseAxis(), type: 'value', min: 0, max: 100, name: '覆盖率', nameTextStyle: { color: COLORS.muted, fontSize: 9 }, axisLabel: { color: COLORS.muted, fontSize: 9, formatter: '{value}%' } },
      yAxis: { ...baseAxis(), type: 'value', min: 0, max: 100, name: '掌握度', nameTextStyle: { color: COLORS.muted, fontSize: 9 }, axisLabel: { color: COLORS.muted, fontSize: 9, formatter: '{value}%' } },
      series: chapters.map(chapter => ({
        id: `chapter-${chapter}`,
        name: chapter,
        type: 'scatter',
        data: valid.filter(item => item.chapter === chapter).map(item => [item.coverage_rate, item.avg_mastery, item.assessed_students, item.label]),
        symbolSize(value) { return Math.max(10, Math.min(30, 8 + Number(value[2] || 0) * 3)) },
        emphasis: { focus: 'series', scale: 1.25 }
      }))
    }
  }
}

export function buildHorizontalBarOption(items, labelField, valueField, suffix = '%', seriesName = '数值') {
  const values = items.map(item => item[valueField])
  return {
    animationDuration: 420,
    animationEasing: 'cubicOut',
    aria: { enabled: true, description: `${seriesName}横向比较` },
    tooltip: {
      ...baseTooltip(),
      formatter(params) {
        return tooltipShell(params.name, [tooltipRow(seriesName, `${Number(params.value).toFixed(1)}${suffix}`, params.color)])
      }
    },
    grid: { top: 8, left: 18, right: 38, bottom: 8, containLabel: true },
    xAxis: { ...baseAxis(), type: 'value', min: 0, max: valueField.includes('mastery') || valueField.includes('rate') ? 100 : undefined, axisLabel: { color: COLORS.muted, fontSize: 9, formatter: `{value}${suffix}` } },
    yAxis: { ...baseAxis(), type: 'category', inverse: true, data: items.map(item => item[labelField]), axisLabel: { color: COLORS.text, fontSize: 10, width: 130, overflow: 'truncate' }, splitLine: { show: false } },
    series: [{
      id: `bar-${valueField}`,
      name: seriesName,
      type: 'bar',
      data: values,
      barMaxWidth: 10,
      itemStyle: { color: COLORS.blue, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: COLORS.muted, fontSize: 9, formatter: `{c}${suffix}` },
    }]
  }
}

export function buildStudentChapterOption(nodes) {
  const chapters = new Map()
  nodes.forEach(node => {
    if (!chapters.has(node.chapter)) chapters.set(node.chapter, { label: node.chapter, total: 0, values: [] })
    const entry = chapters.get(node.chapter)
    entry.total += 1
    if (node.avg_mastery != null) entry.values.push(Number(node.avg_mastery))
  })
  const rows = [...chapters.values()]
    .filter(entry => entry.values.length)
    .map(entry => ({ label: entry.label, avg_mastery: entry.values.reduce((a, b) => a + b, 0) / entry.values.length, assessed: entry.values.length, total: entry.total }))
    .sort((a, b) => a.avg_mastery - b.avg_mastery)
  return { empty: rows.length === 0, option: buildHorizontalBarOption(rows, 'label', 'avg_mastery', '%', '章节掌握度') }
}
