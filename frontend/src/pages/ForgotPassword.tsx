import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Fade,
  Stack,
  Link,
} from '@mui/material'
import { Email as EmailIcon, Security as SecurityIcon } from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import Logo from '../components/Logo'

type StartFlow = 'noop' | 'email_otp' | 'totp'

type StartResponse = {
  flow: StartFlow
  message: string
  challenge_id?: string
  expires_in_seconds?: number
}

export default function ForgotPassword() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [code, setCode] = useState('')
  const [challengeId, setChallengeId] = useState<string | null>(null)
  const [step, setStep] = useState<'form' | 'verify' | 'done'>('form')
  const [verifyKind, setVerifyKind] = useState<'email_otp' | 'totp' | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post<StartResponse>('/auth/password-reset-request/start', {
        email: email.trim(),
        message: message.trim() || undefined,
      })
      if (data.flow === 'noop') {
        setStep('done')
      } else {
        if (!data.challenge_id) {
          setError(t('auth.forgotPasswordError'))
          return
        }
        setChallengeId(data.challenge_id)
        setVerifyKind(data.flow === 'totp' ? 'totp' : 'email_otp')
        setStep('verify')
      }
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || t('auth.forgotPasswordError'))
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!challengeId) return
    const normalized = code.replace(/\D/g, '').slice(0, 6)
    if (normalized.length !== 6) {
      setError(t('auth.forgotPasswordInvalidCode'))
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/password-reset-request/verify', {
        challenge_id: challengeId,
        code: normalized,
      })
      setStep('done')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || t('auth.forgotPasswordVerifyFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Container component="main" maxWidth="xs">
        <Fade in timeout={600}>
          <Paper
            elevation={0}
            sx={{
              p: 5,
              width: '100%',
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                <Logo size="large" showText={false} />
              </Box>
              <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                {t('auth.forgotPasswordTitle')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {step === 'verify'
                  ? verifyKind === 'totp'
                    ? t('auth.forgotPasswordStepTotp')
                    : t('auth.forgotPasswordStepEmail')
                  : t('auth.forgotPasswordIntro')}
              </Typography>
            </Box>

            {step === 'done' && (
              <Alert severity="success" sx={{ mb: 2 }}>
                {t('auth.forgotPasswordSuccess')}
              </Alert>
            )}

            {step === 'form' && (
              <Box component="form" onSubmit={handleStart}>
                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                  </Alert>
                )}
                <Stack spacing={2}>
                  <TextField
                    required
                    fullWidth
                    type="email"
                    label={t('usersAdmin.email')}
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={loading}
                    InputProps={{
                      startAdornment: (
                        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                          <EmailIcon sx={{ color: 'text.secondary' }} />
                        </Box>
                      ),
                    }}
                  />
                  <TextField
                    fullWidth
                    multiline
                    minRows={2}
                    label={t('auth.forgotPasswordMessageLabel')}
                    placeholder={t('auth.forgotPasswordMessagePlaceholder')}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={loading}
                    inputProps={{ maxLength: 2000 }}
                  />
                  <Button type="submit" fullWidth variant="contained" size="large" disabled={loading}>
                    {loading ? t('common.loading') : t('auth.forgotPasswordContinue')}
                  </Button>
                </Stack>
              </Box>
            )}

            {step === 'verify' && (
              <Box component="form" onSubmit={handleVerify}>
                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                  </Alert>
                )}
                <Alert severity="info" icon={<SecurityIcon />} sx={{ mb: 2 }}>
                  {verifyKind === 'totp' ? t('auth.forgotPasswordTotpHint') : t('auth.forgotPasswordOtpHint')}
                </Alert>
                <TextField
                  required
                  fullWidth
                  label={t('auth.forgotPasswordCodeLabel')}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  disabled={loading}
                  inputProps={{ maxLength: 6, inputMode: 'numeric', autoComplete: 'one-time-code' }}
                  sx={{ mb: 2 }}
                />
                <Stack direction="row" spacing={1}>
                  <Button
                    type="button"
                    variant="outlined"
                    fullWidth
                    disabled={loading}
                    onClick={() => {
                      setStep('form')
                      setChallengeId(null)
                      setCode('')
                      setError('')
                    }}
                  >
                    {t('common.back')}
                  </Button>
                  <Button type="submit" variant="contained" fullWidth disabled={loading || code.length !== 6}>
                    {loading ? t('common.loading') : t('auth.forgotPasswordVerifySubmit')}
                  </Button>
                </Stack>
              </Box>
            )}

            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Link component={RouterLink} to="/login" variant="body2" underline="hover">
                {t('auth.forgotPasswordBackLogin')}
              </Link>
            </Box>
          </Paper>
        </Fade>
      </Container>
    </Box>
  )
}
