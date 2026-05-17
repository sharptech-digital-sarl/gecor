import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Typography, Box, Card, CardContent, Skeleton } from '@mui/material'
import {
  Mail as MailIcon,
  CalendarToday as CalendarIcon,
  Warning as WarningIcon,
  Assignment as AssignmentIcon,
  CheckCircle as CheckCircleIcon,
  HourglassEmpty as HourglassEmptyIcon,
  EventAvailable as EventAvailableIcon,
  EventNote as EventNoteIcon,
  TaskAlt as TaskAltIcon,
  PendingActions as PendingActionsIcon,
  PauseCircle as PauseCircleIcon,
} from '@mui/icons-material'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { alpha } from '@mui/material/styles'
import api from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { hasPermission } from '../utils/permissions'

type StatCardConfig = {
  title: string
  value: number
  icon: React.ReactNode
  borderAccent: string
  isLoading: boolean
  path: string
}

function startOfDay(d: Date) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

function endOfDay(d: Date) {
  const x = new Date(d)
  x.setHours(23, 59, 59, 999)
  return x
}

type MailDelaysKpi = {
  to_approved: {
    avg_hours: number | null
    median_hours: number | null
    sample_count: number
  }
  to_archived: {
    avg_hours: number | null
    median_hours: number | null
    sample_count: number
  }
}

type KpiResponse = {
  organization_metrics?: boolean
  mail: {
    by_status: Record<string, number>
    overdue: number
    total: number
    pending_validation?: number
    on_hold?: number
    delays?: MailDelaysKpi
    mine_by_status?: Record<string, number>
    mine_total?: number
    mine_overdue?: number
    mine_pending_validation?: number
    mine_on_hold?: number
  }
  appointments: {
    by_status: Record<string, number>
    total: number
    mine_by_status?: Record<string, number>
    mine_total?: number
  }
  appointment_open_tasks: number
}

export default function Dashboard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const useKpi = hasPermission(user, 'dashboard.kpi')
  const canViewMailDash = hasPermission(user, 'mail.view')
  const canViewAppointmentsDash = hasPermission(user, 'appointments.view')

  const { data: kpi, isLoading: isLoadingKpi, error: kpiError } = useQuery({
    queryKey: ['dashboard-kpi'],
    queryFn: async () => {
      const response = await api.get<KpiResponse>('/dashboard/kpi')
      return response.data
    },
    enabled: !!user && useKpi,
  })

  const showOrgKpi = Boolean(useKpi && kpi?.organization_metrics)

  const { data: mailStats, isLoading: isLoadingMail, error: mailError } = useQuery({
    queryKey: ['mail-stats'],
    queryFn: async () => {
      try {
        const response = await api.get('/mail/', { params: { limit: 1000 } })
        const documents = response.data || []
        return {
          total: documents.length,
          received: documents.filter((d: { status?: string }) => d.status === 'received').length,
          inReview: documents.filter((d: { status?: string }) =>
            ['in_review', 'in_treatment'].includes(d.status || '')
          ).length,
          approved: documents.filter((d: { status?: string }) => d.status === 'approved').length,
          overdue: documents.filter((d: { is_overdue?: boolean }) => d.is_overdue).length,
        }
      } catch (error) {
        console.error('Error fetching mail stats:', error)
        return { total: 0, received: 0, inReview: 0, approved: 0, overdue: 0 }
      }
    },
    enabled: !!user && !useKpi && canViewMailDash,
  })

  const mineBs = kpi?.mail?.mine_by_status || {}
  const mailFromKpi = useKpi && kpi
    ? {
        total: kpi.mail.mine_total ?? 0,
        received: mineBs.received ?? 0,
        inReview: mineBs.in_treatment ?? mineBs.in_review ?? 0,
        approved: mineBs.approved ?? 0,
        overdue: kpi.mail.mine_overdue ?? 0,
      }
    : mailStats

  const isLoadingMailCards = useKpi ? isLoadingKpi : isLoadingMail

  /** Sans vue organisation : statistiques RDV limitées aux rendez-vous de l’utilisateur. */
  const appointmentOrganizerId =
    useKpi && user?.id && !showOrgKpi ? user.id : undefined

  const { data: appointmentStats, isLoading: isLoadingAppointments, error: appointmentError } = useQuery({
    queryKey: ['appointment-stats', appointmentOrganizerId ?? 'default', showOrgKpi],
    enabled: !!user && canViewAppointmentsDash,
    queryFn: async () => {
      try {
        const today = startOfDay(new Date())
        const horizon = new Date(today)
        horizon.setDate(horizon.getDate() + 60)
        horizon.setHours(23, 59, 59, 999)

        const response = await api.get('/appointments/', {
          params: {
            ...(appointmentOrganizerId ? { organizer_id: appointmentOrganizerId } : {}),
            start_date: today.toISOString(),
            end_date: horizon.toISOString(),
            limit: 500,
          },
        })
        const list = (response.data || []) as Array<{ start_time: string; status: string }>
        const todayEnd = endOfDay(today)
        const weekLast = new Date(today)
        weekLast.setDate(weekLast.getDate() + 6)
        const weekEnd = endOfDay(weekLast)

        const inRange = (iso: string, from: Date, to: Date) => {
          const t0 = new Date(iso).getTime()
          return t0 >= from.getTime() && t0 <= to.getTime()
        }

        const todayCount = list.filter((a) => inRange(a.start_time, today, todayEnd)).length
        const weekCount = list.filter((a) => inRange(a.start_time, today, weekEnd)).length
        const confirmed = list.filter((a) => a.status === 'confirmed').length
        const pending = list.filter((a) =>
          ['pending', 'slot_proposed', 'preparation'].includes(a.status)
        ).length

        return { today: todayCount, week: weekCount, confirmed, pending, totalInHorizon: list.length }
      } catch (error) {
        console.error('Error fetching appointment stats:', error)
        return { today: 0, week: 0, confirmed: 0, pending: 0, totalInHorizon: 0 }
      }
    },
  })

  const mailCards: StatCardConfig[] = useMemo(() => {
    const base: StatCardConfig[] = [
      {
        title: t(useKpi ? 'dashboard.mailTotalMine' : 'dashboard.mailTotal'),
        value: mailFromKpi?.total ?? 0,
        icon: <MailIcon />,
        borderAccent: '#1565c0',
        isLoading: isLoadingMailCards,
        path: '/app/mail',
      },
      {
        title: t('dashboard.mailReceived'),
        value: mailFromKpi?.received ?? 0,
        icon: <HourglassEmptyIcon />,
        borderAccent: '#0277bd',
        isLoading: isLoadingMailCards,
        path: '/app/mail',
      },
      {
        title: t('dashboard.mailInTreatment'),
        value: mailFromKpi?.inReview ?? 0,
        icon: <AssignmentIcon />,
        borderAccent: '#00838f',
        isLoading: isLoadingMailCards,
        path: '/app/mail',
      },
      {
        title: t('dashboard.mailApproved'),
        value: mailFromKpi?.approved ?? 0,
        icon: <CheckCircleIcon />,
        borderAccent: '#2e7d32',
        isLoading: isLoadingMailCards,
        path: '/app/mail',
      },
      {
        title: t('dashboard.mailOverdue'),
        value: mailFromKpi?.overdue ?? 0,
        icon: <WarningIcon />,
        borderAccent: '#c62828',
        isLoading: isLoadingMailCards,
        path: '/app/mail',
      },
    ]
    if (useKpi && kpi?.mail) {
      const mbs = kpi.mail.mine_by_status || {}
      base.push(
        {
          title: t('dashboard.mailPendingValidation'),
          value: kpi.mail.mine_pending_validation ?? mbs.pending_validation ?? 0,
          icon: <PendingActionsIcon />,
          borderAccent: '#6a1b9a',
          isLoading: isLoadingKpi,
          path: '/app/mail',
        },
        {
          title: t('dashboard.mailOnHold'),
          value: kpi.mail.mine_on_hold ?? mbs.on_hold ?? 0,
          icon: <PauseCircleIcon />,
          borderAccent: '#5d4037',
          isLoading: isLoadingKpi,
          path: '/app/mail',
        }
      )
    }
    return base
  }, [t, mailFromKpi, isLoadingMailCards, useKpi, kpi, isLoadingKpi])

  const appointmentCards: StatCardConfig[] = useMemo(() => {
    const base: StatCardConfig[] = [
      {
        title: t('dashboard.apptToday'),
        value: appointmentStats?.today ?? 0,
        icon: <CalendarIcon />,
        borderAccent: '#0d47a1',
        isLoading: isLoadingAppointments,
        path: '/app/appointments',
      },
      {
        title: t('dashboard.apptWeek'),
        value: appointmentStats?.week ?? 0,
        icon: <EventNoteIcon />,
        borderAccent: '#00838f',
        isLoading: isLoadingAppointments,
        path: '/app/appointments',
      },
      {
        title: t('dashboard.apptConfirmed'),
        value: appointmentStats?.confirmed ?? 0,
        icon: <EventAvailableIcon />,
        borderAccent: '#1565c0',
        isLoading: isLoadingAppointments,
        path: '/app/appointments',
      },
      {
        title: t('dashboard.apptPending'),
        value: appointmentStats?.pending ?? 0,
        icon: <HourglassEmptyIcon />,
        borderAccent: '#ef6c00',
        isLoading: isLoadingAppointments,
        path: '/app/appointments',
      },
      {
        title: t('dashboard.apptUpcomingTotal'),
        value: appointmentStats?.totalInHorizon ?? 0,
        icon: <CalendarIcon />,
        borderAccent: '#0277bd',
        isLoading: isLoadingAppointments,
        path: '/app/appointments',
      },
    ]
    if (useKpi && kpi) {
      base.push({
        title: showOrgKpi ? t('dashboard.apptOpenTasks') : t('dashboard.apptOpenTasksMine'),
        value: kpi.appointment_open_tasks ?? 0,
        icon: <TaskAltIcon />,
        borderAccent: '#6a1b9a',
        isLoading: isLoadingKpi,
        path: '/app/appointments',
      })
    }
    return base
  }, [t, appointmentStats, isLoadingAppointments, useKpi, kpi, isLoadingKpi, showOrgKpi])

  const orgTotalCards: StatCardConfig[] = useMemo(() => {
    if (!useKpi || !kpi || !showOrgKpi) return []
    return [
      {
        title: t('dashboard.orgMailTotal'),
        value: kpi.mail.total,
        icon: <MailIcon />,
        borderAccent: '#0d47a1',
        isLoading: isLoadingKpi,
        path: '/app/mail',
      },
      {
        title: t('dashboard.orgApptTotal'),
        value: kpi.appointments.total,
        icon: <CalendarIcon />,
        borderAccent: '#006064',
        isLoading: isLoadingKpi,
        path: '/app/appointments',
      },
    ]
  }, [t, useKpi, kpi, isLoadingKpi, showOrgKpi])

  const renderSection = (title: string, subtitle: string, cards: StatCardConfig[]) => (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5, color: 'text.primary' }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {subtitle}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: 'repeat(2, minmax(0, 1fr))',
            sm: 'repeat(3, minmax(0, 1fr))',
            md: 'repeat(5, minmax(0, 1fr))',
          },
          gap: 1.5,
        }}
      >
        {cards.map((card, index) => (
          <Card
            key={`${title}-${index}`}
            onClick={() => navigate(card.path)}
            sx={(theme) => ({
              minWidth: 0,
              height: '100%',
              position: 'relative',
              overflow: 'hidden',
              cursor: 'pointer',
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              borderTop: `3px solid ${card.borderAccent}`,
              borderTopLeftRadius: theme.shape.borderRadius * 1.5,
              borderTopRightRadius: theme.shape.borderRadius * 1.5,
              borderBottomLeftRadius: theme.shape.borderRadius * 1.5,
              borderBottomRightRadius: theme.shape.borderRadius * 1.5,
              boxShadow:
                theme.palette.mode === 'dark'
                  ? `0 2px 12px ${alpha(theme.palette.common.black, 0.4)}`
                  : '0 2px 8px rgba(0, 0, 0, 0.06)',
              transition: 'all 0.25s ease',
              '&:hover': {
                boxShadow:
                  theme.palette.mode === 'dark'
                    ? `0 4px 18px ${alpha(theme.palette.common.black, 0.5)}`
                    : '0 4px 12px rgba(0, 0, 0, 0.08)',
                ...(theme.palette.mode === 'dark'
                  ? { bgcolor: alpha(theme.palette.primary.main, 0.08) }
                  : {}),
              },
            })}
          >
            <CardContent sx={{ p: 1.25, '&:last-child': { pb: 1.25 } }}>
              {card.isLoading ? (
                <>
                  <Skeleton variant="circular" width={36} height={36} sx={{ mb: 1 }} />
                  <Skeleton variant="text" width="90%" height={18} sx={{ mb: 0.5 }} />
                  <Skeleton variant="text" width="50%" height={28} />
                </>
              ) : (
                <>
                  <Box
                    sx={(theme) => ({
                      width: 36,
                      height: 36,
                      borderRadius: 1,
                      bgcolor: alpha(
                        theme.palette.primary.main,
                        theme.palette.mode === 'dark' ? 0.22 : 0.12,
                      ),
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'primary.main',
                      mb: 1,
                      '& svg': { fontSize: 20 },
                    })}
                  >
                    {card.icon}
                  </Box>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontWeight: 600, display: 'block', lineHeight: 1.25, mb: 0.5 }}
                  >
                    {card.title}
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      fontWeight: 700,
                      color: 'text.primary',
                      lineHeight: 1.1,
                      fontSize: { xs: '1.35rem', md: '1.5rem' },
                    }}
                  >
                    {card.value}
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  )

  const mailErr = useKpi ? kpiError : mailError

  const fmtDelay = (x: number | null | undefined) =>
    x != null && !Number.isNaN(x) ? String(x) : '—'

  const delays = useKpi ? kpi?.mail?.delays : undefined

  return (
    <Box sx={{ width: '100%', maxWidth: '100%' }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: 'primary.dark' }}>
          {t('dashboard.title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('common.subtitle')}
        </Typography>
      </Box>

      {((canViewMailDash && mailErr) || (canViewAppointmentsDash && appointmentError)) && (
        <Box sx={{ mb: 3, p: 2, bgcolor: 'error.light', borderRadius: 2, color: 'error.contrastText' }}>
          <Typography variant="body2">{t('dashboard.loadError')}</Typography>
        </Box>
      )}

      {orgTotalCards.length > 0 &&
        renderSection(t('dashboard.sectionOrgTotals'), t('dashboard.sectionOrgTotalsHint'), orgTotalCards)}

      {canViewMailDash &&
        renderSection(
          t('dashboard.sectionMail'),
          useKpi ? t('dashboard.sectionMailMineHint') : t('dashboard.sectionMailHint'),
          mailCards,
        )}
      {showOrgKpi && useKpi && delays && (
        <Box sx={{ mb: 4, px: 0.5 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600, mb: 1 }}>
            {t('dashboard.delaysHint')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('dashboard.delayToApproved', {
              avg: fmtDelay(delays.to_approved?.avg_hours),
              med: fmtDelay(delays.to_approved?.median_hours),
              n: delays.to_approved?.sample_count ?? 0,
            })}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('dashboard.delayToArchived', {
              avg: fmtDelay(delays.to_archived?.avg_hours),
              med: fmtDelay(delays.to_archived?.median_hours),
              n: delays.to_archived?.sample_count ?? 0,
            })}
          </Typography>
        </Box>
      )}
      {canViewAppointmentsDash &&
        renderSection(
          t('dashboard.sectionAppointments'),
          useKpi ? t('dashboard.sectionAppointmentsMineHint') : t('dashboard.sectionAppointmentsHint'),
          appointmentCards,
        )}
    </Box>
  )
}
