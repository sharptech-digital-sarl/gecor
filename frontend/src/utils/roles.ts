/** Master, director ou rôle admin (liste utilisateurs, même périmètre que le backend). */
export function isAdminUser(role: string | undefined | null): boolean {
  if (!role) return false
  const r = String(role).toLowerCase()
  return r === 'master' || r === 'director' || r === 'admin'
}

/** Only master can change roles (matches backend). */
export function isMasterUser(role: string | undefined | null): boolean {
  return String(role || '').toLowerCase() === 'master'
}

/** Master ou direction — périmètre élargi (ex. suppression définitive RDV, archivage courrier direct). */
export function isMasterOrDirector(role: string | undefined | null): boolean {
  const r = String(role || '').toLowerCase()
  return r === 'master' || r === 'director'
}
