import type { SxProps, Theme } from '@mui/material/styles'

/** Hauteur max + défilement pour éviter des tableaux d’une longueur illimitée. */
export const tableContainerScrollSx: SxProps<Theme> = {
  maxHeight: 'min(70vh, 720px)',
  overflow: 'auto',
}
