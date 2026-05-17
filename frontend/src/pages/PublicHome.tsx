import { Link as RouterLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Container,
  Divider,
  Link,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { tokenService } from '../services/tokenService'
import { useDateFormat } from '../hooks/useDateFormat'
import { ModalSectionHeader, ModalSectionBody } from '../components/common/DetailModalLayout'
import { APP_VERSION } from '../constants/appBrand'

type PublicPost = {
  id: string
  title: string
  body: string
  sort_order: number
  created_at: string
  updated_at: string
  author_username: string | null
}

export default function PublicHome() {
  const { t } = useTranslation()
  const { formatDateTime } = useDateFormat()
  const { isAuthenticated, loading } = useAuth()
  const hasToken = !!tokenService.getAccessToken()
  const showAppLink = !loading && (isAuthenticated || hasToken)

  const { data: dynamicPosts = [] } = useQuery({
    queryKey: ['public-info-posts'],
    queryFn: async () => {
      const { data } = await api.get<PublicPost[]>('/public/info-posts')
      return data
    },
    staleTime: 60_000,
  })

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', py: 4 }}>
      <Container maxWidth="md">
        <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, overflow: 'hidden', mb: 3 }}>
          <ModalSectionHeader>
            <Stack direction="row" alignItems="baseline" flexWrap="wrap" columnGap={1} rowGap={0.25}>
              <Typography
                component="h1"
                sx={{
                  fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
                  fontWeight: 800,
                  fontSize: { xs: '1.65rem', sm: '2rem' },
                  letterSpacing: '0.04em',
                  lineHeight: 1.15,
                  color: 'primary.dark',
                }}
              >
                {t('publicHome.title')}
              </Typography>
              <Typography
                component="span"
                variant="subtitle1"
                sx={{ fontWeight: 600, color: 'text.secondary', letterSpacing: '0.04em' }}
              >
                v{APP_VERSION}
              </Typography>
            </Stack>
            <Typography variant="body1" color="text.secondary" sx={{ mt: 1.5 }}>
              {t('publicHome.intro')}
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mt: 2 }}>
              <Button component={RouterLink} to="/public/booking" variant="contained" size="large">
                {t('publicHome.ctaBooking')}
              </Button>
              <Button component={RouterLink} to="/login" variant="outlined" size="large">
                {t('publicHome.ctaLogin')}
              </Button>
              {showAppLink && (
                <Button component={RouterLink} to="/app" variant="text" size="large">
                  {t('publicHome.ctaApp')}
                </Button>
              )}
            </Stack>
          </ModalSectionHeader>
          <ModalSectionBody>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
              {t('publicHome.sectionInfoTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {t('publicHome.sectionInfoBody')}
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, mt: 2 }}>
              {t('publicHome.sectionVisitTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {t('publicHome.sectionVisitBody')}
            </Typography>
            <Typography variant="body2" sx={{ mt: 2 }}>
              <Link component={RouterLink} to="/public/booking" fontWeight={600}>
                {t('publicHome.linkBookingAgain')}
              </Link>
            </Typography>
            {dynamicPosts.length > 0 && (
              <>
                <Divider sx={{ my: 3 }} />
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  {t('publicHome.dynamicPostsTitle')}
                </Typography>
                <Stack spacing={2}>
                  {dynamicPosts.map((p) => (
                    <Paper
                      key={p.id}
                      variant="outlined"
                      sx={{
                        p: 0,
                        borderRadius: 2,
                        overflow: 'hidden',
                        borderColor: 'divider',
                      }}
                    >
                      <Box
                        sx={{
                          px: 2,
                          py: 1.25,
                          bgcolor: 'action.hover',
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          display: 'flex',
                          flexWrap: 'wrap',
                          alignItems: 'baseline',
                          justifyContent: 'space-between',
                          gap: 1,
                        }}
                      >
                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                          {p.title}
                        </Typography>
                        <Box
                          sx={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 1.5,
                            typography: 'caption',
                            color: 'text.secondary',
                          }}
                        >
                          {p.author_username ? (
                            <Typography component="span" variant="caption" color="text.secondary">
                              {t('publicHome.postMetaAuthor', { username: p.author_username })}
                            </Typography>
                          ) : null}
                          <Typography component="span" variant="caption" color="text.secondary">
                            {t('publicHome.postMetaPublished', { date: formatDateTime(p.created_at) })}
                          </Typography>
                          {new Date(p.updated_at).getTime() !== new Date(p.created_at).getTime() ? (
                            <Typography component="span" variant="caption" color="text.secondary">
                              {t('publicHome.postMetaUpdated', { date: formatDateTime(p.updated_at) })}
                            </Typography>
                          ) : null}
                        </Box>
                      </Box>
                      <Box sx={{ px: 2, py: 2 }}>
                        <Typography variant="body2" color="text.primary" sx={{ whiteSpace: 'pre-wrap' }}>
                          {p.body}
                        </Typography>
                      </Box>
                    </Paper>
                  ))}
                </Stack>
              </>
            )}
          </ModalSectionBody>
        </Paper>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          justifyContent="center"
          alignItems="center"
          sx={{ mt: 2, typography: 'body2' }}
        >
          <Link component={RouterLink} to="/privacy" underline="hover" color="text.secondary">
            {t('legal.navPrivacy')}
          </Link>
          <Typography component="span" variant="body2" color="text.disabled" sx={{ display: { xs: 'none', sm: 'inline' } }}>
            ·
          </Typography>
          <Link component={RouterLink} to="/terms" underline="hover" color="text.secondary">
            {t('legal.navTerms')}
          </Link>
        </Stack>
      </Container>
    </Box>
  )
}
