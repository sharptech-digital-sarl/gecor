import { Box } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'

/** En-tête de modale : bandeau sous le titre, séparé du corps. */
export function ModalSectionHeader({ children }: { children: React.ReactNode }) {
  const theme = useTheme()
  return (
    <Box
      sx={{
        px: 3,
        pt: 2.5,
        pb: 2,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: alpha(theme.palette.primary.main, 0.06),
      }}
    >
      {children}
    </Box>
  )
}

/** Corps principal de la modale (scrollable si besoin via parent). */
export function ModalSectionBody({
  children,
  sx,
}: {
  children: React.ReactNode
  sx?: object
}) {
  return <Box sx={{ px: 3, py: 2.5, ...sx }}>{children}</Box>
}

/** Styles pour `DialogActions` : pied de modale distinct. */
export const modalDialogFooterSx = {
  flexWrap: 'wrap' as const,
  gap: 1,
  px: 2,
  py: 1.5,
  borderTop: 1,
  borderColor: 'divider',
  bgcolor: 'action.hover',
}
