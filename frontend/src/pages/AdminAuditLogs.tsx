import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { tableContainerScrollSx } from '../theme/tableScroll'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Autocomplete,
  Chip,
  TableSortLabel,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { useTableSort } from '../hooks/useTableSort'

type AuditRow = {
  id: string
  timestamp: string
  actor_user_id: string | null
  actor_username?: string | null
  actor_email?: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
}

type FilterOptions = {
  actions: string[]
  resource_types: string[]
}

export default function AdminAuditLogs() {
  const { t } = useTranslation()
  const { sortBy, sortDir, toggleSort, sortRows } = useTableSort<
    'timestamp' | 'action' | 'resource' | 'actor' | 'ip'
  >('timestamp', 'desc')
  const [actionsSel, setActionsSel] = useState<string[]>([])
  const [resourceTypesSel, setResourceTypesSel] = useState<string[]>([])
  const [search, setSearch] = useState('')
  /** Valeurs effectivement envoyées à l’API (mise à jour au clic sur Appliquer). */
  const [applied, setApplied] = useState<{
    actions: string[]
    resourceTypes: string[]
    search: string
  }>({ actions: [], resourceTypes: [], search: '' })

  const { data: filterOptions } = useQuery({
    queryKey: ['admin-audit-filter-options'],
    queryFn: async () => {
      const { data } = await api.get<FilterOptions>('/admin/audit-logs/filter-options')
      return data
    },
  })

  const { data, isLoading } = useQuery({
    queryKey: ['admin-audit', applied.actions, applied.resourceTypes, applied.search],
    queryFn: async () => {
      const p = new URLSearchParams()
      p.set('limit', '150')
      applied.actions.forEach((a) => p.append('action', a))
      applied.resourceTypes.forEach((r) => p.append('resource_type', r))
      if (applied.search.trim()) p.set('search', applied.search.trim())
      const qs = p.toString()
      const { data: rows } = await api.get<AuditRow[]>(`/admin/audit-logs?${qs}`)
      return rows
    },
  })

  const applyFilters = () => {
    setApplied({
      actions: [...actionsSel],
      resourceTypes: [...resourceTypesSel],
      search: search.trim(),
    })
  }

  const sortedRows = sortRows(data ?? [], (row, key) => {
    switch (key) {
      case 'timestamp':
        return new Date(row.timestamp)
      case 'action':
        return row.action
      case 'resource':
        return `${row.resource_type} ${row.resource_id ?? ''}`
      case 'actor':
        return `${row.actor_username ?? ''} ${row.actor_email ?? ''}`
      case 'ip':
        return row.ip_address ?? ''
      default:
        return ''
    }
  })

  const auditExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'timestamp', header: t('adminAudit.colTime') },
      { key: 'action', header: t('adminAudit.colAction') },
      { key: 'resource', header: t('adminAudit.colResource') },
      { key: 'actor', header: t('adminAudit.colActor') },
      { key: 'ip', header: t('adminAudit.colIp') },
    ],
    [t]
  )

  const auditExportRows = useMemo(
    () =>
      sortedRows.map((row) => ({
        timestamp: new Date(row.timestamp).toLocaleString(),
        action: row.action,
        resource: row.resource_id ? `${row.resource_type} / ${row.resource_id}` : row.resource_type,
        actor: row.actor_username ? `${row.actor_username} (${row.actor_email ?? '—'})` : '—',
        ip: row.ip_address ?? '—',
      })),
    [sortedRows]
  )

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        {t('adminAudit.title')}
      </Typography>
      <Paper sx={{ p: 2, mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Autocomplete
          multiple
          options={filterOptions?.actions ?? []}
          value={actionsSel}
          onChange={(_, v) => setActionsSel(v)}
          disableCloseOnSelect
          sx={{ minWidth: 220, flex: '1 1 200px' }}
          renderInput={(params) => <TextField {...params} label={t('adminAudit.filterAction')} size="small" />}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip {...getTagProps({ index })} key={option} label={option} size="small" />
            ))
          }
        />
        <Autocomplete
          multiple
          options={filterOptions?.resource_types ?? []}
          value={resourceTypesSel}
          onChange={(_, v) => setResourceTypesSel(v)}
          disableCloseOnSelect
          sx={{ minWidth: 220, flex: '1 1 200px' }}
          renderInput={(params) => <TextField {...params} label={t('adminAudit.filterResource')} size="small" />}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip {...getTagProps({ index })} key={option} label={option} size="small" />
            ))
          }
        />
        <TextField
          size="small"
          label={t('adminAudit.filterSearch')}
          placeholder={t('adminAudit.filterSearchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 220, flex: '1 1 240px' }}
        />
        <Button variant="contained" onClick={applyFilters} sx={{ alignSelf: 'center' }}>
          {t('common.apply')}
        </Button>
        <Box sx={{ ml: 'auto', alignSelf: 'center' }}>
          <TableExportButton
            filenameBase="audit-log"
            sheetName={t('adminAudit.title')}
            columns={auditExportColumns}
            rows={auditExportRows}
            disabled={isLoading}
          />
        </Box>
      </Paper>
      <TableContainer component={Paper} sx={tableContainerScrollSx}>
        {isLoading ? (
          <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : (
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === 'timestamp'}
                    direction={sortBy === 'timestamp' ? sortDir : 'asc'}
                    onClick={() => toggleSort('timestamp')}
                  >
                    {t('adminAudit.colTime')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === 'action'}
                    direction={sortBy === 'action' ? sortDir : 'asc'}
                    onClick={() => toggleSort('action')}
                  >
                    {t('adminAudit.colAction')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === 'resource'}
                    direction={sortBy === 'resource' ? sortDir : 'asc'}
                    onClick={() => toggleSort('resource')}
                  >
                    {t('adminAudit.colResource')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === 'actor'}
                    direction={sortBy === 'actor' ? sortDir : 'asc'}
                    onClick={() => toggleSort('actor')}
                  >
                    {t('adminAudit.colActor')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === 'ip'}
                    direction={sortBy === 'ip' ? sortDir : 'asc'}
                    onClick={() => toggleSort('ip')}
                  >
                    {t('adminAudit.colIp')}
                  </TableSortLabel>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedRows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.timestamp).toLocaleString()}</TableCell>
                  <TableCell>{row.action}</TableCell>
                  <TableCell>
                    {row.resource_type}
                    {row.resource_id ? ` / ${row.resource_id}` : ''}
                  </TableCell>
                  <TableCell>{row.actor_username ? `${row.actor_username} (${row.actor_email ?? '—'})` : '—'}</TableCell>
                  <TableCell>{row.ip_address ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </TableContainer>
    </Box>
  )
}
