import type { AxiosInstance } from 'axios'

/** Decode VAPID public key (base64url) for PushManager.subscribe */
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

/** Request notification permission, register SW, POST subscription to API. Returns false if skipped or denied. */
export async function subscribePushWithApi(api: AxiosInstance): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false
  const { data } = await api.get<{ public_key: string }>('/notifications/vapid-public-key')
  if (!data?.public_key) return false

  const reg = await navigator.serviceWorker.register('/sw.js')
  await reg.update()
  let perm: NotificationPermission = 'denied'
  try {
    perm = await Notification.requestPermission()
  } catch {
    return false
  }
  if (perm !== 'granted') return false

  const key = urlBase64ToUint8Array(data.public_key)
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: key as BufferSource,
  })
  const json = sub.toJSON()
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) return false
  await api.post('/notifications/push-subscription', {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
  })
  return true
}
