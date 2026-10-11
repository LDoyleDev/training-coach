import { beforeAll, beforeEach, expect, test, vi } from 'vitest'

/** The worker's world: its listeners, a cache store, the network. */
type Handler = (event: Record<string, unknown>) => void
const handlers: Record<string, Handler> = {}
const store = new Map<string, Map<string, Response>>()
const worker = {
  location: { origin: 'https://coach.example' },
  addEventListener: (type: string, handler: Handler) => {
    handlers[type] = handler
  },
  skipWaiting: vi.fn(async () => undefined),
  clients: { claim: vi.fn(async () => undefined) },
}
const key = (request: string | { url: string }) =>
  new URL(typeof request === 'string' ? request : request.url, worker.location.origin).pathname
const caches = {
  open: vi.fn(async (name: string) => {
    const cache = store.get(name) ?? new Map<string, Response>()
    store.set(name, cache)
    return {
      addAll: vi.fn(async (urls: string[]) =>
        urls.forEach((u) => cache.set(key(u), new Response(u))),
      ),
      put: vi.fn(async (request: { url: string }, response: Response) => {
        cache.set(key(request), response)
      }),
    }
  }),
  keys: vi.fn(async () => [...store.keys()]),
  delete: vi.fn(async (name: string) => store.delete(name)),
  match: vi.fn(async (request: string | { url: string }) => {
    for (const cache of store.values()) {
      const hit = cache.get(key(request))
      if (hit) return hit
    }
    return undefined
  }),
}
const network = vi.fn<(request: unknown) => Promise<Response>>()

beforeAll(async () => {
  vi.stubGlobal('self', worker)
  vi.stubGlobal('caches', caches)
  vi.stubGlobal('fetch', network)
  await import('./sw.js')
})

beforeEach(() => {
  store.clear()
  network.mockReset()
})

/** Dispatches a fetch; the response the worker gave, or null when it left it to the browser. */
async function get(path: string, init: { method?: string; mode?: string } = {}) {
  const url = path.startsWith('http') ? path : `${worker.location.origin}${path}`
  const respondWith = vi.fn<(r: Promise<Response>) => void>()
  handlers.fetch({ request: { url, method: init.method ?? 'GET', mode: init.mode }, respondWith })
  return respondWith.mock.calls.length ? await respondWith.mock.calls[0][0] : null
}

async function installed() {
  let done: Promise<unknown> = Promise.resolve()
  handlers.install({ waitUntil: (p: Promise<unknown>) => (done = p) })
  await done
}

test('installing caches the app shell and takes over at once', async () => {
  await installed()
  const [name] = store.keys()
  expect(name).toBe('shell-dev')
  expect([...store.get(name)!.keys()]).toEqual(['/index.html'])
  expect(worker.skipWaiting).toHaveBeenCalled()
})

test('a new version drops the old caches', async () => {
  store.set('shell-old', new Map())
  await installed()
  let done: Promise<unknown> = Promise.resolve()
  handlers.activate({ waitUntil: (p: Promise<unknown>) => (done = p) })
  await done
  expect([...store.keys()]).toEqual(['shell-dev'])
  expect(worker.clients.claim).toHaveBeenCalled()
})

test('the API, sign-in and health check always go to the network, never the cache', async () => {
  await installed()
  expect(await get('/api/home')).toBeNull()
  expect(await get('/api/auth/me')).toBeNull()
  expect(await get('/api/auth/redeem', { method: 'POST' })).toBeNull()
  expect(await get('/healthz')).toBeNull()
  expect(await get('/api/export', { mode: 'navigate' })).toBeNull()
  expect(await get('https://elsewhere.example/assets/x.js')).toBeNull()
  expect(await get('/icons/icon-192.png')).toBeNull()
  expect(caches.match).not.toHaveBeenCalledWith(
    expect.objectContaining({ url: expect.stringContaining('/api/') }),
  )
})

test('pages come from the network while online', async () => {
  await installed()
  network.mockResolvedValue(new Response('fresh page'))
  expect(await (await get('/session', { mode: 'navigate' }))!.text()).toBe('fresh page')
})

test('offline, a page opens the cached app', async () => {
  await installed()
  network.mockRejectedValue(new TypeError('offline'))
  expect(await (await get('/progress', { mode: 'navigate' }))!.text()).toBe('/index.html')
})

test('offline with nothing cached, a page says so', async () => {
  network.mockRejectedValue(new TypeError('offline'))
  expect(await (await get('/', { mode: 'navigate' }))!.text()).toContain("You're offline")
})

test('hashed assets are cached the first time and then served from the cache', async () => {
  network.mockResolvedValueOnce(new Response('js'))
  expect(await (await get('/assets/index-abc.js'))!.text()).toBe('js')
  await vi.waitFor(() => expect(store.get('shell-dev')?.has('/assets/index-abc.js')).toBe(true))
  expect(await (await get('/assets/index-abc.js'))!.text()).toBe('js')
  expect(network).toHaveBeenCalledOnce()
})

test('a failed asset is not cached', async () => {
  network.mockResolvedValue(new Response('gone', { status: 404 }))
  expect((await get('/assets/old.js'))!.status).toBe(404)
  expect(store.size).toBe(0)
})
