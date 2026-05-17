/** Nom affiché de l’application (marque). */
export const APP_NAME = 'GECOR'

/** Version affichée (build-time). Défaut côté code : 1.0 */
export const APP_VERSION = (() => {
  const v = import.meta.env.VITE_APP_VERSION
  if (typeof v === 'string' && v.trim()) return v.trim()
  return '1.0'
})()
