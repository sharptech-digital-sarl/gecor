import type { NotificationSoundPresetId } from './notificationSoundPreferences'

let sharedCtx: AudioContext | null = null

/** Évite double bip si Web Push et polling in-app arrivent presque en même temps. */
const DEDUP_MS = 2800
const lastPlayByCategory: Record<string, number> = {}

export function playNotificationToneDeduped(
  category: 'mail' | 'appointment' | 'other',
  preset: NotificationSoundPresetId
): void {
  const now = Date.now()
  const prev = lastPlayByCategory[category] ?? 0
  if (now - prev < DEDUP_MS) return
  lastPlayByCategory[category] = now
  playNotificationTone(preset)
}

function ctx(): AudioContext | null {
  try {
    if (typeof AudioContext === 'undefined') return null
    if (!sharedCtx) sharedCtx = new AudioContext()
    return sharedCtx
  } catch {
    return null
  }
}

/** Joue un bip court (doit être déclenché après une interaction utilisateur pour certains navigateurs). */
export function playNotificationTone(preset: NotificationSoundPresetId): void {
  const c = ctx()
  if (!c) return
  if (c.state === 'suspended') {
    void c.resume().catch(() => undefined)
  }

  const now = c.currentTime
  const scheduleBeep = (freq: number, start: number, duration: number, gain = 0.12) => {
    const osc = c.createOscillator()
    const g = c.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, start)
    g.gain.setValueAtTime(0, start)
    g.gain.linearRampToValueAtTime(gain, start + 0.02)
    g.gain.exponentialRampToValueAtTime(0.001, start + duration)
    osc.connect(g)
    g.connect(c.destination)
    osc.start(start)
    osc.stop(start + duration + 0.05)
  }

  switch (preset) {
    case 'soft':
      scheduleBeep(440, now, 0.14, 0.08)
      break
    case 'standard':
      scheduleBeep(660, now, 0.16, 0.11)
      break
    case 'bright':
      scheduleBeep(880, now, 0.13, 0.1)
      break
    case 'double':
      scheduleBeep(523, now, 0.09, 0.1)
      scheduleBeep(784, now + 0.12, 0.11, 0.1)
      break
    default:
      scheduleBeep(660, now, 0.16, 0.11)
  }
}
