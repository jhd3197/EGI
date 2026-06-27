// Web Push (VAPID) subscription helper for the PWA (plan-11).
//
// Registers the service worker, subscribes the browser's PushManager using the
// server's VAPID public key, and POSTs the subscription to /push/subscribe. The
// `topic` is the operation id the device wants alerts for (null = global).
//
// Everything degrades gracefully: if the browser lacks push support, or the
// server has no VAPID key configured, the helpers return a clear status instead
// of throwing, so the UI can show "unavailable" without breaking.

const API_URL =
  (typeof window !== 'undefined' && localStorage.getItem('egi_api_url')) || ''

export function pushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i)
  return output
}

async function registerServiceWorker() {
  return navigator.serviceWorker.register(`${API_URL}/sw.js`)
}

export async function getPushState() {
  if (!pushSupported()) return { supported: false, subscribed: false }
  try {
    const reg = await navigator.serviceWorker.getRegistration()
    const sub = reg ? await reg.pushManager.getSubscription() : null
    return { supported: true, subscribed: !!sub }
  } catch {
    return { supported: true, subscribed: false }
  }
}

export async function enablePush(topic = null) {
  if (!pushSupported()) return { ok: false, reason: 'unsupported' }

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return { ok: false, reason: 'denied' }

  const keyRes = await fetch(`${API_URL}/push/vapid-public-key`)
  const { key } = await keyRes.json()
  if (!key) return { ok: false, reason: 'server-not-configured' }

  const reg = await registerServiceWorker()
  await navigator.serviceWorker.ready
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  })

  const json = sub.toJSON()
  const res = await fetch(`${API_URL}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      kind: 'webpush',
      endpoint: sub.endpoint,
      p256dh: json.keys?.p256dh,
      auth: json.keys?.auth,
      topic,
    }),
  })
  if (!res.ok) return { ok: false, reason: 'server-error' }
  return { ok: true }
}

export async function disablePush() {
  if (!pushSupported()) return { ok: false, reason: 'unsupported' }
  const reg = await navigator.serviceWorker.getRegistration()
  const sub = reg ? await reg.pushManager.getSubscription() : null
  if (!sub) return { ok: true }
  await fetch(`${API_URL}/push/unsubscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint: sub.endpoint }),
  })
  await sub.unsubscribe()
  return { ok: true }
}
