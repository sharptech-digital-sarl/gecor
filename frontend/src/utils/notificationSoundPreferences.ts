/** Préférences sons (localStorage + synchro GET/PATCH /auth/me). */

export const NOTIFICATION_SOUND_STORAGE = {
  enabled: 'fpi_notification_sound_enabled',
  mailPreset: 'fpi_notification_sound_mail',
  appointmentPreset: 'fpi_notification_sound_appointment',
  otherPreset: 'fpi_notification_sound_other',
} as const

export type NotificationSoundPresetId = 'soft' | 'standard' | 'bright' | 'double'

export const NOTIFICATION_SOUND_PRESETS: NotificationSoundPresetId[] = [
  'soft',
  'standard',
  'bright',
  'double',
]

export type NotificationSoundPrefsPayload = {
  enabled: boolean
  mail: NotificationSoundPresetId
  appointment: NotificationSoundPresetId
  other: NotificationSoundPresetId
}

export function readNotificationSoundEnabled(): boolean {
  try {
    return localStorage.getItem(NOTIFICATION_SOUND_STORAGE.enabled) === '1'
  } catch {
    return false
  }
}

export function writeNotificationSoundEnabled(on: boolean): void {
  try {
    localStorage.setItem(NOTIFICATION_SOUND_STORAGE.enabled, on ? '1' : '0')
  } catch {
    /* ignore */
  }
  dispatchPrefsChanged()
}

export function readMailSoundPreset(): NotificationSoundPresetId {
  return readPreset(NOTIFICATION_SOUND_STORAGE.mailPreset)
}

export function readAppointmentSoundPreset(): NotificationSoundPresetId {
  return readPreset(NOTIFICATION_SOUND_STORAGE.appointmentPreset)
}

export function readOtherSoundPreset(): NotificationSoundPresetId {
  return readPreset(NOTIFICATION_SOUND_STORAGE.otherPreset, 'soft')
}

export function writeMailSoundPreset(id: NotificationSoundPresetId): void {
  try {
    localStorage.setItem(NOTIFICATION_SOUND_STORAGE.mailPreset, id)
  } catch {
    /* ignore */
  }
  dispatchPrefsChanged()
}

export function writeAppointmentSoundPreset(id: NotificationSoundPresetId): void {
  try {
    localStorage.setItem(NOTIFICATION_SOUND_STORAGE.appointmentPreset, id)
  } catch {
    /* ignore */
  }
  dispatchPrefsChanged()
}

export function writeOtherSoundPreset(id: NotificationSoundPresetId): void {
  try {
    localStorage.setItem(NOTIFICATION_SOUND_STORAGE.otherPreset, id)
  } catch {
    /* ignore */
  }
  dispatchPrefsChanged()
}

/** Applique la réponse API sur le stockage local (Web Push + hooks). */
export function syncSoundPrefsFromServer(raw: unknown): void {
  if (!raw || typeof raw !== 'object') return
  const o = raw as Record<string, unknown>
  try {
    if (typeof o.enabled === 'boolean') {
      localStorage.setItem(NOTIFICATION_SOUND_STORAGE.enabled, o.enabled ? '1' : '0')
    }
    if (
      typeof o.mail === 'string' &&
      NOTIFICATION_SOUND_PRESETS.includes(o.mail as NotificationSoundPresetId)
    ) {
      localStorage.setItem(NOTIFICATION_SOUND_STORAGE.mailPreset, o.mail)
    }
    if (
      typeof o.appointment === 'string' &&
      NOTIFICATION_SOUND_PRESETS.includes(o.appointment as NotificationSoundPresetId)
    ) {
      localStorage.setItem(NOTIFICATION_SOUND_STORAGE.appointmentPreset, o.appointment)
    }
    if (
      typeof o.other === 'string' &&
      NOTIFICATION_SOUND_PRESETS.includes(o.other as NotificationSoundPresetId)
    ) {
      localStorage.setItem(NOTIFICATION_SOUND_STORAGE.otherPreset, o.other)
    }
  } catch {
    /* ignore */
  }
  dispatchPrefsChanged()
}

export function writeAllSoundPrefsToStorage(p: NotificationSoundPrefsPayload): void {
  writeNotificationSoundEnabled(p.enabled)
  writeMailSoundPreset(p.mail)
  writeAppointmentSoundPreset(p.appointment)
  writeOtherSoundPreset(p.other)
}

function readPreset(key: string, fallback: NotificationSoundPresetId = 'standard'): NotificationSoundPresetId {
  try {
    const v = localStorage.getItem(key)
    if (v && NOTIFICATION_SOUND_PRESETS.includes(v as NotificationSoundPresetId)) {
      return v as NotificationSoundPresetId
    }
  } catch {
    /* ignore */
  }
  return fallback
}

function dispatchPrefsChanged(): void {
  window.dispatchEvent(new Event('fpi-notification-sound-prefs'))
}

/** Catégorie métier dérivée du payload API (courrier / rendez-vous / autre). */
export function getNotificationCategoryFromPayload(
  payload: Record<string, unknown> | null | undefined
): 'mail' | 'appointment' | 'other' {
  if (!payload || typeof payload !== 'object') return 'other'
  const type = payload.type
  const target = payload.target
  if (type === 'deletion_request') {
    if (target === 'mail') return 'mail'
    if (target === 'appointment') return 'appointment'
    return 'other'
  }
  if (typeof type === 'string') {
    if (type.startsWith('mail_')) return 'mail'
    if (
      type === 'check_in' ||
      type === 'appointment' ||
      type.startsWith('appointment_')
    ) {
      return 'appointment'
    }
  }
  return 'other'
}
