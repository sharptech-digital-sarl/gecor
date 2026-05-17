import type { ComponentType, MouseEvent } from 'react'
import { Box, Button } from '@mui/material'
import dayjs from 'dayjs'
import type { DateCellWrapperProps, DateHeaderProps } from 'react-big-calendar'

type SlotWrapperProps = {
  value: Date
  resource?: unknown
  children: React.ReactNode
}

const hoverWrapSx = {
  position: 'relative' as const,
  flex: 1,
  minHeight: 44,
  height: '100%',
  width: '100%',
  '&:hover .calendar-cell-create-btn': {
    opacity: 1,
    pointerEvents: 'auto' as const,
  },
}

const btnSx = {
  position: 'absolute' as const,
  bottom: 4,
  left: '50%',
  transform: 'translateX(-50%)',
  opacity: 0,
  pointerEvents: 'none' as const,
  transition: 'opacity 0.18s ease',
  zIndex: 4,
  fontSize: '0.65rem',
  py: 0.35,
  px: 1,
  minWidth: 'auto',
  maxWidth: 'calc(100% - 8px)',
  whiteSpace: 'nowrap' as const,
  textOverflow: 'ellipsis',
  overflow: 'hidden',
}

/**
 * Boutons « Créer rendez-vous » au survol des cellules (mois : jour entier à 9h–10h ; semaine/jour : créneau courant).
 */
export function buildCalendarCreateHoverComponents(opts: {
  enabled: boolean
  onOpenCreate: (range: { start: Date; end: Date }) => void
  label: string
  slotStepMinutes: number
}): {
  dateCellWrapper?: ComponentType<DateCellWrapperProps>
  timeSlotWrapper?: ComponentType<SlotWrapperProps>
  month?: { dateHeader: ComponentType<DateHeaderProps> }
} {
  if (!opts.enabled) return {}

  const DateCellWrapper = ({ value, children }: DateCellWrapperProps) => {
    const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation()
      e.preventDefault()
      const start = dayjs(value).startOf('day').hour(9).minute(0).second(0).millisecond(0)
      const end = start.add(1, 'hour')
      opts.onOpenCreate({ start: start.toDate(), end: end.toDate() })
    }
    return (
      <Box className="rbc-calendar-cell-create-root" sx={hoverWrapSx}>
        {children}
        <Button
          type="button"
          className="calendar-cell-create-btn"
          size="small"
          variant="contained"
          color="primary"
          sx={btnSx}
          onClick={handleClick}
        >
          {opts.label}
        </Button>
      </Box>
    )
  }

  const TimeSlotWrapper = ({ value, children }: SlotWrapperProps) => {
    const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation()
      e.preventDefault()
      const start = value
      const end = dayjs(value).add(opts.slotStepMinutes, 'minute').toDate()
      opts.onOpenCreate({ start, end })
    }
    return (
      <Box className="rbc-calendar-cell-create-root" sx={{ ...hoverWrapSx, minHeight: 28 }}>
        {children}
        <Button
          type="button"
          className="calendar-cell-create-btn"
          size="small"
          variant="contained"
          color="primary"
          sx={{ ...btnSx, bottom: 2, fontSize: '0.6rem', py: 0.2 }}
          onClick={handleClick}
        >
          {opts.label}
        </Button>
      </Box>
    )
  }

  /** En-tête de jour (vue mois) : au-dessus de la grille d’événements, donc le bouton reste utilisable même si le jour est rempli. */
  const MonthDateHeader = ({ date, label, drilldownView, onDrillDown }: DateHeaderProps) => {
    const handleCreate = (e: MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation()
      e.preventDefault()
      const start = dayjs(date).startOf('day').hour(9).minute(0).second(0).millisecond(0)
      const end = start.add(1, 'hour')
      opts.onOpenCreate({ start: start.toDate(), end: end.toDate() })
    }
    const headerSx = {
      position: 'relative' as const,
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'flex-end',
      width: '100%',
      minHeight: 36,
      '&:hover .calendar-cell-create-btn': {
        opacity: 1,
        pointerEvents: 'auto' as const,
      },
    }
    const headerBtnSx = {
      ...btnSx,
      position: 'relative' as const,
      bottom: 'auto',
      left: 'auto',
      transform: 'none',
      mt: 0.25,
      alignSelf: 'flex-end',
      maxWidth: '100%',
    }
    return (
      <Box className="rbc-calendar-cell-create-root rbc-calendar-month-date-header" sx={headerSx}>
        {drilldownView ? (
          <button type="button" className="rbc-button-link" onClick={onDrillDown}>
            {label}
          </button>
        ) : (
          <span>{label}</span>
        )}
        <Button
          type="button"
          className="calendar-cell-create-btn"
          size="small"
          variant="contained"
          color="primary"
          sx={headerBtnSx}
          onClick={handleCreate}
        >
          {opts.label}
        </Button>
      </Box>
    )
  }

  return {
    dateCellWrapper: DateCellWrapper,
    timeSlotWrapper: TimeSlotWrapper,
    month: { dateHeader: MonthDateHeader },
  }
}
