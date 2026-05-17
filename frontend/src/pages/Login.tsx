import { useState, useEffect, useRef } from 'react'
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Fade,
  Stack,
  Link,
  Divider,
} from '@mui/material'
import {
  LockOutlined as LockIcon,
  PersonOutline as PersonIcon,
  Security as SecurityIcon,
} from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../hooks/useAuth'
import { tokenService } from '../services/tokenService'
import api from '../services/api'
import Logo from '../components/Logo'
import { APP_VERSION } from '../constants/appBrand'
import PasswordField from '../components/PasswordField'

export default function Login() {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [requiresMFA, setRequiresMFA] = useState(false)
  const [mfaSessionId, setMfaSessionId] = useState<string | null>(null)
  const { login, verifyMFA, isAuthenticated, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [googleLoading, setGoogleLoading] = useState(false)
  const googleOAuthHandled = useRef(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && (isAuthenticated || tokenService.hasTokens())) {
      navigate('/app')
    }
  }, [isAuthenticated, authLoading, navigate])

  // Retour OAuth Google (connexion sans MFA) : cookie refresh + jeton d'accès
  useEffect(() => {
    if (searchParams.get('google_auth') !== '1') return
    if (googleOAuthHandled.current) return
    if (sessionStorage.getItem('fpiconnect_google_auth_lock')) return
    googleOAuthHandled.current = true
    sessionStorage.setItem('fpiconnect_google_auth_lock', '1')
    const nextRaw = searchParams.get('next')
    const nextPath =
      nextRaw && nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/app'
    let cancelled = false
    ;(async () => {
      try {
        const { data } = await api.post<{ access_token?: string; refresh_token?: string }>('/auth/refresh', {})
        if (cancelled) return
        if (data?.access_token) {
          if (data.refresh_token) {
            tokenService.setTokens(data.access_token, data.refresh_token)
          } else {
            tokenService.setAccessToken(data.access_token)
          }
          setSearchParams({}, { replace: true })
          sessionStorage.removeItem('fpiconnect_google_auth_lock')
          window.location.assign(`${window.location.origin}${nextPath}`)
          return
        }
        sessionStorage.removeItem('fpiconnect_google_auth_lock')
        setError('auth.googleLoginOauthFailed')
      } catch {
        sessionStorage.removeItem('fpiconnect_google_auth_lock')
        if (!cancelled) setError('auth.googleLoginOauthFailed')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [searchParams, setSearchParams])

  // Retour OAuth Google avec MFA : afficher l'étape code
  useEffect(() => {
    if (searchParams.get('google_mfa') !== '1') return
    const sid = searchParams.get('mfa_session_id')
    if (!sid) return
    setRequiresMFA(true)
    setMfaSessionId(sid)
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  // Erreurs renvoyées par le callback Google
  useEffect(() => {
    const code = searchParams.get('google_login_error')
    if (!code) return
    const map: Record<string, string> = {
      no_account: 'auth.googleLoginNoAccount',
      inactive: 'auth.googleLoginInactive',
      mfa_policy: 'auth.googleLoginMfaPolicy',
      oauth_failed: 'auth.googleLoginOauthFailed',
      oauth_denied: 'auth.googleLoginOauthDenied',
    }
    setError(map[code] || 'auth.googleLoginOauthFailed')
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await login(username, password)
      
      // Check if MFA is required
      if (response.mfa_required && response.mfa_session_id) {
        setRequiresMFA(true)
        setMfaSessionId(response.mfa_session_id)
        setLoading(false)
      } else {
        // No MFA required, navigate to dashboard
        navigate('/app')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.loginFailed'))
      setLoading(false)
    }
  }

  const handleMFAVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    // Normalize the code: remove any whitespace
    const normalizedCode = mfaCode.replace(/\s/g, '').trim()
    
    // Validate MFA code format (6 digits)
    if (!normalizedCode || normalizedCode.length !== 6 || !/^\d{6}$/.test(normalizedCode)) {
      setError(t('auth.invalidMfaCode'))
      return
    }

    if (!mfaSessionId) {
      setError(t('auth.mfaSessionExpired'))
      return
    }

    setLoading(true)

    try {
      await verifyMFA(mfaSessionId, normalizedCode)
      navigate('/app')
    } catch (err: any) {
      // Enhanced error handling with more specific messages
      const errorDetail = err.response?.data?.detail || err.response?.data?.message
      let errorMessage = t('auth.mfaVerificationFailed')
      
      if (errorDetail) {
        // Check for common error patterns
        if (errorDetail.toLowerCase().includes('invalid') || errorDetail.toLowerCase().includes('incorrect')) {
          errorMessage = t('auth.invalidMfaCode') + ' - ' + errorDetail
        } else if (errorDetail.toLowerCase().includes('expired') || errorDetail.toLowerCase().includes('timeout')) {
          errorMessage = t('auth.mfaSessionExpired') + ' - ' + errorDetail
        } else {
          errorMessage = errorDetail
        }
      }
      
      setError(errorMessage)
      setMfaCode('')
      
      // Log error in development
      if (import.meta.env.DEV) {
        console.error('MFA verification error:', {
          error: err,
          status: err.response?.status,
          detail: errorDetail,
        })
      }
    } finally {
      setLoading(false)
    }
  }

  const handleBackToLogin = () => {
    setRequiresMFA(false)
    setMfaSessionId(null)
    setMfaCode('')
    setError('')
  }

  const handleGoogleLogin = async () => {
    setError('')
    setGoogleLoading(true)
    try {
      const response = await api.get<{ auth_url?: string }>('/auth/google/login/start', {
        params: { next_path: '/app' },
      })
      const url = response.data?.auth_url
      if (!url) throw new Error('Missing OAuth URL')
      window.location.href = url
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      setError(ax.response?.data?.detail || ax.message || 'auth.googleLoginOauthFailed')
    } finally {
      setGoogleLoading(false)
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
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            }}
          >
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Box 
                sx={{ 
                  display: 'flex', 
                  justifyContent: 'center', 
                  mb: 3,
                  '& img': {
                    filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.2))',
                  },
                }}
              >
                <Logo size="large" showText={false} />
              </Box>
              <Stack
                direction="row"
                alignItems="baseline"
                justifyContent="center"
                flexWrap="wrap"
                columnGap={1}
                rowGap={0.25}
                sx={{ mb: 1 }}
              >
                <Typography
                  component="h1"
                  sx={{
                    fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
                    fontWeight: 800,
                    fontSize: { xs: '1.65rem', sm: '2rem' },
                    letterSpacing: '0.04em',
                    lineHeight: 1.15,
                    color: 'primary.dark',
                  }}
                >
                  {t('auth.loginAppTitle')}
                </Typography>
                <Typography
                  component="span"
                  variant="subtitle1"
                  sx={{ fontWeight: 600, color: 'text.secondary', letterSpacing: '0.04em' }}
                >
                  v{APP_VERSION}
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                {t('common.subtitle')}
              </Typography>
              <Link
                component={RouterLink}
                to="/"
                variant="body2"
                underline="hover"
                sx={{ fontWeight: 600 }}
              >
                {t('auth.linkToPublicHome')}
              </Link>
            </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error.startsWith('auth.') ? t(error) : error}
            </Alert>
          )}

            {!requiresMFA ? (
              <Box component="form" onSubmit={handleSubmit}>
                <Stack spacing={2.5}>
                  <TextField
                    required
                    fullWidth
                    label={t('auth.username')}
                    autoComplete="username"
                    autoFocus
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                    InputProps={{
                      startAdornment: (
                        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                          <PersonIcon sx={{ color: 'text.secondary' }} />
                        </Box>
                      ),
                    }}
                  />
                  <PasswordField
                    required
                    fullWidth
                    label={t('auth.password')}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    showStrengthMeter
                    InputProps={{
                      startAdornment: (
                        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                          <LockIcon sx={{ color: 'text.secondary' }} />
                        </Box>
                      ),
                    }}
                  />
                  <Box sx={{ textAlign: 'right', mt: -1 }}>
                    <Link component={RouterLink} to="/forgot-password" variant="body2" underline="hover">
                      {t('auth.forgotPassword')}
                    </Link>
                  </Box>
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    color="primary"
                    size="large"
                    sx={{ mt: 2, py: 1.5 }}
                    disabled={loading || googleLoading}
                  >
                    {loading ? t('auth.signingIn') : t('auth.login')}
                  </Button>
                  <Divider sx={{ my: 1 }}>{t('auth.orContinueWith')}</Divider>
                  <Button
                    type="button"
                    fullWidth
                    variant="outlined"
                    color="inherit"
                    size="large"
                    sx={{
                      py: 1.5,
                      borderColor: 'divider',
                      color: 'text.primary',
                      '&:hover': { borderColor: 'text.secondary', bgcolor: 'action.hover' },
                    }}
                    disabled={loading || googleLoading}
                    onClick={handleGoogleLogin}
                  >
                    {googleLoading ? t('auth.googleRedirecting') : t('auth.continueWithGoogle')}
                  </Button>
                </Stack>
              </Box>
            ) : (
              <Box component="form" onSubmit={handleMFAVerify}>
                <Stack spacing={2.5}>
                  <Alert
                    severity="info"
                    icon={<SecurityIcon />}
                    sx={{
                      borderRadius: 2,
                      '& .MuiAlert-icon': {
                        alignItems: 'center',
                      },
                    }}
                  >
                    {t('auth.mfaRequired')}
                  </Alert>
                  <TextField
                    required
                    fullWidth
                    label={t('auth.mfaCode')}
                    autoFocus
                    value={mfaCode}
                    onChange={(e) => {
                      // Only allow 6 digits, remove any whitespace
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6)
                      setMfaCode(value)
                    }}
                    onPaste={(e) => {
                      // Handle paste: extract only digits
                      e.preventDefault()
                      const pastedText = e.clipboardData.getData('text')
                      const digitsOnly = pastedText.replace(/\D/g, '').slice(0, 6)
                      setMfaCode(digitsOnly)
                    }}
                    disabled={loading}
                    inputProps={{
                      maxLength: 6,
                      pattern: '[0-9]{6}',
                      inputMode: 'numeric',
                      autoComplete: 'one-time-code',
                    }}
                    helperText={t('auth.mfaCodeHelper')}
                    InputProps={{
                      startAdornment: (
                        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                          <SecurityIcon sx={{ color: 'text.secondary' }} />
                        </Box>
                      ),
                    }}
                  />
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    color="primary"
                    size="large"
                    sx={{ mt: 1, py: 1.5 }}
                    disabled={loading || mfaCode.length !== 6}
                  >
                    {loading ? t('auth.verifying') : t('auth.verify')}
                  </Button>
                  <Button
                    type="button"
                    fullWidth
                    variant="outlined"
                    onClick={handleBackToLogin}
                    disabled={loading}
                    sx={{ py: 1.5 }}
                  >
                    {t('auth.backToLogin')}
                  </Button>
                </Stack>
              </Box>
            )}
          </Paper>
        </Fade>
        <Stack
          direction="row"
          spacing={2}
          justifyContent="center"
          alignItems="center"
          flexWrap="wrap"
          sx={{ mt: 3, typography: 'caption' }}
        >
          <Link component={RouterLink} to="/privacy" variant="caption" underline="hover" color="text.secondary">
            {t('legal.navPrivacy')}
          </Link>
          <Typography component="span" variant="caption" color="text.disabled">
            ·
          </Typography>
          <Link component={RouterLink} to="/terms" variant="caption" underline="hover" color="text.secondary">
            {t('legal.navTerms')}
          </Link>
        </Stack>
      </Container>
    </Box>
  )
}

