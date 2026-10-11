/*
 * The service worker (D3): what lets the phone install the app, and opens it when offline.
 *
 * The build (vite.config.ts) fills in VERSION and SHELL, so every deploy changes this file and
 * the browser installs the new worker; it takes over at once and drops the old cache, and the
 * next page you open is the new version.
 *
 * - /api/* and /healthz: always the network, never cached (personal data, sign-in).
 * - Pages: the network first, so sign-in and new deploys are never stale; offline, the cached
 *   app, which then says it is offline.
 * - /assets/*: hashed by the build, so a cached copy is always right.
 */
const VERSION = 'dev'
const SHELL = ['/index.html']

const CACHE = `shell-${VERSION}`

const OFFLINE = `<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Training Coach</title>
<body style="font-family: system-ui, sans-serif; margin: 2rem 1rem; color: #22282d; background: #f1f2ef">
<h1>You're offline</h1>
<p>Training Coach needs a connection. Check your Wi-Fi or mobile data, then try again.</p>
<p><a href="/">Try again</a></p>
</body></html>`

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

async function page(request) {
  try {
    return await fetch(request)
  } catch {
    const shell = await caches.match('/index.html')
    return shell ?? new Response(OFFLINE, { headers: { 'Content-Type': 'text/html' } })
  }
}

async function asset(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) {
    const copy = response.clone()
    caches.open(CACHE).then((cache) => cache.put(request, copy))
  }
  return response
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz') return // network only
  if (request.mode === 'navigate') event.respondWith(page(request))
  else if (url.pathname.startsWith('/assets/')) event.respondWith(asset(request))
})
