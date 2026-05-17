import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tableContainerScrollSx } from '../theme/tableScroll'
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
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import { useDateFormat } from '../hooks/useDateFormat'
import api from '../services/api'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

type DeletionRequestRow = {
  id: string
  target_type: string
  target_id: string
  reason: string | null
  status: string
  created_at: string
}

type TabFilter = 'pending' | 'approved' | 'rejected' | 'all'

export default function DeletionRequests() {
  const { t } = useTranslation()
  const { formatDateTime } = useDateFormat()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<TabFilter>('pending')
  const [resolveOpen, setResolveOpen] = useState(false)
  const [resolveMode, setResolveMode] = useState<'approve' | 'reject'>('approve')
  const [activeRow, setActiveRow] = useState<DeletionRequestRow | null>(null)
  const [notes, setNotes] = useState('')

  const statusParam = tab === 'all' ? 'all' : tab

  const { data: rows, isLoading, error } = useQuery({
    queryKey: ['deletion-requests', statusParam],
    queryFn: async () => {
      const res = await api.get<DeletionRequestRow[]>('/deletion-requests/', {
        params: { status: statusParam },
      })
      return res.data || []
    },
  })

  const resolveMutation = useMutation({
    mutationFn: async ({
      id,
      mode,
      resolution_notes,
    }: {
      id: string
      mode: 'approve' | 'reject'
      resolution_notes: string | null
    }) => {
      const path =
        mode === 'approve'
          ? `/deletion-requests/${id}/approve`
          : `/deletion-requests/${id}/reject`
      return api.post(path, { resolution_notes })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deletion-requests'] })
      queryClient.invalidateQueries({ queryKey: ['mail-documents'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-list'] })
      queryClient.invalidateQueries({ queryKey: ['reception-appointments'] })
      setResolveOpen(false)
      setActiveRow(null)
      setNotes('')
    },
  })

  const openResolve = (row: DeletionRequestRow, mode: 'approve' | 'reject') => {
    setActiveRow(row)
    setResolveMode(mode)
    setNotes('')
    setResolveOpen(true)
  }

  const typeLabel = (targetType: string) => {
    if (targetType === 'mail_document') return t('deletionRequests.typeMail')
    if (targetType === 'appointment') return t('deletionRequests.typeAppointment')
    return targetType
  }

  const deletionExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'created_at', header: t('deletionRequests.colDate') },
      { key: 'target_type', header: t('deletionRequests.colType') },
      { key: 'target_id', header: t('deletionRequests.colTarget') },
      { key: 'reason', header: t('deletionRequests.colReason') },
      { key: 'status', header: t('deletionRequests.colStatus') },
    ],
    [t]
  )

  const deletionExportRows = useMemo(
    () =>
      (rows ?? []).map((row) => ({
        created_at: formatDateTime(row.created_at),
        target_type: typeLabel(row.target_type),
        target_id: row.target_id,
        reason: row.reason || '—',
        status: row.status,
      })),
    [rows, formatDateTime, t]
  )

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
        {t('deletionRequests.title')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('deletionRequests.subtitle')}
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="pending" label={t('deletionRequests.tabPending')} />
        <Tab value="approved" label={t('deletionRequests.tabApproved')} />
        <Tab value="rejected" label={t('deletionRequests.tabRejected')} />
        <Tab value="all" label={t('deletionRequests.tabAll')} />
      </Tabs>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error instanceof Error ? error.message : t('deletionRequests.loadFailed')}
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
        <TableExportButton
          filenameBase={`deletion-requests-${tab}`}
          sheetName={t('deletionRequests.title')}
          columns={deletionExportColumns}
          rows={deletionExportRows}
          disabled={isLoading}
        />
      </Box>

      <TableContainer component={Paper} sx={{ ...tableContainerScrollSx, borderRadius: 2 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>{t('deletionRequests.colDate')}</TableCell>
              <TableCell>{t('deletionRequests.colType')}</TableCell>
              <TableCell>{t('deletionRequests.colTarget')}</TableCell>
              <TableCell>{t('deletionRequests.colReason')}</TableCell>
              <TableCell>{t('deletionRequests.colStatus')}</TableCell>
              <TableCell>{t('common.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                  <CircularProgress size={32} />
                </TableCell>
              </TableRow>
            ) : !rows?.length ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">{t('deletionRequests.empty')}</Typography>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>{formatDateTime(row.created_at)}</TableCell>
                  <TableCell>{typeLabel(row.target_type)}</TableCell>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                    {row.target_id}
                  </TableCell>
                  <TableCell>{row.reason || '—'}</TableCell>
                  <TableCell>{row.status}</TableCell>
                  <TableCell>
                    {row.status === 'pending' ? (
                      <Box display="flex" gap={1} flexWrap="wrap">
                        <Button size="small" color="success" onClick={() => openResolve(row, 'approve')}>
                          {t('deletionRequests.approve')}
                        </Button>
                        <Button size="small" color="error" onClick={() => openResolve(row, 'reject')}>
                          {t('deletionRequests.reject')}
                        </Button>
                      </Box>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={resolveOpen} onClose={() => !resolveMutation.isPending && setResolveOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>
          {resolveMode === 'approve'
            ? t('deletionRequests.approveTitle')
            : t('deletionRequests.rejectTitle')}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {resolveMode === 'approve' ? t('deletionRequests.approveHint') : t('deletionRequests.rejectHint')}
          </Typography>
          <TextField
            label={t('deletionRequests.resolveNotes')}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            disabled={resolveMutation.isPending}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResolveOpen(false)} disabled={resolveMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            color={resolveMode === 'approve' ? 'success' : 'error'}
            disabled={resolveMutation.isPending || !activeRow}
            onClick={() =>
              activeRow &&
              resolveMutation.mutate({
                id: activeRow.id,
                mode: resolveMode,
                resolution_notes: notes.trim() || null,
              })
            }
          >
            {resolveMode === 'approve' ? t('deletionRequests.approve') : t('deletionRequests.reject')}
          </Button>
        </DialogActions>
      </Dialog>

      {resolveMutation.isError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {(resolveMutation.error as any)?.response?.data?.detail ||
            t('deletionRequests.actionFailed')}
        </Alert>
      )}
    </Box>
  )
}
