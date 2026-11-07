import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import People from './People'

type Reply = { status: number; body?: unknown }
const PEOPLE = {
  members: [{ id: 2, label: 'Mum', joined: '2026-11-07' }],
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

test('removing a member asks if they were told, needs the word, and says it is done', async () => {
  const asked = serve({
    'GET /api/people': [
      { status: 200, body: PEOPLE },
      { status: 200, body: { ...PEOPLE, members: [] } },
    ],
    'POST /api/people/2/remove': { status: 204 },
  })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Mum' }))
  expect(screen.getByText(/Have you told Mum and offered them their export/)).toBeInTheDocument()
  const go = screen.getByRole('button', { name: 'Remove Mum' })
  expect(go).toBeDisabled()
  fireEvent.change(screen.getByRole('textbox', { name: /Type remove/ }), {
    target: { value: 'remove' },
  })
  fireEvent.click(go)
  expect(await screen.findByRole('status')).toHaveTextContent('Removed.')
  expect(asked).toContain('POST /api/people/2/remove {"confirm":"remove"}')
  expect(await screen.findByText(/0 of 5 members/)).toBeInTheDocument()
})

test('keeping them closes the question without removing anyone', async () => {
  const asked = serve({ 'GET /api/people': { status: 200, body: PEOPLE } })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Mum' }))
  fireEvent.click(screen.getByRole('button', { name: 'Keep them' }))
  expect(screen.queryByRole('textbox', { name: /Type remove/ })).not.toBeInTheDocument()
  expect(asked.some((a) => a.includes('/remove'))).toBe(false)
})

test('someone already gone, or a stale sign-in, says so', async () => {
  serve({
    'GET /api/people': { status: 200, body: PEOPLE },
    'POST /api/people/2/remove': [{ status: 404 }, { status: 403 }],
  })
  render(<People />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Mum' }))
  fireEvent.change(screen.getByRole('textbox', { name: /Type remove/ }), {
    target: { value: 'remove' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Remove Mum' }))
  expect(await screen.findByRole('status')).toHaveTextContent('They had already gone.')
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Mum' }))
  fireEvent.change(screen.getByRole('textbox', { name: /Type remove/ }), {
    target: { value: 'remove' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Remove Mum' }))
  expect(await screen.findByText(/removing someone needs you to confirm/)).toBeInTheDocument()
})
