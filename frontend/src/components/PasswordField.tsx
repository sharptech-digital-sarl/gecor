import { useState } from 'react'
import {
  TextField,
  TextFieldProps,
  InputAdornment,
  IconButton,
  Box,
  LinearProgress,
  Typography,
  Stack,
} from '@mui/material'
import { Visibility, VisibilityOff } from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import { evaluatePasswordStrength } from '../utils/passwordStrength'

export type PasswordFieldProps = Omit<TextFieldProps, 'type'> & {
  /** Affiche la jauge et la liste de critères (nouveaux mots de passe). */
  showStrengthMeter?: boolean
}

export default function PasswordField({
  showStrengthMeter = false,
  value,
  InputProps,
  ...rest
}: PasswordFieldProps) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  const str = typeof value === 'string' ? value : ''
  const strength = showStrengthMeter ? evaluatePasswordStrength(str) : null

  return (
    <Box>
      <TextField
        {...rest}
        type={visible ? 'text' : 'password'}
        value={value}
        InputProps={{
          ...InputProps,
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label={visible ? t('passwordStrength.hidePassword') : t('passwordStrength.showPassword')}
                onClick={() => setVisible((v) => !v)}
                onMouseDown={(e) => e.preventDefault()}
                edge="end"
                size="small"
              >
                {visible ? <VisibilityOff /> : <Visibility />}
              </IconButton>
              {InputProps?.endAdornment}
            </InputAdornment>
          ),
        }}
      />
      {strength && str.length > 0 && (
        <Box sx={{ mt: 1 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {t('passwordStrength.meterLabel')}
            </Typography>
            <Typography variant="caption" color={`${strength.color}.main`} sx={{ fontWeight: 600 }}>
              {t(strength.labelKey)}
            </Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={strength.percent}
            color={strength.color === 'info' ? 'primary' : strength.color}
            sx={{ height: 6, borderRadius: 1 }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {t('passwordStrength.complianceHint')}
          </Typography>
          <Stack component="ul" sx={{ m: 0, pl: 2, mt: 0.5 }} spacing={0.25}>
            {strength.rules.map((r) => (
              <Typography
                key={r.key}
                component="li"
                variant="caption"
                sx={{ color: r.ok ? 'success.main' : 'text.disabled' }}
              >
                {t(r.key)}
              </Typography>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  )
}
