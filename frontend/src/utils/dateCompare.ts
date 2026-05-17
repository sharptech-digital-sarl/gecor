/** True if `iso` falls on the same local calendar day as `ref`. */
export function isSameLocalDay(iso: string | Date, ref: Date = new Date()): boolean {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return (
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate()
  )
}
