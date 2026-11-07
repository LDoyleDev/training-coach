import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Leave from './Leave'

type Reply = { status: number; body?: unknown }

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

const MEMBER = { status: 200, body: { user_id: 2, role: 'member' } }

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

test.each([
  ['the owner', { status: 200, body: { user_id: 1, role: 'admin' } }],
  ['signed out', { status: 401 }],
  ['a failure', { status: 500 }],
])('hidden for %s', async (_who, reply) => {
  serve({ 'GET /api/auth/me': reply })
  const { container } = render(<Leave />)
  await new Promise((r) => setTimeout(r, 0))
  expect(container).toBeEmptyDOMElement()
})

test('a member leaves once they type the word, and goes to sign-in', async () => {
  const asked = serve({ 'GET /api/auth/me': MEMBER, 'POST /api/account/leave': { status: 204 } })
  const assign = vi.fn()
  vi.stubGlobal('location', { ...window.location, assign })
  render(<Leave />)
  const go = await screen.findByRole('button', { name: 'Leave Training Coach' })
  expect(go).toBeDisabled()
  fireEvent.change(screen.getByRole('textbox', { name: /Type leave/ }), {
    target: { value: 'leave' },
  })
  fireEvent.click(go)
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/signin'))
  expect(asked).toContain('POST /api/account/leave {"confirm":"leave"}')
})

test('a failure or a stale sign-in says nothing was deleted, or what to do', async () => {
  serve({
    'GET /api/auth/me': MEMBER,
    'POST /api/account/leave': [{ status: 500 }, { status: 403 }],
  })
  render(<Leave />)
  fireEvent.change(await screen.findByRole('textbox', { name: /Type leave/ }), {
    target: { value: 'leave' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Leave Training Coach' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Nothing was deleted')
  fireEvent.click(screen.getByRole('button', { name: 'Leave Training Coach' }))
  expect(await screen.findByText(/leaving needs you to confirm/)).toBeInTheDocument()
})
