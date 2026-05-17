import { useMemo, useState, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
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
  IconButton,
  Alert,
  CircularProgress,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TableSortLabel,
  Checkbox,
} from '@mui/material'
import { useTheme, alpha } from '@mui/material/styles'
import {
  Add as AddIcon,
  Visibility as ViewIcon,
  Search as SearchIcon,
  DeleteOutline as DeleteOutlineIcon,
} from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import { useDateFormat } from '../hooks/useDateFormat'
import { tableContainerScrollSx } from '../theme/tableScroll'
import { useTableSort } from '../hooks/useTableSort'
import api from '../services/api'
import DocumentUpload from '../components/mail/DocumentUpload'
import DocumentViewer from '../components/mail/DocumentViewer'
import { useAuth } from '../hooks/useAuth'
import { hasPermission } from '../utils/permissions'
import { isAdminUser } from '../utils/roles'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

type MailSortKey = 'reference_number' | 'title' | 'status' | 'priority' | 'created_at'

export default function MailManagement() {
  const { t } = useTranslation()
  const theme = useTheme()
  const { user } = useAuth()
  const { formatDate, formatTime } = useDateFormat()
  const canCreateMail = hasPermission(user, 'mail.create')
  const canBulkDeleteMail = isAdminUser(user?.role) && hasPermission(user, 'mail.delete')
  const [selectedMailIds, setSelectedMailIds] = useState<string[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)
  const [viewOpen, setViewOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const { sortBy, sortDir, toggleSort, sortRows } = useTableSort<MailSortKey>('created_at', 'desc')
  const queryClient = useQueryClient()

  const { data: documents, isLoading, error } = useQuery({
    queryKey: ['mail-documents'],
    queryFn: async () => {
      try {
        const response = await api.get('/mail/')
        return response.data
      } catch (err: any) {
        throw new Error(err.response?.data?.detail || t('mail.failedToLoad'))
      }
    },
  })

  const mailStatusLabel = (status: string) => {
    const m: Record<string, string> = {
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
    return m[status] || status || '—'
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, 'default' | 'info' | 'success' | 'error' | 'secondary' | 'warning'> = {
      received: 'default',
      in_review: 'info',
      in_treatment: 'info',
      indexed: 'default',
      assigned: 'info',
      pending_validation: 'warning',
      pending_director: 'secondary',
      on_hold: 'warning',
      approved: 'success',
      closed: 'info',
      rejected: 'error',
      archived: 'secondary',
    }
    return colors[status] || 'default'
  }

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, 'default' | 'info' | 'warning' | 'error'> = {
      low: 'default',
      normal: 'info',
      high: 'warning',
      urgent: 'error',
    }
    return colors[priority] || 'default'
  }

  const handleView = (document: any) => {
    setSelectedDocument(document)
    setViewOpen(true)
  }

  const handleUploadClose = () => {
    setUploadOpen(false)
    queryClient.invalidateQueries({ queryKey: ['mail-documents'] })
  }

  const filtered = useMemo(() => {
    if (!documents?.length) return []
    return documents.filter((doc: any) => {
      if (statusFilter && doc.status !== statusFilter) return false
      if (priorityFilter && doc.priority !== priorityFilter) return false
      if (!searchTerm) return true
      const search = searchTerm.toLowerCase()
      return (
        doc.title?.toLowerCase().includes(search) ||
        doc.reference_number?.toLowerCase().includes(search) ||
        doc.description?.toLowerCase().includes(search)
      )
    })
  }, [documents, searchTerm, statusFilter, priorityFilter])

  const sortedDocuments = useMemo(
    () =>
      sortRows(filtered, (row: any, key) => {
        switch (key) {
          case 'reference_number':
            return row.reference_number || ''
          case 'title':
            return row.title || ''
          case 'status':
            return row.status || ''
          case 'priority':
            return row.priority || ''
          case 'created_at':
            return row.created_at ? new Date(row.created_at).getTime() : 0
          default:
            return ''
        }
      }),
    [filtered, sortRows]
  )

  const selectableMailIds = useMemo(
    () => sortedDocuments.map((d: { id: string }) => d.id),
    [sortedDocuments]
  )

  const mailPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'low':
        return t('mail.priorityLow')
      case 'normal':
        return t('mail.priorityNormal')
      case 'high':
        return t('mail.priorityHigh')
      case 'urgent':
        return t('mail.priorityUrgent')
      default:
        return priority || t('mail.priorityNormal')
    }
  }

  const mailExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'reference_number', header: t('mail.reference') },
      { key: 'title', header: t('mail.titleLabel') },
      { key: 'description', header: t('mail.description') },
      { key: 'status', header: t('mail.status') },
      { key: 'priority', header: t('mail.priority') },
      { key: 'created', header: t('mail.created') },
    ],
    [t]
  )

  const mailExportRows = useMemo(
    () =>
      sortedDocuments.map((doc: any) => ({
        reference_number: doc.reference_number || '',
        title: doc.title || '',
        description: doc.description || '',
        status: mailStatusLabel(doc.status),
        priority: doc.has_pending_deletion_request
          ? `${mailPriorityLabel(doc.priority)} · ${t('mail.pendingDeletionBadge')}`
          : mailPriorityLabel(doc.priority),
        created: doc.created_at
          ? `${formatDate(doc.created_at, 'LL')} ${formatTime(doc.created_at)}`
          : '',
      })),
    [sortedDocuments, t, formatDate, formatTime]
  )

  useEffect(() => {
    setSelectedMailIds((prev) => prev.filter((id) => selectableMailIds.includes(id)))
  }, [selectableMailIds])

  const bulkDeleteMailMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const { data } = await api.post<{ deleted_count: number }>('/mail/bulk-delete', { ids })
      return data
    },
    onSuccess: () => {
      setSelectedMailIds([])
      queryClient.invalidateQueries({ queryKey: ['mail-documents'] })
    },
  })

  const toggleMailRow = useCallback((id: string) => {
    setSelectedMailIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }, [])

  const selectAllMailRows = useCallback(() => {
    setSelectedMailIds((prev) =>
      prev.length === selectableMailIds.length ? [] : [...selectableMailIds]
    )
  }, [selectableMailIds])

  const handleBulkDeleteMail = () => {
    if (!selectedMailIds.length) return
    if (!window.confirm(t('mail.bulkDeleteConfirm', { count: selectedMailIds.length }))) return
    bulkDeleteMailMutation.mutate(selectedMailIds)
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
            {t('mail.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {documents ? `${documents.length} ${t('mail.documents')}` : t('mail.loading')}
          </Typography>
        </Box>
        <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
          {canCreateMail && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<AddIcon />}
              onClick={() => setUploadOpen(true)}
              sx={{
                minWidth: 180,
              }}
            >
              {t('mail.uploadDocument')}
            </Button>
          )}
          {canBulkDeleteMail && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteOutlineIcon />}
              disabled={!selectedMailIds.length || bulkDeleteMailMutation.isPending}
              onClick={handleBulkDeleteMail}
            >
              {bulkDeleteMailMutation.isPending
                ? t('common.loading')
                : t('mail.bulkDeleteSelected', { count: selectedMailIds.length })}
            </Button>
          )}
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error instanceof Error ? error.message : t('mail.failedToLoad')}
        </Alert>
      )}

      <Box
        mb={2}
        display="flex"
        flexWrap="wrap"
        gap={2}
        alignItems="center"
        sx={{ maxWidth: '100%' }}
      >
        <TextField
          placeholder={t('mail.searchPlaceholder')}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 220, flex: '1 1 220px' }}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>{t('mail.filterStatus')}</InputLabel>
          <Select
            label={t('mail.filterStatus')}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as string)}
          >
            <MenuItem value="">{t('mail.filterAll')}</MenuItem>
            <MenuItem value="received">{t('mail.statusReceived')}</MenuItem>
            <MenuItem value="indexed">{t('mail.statusIndexed')}</MenuItem>
            <MenuItem value="assigned">{t('mail.statusAssigned')}</MenuItem>
            <MenuItem value="in_treatment">{t('mail.statusInTreatment')}</MenuItem>
            <MenuItem value="pending_director">{t('mail.statusPendingDirector')}</MenuItem>
            <MenuItem value="pending_validation">{t('mail.statusPendingValidation')}</MenuItem>
            <MenuItem value="on_hold">{t('mail.statusOnHold')}</MenuItem>
            <MenuItem value="approved">{t('mail.statusApproved')}</MenuItem>
            <MenuItem value="closed">{t('mail.statusClosed')}</MenuItem>
            <MenuItem value="rejected">{t('mail.statusRejected')}</MenuItem>
            <MenuItem value="archived">{t('mail.statusArchived')}</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>{t('mail.filterPriority')}</InputLabel>
          <Select
            label={t('mail.filterPriority')}
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as string)}
          >
            <MenuItem value="">{t('mail.filterAll')}</MenuItem>
            <MenuItem value="low">{t('mail.priorityLow')}</MenuItem>
            <MenuItem value="normal">{t('mail.priorityNormal')}</MenuItem>
            <MenuItem value="high">{t('mail.priorityHigh')}</MenuItem>
            <MenuItem value="urgent">{t('mail.priorityUrgent')}</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ ml: 'auto', flexShrink: 0 }}>
          <TableExportButton
            filenameBase="mail-documents"
            sheetName={t('mail.title')}
            columns={mailExportColumns}
            rows={mailExportRows}
            disabled={isLoading}
          />
        </Box>
      </Box>

      <TableContainer
        component={Paper}
        sx={{
          ...tableContainerScrollSx,
          borderRadius: 3,
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04)',
          transition: 'all 0.3s ease',
          '&:hover': {
            boxShadow: '0 6px 20px rgba(0, 0, 0, 0.1)',
          },
        }}
      >
        <Table stickyHeader>
          <TableHead>
            <TableRow
              sx={{
                '& .MuiTableCell-head': {
                  fontSize: '0.95rem',
                  letterSpacing: '0.5px',
                },
              }}
            >
              {canBulkDeleteMail && (
                <TableCell padding="checkbox" sx={{ width: 48 }}>
                  <Checkbox
                    size="small"
                    indeterminate={
                      selectedMailIds.length > 0 && selectedMailIds.length < selectableMailIds.length
                    }
                    checked={
                      selectableMailIds.length > 0 && selectedMailIds.length === selectableMailIds.length
                    }
                    onChange={selectAllMailRows}
                    inputProps={{ 'aria-label': t('mail.bulkSelectAllAria') }}
                  />
                </TableCell>
              )}
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'reference_number'}
                  direction={sortBy === 'reference_number' ? sortDir : 'asc'}
                  onClick={() => toggleSort('reference_number')}
                >
                  {t('mail.reference')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'title'}
                  direction={sortBy === 'title' ? sortDir : 'asc'}
                  onClick={() => toggleSort('title')}
                >
                  {t('mail.titleLabel')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'status'}
                  direction={sortBy === 'status' ? sortDir : 'asc'}
                  onClick={() => toggleSort('status')}
                >
                  {t('mail.status')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'priority'}
                  direction={sortBy === 'priority' ? sortDir : 'asc'}
                  onClick={() => toggleSort('priority')}
                >
                  {t('mail.priority')}
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'created_at'}
                  direction={sortBy === 'created_at' ? sortDir : 'asc'}
                  onClick={() => toggleSort('created_at')}
                >
                  {t('mail.created')}
                </TableSortLabel>
              </TableCell>
              <TableCell>{t('common.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={canBulkDeleteMail ? 7 : 6} align="center" sx={{ py: 4 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : !sortedDocuments || sortedDocuments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canBulkDeleteMail ? 7 : 6} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    {searchTerm || statusFilter || priorityFilter
                      ? t('mail.noSearchResults')
                      : t('mail.noDocuments')}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              sortedDocuments.map((doc: any) => (
                <TableRow
                  key={doc.id}
                  hover
                  selected={canBulkDeleteMail && selectedMailIds.includes(doc.id)}
                  sx={[
                    {
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        bgcolor: 'action.hover',
                      },
                    },
                    doc.highlight_destined
                      ? {
                          bgcolor: alpha(
                            theme.palette.warning.main,
                            theme.palette.mode === 'dark' ? 0.14 : 0.1,
                          ),
                          boxShadow: `inset 3px 0 0 ${theme.palette.warning.main}`,
                        }
                      : {},
                  ]}
                >
                  {canBulkDeleteMail && (
                    <TableCell padding="checkbox">
                      <Checkbox
                        size="small"
                        checked={selectedMailIds.includes(doc.id)}
                        onChange={() => toggleMailRow(doc.id)}
                        inputProps={{ 'aria-label': t('mail.bulkSelectRowAria', { ref: doc.reference_number }) }}
                      />
                    </TableCell>
                  )}
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {doc.reference_number || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{doc.title || '-'}</Typography>
                    {doc.description && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        display="block"
                        sx={{ mt: 0.5 }}
                      >
                        {doc.description.length > 50
                          ? `${doc.description.substring(0, 50)}...`
                          : doc.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip label={mailStatusLabel(doc.status)} color={getStatusColor(doc.status)} size="small" />
                  </TableCell>
                  <TableCell>
                    <Box display="flex" flexWrap="wrap" gap={0.5} alignItems="center">
                      <Chip
                        label={
                          doc.priority === 'low'
                            ? t('mail.priorityLow')
                            : doc.priority === 'normal'
                              ? t('mail.priorityNormal')
                              : doc.priority === 'high'
                                ? t('mail.priorityHigh')
                                : doc.priority === 'urgent'
                                  ? t('mail.priorityUrgent')
                                  : doc.priority || 'normal'
                        }
                        color={getPriorityColor(doc.priority)}
                        size="small"
                        variant="outlined"
                      />
                      {doc.has_pending_deletion_request && (
                        <Chip label={t('mail.pendingDeletionBadge')} size="small" color="warning" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatDate(doc.created_at, 'LL')}</Typography>
                    {doc.created_at && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        {formatTime(doc.created_at)}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      color="primary"
                      onClick={() => handleView(doc)}
                      title={t('mail.viewDocument')}
                    >
                      <ViewIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {canCreateMail && <DocumentUpload open={uploadOpen} onClose={handleUploadClose} />}

      <DocumentViewer
        open={viewOpen}
        document={selectedDocument}
        onClose={() => setViewOpen(false)}
        onMailChanged={() => queryClient.invalidateQueries({ queryKey: ['mail-documents'] })}
      />
    </Box>
  )
}
