/** Ancien format API : PNG en base64. Les QR sont servis en fichier (`/public/.../visitor-qrcode`). */
export function qrPngSrcFromApiBase64(raw: string | null | undefined): string | null {
  if (raw == null || !String(raw).trim()) return null
  const t = String(raw).trim()
  if (t.startsWith('data:')) return t
  return `data:image/png;base64,${t}`
}
