import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import People from './People'

type Reply = { status: number; body?: unknown }
const PEOPLE = {
  members: [{ label: 'Mum', joined: '2026-11-07' }],
  invites: [
    { id: 4, label: 'Sam', created_at: '2026-11-07T08:00:00Z', expires_at: '2026-11-10T08:00:00Z' },
  ],
  max_members: 5,
}

function serve(routes: Record<string, Reply | Reply[]>) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push(`${route} ${typeof init?.body === 'string' ? init.body : ''}`.trim())
      const found = routes[route]
      const reply = (Array.isArray(found)
        ? found.length > 1
          ? found.shift()
          : found[0]
        : found) ?? {
        status: 500,
      }
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status: reply.status,
      })
    }),
  )
  return asked
}

afterEach(() => vi.unstubAllGlobals())

test.each([401, 403, 404])('hidden when the answer is %i', async (status) => {
  serve({ 'GET /api/people': { status } })
  const { container } = render(<People />)
  await new Promise((r) => setTimeout(r, 0))
  expect(container).toBeEmptyDOMElement()
})

test('lists members by name and join day, and open invites', async () => {
  serve({ 'GET /api/people': { status: 200, body: PEOPLE } })
  render(<People />)
  expect(await screen.findByText(/1 of 5 members/)).toBeInTheDocument()
  expect(screen.getByText('Mum, joined 7 Nov')).toBeInTheDocument()
  expect(screen.getByText('Sam, until 10 Nov')).toBeInTheDocument()
})

test('making an invite shows its link once', async () => {
  const asked = serve({
    'GET /api/people': { status: 200, body: { ...PEOPLE, invites: [] } },
    'POST /api/invites': {
      status: 201,
      body: { token: 'tok123', expires_at: '2026-11-10T08:00:00Z' },
    },
  })
  render(<People />)
  fireEvent.change(await screen.findByRole('textbox', { name: /Who is it for/ }), {
    target: { value: ' Dad ' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Make an invite' }))
  expect(await screen.findByRole('textbox', { name: 'Invite link' })).toHaveValue(
    `${window.location.origin}/join#tok123`,
  )
  expect(asked).toContain('POST /api/invites {"label":"Dad"}')
})

test('a full house offers no invite, and a refusal says why', async () => {
  serve({ 'GET /api/people': { status: 200, body: { ...PEOPLE, max_members: 2 } } })
  render(<People />)
  await screen.findByText(/1 of 2 members/)
  expect(screen.queryByRole('button', { name: 'Make an invite' })).not.toBeInTheDocument()
})

test('the server saying full is shown', async () => {
  serve({
    'GET /api/people': { status: 200, body: { ...PEOPLE, invites: [] } },
    'POST /api/invites': { status: 409 },
  })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Make an invite' }))
  expect(await screen.findByRole('status')).toHaveTextContent('no room for another member')
})

test('revoking an invite says so, or that it was used already', async () => {
  serve({
    'GET /api/people': { status: 200, body: PEOPLE },
    'DELETE /api/invites/4': [{ status: 204 }, { status: 404 }],
  })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Revoke Sam' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Invite revoked.')
  fireEvent.click(screen.getByRole('button', { name: 'Revoke Sam' }))
  expect(await screen.findByText('That invite was already used.')).toBeInTheDocument()
})

test('a lost sign-in or a failure says what to do', async () => {
  serve({
    'GET /api/people': { status: 200, body: { ...PEOPLE, invites: [] } },
    'POST /api/invites': [{ status: 401 }, { status: 500 }],
  })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Make an invite' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Your sign-in ended')
  fireEvent.click(screen.getByRole('button', { name: 'Make an invite' }))
  expect(await screen.findByText(/That didn't work/)).toBeInTheDocument()
})
