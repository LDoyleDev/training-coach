import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CategoryConsent, ConsentCategory, Consents } from '../api'
import Consented from './Consented'

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

const ALL: ConsentCategory[] = ['body', 'daily_check', 'band', 'walkthrough']
const entry = (category: ConsentCategory, open: boolean): CategoryConsent => ({
  category,
  version: 1,
  open,
  answer: open ? 'given' : null,
  at: open ? '2026-11-08T09:00:00Z' : null,
})
const member = (...open: ConsentCategory[]): Consents => ({
  asked: true,
  categories: ALL.map((c) => entry(c, open.includes(c))),
})
const OWNER: Consents = { asked: false, categories: ALL.map((c) => entry(c, true)) }

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const tick = () => act(() => new Promise((r) => setTimeout(r, 0)))

function body() {
  return render(
    <Consented category="body">
      <p>the measurements</p>
    </Consented>,
  )
}

test('a member who hasn’t said yes sees the card instead of the page', async () => {
  serve({ 'GET /api/consents': { status: 200, body: member('band') } })
  body()
  expect(
    await screen.findByRole('heading', { name: 'Keep your measurements and photos?' }),
  ).toBeInTheDocument()
  expect(screen.getByText(/This is health data/)).toBeInTheDocument()
  expect(screen.getByText(/withdraw at any time on Account/)).toBeInTheDocument()
  expect(screen.getByText(/private test for invited family and friends/)).toBeInTheDocument()
  expect(screen.queryByText('the measurements')).not.toBeInTheDocument()
})

test.each([
  ['the owner', { status: 200, body: OWNER }],
  ['a member who said yes', { status: 200, body: member('body') }],
  ['signed out', { status: 401 }],
  ['a failure', { status: 500 }],
  ['an unexpected answer', { status: 200, body: [] }],
])('%s sees the page, never the card', async (_who, reply) => {
  serve({ 'GET /api/consents': reply })
  const { container } = body()
  expect(container).toBeEmptyDOMElement() // nothing while it's read
  expect(await screen.findByText('the measurements')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Yes, keep it' })).not.toBeInTheDocument()
})

test('“Yes, keep it” gives consent to the wording shown, and opens the page', async () => {
  const asked = serve({
    'GET /api/consents': { status: 200, body: member() },
    'PUT /api/consents/body': { status: 200, body: member('body') },
  })
  body()
  fireEvent.click(await screen.findByRole('button', { name: 'Yes, keep it' }))
  expect(await screen.findByText('the measurements')).toBeInTheDocument()
  expect(asked).toContain('PUT /api/consents/body {"version":1}')
})

test('one yes opens every part of the page that waits for it, read once', async () => {
  const asked = serve({
    'GET /api/consents': { status: 200, body: member() },
    'PUT /api/consents/band': { status: 200, body: member('band') },
  })
  render(
    <>
      <Consented category="band">
        <p>band import</p>
      </Consented>
      <Consented category="band" quiet>
        <p>heart-rate zones</p>
      </Consented>
    </>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Yes, keep it' }))
  expect(await screen.findByText('band import')).toBeInTheDocument()
  expect(screen.getByText('heart-rate zones')).toBeInTheDocument()
  expect(asked.filter((a) => a === 'GET /api/consents')).toHaveLength(1)
})

test('“Not now” leaves it off, with a way to change your mind', async () => {
  const asked = serve({ 'GET /api/consents': { status: 200, body: member() } })
  body()
  fireEvent.click(await screen.findByRole('button', { name: 'Not now' }))
  expect(screen.getByText(/Measurements and photos stay off/)).toBeInTheDocument()
  expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Turn it on' }))
  expect(screen.getByRole('heading', { name: /Keep your measurements/ })).toBeInTheDocument()
  expect(asked.some((a) => a.startsWith('PUT'))).toBe(false)
})

test.each([
  [{ status: 401 }, 'Your sign-in ended. Sign in again, then retry.'],
  [{ status: 409 }, /wording changed since the page opened/],
  [{ status: 500 }, /check your connection/i],
])('a yes that fails says why and can be tried again (%o)', async (reply, text) => {
  serve({
    'GET /api/consents': { status: 200, body: member() },
    'PUT /api/consents/body': reply,
  })
  body()
  fireEvent.click(await screen.findByRole('button', { name: 'Yes, keep it' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
  expect(screen.getByRole('button', { name: 'Yes, keep it' })).toBeEnabled()
  expect(screen.queryByText('the measurements')).not.toBeInTheDocument()
})

test('a quiet part shows nothing until it’s open, and asks nothing', async () => {
  serve({ 'GET /api/consents': { status: 200, body: member() } })
  const { container } = render(
    <Consented category="band" quiet>
      <p>from your band</p>
    </Consented>,
  )
  await tick()
  expect(container).toBeEmptyDOMElement()
})
