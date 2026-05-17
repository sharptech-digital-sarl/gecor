import dayjs from 'dayjs'
import 'dayjs/locale/en'
import 'dayjs/locale/fr'
import localizedFormat from 'dayjs/plugin/localizedFormat'
import relativeTime from 'dayjs/plugin/relativeTime'
import { normalizeApiDatetimeIsoString } from './apiDatetime'

dayjs.extend(localizedFormat)
dayjs.extend(relativeTime)

function dayjsFromApiInput(date: string | Date | dayjs.Dayjs | null | undefined): dayjs.Dayjs | null {
  if (date == null) return null
  if (dayjs.isDayjs(date)) return date.isValid() ? date : null
  if (date instanceof Date) {
    const d = dayjs(date)
    return d.isValid() ? d : null
  }
  if (typeof date === 'string') {
    const n = normalizeApiDatetimeIsoString(date)
    const d = dayjs(n ?? date)
    return d.isValid() ? d : null
  }
  const d = dayjs(date as never)
  return d.isValid() ? d : null
}

/**
 * Format a date according to the selected language
 * @param date - Date string, Date object, or dayjs object
 * @param format - Format string (default: 'LL' for long date format)
 * @param locale - Language code ('en' or 'fr')
 */
export function formatDate(
  date: string | Date | dayjs.Dayjs | null | undefined,
  format: string = 'LL',
  locale: string = 'en'
): string {
  const d = dayjsFromApiInput(date)
  if (!d) return '-'
  dayjs.locale(locale)
  return d.format(format)
}

/**
 * Format a time according to the selected language
 * @param date - Date string, Date object, or dayjs object
 * @param locale - Language code ('en' or 'fr')
 */
export function formatTime(
  date: string | Date | dayjs.Dayjs | null | undefined,
  locale: string = 'en'
): string {
  const d = dayjsFromApiInput(date)
  if (!d) return '-'
  dayjs.locale(locale)
  return d.format('LT')
}

/**
 * Format a date and time according to the selected language
 * @param date - Date string, Date object, or dayjs object
 * @param locale - Language code ('en' or 'fr')
 */
export function formatDateTime(
  date: string | Date | dayjs.Dayjs | null | undefined,
  locale: string = 'en'
): string {
  const d = dayjsFromApiInput(date)
  if (!d) return '-'
  dayjs.locale(locale)
  return d.format('LLL')
}

/**
 * Format a date range (start - end time)
 * @param startDate - Start date
 * @param endDate - End date
 * @param locale - Language code ('en' or 'fr')
 */
export function formatTimeRange(
  startDate: string | Date | dayjs.Dayjs | null | undefined,
  endDate: string | Date | dayjs.Dayjs | null | undefined,
  locale: string = 'en'
): string {
  const start = dayjsFromApiInput(startDate)
  const end = dayjsFromApiInput(endDate)
  if (!start || !end) return '-'
  dayjs.locale(locale)
  return `${start.format('LT')} - ${end.format('LT')}`
}

/**
 * Get current locale from i18n
 */
export function getCurrentLocale(): string {
  const stored = localStorage.getItem('i18nextLng')
  return stored || 'en'
}

