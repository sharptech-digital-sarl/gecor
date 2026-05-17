import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Alert,
  LinearProgress,
  Typography,
  MenuItem,
} from '@mui/material'
import { useDropzone } from 'react-dropzone'
import api from '../../services/api'

interface DocumentUploadProps {
  open: boolean
  onClose: () => void
}

export default function DocumentUpload({ open, onClose }: DocumentUploadProps) {
  const { t } = useTranslation()
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('normal')

  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await api.post('/mail/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      return response.data
    },
    onSuccess: () => {
      onClose()
      setFile(null)
      setTitle('')
      setDescription('')
      setPriority('normal')
    },
  })

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff'],
    },
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0])
        if (!title) {
          setTitle(acceptedFiles[0].name)
        }
      }
    },
    maxFiles: 1,
  })

  const handleSubmit = () => {
    if (!file || !title) {
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', title)
    formData.append('description', description)
    formData.append('priority', priority)

    uploadMutation.mutate(formData)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t('mail.upload.title')}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Box
            {...getRootProps()}
            sx={{
              border: '2px dashed',
              borderColor: isDragActive ? 'primary.main' : 'grey.300',
              borderRadius: 2,
              p: 3,
              textAlign: 'center',
              cursor: 'pointer',
              bgcolor: isDragActive ? 'action.hover' : 'background.paper',
            }}
          >
            <input {...getInputProps()} />
            {file ? (
              <Typography>{file.name}</Typography>
            ) : (
              <Typography>
                {isDragActive
                  ? t('mail.upload.dropHere')
                  : t('mail.upload.dragDrop')}
              </Typography>
            )}
          </Box>

          <TextField
            fullWidth
            label={t('mail.titleLabel')}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            margin="normal"
            required
          />

          <TextField
            fullWidth
            label={t('mail.description')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            margin="normal"
            multiline
            rows={3}
          />

          <TextField
            fullWidth
            select
            label={t('mail.priority')}
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            margin="normal"
          >
            <MenuItem value="low">{t('mail.priorityLow')}</MenuItem>
            <MenuItem value="normal">{t('mail.priorityNormal')}</MenuItem>
            <MenuItem value="high">{t('mail.priorityHigh')}</MenuItem>
            <MenuItem value="urgent">{t('mail.priorityUrgent')}</MenuItem>
          </TextField>

          {uploadMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {uploadMutation.error instanceof Error
                ? uploadMutation.error.message
                : t('mail.upload.uploadFailed')}
            </Alert>
          )}

          {uploadMutation.isPending && <LinearProgress sx={{ mt: 2 }} />}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('common.cancel')}</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!file || !title || uploadMutation.isPending}
        >
          {uploadMutation.isPending
            ? t('mail.upload.uploading')
            : t('mail.upload.uploadButton')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
