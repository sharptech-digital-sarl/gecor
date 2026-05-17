import type { TFunction } from 'i18next'

/** Messages anglais renvoyés par l’API → clés i18n (appointments.*). */
const APPOINTMENT_API_DETAIL_KEYS: Record<string, string> = {
  'Visitor already checked in': 'appointments.visitorAlreadyCheckedIn',
}

export function translateKnownAppointmentApiDetail(t: TFunction, detail: unknown): string | null {
  if (typeof detail !== 'string') return null
  const key = APPOINTMENT_API_DETAIL_KEYS[detail]
  return key ? t(key) : null
}

export function axiosErrorDetail(err: unknown): unknown {
  if (typeof err !== 'object' || err === null || !('response' in err)) return undefined
  return (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
}
