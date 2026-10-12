import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Proposals from './Proposals'

const TOKEN = 'ab'.repeat(16)
const PROPOSAL = {
  token: TOKEN,
  kind: 'strength',
  on: '2026-10-12',
  source: 'Claude',
  summary: 'Torso + neck on Mon 12 Oct: Pull-up 8 / 8 / 7',
  expires_at: '2026-10-13T08:00:00Z',
}

type Reply = { status: number; body?: unknown }

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

const waiting = (then: unknown[] = []): Reply[] => [
  { status: 200, body: [PROPOSAL] },
  { status: 200, body: then },
]

test('it names the app as a claim and says what Save writes', async () => {
  serve({ 'GET /api/proposals': waiting() })
  render(<Proposals onSaved={vi.fn()} />)
  expect(await screen.findByText(/Pull-up 8 \/ 8 \/ 7/)).toBeInTheDocument()
  expect(screen.getByText('“Claude”')).toBeInTheDocument()
  expect(screen.getByText('Nothing is saved until you tap Save.')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Proposed by your AI' })).toBeInTheDocument()
})

test('save goes through and the page hears what was saved', async () => {
  const saved = vi.fn()
  const asked = serve({
    'GET /api/proposals': waiting(),
    [`POST /api/proposals/${TOKEN}/save`]: [
      { status: 200, body: { summary: PROPOSAL.summary, workout: true } },
    ],
  })
  render(<Proposals onSaved={saved} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  await vi.waitFor(() => expect(saved).toHaveBeenCalledWith(`Saved: ${PROPOSAL.summary}.`))
  expect(asked).toContain(`POST /api/proposals/${TOKEN}/save`)
  await vi.waitFor(() => expect(screen.queryByText(/Pull-up/)).not.toBeInTheDocument())
})

test('discard saves nothing', async () => {
  const saved = vi.fn()
  serve({
    'GET /api/proposals': waiting(),
    [`POST /api/proposals/${TOKEN}/discard`]: [{ status: 204 }],
  })
  render(<Proposals onSaved={saved} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Discard' }))
  expect(await screen.findByText('Discarded. Nothing was saved.')).toBeInTheDocument()
  expect(saved).not.toHaveBeenCalled()
})

test.each([
  [{ status: 409, body: { detail: 'already_saved' } }, 'That was already saved.'],
  [
    { status: 409, body: { detail: 'already_discarded' } },
    'That was already discarded. Nothing was saved.',
  ],
  [{ status: 404, body: { detail: 'gone' } }, /That proposal has gone/],
  [
    { status: 409, body: { detail: "today's session changed" } },
    "Not saved: today's session changed. Ask your AI again if you want it.",
  ],
  [{ status: 500 }, "That didn't work. Check your connection and try again."],
])('a save answered %o says so', async (reply, text) => {
  const saved = vi.fn()
  serve({
    'GET /api/proposals': waiting([]),
    [`POST /api/proposals/${TOKEN}/save`]: [reply],
  })
  render(<Proposals onSaved={saved} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
  expect(saved).not.toHaveBeenCalled()
})

test('a sign-in that ended says so', async () => {
  serve({
    'GET /api/proposals': waiting(),
    [`POST /api/proposals/${TOKEN}/discard`]: [{ status: 401 }],
  })
  render(<Proposals onSaved={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Discard' }))
  expect(await screen.findByRole('link', { name: /sign in/i })).toBeInTheDocument()
})

test('nothing waiting, signed out or unreachable shows nothing', async () => {
  for (const reply of [{ status: 200, body: [] }, { status: 401 }, { status: 500 }]) {
    const asked = serve({ 'GET /api/proposals': [reply] })
    const { container, unmount } = render(<Proposals onSaved={vi.fn()} />)
    await vi.waitFor(() => expect(asked).toContain('GET /api/proposals'))
    expect(container).toBeEmptyDOMElement()
    unmount()
  }
})
