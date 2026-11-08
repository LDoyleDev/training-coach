import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Recovered from './Recovered'

const me = (recovered_by_admin_at: string | null) => ({
  user_id: 2,
  role: 'member',
  closed: false,
  closing_on: null,
  recovered_by_admin_at,
})

function answer(status: number, body?: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })),
  )
}

afterEach(() => vi.unstubAllGlobals())

test('says when the admin recovered the account, with nothing to dismiss it', async () => {
  answer(200, me('2026-11-07T10:00:00Z'))
  render(<Recovered />)
  expect(
    await screen.findByText(/recovered with a link from the admin on 7 November 2026/),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test.each([
  ['no recovery', 200, me(null)],
  ['signed out', 401, undefined],
  ['a failure', 500, undefined],
])('hidden with %s', async (_why, status, body) => {
  answer(status, body)
  const { container } = render(<Recovered />)
  await new Promise((r) => setTimeout(r, 0))
  expect(container).toBeEmptyDOMElement()
})
