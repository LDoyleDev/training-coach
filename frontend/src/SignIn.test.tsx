import { fireEvent, render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { nextPage } from './next'
import SignIn from './SignIn'

const webauthn = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  startRegistration: vi.fn(async () => ({ id: 'new-key' })),
  startAuthentication: vi.fn(async () => ({ id: 'my-key' })),
}))
vi.mock('@simplewebauthn/browser', () => webauthn)

const TOKEN = 'a'.repeat(43)

/** Catch navigation: jsdom can't leave the page. */
function goes() {
  const assign = vi.fn()
  vi.stubGlobal('location', { ...window.location, assign })
  return assign
}

/** Answer each fetch by its path: a status, and JSON for ceremony options. */
function server(statuses: Record<string, number>) {
  const fetchMock = vi.fn(async (path: string) => {
    const status = statuses[path] ?? 500
    if (path.endsWith('/options') && status === 200) {
      return new Response(JSON.stringify({ challenge: 'c' }), { status })
    }
    return new Response(null, { status })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  window.history.replaceState(null, '', `/signin#${TOKEN}`)
  webauthn.browserSupportsWebAuthn.mockReturnValue(true)
  webauthn.startRegistration.mockResolvedValue({ id: 'new-key' })
  webauthn.startAuthentication.mockResolvedValue({ id: 'my-key' })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('a fresh link signs in and leaves no token in the address bar', async () => {
  const fetchMock = server({ '/api/auth/redeem': 204 })
  render(<SignIn />)
  expect(await screen.findByText("You're signed in on this device.")).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/')
  expect(window.location.hash).toBe('')
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/auth/redeem',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ token: TOKEN }) }),
  )
})

test('after a link, a passkey can be added', async () => {
  server({
    '/api/auth/redeem': 204,
    '/api/auth/passkeys/register/options': 200,
    '/api/auth/passkeys/register': 204,
  })
  render(<SignIn />)
  fireEvent.click(await screen.findByRole('button', { name: 'Use your fingerprint next time' }))
  expect(await screen.findByText(/Passkey added/)).toBeInTheDocument()
  expect(webauthn.startRegistration).toHaveBeenCalledWith({ optionsJSON: { challenge: 'c' } })
})

test('a cancelled or refused passkey says it was not added', async () => {
  server({ '/api/auth/redeem': 204, '/api/auth/passkeys/register/options': 200 })
  webauthn.startRegistration.mockRejectedValue(new Error('cancelled'))
  render(<SignIn />)
  fireEvent.click(await screen.findByRole('button', { name: 'Use your fingerprint next time' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("The passkey wasn't added")
})

test('without passkey support no passkey is offered', async () => {
  webauthn.browserSupportsWebAuthn.mockReturnValue(false)
  server({ '/api/auth/redeem': 204 })
  render(<SignIn />)
  expect(await screen.findByText("You're signed in on this device.")).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('a used or expired link says how to get a new one', async () => {
  server({ '/api/auth/redeem': 401 })
  render(<SignIn />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Send /login to the bot')
})

test('a server failure is not mistaken for a bad link', async () => {
  server({ '/api/auth/redeem': 500 })
  render(<SignIn />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't reach the server")
})

test('the link is posted once, even when React runs the effect twice', async () => {
  const fetchMock = server({ '/api/auth/redeem': 204 })
  render(
    <StrictMode>
      <SignIn />
    </StrictMode>,
  )
  expect(await screen.findByText("You're signed in on this device.")).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

test('without a link, sign in with a fingerprint and go back where you were', async () => {
  window.history.replaceState(null, '', '/signin?next=/account')
  const assign = goes()
  server({ '/api/auth/passkeys/sign-in/options': 200, '/api/auth/passkeys/sign-in': 204 })
  render(<SignIn />)
  fireEvent.click(screen.getByRole('button', { name: 'Sign in with fingerprint or face' }))
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/account'))
  expect(webauthn.startAuthentication).toHaveBeenCalledWith({ optionsJSON: { challenge: 'c' } })
})

test('a passkey that is not accepted can be tried again', async () => {
  window.history.replaceState(null, '', '/signin')
  server({ '/api/auth/passkeys/sign-in/options': 200, '/api/auth/passkeys/sign-in': 401 })
  render(<SignIn />)
  fireEvent.click(screen.getByRole('button', { name: 'Sign in with fingerprint or face' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("That didn't sign you in")
  expect(screen.getByRole('button', { name: 'Sign in with fingerprint or face' })).toBeVisible()
})

test('a cancelled fingerprint prompt or a server error can be tried again', async () => {
  window.history.replaceState(null, '', '/signin')
  server({ '/api/auth/passkeys/sign-in/options': 503 })
  render(<SignIn />)
  fireEvent.click(screen.getByRole('button', { name: 'Sign in with fingerprint or face' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("That didn't sign you in")
})

test('a browser without passkeys is told how to sign in', () => {
  window.history.replaceState(null, '', '/signin')
  webauthn.browserSupportsWebAuthn.mockReturnValue(false)
  server({})
  render(<SignIn />)
  expect(screen.getByText("This browser can't use passkeys.")).toBeInTheDocument()
  expect(screen.getByText(/Send \/login to the bot/)).toBeInTheDocument()
})

test('once a passkey exists, a link asks for the fingerprint instead', async () => {
  server({
    '/api/auth/redeem': 403,
    '/api/auth/passkeys/sign-in/options': 200,
    '/api/auth/passkeys/sign-in': 204,
  })
  render(<SignIn />)
  expect(await screen.findByText(/doesn't sign you in on its own/)).toBeInTheDocument()
  expect(screen.getByText(/send \/recover/i)).toBeInTheDocument()
  const assign = goes()
  fireEvent.click(screen.getByRole('button', { name: 'Sign in with fingerprint or face' }))
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/'))
})

test.each([
  ['?next=/account', '/account'],
  ['?next=/progress', '/progress'],
  ['?next=//evil.example', '/'],
  ['?next=https://evil.example', '/'],
  ['?next=/\\evil.example', '/'],
  ['?next=/%09/evil.example', '/'],
  ['?next=/%0a/evil.example', '/'],
  ['?next=/account%0a', '/'],
  ['?next=javascript:alert(1)', '/'],
  ['?next=/unknown', '/'],
  ['', '/'],
])('next page %s goes to %s', (search, page) => {
  expect(nextPage(search)).toBe(page)
})
