import * as XLSX from 'xlsx'

export type TableExportColumn = { key: string; header: string }

export function sanitizeFilenameBase(s: string): string {
  const t = s.replace(/[^a-zA-Z0-9._-]+/g, '_').replace(/^_+|_+$/g, '')
  return t.slice(0, 80) || 'export'
}

export function sanitizeSheetName(s: string): string {
  const t = s.replace(/[/\\*?\[\]:]/g, '-').trim()
  return (t.slice(0, 31) || 'Sheet1').replace(/^'+/, '')
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function downloadTableJson(
  filenameBase: string,
  columns: TableExportColumn[],
  rows: Array<Record<string, unknown>>,
) {
  const data = rows.map((row) => {
    const o: Record<string, unknown> = {}
    for (const c of columns) {
      o[c.header] = row[c.key] ?? ''
    }
    return o
  })
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
  triggerDownload(blob, `${sanitizeFilenameBase(filenameBase)}.json`)
}

export function downloadTableXlsx(
  filenameBase: string,
  sheetName: string,
  columns: TableExportColumn[],
  rows: Array<Record<string, unknown>>,
) {
  const headerRow = columns.map((c) => c.header)
  const aoa: unknown[][] = [headerRow]
  for (const row of rows) {
    aoa.push(columns.map((c) => row[c.key] ?? ''))
  }
  const ws = XLSX.utils.aoa_to_sheet(aoa)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, sanitizeSheetName(sheetName))
  const buf = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
  const blob = new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  triggerDownload(blob, `${sanitizeFilenameBase(filenameBase)}.xlsx`)
}
