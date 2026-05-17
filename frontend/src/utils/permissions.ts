export function hasPermission(
  user: { permissions?: string[] } | null | undefined,
  key: string
): boolean {
  return !!user?.permissions?.includes(key)
}

/** Master, director ou rôle admin (même jeu que le backend) ; sinon permission explicite. */
export function canReviewDeletionRequests(
  user: { role?: string; permissions?: string[] } | null | undefined
): boolean {
  if (!user) return false
  const r = String(user.role || '').toLowerCase()
  if (r === 'master' || r === 'director' || r === 'admin') return true
  return hasPermission(user, 'deletion_requests.review')
}
