/* eslint-disable no-restricted-globals */
self.addEventListener('push', (event) => {
  let title = 'GECOR'
  let body = ''
  let soundCategory = 'other'
  try {
    const data = event.data ? event.data.json() : {}
    title = data.title || title
    body = data.body || ''
    if (data.sound_category === 'mail' || data.sound_category === 'appointment' || data.sound_category === 'other') {
      soundCategory = data.sound_category
    }
  } catch {
    body = event.data ? event.data.text() : ''
  }
  event.waitUntil(
    (async () => {
      await self.registration.showNotification(title, { body, icon: '/favicon.ico' })
      const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of clientsList) {
        client.postMessage({ type: 'fpi-push-sound', category: soundCategory })
      }
    })()
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(self.clients.openWindow('/app'))
})
