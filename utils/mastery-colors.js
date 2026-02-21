// Mastery color gradient endpoints (0-100 segmented interpolation)
const MASTERY_COLOR_START = { r: 255, g: 50, b: 66 }   // #FF3242 (mastery=0)
const MASTERY_COLOR_MID   = { r: 255, g: 217, b: 61 }   // #FFD93D (mastery=50)
const MASTERY_COLOR_END   = { r: 73, g: 255, b: 170 }    // #49FFAA (mastery=100)

export function interpolateMasteryRGB(mastery) {
  const m = Math.max(0, Math.min(100, mastery ?? 0))
  if (m <= 50) {
    const t = m / 50
    return {
      r: Math.round(MASTERY_COLOR_START.r + (MASTERY_COLOR_MID.r - MASTERY_COLOR_START.r) * t),
      g: Math.round(MASTERY_COLOR_START.g + (MASTERY_COLOR_MID.g - MASTERY_COLOR_START.g) * t),
      b: Math.round(MASTERY_COLOR_START.b + (MASTERY_COLOR_MID.b - MASTERY_COLOR_START.b) * t)
    }
  }
  const t = (m - 50) / 50
  return {
    r: Math.round(MASTERY_COLOR_MID.r + (MASTERY_COLOR_END.r - MASTERY_COLOR_MID.r) * t),
    g: Math.round(MASTERY_COLOR_MID.g + (MASTERY_COLOR_END.g - MASTERY_COLOR_MID.g) * t),
    b: Math.round(MASTERY_COLOR_MID.b + (MASTERY_COLOR_END.b - MASTERY_COLOR_MID.b) * t)
  }
}

export function getMasteryColor(mastery) {
  if (mastery == null) return '#9CA3AF'
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

export function getMasteryGlowColor(mastery, opacity = 0.5) {
  const { r, g, b } = interpolateMasteryRGB(mastery)
  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}
