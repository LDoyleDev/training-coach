import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import AiComments from './AiComments'

const NONE = {
  available: true,
  connected: false,
  ends_in: null,
  enabled: false,
  body: false,
  readiness: false,
  failed: false,
}
const STORED = { ...NONE, connected: true, ends_in: '4f2a', enabled: true }
const KEY = 'gsk_' + 'a'.repeat(48) + '4f2a'

type Reply = { status: number; body?: unknown }

/** Fake the API: each "METHOD path" answers from its list in turn (the last one repeats). */
function serve(routes: Record<string, Reply[]>) {
  const asked: { route: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push({ route, body: init?.body ? JSON.parse(String(init.body)) : undefined })
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

test('a new key is checked, saved and never shown again', async () => {
  const asked = serve({
    'GET /api/account/ai': [{ status: 200, body: NONE }],
    'PUT /api/account/ai/key': [{ status: 200, body: STORED }],
  })
  render(<AiComments />)
  const field = await screen.findByLabelText(/Groq API key/)
  expect(field).toHaveAttribute('type', 'password')
  fireEvent.change(field, { target: { value: ` ${KEY} ` } })
  fireEvent.click(screen.getByRole('button', { name: 'Check and save the key' }))
  expect(await screen.findByText(/stored encrypted and won’t be shown again/)).toBeInTheDocument()
  expect(asked[1]).toEqual({ route: 'PUT /api/account/ai/key', body: { key: KEY } })
  expect(screen.getByText('…4f2a')).toBeInTheDocument()
  expect(screen.getByLabelText('Replace with a new Groq key')).toHaveValue('')
  expect(document.body.textContent).not.toContain(KEY)
})

test.each([
  [400, "Groq didn't accept that key."],
  [422, "Groq didn't accept that key."],
  [503, "Couldn't reach Groq"],
  [403, 'Sign in again to add a key'],
  [401, 'Your sign-in ended'],
  [500, "That didn't work."],
])('a key answered %i says why', async (status, message) => {
  serve({
    'GET /api/account/ai': [{ status: 200, body: NONE }],
    'PUT /api/account/ai/key': [{ status }],
  })
  render(<AiComments />)
  fireEvent.change(await screen.findByLabelText(/Groq API key/), { target: { value: KEY } })
  fireEvent.click(screen.getByRole('button', { name: 'Check and save the key' }))
  expect(await screen.findByText(message, { exact: false })).toBeInTheDocument()
})

test('choices, test and remove', async () => {
  const asked = serve({
    'GET /api/account/ai': [{ status: 200, body: STORED }],
    'PUT /api/account/ai': [{ status: 200, body: { ...STORED, body: true } }],
    'POST /api/account/ai/test': [{ status: 204 }, { status: 400 }],
    'DELETE /api/account/ai/key': [{ status: 204 }],
  })
  render(<AiComments />)
  fireEvent.click(await screen.findByLabelText('Comments may see body measurements (health data)'))
  await vi.waitFor(() =>
    expect(screen.getByLabelText('Comments may see body measurements (health data)')).toBeChecked(),
  )
  expect(asked[1].body).toEqual({ enabled: true, body: true, readiness: false })
  fireEvent.click(screen.getByRole('button', { name: 'Test the key' }))
  expect(await screen.findByText('The key works.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Test the key' }))
  expect(await screen.findByText(/didn't accept that key/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove the key' }))
  expect(await screen.findByText(/^Removed\./)).toBeInTheDocument()
  expect(screen.queryByText('…4f2a')).not.toBeInTheDocument()
  expect(screen.getByLabelText(/Groq API key/)).toBeInTheDocument()
})

test('a key that stopped working says so', async () => {
  serve({ 'GET /api/account/ai': [{ status: 200, body: { ...STORED, failed: true } }] })
  render(<AiComments />)
  expect(await screen.findByText(/stopped working/)).toBeInTheDocument()
})

test('failed changes say so', async () => {
  serve({
    'GET /api/account/ai': [{ status: 200, body: STORED }],
    'PUT /api/account/ai': [{ status: 401 }],
    'POST /api/account/ai/test': [{ status: 500 }],
    'DELETE /api/account/ai/key': [{ status: 500 }],
  })
  render(<AiComments />)
  fireEvent.click(await screen.findByLabelText('Send me AI comments'))
  expect(await screen.findByText(/sign-in ended/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Test the key' }))
  expect(await screen.findByText(/That didn't work/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove the key' }))
  await vi.waitFor(() => expect(screen.getByText('…4f2a')).toBeInTheDocument())
})

test('not set up on the server: no key field', async () => {
  serve({ 'GET /api/account/ai': [{ status: 200, body: { ...NONE, available: false } }] })
  render(<AiComments />)
  expect(await screen.findByText(/aren’t set up on this server/)).toBeInTheDocument()
  expect(screen.queryByLabelText(/Groq API key/)).not.toBeInTheDocument()
})

test.each([401, 500])('hidden when the status answers %i', async (status) => {
  serve({ 'GET /api/account/ai': [{ status }] })
  const { container } = render(<AiComments />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})
