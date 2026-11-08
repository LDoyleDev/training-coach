import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CategoryConsent, Consents as View } from '../api'
import Consents from './Consents'

const webauthn = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  startRegistration: vi.fn(async () => ({ id: 'new-key' })),
  startAuthentication: vi.fn(async () => ({ id: 'my-key' })),
}))
vi.mock('@simplewebauthn/browser', () => webauthn)

type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply | Reply[]>) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push(route)
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

const BODY: CategoryConsent = {
  category: 'body',
  version: 1,
  open: true,
  answer: 'given',
  at: '2026-11-08T09:00:00Z',
}
const MEMBER: View = {
  asked: true,
  categories: [
    BODY,
    {
      category: 'daily_check',
      version: 1,
      open: false,
      answer: 'withdrawn',
      at: '2026-11-07T09:00:00Z',
    },
    { category: 'band', version: 1, open: false, answer: 'given', at: '2026-11-01T09:00:00Z' },
    { category: 'walkthrough', version: 1, open: false, answer: null, at: null },
  ],
}
const WITHDRAWN: View = {
  ...MEMBER,
  categories: [
    { ...BODY, open: false, answer: 'withdrawn', at: '2026-11-09T09:00:00Z' },
    ...MEMBER.categories.slice(1),
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const item = (name: string) => screen.getByText(name).closest('li') as HTMLElement

test.each([
  ['the owner', { status: 200, body: { ...MEMBER, asked: false } }],
  ['signed out', { status: 401 }],
  ['a failure', { status: 500 }],
])('hidden for %s', async (_who, reply) => {
  serve({ 'GET /api/consents': reply })
  const { container } = render(<Consents />)
  await new Promise((r) => setTimeout(r, 0))
  expect(container).toBeEmptyDOMElement()
})

test('a member sees each category on or off, with its date', async () => {
  serve({ 'GET /api/consents': { status: 200, body: MEMBER } })
  render(<Consents />)
  expect(await screen.findByRole('heading', { name: "What you've agreed to" })).toBeInTheDocument()
  expect(item('Measurements and photos')).toHaveTextContent('On since 8 Nov 2026')
  expect(item('Daily check')).toHaveTextContent('Off since 7 Nov 2026')
  expect(item('Band data and heart rate')).toHaveTextContent('the wording changed')
  expect(item('Walk-through answers')).toHaveTextContent('Off: not asked yet')
  // Withdraw is beside what was given, and nothing else.
  expect(screen.getByRole('button', { name: 'Withdraw Measurements and photos' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Withdraw Band data and heart rate' })).toBeVisible()
  expect(screen.getAllByRole('button', { name: /^Withdraw / })).toHaveLength(2)
})

test('withdrawing says what it deletes first, and “Keep it” deletes nothing', async () => {
  const asked = serve({ 'GET /api/consents': { status: 200, body: MEMBER } })
  render(<Consents />)
  fireEvent.click(await screen.findByRole('button', { name: 'Withdraw Measurements and photos' }))
  const row = item('Measurements and photos')
  expect(row).toHaveTextContent(/deletes every measurement and photo.*It can't be undone/)
  fireEvent.click(within(row).getByRole('button', { name: 'Keep it' }))
  expect(screen.queryByRole('button', { name: 'Withdraw and delete' })).not.toBeInTheDocument()
  expect(asked).not.toContain('DELETE /api/consents/body')
})

test('a confirmed withdrawal deletes it and shows it off', async () => {
  const asked = serve({
    'GET /api/consents': { status: 200, body: MEMBER },
    'DELETE /api/consents/body': { status: 200, body: WITHDRAWN },
  })
  render(<Consents />)
  fireEvent.click(await screen.findByRole('button', { name: 'Withdraw Measurements and photos' }))
  fireEvent.click(screen.getByRole('button', { name: 'Withdraw and delete' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Measurements and photos: withdrawn and deleted.',
  )
  expect(item('Measurements and photos')).toHaveTextContent('Off since 9 Nov 2026')
  expect(asked).toContain('DELETE /api/consents/body')
})

test('an old sign-in asks for the fingerprint once, then withdraws', async () => {
  const asked = serve({
    'GET /api/consents': { status: 200, body: MEMBER },
    'DELETE /api/consents/body': [{ status: 403 }, { status: 200, body: WITHDRAWN }],
    'POST /api/auth/passkeys/confirm/options': { status: 200, body: { challenge: 'c' } },
    'POST /api/auth/passkeys/confirm': { status: 204 },
  })
  render(<Consents />)
  fireEvent.click(await screen.findByRole('button', { name: 'Withdraw Measurements and photos' }))
  fireEvent.click(screen.getByRole('button', { name: 'Withdraw and delete' }))
  expect(await screen.findByRole('status')).toHaveTextContent('withdrawn and deleted')
  expect(webauthn.startAuthentication).toHaveBeenCalled()
  expect(asked.filter((a) => a === 'DELETE /api/consents/body')).toHaveLength(2)
})

test.each([
  [[{ status: 403 }], /withdrawing needs you to confirm it’s you/], // no passkey to confirm with
  [[{ status: 401 }], 'Your sign-in ended. Sign in again, then retry.'],
  [[{ status: 500 }], /Nothing was deleted/],
])('a withdrawal that fails says why (%o)', async (replies, text) => {
  serve({
    'GET /api/consents': { status: 200, body: MEMBER },
    'DELETE /api/consents/body': replies,
    'POST /api/auth/passkeys/confirm/options': { status: 409 },
  })
  render(<Consents />)
  fireEvent.click(await screen.findByRole('button', { name: 'Withdraw Measurements and photos' }))
  fireEvent.click(screen.getByRole('button', { name: 'Withdraw and delete' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
  expect(item('Measurements and photos')).toHaveTextContent('On since')
  expect(screen.getByRole('button', { name: 'Withdraw and delete' })).toBeEnabled()
})
