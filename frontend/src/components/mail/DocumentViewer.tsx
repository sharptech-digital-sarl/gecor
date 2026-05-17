import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material'
import SignaturePad from './SignaturePad'
import ImageViewer from './ImageViewer'
import api from '../../services/api'
import { useAuth } from '../../hooks/useAuth'
import { hasPermission } from '../../utils/permissions'
import { isMasterOrDirector } from '../../utils/roles'
import {
  ModalSectionHeader,
  ModalSectionBody,
  modalDialogFooterSx,
} from '../common/DetailModalLayout'

type AvailableMailAction = {
  action_key: string
  to_status: string
  label: string
  requires_assignee: boolean
}

/** Valeurs stockées en `current_department` (orientation secrétariat). */
const ROUTING_SERVICE_IDS = [
  'finance',
  'hr',
  'legal',
  'it',
  'operations',
  'communication',
  'dg_office',
  'other',
] as const

const ROUTING_I18N: Record<(typeof ROUTING_SERVICE_IDS)[number], string> = {
  finance: 'mail.viewer.routingFinance',
  hr: 'mail.viewer.routingHr',
  legal: 'mail.viewer.routingLegal',
  it: 'mail.viewer.routingIt',
  operations: 'mail.viewer.routingOperations',
  communication: 'mail.viewer.routingCommunication',
  dg_office: 'mail.viewer.routingDgOffice',
  other: 'mail.viewer.routingOther',
}

interface DocumentViewerProps {
  open: boolean
  document: any
  onClose: () => void
  /** Refresh list after delete or deletion request */
  onMailChanged?: () => void
}

export default function DocumentViewer({
  open,
  document,
  onClose,
  onMailChanged,
}: DocumentViewerProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState(0)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [requestOpen, setRequestOpen] = useState(false)
  const [requestReason, setRequestReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const [pendingAction, setPendingAction] = useState<AvailableMailAction | null>(null)
  const [assigneeId, setAssigneeId] = useState('')
  const [routingDepartment, setRoutingDepartment] = useState('')
  const [transitionNotes, setTransitionNotes] = useState('')

  const [freshDoc, setFreshDoc] = useState<any>(null)
  useEffect(() => {
    if (open && document) setFreshDoc(null)
  }, [open, document?.id])

  const displayDoc = freshDoc ?? document

  const { data: availableActions = [] } = useQuery({
    queryKey: ['mail-available-actions', displayDoc?.id],
    queryFn: async () => {
      const r = await api.get<AvailableMailAction[]>(`/mail/${displayDoc!.id}/available-actions`)
      return r.data
    },
    enabled: open && !!displayDoc?.id,
  })

  const { data: userOptions = [] } = useQuery({
    queryKey: ['mail-assign-users'],
    queryFn: async () => {
      const r = await api.get<Array<{ id: string; full_name: string; email: string }>>('/users/', {
        params: { limit: 200 },
      })
      return r.data || []
    },
    enabled: open && assignOpen,
  })

  const transitionMutation = useMutation({
    mutationFn: async (body: {
      action_key: string
      notes?: string | null
      assigned_to_id?: string | null
      current_department?: string | null
    }) => {
      const id = displayDoc?.id
      if (!id) throw new Error('No document')
      await api.post(`/mail/${id}/transition`, body)
    },
    onSuccess: async () => {
      const id = document?.id
      if (!id) return
      await queryClient.invalidateQueries({ queryKey: ['mail-documents'] })
      await queryClient.invalidateQueries({ queryKey: ['mail-available-actions', id] })
      onMailChanged?.()
      const r = await api.get(`/mail/${id}`)
      setFreshDoc(r.data)
    },
  })
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [fileType, setFileType] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    if (!open) {
      setDeleteConfirmOpen(false)
      setRequestOpen(false)
      setRequestReason('')
      setActionError(null)
      setActionLoading(false)
    }
  }, [open])

  useEffect(() => {
    // Cleanup previous blob URL when document or tab changes
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current)
      blobUrlRef.current = null
    }
    setFileUrl(null)
    setFileType(null)
    setError(null)

    if (open && displayDoc && tab === 1) {
      // Fetch the file with authentication and create a blob URL
      setLoading(true)
      setError(null)

      api
        .get(`/mail/${displayDoc.id}/file`, {
          responseType: 'blob',
        })
        .then((response) => {
          // IMPORTANT: Utiliser le Content-Type de la réponse HTTP directement
          const contentType = response.headers['content-type'] || response.headers['Content-Type'] || ''
          const fileName = displayDoc.title || displayDoc.file_name || ''
          
          // Determine file type from Content-Type for display purposes
          let detectedType = 'unknown'
          
          if (contentType.includes('application/pdf')) {
            detectedType = 'pdf'
          } else if (contentType.includes('image/')) {
            detectedType = 'image'
          } else if (fileName.toLowerCase().endsWith('.pdf')) {
            detectedType = 'pdf'
          } else if (/\.(jpg|jpeg|png|gif|bmp|tiff|webp)$/i.test(fileName)) {
            detectedType = 'image'
          }
          
          // IMPORTANT: Créer le blob avec le Content-Type de la réponse HTTP
          // Utiliser le Content-Type du serveur, pas celui détecté côté client
          const blob = new Blob([response.data], { 
            type: contentType || 'application/octet-stream'
          })
          
          // Vérifier dans la console (en développement)
          if (import.meta.env.DEV) {
            console.log('Content-Type from server:', contentType)
            console.log('Blob type:', blob.type)
            console.log('Blob size:', blob.size)
            console.log('Detected type for display:', detectedType)
          }
          
          // Debug logs
          if (import.meta.env.DEV) {
            console.log('Document file response:', {
              contentType,
              fileName,
              detectedType,
              blobType: blob.type,
              blobSize: blob.size,
              headers: response.headers,
            })
          }
          
          // Nettoyer l'ancien blob URL avant d'en créer un nouveau
          if (blobUrlRef.current) {
            URL.revokeObjectURL(blobUrlRef.current)
          }
          
          const url = URL.createObjectURL(blob)
          blobUrlRef.current = url
          
          // Verify blob URL
          if (import.meta.env.DEV) {
            console.log('Blob URL created:', url)
            console.log('Blob URL valid:', url.startsWith('blob:'))
          }
          
          setFileUrl(url)
          setFileType(detectedType)
          setLoading(false)
        })
        .catch((err) => {
          console.error('Error loading document:', err)
          console.error('Error details:', {
            status: err.response?.status,
            statusText: err.response?.statusText,
            data: err.response?.data,
            headers: err.response?.headers,
          })
          setError(
            err.response?.data?.detail ||
              err.message ||
              t('mail.viewer.failedToLoad')
          )
          setLoading(false)
        })
    }

    // Cleanup blob URL when component unmounts
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [open, displayDoc?.id, tab, t])

  if (!document) return null

  const canDelete = hasPermission(user, 'mail.delete')
  const canRequestDelete =
    hasPermission(user, 'mail.request_delete') && !displayDoc.has_pending_deletion_request
  const canExecutiveArchive =
    isMasterOrDirector(user?.role) && displayDoc.status !== 'archived'

  const handleExecutiveArchive = async () => {
    if (!window.confirm(t('mail.viewer.executiveArchiveConfirm'))) return
    setActionError(null)
    setActionLoading(true)
    try {
      const r = await api.post(`/mail/${displayDoc.id}/executive-archive`)
      setFreshDoc(r.data)
      await queryClient.invalidateQueries({ queryKey: ['mail-documents'] })
      await queryClient.invalidateQueries({ queryKey: ['mail-available-actions', displayDoc.id] })
      onMailChanged?.()
    } catch (err: any) {
      setActionError(
        err.response?.data?.detail || err.message || t('mail.viewer.executiveArchiveFailed')
      )
    } finally {
      setActionLoading(false)
    }
  }

  const handleDirectDelete = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      await api.delete(`/mail/${displayDoc.id}`)
      setDeleteConfirmOpen(false)
      onMailChanged?.()
      onClose()
    } catch (err: any) {
      setActionError(
        err.response?.data?.detail || err.message || t('mail.viewer.deleteFailed')
      )
    } finally {
      setActionLoading(false)
    }
  }

  const handleSubmitDeletionRequest = async () => {
    setActionError(null)
    setActionLoading(true)
    try {
      await api.post(`/mail/${displayDoc.id}/deletion-request`, {
        reason: requestReason.trim() || null,
      })
      setRequestOpen(false)
      setRequestReason('')
      onMailChanged?.()
      onClose()
    } catch (err: any) {
      setActionError(
        err.response?.data?.detail || err.message || t('mail.viewer.requestDeleteFailed')
      )
    } finally {
      setActionLoading(false)
    }
  }

  const getStatusLabel = (status: string) => {
    const statusMap: Record<string, string> = {
      received: t('mail.statusReceived'),
      in_review: t('mail.statusInTreatment'),
      in_treatment: t('mail.statusInTreatment'),
      indexed: t('mail.statusIndexed'),
      assigned: t('mail.statusAssigned'),
      pending_validation: t('mail.statusPendingValidation'),
      pending_director: t('mail.statusPendingDirector'),
      on_hold: t('mail.statusOnHold'),
      approved: t('mail.statusApproved'),
      closed: t('mail.statusClosed'),
      rejected: t('mail.statusRejected'),
      archived: t('mail.statusArchived'),
    }
    return statusMap[status] || status
  }

  const getPriorityLabel = (priority: string) => {
    const priorityMap: any = {
      low: t('mail.priorityLow'),
      normal: t('mail.priorityNormal'),
      high: t('mail.priorityHigh'),
      urgent: t('mail.priorityUrgent'),
    }
    return priorityMap[priority] || priority
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth PaperProps={{ sx: { overflow: 'hidden' } }}>
      <ModalSectionHeader>
        <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
          {t('mail.viewDocument')}
        </Typography>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
          {displayDoc.title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('mail.viewer.reference')}: <strong>{displayDoc.reference_number}</strong>
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
          <Chip label={getStatusLabel(displayDoc.status)} size="small" />
          <Chip label={getPriorityLabel(displayDoc.priority)} color="secondary" size="small" />
          {displayDoc.has_pending_deletion_request && (
            <Chip label={t('mail.viewer.pendingDeletionRequest')} color="warning" size="small" />
          )}
        </Box>
      </ModalSectionHeader>
      <DialogContent sx={{ p: 0 }}>
        <ModalSectionBody sx={{ pb: 0 }}>
        {actionError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
          <Tab label={t('mail.viewer.details')} />
          <Tab label={t('mail.viewer.document')} />
          <Tab label={t('mail.viewer.signature')} />
        </Tabs>

        {tab === 0 && (
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('mail.viewer.reference')}: {displayDoc.reference_number}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              {displayDoc.description}
            </Typography>
            {availableActions.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t('mail.viewer.workflowActions')}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {availableActions.map((a) => (
                    <Button
                      key={a.action_key}
                      size="small"
                      variant="outlined"
                      disabled={transitionMutation.isPending}
                      onClick={() => {
                        setActionError(null)
                        if (a.requires_assignee) {
                          setPendingAction(a)
                          setAssigneeId('')
                          setRoutingDepartment(
                            a.action_key === 'assign' && displayDoc.current_department
                              ? String(displayDoc.current_department)
                              : ''
                          )
                          setAssignOpen(true)
                        } else {
                          transitionMutation.mutate({
                            action_key: a.action_key,
                            notes: transitionNotes.trim() || null,
                          })
                        }
                      }}
                    >
                      {a.label}
                    </Button>
                  ))}
                </Box>
                <TextField
                  label={t('mail.viewer.transitionNotes')}
                  value={transitionNotes}
                  onChange={(e) => setTransitionNotes(e.target.value)}
                  size="small"
                  fullWidth
                  sx={{ mt: 1.5 }}
                  multiline
                  minRows={1}
                />
                {transitionMutation.isError && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    {(transitionMutation.error as any)?.response?.data?.detail ||
                      t('mail.viewer.transitionFailed')}
                  </Alert>
                )}
              </Box>
            )}
            {displayDoc.ocr_keywords && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">
                  {t('mail.viewer.detectedKeywords')}:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                  {displayDoc.ocr_keywords.map((keyword: string) => (
                    <Chip key={keyword} label={keyword} size="small" />
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        )}

        {tab === 1 && (
          <Box>
            {loading ? (
              <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight="600px"
                flexDirection="column"
                gap={2}
              >
                <CircularProgress />
                <Typography>
                  {t('mail.viewer.loadingDocument')}
                </Typography>
              </Box>
            ) : error ? (
              <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight="600px"
              >
                <Alert severity="error" sx={{ maxWidth: '80%' }}>
                  {error}
                </Alert>
              </Box>
            ) : fileUrl ? (
              <Box
                sx={{
                  width: '100%',
                  minHeight: '600px',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  bgcolor: 'action.hover',
                  overflow: 'auto',
                }}
              >
                {fileType === 'pdf' ? (
                  <Box
                    component="embed"
                    src={`${fileUrl}#toolbar=1`}
                    type="application/pdf"
                    sx={{
                      width: '100%',
                      height: '600px',
                      border: 'none',
                    }}
                    title="PDF preview"
                    onError={(e: any) => {
                      console.error('Embed error:', e)
                      console.error('Blob URL:', fileUrl)
                      // Vérifier si le blob est valide
                      if (fileUrl) {
                        fetch(fileUrl)
                          .then((res) => res.blob())
                          .then((blob) => {
                            console.log('Fetched blob type:', blob.type)
                            console.log('Fetched blob size:', blob.size)
                          })
                          .catch((fetchErr) => {
                            console.error('Fetch blob error:', fetchErr)
                          })
                      }
                    }}
                  />
                ) : fileType === 'image' && fileUrl ? (
                  <ImageViewer
                    src={fileUrl}
                    alt={displayDoc.title || 'Document preview'}
                  />
                ) : (
                  <iframe
                    src={fileUrl || undefined}
                    style={{
                      width: '100%',
                      height: '600px',
                      border: 'none',
                    }}
                    title="Document preview"
                    onError={(e: any) => {
                      console.error('Iframe error:', e)
                      console.error('Blob URL:', fileUrl)
                    }}
                  />
                )}
              </Box>
            ) : (
              <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight="600px"
              >
                <Typography color="error">
                  {t('mail.viewer.failedToLoad')}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {tab === 2 && <SignaturePad documentId={displayDoc.id} />}
        </ModalSectionBody>
      </DialogContent>
      <DialogActions sx={modalDialogFooterSx}>
        {canExecutiveArchive && (
          <Button
            color="secondary"
            variant="outlined"
            disabled={actionLoading}
            onClick={() => void handleExecutiveArchive()}
          >
            {t('mail.viewer.executiveArchive')}
          </Button>
        )}
        {canDelete && (
          <Button color="error" onClick={() => setDeleteConfirmOpen(true)}>
            {t('common.delete')}
          </Button>
        )}
        {canRequestDelete && (
          <Button color="warning" variant="outlined" onClick={() => setRequestOpen(true)}>
            {t('mail.viewer.requestDeletion')}
          </Button>
        )}
        <Button onClick={onClose}>{t('common.close')}</Button>
      </DialogActions>

      <Dialog open={deleteConfirmOpen} onClose={() => !actionLoading && setDeleteConfirmOpen(false)}>
        <DialogTitle>{t('mail.viewer.confirmDeleteTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2">{t('mail.viewer.confirmDeleteBody')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)} disabled={actionLoading}>
            {t('common.cancel')}
          </Button>
          <Button color="error" variant="contained" onClick={handleDirectDelete} disabled={actionLoading}>
            {t('common.delete')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={requestOpen} onClose={() => !actionLoading && setRequestOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('mail.viewer.requestDeletionTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {t('mail.viewer.requestDeletionHint')}
          </Typography>
          <TextField
            label={t('mail.viewer.requestDeletionReason')}
            value={requestReason}
            onChange={(e) => setRequestReason(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            disabled={actionLoading}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRequestOpen(false)} disabled={actionLoading}>
            {t('common.cancel')}
          </Button>
          <Button variant="contained" onClick={handleSubmitDeletionRequest} disabled={actionLoading}>
            {t('common.submit')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={assignOpen} onClose={() => !transitionMutation.isPending && setAssignOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {pendingAction?.action_key === 'assign'
            ? t('mail.viewer.assignForRouting')
            : t('mail.viewer.assignForTransition')}
        </DialogTitle>
        <DialogContent>
          {pendingAction?.action_key === 'assign' && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 1 }}>
                {t('mail.viewer.routingServiceHint')}
              </Typography>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel id="mail-routing-label">{t('mail.viewer.routingService')}</InputLabel>
                <Select
                  labelId="mail-routing-label"
                  label={t('mail.viewer.routingService')}
                  value={routingDepartment}
                  onChange={(e) => setRoutingDepartment(e.target.value as string)}
                >
                  <MenuItem value="">
                    <em>{t('mail.viewer.routingServicePlaceholder')}</em>
                  </MenuItem>
                  {ROUTING_SERVICE_IDS.map((id) => (
                    <MenuItem key={id} value={id}>
                      {t(ROUTING_I18N[id])}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel id="mail-assignee-label">{t('mail.viewer.assignee')}</InputLabel>
            <Select
              labelId="mail-assignee-label"
              label={t('mail.viewer.assignee')}
              value={assigneeId}
              onChange={(e) => setAssigneeId(e.target.value as string)}
            >
              {userOptions.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {u.full_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAssignOpen(false)} disabled={transitionMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            disabled={
              transitionMutation.isPending ||
              !assigneeId ||
              !pendingAction ||
              (pendingAction.action_key === 'assign' && !routingDepartment)
            }
            onClick={() => {
              if (!pendingAction || !assigneeId) return
              const dept =
                pendingAction.action_key === 'assign' && routingDepartment
                  ? routingDepartment
                  : null
              transitionMutation.mutate(
                {
                  action_key: pendingAction.action_key,
                  assigned_to_id: assigneeId,
                  notes: transitionNotes.trim() || null,
                  ...(dept ? { current_department: dept } : {}),
                },
                {
                  onSettled: () => {
                    setAssignOpen(false)
                    setPendingAction(null)
                  },
                }
              )
            }}
          >
            {t('common.submit')}
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  )
}
