import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import JoinPage from './JoinPage'

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  passkeysSupported: () => true,
  addPasskey: vi.fn(async () => true),
}))

function serve(status: number | 'error') {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      sent.push(JSON.parse(String(init?.body)))
      if (status === 'error') throw new TypeError('offline')
      return new Response(null, { status })
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

const open = (hash = '#tok123') => {
  window.history.replaceState(null, '', `/join${hash}`)
  render(<JoinPage />)
}

test('the invite leaves the address bar, and joining waits for the adult box', () => {
  serve(204)
  open()
  expect(window.location.hash).toBe('')
  expect(screen.getByRole('button', { name: 'Join' })).toBeDisabled()
  fireEvent.click(screen.getByRole('checkbox', { name: "I'm 18 or over" }))
  expect(screen.getByRole('button', { name: 'Join' })).toBeEnabled()
})

test('joining signs in and offers a passkey', async () => {
  const sent = serve(204)
  open()
  fireEvent.click(screen.getByRole('checkbox', { name: "I'm 18 or over" }))
  fireEvent.click(screen.getByRole('button', { name: 'Join' }))
  expect(await screen.findByText("You're in.")).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Set up your plan' })).toHaveAttribute('href', '/start')
  expect(sent).toEqual([{ token: 'tok123', adult: true }])
  fireEvent.click(screen.getByRole('button', { name: 'Add a passkey' }))
  expect(await screen.findByText('Passkey added.')).toBeInTheDocument()
})

test.each([
  [401, 'expired or was used'],
  [409, 'no room'],
  [404, "aren't open"],
  [500, "That didn't work"],
  ['error' as const, "That didn't work"],
])('a refusal (%s) says why', async (status, text) => {
  serve(status)
  open()
  fireEvent.click(screen.getByRole('checkbox', { name: "I'm 18 or over" }))
  fireEvent.click(screen.getByRole('button', { name: 'Join' }))
  expect(await screen.findByRole('status')).toHaveTextContent(text)
})

test('a link without an invite says so', () => {
  serve(204)
  open('')
  expect(screen.getByText(/no invite in it/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Join' })).not.toBeInTheDocument()
})

test('joining says it is a private test for invited people', () => {
  serve(204)
  open('')
  expect(screen.getByText(/private test for invited family and friends/)).toBeInTheDocument()
})
