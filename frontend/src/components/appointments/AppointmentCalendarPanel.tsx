import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Paper,
  Dialog,
  DialogContent,
  DialogActions,
  Button,
  CircularProgress,
  Alert,
  Chip,
  Avatar,
  Tooltip,
  IconButton,
} from '@mui/material'
import {
  ModalSectionHeader,
  ModalSectionBody,
  modalDialogFooterSx,
} from '../common/DetailModalLayout'
import { Calendar, momentLocalizer } from 'react-big-calendar'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import moment from 'moment'
import 'moment/locale/fr'
import dayjs from 'dayjs'
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore'
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter'
import isBetween from 'dayjs/plugin/isBetween'
import weekday from 'dayjs/plugin/weekday'
import weekOfYear from 'dayjs/plugin/weekOfYear'
import weekYear from 'dayjs/plugin/weekYear'
import duration from 'dayjs/plugin/duration'
import minMax from 'dayjs/plugin/minMax'
import { useTranslation } from 'react-i18next'
import { useDateFormat } from '../../hooks/useDateFormat'
import { useAuth } from '../../hooks/useAuth'
import api from '../../services/api'
import VisitorPhotoZoomDialog from './VisitorPhotoZoomDialog'
import { hasPermission } from '../../utils/permissions'
import {
  ZoomIn as ZoomInIcon,
  HowToReg as HowToRegIcon,
  TaskAlt as TaskAltIcon,
  DeleteOutline as DeleteOutlineIcon,
  PersonOff as PersonOffIcon,
  Add as AddIcon,
} from '@mui/icons-material'
import type { SlotInfo, Components } from 'react-big-calendar'
import CreateAppointmentDialog from './CreateAppointmentDialog'
import { buildCalendarCreateHoverComponents } from './CalendarCreateCellWrappers'

/** Aligné sur le pas par défaut du calendrier (créneaux semaine / jour). */
const CALENDAR_SLOT_STEP_MINUTES = 30

dayjs.extend(isSameOrBefore)
dayjs.extend(isSameOrAfter)
dayjs.extend(isBetween)
dayjs.extend(weekday)
dayjs.extend(weekOfYear)
dayjs.extend(weekYear)
dayjs.extend(duration)
dayjs.extend(minMax)

/** Rendez-vous — bleu (aligné sur la charte FPI) */
const COLOR_APPOINTMENT = '#1565c0'
/** Courriers — orange distinct */
const COLOR_MAIL = '#e65100'

export type CalendarEventType = 'appointment' | 'mail'

export type CalendarEvent = {
  id: string
  title: string
  start: Date
  end: Date
  eventType: CalendarEventType
  resource: any
}

function mailDocumentToEvent(doc: any): CalendarEvent {
  const anchor = doc.response_deadline ? new Date(doc.response_deadline) : new Date(doc.created_at)
  let end = dayjs(anchor).add(1, 'hour').toDate()
  if (end <= anchor) {
    end = dayjs(anchor).add(30, 'minute').toDate()
  }
  const label = doc.reference_number
    ? `${doc.reference_number} — ${doc.title || ''}`.trim().slice(0, 100)
    : doc.title || doc.reference_number || '—'
  return {
    id: `mail-${doc.id}`,
    title: label,
    start: anchor,
    end,
    eventType: 'mail',
    resource: { ...doc, eventType: 'mail' as const },
  }
}

export default function AppointmentCalendarPanel() {
  const { t, i18n } = useTranslation()
  const { formatDateTime } = useDateFormat()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const canDeleteApt = hasPermission(user, 'appointments.delete')
  const [viewOpen, setViewOpen] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null)
  const [visitorPhotoUrl, setVisitorPhotoUrl] = useState<string | null>(null)
  const [visitorPhotoZoomOpen, setVisitorPhotoZoomOpen] = useState(false)
  const visitorPhotoBlobRef = useRef<string | null>(null)
  const [visitorIdDocUrl, setVisitorIdDocUrl] = useState<string | null>(null)
  const [visitorIdDocZoomOpen, setVisitorIdDocZoomOpen] = useState(false)
  const visitorIdDocBlobRef = useRef<string | null>(null)
  const [openingMail, setOpeningMail] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createInitialRange, setCreateInitialRange] = useState<{ start: Date; end: Date } | null>(null)
  const canCreateAppointment = hasPermission(user, 'appointments.create')

  useEffect(() => {
    dayjs.locale(i18n.language)
    const lng = (i18n.resolvedLanguage || i18n.language || 'en').toLowerCase()
    moment.locale(lng.startsWith('fr') ? 'fr' : 'en')
  }, [i18n.language, i18n.resolvedLanguage])

  /** react-big-calendar attend Moment via momentLocalizer — Day.js n’expose pas localeData() (erreur vues semaine/jour). */
  const localizer = useMemo(() => {
    const lng = (i18n.resolvedLanguage || i18n.language || 'en').toLowerCase()
    moment.locale(lng.startsWith('fr') ? 'fr' : 'en')
    return momentLocalizer(moment)
  }, [i18n.language, i18n.resolvedLanguage])

  const [appointmentsQuery, mailQuery] = useQueries({
    queries: [
      {
        queryKey: ['appointments'],
        queryFn: async () => {
          const response = await api.get('/appointments/')
          return response.data as any[]
        },
      },
      {
        queryKey: ['mail-documents'],
        queryFn: async () => {
          const response = await api.get('/mail/', { params: { limit: 500 } })
          return response.data as any[]
        },
      },
    ],
  })

  const events: CalendarEvent[] = useMemo(() => {
    const aptEvents: CalendarEvent[] = (appointmentsQuery.data || []).map((apt: any) => ({
      id: String(apt.id),
      title: apt.title,
      start: new Date(apt.start_time),
      end: new Date(apt.end_time),
      eventType: 'appointment' as const,
      resource: { ...apt, eventType: 'appointment' as const },
    }))
    const mailEvents: CalendarEvent[] = (mailQuery.data || []).map(mailDocumentToEvent)
    return [...aptEvents, ...mailEvents]
  }, [appointmentsQuery.data, mailQuery.data])

  const isLoading = appointmentsQuery.isLoading || mailQuery.isLoading
  const queryError = appointmentsQuery.error || mailQuery.error

  const handleSelectEvent = (event: CalendarEvent) => {
    setSelectedEvent(event)
    setViewOpen(true)
  }

  useEffect(() => {
    const revokeCurrent = () => {
      if (visitorPhotoBlobRef.current) {
        URL.revokeObjectURL(visitorPhotoBlobRef.current)
        visitorPhotoBlobRef.current = null
      }
      setVisitorPhotoUrl(null)
    }

    if (!viewOpen || selectedEvent?.eventType !== 'appointment') {
      revokeCurrent()
      return undefined
    }
    const apt = selectedEvent.resource
    if (!apt?.visitor?.visitor_photo_path || !apt?.id) {
      revokeCurrent()
      return undefined
    }
    let alive = true
    revokeCurrent()
    ;(async () => {
      try {
        const res = await api.get(`/appointments/${apt.id}/visitor/photo`, { responseType: 'blob' })
        if (!alive) return
        const url = URL.createObjectURL(res.data)
        if (!alive) {
          URL.revokeObjectURL(url)
          return
        }
        visitorPhotoBlobRef.current = url
        setVisitorPhotoUrl(url)
      } catch {
        if (alive) revokeCurrent()
      }
    })()
    return () => {
      alive = false
      revokeCurrent()
    }
  }, [viewOpen, selectedEvent])

  useEffect(() => {
    const revokeCurrent = () => {
      if (visitorIdDocBlobRef.current) {
        URL.revokeObjectURL(visitorIdDocBlobRef.current)
        visitorIdDocBlobRef.current = null
      }
      setVisitorIdDocUrl(null)
    }

    if (!viewOpen || selectedEvent?.eventType !== 'appointment') {
      revokeCurrent()
      return undefined
    }
    const apt = selectedEvent.resource
    if (!apt?.visitor?.visitor_id_document_path || !apt?.id) {
      revokeCurrent()
      return undefined
    }
    let alive = true
    revokeCurrent()
    ;(async () => {
      try {
        const res = await api.get(`/appointments/${apt.id}/visitor/id-document`, { responseType: 'blob' })
        if (!alive) return
        const url = URL.createObjectURL(res.data)
        if (!alive) {
          URL.revokeObjectURL(url)
          return
        }
        visitorIdDocBlobRef.current = url
        setVisitorIdDocUrl(url)
      } catch {
        if (alive) revokeCurrent()
      }
    })()
    return () => {
      alive = false
      revokeCurrent()
    }
  }, [viewOpen, selectedEvent])

  useEffect(() => {
    if (!viewOpen) {
      setVisitorPhotoZoomOpen(false)
      setVisitorIdDocZoomOpen(false)
    }
  }, [viewOpen])

  const confirmMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/confirm`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      setSelectedEvent((prev) =>
        prev?.eventType === 'appointment' && prev.resource && String(prev.resource.id) === String(data.id)
          ? { ...prev, resource: { ...prev.resource, ...data } }
          : prev
      )
    },
  })

  const completeMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/complete`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      setViewOpen(false)
    },
  })

  const noShowMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/no-show`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      setSelectedEvent((prev) =>
        prev?.eventType === 'appointment' && prev.resource && String(prev.resource.id) === String(data.id)
          ? { ...prev, resource: { ...prev.resource, ...data } }
          : prev
      )
      setViewOpen(false)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/cancel`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      setViewOpen(false)
    },
  })

  const openMailFile = useCallback(async () => {
    if (selectedEvent?.eventType !== 'mail' || !selectedEvent.resource?.id) return
    setOpeningMail(true)
    try {
      const res = await api.get(`/mail/${selectedEvent.resource.id}/file`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      window.open(url, '_blank', 'noopener,noreferrer')
      window.setTimeout(() => URL.revokeObjectURL(url), 120_000)
    } catch {
      /* ignore */
    } finally {
      setOpeningMail(false)
    }
  }, [selectedEvent])

  const eventPropGetter = (event: CalendarEvent) => {
    const isMail = event.eventType === 'mail'
    const bg = isMail ? COLOR_MAIL : COLOR_APPOINTMENT
    return {
      style: {
        backgroundColor: bg,
        color: 'white',
        borderRadius: '4px',
        border: 'none',
        fontSize: '0.8rem',
      },
    }
  }

  const appointmentStatusLabel = (status?: string) => {
    switch (status) {
      case 'pending':
        return t('appointments.statusPending')
      case 'confirmed':
        return t('appointments.statusConfirmed')
      case 'cancelled':
        return t('appointments.statusCancelled')
      case 'completed':
        return t('appointments.statusCompleted')
      case 'no_show':
        return t('appointments.statusNoShow')
      default:
        return status || '—'
    }
  }

  const isVisitHostCalendar = (apt: { organizer_id?: string }) =>
    user?.id != null &&
    apt?.organizer_id != null &&
    String(user.id) === String(apt.organizer_id)

  const canConfirmAptCalendar = (apt: { organizer_id?: string }) =>
    isVisitHostCalendar(apt) || user?.role === 'master'

  const canCompleteAptCalendar = (apt: { organizer_id?: string }) =>
    isVisitHostCalendar(apt) || user?.role === 'master' || canDeleteApt

  const canCancelAptCalendar = (apt: { organizer_id?: string }) =>
    isVisitHostCalendar(apt) || canDeleteApt

  const handleCloseCreateAppointment = () => {
    setCreateOpen(false)
    setCreateInitialRange(null)
  }

  const handleOpenCreateAppointment = () => {
    setCreateInitialRange(null)
    setCreateOpen(true)
  }

  const handleSelectCalendarSlot = (slotInfo: SlotInfo) => {
    if (!canCreateAppointment) return
    setCreateInitialRange({ start: slotInfo.start, end: slotInfo.end })
    setCreateOpen(true)
  }

  const handleOpenCreateWithRange = useCallback((range: { start: Date; end: Date }) => {
    setCreateInitialRange(range)
    setCreateOpen(true)
  }, [])

  const calendarHoverComponents = useMemo(
    () =>
      buildCalendarCreateHoverComponents({
        enabled: canCreateAppointment,
        onOpenCreate: handleOpenCreateWithRange,
        label: t('reception.calendarCellCreateButton'),
        slotStepMinutes: CALENDAR_SLOT_STEP_MINUTES,
      }),
    [canCreateAppointment, handleOpenCreateWithRange, t]
  )

  const mailStatusLabel = (status?: string) => {
    switch (status) {
      case 'received':
        return t('mail.statusReceived')
      case 'in_review':
      case 'in_treatment':
        return t('mail.statusInTreatment')
      case 'indexed':
        return t('mail.statusIndexed')
      case 'assigned':
        return t('mail.statusAssigned')
      case 'pending_validation':
        return t('mail.statusPendingValidation')
      case 'pending_director':
        return t('mail.statusPendingDirector')
      case 'on_hold':
        return t('mail.statusOnHold')
      case 'approved':
        return t('mail.statusApproved')
      case 'closed':
        return t('mail.statusClosed')
      case 'rejected':
        return t('mail.statusRejected')
      case 'archived':
        return t('mail.statusArchived')
      default:
        return status || '—'
    }
  }

  return (
    <>
      <Paper sx={{ p: 2, minHeight: '600px' }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 2,
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1,
          }}
        >
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t('reception.calendarLegend')}
            </Typography>
            <Chip
              size="small"
              label={t('reception.legendAppointments')}
              sx={{ bgcolor: COLOR_APPOINTMENT, color: 'white', fontWeight: 600 }}
            />
            <Chip
              size="small"
              label={t('reception.legendMail')}
              sx={{ bgcolor: COLOR_MAIL, color: 'white', fontWeight: 600 }}
            />
          </Box>
          {canCreateAppointment && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenCreateAppointment}>
              {t('reception.newAppointmentButton')}
            </Button>
          )}
        </Box>
        {canCreateAppointment && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            {t('reception.calendarHoverCreateHint')}
          </Typography>
        )}

        {isLoading ? (
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={400} flexDirection="column" gap={2}>
            <CircularProgress />
            <Typography color="text.secondary">{t('appointments.loadingAppointments')}</Typography>
          </Box>
        ) : queryError ? (
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={400} flexDirection="column" gap={2}>
            <Typography color="error" variant="h6">
              {t('appointments.loadFailed')}
            </Typography>
          </Box>
        ) : (
          <>
            <Box
              sx={{
                height: '100%',
                width: '100%',
                '& .rbc-row-bg': { display: 'flex' },
                '& .rbc-day-bg': { flex: 1 },
              }}
            >
              <Calendar
                localizer={localizer}
                events={events}
                startAccessor="start"
                endAccessor="end"
                style={{ height: '100%', minHeight: '550px' }}
                onSelectEvent={(ev) => handleSelectEvent(ev as CalendarEvent)}
                selectable={canCreateAppointment ? 'ignoreEvents' : false}
                onSelectSlot={handleSelectCalendarSlot}
                step={CALENDAR_SLOT_STEP_MINUTES}
                defaultView="month"
                views={['month', 'week', 'day', 'agenda']}
                popup
                eventPropGetter={(ev) => eventPropGetter(ev as CalendarEvent)}
                components={calendarHoverComponents as Components<CalendarEvent>}
              />
            </Box>
            {events.length === 0 && (
              <Box sx={{ mt: 2, textAlign: 'center', py: 2 }}>
                <Typography variant="body1" color="text.secondary" gutterBottom>
                  {t('reception.calendarEmpty')}
                </Typography>
              </Box>
            )}
          </>
        )}
      </Paper>

      {queryError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {queryError instanceof Error ? queryError.message : t('appointments.loadFailed')}
        </Alert>
      )}

      <Dialog
        open={viewOpen}
        onClose={() => setViewOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { overflow: 'hidden' } }}
      >
        {selectedEvent?.eventType === 'appointment' && selectedEvent.resource && (
          <ModalSectionHeader>
            <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('appointments.appointmentDetails')}
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              {selectedEvent.resource.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {formatDateTime(selectedEvent.resource.start_time)} — {formatDateTime(selectedEvent.resource.end_time)}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
              <Chip label={appointmentStatusLabel(selectedEvent.resource.status)} size="small" variant="outlined" />
              {selectedEvent.resource.visitor?.checked_in !== undefined && (
                <Chip
                  label={
                    selectedEvent.resource.visitor?.checked_in
                      ? t('reception.checkedIn')
                      : t('reception.pendingCheckIn')
                  }
                  color={selectedEvent.resource.visitor?.checked_in ? 'success' : 'default'}
                  size="small"
                />
              )}
            </Box>
          </ModalSectionHeader>
        )}
        {selectedEvent?.eventType === 'mail' && selectedEvent.resource && (
          <ModalSectionHeader>
            <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('reception.mailDetails')}
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              {selectedEvent.resource.title}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
              <Chip label={selectedEvent.resource.reference_number || '—'} size="small" variant="outlined" />
              <Chip label={mailStatusLabel(selectedEvent.resource.status)} size="small" />
              {selectedEvent.resource.is_overdue && (
                <Chip label={t('dashboard.mailOverdue')} color="error" size="small" />
              )}
            </Box>
          </ModalSectionHeader>
        )}
        <DialogContent sx={{ p: 0 }}>
          {selectedEvent?.eventType === 'appointment' && selectedEvent.resource && (
            <ModalSectionBody>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <Box sx={{ flexShrink: 0, display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                <Tooltip
                  title={visitorPhotoUrl ? t('appointments.visitorPhotoZoomEnlarge') : ''}
                  disableHoverListener={!visitorPhotoUrl}
                >
                  <Box
                    sx={{
                      position: 'relative',
                      width: 96,
                      height: 96,
                      cursor: visitorPhotoUrl ? 'zoom-in' : 'default',
                    }}
                    onClick={() => visitorPhotoUrl && setVisitorPhotoZoomOpen(true)}
                    onKeyDown={(e) => {
                      if ((e.key === 'Enter' || e.key === ' ') && visitorPhotoUrl) {
                        e.preventDefault()
                        setVisitorPhotoZoomOpen(true)
                      }
                    }}
                    role={visitorPhotoUrl ? 'button' : undefined}
                    tabIndex={visitorPhotoUrl ? 0 : undefined}
                  >
                    <Avatar
                      src={visitorPhotoUrl || undefined}
                      alt={selectedEvent.resource.visitor_name || ''}
                      imgProps={{
                        onError: () => {
                          if (visitorPhotoBlobRef.current) {
                            URL.revokeObjectURL(visitorPhotoBlobRef.current)
                            visitorPhotoBlobRef.current = null
                          }
                          setVisitorPhotoUrl(null)
                        },
                      }}
                      sx={{ width: 96, height: 96, bgcolor: 'primary.main', fontSize: '2rem' }}
                    >
                      {(selectedEvent.resource.visitor_name || selectedEvent.resource.title || '?')
                        .toString()
                        .trim()
                        .charAt(0)
                        .toUpperCase()}
                    </Avatar>
                    {visitorPhotoUrl && (
                      <IconButton
                        size="small"
                        aria-label={t('appointments.visitorPhotoZoomEnlarge')}
                        sx={{
                          position: 'absolute',
                          bottom: -6,
                          right: -6,
                          bgcolor: 'background.paper',
                          boxShadow: 2,
                          '&:hover': { bgcolor: 'background.paper' },
                        }}
                        onClick={(e) => {
                          e.stopPropagation()
                          setVisitorPhotoZoomOpen(true)
                        }}
                      >
                        <ZoomInIcon fontSize="small" color="primary" />
                      </IconButton>
                    )}
                  </Box>
                </Tooltip>
                {selectedEvent.resource.visitor?.visitor_id_document_path ? (
                  <Box sx={{ textAlign: 'center', maxWidth: 120 }}>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      display="block"
                      sx={{ mb: 0.5, fontWeight: 600 }}
                    >
                      {t('appointments.visitorIdDocumentLabel')}
                    </Typography>
                    <Tooltip
                      title={visitorIdDocUrl ? t('appointments.visitorIdDocumentZoomEnlarge') : ''}
                      disableHoverListener={!visitorIdDocUrl}
                    >
                      <Box
                        sx={{
                          position: 'relative',
                          width: 96,
                          height: 96,
                          borderRadius: 1,
                          overflow: 'hidden',
                          border: 1,
                          borderColor: 'divider',
                          cursor: visitorIdDocUrl ? 'zoom-in' : 'default',
                          bgcolor: 'action.hover',
                        }}
                        onClick={() => visitorIdDocUrl && setVisitorIdDocZoomOpen(true)}
                        onKeyDown={(e) => {
                          if ((e.key === 'Enter' || e.key === ' ') && visitorIdDocUrl) {
                            e.preventDefault()
                            setVisitorIdDocZoomOpen(true)
                          }
                        }}
                        role={visitorIdDocUrl ? 'button' : undefined}
                        tabIndex={visitorIdDocUrl ? 0 : undefined}
                      >
                        {visitorIdDocUrl ? (
                          <Box
                            component="img"
                            src={visitorIdDocUrl}
                            alt=""
                            sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        ) : null}
                      </Box>
                    </Tooltip>
                  </Box>
                ) : null}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                {selectedEvent.resource.description && (
                  <Typography variant="body2" color="text.secondary" paragraph>
                    {selectedEvent.resource.description}
                  </Typography>
                )}
                {selectedEvent.resource.visitor_name && (
                  <>
                    <Typography variant="body2" paragraph>
                      <strong>{t('appointments.visitor')}:</strong> {selectedEvent.resource.visitor_name}
                    </Typography>
                    {selectedEvent.resource.visitor_email && (
                      <Typography variant="body2" paragraph>
                        <strong>{t('appointments.email')}:</strong> {selectedEvent.resource.visitor_email}
                      </Typography>
                    )}
                    {selectedEvent.resource.visitor_company && (
                      <Typography variant="body2" paragraph>
                        <strong>{t('appointments.company')}:</strong> {selectedEvent.resource.visitor_company}
                      </Typography>
                    )}
                  </>
                )}
              </Box>
            </Box>
            </ModalSectionBody>
          )}
          {selectedEvent?.eventType === 'mail' && selectedEvent.resource && (
            <ModalSectionBody>
            <Box>
              <Typography variant="body2" paragraph>
                <strong>{t('mail.priority')}:</strong> {selectedEvent.resource.priority || '—'}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>{t('mail.created')}:</strong> {formatDateTime(selectedEvent.resource.created_at)}
              </Typography>
              {selectedEvent.resource.response_deadline && (
                <Typography variant="body2" paragraph>
                  <strong>{t('reception.mailDeadline')}:</strong>{' '}
                  {formatDateTime(selectedEvent.resource.response_deadline)}
                </Typography>
              )}
              {selectedEvent.resource.description && (
                <Typography variant="body2" color="text.secondary" paragraph>
                  {selectedEvent.resource.description}
                </Typography>
              )}
              <Button
                sx={{ mt: 2 }}
                variant="outlined"
                onClick={() => void openMailFile()}
                disabled={openingMail}
              >
                {openingMail ? t('common.loading') : t('reception.openMailDocument')}
              </Button>
            </Box>
            </ModalSectionBody>
          )}
        </DialogContent>
        <DialogActions sx={modalDialogFooterSx}>
          <Button onClick={() => setViewOpen(false)}>{t('common.close')}</Button>
          {selectedEvent?.eventType === 'appointment' && selectedEvent.resource && (
            <>
              {selectedEvent.resource.status === 'pending' &&
                canConfirmAptCalendar(selectedEvent.resource) && (
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<HowToRegIcon />}
                    onClick={() => confirmMutation.mutate(selectedEvent.resource.id)}
                    disabled={confirmMutation.isPending}
                  >
                    {confirmMutation.isPending ? t('common.loading') : t('appointments.confirmAppointment')}
                  </Button>
                )}
              {selectedEvent.resource.status === 'confirmed' &&
                canCompleteAptCalendar(selectedEvent.resource) && (
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<TaskAltIcon />}
                    onClick={() => completeMutation.mutate(selectedEvent.resource.id)}
                    disabled={completeMutation.isPending || noShowMutation.isPending}
                  >
                    {completeMutation.isPending ? t('common.loading') : t('appointments.completeAppointment')}
                  </Button>
                )}
              {selectedEvent.resource.status === 'confirmed' &&
                canCompleteAptCalendar(selectedEvent.resource) && (
                  <Button
                    variant="outlined"
                    color="warning"
                    startIcon={<PersonOffIcon />}
                    onClick={() => noShowMutation.mutate(selectedEvent.resource.id)}
                    disabled={completeMutation.isPending || noShowMutation.isPending}
                  >
                    {noShowMutation.isPending ? t('common.loading') : t('appointments.noShowButton')}
                  </Button>
                )}
              {selectedEvent.resource.status !== 'cancelled' &&
                selectedEvent.resource.status !== 'completed' &&
                selectedEvent.resource.status !== 'no_show' &&
                canCancelAptCalendar(selectedEvent.resource) && (
                  <Button
                    color="error"
                    startIcon={<DeleteOutlineIcon />}
                    onClick={() => {
                      if (window.confirm(t('appointments.confirmCancelBody'))) {
                        cancelMutation.mutate(selectedEvent.resource.id)
                      }
                    }}
                    disabled={cancelMutation.isPending}
                  >
                    {t('appointments.cancelAppointment')}
                  </Button>
                )}
            </>
          )}
        </DialogActions>
      </Dialog>

      <VisitorPhotoZoomDialog
        open={visitorPhotoZoomOpen}
        onClose={() => setVisitorPhotoZoomOpen(false)}
        imageUrl={visitorPhotoUrl}
        visitorName={
          selectedEvent?.eventType === 'appointment'
            ? selectedEvent.resource?.visitor_name
            : undefined
        }
      />
      <VisitorPhotoZoomDialog
        open={visitorIdDocZoomOpen}
        onClose={() => setVisitorIdDocZoomOpen(false)}
        imageUrl={visitorIdDocUrl}
        visitorName={
          selectedEvent?.eventType === 'appointment'
            ? selectedEvent.resource?.visitor_name
            : undefined
        }
        title={t('appointments.visitorIdDocumentZoomTitle')}
        hint={t('appointments.visitorIdDocumentZoomHint')}
      />

      <CreateAppointmentDialog
        key={
          !createOpen
            ? 'create-apt-closed'
            : createInitialRange
              ? `create-apt-${createInitialRange.start.getTime()}-${createInitialRange.end.getTime()}`
              : 'create-apt-empty'
        }
        open={createOpen}
        onClose={handleCloseCreateAppointment}
        defaultHostUserId={user?.id}
        initialRange={createInitialRange}
      />
    </>
  )
}
