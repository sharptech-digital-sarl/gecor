import { useQuery } from '@tanstack/react-query'
import { tableContainerScrollSx } from '../theme/tableScroll'
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
  CircularProgress,
  Tabs,
  Tab,
  TableSortLabel,
} from '@mui/material'
import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { useTableSort } from '../hooks/useTableSort'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

type InApp = {
  id: string
  user_id?: string
  user_username?: string | null
  user_email?: string | null
  title: string
  body: string
  read_at: string | null
  created_at: string
}

type EmailN = {
  id: string
  notification_type: string
  status: string
  subject: string | null
  message: string
  recipient_email: string | null
  recipient_id?: string | null
  recipient_username?: string | null
  created_at: string
}

type Overview = {
  in_app: InApp[]
  email_notifications: EmailN[]
}

export default function AdminSystemNotifications() {
  const { t } = useTranslation()
  const [tab, setTab] = useState(0)
  const inAppSort = useTableSort<'time' | 'user' | 'title' | 'body' | 'read'>('time', 'desc')
  const emailSort = useTableSort<'time' | 'status' | 'recipient' | 'subject'>('time', 'desc')

  const { data, isLoading } = useQuery({
    queryKey: ['admin-notifications-overview'],
    queryFn: async () => {
      const { data: d } = await api.get<Overview>('/admin/notifications')
      return d
    },
  })

  const sortedInApp = inAppSort.sortRows(data?.in_app ?? [], (row, key) => {
    switch (key) {
      case 'time':
        return new Date(row.created_at)
      case 'user':
        return `${row.user_username ?? ''} ${row.user_email ?? ''}`
      case 'title':
        return row.title
      case 'body':
        return row.body
      case 'read':
        return row.read_at ? 1 : 0
      default:
        return ''
    }
  })

  const sortedEmail = emailSort.sortRows(data?.email_notifications ?? [], (row, key) => {
    switch (key) {
      case 'time':
        return new Date(row.created_at)
      case 'status':
        return row.status
      case 'recipient':
        return `${row.recipient_username ?? ''} ${row.recipient_email ?? ''}`
      case 'subject':
        return row.subject ?? row.message.slice(0, 80)
      default:
        return ''
    }
  })

  const inAppExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'time', header: t('adminNotifications.colTime') },
      { key: 'user', header: t('adminNotifications.colUser') },
      { key: 'title', header: t('adminNotifications.colTitle') },
      { key: 'body', header: t('adminNotifications.colBody') },
      { key: 'read', header: t('adminNotifications.colRead') },
    ],
    [t]
  )

  const inAppExportRows = useMemo(
    () =>
      sortedInApp.map((row) => ({
        time: new Date(row.created_at).toLocaleString(),
        user: row.user_username ? `${row.user_username} (${row.user_email ?? '—'})` : '—',
        title: row.title,
        body: row.body,
        read: row.read_at ? t('common.yes') : t('common.no'),
      })),
    [sortedInApp, t]
  )

  const emailExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'time', header: t('adminNotifications.colTime') },
      { key: 'status', header: t('adminNotifications.colStatus') },
      { key: 'recipient', header: t('adminNotifications.colRecipient') },
      { key: 'subject', header: t('adminNotifications.colSubject') },
    ],
    [t]
  )

  const emailExportRows = useMemo(
    () =>
      sortedEmail.map((row) => ({
        time: new Date(row.created_at).toLocaleString(),
        status: row.status,
        recipient: row.recipient_username
          ? `${row.recipient_username} (${row.recipient_email ?? '—'})`
          : row.recipient_email ?? '—',
        subject: row.subject ?? row.message.slice(0, 80),
      })),
    [sortedEmail]
  )

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        {t('adminNotifications.title')}
      </Typography>
      <Paper sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label={t('adminNotifications.tabInApp')} />
          <Tab label={t('adminNotifications.tabEmail')} />
        </Tabs>
      </Paper>
      {isLoading ? (
        <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      ) : tab === 0 ? (
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            <TableExportButton
              filenameBase="notifications-in-app"
              sheetName={t('adminNotifications.tabInApp')}
              columns={inAppExportColumns}
              rows={inAppExportRows}
              disabled={isLoading}
            />
          </Box>
          <TableContainer component={Paper} sx={tableContainerScrollSx}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={inAppSort.sortBy === 'time'}
                    direction={inAppSort.sortBy === 'time' ? inAppSort.sortDir : 'asc'}
                    onClick={() => inAppSort.toggleSort('time')}
                  >
                    {t('adminNotifications.colTime')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={inAppSort.sortBy === 'user'}
                    direction={inAppSort.sortBy === 'user' ? inAppSort.sortDir : 'asc'}
                    onClick={() => inAppSort.toggleSort('user')}
                  >
                    {t('adminNotifications.colUser')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={inAppSort.sortBy === 'title'}
                    direction={inAppSort.sortBy === 'title' ? inAppSort.sortDir : 'asc'}
                    onClick={() => inAppSort.toggleSort('title')}
                  >
                    {t('adminNotifications.colTitle')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={inAppSort.sortBy === 'body'}
                    direction={inAppSort.sortBy === 'body' ? inAppSort.sortDir : 'asc'}
                    onClick={() => inAppSort.toggleSort('body')}
                  >
                    {t('adminNotifications.colBody')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={inAppSort.sortBy === 'read'}
                    direction={inAppSort.sortBy === 'read' ? inAppSort.sortDir : 'asc'}
                    onClick={() => inAppSort.toggleSort('read')}
                  >
                    {t('adminNotifications.colRead')}
                  </TableSortLabel>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedInApp.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                  <TableCell>{row.user_username ? `${row.user_username} (${row.user_email ?? '—'})` : '—'}</TableCell>
                  <TableCell>{row.title}</TableCell>
                  <TableCell sx={{ maxWidth: 280 }}>{row.body}</TableCell>
                  <TableCell>{row.read_at ? t('common.yes') : t('common.no')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        </>
      ) : (
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            <TableExportButton
              filenameBase="notifications-email"
              sheetName={t('adminNotifications.tabEmail')}
              columns={emailExportColumns}
              rows={emailExportRows}
              disabled={isLoading}
            />
          </Box>
          <TableContainer component={Paper} sx={tableContainerScrollSx}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={emailSort.sortBy === 'time'}
                    direction={emailSort.sortBy === 'time' ? emailSort.sortDir : 'asc'}
                    onClick={() => emailSort.toggleSort('time')}
                  >
                    {t('adminNotifications.colTime')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={emailSort.sortBy === 'status'}
                    direction={emailSort.sortBy === 'status' ? emailSort.sortDir : 'asc'}
                    onClick={() => emailSort.toggleSort('status')}
                  >
                    {t('adminNotifications.colStatus')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={emailSort.sortBy === 'recipient'}
                    direction={emailSort.sortBy === 'recipient' ? emailSort.sortDir : 'asc'}
                    onClick={() => emailSort.toggleSort('recipient')}
                  >
                    {t('adminNotifications.colRecipient')}
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={emailSort.sortBy === 'subject'}
                    direction={emailSort.sortBy === 'subject' ? emailSort.sortDir : 'asc'}
                    onClick={() => emailSort.toggleSort('subject')}
                  >
                    {t('adminNotifications.colSubject')}
                  </TableSortLabel>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedEmail.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                  <TableCell>{row.status}</TableCell>
                  <TableCell>{row.recipient_username ? `${row.recipient_username} (${row.recipient_email ?? '—'})` : row.recipient_email ?? '—'}</TableCell>
                  <TableCell>{row.subject ?? row.message.slice(0, 80)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        </>
      )}
    </Box>
  )
}
