import type { TFunction } from 'i18next'

export type CheckInPunctualityStatus = 'early' | 'on_time' | 'late'

export interface CheckInPunctualityApiPayload {
  message: string
  punctuality_status: CheckInPunctualityStatus
  minutes_delta: number
}

/** Aligné sur le backend : retard après l'heure prévue ; à l'heure dans les 5 min avant. */
export function computeCheckInPunctualityFromTimes(
  startTimeIso: string,
  checkInIso: string
): { status: CheckInPunctualityStatus; minutesDelta: number } {
  const start = new Date(startTimeIso).getTime()
  const checkin = new Date(checkInIso).getTime()
  if (Number.isNaN(start) || Number.isNaN(checkin)) {
    return { status: 'on_time', minutesDelta: 0 }
  }
  if (checkin > start) {
    const minutes = Math.max(1, Math.ceil((checkin - start) / 60_000))
    return { status: 'late', minutesDelta: minutes }
  }
  const windowStart = start - 5 * 60_000
  if (checkin >= windowStart) {
    return { status: 'on_time', minutesDelta: 0 }
  }
  const minutes = Math.max(1, Math.ceil((start - checkin) / 60_000))
  return { status: 'early', minutesDelta: minutes }
}

export function punctualityToastMessage(t: TFunction, data: CheckInPunctualityApiPayload): string {
  switch (data.punctuality_status) {
    case 'on_time':
      return t('appointments.checkInPunctualityOnTime')
    case 'early':
      return data.minutes_delta === 1
        ? t('appointments.checkInPunctualityEarlyOne')
        : t('appointments.checkInPunctualityEarlyOther', { count: data.minutes_delta })
    case 'late':
      return data.minutes_delta === 1
        ? t('appointments.checkInPunctualityLateOne')
        : t('appointments.checkInPunctualityLateOther', { count: data.minutes_delta })
    default:
      return data.message
  }
}
