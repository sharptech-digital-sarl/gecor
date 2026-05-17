import { useState, useEffect } from 'react'

/** `true` lorsque l’onglet est au premier plan (pour adapter le polling, etc.). */
export function useDocumentVisible(): boolean {
  const [visible, setVisible] = useState(
    () => typeof document !== 'undefined' && document.visibilityState === 'visible'
  )

  useEffect(() => {
    const fn = () => setVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', fn)
    return () => document.removeEventListener('visibilitychange', fn)
  }, [])

  return visible
}
