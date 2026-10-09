import { render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import SignIn from './SignIn'

const TOKEN = 'a'.repeat(43)

function answer(status: number) {
  const fetchMock = vi.fn(async () => new Response(null, { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  window.history.replaceState(null, '', `/signin#${TOKEN}`)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('a fresh link signs in and leaves no token in the address bar', async () => {
  const fetchMock = answer(204)
  render(<SignIn />)
  expect(await screen.findByText("You're signed in on this device.")).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/')
  expect(window.location.hash).toBe('')
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/auth/redeem',
    expect.objectContaining({ method: 'POST', body: JSON.stringify({ token: TOKEN }) }),
  )
})

test('a used or expired link says how to get a new one', async () => {
  answer(401)
  render(<SignIn />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Send /login to the bot')
})

test('a link without a token says so without calling the server', async () => {
  const fetchMock = answer(204)
  window.history.replaceState(null, '', '/signin')
  render(<SignIn />)
  expect(await screen.findByRole('alert')).toHaveTextContent('incomplete')
  expect(fetchMock).not.toHaveBeenCalled()
})

test('a server failure is not mistaken for a bad link', async () => {
  answer(500)
  render(<SignIn />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't reach the server")
})

test('the link is posted once, even when React runs the effect twice', async () => {
  const fetchMock = answer(204)
  render(
    <StrictMode>
      <SignIn />
    </StrictMode>,
  )
  expect(await screen.findByText("You're signed in on this device.")).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
