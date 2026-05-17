import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Typography, Paper, Divider, Button, Alert } from '@mui/material'
import { useAuth } from '../hooks/useAuth'
import api from '../services/api'

/**
 * Connexion OAuth Google Calendar (tokens utilisateur, sync des RDV confirmés).
 */
export default function GoogleCalendarIntegration() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [calendarMessage, setCalendarMessage] = useState<null | { type: 'success' | 'error'; text: string }>(
    null,
  )
  const [calendarLoading, setCalendarLoading] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const googleStatus = params.get('google_calendar')
    if (!googleStatus) return
    if (googleStatus === 'connected') {
      setCalendarMessage({ type: 'success', text: t('settings.googleCalendarConnected') })
    } else {
      setCalendarMessage({ type: 'error', text: t('settings.googleCalendarError') })
    }
  }, [])

  const handleGoogleConnect = async () => {
    setCalendarLoading(true)
    try {
      const response = await api.get('/auth/google/start', { params: { next_path: '/app/settings' } })
      const url = response.data?.auth_url
      if (!url) throw new Error('Missing OAuth URL')
      window.location.href = url
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      setCalendarMessage({
        type: 'error',
        text: ax.response?.data?.detail || ax.message || t('settings.googleCalendarConnectFailed'),
      })
    } finally {
      setCalendarLoading(false)
    }
  }

  const handleGoogleDisconnect = async () => {
    setCalendarLoading(true)
    try {
      await api.post('/auth/google/disconnect')
      setCalendarMessage({ type: 'success', text: t('settings.googleCalendarDisconnected') })
      window.location.reload()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      setCalendarMessage({
        type: 'error',
        text: ax.response?.data?.detail || ax.message || t('settings.googleCalendarDisconnectFailed'),
      })
    } finally {
      setCalendarLoading(false)
    }
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        {t('settings.calendarIntegrations')}
      </Typography>
      <Divider sx={{ my: 2 }} />
      {calendarMessage && (
        <Alert severity={calendarMessage.type} sx={{ mb: 2 }} onClose={() => setCalendarMessage(null)}>
          {calendarMessage.text}
        </Alert>
      )}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.googleCalendarDescription')}
      </Typography>
      <Typography variant="body2" sx={{ mb: 2 }}>
        {t('settings.googleCalendarAccountLabel')}{' '}
        <strong>{user?.google_account_email || t('settings.googleCalendarNotConnected')}</strong>
      </Typography>
      {!user?.google_account_email ? (
        <Button variant="contained" onClick={handleGoogleConnect} disabled={calendarLoading}>
          {t('settings.googleCalendarConnect')}
        </Button>
      ) : (
        <Button variant="outlined" color="warning" onClick={handleGoogleDisconnect} disabled={calendarLoading}>
          {t('settings.googleCalendarDisconnect')}
        </Button>
      )}
    </Paper>
  )
}
