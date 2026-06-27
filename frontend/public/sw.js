/* EGI service worker (plan-11) — Web Push receiver for the PWA.
 *
 * Minimal by design: it shows incoming push notifications and focuses/opens the
 * app when one is clicked. The push payload is JSON: { title, body }.
 */

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch (e) {
    data = { title: 'EGI', body: event.data ? event.data.text() : '' }
  }
  const title = data.title || 'EGI'
  const options = {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const win of wins) {
        if ('focus' in win) return win.focus()
      }
      if (clients.openWindow) return clients.openWindow(url)
    })
  )
})
