import { useState, useRef } from 'react'
import { Box, IconButton, Toolbar, Paper } from '@mui/material'
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  RotateLeft as RotateLeftIcon,
  RotateRight as RotateRightIcon,
  FitScreen as FitScreenIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material'
import { useTranslation } from 'react-i18next'

interface ImageViewerProps {
  src: string
  alt: string
}

export default function ImageViewer({ src, alt }: ImageViewerProps) {
  const { t } = useTranslation()
  const [scale, setScale] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)

  const handleZoomIn = () => {
    setScale((prev) => Math.min(prev + 0.25, 5))
  }

  const handleZoomOut = () => {
    setScale((prev) => Math.max(prev - 0.25, 0.25))
  }

  const handleRotateLeft = () => {
    setRotation((prev) => (prev - 90) % 360)
  }

  const handleRotateRight = () => {
    setRotation((prev) => (prev + 90) % 360)
  }

  const handleFitScreen = () => {
    setScale(1)
    setPosition({ x: 0, y: 0 })
    setRotation(0)
  }

  const handleFullscreen = () => {
    if (!containerRef.current) return

    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      containerRef.current.requestFullscreen()
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    if (scale <= 1) return
    setIsDragging(true)
    setDragStart({
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || scale <= 1) return
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '600px',
        position: 'relative',
        overflow: 'hidden',
        bgcolor: 'action.hover',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <Paper
        elevation={2}
        sx={{
          position: 'absolute',
          top: 8,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 10,
          display: 'flex',
          gap: 0.5,
          p: 0.5,
        }}
      >
        <Toolbar variant="dense" sx={{ minHeight: 'auto', p: 0 }}>
          <IconButton
            size="small"
            onClick={handleZoomOut}
            title={t('mail.viewer.zoomOut')}
            disabled={scale <= 0.25}
          >
            <ZoomOutIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleZoomIn}
            title={t('mail.viewer.zoomIn')}
            disabled={scale >= 5}
          >
            <ZoomInIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleRotateLeft}
            title={t('mail.viewer.rotateLeft')}
          >
            <RotateLeftIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleRotateRight}
            title={t('mail.viewer.rotateRight')}
          >
            <RotateRightIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleFitScreen}
            title={t('mail.viewer.fitScreen')}
          >
            <FitScreenIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleFullscreen}
            title={t('mail.viewer.fullscreen')}
          >
            <FullscreenIcon />
          </IconButton>
        </Toolbar>
      </Paper>

      <Box
        sx={{
          transform: `translate(${position.x}px, ${position.y}px) rotate(${rotation}deg) scale(${scale})`,
          transition: isDragging ? 'none' : 'transform 0.2s ease',
          cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default',
        }}
      >
        <Box
          component="img"
          ref={imageRef}
          src={src}
          alt={alt}
          sx={{
            maxWidth: '100%',
            maxHeight: '600px',
            objectFit: 'contain',
            userSelect: 'none',
            display: 'block',
          }}
          draggable={false}
        />
      </Box>
    </Box>
  )
}

