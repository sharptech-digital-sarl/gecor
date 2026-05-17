import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Alert,
  Stack,
  Divider,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
} from '@mui/material'
import {
  Security as SecurityIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material'
import { QRCodeSVG } from 'qrcode.react'
import { alpha, useTheme } from '@mui/material/styles'
import { useAuth } from '../hooks/useAuth'

export default function MfaSetup() {
  const { t } = useTranslation()
  const theme = useTheme()
  const { user, setupMFA, activateMFA, disableMFA, refreshUser } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [setupData, setSetupData] = useState<{ secret: string; otpauth_url: string } | null>(null)
  const [activationCode, setActivationCode] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [disableDialogOpen, setDisableDialogOpen] = useState(false)

  const handleSetup = async () => {
    setLoading(true)
    setError('')
    setSuccess('')
    setSetupData(null)
    setActivationCode('')

    try {
      const data = await setupMFA()
      setSetupData(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('mfa.setupFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleActivate = async () => {
    if (!activationCode || activationCode.length !== 6 || !/^\d{6}$/.test(activationCode)) {
      setError(t('auth.invalidMfaCode'))
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await activateMFA(activationCode)
      setSuccess(t('mfa.activated'))
      setSetupData(null)
      setActivationCode('')
    } catch (err: any) {
      setError(err.response?.data?.detail || t('mfa.activationFailed'))
      setActivationCode('')
    } finally {
      setLoading(false)
    }
  }

  const handleDisable = async () => {
    if (!disableCode || disableCode.length !== 6 || !/^\d{6}$/.test(disableCode)) {
      setError(t('auth.invalidMfaCode'))
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await disableMFA(disableCode)
      setSuccess(t('mfa.disabled'))
      setDisableDialogOpen(false)
      setDisableCode('')
      await refreshUser()
    } catch (err: any) {
      setError(err.response?.data?.detail || t('mfa.disableFailed'))
      setDisableCode('')
    } finally {
      setLoading(false)
    }
  }

  const isMfaEnabled = user?.is_mfa_enabled || false

  const handleMfaSwitch = (_: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
    if (checked && !isMfaEnabled) {
      if (!setupData && !loading) {
        void handleSetup()
      }
      return
    }
    if (!checked && isMfaEnabled) {
      setDisableDialogOpen(true)
    }
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Box display="flex" alignItems="center" gap={2} mb={2}>
        <SecurityIcon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Box flex={1}>
          <Typography variant="h6">{t('settings.security')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('settings.securityDescription')}
          </Typography>
        </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          py: 1.5,
          px: 0,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            {t('mfa.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('mfa.toggleHint')}
          </Typography>
        </Box>
        <Switch
          checked={isMfaEnabled}
          onChange={handleMfaSwitch}
          color="primary"
          inputProps={{ 'aria-label': t('mfa.title') }}
          disabled={loading}
        />
      </Box>

      <Divider sx={{ my: 2 }} />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      {isMfaEnabled ? (
        <Stack spacing={2}>
          <Alert severity="success" icon={<CheckCircleIcon />}>
            {t('mfa.enabled')}
          </Alert>
          <Typography variant="body2" color="text.secondary">
            {t('mfa.enabledDescription')}
          </Typography>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={() => setDisableDialogOpen(true)}
            disabled={loading}
          >
            {t('mfa.disable')}
          </Button>
        </Stack>
      ) : (
        <Stack spacing={3}>
          {!setupData ? (
            <>
              <Typography variant="body2" color="text.secondary">
                {t('mfa.notEnabled')}
              </Typography>
              <Button
                variant="contained"
                color="primary"
                startIcon={<SecurityIcon />}
                onClick={handleSetup}
                disabled={loading}
              >
                {loading ? <CircularProgress size={20} /> : t('mfa.setup')}
              </Button>
            </>
          ) : (
            <>
              <Alert severity="info">
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {t('mfa.setupInstructions')}
                </Typography>
                <Typography variant="body2" component="ol" sx={{ pl: 2, m: 0 }}>
                  <li>{t('mfa.step1')}</li>
                  <li>{t('mfa.step2')}</li>
                  <li>{t('mfa.step3')}</li>
                </Typography>
              </Alert>

              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  p: 3,
                  bgcolor: 'background.paper',
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <QRCodeSVG
                  value={setupData.otpauth_url}
                  size={200}
                  level="M"
                  includeMargin={true}
                />
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                    {t('mfa.secretLabel')}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: 'monospace',
                      bgcolor: alpha(theme.palette.text.primary, 0.08),
                      p: 1,
                      borderRadius: 1,
                      wordBreak: 'break-all',
                    }}
                  >
                    {setupData.secret}
                  </Typography>
                </Box>
              </Box>

              <TextField
                fullWidth
                label={t('auth.mfaCode')}
                value={activationCode}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 6)
                  setActivationCode(value)
                }}
                disabled={loading}
                inputProps={{
                  maxLength: 6,
                  pattern: '[0-9]{6}',
                  inputMode: 'numeric',
                }}
                helperText={t('mfa.activationHelper')}
                InputProps={{
                  startAdornment: (
                    <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                      <SecurityIcon sx={{ color: 'text.secondary' }} />
                    </Box>
                  ),
                }}
              />

              <Stack direction="row" spacing={2}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleActivate}
                  disabled={loading || activationCode.length !== 6}
                >
                  {loading ? <CircularProgress size={20} /> : t('mfa.activate')}
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => {
                    setSetupData(null)
                    setActivationCode('')
                    setError('')
                  }}
                  disabled={loading}
                >
                  {t('common.cancel')}
                </Button>
              </Stack>
            </>
          )}
        </Stack>
      )}

      {/* Disable MFA Dialog */}
      <Dialog open={disableDialogOpen} onClose={() => setDisableDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('mfa.disableTitle')}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="warning">{t('mfa.disableWarning')}</Alert>
            <TextField
              fullWidth
              label={t('auth.mfaCode')}
              value={disableCode}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6)
                setDisableCode(value)
              }}
              disabled={loading}
              inputProps={{
                maxLength: 6,
                pattern: '[0-9]{6}',
                inputMode: 'numeric',
              }}
              helperText={t('mfa.disableHelper')}
              InputProps={{
                startAdornment: (
                  <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                    <SecurityIcon sx={{ color: 'text.secondary' }} />
                  </Box>
                ),
              }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDisableDialogOpen(false)} disabled={loading}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleDisable}
            variant="contained"
            color="error"
            disabled={loading || disableCode.length !== 6}
          >
            {loading ? <CircularProgress size={20} /> : t('mfa.disable')}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  )
}

