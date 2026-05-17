import { Link as RouterLink } from 'react-router-dom'
import { Box, Container, Link, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

type Section = { titleKey: string; bodyKey: string }

type Props = {
  titleKey: string
  updatedKey: string
  sections: readonly Section[]
}

export default function LegalDocumentPage({ titleKey, updatedKey, sections }: Props) {
  const { t } = useTranslation()

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', py: 4 }}>
      <Container maxWidth="md">
        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, sm: 4 },
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
          }}
        >
          <Typography
            component="h1"
            variant="h4"
            sx={{
              fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
              fontWeight: 800,
              letterSpacing: '0.03em',
              color: 'primary.dark',
              mb: 1,
            }}
          >
            {t(titleKey)}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 3 }}>
            {t(updatedKey)}
          </Typography>
          <Stack spacing={3}>
            {sections.map((s) => (
              <Box key={s.titleKey}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  {t(s.titleKey)}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.primary"
                  sx={{ whiteSpace: 'pre-wrap', textAlign: 'justify' }}
                >
                  {t(s.bodyKey)}
                </Typography>
              </Box>
            ))}
          </Stack>
          <Box sx={{ mt: 4, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            <Link component={RouterLink} to="/" underline="hover" fontWeight={600}>
              {t('legal.backHome')}
            </Link>
          </Box>
        </Paper>
      </Container>
    </Box>
  )
}
