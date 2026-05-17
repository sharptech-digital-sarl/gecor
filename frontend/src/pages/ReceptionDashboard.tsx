import { Box, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { useDateFormat } from '../hooks/useDateFormat'
import AppointmentCalendarPanel from '../components/appointments/AppointmentCalendarPanel'

export default function ReceptionDashboard() {
  const { t } = useTranslation()
  const { formatDate } = useDateFormat()

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
          {t('reception.title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('reception.calendarSubtitle')} — {formatDate(new Date(), 'LL')}
        </Typography>
      </Box>
      <AppointmentCalendarPanel />
    </Box>
  )
}
