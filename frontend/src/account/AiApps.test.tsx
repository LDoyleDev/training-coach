import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import AiApps from './AiApps'

const APP = {
  id: 7,
  client_name: 'Claude',
  redirect_host: 'claude.ai',
  scopes: ['training:read', 'body:read'],
  created_at: '2026-10-11T12:00:00Z',
  last_used_at: null,
  ends_at: '2027-01-09T12:00:00Z',
}

function server(lists: unknown[], revoke = 204) {
  const fetchMock = vi.fn(async (_path: string, init?: RequestInit) => {
    if (init?.method === 'DELETE') return new Response(null, { status: revoke })
    const next = lists.length > 1 ? lists.shift() : lists[0]
    if (typeof next === 'number') return new Response(null, { status: next })
    return new Response(JSON.stringify(next), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

test('a connected app shows its claimed name, host and what it reads', async () => {
  server([[APP]])
  render(<AiApps />)
  const item = await screen.findByText(/Calls itself “Claude”/)
  expect(item).toHaveTextContent('claude.ai')
  expect(item).toHaveTextContent('reads training, body measurements')
  expect(item).toHaveTextContent('not used yet')
})

test('revoking says so and the app goes', async () => {
  const fetchMock = server([[APP], []])
  render(<AiApps />)
  fireEvent.click(await screen.findByRole('button', { name: 'Revoke Claude' }))
  expect(await screen.findByRole('status')).toHaveTextContent("“Claude” can't read anything now.")
  expect(await screen.findByText(/None\. To connect one/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/account/connections/7',
    expect.objectContaining({ method: 'DELETE' }),
  )
})

test('a failed revoke says to try again', async () => {
  server([[APP]], 500)
  render(<AiApps />)
  fireEvent.click(await screen.findByRole('button', { name: 'Revoke Claude' }))
  expect(await screen.findByRole('status')).toHaveTextContent("That didn't work")
})

test('signed out, the section is left out', async () => {
  server([401])
  const { container } = render(<AiApps />)
  await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
})

test('a load error is said plainly', async () => {
  server([500])
  render(<AiApps />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your connected apps")
})
