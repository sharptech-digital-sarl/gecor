/**
 * Aligne les chaînes renvoyées par l’API avec une interprétation UTC cohérente
 * (évite le décalage quand la chaîne ISO n’a pas de suffixe Z / fuseau).
 */
export function normalizeApiDatetimeIsoString(input: string): string | null {
  const s = input.trim()
  if (!s) return null
  if (/[zZ]$/.test(s)) return s
  if (/[+-]\d{2}:\d{2}$/.test(s) || /[+-]\d{4}$/.test(s)) return s
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s}T00:00:00.000Z`
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return s.endsWith('Z') ? s : `${s}Z`
  return s
}
