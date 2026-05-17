import { useRef, useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Button, TextField, Alert, Paper, CircularProgress } from '@mui/material'
import { useTranslation } from 'react-i18next'
import SignatureCanvas from 'react-signature-canvas'
import api from '../../services/api'

interface SignaturePadProps {
  documentId: number
}

export default function SignaturePad({ documentId }: SignaturePadProps) {
  const { t } = useTranslation()
  const sigPadRef = useRef<SignatureCanvas>(null)
  const [comments, setComments] = useState('')
  const [canvasReady, setCanvasReady] = useState(false)
  const queryClient = useQueryClient()

  // Fetch existing signature
  const { data: existingSignature, isLoading: isLoadingSignature } = useQuery({
    queryKey: ['signature', documentId],
    queryFn: async () => {
      try {
        const response = await api.get(`/signatures/?document_id=${documentId}`)
        // API might return an array or a single object
        const signatures = Array.isArray(response.data) ? response.data : [response.data]
        return signatures.length > 0 ? signatures[0] : null
      } catch (err: any) {
        // If 404, no signature exists yet
        if (err.response?.status === 404) {
          return null
        }
        throw err
      }
    },
  })

  const signatureMutation = useMutation({
    mutationFn: async (data: { signature_data: string; comments: string }) => {
      const response = await api.post('/signatures/', {
        document_id: documentId,
        signature_data: data.signature_data,
        comments: data.comments,
      })
      return response.data
    },
    onSuccess: () => {
      // Invalidate and refetch signature after saving
      queryClient.invalidateQueries({ queryKey: ['signature', documentId] })
    },
  })

  // Mark canvas as ready when component mounts
  useEffect(() => {
    // Check if canvas ref is available
    const checkCanvasReady = () => {
      if (sigPadRef.current) {
        setCanvasReady(true)
        if (import.meta.env.DEV) {
          console.log('SignaturePad: Canvas ref is available')
        }
        return true
      }
      return false
    }

    // Try immediately
    if (checkCanvasReady()) {
      return
    }

    // If not ready, try with delays
    const timers: ReturnType<typeof setTimeout>[] = []
    const delays = [50, 100, 200, 300]
    delays.forEach((delay: number) => {
      const timer = setTimeout(() => {
        if (checkCanvasReady()) {
          // Clear remaining timers if successful
          timers.forEach((t) => clearTimeout(t))
        }
      }, delay)
      timers.push(timer)
    })

    return () => {
      timers.forEach((timer) => clearTimeout(timer))
    }
  }, [])

  // Load existing signature into canvas
  useEffect(() => {
    if (isLoadingSignature) {
      if (import.meta.env.DEV) {
        console.log('SignaturePad: Still loading signature from API')
      }
      return // Don't do anything while loading
    }

    if (!existingSignature) {
      if (import.meta.env.DEV) {
        console.log('SignaturePad: No existing signature object found')
      }
      return // No signature to load
    }

    if (!existingSignature.signature_data) {
      if (import.meta.env.DEV) {
        console.log('SignaturePad: No signature_data in existing signature', {
          signature: existingSignature,
        })
      }
      return // No signature data to load
    }

    if (!sigPadRef.current) {
      if (import.meta.env.DEV) {
        console.log('SignaturePad: Canvas ref not available, will retry')
      }
      // Don't return, let the retry mechanism handle it
    }

    if (import.meta.env.DEV) {
      console.log('SignaturePad: Signature data received from API', {
        hasSignature: !!existingSignature,
        hasData: !!existingSignature.signature_data,
        dataType: typeof existingSignature.signature_data,
        dataLength: existingSignature.signature_data?.length,
        isDataUrl: existingSignature.signature_data?.startsWith('data:image/'),
      })
    }

    // Function to load signature
    const loadSignature = () => {
      if (!sigPadRef.current) {
        if (import.meta.env.DEV) {
          console.log('SignaturePad: Canvas ref still not available')
        }
        return false
      }

      try {
        const signatureData = existingSignature.signature_data
        
        // Validate that signature_data is a data URL
        if (!signatureData) {
          if (import.meta.env.DEV) {
            console.warn('SignaturePad: signature_data is empty or null')
          }
          return false
        }

        // Check if it's a valid data URL format
        const isDataUrl = signatureData.startsWith('data:image/')
        if (!isDataUrl) {
          if (import.meta.env.DEV) {
            console.warn('SignaturePad: signature_data is not in data URL format', {
              dataStart: signatureData.substring(0, 50),
              expectedFormat: 'data:image/png;base64,...',
            })
          }
          // Try to fix it by adding the prefix if it's just base64
          if (signatureData.startsWith('iVBORw0KGgo') || signatureData.length > 100) {
            // Likely base64 without prefix, add it
            const fixedDataUrl = `data:image/png;base64,${signatureData}`
            if (import.meta.env.DEV) {
              console.log('SignaturePad: Attempting to fix format by adding data URL prefix')
            }
            sigPadRef.current.fromDataURL(fixedDataUrl)
            setComments(existingSignature.comments || '')
            return true
          }
          return false
        }

        if (import.meta.env.DEV) {
          console.log('SignaturePad: Attempting to load signature', {
            hasData: !!signatureData,
            dataLength: signatureData?.length,
            isDataUrl: true,
            mimeType: signatureData.substring(5, signatureData.indexOf(';')),
            dataStart: signatureData.substring(0, 50),
          })
        }

        // Use fromDataURL method from react-signature-canvas
        // Backend now returns data URL format: data:image/png;base64,...
        sigPadRef.current.fromDataURL(signatureData, {
          width: 600,
          height: 200,
        })
        setComments(existingSignature.comments || '')
        
        if (import.meta.env.DEV) {
          console.log('SignaturePad: Signature loaded successfully using fromDataURL')
        }
        return true
      } catch (error) {
        console.error('SignaturePad: Failed to load signature:', error)
        return false
      }
    }

    // Try to load immediately
    if (loadSignature()) {
      return
    }

    // If canvas not ready, try again with increasing delays
    const timers: ReturnType<typeof setTimeout>[] = []
    const delays = [100, 300, 500]
    delays.forEach((delay: number) => {
      const timer = setTimeout(() => {
        if (loadSignature()) {
          // Clear remaining timers if successful
          timers.forEach((t) => clearTimeout(t))
        }
      }, delay)
      timers.push(timer)
    })

    return () => {
      timers.forEach((timer) => clearTimeout(timer))
    }
  }, [existingSignature, isLoadingSignature, canvasReady])

  const handleClear = () => {
    sigPadRef.current?.clear()
  }

  const handleSave = () => {
    if (!sigPadRef.current) return

    const signatureData = sigPadRef.current.toDataURL()
    signatureMutation.mutate({
      signature_data: signatureData,
      comments,
    })
  }

  if (isLoadingSignature) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <SignatureCanvas
          ref={sigPadRef}
          canvasProps={{
            width: 600,
            height: 200,
            className: 'signature-canvas',
          }}
          backgroundColor="#ffffff"
          onEnd={() => {
            // Canvas is ready when user can draw
            if (!canvasReady) {
              setCanvasReady(true)
            }
          }}
        />
      </Paper>

      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <Button variant="outlined" onClick={handleClear}>
          {t('mail.signature.clear')}
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={signatureMutation.isPending}
        >
          {signatureMutation.isPending
            ? t('mail.signature.saving')
            : t('mail.signature.saveSignature')}
        </Button>
      </Box>

      <TextField
        fullWidth
        label={t('mail.signature.comments')}
        value={comments}
        onChange={(e) => setComments(e.target.value)}
        multiline
        rows={3}
        margin="normal"
      />

      {signatureMutation.isSuccess && (
        <Alert severity="success" sx={{ mt: 2 }}>
          {t('mail.signature.savedSuccessfully')}
        </Alert>
      )}

      {signatureMutation.isError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {t('mail.signature.saveFailed')}
        </Alert>
      )}
    </Box>
  )
}
