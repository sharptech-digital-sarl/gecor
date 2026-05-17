import { useTranslation } from 'react-i18next'
import {
  formatDate as formatDateUtil,
  formatTime as formatTimeUtil,
  formatDateTime as formatDateTimeUtil,
  formatTimeRange as formatTimeRangeUtil,
} from '../utils/dateFormat'

/**
 * Custom hook to format dates according to the current language
 */
export function useDateFormat() {
  const { i18n } = useTranslation()

  return {
    formatDate: (date: string | Date | null | undefined, format: string = 'LL') =>
      formatDateUtil(date, format, i18n.language),
    formatTime: (date: string | Date | null | undefined) =>
      formatTimeUtil(date, i18n.language),
    formatDateTime: (date: string | Date | null | undefined) =>
      formatDateTimeUtil(date, i18n.language),
    formatTimeRange: (
      startDate: string | Date | null | undefined,
      endDate: string | Date | null | undefined
    ) => formatTimeRangeUtil(startDate, endDate, i18n.language),
    locale: i18n.language,
  }
}

