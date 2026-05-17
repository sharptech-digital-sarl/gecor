import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Slider,
  Typography,
  Stack,
} from '@mui/material'
import { ZoomIn as ZoomInIcon, ZoomOut as ZoomOutIcon } from '@mui/icons-material'
import { useTranslation } from 'react-i18next'

const MIN_ZOOM = 1
const MAX_ZOOM = 4

export type VisitorPhotoZoomDialogProps = {
  open: boolean
  onClose: () => void
  imageUrl: string | null
  visitorName?: string
  /** Overrides default i18n title (e.g. ID document) */
  title?: string
  /** Overrides default i18n hint */
  hint?: string
}

/**
 * Grande vue de la photo du visiteur avec zoom (curseur + défilement).
 */
export default function VisitorPhotoZoomDialog({
  open,
  onClose,
  imageUrl,
  visitorName,
  title: titleOverride,
  hint: hintOverride,
}: VisitorPhotoZoomDialogProps) {
  const { t } = useTranslation()
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    if (!open) setZoom(1)
  }, [open])

  const effectiveOpen = open && !!imageUrl

  return (
    <Dialog open={effectiveOpen} onClose={onClose} maxWidth="md" fullWidth scroll="paper">
      <DialogTitle>
        {titleOverride ?? t('appointments.visitorPhotoZoomTitle')}
        {visitorName ? ` — ${visitorName}` : ''}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {hintOverride ?? t('appointments.visitorPhotoZoomHint')}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <ZoomOutIcon fontSize="small" color="action" sx={{ flexShrink: 0 }} />
          <Slider
            value={zoom}
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.25}
            onChange={(_, v) => setZoom(v as number)}
            aria-label={titleOverride ?? t('appointments.visitorPhotoZoomTitle')}
            sx={{ flex: 1 }}
          />
          <ZoomInIcon fontSize="small" color="action" sx={{ flexShrink: 0 }} />
          <Typography variant="caption" sx={{ minWidth: 44, textAlign: 'right' }}>
            {Math.round(zoom * 100)}%
          </Typography>
        </Stack>
        <Box
          sx={{
            overflow: 'auto',
            maxHeight: { xs: '50vh', sm: '65vh' },
            bgcolor: 'action.hover',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
            touchAction: 'pan-x pan-y pinch-zoom',
          }}
          onWheel={(e) => {
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault()
              const delta = e.deltaY > 0 ? -0.12 : 0.12
              setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z + delta)))
            }
          }}
        >
          {imageUrl && (
            <img
              src={imageUrl}
              alt={visitorName || ''}
              style={{
                width: `${zoom * 100}%`,
                maxWidth: 'none',
                height: 'auto',
                display: 'block',
                margin: '0 auto',
              }}
            />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common.close')}</Button>
      </DialogActions>
    </Dialog>
  )
}
