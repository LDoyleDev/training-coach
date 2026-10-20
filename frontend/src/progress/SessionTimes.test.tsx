import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import SessionTimes from './SessionTimes'

function serve(status: number, body?: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('each timed session with its usual, last and fastest time', async () => {
  serve(200, [
    { session: 'Legs', usual: 38, last: 41, fastest: 35, timed: 6 },
    { session: 'Upper', usual: 44, last: 44, fastest: 44, timed: 1 },
  ])
  render(<SessionTimes />)
  expect(await screen.findByRole('heading', { name: 'How long sessions take' })).toBeVisible()
  const [legs, upper] = screen.getAllByRole('listitem')
  expect(legs).toHaveTextContent('Legs: usually 38 min · last 41 · fastest 35 (6 timed)')
  expect(upper).toHaveTextContent(/^Upper: usually 44 min$/) // one time: nothing to compare
})

test.each([
  ['nothing timed yet', 200, []],
  ['signed out', 401, undefined],
  ['a failed load', 500, undefined],
])('%s shows nothing', async (_, status, body) => {
  serve(status, body)
  const { container } = render(<SessionTimes />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})
