import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TableSortLabel,
  TextField,
  Avatar,
  Tooltip,
  IconButton,
  Snackbar,
  FormControlLabel,
  Checkbox,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  Grid,
} from '@mui/material'
import { useTheme, alpha } from '@mui/material/styles'
import {
  Add as AddIcon,
  CheckCircle as CheckIcon,
  Visibility as ViewIcon,
  DeleteOutline as DeleteOutlineIcon,
  EventBusy as EventBusyIcon,
  ZoomIn as ZoomInIcon,
  HowToReg as HowToRegIcon,
  TaskAlt as TaskAltIcon,
  PersonOff as PersonOffIcon,
  QrCodeScanner as QrCodeScannerIcon,
  Inventory2 as Inventory2Icon,
  DeleteForever as DeleteForeverIcon,
  Search as SearchIcon,
  FilterAltOff as FilterAltOffIcon,
} from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import { useDateFormat } from '../hooks/useDateFormat'
import { useAuth } from '../hooks/useAuth'
import { useTableSort } from '../hooks/useTableSort'
import { tableContainerScrollSx } from '../theme/tableScroll'
import { isSameLocalDay } from '../utils/dateCompare'
import api from '../services/api'
import CreateAppointmentDialog from '../components/appointments/CreateAppointmentDialog'
import VisitorPhotoZoomDialog from '../components/appointments/VisitorPhotoZoomDialog'
import { hasPermission } from '../utils/permissions'
import { isAdminUser, isMasterOrDirector } from '../utils/roles'
import { Html5Qrcode } from 'html5-qrcode'
import {
  computeCheckInPunctualityFromTimes,
  punctualityToastMessage,
  type CheckInPunctualityApiPayload,
} from '../utils/checkInPunctuality'
import {
  axiosErrorDetail,
  translateKnownAppointmentApiDetail,
} from '../utils/translateKnownApiDetail'
import {
  ModalSectionHeader,
  ModalSectionBody,
  modalDialogFooterSx,
} from '../components/common/DetailModalLayout'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

/** ID du conteneur pour html5-qrcode (scan QR cross-navigateur, pas seulement Chrome). */
const APPOINTMENTS_QR_READER_ID = 'appointments-qr-reader'

type AptRow = {
  id: string
  organizer_id?: string
  title?: string
  description?: string
  start_time: string
  end_time: string
  visitor_name?: string
  visitor_email?: string
  visitor_phone?: string
  visitor_company?: string
  status?: string
  organizer?: { full_name?: string; role?: string }
  visitor?: {
    checked_in?: boolean
    checked_in_at?: string | null
    visitor_photo_path?: string | null
    visitor_id_document_path?: string | null
  }
  has_pending_deletion_request?: boolean
  archived_at?: string | null
  booking_source?: string
  internal_notes?: string | null
  reception_validated_at?: string | null
  visitor_booking_email_sent_at?: string | null
  highlight_destined?: boolean
}

type SortKey = 'start_time' | 'visitor_name' | 'visitor_company' | 'organizer' | 'status'

/** Aligné sur le backend : vue liste complète du service (pas analyst / admin / invité). */
const APPOINTMENT_BROAD_LIST_ROLES = new Set(['master', 'director', 'receptionist', 'secretary'])

const APPOINTMENT_STATUS_FILTER_VALUES = [
  '',
  'pending',
  'slot_proposed',
  'pending_authorization',
  'preparation',
  'confirmed',
  'cancelled',
  'completed',
  'no_show',
] as const

function localYmdToStartIso(ymd: string): string | undefined {
  if (!ymd || !/^\d{4}-\d{2}-\d{2}$/.test(ymd)) return undefined
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d, 0, 0, 0, 0).toISOString()
}

function localYmdToEndIso(ymd: string): string | undefined {
  if (!ymd || !/^\d{4}-\d{2}-\d{2}$/.test(ymd)) return undefined
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d, 23, 59, 59, 999).toISOString()
}

type VisitHostFilterOption = { id: string; full_name: string; username: string }

export default function Appointments() {
  const { t } = useTranslation()
  const { formatDateTime, formatTime } = useDateFormat()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [viewOpen, setViewOpen] = useState(false)
  const [selectedAppointment, setSelectedAppointment] = useState<AptRow | null>(null)
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false)
  const [requestCancelOpen, setRequestCancelOpen] = useState(false)
  const [requestCancelReason, setRequestCancelReason] = useState('')
  const [actionMessage, setActionMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null)
  const [visitorPhotoUrl, setVisitorPhotoUrl] = useState<string | null>(null)
  const [visitorPhotoLoading, setVisitorPhotoLoading] = useState(false)
  const [visitorPhotoZoomOpen, setVisitorPhotoZoomOpen] = useState(false)
  const [visitorIdDocUrl, setVisitorIdDocUrl] = useState<string | null>(null)
  const [visitorIdDocLoading, setVisitorIdDocLoading] = useState(false)
  const [visitorIdDocZoomOpen, setVisitorIdDocZoomOpen] = useState(false)
  const visitorIdDocBlobRef = useRef<string | null>(null)
  const [qrPayload, setQrPayload] = useState('')
  const [qrScanError, setQrScanError] = useState('')
  const [isQrScanning, setIsQrScanning] = useState(false)
  const visitorPhotoBlobRef = useRef<string | null>(null)
  const html5QrCodeRef = useRef<Html5Qrcode | null>(null)
  /** Évite les doubles appels si la lib déclenche plusieurs fois le même décodage. */
  const qrDecodeLockRef = useRef(false)
  const { sortBy, sortDir, toggleSort, sortRows } = useTableSort<SortKey>('start_time', 'desc')
  const theme = useTheme()
  const [checkInToast, setCheckInToast] = useState<{
    open: boolean
    message: string
    severity: 'success' | 'info' | 'error'
  }>({ open: false, message: '', severity: 'success' })
  const [internalNotesDraft, setInternalNotesDraft] = useState('')
  const [finalizeForceResend, setFinalizeForceResend] = useState(false)

  const showCheckInPunctualityToast = (data: CheckInPunctualityApiPayload) => {
    const message = punctualityToastMessage(t, data)
    const severity =
      data.punctuality_status === 'late'
        ? 'error'
        : data.punctuality_status === 'early'
          ? 'info'
          : 'success'
    setCheckInToast({ open: true, message, severity })
  }

  const checkInRowSx = (apt: AptRow) => {
    if (!apt.visitor?.checked_in || !apt.visitor?.checked_in_at) return undefined
    const { status } = computeCheckInPunctualityFromTimes(apt.start_time, apt.visitor.checked_in_at)
    const bg =
      status === 'early'
        ? alpha(theme.palette.info.main, 0.14)
        : status === 'on_time'
          ? alpha(theme.palette.success.main, 0.14)
          : alpha(theme.palette.error.main, 0.14)
    return { bgcolor: bg }
  }

  const appointmentTableRowSx = (apt: AptRow) => (tt: typeof theme) => {
    const punctual = checkInRowSx(apt)
    if (!apt.highlight_destined) {
      return punctual ?? {}
    }
    return {
      ...(punctual ?? {}),
      boxShadow: `inset 4px 0 0 ${tt.palette.warning.main}`,
      ...(!punctual
        ? {
            bgcolor: alpha(tt.palette.warning.main, tt.palette.mode === 'dark' ? 0.12 : 0.1),
          }
        : {}),
    }
  }

  const canUpdateApt = hasPermission(user, 'appointments.update')

  const canCreate = hasPermission(user, 'appointments.create')
  const canCheckIn = hasPermission(user, 'reception.checkin')
  const canDeleteApt = hasPermission(user, 'appointments.delete')
  const canRequestCancel = hasPermission(user, 'appointments.request_delete')
  const canBulkOps = isAdminUser(user?.role) && canDeleteApt
  const canExecutivePurge = isMasterOrDirector(user?.role) && canDeleteApt
  const showSelectionColumn = canBulkOps || canExecutivePurge
  const [selectedAptIds, setSelectedAptIds] = useState<string[]>([])
  const [includeArchived, setIncludeArchived] = useState(false)

  const aptBroadAccess =
    user?.role != null && APPOINTMENT_BROAD_LIST_ROLES.has(String(user.role).toLowerCase())

  const [filterSearchInput, setFilterSearchInput] = useState('')
  const [filterSearchDebounced, setFilterSearchDebounced] = useState('')
  useEffect(() => {
    const t = window.setTimeout(() => setFilterSearchDebounced(filterSearchInput.trim()), 400)
    return () => window.clearTimeout(t)
  }, [filterSearchInput])

  const [filterStatus, setFilterStatus] = useState<string>('')
  const [filterOrganizerId, setFilterOrganizerId] = useState<string>('')
  const [filterDateFrom, setFilterDateFrom] = useState<string>('')
  const [filterDateTo, setFilterDateTo] = useState<string>('')
  const [filterBookingSource, setFilterBookingSource] = useState<string>('')
  const [filterCheckedIn, setFilterCheckedIn] = useState<string>('')
  const [filterReceptionValidated, setFilterReceptionValidated] = useState<string>('')
  const [filterPendingCancellation, setFilterPendingCancellation] = useState(false)

  const { data: visitHostFilterOptions = [] } = useQuery({
    queryKey: ['appointments-filter-hosts'],
    enabled: aptBroadAccess,
    queryFn: async () => {
      const { data } = await api.get<VisitHostFilterOption[]>('/users/visit-host-candidates')
      return data || []
    },
  })

  const listQueryParams = useMemo(() => {
    const params: Record<string, string | boolean | number> = { limit: 800 }
    if (includeArchived) params.include_archived = true
    if (filterSearchDebounced) params.search = filterSearchDebounced
    if (filterStatus) params.status = filterStatus
    if (aptBroadAccess && filterOrganizerId) params.organizer_id = filterOrganizerId
    const sd = localYmdToStartIso(filterDateFrom)
    const ed = localYmdToEndIso(filterDateTo)
    if (sd) params.start_date = sd
    if (ed) params.end_date = ed
    if (filterBookingSource === 'internal' || filterBookingSource === 'public') {
      params.booking_source = filterBookingSource
    }
    if (filterCheckedIn === 'yes') params.checked_in = true
    if (filterCheckedIn === 'no') params.checked_in = false
    if (filterReceptionValidated === 'yes') params.reception_validated = true
    if (filterReceptionValidated === 'no') params.reception_validated = false
    if (filterPendingCancellation) params.pending_cancellation_only = true
    return params
  }, [
    includeArchived,
    filterSearchDebounced,
    filterStatus,
    filterOrganizerId,
    aptBroadAccess,
    filterDateFrom,
    filterDateTo,
    filterBookingSource,
    filterCheckedIn,
    filterReceptionValidated,
    filterPendingCancellation,
  ])

  const { data: appointments, isLoading, error } = useQuery({
    queryKey: ['appointments-list', listQueryParams],
    queryFn: async () => {
      const response = await api.get('/appointments/', { params: listQueryParams })
      return (response.data || []) as AptRow[]
    },
  })

  const resetListFilters = useCallback(() => {
    setFilterSearchInput('')
    setFilterSearchDebounced('')
    setFilterStatus('')
    setFilterOrganizerId('')
    setFilterDateFrom('')
    setFilterDateTo('')
    setFilterBookingSource('')
    setFilterCheckedIn('')
    setFilterReceptionValidated('')
    setFilterPendingCancellation(false)
  }, [])

  const checkInMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/check-in`)
      return response.data as CheckInPunctualityApiPayload
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      showCheckInPunctualityToast(data)
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      const translated = translateKnownAppointmentApiDetail(t, detail)
      const fallback =
        typeof detail === 'string'
          ? detail
          : err instanceof Error
            ? err.message
            : ''
      setActionMessage({
        type: 'error',
        text: (translated ?? fallback) || t('appointments.checkInFailed'),
      })
    },
  })

  const checkInByQrMutation = useMutation({
    mutationFn: async (raw: string) => {
      const response = await api.post('/appointments/check-in-by-qr', { raw })
      return response.data as CheckInPunctualityApiPayload
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setQrPayload('')
      showCheckInPunctualityToast(data)
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      const translated = translateKnownAppointmentApiDetail(t, detail)
      const fallback =
        typeof detail === 'string'
          ? detail
          : err instanceof Error
            ? err.message
            : ''
      setActionMessage({
        type: 'error',
        text: (translated ?? fallback) || t('appointments.qrCheckInFailed'),
      })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/confirm`)
      return response.data as AptRow
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setSelectedAppointment(data)
      setActionMessage({ type: 'success', text: t('appointments.confirmSuccess') })
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.confirmFailed'),
      })
    },
  })

  const completeMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/complete`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setViewOpen(false)
      setSelectedAppointment(null)
      setActionMessage({ type: 'success', text: t('appointments.completeSuccess') })
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.completeFailed'),
      })
    },
  })

  const noShowMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/no-show`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setViewOpen(false)
      setSelectedAppointment(null)
      setActionMessage({ type: 'success', text: t('appointments.noShowSuccess') })
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.noShowFailed'),
      })
    },
  })

  const bulkCancelAptMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await api.post<{ deleted_count: number }>('/appointments/bulk-delete', { ids })
      return data
    },
    onSuccess: (data) => {
      setSelectedAptIds([])
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      const n = data?.deleted_count ?? 0
      setActionMessage({
        type: 'success',
        text: t('appointments.bulkCancelSuccess', { count: n }),
      })
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      setActionMessage({
        type: 'error',
        text:
          (typeof detail === 'string' ? detail : '') ||
          t('appointments.bulkCancelFailed'),
      })
    },
  })

  const bulkArchiveAptMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await api.post<{ archived_count: number }>('/appointments/bulk-archive', { ids })
      return data
    },
    onSuccess: (data) => {
      setSelectedAptIds([])
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      const n = data?.archived_count ?? 0
      setActionMessage({
        type: 'success',
        text: t('appointments.bulkArchiveSuccess', { count: n }),
      })
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      setActionMessage({
        type: 'error',
        text:
          (typeof detail === 'string' ? detail : '') ||
          t('appointments.bulkArchiveFailed'),
      })
    },
  })

  const archiveSingleMutation = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<AptRow>(`/appointments/${id}/archive`)
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      setActionMessage({ type: 'success', text: t('appointments.archiveSuccess') })
      if (selectedAppointment?.id === data.id) {
        setSelectedAppointment(data as AptRow)
      }
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      setActionMessage({
        type: 'error',
        text: (typeof detail === 'string' ? detail : '') || t('appointments.archiveFailed'),
      })
    },
  })

  const bulkPermanentAptMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await api.post<{ deleted_count: number }>('/appointments/bulk-permanent-delete', {
        ids,
      })
      return data
    },
    onSuccess: (data) => {
      setSelectedAptIds([])
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      const n = data?.deleted_count ?? 0
      setActionMessage({
        type: 'success',
        text: t('appointments.bulkPermanentSuccess', { count: n }),
      })
      setViewOpen(false)
      setSelectedAppointment(null)
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      setActionMessage({
        type: 'error',
        text:
          (typeof detail === 'string' ? detail : '') ||
          t('appointments.bulkPermanentFailed'),
      })
    },
  })

  const permanentSingleMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/appointments/${id}/permanent`)
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      setActionMessage({ type: 'success', text: t('appointments.permanentDeleteSuccess') })
      if (selectedAppointment?.id === id) {
        setViewOpen(false)
        setSelectedAppointment(null)
      }
    },
    onError: (err: unknown) => {
      const detail = axiosErrorDetail(err)
      setActionMessage({
        type: 'error',
        text: (typeof detail === 'string' ? detail : '') || t('appointments.permanentDeleteFailed'),
      })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const response = await api.post(`/appointments/${appointmentId}/cancel`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpi'] })
      setCancelConfirmOpen(false)
      setViewOpen(false)
      setSelectedAppointment(null)
      setActionMessage({ type: 'success', text: t('appointments.cancelledSuccess') })
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.cancelFailed'),
      })
    },
  })

  const saveInternalNotesMutation = useMutation({
    mutationFn: async ({ id, internal_notes }: { id: string; internal_notes: string }) => {
      await api.put(`/appointments/${id}`, { internal_notes })
    },
    onSuccess: (_, v) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setActionMessage({ type: 'success', text: t('appointments.internalNotesSaved') })
      setSelectedAppointment((prev) =>
        prev && prev.id === v.id ? { ...prev, internal_notes: v.internal_notes } : prev
      )
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.internalNotesFailed'),
      })
    },
  })

  const finalizeReceptionMutation = useMutation({
    mutationFn: async ({
      id,
      internal_notes,
      force_resend_visitor_email,
    }: {
      id: string
      internal_notes: string
      force_resend_visitor_email: boolean
    }) => {
      const { data } = await api.post(`/appointments/${id}/reception-finalize`, {
        internal_notes: internal_notes || null,
        send_visitor_email: true,
        force_resend_visitor_email: force_resend_visitor_email,
      })
      return data
    },
    onSuccess: (data: AptRow) => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setActionMessage({ type: 'success', text: t('appointments.finalizeSuccess') })
      const id = data?.id
      if (id) {
        setSelectedAppointment((prev) => (prev && prev.id === id ? { ...prev, ...data } : prev))
      }
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.finalizeFailed'),
      })
    },
  })

  const requestCancelMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
      const response = await api.post(`/appointments/${id}/deletion-request`, {
        reason: reason.trim() || null,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setRequestCancelOpen(false)
      setRequestCancelReason('')
      setViewOpen(false)
      setSelectedAppointment(null)
      setActionMessage({ type: 'success', text: t('appointments.cancellationRequestSent') })
    },
    onError: (err: any) => {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || t('appointments.cancellationRequestFailed'),
      })
    },
  })

  useEffect(() => {
    if (selectedAppointment) {
      setInternalNotesDraft(selectedAppointment.internal_notes ?? '')
      setFinalizeForceResend(false)
    }
  }, [selectedAppointment?.id, selectedAppointment?.internal_notes, viewOpen])

  const sorted = appointments
    ? sortRows(appointments, (row, key) => {
        switch (key) {
          case 'start_time':
            return new Date(row.start_time).getTime()
          case 'visitor_name':
            return row.visitor_name || ''
          case 'visitor_company':
            return row.visitor_company || ''
          case 'organizer':
            return row.organizer?.full_name || ''
          case 'status':
            return row.status || ''
          default:
            return ''
        }
      })
    : []

  const statusLabel = (status?: string) => {
    switch (status) {
      case 'pending':
        return t('appointments.statusPending')
      case 'slot_proposed':
        return t('appointments.statusSlotProposed')
      case 'pending_authorization':
        return t('appointments.statusPendingAuthorization')
      case 'preparation':
        return t('appointments.statusPreparation')
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

  const receptionStatus = (apt: AptRow) =>
    apt.visitor?.checked_in ? t('reception.checkedIn') : t('reception.pending')

  const appointmentsExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'when', header: t('reception.time') },
      { key: 'visitor_name', header: t('reception.visitorName') },
      { key: 'visitor_company', header: t('reception.company') },
      { key: 'host', header: t('appointments.columnVisitHost') },
      { key: 'status', header: t('reception.status') },
    ],
    [t]
  )

  const appointmentsExportRows = useMemo(
    () =>
      sorted.map((apt) => {
        const statusParts = [statusLabel(apt.status), receptionStatus(apt)]
        if (apt.has_pending_deletion_request) {
          statusParts.push(t('appointments.pendingCancellationBadge'))
        }
        if (apt.booking_source === 'public') {
          statusParts.push(t('appointments.publicBookingBadge'))
        }
        if (apt.archived_at) {
          statusParts.push(t('appointments.archivedBadge'))
        }
        const hostRole = apt.organizer?.role
          ? t(`usersAdmin.roleNames.${apt.organizer.role}`, { defaultValue: apt.organizer.role })
          : ''
        const host =
          apt.organizer?.full_name != null
            ? hostRole
              ? `${apt.organizer.full_name} (${hostRole})`
              : apt.organizer.full_name
            : '—'
        return {
          when: `${formatTime(apt.start_time)} – ${formatTime(apt.end_time)}\n${formatDateTime(apt.start_time)}`,
          visitor_name: apt.visitor_name || '—',
          visitor_company: apt.visitor_company || '—',
          host,
          status: statusParts.join(' · '),
        }
      }),
    [sorted, formatTime, formatDateTime, t]
  )

  const isVisitHost = (apt: AptRow) =>
    user?.id != null &&
    apt.organizer_id != null &&
    String(user.id) === String(apt.organizer_id)

  const canConfirmAppointment = (apt: AptRow) =>
    isVisitHost(apt) || user?.role === 'master'

  const canCompleteAppointment = (apt: AptRow) =>
    isVisitHost(apt) || user?.role === 'master' || canDeleteApt

  const canCancelAppointmentDirect = (apt: AptRow) =>
    isVisitHost(apt) || canDeleteApt

  const bulkSelectableAptIds = useMemo(
    () =>
      canExecutivePurge
        ? sorted.map((apt) => apt.id)
        : sorted.filter((apt) => !apt.archived_at).map((apt) => apt.id),
    [sorted, canExecutivePurge]
  )

  const cancellableAptIds = useMemo(
    () =>
      sorted
        .filter(
          (apt) =>
            !apt.archived_at &&
            apt.status !== 'cancelled' &&
            apt.status !== 'completed' &&
            apt.status !== 'no_show' &&
            canCancelAppointmentDirect(apt)
        )
        .map((apt) => apt.id),
    [sorted, user, canDeleteApt]
  )

  useEffect(() => {
    setSelectedAptIds((prev) => prev.filter((id) => bulkSelectableAptIds.includes(id)))
  }, [bulkSelectableAptIds])

  const toggleAptRow = useCallback(
    (id: string) => {
      if (!bulkSelectableAptIds.includes(id)) return
      setSelectedAptIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
    },
    [bulkSelectableAptIds]
  )

  const selectAllAptRows = useCallback(() => {
    setSelectedAptIds((prev) =>
      prev.length === bulkSelectableAptIds.length ? [] : [...bulkSelectableAptIds]
    )
  }, [bulkSelectableAptIds])

  const bulkCancelSelectionEnabled =
    selectedAptIds.length > 0 && selectedAptIds.every((id) => cancellableAptIds.includes(id))

  const bulkOpsPending =
    bulkCancelAptMutation.isPending ||
    bulkArchiveAptMutation.isPending ||
    bulkPermanentAptMutation.isPending

  const handleBulkCancelApt = () => {
    if (!bulkCancelSelectionEnabled) return
    if (!window.confirm(t('appointments.bulkCancelConfirm', { count: selectedAptIds.length }))) return
    bulkCancelAptMutation.mutate(selectedAptIds)
  }

  const handleBulkArchiveApt = () => {
    if (!selectedAptIds.length) return
    if (!window.confirm(t('appointments.bulkArchiveConfirm', { count: selectedAptIds.length }))) return
    bulkArchiveAptMutation.mutate(selectedAptIds)
  }

  const handleBulkPermanentApt = () => {
    if (!selectedAptIds.length || !canExecutivePurge) return
    if (!window.confirm(t('appointments.bulkPermanentConfirm', { count: selectedAptIds.length }))) return
    bulkPermanentAptMutation.mutate(selectedAptIds)
  }

  useEffect(() => {
    const revokeCurrent = () => {
      if (visitorPhotoBlobRef.current) {
        URL.revokeObjectURL(visitorPhotoBlobRef.current)
        visitorPhotoBlobRef.current = null
      }
      setVisitorPhotoUrl(null)
    }

    if (!viewOpen || !selectedAppointment?.id) {
      revokeCurrent()
      setVisitorPhotoLoading(false)
      return undefined
    }
    if (!selectedAppointment.visitor?.visitor_photo_path) {
      revokeCurrent()
      setVisitorPhotoLoading(false)
      return undefined
    }
    let alive = true
    revokeCurrent()
    setVisitorPhotoLoading(true)
    ;(async () => {
      try {
        const res = await api.get(`/appointments/${selectedAppointment.id}/visitor/photo`, {
          responseType: 'blob',
        })
        if (!alive) return
        const url = URL.createObjectURL(res.data)
        if (!alive) {
          URL.revokeObjectURL(url)
          return
        }
        visitorPhotoBlobRef.current = url
        setVisitorPhotoUrl(url)
      } catch (e) {
        if (import.meta.env.DEV) {
          console.warn('[Appointments] GET visitor/photo failed', e)
        }
        if (alive) revokeCurrent()
      } finally {
        if (alive) setVisitorPhotoLoading(false)
      }
    })()
    return () => {
      alive = false
      revokeCurrent()
    }
  }, [viewOpen, selectedAppointment?.id, selectedAppointment?.visitor?.visitor_photo_path])

  useEffect(() => {
    const revokeCurrent = () => {
      if (visitorIdDocBlobRef.current) {
        URL.revokeObjectURL(visitorIdDocBlobRef.current)
        visitorIdDocBlobRef.current = null
      }
      setVisitorIdDocUrl(null)
    }

    if (!viewOpen || !selectedAppointment?.id) {
      revokeCurrent()
      setVisitorIdDocLoading(false)
      return undefined
    }
    if (!selectedAppointment.visitor?.visitor_id_document_path) {
      revokeCurrent()
      setVisitorIdDocLoading(false)
      return undefined
    }
    let alive = true
    revokeCurrent()
    setVisitorIdDocLoading(true)
    ;(async () => {
      try {
        const res = await api.get(`/appointments/${selectedAppointment.id}/visitor/id-document`, {
          responseType: 'blob',
        })
        if (!alive) return
        const url = URL.createObjectURL(res.data)
        if (!alive) {
          URL.revokeObjectURL(url)
          return
        }
        visitorIdDocBlobRef.current = url
        setVisitorIdDocUrl(url)
      } catch (e) {
        if (import.meta.env.DEV) {
          console.warn('[Appointments] GET visitor/id-document failed', e)
        }
        if (alive) revokeCurrent()
      } finally {
        if (alive) setVisitorIdDocLoading(false)
      }
    })()
    return () => {
      alive = false
      revokeCurrent()
    }
  }, [viewOpen, selectedAppointment?.id, selectedAppointment?.visitor?.visitor_id_document_path])

  useEffect(() => {
    if (!viewOpen) {
      setVisitorPhotoZoomOpen(false)
      setVisitorIdDocZoomOpen(false)
    }
  }, [viewOpen])

  const stopQrScan = async () => {
    const scanner = html5QrCodeRef.current
    html5QrCodeRef.current = null
    if (scanner) {
      try {
        await scanner.stop()
      } catch {
        // déjà arrêté ou pas démarré
      }
      try {
        scanner.clear()
      } catch {
        // ignore
      }
    }
    setIsQrScanning(false)
  }

  const startQrScan = async () => {
    setQrScanError('')
    qrDecodeLockRef.current = false
    if (html5QrCodeRef.current) {
      await stopQrScan()
    }
    setIsQrScanning(true)
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
    })
    try {
      const html5QrCode = new Html5Qrcode(APPOINTMENTS_QR_READER_ID)
      html5QrCodeRef.current = html5QrCode
      await html5QrCode.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText) => {
          if (qrDecodeLockRef.current) return
          const raw = decodedText.trim()
          if (!raw) return
          qrDecodeLockRef.current = true
          setQrPayload(raw)
          void (async () => {
            try {
              await stopQrScan()
            } catch {
              // ignore
            }
            checkInByQrMutation.mutate(raw, {
              onSettled: () => {
                qrDecodeLockRef.current = false
              },
            })
          })()
        },
        () => undefined
      )
    } catch (err: unknown) {
      html5QrCodeRef.current = null
      const message = err instanceof Error ? err.message : String(err)
      setQrScanError(message || t('appointments.qrScannerStartFailed'))
      setIsQrScanning(false)
    }
  }

  useEffect(() => {
    return () => {
      const scanner = html5QrCodeRef.current
      html5QrCodeRef.current = null
      if (scanner) {
        scanner
          .stop()
          .then(() => scanner.clear())
          .catch(() => {
            try {
              scanner.clear()
            } catch {
              // ignore
            }
          })
      }
    }
  }, [])

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {t('appointments.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('appointments.listSubtitle')}
          </Typography>
        </Box>
        <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
          {canCreate && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
              sx={{ minWidth: 180 }}
            >
              {t('appointments.newAppointment')}
            </Button>
          )}
          {canBulkOps && (
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={includeArchived}
                  onChange={(e) => setIncludeArchived(e.target.checked)}
                />
              }
              label={t('appointments.showArchivedToggle')}
              sx={{ mr: 0, ml: 0 }}
            />
          )}
          {canBulkOps && (
            <>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteOutlineIcon />}
                disabled={!bulkCancelSelectionEnabled || bulkOpsPending}
                onClick={handleBulkCancelApt}
              >
                {bulkCancelAptMutation.isPending
                  ? t('common.loading')
                  : t('appointments.bulkCancelSelected', { count: selectedAptIds.length })}
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<Inventory2Icon />}
                disabled={!selectedAptIds.length || bulkOpsPending}
                onClick={handleBulkArchiveApt}
              >
                {bulkArchiveAptMutation.isPending
                  ? t('common.loading')
                  : t('appointments.bulkArchiveSelected', { count: selectedAptIds.length })}
              </Button>
              {canExecutivePurge && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteForeverIcon />}
                  disabled={!selectedAptIds.length || bulkOpsPending}
                  onClick={handleBulkPermanentApt}
                >
                  {bulkPermanentAptMutation.isPending
                    ? t('common.loading')
                    : t('appointments.bulkPermanentSelected', { count: selectedAptIds.length })}
                </Button>
              )}
            </>
          )}
        </Box>
      </Box>

      {actionMessage && (
        <Alert
          severity={actionMessage.type}
          sx={{ mb: 2 }}
          onClose={() => setActionMessage(null)}
        >
          {actionMessage.text}
        </Alert>
      )}

      {canCheckIn && (
        <Paper sx={{ p: 2, mb: 2, borderRadius: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t('appointments.qrCheckInTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('appointments.qrCheckInSubtitle')}
          </Typography>
          {qrScanError && (
            <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setQrScanError('')}>
              {qrScanError}
            </Alert>
          )}
          <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
            <TextField
              label={t('appointments.qrPayloadLabel')}
              value={qrPayload}
              onChange={(e) => setQrPayload(e.target.value)}
              size="small"
              sx={{ minWidth: 320, flex: 1 }}
            />
            <Button
              variant="contained"
              startIcon={<CheckIcon />}
              onClick={() => checkInByQrMutation.mutate(qrPayload)}
              disabled={!qrPayload.trim() || checkInByQrMutation.isPending}
            >
              {t('appointments.qrCheckInAction')}
            </Button>
            {!isQrScanning ? (
              <Button variant="outlined" startIcon={<QrCodeScannerIcon />} onClick={() => void startQrScan()}>
                {t('appointments.qrStartScan')}
              </Button>
            ) : (
              <Button variant="outlined" color="warning" onClick={() => void stopQrScan()}>
                {t('appointments.qrStopScan')}
              </Button>
            )}
          </Box>
          <Box sx={{ mt: 2, display: isQrScanning ? 'block' : 'none' }}>
            <div
              id={APPOINTMENTS_QR_READER_ID}
              style={{ width: '100%', maxWidth: 460, minHeight: 200 }}
            />
          </Box>
        </Paper>
      )}

      <Paper
        elevation={0}
        sx={{
          mb: 2,
          p: 2,
          borderRadius: 3,
          border: 1,
          borderColor: 'divider',
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1} mb={2}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {t('appointments.filtersTitle')}
          </Typography>
          <Button
            size="small"
            startIcon={<FilterAltOffIcon />}
            onClick={resetListFilters}
            disabled={
              !filterSearchInput &&
              !filterStatus &&
              !filterOrganizerId &&
              !filterDateFrom &&
              !filterDateTo &&
              !filterBookingSource &&
              !filterCheckedIn &&
              !filterReceptionValidated &&
              !filterPendingCancellation
            }
          >
            {t('appointments.filtersReset')}
          </Button>
        </Box>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6} lg={4}>
            <TextField
              fullWidth
              size="small"
              label={t('appointments.filterSearch')}
              placeholder={t('appointments.filterSearchPlaceholder')}
              value={filterSearchInput}
              onChange={(e) => setFilterSearchInput(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="apt-filter-status">{t('appointments.filterStatus')}</InputLabel>
              <Select
                labelId="apt-filter-status"
                label={t('appointments.filterStatus')}
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <MenuItem value="">{t('appointments.filterAny')}</MenuItem>
                {APPOINTMENT_STATUS_FILTER_VALUES.filter(Boolean).map((s) => (
                  <MenuItem key={s} value={s}>
                    {statusLabel(s)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          {aptBroadAccess && (
            <Grid item xs={12} sm={6} md={4} lg={3}>
              <FormControl fullWidth size="small">
                <InputLabel id="apt-filter-host">{t('appointments.filterHost')}</InputLabel>
                <Select
                  labelId="apt-filter-host"
                  label={t('appointments.filterHost')}
                  value={filterOrganizerId}
                  onChange={(e) => setFilterOrganizerId(e.target.value)}
                >
                  <MenuItem value="">{t('appointments.filterAny')}</MenuItem>
                  {visitHostFilterOptions.map((h) => (
                    <MenuItem key={h.id} value={h.id}>
                      {h.full_name || h.username}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          )}
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label={t('appointments.filterDateFrom')}
              value={filterDateFrom}
              onChange={(e) => setFilterDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label={t('appointments.filterDateTo')}
              value={filterDateTo}
              onChange={(e) => setFilterDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="apt-filter-booking">{t('appointments.filterBookingSource')}</InputLabel>
              <Select
                labelId="apt-filter-booking"
                label={t('appointments.filterBookingSource')}
                value={filterBookingSource}
                onChange={(e) => setFilterBookingSource(e.target.value)}
              >
                <MenuItem value="">{t('appointments.filterAny')}</MenuItem>
                <MenuItem value="internal">{t('appointments.bookingInternal')}</MenuItem>
                <MenuItem value="public">{t('appointments.bookingPublic')}</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="apt-filter-checkin">{t('appointments.filterCheckedIn')}</InputLabel>
              <Select
                labelId="apt-filter-checkin"
                label={t('appointments.filterCheckedIn')}
                value={filterCheckedIn}
                onChange={(e) => setFilterCheckedIn(e.target.value)}
              >
                <MenuItem value="">{t('appointments.filterAny')}</MenuItem>
                <MenuItem value="yes">{t('common.yes')}</MenuItem>
                <MenuItem value="no">{t('common.no')}</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="apt-filter-reception">{t('appointments.filterReceptionValidated')}</InputLabel>
              <Select
                labelId="apt-filter-reception"
                label={t('appointments.filterReceptionValidated')}
                value={filterReceptionValidated}
                onChange={(e) => setFilterReceptionValidated(e.target.value)}
              >
                <MenuItem value="">{t('appointments.filterAny')}</MenuItem>
                <MenuItem value="yes">{t('common.yes')}</MenuItem>
                <MenuItem value="no">{t('common.no')}</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={4} lg={3}>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={filterPendingCancellation}
                  onChange={(e) => setFilterPendingCancellation(e.target.checked)}
                />
              }
              label={t('appointments.filterPendingCancellation')}
            />
          </Grid>
        </Grid>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          {t('appointments.filtersResultHint')}
        </Typography>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error instanceof Error ? error.message : t('appointments.loadFailed')}
        </Alert>
      )}

      {(canBulkOps || canExecutivePurge) && selectedAptIds.length > 0 && (
        <Paper
          elevation={0}
          sx={{
            mb: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 1.5,
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
            bgcolor: 'action.hover',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('appointments.bulkSelectionCount', { count: selectedAptIds.length })}
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            <Button
              variant="contained"
              color="error"
              size="medium"
              startIcon={<DeleteOutlineIcon />}
              disabled={!bulkCancelSelectionEnabled || bulkOpsPending}
              onClick={handleBulkCancelApt}
            >
              {bulkCancelAptMutation.isPending
                ? t('common.loading')
                : t('appointments.bulkCancelSelected', { count: selectedAptIds.length })}
            </Button>
            <Button
              variant="contained"
              color="secondary"
              size="medium"
              startIcon={<Inventory2Icon />}
              disabled={bulkOpsPending}
              onClick={handleBulkArchiveApt}
            >
              {bulkArchiveAptMutation.isPending
                ? t('common.loading')
                : t('appointments.bulkArchiveSelected', { count: selectedAptIds.length })}
            </Button>
            {canExecutivePurge && (
              <Button
                variant="contained"
                color="error"
                size="medium"
                startIcon={<DeleteForeverIcon />}
                disabled={bulkOpsPending}
                onClick={handleBulkPermanentApt}
              >
                {bulkPermanentAptMutation.isPending
                  ? t('common.loading')
                  : t('appointments.bulkPermanentSelected', { count: selectedAptIds.length })}
              </Button>
            )}
          </Box>
        </Paper>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
        <TableExportButton
          filenameBase="appointments"
          sheetName={t('appointments.title')}
          columns={appointmentsExportColumns}
          rows={appointmentsExportRows}
          disabled={isLoading}
        />
      </Box>

      <TableContainer
        component={Paper}
        sx={{
          ...tableContainerScrollSx,
          borderRadius: 3,
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              {showSelectionColumn && (
                <TableCell padding="checkbox" sx={{ width: 48 }}>
                  <Checkbox
                    size="small"
                    indeterminate={
                      selectedAptIds.length > 0 &&
                      selectedAptIds.length < bulkSelectableAptIds.length
                    }
                    checked={
                      bulkSelectableAptIds.length > 0 &&
                      selectedAptIds.length === bulkSelectableAptIds.length
                    }
                    onChange={selectAllAptRows}
                    inputProps={{ 'aria-label': t('appointments.bulkSelectAllAria') }}
                  />
                </TableCell>
              )}
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'start_time'}
                  direction={sortBy === 'start_time' ? sortDir : 'asc'}
                  onClick={() => toggleSort('start_time')}
                >
                  {t('reception.time')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'visitor_name'}
                  direction={sortBy === 'visitor_name' ? sortDir : 'asc'}
                  onClick={() => toggleSort('visitor_name')}
                >
                  {t('reception.visitorName')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'visitor_company'}
                  direction={sortBy === 'visitor_company' ? sortDir : 'asc'}
                  onClick={() => toggleSort('visitor_company')}
                >
                  {t('reception.company')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'organizer'}
                  direction={sortBy === 'organizer' ? sortDir : 'asc'}
                  onClick={() => toggleSort('organizer')}
                >
                  {t('appointments.columnVisitHost')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'status'}
                  direction={sortBy === 'status' ? sortDir : 'asc'}
                  onClick={() => toggleSort('status')}
                >
                  {t('reception.status')}
                </TableSortLabel>
              </TableCell>
              <TableCell>{t('common.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={showSelectionColumn ? 7 : 6} align="center" sx={{ py: 4 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : !sorted.length ? (
              <TableRow>
                <TableCell colSpan={showSelectionColumn ? 7 : 6} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">{t('appointments.noAppointments')}</Typography>
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((apt) => {
                const showCheckIn =
                  isSameLocalDay(apt.start_time) &&
                  !apt.visitor?.checked_in &&
                  !apt.archived_at
                const aptSelectable = bulkSelectableAptIds.includes(apt.id)
                return (
                  <TableRow
                    key={apt.id}
                    hover
                    selected={showSelectionColumn && selectedAptIds.includes(apt.id)}
                    sx={appointmentTableRowSx(apt)}
                  >
                    {showSelectionColumn && (
                      <TableCell padding="checkbox">
                        <Checkbox
                          size="small"
                          disabled={!aptSelectable}
                          checked={selectedAptIds.includes(apt.id)}
                          onChange={() => toggleAptRow(apt.id)}
                          inputProps={{
                            'aria-label': t('appointments.bulkSelectRowAria', {
                              name: apt.visitor_name || apt.title || apt.id,
                            }),
                          }}
                        />
                      </TableCell>
                    )}
                    <TableCell>
                      <Typography variant="body2">
                        {formatTime(apt.start_time)} – {formatTime(apt.end_time)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDateTime(apt.start_time)}
                      </Typography>
                    </TableCell>
                    <TableCell>{apt.visitor_name || '—'}</TableCell>
                    <TableCell>{apt.visitor_company || '—'}</TableCell>
                    <TableCell>
                      {apt.organizer?.full_name || '—'}
                      {apt.organizer?.role && (
                        <Typography component="span" variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          {t(`usersAdmin.roleNames.${apt.organizer.role}`, { defaultValue: apt.organizer.role })}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Box display="flex" flexWrap="wrap" gap={0.5} alignItems="center">
                        <Chip label={statusLabel(apt.status)} size="small" variant="outlined" />
                        <Chip
                          label={receptionStatus(apt)}
                          color={apt.visitor?.checked_in ? 'success' : 'default'}
                          size="small"
                        />
                        {apt.has_pending_deletion_request && (
                          <Chip label={t('appointments.pendingCancellationBadge')} size="small" color="warning" />
                        )}
                        {apt.booking_source === 'public' && (
                          <Chip label={t('appointments.publicBookingBadge')} size="small" color="info" variant="outlined" />
                        )}
                        {apt.archived_at && (
                          <Chip label={t('appointments.archivedBadge')} size="small" color="default" />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<ViewIcon />}
                          onClick={() => {
                            setSelectedAppointment(apt)
                            setViewOpen(true)
                          }}
                        >
                          {t('common.view')}
                        </Button>
                        {canBulkOps && !apt.archived_at && (
                          <Tooltip title={t('appointments.archiveAppointment')}>
                            <IconButton
                              size="small"
                              color="secondary"
                              aria-label={t('appointments.archiveAppointment')}
                              disabled={archiveSingleMutation.isPending}
                              onClick={() => {
                                if (!window.confirm(t('appointments.archiveOneConfirm'))) return
                                archiveSingleMutation.mutate(apt.id)
                              }}
                            >
                              <Inventory2Icon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {canExecutivePurge && (
                          <Tooltip title={t('appointments.permanentDelete')}>
                            <IconButton
                              size="small"
                              color="error"
                              aria-label={t('appointments.permanentDelete')}
                              disabled={permanentSingleMutation.isPending}
                              onClick={() => {
                                if (!window.confirm(t('appointments.permanentDeleteOneConfirm'))) return
                                permanentSingleMutation.mutate(apt.id)
                              }}
                            >
                              <DeleteForeverIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {showCheckIn && canCheckIn && (
                          <Button
                            size="small"
                            variant="contained"
                            startIcon={<CheckIcon />}
                            onClick={() => checkInMutation.mutate(apt.id)}
                            disabled={checkInMutation.isPending}
                          >
                            {t('reception.checkIn')}
                          </Button>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {canCreate && (
        <CreateAppointmentDialog
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          defaultHostUserId={user?.id != null ? String(user.id) : undefined}
        />
      )}

      <Dialog
        open={viewOpen}
        onClose={() => setViewOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { overflow: 'hidden' } }}
      >
        {selectedAppointment && (
          <ModalSectionHeader>
            <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('reception.appointmentDetails')}
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              {selectedAppointment.title || '—'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              {formatDateTime(selectedAppointment.start_time)} — {formatTime(selectedAppointment.end_time)}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
              <Chip label={statusLabel(selectedAppointment.status)} size="small" variant="outlined" />
              <Chip
                label={
                  selectedAppointment.visitor?.checked_in
                    ? t('reception.checkedIn')
                    : t('reception.pendingCheckIn')
                }
                color={selectedAppointment.visitor?.checked_in ? 'success' : 'default'}
                size="small"
              />
              {selectedAppointment.has_pending_deletion_request && (
                <Chip label={t('appointments.pendingCancellationBadge')} size="small" color="warning" />
              )}
              {selectedAppointment.booking_source === 'public' && (
                <Chip label={t('appointments.publicBookingBadge')} size="small" color="info" variant="outlined" />
              )}
              {selectedAppointment.reception_validated_at && (
                <Chip label={t('appointments.receptionValidatedBadge')} size="small" />
              )}
              {selectedAppointment.visitor_booking_email_sent_at && (
                <Chip label={t('appointments.visitorEmailSentBadge')} size="small" color="success" variant="outlined" />
              )}
            </Box>
          </ModalSectionHeader>
        )}
        <DialogContent sx={{ p: 0 }}>
          {selectedAppointment && (
            <ModalSectionBody sx={{ pt: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
              <Box
                sx={{
                  flexShrink: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <Tooltip
                  title={
                    visitorPhotoUrl && !visitorPhotoLoading
                      ? t('appointments.visitorPhotoZoomEnlarge')
                      : ''
                  }
                  disableHoverListener={!visitorPhotoUrl || visitorPhotoLoading}
                >
                  <Box
                    sx={{
                      position: 'relative',
                      width: 96,
                      height: 96,
                      cursor:
                        visitorPhotoUrl && !visitorPhotoLoading ? 'zoom-in' : 'default',
                    }}
                    onClick={() => {
                      if (visitorPhotoUrl && !visitorPhotoLoading) {
                        setVisitorPhotoZoomOpen(true)
                      }
                    }}
                    onKeyDown={(e) => {
                      if (
                        (e.key === 'Enter' || e.key === ' ') &&
                        visitorPhotoUrl &&
                        !visitorPhotoLoading
                      ) {
                        e.preventDefault()
                        setVisitorPhotoZoomOpen(true)
                      }
                    }}
                    role={visitorPhotoUrl && !visitorPhotoLoading ? 'button' : undefined}
                    tabIndex={visitorPhotoUrl && !visitorPhotoLoading ? 0 : undefined}
                  >
                    <Avatar
                      src={visitorPhotoUrl || undefined}
                      alt={selectedAppointment.visitor_name || ''}
                      imgProps={{
                        onError: () => {
                          if (visitorPhotoBlobRef.current) {
                            URL.revokeObjectURL(visitorPhotoBlobRef.current)
                            visitorPhotoBlobRef.current = null
                          }
                          setVisitorPhotoUrl(null)
                        },
                      }}
                      sx={{
                        width: 96,
                        height: 96,
                        bgcolor: 'primary.main',
                        fontSize: '2rem',
                      }}
                    >
                      {(selectedAppointment.visitor_name || selectedAppointment.title || '?')
                        .toString()
                        .trim()
                        .charAt(0)
                        .toUpperCase()}
                    </Avatar>
                    {visitorPhotoUrl && !visitorPhotoLoading && (
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
                    {visitorPhotoLoading && (
                      <Box
                        sx={{
                          position: 'absolute',
                          inset: 0,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '50%',
                          bgcolor: 'action.hover',
                          opacity: 0.85,
                        }}
                      >
                        <CircularProgress size={28} />
                      </Box>
                    )}
                  </Box>
                </Tooltip>
                {selectedAppointment.visitor?.visitor_id_document_path ? (
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
                      title={
                        visitorIdDocUrl && !visitorIdDocLoading
                          ? t('appointments.visitorIdDocumentZoomEnlarge')
                          : ''
                      }
                      disableHoverListener={!visitorIdDocUrl || visitorIdDocLoading}
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
                          cursor: visitorIdDocUrl && !visitorIdDocLoading ? 'zoom-in' : 'default',
                          bgcolor: 'action.hover',
                        }}
                        onClick={() => {
                          if (visitorIdDocUrl && !visitorIdDocLoading) setVisitorIdDocZoomOpen(true)
                        }}
                        onKeyDown={(e) => {
                          if (
                            (e.key === 'Enter' || e.key === ' ') &&
                            visitorIdDocUrl &&
                            !visitorIdDocLoading
                          ) {
                            e.preventDefault()
                            setVisitorIdDocZoomOpen(true)
                          }
                        }}
                        role={visitorIdDocUrl && !visitorIdDocLoading ? 'button' : undefined}
                        tabIndex={visitorIdDocUrl && !visitorIdDocLoading ? 0 : undefined}
                      >
                        {visitorIdDocUrl && !visitorIdDocLoading ? (
                          <Box
                            component="img"
                            src={visitorIdDocUrl}
                            alt=""
                            sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        ) : null}
                        {visitorIdDocLoading && (
                          <Box
                            sx={{
                              position: 'absolute',
                              inset: 0,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            <CircularProgress size={28} />
                          </Box>
                        )}
                      </Box>
                    </Tooltip>
                  </Box>
                ) : null}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
              {selectedAppointment.description && (
                <Typography variant="body2" color="text.secondary" paragraph>
                  {selectedAppointment.description}
                </Typography>
              )}
              <Typography variant="body2" paragraph>
                <strong>{t('reception.visitorName')}:</strong> {selectedAppointment.visitor_name || '—'}
              </Typography>
              {selectedAppointment.visitor_email && (
                <Typography variant="body2" paragraph>
                  <strong>{t('appointments.email')}:</strong> {selectedAppointment.visitor_email}
                </Typography>
              )}
              {selectedAppointment.visitor_company && (
                <Typography variant="body2" paragraph>
                  <strong>{t('reception.company')}:</strong> {selectedAppointment.visitor_company}
                </Typography>
              )}
              <Typography variant="body2" paragraph>
                <strong>{t('appointments.solicitedPersonLabel')}:</strong> {selectedAppointment.organizer?.full_name || '—'}
                {selectedAppointment.organizer?.role && (
                  <>
                    {' '}
                    <Typography component="span" variant="body2" color="text.secondary">
                      ({t('appointments.solicitedPersonFunction')}:{' '}
                      {t(`usersAdmin.roleNames.${selectedAppointment.organizer.role}`, {
                        defaultValue: selectedAppointment.organizer.role,
                      })}
                      )
                    </Typography>
                  </>
                )}
              </Typography>
              {selectedAppointment.has_pending_deletion_request && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  {t('appointments.pendingCancellationNotice')}
                </Alert>
              )}
              {selectedAppointment.archived_at && (
                <Alert severity="info" sx={{ mt: 1 }}>
                  {t('appointments.archivedDetailNotice')}
                </Alert>
              )}
              {canUpdateApt && !selectedAppointment.archived_at && (
                <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    {t('appointments.internalNotesLabel')}
                  </Typography>
                  <TextField
                    value={internalNotesDraft}
                    onChange={(e) => setInternalNotesDraft(e.target.value)}
                    fullWidth
                    multiline
                    minRows={2}
                    size="small"
                    disabled={saveInternalNotesMutation.isPending || finalizeReceptionMutation.isPending}
                  />
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', mt: 1.5 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() =>
                        selectedAppointment &&
                        saveInternalNotesMutation.mutate({
                          id: selectedAppointment.id,
                          internal_notes: internalNotesDraft,
                        })
                      }
                      disabled={
                        saveInternalNotesMutation.isPending ||
                        finalizeReceptionMutation.isPending ||
                        !selectedAppointment
                      }
                    >
                      {t('appointments.saveInternalNotes')}
                    </Button>
                    <Button
                      size="small"
                      variant="contained"
                      color="secondary"
                      onClick={() =>
                        selectedAppointment &&
                        finalizeReceptionMutation.mutate({
                          id: selectedAppointment.id,
                          internal_notes: internalNotesDraft,
                          force_resend_visitor_email: finalizeForceResend,
                        })
                      }
                      disabled={
                        finalizeReceptionMutation.isPending ||
                        saveInternalNotesMutation.isPending ||
                        !selectedAppointment
                      }
                    >
                      {t('appointments.finalizeReception')}
                    </Button>
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={finalizeForceResend}
                          onChange={(e) => setFinalizeForceResend(e.target.checked)}
                          disabled={finalizeReceptionMutation.isPending}
                        />
                      }
                      label={t('appointments.forceResendEmail')}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                    {t('appointments.finalizeReceptionHint')}
                  </Typography>
                </Box>
              )}
              </Box>
            </Box>
            </ModalSectionBody>
          )}
        </DialogContent>
        <DialogActions sx={modalDialogFooterSx}>
          <Button onClick={() => setViewOpen(false)}>{t('common.close')}</Button>
          {selectedAppointment &&
            selectedAppointment.status === 'pending' &&
            canConfirmAppointment(selectedAppointment) && (
              <Button
                variant="contained"
                color="success"
                startIcon={<HowToRegIcon />}
                onClick={() => confirmMutation.mutate(selectedAppointment.id)}
                disabled={confirmMutation.isPending}
              >
                {confirmMutation.isPending ? t('common.loading') : t('appointments.confirmAppointment')}
              </Button>
            )}
          {selectedAppointment &&
            !selectedAppointment.archived_at &&
            selectedAppointment.status === 'confirmed' &&
            canCompleteAppointment(selectedAppointment) && (
              <Button
                variant="contained"
                color="primary"
                startIcon={<TaskAltIcon />}
                onClick={() => completeMutation.mutate(selectedAppointment.id)}
                disabled={completeMutation.isPending || noShowMutation.isPending}
              >
                {completeMutation.isPending ? t('common.loading') : t('appointments.completeAppointment')}
              </Button>
            )}
          {selectedAppointment &&
            !selectedAppointment.archived_at &&
            selectedAppointment.status === 'confirmed' &&
            canCompleteAppointment(selectedAppointment) && (
              <Button
                variant="outlined"
                color="warning"
                startIcon={<PersonOffIcon />}
                onClick={() => noShowMutation.mutate(selectedAppointment.id)}
                disabled={completeMutation.isPending || noShowMutation.isPending}
              >
                {noShowMutation.isPending ? t('common.loading') : t('appointments.noShowButton')}
              </Button>
            )}
          {selectedAppointment &&
            !selectedAppointment.archived_at &&
            selectedAppointment.status !== 'cancelled' &&
            selectedAppointment.status !== 'completed' &&
            selectedAppointment.status !== 'no_show' &&
            canCancelAppointmentDirect(selectedAppointment) && (
              <Button
                color="error"
                startIcon={<DeleteOutlineIcon />}
                onClick={() => setCancelConfirmOpen(true)}
              >
                {t('appointments.cancelAppointment')}
              </Button>
            )}
          {selectedAppointment &&
            !selectedAppointment.archived_at &&
            selectedAppointment.status !== 'cancelled' &&
            selectedAppointment.status !== 'completed' &&
            selectedAppointment.status !== 'no_show' &&
            canRequestCancel &&
            !selectedAppointment.has_pending_deletion_request &&
            !canCancelAppointmentDirect(selectedAppointment) && (
              <Button
                color="warning"
                variant="outlined"
                startIcon={<EventBusyIcon />}
                onClick={() => setRequestCancelOpen(true)}
              >
                {t('appointments.requestCancellation')}
              </Button>
            )}
          {selectedAppointment &&
            !selectedAppointment.archived_at &&
            isSameLocalDay(selectedAppointment.start_time) &&
            !selectedAppointment.visitor?.checked_in &&
            canCheckIn && (
              <Button
                variant="contained"
                startIcon={<CheckIcon />}
                onClick={() => {
                  checkInMutation.mutate(selectedAppointment.id)
                  setViewOpen(false)
                }}
                disabled={checkInMutation.isPending}
              >
                {t('appointments.checkInDetailLabel')}
              </Button>
            )}
          {selectedAppointment && canBulkOps && !selectedAppointment.archived_at && (
            <Button
              color="secondary"
              variant="outlined"
              startIcon={<Inventory2Icon />}
              disabled={archiveSingleMutation.isPending}
              onClick={() => {
                if (!window.confirm(t('appointments.archiveOneConfirm'))) return
                archiveSingleMutation.mutate(selectedAppointment.id)
              }}
            >
              {archiveSingleMutation.isPending ? t('common.loading') : t('appointments.archiveAppointment')}
            </Button>
            )}
          {selectedAppointment && canExecutivePurge && (
            <Button
              color="error"
              variant="outlined"
              startIcon={<DeleteForeverIcon />}
              disabled={permanentSingleMutation.isPending}
              onClick={() => {
                if (!window.confirm(t('appointments.permanentDeleteOneConfirm'))) return
                permanentSingleMutation.mutate(selectedAppointment.id)
              }}
            >
              {permanentSingleMutation.isPending
                ? t('common.loading')
                : t('appointments.permanentDelete')}
            </Button>
            )}
        </DialogActions>
      </Dialog>

      <VisitorPhotoZoomDialog
        open={visitorPhotoZoomOpen}
        onClose={() => setVisitorPhotoZoomOpen(false)}
        imageUrl={visitorPhotoUrl}
        visitorName={selectedAppointment?.visitor_name}
      />
      <VisitorPhotoZoomDialog
        open={visitorIdDocZoomOpen}
        onClose={() => setVisitorIdDocZoomOpen(false)}
        imageUrl={visitorIdDocUrl}
        visitorName={selectedAppointment?.visitor_name}
        title={t('appointments.visitorIdDocumentZoomTitle')}
        hint={t('appointments.visitorIdDocumentZoomHint')}
      />

      <Dialog open={cancelConfirmOpen} onClose={() => !cancelMutation.isPending && setCancelConfirmOpen(false)}>
        <DialogTitle>{t('appointments.confirmCancelTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2">{t('appointments.confirmCancelBody')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCancelConfirmOpen(false)} disabled={cancelMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={cancelMutation.isPending || !selectedAppointment}
            onClick={() => selectedAppointment && cancelMutation.mutate(selectedAppointment.id)}
          >
            {t('appointments.cancelAppointment')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={requestCancelOpen}
        onClose={() => !requestCancelMutation.isPending && setRequestCancelOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t('appointments.requestCancellationTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {t('appointments.requestCancellationHint')}
          </Typography>
          <TextField
            label={t('appointments.requestCancellationReason')}
            value={requestCancelReason}
            onChange={(e) => setRequestCancelReason(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            disabled={requestCancelMutation.isPending}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRequestCancelOpen(false)} disabled={requestCancelMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            disabled={requestCancelMutation.isPending || !selectedAppointment}
            onClick={() =>
              selectedAppointment &&
              requestCancelMutation.mutate({
                id: selectedAppointment.id,
                reason: requestCancelReason,
              })
            }
          >
            {t('common.submit')}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={checkInToast.open}
        autoHideDuration={6000}
        onClose={(_, reason) => {
          if (reason === 'clickaway') return
          setCheckInToast((s) => ({ ...s, open: false }))
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={checkInToast.severity}
          variant="filled"
          onClose={() => setCheckInToast((s) => ({ ...s, open: false }))}
          sx={{ width: '100%' }}
        >
          {checkInToast.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}
