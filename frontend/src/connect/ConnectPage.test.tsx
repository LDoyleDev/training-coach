import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import ConnectPage from './ConnectPage'

const webauthn = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  startRegistration: vi.fn(async () => ({ id: 'new-key' })),
  startAuthentication: vi.fn(async () => ({ id: 'my-key' })),
}))
vi.mock('@simplewebauthn/browser', () => webauthn)

const HANDLE = 'h'.repeat(43)
const CONSENT = {
  client_id: 'client-one',
  client_name: 'Claude',
  redirect_uri: 'https://claude.ai/api/mcp/auth_callback',
  redirect_host: 'claude.ai',
  scopes: [
    { scope: 'training:read', label: 'Your plan and workouts', health: false },
    { scope: 'body:read', label: 'Your body measurements (health data)', health: true },
  ],
}
const BACK = 'https://claude.ai/api/mcp/auth_callback?code=c&state=s'

type Reply = number | [number, unknown]

/** Answer each fetch by its path: a status, or a status and a JSON body. */
function server(replies: Record<string, Reply>) {
  const fetchMock = vi.fn(async (path: string, _init?: RequestInit) => {
    const reply = replies[path] ?? 500
    const [status, body] = typeof reply === 'number' ? [reply, undefined] : reply
    if (path.endsWith('/options') && status === 200) {
      return new Response(JSON.stringify({ challenge: 'c' }), { status })
    }
    return new Response(body === undefined ? null : JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function goes() {
  const assign = vi.fn()
  vi.stubGlobal('location', { ...window.location, hash: `#${HANDLE}`, assign })
  return assign
}

const sent = (fetchMock: ReturnType<typeof server>, path: string) =>
  fetchMock.mock.calls.filter(([p]) => p === path).map(([, init]) => JSON.parse(String(init?.body)))

beforeEach(() => {
  window.history.replaceState(null, '', `/connect#${HANDLE}`)
  webauthn.startAuthentication.mockResolvedValue({ id: 'my-key' })
})

afterEach(() => vi.unstubAllGlobals())

test('it names the app as a claim, where it goes back, and ticks no health data', async () => {
  server({ '/api/connect/details': [200, CONSENT] })
  render(<ConnectPage />)
  expect(await screen.findByText('“Claude”')).toBeInTheDocument()
  expect(screen.getByText(/calls itself/)).toHaveTextContent('Anyone can give an app that name')
  expect(screen.getByText('claude.ai')).toBeInTheDocument()
  expect(screen.getByRole('checkbox', { name: 'Your plan and workouts' })).toBeChecked()
  expect(
    screen.getByRole('checkbox', { name: 'Your body measurements (health data)' }),
  ).not.toBeChecked()
  expect(window.location.hash).toBe('')
})

test('allowing asks for the passkey, then goes back to the app with only what was ticked', async () => {
  const assign = goes()
  const fetchMock = server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 200,
    '/api/auth/passkeys/confirm': 204,
    '/api/connect/bind': 204,
    '/api/connect/approve': [200, { redirect: BACK }],
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('checkbox', { name: /body measurements/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Allow with your fingerprint' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(BACK))
  expect(webauthn.startAuthentication).toHaveBeenCalled()
  expect(sent(fetchMock, '/api/connect/approve')).toEqual([
    {
      handle: HANDLE,
      client_id: 'client-one',
      redirect_uri: CONSENT.redirect_uri,
      scopes: ['training:read', 'body:read'],
    },
  ])
  expect(screen.getByRole('status')).toHaveTextContent('Going back to claude.ai')
})

test('signed out, the passkey signs in first', async () => {
  const assign = goes()
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 401,
    '/api/auth/passkeys/sign-in/options': 200,
    '/api/auth/passkeys/sign-in': 204,
    '/api/connect/bind': 204,
    '/api/connect/approve': [200, { redirect: BACK }],
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Allow with your fingerprint' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(BACK))
})

test('a refused or missing passkey says what to do', async () => {
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 409,
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Allow with your fingerprint' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('a link from the bot can’t connect')
})

test('a cancelled fingerprint prompt says it did not confirm', async () => {
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 200,
  })
  webauthn.startAuthentication.mockRejectedValue(new Error('cancelled'))
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Allow with your fingerprint' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('didn’t confirm it’s you')
})

test('a stale page bound elsewhere, or a refusal, is explained', async () => {
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 200,
    '/api/auth/passkeys/confirm': 204,
    '/api/connect/bind': 409,
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Allow with your fingerprint' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This request has expired')
})

test('the server’s reason is shown when approval is refused', async () => {
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/auth/passkeys/confirm/options': 200,
    '/api/auth/passkeys/confirm': 204,
    '/api/connect/bind': 204,
    '/api/connect/approve': [400, { detail: 'Tick at least one thing to share.' }],
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Allow with your fingerprint' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Tick at least one thing')
})

test('nothing ticked can’t be allowed', async () => {
  server({ '/api/connect/details': [200, CONSENT] })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Your plan and workouts' }))
  expect(screen.getByRole('button', { name: 'Allow with your fingerprint' })).toBeDisabled()
})

test('not allowing goes back to the app with nothing', async () => {
  const assign = goes()
  server({
    '/api/connect/details': [200, CONSENT],
    '/api/connect/deny': [200, { redirect: `${CONSENT.redirect_uri}?error=access_denied` }],
  })
  render(<ConnectPage />)
  fireEvent.click(await screen.findByRole('button', { name: "Don't allow" }))
  await waitFor(() =>
    expect(assign).toHaveBeenCalledWith(`${CONSENT.redirect_uri}?error=access_denied`),
  )
})

test('an expired request, or none, says to start again', async () => {
  server({ '/api/connect/details': 404 })
  render(<ConnectPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Start again from your AI app')
})

test('a page opened without a request says to start again', async () => {
  window.history.replaceState(null, '', '/connect')
  server({})
  render(<ConnectPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Start again from your AI app')
})

test('a server it cannot reach is said plainly', async () => {
  server({ '/api/connect/details': 500 })
  render(<ConnectPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't reach the server")
})
