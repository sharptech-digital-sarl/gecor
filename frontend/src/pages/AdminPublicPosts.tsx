import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tableContainerScrollSx } from '../theme/tableScroll'
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Switch,
  FormControlLabel,
  CircularProgress,
  IconButton,
} from '@mui/material'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import EditIcon from '@mui/icons-material/Edit'
import AddIcon from '@mui/icons-material/Add'
import { useTranslation } from 'react-i18next'
import api from '../services/api'
import { TableExportButton, type TableExportColumn } from '../components/TableExportButton'

type Post = {
  id: string
  title: string
  body: string
  sort_order: number
  published: boolean
  updated_at: string
}

const emptyForm = { title: '', body: '', sort_order: 0, published: true }

export default function AdminPublicPosts() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Post | null>(null)
  const [form, setForm] = useState(emptyForm)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-info-posts'],
    queryFn: async () => {
      const { data: rows } = await api.get<Post[]>('/admin/info-posts', {
        params: { include_unpublished: true },
      })
      return rows
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editing) {
        await api.put(`/admin/info-posts/${editing.id}`, form)
      } else {
        await api.post('/admin/info-posts', form)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-info-posts'] })
      setDialogOpen(false)
      setEditing(null)
      setForm(emptyForm)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/admin/info-posts/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-info-posts'] }),
  })

  const openCreate = () => {
    setEditing(null)
    const maxOrder = (data ?? []).reduce((m, p) => Math.max(m, p.sort_order ?? 0), -1)
    setForm({ ...emptyForm, sort_order: maxOrder + 1 })
    setDialogOpen(true)
  }

  const openEdit = (p: Post) => {
    setEditing(p)
    setForm({
      title: p.title,
      body: p.body,
      sort_order: p.sort_order,
      published: p.published,
    })
    setDialogOpen(true)
  }

  const postsExportColumns = useMemo<TableExportColumn[]>(
    () => [
      { key: 'sort_order', header: t('adminPublicPosts.colOrder') },
      { key: 'title', header: t('adminPublicPosts.colTitle') },
      { key: 'published', header: t('adminPublicPosts.colPublished') },
      { key: 'updated_at', header: t('adminPublicPosts.colUpdated') },
    ],
    [t]
  )

  const postsExportRows = useMemo(
    () =>
      (data ?? []).map((p) => ({
        sort_order: p.sort_order,
        title: p.title,
        published: p.published ? t('common.yes') : t('common.no'),
        updated_at: new Date(p.updated_at).toLocaleString(),
      })),
    [data, t]
  )

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={1}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          {t('adminPublicPosts.title')}
        </Typography>
        <Box display="flex" gap={1} alignItems="center" flexWrap="wrap">
          <TableExportButton
            filenameBase="public-posts"
            sheetName={t('adminPublicPosts.title')}
            columns={postsExportColumns}
            rows={postsExportRows}
            disabled={isLoading}
          />
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            {t('adminPublicPosts.create')}
          </Button>
        </Box>
      </Box>
      <TableContainer component={Paper} sx={tableContainerScrollSx}>
        {isLoading ? (
          <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : (
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>{t('adminPublicPosts.colOrder')}</TableCell>
                <TableCell>{t('adminPublicPosts.colTitle')}</TableCell>
                <TableCell>{t('adminPublicPosts.colPublished')}</TableCell>
                <TableCell>{t('adminPublicPosts.colUpdated')}</TableCell>
                <TableCell>{t('common.actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(data ?? []).map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.sort_order}</TableCell>
                  <TableCell>{p.title}</TableCell>
                  <TableCell>{p.published ? t('common.yes') : t('common.no')}</TableCell>
                  <TableCell>{new Date(p.updated_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => openEdit(p)} aria-label={t('common.edit')}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => deleteMutation.mutate(p.id)}
                      aria-label={t('common.delete')}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </TableContainer>

      <Dialog open={dialogOpen} onClose={() => !saveMutation.isPending && setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? t('adminPublicPosts.edit') : t('adminPublicPosts.create')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label={t('adminPublicPosts.fieldTitle')}
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            fullWidth
            required
          />
          <TextField
            label={t('adminPublicPosts.fieldBody')}
            value={form.body}
            onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
            fullWidth
            multiline
            minRows={4}
            required
          />
          <TextField
            type="number"
            label={t('adminPublicPosts.fieldOrder')}
            value={form.sort_order}
            onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) || 0 }))}
            fullWidth
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.published}
                onChange={(e) => setForm((f) => ({ ...f, published: e.target.checked }))}
              />
            }
            label={t('adminPublicPosts.fieldPublished')}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saveMutation.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            disabled={saveMutation.isPending || !form.title.trim() || !form.body.trim()}
            onClick={() => saveMutation.mutate()}
          >
            {t('common.save')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
