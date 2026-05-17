import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
  type SxProps,
  type Theme,
} from '@mui/material'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import PasswordField from './PasswordField'

type FlowKind = 'email_otp' | 'totp'

type Props = {
  onSuccess: () => void | Promise<void>
  intro: string
  title?: string
  variant?: 'dialog' | 'inline'
  sx?: SxProps<Theme>
}

function mapErrorDetail(detail: unknown, t: (k: string) => string): string {
  if (typeof detail !== 'string') return t('settings.passwordChangeError')
  const d = detail
  if (d === 'Current password is incorrect') return t('settings.passwordChangeErrorCurrent')
  if (d === 'New password must be different from current password')
    return t('settings.passwordChangeErrorSame')
  if (d === 'Invalid verification code' || d === 'Invalid authenticator code')
    return t('settings.passwordChangeErrorOtp')
  if (d === 'Invalid or expired challenge') return t('settings.passwordChangeErrorChallenge')
  if (
    d.includes('SMTP') ||
    d.includes('Email OTP is unavailable') ||
    d.includes('Could not send verification email')
  )
    return t('settings.passwordChangeErrorSmtp')
  return d
}

export default function PasswordChangeFlow({
  onSuccess,
  intro,
  title,
  variant = 'inline',
  sx,
}: Props) {
  const { t } = useTranslation()
  const [step, setStep] = useState<'passwords' | 'otp'>('passwords')
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [challengeId, setChallengeId] = useState<string | null>(null)
  const [flow, setFlow] = useState<FlowKind | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resetAll = () => {
    setStep('passwords')
    setCurrent('')
    setNext('')
    setConfirm('')
    setOtpCode('')
    setChallengeId(null)
    setFlow(null)
    setError('')
  }

  const handleStart = async () => {
    setError('')
    if (next.length < 8) {
      setError(t('settings.passwordChangeTooShort'))
      return
    }
    if (next !== confirm) {
      setError(t('settings.passwordChangeMismatch'))
      return
    }
    setLoading(true)
    try {
      const { data } = await api.post<{
        flow: FlowKind
        challenge_id: string
        expires_in_seconds: number
        message: string
      }>('/auth/me/change-password/start', {
        current_password: current,
        new_password: next,
      })
      setChallengeId(data.challenge_id)
      setFlow(data.flow)
      setOtpCode('')
      setStep('otp')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } }
      const detail = ax.response?.data?.detail
      setError(mapErrorDetail(detail, t))
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async () => {
    if (!challengeId) return
    setError('')
    const digits = otpCode.replace(/\D/g, '')
    if (digits.length !== 6) {
      setError(t('settings.passwordChangeOtpInvalid'))
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/me/change-password/complete', {
        challenge_id: challengeId,
        code: digits,
      })
      resetAll()
      await onSuccess()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } }
      const detail = ax.response?.data?.detail
      setError(mapErrorDetail(detail, t))
    } finally {
      setLoading(false)
    }
  }

  const body = (
    <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {intro}
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {step === 'passwords' && (
        <Stack spacing={2}>
          <PasswordField
            fullWidth
            label={t('settings.passwordChangeCurrent')}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            disabled={loading}
            autoComplete="current-password"
            showStrengthMeter={false}
          />
          <PasswordField
            fullWidth
            label={t('settings.passwordChangeNew')}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            disabled={loading}
            autoComplete="new-password"
            showStrengthMeter
          />
          <PasswordField
            fullWidth
            label={t('settings.passwordChangeConfirm')}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={loading}
            autoComplete="new-password"
            showStrengthMeter={false}
          />
          <Box>
            <Button
              variant="contained"
              disabled={
                loading ||
                !current ||
                next.length < 8 ||
                next !== confirm
              }
              onClick={() => void handleStart()}
            >
              {loading ? t('common.loading') : t('settings.passwordChangeRequestCode')}
            </Button>
          </Box>
        </Stack>
      )}

      {step === 'otp' && (
        <Stack spacing={2}>
          <Alert severity="info">
            {flow === 'totp'
              ? t('settings.passwordChangeOtpHintTotp')
              : t('settings.passwordChangeOtpHintEmail')}
          </Alert>
          <TextField
            fullWidth
            label={t('settings.passwordChangeOtpLabel')}
            value={otpCode}
            onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            disabled={loading}
            inputProps={{
              inputMode: 'numeric',
              maxLength: 6,
              'aria-label': t('settings.passwordChangeOtpLabel'),
            }}
            autoComplete="one-time-code"
          />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              variant="outlined"
              disabled={loading}
              onClick={() => {
                setStep('passwords')
                setOtpCode('')
                setError('')
              }}
            >
              {t('settings.passwordChangeBack')}
            </Button>
            <Button
              variant="contained"
              disabled={loading || otpCode.replace(/\D/g, '').length !== 6}
              onClick={() => void handleComplete()}
            >
              {loading ? t('common.loading') : t('settings.passwordChangeVerify')}
            </Button>
          </Stack>
        </Stack>
      )}
    </>
  )

  if (variant === 'dialog') {
    return <Box sx={sx}>{body}</Box>
  }

  return (
    <Paper sx={{ p: 3, ...sx }}>
      <Box display="flex" alignItems="center" gap={1.5} mb={1}>
        <LockOutlinedIcon color="primary" />
        <Typography variant="h6">{title ?? t('settings.passwordChangeSectionTitle')}</Typography>
      </Box>
      <Divider sx={{ my: 2 }} />
      {body}
    </Paper>
  )
}
