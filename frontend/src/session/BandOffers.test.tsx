import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { emptyWeek } from '../test/cardioWeek'
import BandOffers from './BandOffers'

const today = new Date().toLocaleDateString('en-CA')
const WALK = {
  id: 5,
  on: today,
  activity: 'walk',
  minutes: 46,
  zone2: 38,
  kind: 'zone2',
  value: 38,
  text: 'Walk, 46 min, 38 in zone 2 - count it?',
}
const COUNTED = {
  workout_id: 9,
  already_saved: false,
  planned: true,
  week: emptyWeek({ zone2: 38, zone2_target: [45, 75], total: 46, total_target: [75, 115] }),
}

type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply[]>) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push(route)
      const replies = routes[route] ?? [{ status: 500 }]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]
      const body = reply.body === undefined ? null : JSON.stringify(reply.body)
      return new Response(reply.status === 204 ? null : body, { status: reply.status })
    }),
  )
  return asked
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('count it saves and says how the week stands', async () => {
  const counted = vi.fn()
  const asked = serve({
    'GET /api/band/offers': [
      { status: 200, body: [WALK] },
      { status: 200, body: [] },
    ],
    'POST /api/band/offers/5/count': [{ status: 200, body: COUNTED }],
  })
  render(<BandOffers onCounted={counted} />)
  expect(await screen.findByText(WALK.text)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Count it' }))
  await vi.waitFor(() =>
    expect(counted).toHaveBeenCalledWith(
      'Counted, and today’s session is done. Last 7 days: cardio 46 of 75-115 min, zone 2 38 of 45-75.',
    ),
  )
  expect(asked).toContain('POST /api/band/offers/5/count')
  await vi.waitFor(() => expect(screen.queryByText(WALK.text)).not.toBeInTheDocument())
})

test('an extra without a target, from an earlier day', async () => {
  const counted = vi.fn()
  serve({
    'GET /api/band/offers': [{ status: 200, body: [{ ...WALK, on: '2026-10-09' }] }],
    'POST /api/band/offers/5/count': [
      {
        status: 200,
        body: {
          ...COUNTED,
          planned: false,
          week: { ...COUNTED.week, zone2_target: null, total_target: null },
        },
      },
    ],
  })
  render(<BandOffers onCounted={counted} />)
  expect(await screen.findByText(/Fri: Walk, 46 min/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Count it' }))
  await vi.waitFor(() =>
    expect(counted).toHaveBeenCalledWith('Counted. Last 7 days: cardio 46 min, zone 2 38.'),
  )
})

test('not this one takes it away', async () => {
  const asked = serve({
    'GET /api/band/offers': [{ status: 200, body: [WALK] }],
    'POST /api/band/offers/5/dismiss': [{ status: 204 }],
  })
  const { container } = render(<BandOffers onCounted={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Not this one' }))
  await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  expect(asked).toContain('POST /api/band/offers/5/dismiss')
})

test.each([
  [{ status: 404 }, /isn’t on offer any more/],
  [{ status: 409 }, /Today’s session changed/],
  [{ status: 500 }, /That didn't work/],
])('a count that fails says why', async (reply, text) => {
  serve({
    'GET /api/band/offers': [{ status: 200, body: [WALK] }],
    'POST /api/band/offers/5/count': [reply],
  })
  render(<BandOffers onCounted={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Count it' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test('a sign-in that ended says so', async () => {
  serve({
    'GET /api/band/offers': [{ status: 200, body: [WALK] }],
    'POST /api/band/offers/5/dismiss': [{ status: 401 }],
  })
  render(<BandOffers onCounted={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Not this one' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your sign-in has ended.')
})

test('nothing shows without offers, signed out or on errors', async () => {
  for (const reply of [{ status: 200, body: [] }, { status: 401 }, { status: 500 }]) {
    serve({ 'GET /api/band/offers': [reply] })
    const { container, unmount } = render(<BandOffers onCounted={vi.fn()} />)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(container).toBeEmptyDOMElement()
    unmount()
  }
})

test('counting into a day that has its session asks first', async () => {
  const counted = vi.fn()
  const clash = {
    day: today,
    moving: false,
    recorded: [{ workout_id: 4, name: 'Long zone 2', summary: '45 min' }],
  }
  serve({
    'GET /api/band/offers': [{ status: 200, body: [WALK] }],
    'POST /api/band/offers/5/count': [
      { status: 409, body: { detail: clash } },
      { status: 409, body: { detail: { ...clash, day: '2026-10-01', moving: true } } },
      { status: 422, body: { detail: 'pick a different day to move it to' } },
      { status: 200, body: COUNTED },
    ],
  })
  render(<BandOffers onCounted={counted} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Count it' }))
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('Long zone 2: 45 min')
  fireEvent.click(screen.getByRole('button', { name: 'Move it to another day' }))
  fireEvent.click(screen.getAllByRole('button', { name: /\d{2} \w{3}$/ })[0])
  expect(await screen.findByText(/has Long zone 2 \(45 min\) too/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  fireEvent.click(screen.getByRole('button', { name: 'Replace it' }))
  expect(await screen.findByText('pick a different day to move it to')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Add to that day' }))
  await vi.waitFor(() => expect(counted).toHaveBeenCalled())
})
