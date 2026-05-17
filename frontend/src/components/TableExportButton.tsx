import DownloadIcon from '@mui/icons-material/Download'
import { Button, Menu, MenuItem } from '@mui/material'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { downloadTableJson, downloadTableXlsx, type TableExportColumn } from '../utils/tableExport'

export type { TableExportColumn }

type Props = {
  filenameBase: string
  sheetName?: string
  columns: TableExportColumn[]
  rows: Record<string, unknown>[]
  disabled?: boolean
  size?: 'small' | 'medium' | 'large'
}

export function TableExportButton({
  filenameBase,
  sheetName = 'Export',
  columns,
  rows,
  disabled,
  size = 'small',
}: Props) {
  const { t } = useTranslation()
  const [anchor, setAnchor] = useState<null | HTMLElement>(null)
  const open = Boolean(anchor)
  const isDisabled = disabled || rows.length === 0

  const handleJson = () => {
    downloadTableJson(filenameBase, columns, rows)
    setAnchor(null)
  }

  const handleXlsx = () => {
    downloadTableXlsx(filenameBase, sheetName, columns, rows)
    setAnchor(null)
  }

  return (
    <>
      <Button
        size={size}
        variant="outlined"
        startIcon={<DownloadIcon />}
        disabled={isDisabled}
        onClick={(e) => setAnchor(e.currentTarget)}
      >
        {t('common.export')}
      </Button>
      <Menu anchorEl={anchor} open={open} onClose={() => setAnchor(null)}>
        <MenuItem onClick={handleXlsx}>{t('common.exportXlsx')}</MenuItem>
        <MenuItem onClick={handleJson}>{t('common.exportJson')}</MenuItem>
      </Menu>
    </>
  )
}
