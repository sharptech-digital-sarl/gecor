import { useEffect, useRef } from 'react'
import {
  getNotificationCategoryFromPayload,
  readAppointmentSoundPreset,
  readMailSoundPreset,
  readNotificationSoundEnabled,
  readOtherSoundPreset,
} from '../utils/notificationSoundPreferences'
import { playNotificationToneDeduped } from '../utils/playNotificationTone'

export type InAppNotificationRow = {
  id: string
  read_at: string | null
  payload?: Record<string, unknown> | null
}

/**
 * Détecte les nouvelles notifications (polling) et joue le son selon la catégorie (courrier, RDV, autre).
 * Le premier lot reçu sert de référence (aucun bip pour les déjà présentes).
 */
export function useInAppNotificationSounds(items: InAppNotificationRow[], enabled: boolean) {
  const initializedRef = useRef(false)
  const knownIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!enabled) {
      initializedRef.current = false
      knownIdsRef.current = new Set()
      return
    }

    if (items.length === 0) return

    const idsNow = new Set(items.map((i) => i.id))

    if (!initializedRef.current) {
      initializedRef.current = true
      knownIdsRef.current = idsNow
      return
    }

    const soundOn = readNotificationSoundEnabled()
    const mailPreset = readMailSoundPreset()
    const aptPreset = readAppointmentSoundPreset()
    const otherPreset = readOtherSoundPreset()

    for (const n of items) {
      if (knownIdsRef.current.has(n.id)) continue
      knownIdsRef.current.add(n.id)
      if (n.read_at || !soundOn) continue

      const cat = getNotificationCategoryFromPayload(n.payload ?? undefined)
      if (cat === 'mail') playNotificationToneDeduped('mail', mailPreset)
      else if (cat === 'appointment') playNotificationToneDeduped('appointment', aptPreset)
      else playNotificationToneDeduped('other', otherPreset)
    }
  }, [items, enabled])
}
