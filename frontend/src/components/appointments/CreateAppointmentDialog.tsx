import { useState, useRef, useEffect, useLayoutEffect, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Grid,
  Box,
  Typography,
  Menu,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  CircularProgress,
} from '@mui/material'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker'
import dayjs, { Dayjs } from 'dayjs'
import { useTranslation } from 'react-i18next'
import api from '../../services/api'

type VisitHostCandidate = {
  id: string
  full_name: string
  username: string
  role: string
}

type Props = {
  open: boolean
  onClose: () => void
  /** Si présent dans la liste des hôtes, pré-remplit le sélecteur (ex. utilisateur connecté). */
  defaultHostUserId?: string
  /** Créneau initial (ex. sélection sur le calendrier réception). `null` = horaires par défaut à l’ouverture. */
  initialRange?: { start: string | Date; end: string | Date } | null
}

type LocationMode = 'on_site' | 'custom'

export default function CreateAppointmentDialog({
  open,
  onClose,
  defaultHostUserId,
  initialRange = null,
}: Props) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [startTime, setStartTime] = useState<Dayjs | null>(dayjs().add(1, 'hour'))
  const [endTime, setEndTime] = useState<Dayjs | null>(dayjs().add(2, 'hour'))
  const [visitorName, setVisitorName] = useState('')
  const [visitorEmail, setVisitorEmail] = useState('')
  const [visitorPhone, setVisitorPhone] = useState('')
  const [visitorCompany, setVisitorCompany] = useState('')
  const [visitorPhotoDataUrl, setVisitorPhotoDataUrl] = useState<string | null>(null)
  const [visitorIdDocumentDataUrl, setVisitorIdDocumentDataUrl] = useState<string | null>(null)
  const photoFileInputRef = useRef<HTMLInputElement>(null)
  const idDocFileInputRef = useRef<HTMLInputElement>(null)
  const [photoMenuAnchor, setPhotoMenuAnchor] = useState<null | HTMLElement>(null)
  const [webcamOpen, setWebcamOpen] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const webcamStreamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState('')
  const [solicitedUserId, setSolicitedUserId] = useState('')
  const [locationMode, setLocationMode] = useState<LocationMode>('on_site')
  const [customLocation, setCustomLocation] = useState('')

  const {
    data: visitHosts,
    isLoading: visitHostsLoading,
    isError: visitHostsError,
  } = useQuery({
    queryKey: ['visit-host-candidates'],
    queryFn: async () => {
      const response = await api.get<VisitHostCandidate[]>('/users/visit-host-candidates')
      return response.data
    },
    enabled: open,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (!open || !visitHosts?.length) return
    const preferred =
      defaultHostUserId && visitHosts.some((h) => h.id === defaultHostUserId)
        ? defaultHostUserId
        : ''
    setSolicitedUserId(preferred)
  }, [open, visitHosts, defaultHostUserId])

  /** Clé stable pour réagir au créneau calendrier même si la référence d’objet ne change pas. */
  const initialRangeKey = useMemo(() => {
    if (initialRange?.start == null || initialRange?.end == null) return ''
    const a = dayjs(initialRange.start)
    const b = dayjs(initialRange.end)
    if (!a.isValid() || !b.isValid()) return ''
    return `${a.valueOf()}-${b.valueOf()}`
  }, [initialRange])

  useLayoutEffect(() => {
    if (!open) return
    if (initialRangeKey && initialRange?.start != null && initialRange?.end != null) {
      const s = dayjs(initialRange.start)
      const e = dayjs(initialRange.end)
      if (s.isValid() && e.isValid() && e.isAfter(s)) {
        setStartTime(s)
        setEndTime(e)
        return
      }
    }
    setStartTime(dayjs().add(1, 'hour'))
    setEndTime(dayjs().add(2, 'hour'))
  }, [open, initialRangeKey, initialRange])

  const selectedHost = visitHosts?.find((h) => h.id === solicitedUserId)

  const stopWebcamStream = () => {
    webcamStreamRef.current?.getTracks().forEach((track) => track.stop())
    webcamStreamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }

  useEffect(() => {
    if (!webcamOpen) return undefined
    let cancelled = false
    ;(async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user' },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        webcamStreamRef.current = stream
        const el = videoRef.current
        if (el) {
          el.srcObject = stream
          await el.play().catch(() => undefined)
        }
      } catch {
        if (!cancelled) {
          setError(t('appointments.visitorPhotoWebcamError'))
          setWebcamOpen(false)
        }
      }
    })()
    return () => {
      cancelled = true
      stopWebcamStream()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- t() for error message; only webcamOpen should restart camera
  }, [webcamOpen])

  const createMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      const response = await api.post('/appointments/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      handleClose()
    },
    onError: (err: any) => {
      const errorData = err.response?.data
      if (errorData?.detail) {
        if (Array.isArray(errorData.detail)) {
          const errorMessages = errorData.detail
            .map((e: any) => {
              const field = e.loc?.join('.') || e.loc?.[e.loc.length - 1] || 'field'
              return `${field}: ${e.msg}`
            })
            .join(', ')
          setError(errorMessages)
        } else {
          setError(errorData.detail)
        }
      } else {
        setError(t('appointments.createFailed'))
      }
    },
  })

  const handleClose = () => {
    setTitle('')
    setDescription('')
    setStartTime(dayjs().add(1, 'hour'))
    setEndTime(dayjs().add(2, 'hour'))
    setVisitorName('')
    setVisitorEmail('')
    setVisitorPhone('')
    setVisitorCompany('')
    setVisitorPhotoDataUrl(null)
    setVisitorIdDocumentDataUrl(null)
    if (photoFileInputRef.current) photoFileInputRef.current.value = ''
    if (idDocFileInputRef.current) idDocFileInputRef.current.value = ''
    setPhotoMenuAnchor(null)
    setWebcamOpen(false)
    stopWebcamStream()
    setSolicitedUserId('')
    setLocationMode('on_site')
    setCustomLocation('')
    setError('')
    onClose()
  }

  const estimateDataUrlBytes = (dataUrl: string) => {
    const base64 = dataUrl.split(',')[1]
    if (!base64) return 0
    return Math.ceil((base64.length * 3) / 4)
  }

  const captureFromWebcam = () => {
    const video = videoRef.current
    if (!video || video.videoWidth === 0) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0)
    let quality = 0.92
    let dataUrl = canvas.toDataURL('image/jpeg', quality)
    while (estimateDataUrlBytes(dataUrl) > 5 * 1024 * 1024 && quality > 0.3) {
      quality -= 0.1
      dataUrl = canvas.toDataURL('image/jpeg', quality)
    }
    if (estimateDataUrlBytes(dataUrl) > 5 * 1024 * 1024) {
      setError(t('appointments.visitorPhotoTooLarge'))
      return
    }
    setVisitorPhotoDataUrl(dataUrl)
    setWebcamOpen(false)
    stopWebcamStream()
  }

  const closeWebcamDialog = () => {
    setWebcamOpen(false)
    stopWebcamStream()
  }

  const onVisitorPhotoSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError(t('appointments.visitorPhotoInvalidType'))
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError(t('appointments.visitorPhotoTooLarge'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const r = reader.result
      if (typeof r === 'string') setVisitorPhotoDataUrl(r)
    }
    reader.readAsDataURL(file)
  }

  const onVisitorIdDocumentSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError(t('appointments.visitorPhotoInvalidType'))
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError(t('appointments.visitorPhotoTooLarge'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const r = reader.result
      if (typeof r === 'string') setVisitorIdDocumentDataUrl(r)
    }
    reader.readAsDataURL(file)
  }

  const handleCreate = () => {
    if (!startTime || !endTime) {
      setError(t('appointments.selectTimes'))
      return
    }
    if (endTime.isBefore(startTime)) {
      setError(t('appointments.endBeforeStart'))
      return
    }
    if (!solicitedUserId) {
      setError(t('appointments.solicitedPersonRequired'))
      return
    }
    if (locationMode === 'custom' && !customLocation.trim()) {
      setError(t('appointments.locationCustomRequired'))
      return
    }
    const location =
      locationMode === 'on_site' ? t('appointments.locationModeOnSite') : customLocation.trim()
    createMutation.mutate({
      title,
      description,
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      organizer_id: solicitedUserId,
      location,
      visitor_name: visitorName,
      visitor_email: visitorEmail,
      visitor_phone: visitorPhone,
      visitor_company: visitorCompany,
      ...(visitorPhotoDataUrl ? { visitor_photo_base64: visitorPhotoDataUrl } : {}),
      ...(visitorIdDocumentDataUrl ? { visitor_id_document_base64: visitorIdDocumentDataUrl } : {}),
    })
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{t('appointments.createTitle')}</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}
        {visitHostsError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {t('appointments.visitHostsLoadError')}
          </Alert>
        )}
        <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={i18n.language}>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6}>
              {visitHostsLoading ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minHeight: 56 }}>
                  <CircularProgress size={22} />
                  <Typography variant="body2" color="text.secondary">
                    {t('common.loading')}
                  </Typography>
                </Box>
              ) : visitHosts?.length ? (
                <FormControl fullWidth required>
                  <InputLabel id="solicited-person-label">{t('appointments.solicitedPersonLabel')}</InputLabel>
                  <Select
                    labelId="solicited-person-label"
                    label={t('appointments.solicitedPersonLabel')}
                    value={solicitedUserId}
                    onChange={(e) => setSolicitedUserId(e.target.value as string)}
                  >
                    {visitHosts.map((h) => (
                      <MenuItem key={h.id} value={h.id}>
                        {h.full_name} ({h.username})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                !visitHostsError && (
                  <Alert severity="warning">{t('appointments.noVisitHosts')}</Alert>
                )
              )}
            </Grid>
            <Grid item xs={12} md={6} sx={{ display: 'flex', alignItems: 'center' }}>
              {selectedHost && (
                <Box
                  sx={{
                    pl: { xs: 0, md: 1 },
                    py: 1,
                    px: 2,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    border: 1,
                    borderColor: 'divider',
                    width: '100%',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('appointments.solicitedPersonFunction')}
                  </Typography>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {t(`usersAdmin.roleNames.${selectedHost.role}`, { defaultValue: selectedHost.role })}
                  </Typography>
                </Box>
              )}
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label={t('appointments.titleLabel')}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label={t('appointments.descriptionLabel')}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                multiline
                rows={3}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <DateTimePicker
                label={t('appointments.startTime')}
                value={startTime}
                onChange={(newValue) => {
                  setStartTime(newValue)
                  if (newValue) setEndTime(newValue.add(1, 'hour'))
                  else setEndTime(null)
                }}
                slotProps={{ textField: { fullWidth: true, required: true } }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <DateTimePicker
                label={t('appointments.endTime')}
                value={endTime}
                onChange={(newValue) => setEndTime(newValue)}
                slotProps={{ textField: { fullWidth: true, required: true } }}
                minDateTime={startTime || undefined}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel id="create-apt-location-mode-label">{t('appointments.locationLabel')}</InputLabel>
                <Select
                  labelId="create-apt-location-mode-label"
                  label={t('appointments.locationLabel')}
                  value={locationMode}
                  onChange={(e) => {
                    const v = e.target.value as LocationMode
                    setLocationMode(v)
                    if (v === 'on_site') setCustomLocation('')
                  }}
                >
                  <MenuItem value="on_site">{t('appointments.locationModeOnSite')}</MenuItem>
                  <MenuItem value="custom">{t('appointments.locationModeSpecify')}</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            {locationMode === 'custom' && (
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label={t('appointments.locationCustomLabel')}
                  value={customLocation}
                  onChange={(e) => setCustomLocation(e.target.value)}
                  required
                  placeholder={t('appointments.locationCustomPlaceholder')}
                />
              </Grid>
            )}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={t('appointments.visitorName')}
                value={visitorName}
                onChange={(e) => setVisitorName(e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={t('appointments.visitorEmail')}
                type="email"
                value={visitorEmail}
                onChange={(e) => setVisitorEmail(e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={t('appointments.visitorPhone')}
                value={visitorPhone}
                onChange={(e) => setVisitorPhone(e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={t('appointments.visitorCompany')}
                value={visitorCompany}
                onChange={(e) => setVisitorCompany(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <input
                ref={photoFileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={onVisitorPhotoSelected}
              />
              <Menu
                anchorEl={photoMenuAnchor}
                open={Boolean(photoMenuAnchor)}
                onClose={() => setPhotoMenuAnchor(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                sx={{ zIndex: 1600 }}
              >
                <MenuItem
                  onClick={() => {
                    setPhotoMenuAnchor(null)
                    setWebcamOpen(true)
                  }}
                >
                  {t('appointments.visitorPhotoMenuWebcam')}
                </MenuItem>
                <MenuItem
                  onClick={() => {
                    setPhotoMenuAnchor(null)
                    photoFileInputRef.current?.click()
                  }}
                >
                  {t('appointments.visitorPhotoMenuFile')}
                </MenuItem>
              </Menu>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
                <Button
                  variant="outlined"
                  component="button"
                  type="button"
                  onClick={(e) => setPhotoMenuAnchor(e.currentTarget)}
                >
                  {t('appointments.visitorPhotoButton')}
                </Button>
                {visitorPhotoDataUrl && (
                  <>
                    <Box
                      component="img"
                      src={visitorPhotoDataUrl}
                      alt=""
                      sx={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 1, border: 1, borderColor: 'divider' }}
                    />
                    <Button
                      size="small"
                      onClick={() => {
                        setVisitorPhotoDataUrl(null)
                        if (photoFileInputRef.current) photoFileInputRef.current.value = ''
                      }}
                    >
                      {t('appointments.visitorPhotoClear')}
                    </Button>
                  </>
                )}
                {!visitorPhotoDataUrl && (
                  <Typography variant="caption" color="text.secondary">
                    {t('appointments.visitorPhotoHint')}
                  </Typography>
                )}
              </Box>
            </Grid>
            <Grid item xs={12}>
              <input
                ref={idDocFileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={onVisitorIdDocumentSelected}
              />
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
                <Button
                  variant="outlined"
                  component="button"
                  type="button"
                  onClick={() => idDocFileInputRef.current?.click()}
                >
                  {t('appointments.visitorIdDocumentButton')}
                </Button>
                {visitorIdDocumentDataUrl && (
                  <>
                    <Box
                      component="img"
                      src={visitorIdDocumentDataUrl}
                      alt=""
                      sx={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 1, border: 1, borderColor: 'divider' }}
                    />
                    <Button
                      size="small"
                      onClick={() => {
                        setVisitorIdDocumentDataUrl(null)
                        if (idDocFileInputRef.current) idDocFileInputRef.current.value = ''
                      }}
                    >
                      {t('appointments.visitorIdDocumentClear')}
                    </Button>
                  </>
                )}
                {!visitorIdDocumentDataUrl && (
                  <Typography variant="caption" color="text.secondary">
                    {t('appointments.visitorIdDocumentHint')}
                  </Typography>
                )}
              </Box>
            </Grid>
          </Grid>
        </LocalizationProvider>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>{t('common.cancel')}</Button>
        <Button
          onClick={handleCreate}
          variant="contained"
          disabled={
            createMutation.isPending ||
            visitHostsLoading ||
            !visitHosts?.length ||
            visitHostsError ||
            !solicitedUserId
          }
        >
          {createMutation.isPending ? t('appointments.creating') : t('appointments.create')}
        </Button>
      </DialogActions>

      <Dialog open={webcamOpen} onClose={closeWebcamDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{t('appointments.visitorPhotoWebcamTitle')}</DialogTitle>
        <DialogContent>
          <Box
            sx={{
              width: '100%',
              bgcolor: 'grey.900',
              borderRadius: 1,
              overflow: 'hidden',
              aspectRatio: '4/3',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Box
              component="video"
              ref={videoRef}
              autoPlay
              playsInline
              muted
              sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeWebcamDialog}>{t('common.cancel')}</Button>
          <Button variant="contained" onClick={captureFromWebcam}>
            {t('appointments.visitorPhotoCapture')}
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  )
}
