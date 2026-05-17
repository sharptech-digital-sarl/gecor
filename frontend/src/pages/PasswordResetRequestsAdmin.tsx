import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tableContainerScrollSx } from '../theme/tableScroll'
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Chip,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Stack,
  Radio,
  RadioGroup,
  FormLabel,
  FormControlLabel,
  Checkbox,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import PasswordField from '../components/PasswordField'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

type Row = {
  id: string
  email_requested: string
  user_id: string | null
  requester_username: string | null
  requester_full_name: string | null
  requester_message: string | null
  status: string
  created_at: string
  last_master_reminder_at: string | null
  resolved_at: string | null
  resolution_note: string | null
  password_reset_at: string | null
  password_reset_mode: string | null
  password_reset_must_change: boolean | null
}

export default function PasswordResetRequestsAdmin() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [resolveTarget, setResolveTarget] = useState<Row | null>(null)
  const [resolveAction, setResolveAction] = useState<'completed' | 'rejected'>('completed')
  const [resolveNote, setResolveNote] = useState('')
  const [resetTarget, setResetTarget] = useState<Row | null>(null)
  const [resetMode, setResetMode] = useState<'policy' | 'custom'>('policy')
  const [resetCustomPassword, setResetCustomPassword] = useState('')
  const [resetMustChange, setResetMustChange] = useState(true)
  const [resetPwdShown, setResetPwdShown] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['password-reset-requests', statusFilter],
    queryFn: async () => {
      const { data: rows } = await api.get<Row[]>('/users/password-reset-requests', {
        params: statusFilter === 'all' ? undefined : { status_filter: statusFilter },
      })
      return rows
    },
  })

  const resolveMutation = useMutation({
    mutationFn: async ({
      id,
      action,
      note,
    }: {
      id: string
      action: 'completed' | 'rejected'
      note?: string
    }) => {
      await api.post(`/users/password-reset-requests/${id}/resolve`, { action, note: note || undefined })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['password-reset-requests'] })
      setResolveTarget(null)
      setResolveNote('')
    },
  })

  const resetPwdMutation = useMutation({
    mutationFn: async (payload: {
      id: string
      mode: 'policy' | 'custom'
      new_password?: string
      must_change_on_next_login: boolean
    }) => {
      const { data: out } = await api.post<{ message: string; temporary_password?: string | null }>(
        `/users/password-reset-requests/${payload.id}/reset-password`,
        {
          mode: payload.mode,
          new_password: payload.mode === 'custom' ? payload.new_password : undefined,
          must_change_on_next_login: payload.must_change_on_next_login,
        }
      )
      return out
    },
    onSuccess: (out) => {
      queryClient.invalidateQueries({ queryKey: ['password-reset-requests'] })
      setResetPwdShown(out.temporary_password || null)
      if (!out.temporary_password) {
        setResetTarget(null)
        setResetCustomPassword('')
      }
    },
  })

  const openResolve = (row: Row, action: 'completed' | 'rejected') => {
    setResolveTarget(row)
    setResolveAction(action)
    setResolveNote('')
  }

  const openReset = (row: Row) => {
    setResetTarget(row)
    setResetMode('policy')
    setResetCustomPassword('')
    setResetMustChange(true)
    setResetPwdShown(null)
  }

  const closeResetDialog = () => {
    if (resetPwdMutation.isPending) return
    setResetTarget(null)
    setResetPwdShown(null)
    setResetCustomPassword('')
  }

  const statusChip = (s: string) => {
    const color = s === 'pending' ? 'warning' : s === 'completed' ? 'success' : 'default'
    return <Chip size="small" label={t(`passwordResetRequests.status.${s}`, { defaultValue: s })} color={color} />
  }

  const modeLabel = useCallback((m: string | null) => {
    if (!m) return '—'
    if (m === 'policy') return t('passwordResetRequests.modePolicy')
    if (m === 'custom') return t('passwordResetRequests.modeCustom')
    return m
  }, [t])

  const pwdResetExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'created_at', header: t('passwordResetRequests.colCreated') },
      { key: 'email', header: t('usersAdmin.email') },
      { key: 'account', header: t('passwordResetRequests.colAccount') },
      { key: 'message', header: t('passwordResetRequests.colMessage') },
      { key: 'status', header: t('passwordResetRequests.colStatus') },
      { key: 'password_reset_at', header: t('passwordResetRequests.colPasswordReset') },
      { key: 'reset_mode', header: t('passwordResetRequests.colResetMode') },
      { key: 'last_reminder', header: t('passwordResetRequests.colLastReminder') },
      { key: 'resolution', header: t('passwordResetRequests.colResolutionExport') },
    ],
    [t]
  )

  const pwdResetExportRows = useMemo(
    () =>
      (data ?? []).map((row) => {
        const resolutionParts: string[] = []
        if (row.status !== 'pending') {
          resolutionParts.push(row.resolution_note || '—')
          if (row.password_reset_must_change != null) {
            resolutionParts.push(
              row.password_reset_must_change
                ? t('passwordResetRequests.mustChangeYes')
                : t('passwordResetRequests.mustChangeNo')
            )
          }
        }
        return {
          created_at: new Date(row.created_at).toLocaleString(),
          email: row.email_requested,
          account:
            row.requester_full_name || row.requester_username
              ? `${row.requester_full_name || ''} (${row.requester_username || '—'})`.trim()
              : '—',
          message: row.requester_message || '—',
          status: t(`passwordResetRequests.status.${row.status}`, { defaultValue: row.status }),
          password_reset_at: row.password_reset_at ? new Date(row.password_reset_at).toLocaleString() : '—',
          reset_mode: modeLabel(row.password_reset_mode),
          last_reminder: row.last_master_reminder_at
            ? new Date(row.last_master_reminder_at).toLocaleString()
            : '—',
          resolution: row.status === 'pending' ? '—' : resolutionParts.join(' · '),
        }
      }),
    [data, t, modeLabel]
  )

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        {t('passwordResetRequests.title')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('passwordResetRequests.subtitle')}
      </Typography>

      <Paper sx={{ p: 2, mb: 2, borderRadius: 2 }}>
        <FormControl sx={{ minWidth: 220 }}>
          <InputLabel>{t('passwordResetRequests.filterStatus')}</InputLabel>
          <Select
            label={t('passwordResetRequests.filterStatus')}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <MenuItem value="pending">{t('passwordResetRequests.status.pending')}</MenuItem>
            <MenuItem value="completed">{t('passwordResetRequests.status.completed')}</MenuItem>
            <MenuItem value="rejected">{t('passwordResetRequests.status.rejected')}</MenuItem>
            <MenuItem value="all">{t('passwordResetRequests.filterAll')}</MenuItem>
          </Select>
        </FormControl>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {t('passwordResetRequests.loadError')}
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
        <TableExportButton
          filenameBase={`password-reset-requests-${statusFilter}`}
          sheetName={t('passwordResetRequests.title')}
          columns={pwdResetExportColumns}
          rows={pwdResetExportRows}
          disabled={isLoading}
        />
      </Box>

      <TableContainer component={Paper} sx={{ ...tableContainerScrollSx, borderRadius: 2 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>{t('passwordResetRequests.colCreated')}</TableCell>
              <TableCell>{t('usersAdmin.email')}</TableCell>
              <TableCell>{t('passwordResetRequests.colAccount')}</TableCell>
              <TableCell>{t('passwordResetRequests.colMessage')}</TableCell>
              <TableCell>{t('passwordResetRequests.colStatus')}</TableCell>
              <TableCell>{t('passwordResetRequests.colPasswordReset')}</TableCell>
              <TableCell>{t('passwordResetRequests.colResetMode')}</TableCell>
              <TableCell>{t('passwordResetRequests.colLastReminder')}</TableCell>
              <TableCell align="right">{t('common.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                  <CircularProgress size={28} />
                </TableCell>
              </TableRow>
            ) : !data?.length ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Typography variant="body2" color="text.secondary">
                    {t('passwordResetRequests.empty')}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              data.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                  <TableCell>{row.email_requested}</TableCell>
                  <TableCell>
                    {row.requester_full_name || row.requester_username
                      ? `${row.requester_full_name || ''} (${row.requester_username || '—'})`.trim()
                      : '—'}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 180, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {row.requester_message || '—'}
                  </TableCell>
                  <TableCell>{statusChip(row.status)}</TableCell>
                  <TableCell>
                    {row.password_reset_at ? new Date(row.password_reset_at).toLocaleString() : '—'}
                  </TableCell>
                  <TableCell>{modeLabel(row.password_reset_mode)}</TableCell>
                  <TableCell>
                    {row.last_master_reminder_at
                      ? new Date(row.last_master_reminder_at).toLocaleString()
                      : '—'}
                  </TableCell>
                  <TableCell align="right">
                    {row.status === 'pending' ? (
                      <Stack direction="row" spacing={0.5} justifyContent="flex-end" flexWrap="wrap" useFlexGap>
                        {row.user_id ? (
                          <Button size="small" variant="contained" color="primary" onClick={() => openReset(row)}>
                            {t('passwordResetRequests.resetPasswordAction')}
                          </Button>
                        ) : (
                          <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 140 }}>
                            {t('passwordResetRequests.resetPasswordNoUser')}
                          </Typography>
                        )}
                        <Button size="small" variant="outlined" color="success" onClick={() => openResolve(row, 'completed')}>
                          {t('passwordResetRequests.markCompleted')}
                        </Button>
                        <Button size="small" variant="outlined" color="inherit" onClick={() => openResolve(row, 'rejected')}>
                          {t('passwordResetRequests.markRejected')}
                        </Button>
                      </Stack>
                    ) : (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ maxWidth: 200 }}>
                        {row.resolution_note || '—'}
                        {row.password_reset_must_change != null && (
                          <span>
                            {' '}
                            · {row.password_reset_must_change ? t('passwordResetRequests.mustChangeYes') : t('passwordResetRequests.mustChangeNo')}
                          </span>
                        )}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog
        open={Boolean(resolveTarget)}
        onClose={() => !resolveMutation.isPending && setResolveTarget(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {resolveAction === 'completed'
            ? t('passwordResetRequests.dialogCompleteTitle')
            : t('passwordResetRequests.dialogRejectTitle')}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {resolveTarget?.email_requested}
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={2}
            label={t('passwordResetRequests.noteOptional')}
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
            disabled={resolveMutation.isPending}
          />
          {resolveMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {t('passwordResetRequests.resolveError')}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResolveTarget(null)} disabled={resolveMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            color={resolveAction === 'completed' ? 'success' : 'inherit'}
            disabled={resolveMutation.isPending || !resolveTarget}
            onClick={() =>
              resolveTarget &&
              resolveMutation.mutate({
                id: resolveTarget.id,
                action: resolveAction,
                note: resolveNote.trim() || undefined,
              })
            }
          >
            {resolveMutation.isPending ? t('common.loading') : t('common.confirm')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(resetTarget)} onClose={closeResetDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{t('passwordResetRequests.resetPasswordDialogTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {resetTarget?.email_requested}
          </Typography>
          {resetPwdShown ? (
            <Alert severity="success" sx={{ mb: 1 }}>
              <Typography variant="body2">{t('passwordResetRequests.resetPasswordSuccess')}</Typography>
              <Typography variant="body2" sx={{ mt: 1, fontFamily: 'monospace' }}>
                {t('usersAdmin.resetPasswordTemporaryLabel')}: {resetPwdShown}
              </Typography>
            </Alert>
          ) : (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <FormLabel>{t('usersAdmin.resetPasswordModeLabel')}</FormLabel>
              <RadioGroup
                value={resetMode}
                onChange={(e) => setResetMode(e.target.value as 'policy' | 'custom')}
              >
                <FormControlLabel
                  value="policy"
                  control={<Radio />}
                  label={t('passwordResetRequests.resetPasswordPolicyEnv')}
                />
                <FormControlLabel
                  value="custom"
                  control={<Radio />}
                  label={t('passwordResetRequests.resetPasswordCustom')}
                />
              </RadioGroup>
              {resetMode === 'custom' && (
                <PasswordField
                  label={t('auth.password')}
                  value={resetCustomPassword}
                  onChange={(e) => setResetCustomPassword(e.target.value)}
                  fullWidth
                  autoComplete="new-password"
                  helperText={t('usersAdmin.resetPasswordCustomHint')}
                  showStrengthMeter
                />
              )}
              <FormControlLabel
                control={
                  <Checkbox checked={resetMustChange} onChange={(e) => setResetMustChange(e.target.checked)} />
                }
                label={t('passwordResetRequests.resetPasswordMustChange')}
              />
              {resetPwdMutation.isError && (
                <Alert severity="error">
                  {(resetPwdMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                    t('usersAdmin.resetPasswordError')}
                </Alert>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeResetDialog} disabled={resetPwdMutation.isPending}>
            {resetPwdShown ? t('common.close') : t('common.cancel')}
          </Button>
          {!resetPwdShown && resetTarget && (
            <Button
              variant="contained"
              disabled={
                resetPwdMutation.isPending ||
                (resetMode === 'custom' && resetCustomPassword.length < 8)
              }
              onClick={() =>
                resetPwdMutation.mutate({
                  id: resetTarget.id,
                  mode: resetMode,
                  new_password: resetMode === 'custom' ? resetCustomPassword : undefined,
                  must_change_on_next_login: resetMustChange,
                })
              }
            >
              {resetPwdMutation.isPending ? t('common.loading') : t('passwordResetRequests.resetPasswordSubmit')}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  )
}
