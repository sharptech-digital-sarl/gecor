import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Box,
  Typography,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Grid,
  Card,
  CardContent,
  Stack,
  FormControlLabel,
  Switch,
  Button,
} from '@mui/material'
import {
  Settings as SettingsIcon,
  Palette as PaletteIcon,
  Person as PersonIcon,
  VolumeUp as VolumeUpIcon,
} from '@mui/icons-material'
import MfaSetup from '../components/MfaSetup'
import PasswordChangeFlow from '../components/PasswordChangeFlow'
import GoogleCalendarIntegration from '../components/GoogleCalendarIntegration'
import { useAuth } from '../hooks/useAuth'
import api from '../services/api'
import { tokenService } from '../services/tokenService'
import { useAppThemeMode, type ThemePreference } from '../theme/AppThemeProvider'
import {
  NOTIFICATION_SOUND_PRESETS,
  readAppointmentSoundPreset,
  readMailSoundPreset,
  readNotificationSoundEnabled,
  readOtherSoundPreset,
  type NotificationSoundPrefsPayload,
  type NotificationSoundPresetId,
  writeAllSoundPrefsToStorage,
} from '../utils/notificationSoundPreferences'
import { playNotificationTone } from '../utils/playNotificationTone'

export default function Settings() {
  const { t, i18n } = useTranslation()
  const { user, refreshUser } = useAuth()
  const { preference: themePreference, setPreference: setThemePreference } = useAppThemeMode()
  const [language, setLanguage] = useState(i18n.language || 'en')
  const [soundEnabled, setSoundEnabled] = useState(() => readNotificationSoundEnabled())
  const [mailSound, setMailSound] = useState<NotificationSoundPresetId>(() => readMailSoundPreset())
  const [appointmentSound, setAppointmentSound] = useState<NotificationSoundPresetId>(() =>
    readAppointmentSoundPreset()
  )
  const [otherSound, setOtherSound] = useState<NotificationSoundPresetId>(() => readOtherSoundPreset())

  const persistNotificationSoundPrefs = useCallback(
    async (payload: NotificationSoundPrefsPayload) => {
      writeAllSoundPrefsToStorage(payload)
      if (!tokenService.getAccessToken()) return
      try {
        await api.patch('/auth/me', { notification_sound_prefs: payload })
        await refreshUser()
      } catch {
        /* ignore */
      }
    },
    [refreshUser]
  )

  const soundPrefsFromUserKey = user?.notification_sound_prefs
    ? JSON.stringify(user.notification_sound_prefs)
    : ''

  useEffect(() => {
    if (!user?.notification_sound_prefs) return
    const p = user.notification_sound_prefs
    setSoundEnabled(!!p.enabled)
    if (NOTIFICATION_SOUND_PRESETS.includes(p.mail)) setMailSound(p.mail)
    if (NOTIFICATION_SOUND_PRESETS.includes(p.appointment)) setAppointmentSound(p.appointment)
    if (NOTIFICATION_SOUND_PRESETS.includes(p.other)) setOtherSound(p.other)
  }, [user?.id, soundPrefsFromUserKey])

  useEffect(() => {
    setLanguage(i18n.language || 'en')
  }, [i18n.language])

  useEffect(() => {
    const pl = user?.preferred_locale
    if (pl !== 'en' && pl !== 'fr') return
    if (i18n.language === pl) return
    i18n.changeLanguage(pl)
    setLanguage(pl)
    localStorage.setItem('i18nextLng', pl)
  }, [user?.preferred_locale])

  const handleLanguageChange = async (event: { target: { value: string } }) => {
    const newLanguage = event.target.value
    setLanguage(newLanguage)
    i18n.changeLanguage(newLanguage)
    localStorage.setItem('i18nextLng', newLanguage)
    if (tokenService.getAccessToken() && (newLanguage === 'en' || newLanguage === 'fr')) {
      try {
        await api.patch('/auth/me', { preferred_locale: newLanguage })
        await refreshUser()
      } catch {
        /* ignore */
      }
    }
  }

  const handleThemeChange = (event: { target: { value: string } }) => {
    const v = event.target.value
    if (v === 'light' || v === 'dark' || v === 'system') {
      setThemePreference(v as ThemePreference)
    }
  }

  const presetLabel = (id: NotificationSoundPresetId) => t(`settings.soundPreset.${id}`)

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <SettingsIcon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Typography variant="h4">{t('settings.title')}</Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Box display="flex" alignItems="center" gap={1.5} mb={1}>
              <PaletteIcon color="primary" />
              <Typography variant="h6">{t('settings.appearance')}</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.appearanceDescription')}
            </Typography>
            <Divider sx={{ my: 2 }} />

            <Stack spacing={3} sx={{ mt: 2 }}>
              <FormControl fullWidth>
                <InputLabel id="language-select-label">{t('settings.language')}</InputLabel>
                <Select
                  labelId="language-select-label"
                  id="language-select"
                  value={language}
                  label={t('settings.language')}
                  onChange={handleLanguageChange}
                >
                  <MenuItem value="en">
                    <Box display="flex" alignItems="center" gap={1}>
                      <span>🇬🇧</span>
                      <span>{t('settings.english')}</span>
                    </Box>
                  </MenuItem>
                  <MenuItem value="fr">
                    <Box display="flex" alignItems="center" gap={1}>
                      <span>🇫🇷</span>
                      <span>{t('settings.french')}</span>
                    </Box>
                  </MenuItem>
                </Select>
              </FormControl>
              <Typography variant="body2" color="text.secondary">
                {t('settings.languageDescription')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('settings.languageEmailSync')}
              </Typography>

              <Divider />

              <FormControl fullWidth>
                <InputLabel id="theme-select-label">{t('settings.theme')}</InputLabel>
                <Select
                  labelId="theme-select-label"
                  id="theme-select"
                  value={themePreference}
                  label={t('settings.theme')}
                  onChange={handleThemeChange}
                >
                  <MenuItem value="light">{t('settings.themeLight')}</MenuItem>
                  <MenuItem value="dark">{t('settings.themeDark')}</MenuItem>
                  <MenuItem value="system">{t('settings.themeSystem')}</MenuItem>
                </Select>
              </FormControl>
              <Typography variant="body2" color="text.secondary">
                {t('settings.themeDescription')}
              </Typography>
            </Stack>
          </Paper>

          <Paper sx={{ p: 3, mt: 3 }}>
            <Box display="flex" alignItems="center" gap={1.5} mb={1}>
              <VolumeUpIcon color="primary" />
              <Typography variant="h6">{t('settings.notificationSounds')}</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.notificationSoundsDescription')}
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              {t('settings.notificationSoundsSynced')}
            </Typography>
            <Divider sx={{ my: 2 }} />
            <Stack spacing={2.5}>
              <FormControlLabel
                control={
                  <Switch
                    checked={soundEnabled}
                    onChange={(_, c) => {
                      setSoundEnabled(c)
                      void persistNotificationSoundPrefs({
                        enabled: c,
                        mail: mailSound,
                        appointment: appointmentSound,
                        other: otherSound,
                      })
                    }}
                  />
                }
                label={t('settings.notificationSoundsEnable')}
              />
              <FormControl fullWidth disabled={!soundEnabled}>
                <InputLabel id="sound-mail-label">{t('settings.notificationSoundMail')}</InputLabel>
                <Select
                  labelId="sound-mail-label"
                  label={t('settings.notificationSoundMail')}
                  value={mailSound}
                  onChange={(e) => {
                    const v = e.target.value as NotificationSoundPresetId
                    setMailSound(v)
                    void persistNotificationSoundPrefs({
                      enabled: soundEnabled,
                      mail: v,
                      appointment: appointmentSound,
                      other: otherSound,
                    })
                  }}
                >
                  {NOTIFICATION_SOUND_PRESETS.map((id) => (
                    <MenuItem key={id} value={id}>
                      {presetLabel(id)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth disabled={!soundEnabled}>
                <InputLabel id="sound-apt-label">{t('settings.notificationSoundAppointment')}</InputLabel>
                <Select
                  labelId="sound-apt-label"
                  label={t('settings.notificationSoundAppointment')}
                  value={appointmentSound}
                  onChange={(e) => {
                    const v = e.target.value as NotificationSoundPresetId
                    setAppointmentSound(v)
                    void persistNotificationSoundPrefs({
                      enabled: soundEnabled,
                      mail: mailSound,
                      appointment: v,
                      other: otherSound,
                    })
                  }}
                >
                  {NOTIFICATION_SOUND_PRESETS.map((id) => (
                    <MenuItem key={id} value={id}>
                      {presetLabel(id)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth disabled={!soundEnabled}>
                <InputLabel id="sound-other-label">{t('settings.notificationSoundOther')}</InputLabel>
                <Select
                  labelId="sound-other-label"
                  label={t('settings.notificationSoundOther')}
                  value={otherSound}
                  onChange={(e) => {
                    const v = e.target.value as NotificationSoundPresetId
                    setOtherSound(v)
                    void persistNotificationSoundPrefs({
                      enabled: soundEnabled,
                      mail: mailSound,
                      appointment: appointmentSound,
                      other: v,
                    })
                  }}
                >
                  {NOTIFICATION_SOUND_PRESETS.map((id) => (
                    <MenuItem key={id} value={id}>
                      {presetLabel(id)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Typography variant="caption" color="text.secondary">
                {t('settings.notificationSoundOtherHint')}
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={!soundEnabled}
                  onClick={() => playNotificationTone(mailSound)}
                >
                  {t('settings.notificationSoundTestMail')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={!soundEnabled}
                  onClick={() => playNotificationTone(appointmentSound)}
                >
                  {t('settings.notificationSoundTestAppointment')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={!soundEnabled}
                  onClick={() => playNotificationTone(otherSound)}
                >
                  {t('settings.notificationSoundTestOther')}
                </Button>
              </Stack>
            </Stack>
          </Paper>

          <Box sx={{ mt: 3 }}>
            <PasswordChangeFlow
              variant="inline"
              intro={t('settings.passwordChangeSectionIntro')}
              onSuccess={() => refreshUser()}
            />
          </Box>

          <Box sx={{ mt: 3 }}>
            <MfaSetup />
          </Box>

          <Box sx={{ mt: 3 }}>
            <Typography variant="h6" sx={{ mb: 1.5, px: 0.5 }}>
              {t('settings.integrationsSection')}
            </Typography>
            <GoogleCalendarIntegration />
          </Box>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <PersonIcon color="primary" fontSize="small" />
                <Typography variant="h6">{t('settings.account')}</Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />
              <Stack spacing={1.5}>
                <Box>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('settings.accountName')}
                  </Typography>
                  <Typography variant="body1">{user?.full_name || '—'}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('settings.accountUsername')}
                  </Typography>
                  <Typography variant="body1">{user?.username || '—'}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('settings.accountEmail')}
                  </Typography>
                  <Typography variant="body1" sx={{ wordBreak: 'break-word' }}>
                    {user?.email || '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('settings.accountRole')}
                  </Typography>
                  <Typography variant="body1">{user?.role || '—'}</Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
