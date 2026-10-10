import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Account from './Account'
import type { SignIns } from './api'

const webauthn = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  startRegistration: vi.fn(async () => ({ id: 'new-key' })),
  startAuthentication: vi.fn(async () => ({ id: 'my-key' })),
}))
vi.mock('@simplewebauthn/browser', () => webauthn)

const SIGN_INS: SignIns = {
  passkeys: [
    {
      id: 7,
      name: 'Pixel',
      created_at: '2026-10-09T20:00:00Z',
      last_used_at: '2026-10-10T07:00:00Z',
    },
  ],
  devices: [
    {
      id: 1,
      label: 'Pixel',
      created_at: '2026-10-09T20:00:00Z',
      last_seen_at: '2026-10-10T07:00:00Z',
      current: true,
    },
    {
      id: 2,
      label: 'Old laptop',
      created_at: '2026-10-01T20:00:00Z',
      last_seen_at: '2026-10-02T07:00:00Z',
      current: false,
    },
  ],
}

function server(signIns: SignIns | null | 'error', calls: string[] = [], stale = false) {
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${path}`)
    if (stale && path !== '/api/account/sign-ins' && !path.includes('/devices/'))
      return new Response(null, { status: 403 })
    if (path === '/api/account/sign-ins') {
      if (signIns === 'error') return new Response(null, { status: 500 })
      if (signIns === null) return new Response(null, { status: 401 })
      return new Response(JSON.stringify(signIns), { status: 200 })
    }
    if (path.endsWith('/options')) return new Response('{"challenge":"c"}', { status: 200 })
    return new Response(null, { status: 204 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

beforeEach(() => {
  webauthn.browserSupportsWebAuthn.mockReturnValue(true)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('lists passkeys and browsers, marking this one', async () => {
  server(SIGN_INS)
  render(<Account />)
  expect(await screen.findByText(/Pixel · added/)).toBeInTheDocument()
  expect(screen.getByText(/This browser/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign out Old laptop' })).toBeInTheDocument()
})

test('removing a passkey and signing out a lost browser call the API', async () => {
  const calls = server(SIGN_INS)
  render(<Account />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove passkey Pixel' }))
  expect(await screen.findByText('Passkey removed.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Sign out Old laptop' }))
  expect(await screen.findByText('That browser is signed out.')).toBeInTheDocument()
  expect(calls).toContain('DELETE /api/account/passkeys/7')
  expect(calls).toContain('DELETE /api/account/devices/2')
})

test('a passkey can be added from here', async () => {
  server({ ...SIGN_INS, passkeys: [] })
  render(<Account />)
  expect(await screen.findByText(/No passkeys yet/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Add a passkey on this device' }))
  expect(await screen.findByText('Passkey added.')).toBeInTheDocument()
})

test('a failed action says so', async () => {
  server(SIGN_INS)
  webauthn.startRegistration.mockRejectedValueOnce(new Error('cancelled'))
  render(<Account />)
  fireEvent.click(await screen.findByRole('button', { name: 'Add a passkey on this device' }))
  expect(await screen.findByText("The passkey wasn't added.")).toBeInTheDocument()
})

test('signed out, it links to sign-in', async () => {
  server(null)
  render(<Account />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/signin')
})

test('a server error is shown', async () => {
  server('error')
  render(<Account />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your sign-ins")
})

test('signing out here goes to the sign-in page', async () => {
  const calls = server(SIGN_INS)
  const assign = vi.fn()
  vi.stubGlobal('location', { ...window.location, assign })
  render(<Account />)
  fireEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/signin'))
  expect(calls).toContain('POST /api/auth/signout')
})

test('changing passkeys without a recent sign-in explains how', async () => {
  server(SIGN_INS, [], true)
  render(<Account />)
  fireEvent.click(await screen.findByRole('button', { name: 'Add a passkey on this device' }))
  expect(await screen.findByText(/needs a recent sign-in/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove passkey Pixel' }))
  expect(await screen.findByText(/needs a recent sign-in/)).toBeInTheDocument()
})
