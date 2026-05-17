import { useMemo, useState } from 'react'
import { Box, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

interface LogoProps {
  size?: 'small' | 'medium' | 'large'
  showText?: boolean
  variant?: 'horizontal' | 'vertical'
}

const LOGO_DIR = '/logo'
const DEFAULT_LOGO_FILE = 'default.svg'

/** Nom de fichier uniquement (sous public/logo/), sans chemin — sécurité. */
function sanitizeLogoFileName(name: string): string {
  const base = (name || '').trim()
  if (!base || base.includes('/') || base.includes('\\') || base.includes('..')) {
    return DEFAULT_LOGO_FILE
  }
  if (!/^[\w.\-]+$/.test(base)) {
    return DEFAULT_LOGO_FILE
  }
  return base
}

function logoUrl(file: string): string {
  return `${LOGO_DIR}/${file}`
}

export default function Logo({ size = 'medium', showText = true, variant = 'horizontal' }: LogoProps) {
  const { t } = useTranslation()
  const configuredFile = sanitizeLogoFileName(
    (import.meta.env.VITE_LOGO_FILE as string | undefined) || DEFAULT_LOGO_FILE
  )
  const primarySrc = logoUrl(configuredFile)
  const fallbackImageSrc = logoUrl(DEFAULT_LOGO_FILE)

  const [imgSrc, setImgSrc] = useState(primarySrc)
  const [imageFailed, setImageFailed] = useState(false)

  const monogram = useMemo(() => {
    const fromEnv = (import.meta.env.VITE_LOGO_MONOGRAM as string | undefined)?.trim()
    if (fromEnv) {
      return fromEnv.slice(0, 3).toUpperCase()
    }
    const name = t('common.appName', { defaultValue: 'App' })
    const letters = name.replace(/[^a-zA-ZÀ-ÿ0-9]/g, '').slice(0, 2)
    return letters.length >= 2 ? letters.toUpperCase() : name.slice(0, 2).toUpperCase() || '•'
  }, [t])

  const sizes = {
    small: { icon: 32, textSize: 14, spacing: 1 },
    medium: { icon: 48, textSize: 16, spacing: 1.5 },
    large: { icon: 80, textSize: 24, spacing: 2 },
  }

  const currentSize = sizes[size]

  const handleImgError = () => {
    if (imgSrc !== fallbackImageSrc && configuredFile !== DEFAULT_LOGO_FILE) {
      setImgSrc(fallbackImageSrc)
      return
    }
    setImageFailed(true)
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: currentSize.spacing,
        flexDirection: variant === 'vertical' ? 'column' : 'row',
      }}
    >
      {!imageFailed ? (
        <Box
          component="img"
          src={imgSrc}
          alt={showText ? '' : t('common.appName')}
          onError={handleImgError}
          sx={{
            height: currentSize.icon,
            width: 'auto',
            maxWidth: currentSize.icon * 2,
            objectFit: 'contain',
            display: 'block',
            filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1))',
          }}
        />
      ) : (
        <Box
          className="text-logo"
          sx={{
            display: 'flex',
            width: currentSize.icon,
            height: currentSize.icon,
            borderRadius: 2,
            bgcolor: 'primary.dark',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 1px 4px rgba(0, 0, 0, 0.15)',
            position: 'relative',
            flexShrink: 0,
            '&::after': {
              content: '""',
              position: 'absolute',
              inset: 0,
              borderRadius: 2,
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, transparent 100%)',
            },
          }}
        >
          <Typography
            sx={{
              color: 'white',
              fontWeight: 800,
              fontSize: Math.max(currentSize.icon * (monogram.length > 2 ? 0.28 : 0.36), 10),
              letterSpacing: '-0.02em',
              lineHeight: 1,
              position: 'relative',
              zIndex: 1,
            }}
          >
            {monogram}
          </Typography>
        </Box>
      )}
      {showText && (
        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          <Typography
            variant={size === 'large' ? 'h5' : size === 'medium' ? 'h6' : 'body1'}
            sx={{
              fontWeight: 700,
              color: variant === 'horizontal' ? 'white' : 'text.primary',
              background: 'none',
              backgroundClip: 'unset',
              WebkitBackgroundClip: 'unset',
              WebkitTextFillColor: 'unset',
              lineHeight: 1.2,
              fontSize: `${currentSize.textSize}px`,
              textShadow: variant === 'horizontal' ? '0 1px 2px rgba(0, 0, 0, 0.1)' : 'none',
            }}
          >
            {t('common.appName')}
          </Typography>
          {variant === 'vertical' && size !== 'small' && (
            <Typography
              variant="caption"
              sx={{
                color: 'text.secondary',
                fontSize: `${currentSize.textSize * 0.7}px`,
                mt: 0.5,
              }}
            >
              {t('common.subtitle')}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  )
}
