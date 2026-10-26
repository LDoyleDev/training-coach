import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BandImport from './BandImport'

const URL = 'https://coach.example.com/api/ingest/health-connect'
const NONE = {
  exists: false,
  created_at: null,
  last_used_at: null,
  last_taken_at: null,
  refused_at: null,
  refused_reason: null,
  app_version: null,
  url: URL,
}
const MADE = { ...NONE, exists: true, created_at: '2026-10-11T08:00:00Z' }
const SECRET = 'tci_' + 'ab'.repeat(16)

type Reply = { status: number; body?: unknown }

/** Fake the API: each "METHOD path" answers from its list in turn (the last one repeats). */
function serve(routes: Record<string, Reply[]>) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push(route)
      const replies = routes[route] ?? [{ status: 500 }]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]
      const body = reply.body === undefined ? null : JSON.stringify(reply.body)
      return new Response(reply.status === 204 ? null : body, { status: reply.status })
    }),
  )
  return asked
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('a secret is made and shown once', async () => {
  serve({
    'GET /api/account/ingest': [{ status: 200, body: NONE }],
    'POST /api/account/ingest': [{ status: 200, body: { ...MADE, secret: SECRET } }],
  })
  render(<BandImport />)
  expect(await screen.findByText(/It needs a secret from here/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Make a secret' }))
  expect(await screen.findByText(SECRET)).toBeInTheDocument()
  expect(screen.getByText(/it won’t be shown again/)).toBeInTheDocument()
  expect(screen.getByText('No data has arrived yet.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Make a new secret' })).toBeInTheDocument()
})

test('when data last arrived, and stopping the import', async () => {
  const asked = serve({
    'GET /api/account/ingest': [
      {
        status: 200,
        body: {
          ...MADE,
          last_used_at: '2026-10-11T09:30:00Z',
          last_taken_at: '2026-10-11T09:30:00Z',
        },
      },
    ],
    'DELETE /api/account/ingest': [{ status: 204 }],
  })
  render(<BandImport />)
  expect(await screen.findByText(/Last data arrived/)).toBeInTheDocument()
  expect(screen.queryByText(/Last sync/)).not.toBeInTheDocument()
  expect(screen.getByText(/A new secret replaces the old one/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Stop band import' }))
  expect(await screen.findByText(/can’t send band data/)).toBeInTheDocument()
  expect(asked).toContain('DELETE /api/account/ingest')
  expect(screen.queryByRole('button', { name: 'Stop band import' })).not.toBeInTheDocument()
})

test('syncs that bring nothing new show apart from data arriving', async () => {
  serve({
    'GET /api/account/ingest': [
      { status: 200, body: { ...MADE, last_used_at: '2026-10-12T09:30:00Z' } },
    ],
  })
  render(<BandImport />)
  expect(await screen.findByText(/No data has arrived yet\. Last sync/)).toBeInTheDocument()
})

test('HC Webhook is shown the address to post to', async () => {
  serve({ 'GET /api/account/ingest': [{ status: 200, body: { ...MADE, app_version: '1.9.31' } }] })
  render(<BandImport />)
  expect(await screen.findByText(URL)).toBeInTheDocument()
})

test('without a public address it says so to HC Webhook', async () => {
  const webhook = { ...MADE, app_version: '1.9.31', url: null }
  serve({ 'GET /api/account/ingest': [{ status: 200, body: webhook }] })
  render(<BandImport />)
  expect(await screen.findByText(/needs the server’s public address/)).toBeInTheDocument()
})

test('the reader, with its address built in, is shown none', async () => {
  // Review of #376: "needs a secret" above an address, or a missing-address warning, contradicted it.
  for (const url of [URL, null]) {
    serve({
      'GET /api/account/ingest': [
        { status: 200, body: { ...MADE, url, app_version: 'tc-reader/0.0.6' } },
      ],
    })
    const { unmount } = render(<BandImport />)
    expect(await screen.findByText(/It needs a secret from here/)).toBeInTheDocument()
    expect(screen.queryByText(/Address:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/public address/)).not.toBeInTheDocument()
    unmount()
  }
})

test.each([
  [401, 'Your sign-in ended.'],
  [500, "That didn't work."],
])('a failed new secret (%i) says what to do', async (status, text) => {
  serve({
    'GET /api/account/ingest': [{ status: 200, body: NONE }],
    'POST /api/account/ingest': [{ status }],
  })
  render(<BandImport />)
  fireEvent.click(await screen.findByRole('button', { name: 'Make a secret' }))
  expect(await screen.findByText(new RegExp(text))).toBeInTheDocument()
})

test('a stale sign-in that can’t be confirmed asks for the fingerprint', async () => {
  serve({
    'GET /api/account/ingest': [{ status: 200, body: NONE }],
    'POST /api/account/ingest': [{ status: 403 }],
    'POST /api/auth/passkeys/confirm/options': [{ status: 403 }],
  })
  render(<BandImport />)
  fireEvent.click(await screen.findByRole('button', { name: 'Make a secret' }))
  expect(await screen.findByText(/confirm it’s you/)).toBeInTheDocument()
})

test('a failed removal says so', async () => {
  serve({
    'GET /api/account/ingest': [{ status: 200, body: MADE }],
    'DELETE /api/account/ingest': [{ status: 500 }],
  })
  render(<BandImport />)
  fireEvent.click(await screen.findByRole('button', { name: 'Stop band import' }))
  expect(await screen.findByText(/That didn't work/)).toBeInTheDocument()
})

test('hidden when signed out or the server fails', async () => {
  serve({ 'GET /api/account/ingest': [{ status: 401 }] })
  const { container } = render(<BandImport />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})

test('a refused sync is shown with why, and the app version', async () => {
  serve({
    'GET /api/account/ingest': [
      {
        status: 200,
        body: {
          ...MADE,
          last_used_at: '2026-10-11T09:30:00Z',
          last_taken_at: '2026-10-11T09:30:00Z',
          refused_at: '2026-10-11T10:00:00Z',
          refused_reason: 'too_large',
          app_version: '1.9.22',
        },
      },
    ],
  })
  render(<BandImport />)
  expect(await screen.findByText(/Last refused sync/)).toHaveTextContent(
    'it was over 5 MB. In HC Webhook, set heart rate to 1 minute, not Full.',
  )
  expect(screen.getByText(/From HC Webhook 1\.9\.22\./)).toBeInTheDocument()
})

test('the Coach reader is named from its version, with its own advice', async () => {
  // Spec step 4 (docs/specs/android-reader.md): the sending app from its version string.
  serve({
    'GET /api/account/ingest': [
      {
        status: 200,
        body: {
          ...MADE,
          last_used_at: '2026-10-11T09:30:00Z',
          last_taken_at: '2026-10-11T09:30:00Z',
          refused_at: '2026-10-11T10:00:00Z',
          refused_reason: 'too_large',
          app_version: 'tc-reader/0.0.6',
        },
      },
    ],
    'POST /api/account/ingest': [{ status: 200, body: { ...MADE, secret: SECRET } }],
  })
  render(<BandImport />)
  expect(await screen.findByText(/From the Coach reader 0\.0\.6\./)).toBeInTheDocument()
  expect(screen.getByText(/Last refused sync/)).toHaveTextContent('after three refusals skips it')
  expect(screen.getByText(/from the Coach reader app on your phone/)).toBeInTheDocument()
  expect(screen.queryByText(/HC Webhook/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Make a new secret' }))
  expect(await screen.findByText(/paste it under Secret/)).toBeInTheDocument()
})

test('a sync HC Webhook couldn’t send as JSON says where to fix it', async () => {
  serve({
    'GET /api/account/ingest': [
      {
        status: 200,
        body: {
          ...MADE,
          refused_at: '2026-10-11T10:00:00Z',
          refused_reason: 'not_json',
          app_version: '1.9.31',
        },
      },
    ],
  })
  render(<BandImport />)
  expect(await screen.findByText(/Last refused sync/)).toHaveTextContent(
    'In HC Webhook, set the delivery format to JSON.',
  )
  expect(screen.getByText(/Health Connect Webhook app/)).toBeInTheDocument()
})

test('no refusal line without one', async () => {
  serve({ 'GET /api/account/ingest': [{ status: 200, body: MADE }] })
  render(<BandImport />)
  expect(await screen.findByText('No data has arrived yet.')).toBeInTheDocument()
  expect(screen.queryByText(/Last refused sync/)).not.toBeInTheDocument()
})
