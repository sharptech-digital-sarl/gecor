import { useState, useEffect, useRef } from 'react'
import {
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Popover,
  Tooltip,
  Typography,
} from '@mui/material'
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { subscribePushWithApi } from '../utils/webPush'
import { useAuth } from '../hooks/useAuth'
import { useInAppNotificationSounds } from '../hooks/useInAppNotificationSounds'
import { useDocumentVisible } from '../hooks/useDocumentVisible'
import { useNotificationsSSE } from '../hooks/useNotificationsSSE'

type InAppRow = {
  id: string
  title: string
  body: string
  read_at: string | null
  created_at: string
  payload?: Record<string, unknown> | null
}

export default function NotificationBell() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const qc = useQueryClient()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const pushTried = useRef(false)
  const open = Boolean(anchorEl)
  const tabVisible = useDocumentVisible()
  const sseConnected = useNotificationsSSE(Boolean(user?.id))

  /** SSE actif : filet de sécurité allégé (tâches Celery ne passent pas par le hub). Sinon polling court. */
  const refetchIntervalMs = !tabVisible
    ? 90_000
    : sseConnected
      ? 45_000
      : open
        ? 8_000
        : 12_000

  const { data: items = [], error } = useQuery({
    queryKey: ['in-app-notifications', user?.id],
    queryFn: async () => {
      const { data } = await api.get<InAppRow[]>('/notifications', { params: { limit: 40 } })
      return Array.isArray(data) ? data : []
    },
    enabled: Boolean(user?.id),
    refetchInterval: refetchIntervalMs,
    refetchOnWindowFocus: true,
    staleTime: 0,
  })

  useInAppNotificationSounds(items, Boolean(user?.id))

  const unread = items.filter((n) => !n.read_at).length

  const readOne = useMutation({
    mutationFn: async (id: string) => {
      await api.patch(`/notifications/${id}/read`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['in-app-notifications'] }),
  })

  const readAll = useMutation({
    mutationFn: async () => {
      await api.post('/notifications/read-all')
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['in-app-notifications'] }),
  })

  useEffect(() => {
    if (pushTried.current) return
    pushTried.current = true
    void subscribePushWithApi(api).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (open && user?.id) {
      void qc.invalidateQueries({ queryKey: ['in-app-notifications'] })
    }
  }, [open, user?.id, qc])

  const handleBellClick = (e: React.MouseEvent<HTMLElement>) => {
    setAnchorEl((prev) => (prev ? null : e.currentTarget))
  }

  return (
    <>
      <Tooltip title={t('notifications.tooltip')}>
        <IconButton
          color="inherit"
          onClick={handleBellClick}
          aria-label={t('notifications.tooltip')}
          aria-expanded={open}
        >
          <Badge badgeContent={unread} color="error" max={99} invisible={unread === 0}>
            <NotificationsNoneIcon />
          </Badge>
        </IconButton>
      </Tooltip>
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{
          paper: {
            sx: {
              width: 360,
              maxWidth: 'calc(100vw - 24px)',
              maxHeight: 'min(80vh, 520px)',
              display: 'flex',
              flexDirection: 'column',
              mt: 1,
            },
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6" component="span">
            {t('notifications.title')}
          </Typography>
          <Button size="small" onClick={() => readAll.mutate()} disabled={readAll.isPending || unread === 0}>
            {t('notifications.markAllRead')}
          </Button>
        </Box>
        <Divider />
        <Box sx={{ overflow: 'auto', flex: 1 }}>
          <List dense>
            {error ? (
              <ListItemText sx={{ px: 2, py: 2 }} primary={t('notifications.loadError')} />
            ) : items.length === 0 ? (
              <ListItemText sx={{ px: 2, py: 2 }} primary={t('notifications.empty')} />
            ) : (
              items.map((n) => (
                <ListItemButton
                  key={n.id}
                  selected={!n.read_at}
                  alignItems="flex-start"
                  onClick={() => {
                    if (!n.read_at) readOne.mutate(n.id)
                  }}
                >
                  <ListItemText
                    primary={n.title}
                    secondary={
                      <>
                        <Typography component="span" variant="body2" color="text.primary" display="block">
                          {n.body}
                        </Typography>
                        <Typography component="span" variant="caption" color="text.secondary">
                          {new Date(n.created_at).toLocaleString()}
                        </Typography>
                      </>
                    }
                  />
                </ListItemButton>
              ))
            )}
          </List>
        </Box>
      </Popover>
    </>
  )
}
