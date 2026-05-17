import {
  readAppointmentSoundPreset,
  readMailSoundPreset,
  readNotificationSoundEnabled,
  readOtherSoundPreset,
} from './notificationSoundPreferences'
import { playNotificationToneDeduped } from './playNotificationTone'
import { queryClient } from '../queryClient'

let registered = false

function isCategory(x: unknown): x is 'mail' | 'appointment' | 'other' {
  return x === 'mail' || x === 'appointment' || x === 'other'
}

/** Écoute les messages du service worker (Web Push) pour jouer le timbre choisi. */
export function registerPushSoundListener(): void {
  if (registered) return
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return
  registered = true

  navigator.serviceWorker.addEventListener('message', (event: MessageEvent) => {
    const d = event.data
    if (!d || d.type !== 'fpi-push-sound') return

    void queryClient.invalidateQueries({ queryKey: ['in-app-notifications'] })

    if (!isCategory(d.category)) return
    if (!readNotificationSoundEnabled()) return

    if (d.category === 'mail') playNotificationToneDeduped('mail', readMailSoundPreset())
    else if (d.category === 'appointment')
      playNotificationToneDeduped('appointment', readAppointmentSoundPreset())
    else playNotificationToneDeduped('other', readOtherSoundPreset())
  })
}
