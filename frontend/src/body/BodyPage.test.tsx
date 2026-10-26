import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { BodyAverage, BodyEstimate, MeasureKind, Measurement } from '../api'
import BodyPage from './BodyPage'

const KINDS: MeasureKind[] = [
  {
    kind: 'bodyweight',
    label: 'Bodyweight',
    unit: 'kg',
    decimals: 1,
    low: 30,
    high: 250,
    how: 'Same scale.',
  },
  {
    kind: 'waist',
    label: 'Waist',
    unit: 'cm',
    decimals: 1,
    low: 40,
    high: 200,
    how: 'At the navel.',
  },
]

const GUIDE = {
  checklist: ['In the morning, after the toilet.', 'Measure twice; enter the average.'],
  cadence: 'Weight daily or weekly; the tape every 2 to 4 weeks.',
}

const FAT: MeasureKind = {
  kind: 'body_fat_scale',
  label: 'Body fat (scale)',
  unit: '%',
  decimals: 1,
  low: 3,
  high: 60,
  how: 'Same scale, barefoot.',
}

type Server = {
  entries?: Measurement[]
  kinds?: MeasureKind[]
  estimates?: BodyEstimate[]
  averages?: BodyAverage[]
  warnings?: string[]
  signedIn?: boolean
  save?: 'refuse' | 'fail'
  remove?: 'fail'
  extras?: 'fail' // the guide, the estimate and the 7-day average all answer 500
}

/** A fake API; returns the requests sent that change something. */
function serve(server: Server = {}) {
  const sent: { method: string; path: string; body: unknown }[] = []
  let entries = server.entries ?? []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (server.signedIn === false) return new Response(null, { status: 401 })
      const method = init?.method ?? 'GET'
      if (method !== 'GET') {
        sent.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null })
        if (method === 'DELETE') {
          if (server.remove === 'fail') return new Response(null, { status: 500 })
          entries = entries.filter((e) => path !== `/api/body/${e.on}/${e.kind}`)
          return new Response(null, { status: 204 })
        }
        if (server.save === 'refuse')
          return Response.json({ detail: 'Waist must be from 40 to 200 cm' }, { status: 422 })
        if (server.save === 'fail') return new Response(null, { status: 500 })
        return Response.json({ warnings: server.warnings ?? [] })
      }
      if (path === '/api/body/kinds') return Response.json(server.kinds ?? KINDS)
      if (server.extras === 'fail' && path !== '/api/body')
        return new Response(null, { status: 500 })
      if (path === '/api/body/guide') return Response.json(GUIDE)
      if (path === '/api/body/estimates') return Response.json(server.estimates ?? [])
      if (path === '/api/body/averages') return Response.json(server.averages ?? [])
      return Response.json(entries)
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test('a failed guide, estimate or average still shows and adds measurements', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'bodyweight', value: 83.1 }], extras: 'fail' })
  render(<BodyPage />)
  expect(await screen.findByRole('heading', { name: 'Add measurements' })).toBeInTheDocument()
  expect(screen.getAllByText(/83\.1/).length).toBeGreaterThan(0)
  expect(screen.queryByText('Before you measure')).not.toBeInTheDocument() // no guide to show
})

test('the latest values compare with the first and the last', async () => {
  serve({
    entries: [
      { on: '2026-10-10', kind: 'bodyweight', value: 83.1 },
      { on: '2026-10-03', kind: 'bodyweight', value: 83.6 },
      { on: '2026-09-28', kind: 'bodyweight', value: 84.2 },
    ],
  })
  render(<BodyPage />)
  expect(
    await screen.findByText(/83.1 kg · since first -1.1 · since last -0.5/),
  ).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Bodyweight, \d+ entries$/ })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
})

test('filled-in values are saved for the chosen day', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Bodyweight'), { target: { value: '83,4' } })
  fireEvent.change(screen.getByLabelText('Day'), { target: { value: '2026-10-08' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(sent).toEqual([
    { method: 'PUT', path: '/api/body', body: { on: '2026-10-08', values: { bodyweight: 83.4 } } },
  ])
  expect(screen.getByLabelText('Bodyweight')).toHaveValue('')
})

test('nothing typed, or not a number, is caught before sending', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  expect(screen.getByText('Fill in at least one.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Waist'), { target: { value: 'big' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(screen.getByText("Waist isn't a number.")).toBeInTheDocument()
  expect(sent).toEqual([])
})

test('a refused or failed save says so and keeps what was typed', async () => {
  serve({ save: 'refuse' })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '820' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Waist must be from 40 to 200 cm')).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve({ save: 'fail' })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByLabelText('Waist')).toHaveValue('820')
})

test('a measurement can be removed', async () => {
  const sent = serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Waist on 2026-10-10' }))
  await screen.findByRole('heading', { name: 'Add measurements' })
  expect(sent).toEqual([{ method: 'DELETE', path: '/api/body/2026-10-10/waist', body: null }])
  expect(await screen.findByRole('heading', { name: 'Body' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'History' })).not.toBeInTheDocument()
})

test('a failed remove says so', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'mystery' as never, value: 1 }], remove: 'fail' })
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove mystery on 2026-10-10' }))
  expect(await screen.findByText(/Couldn't remove it/)).toBeInTheDocument()
})

test('signed out, or the server down', async () => {
  serve({ signedIn: false })
  const { unmount } = render(<BodyPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  unmount()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  render(<BodyPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your measurements.")
})

test('an ended sign-in points to sign in and keeps what was typed', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '85' } })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toHaveAttribute(
    'href',
    expect.stringMatching(/^\/signin\?next=/),
  )
  expect(screen.getByLabelText('Waist')).toHaveValue('85')
  expect(sent).toEqual([])
})

test('a remove after an ended sign-in points to sign in too', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  const button = await screen.findByRole('button', { name: 'Remove Waist on 2026-10-10' })
  // The photos section loads its list once the page is ready: let it, so only the remove meets
  // the ended sign-in (otherwise the photos would rightly show their own notice too).
  await waitFor(() =>
    expect(vi.mocked(fetch).mock.calls.some(([path]) => path === '/api/photos')).toBe(true),
  )
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(button)
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})

test('removing clears an earlier note', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Bodyweight'), { target: { value: '83' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Waist on 2026-10-10' }))
  await waitFor(() => expect(screen.queryByText('Saved.')).not.toBeInTheDocument())
})

test('a retry after signing in again clears the notice', async () => {
  serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '85' } })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve() // signed in again in another tab
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Sign in again' })).not.toBeInTheDocument()
})

test('the checklist and how to take each one fold open', async () => {
  serve()
  render(<BodyPage />)
  const summary = await screen.findByText('Before you measure')
  const checklist = summary.closest('details')!
  expect(checklist).not.toHaveAttribute('open')
  fireEvent.click(summary)
  expect(checklist).toHaveAttribute('open')
  expect(screen.getByText('Measure twice; enter the average.')).toBeVisible()
  expect(screen.getByText(/the tape every 2 to 4 weeks/)).toBeInTheDocument()
  const how = screen.getByText('(Waist)').closest('summary')!
  expect(how).toHaveTextContent('How?')
  fireEvent.click(how)
  expect(how.closest('details')).toHaveAttribute('open')
  expect(screen.getByText('At the navel.')).toBeInTheDocument()
})

test('a far value is saved with a warning that stays until dismissed', async () => {
  const warning = 'Waist is 3.5 cm off your last (12 Oct): different landmark? Re-measure.'
  serve({ warnings: [warning] })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '88.5' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  const region = screen.getByRole('region', { name: 'Saved, but worth a second look' })
  expect(region).toHaveTextContent(warning)
  fireEvent.click(screen.getByRole('button', { name: 'Close' })) // the toast goes, the warning stays
  expect(screen.getByText(warning)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
  expect(screen.queryByText(warning)).not.toBeInTheDocument()
})

test('the next save clears the last warnings', async () => {
  const warning = 'Bodyweight is 2.4 kg off your last (3 Oct): different scale or time of day?'
  const sent = serve({ warnings: [warning] })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Bodyweight'), { target: { value: '85' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText(warning)).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve()
  fireEvent.change(screen.getByLabelText('Bodyweight'), { target: { value: '83' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(screen.queryByText(warning)).not.toBeInTheDocument())
  expect(sent).toHaveLength(1)
})

test("bodyweight's headline is its 7-day average", async () => {
  serve({
    entries: [
      { on: '2026-10-24', kind: 'bodyweight', value: 81.8 },
      { on: '2026-10-22', kind: 'bodyweight', value: 82.4 },
    ],
    averages: [
      { on: '2026-10-24', value: 82.1, count: 2 },
      { on: '2026-10-22', value: 82.4, count: 1 },
    ],
  })
  render(<BodyPage />)
  expect(await screen.findByText(/7-day average 82.1 kg · from 2 weigh-ins/)).toBeInTheDocument()
  expect(screen.getByText('Last weigh-in 81.8 kg (2026-10-24)')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Bodyweight, 7-day average, 2 days' })).toBeInTheDocument()
})

test('one weigh-in is one, not ones', async () => {
  serve({
    entries: [{ on: '2026-10-24', kind: 'bodyweight', value: 81.8 }],
    averages: [{ on: '2026-10-24', value: 81.8, count: 1 }],
  })
  render(<BodyPage />)
  expect(await screen.findByText(/from 1 weigh-in$/)).toBeInTheDocument()
})

test('body fat shows the scale and the tape estimate as two named lines', async () => {
  serve({
    kinds: [...KINDS, FAT],
    entries: [
      { on: '2026-10-24', kind: 'body_fat_scale', value: 18.2 },
      { on: '2026-10-10', kind: 'body_fat_scale', value: 19.0 },
    ],
    estimates: [
      { on: '2026-10-24', value: 21.6 },
      { on: '2026-10-10', value: 20.9 },
    ],
  })
  render(<BodyPage />)
  const latest = await screen.findByRole('region', { name: 'Latest' })
  expect(latest).toHaveTextContent('Body fat (scale): 18.2 % · since first -0.8 (2026-10-24)')
  expect(latest).toHaveTextContent('Tape, estimate from waist and neck, ±4%')
  // No headline number for the estimate: its values are only in the dots' hover titles.
  expect(screen.queryByText(/21\.6/, { ignore: 'title, script, style' })).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Body fat, %/ })).toHaveAccessibleName(
    'Body fat, %. Scale: 2 days, from 19.0 % to 18.2 %. Tape, estimate from waist and neck, ±4%: 2 days, from 20.9 % to 21.6 %',
  )
})

test('the tape estimate alone still shows body fat', async () => {
  serve({ kinds: [...KINDS, FAT], estimates: [{ on: '2026-10-24', value: 21.6 }] })
  render(<BodyPage />)
  expect(await screen.findByRole('heading', { name: 'Latest' })).toBeInTheDocument()
  expect(screen.getByText('Body fat')).toBeInTheDocument()
  expect(screen.queryByText('Scale')).not.toBeInTheDocument()
  expect(
    screen.getByRole('img', { name: /Tape, estimate from waist and neck, ±4%: 1 day, 21.6 %/ }),
  ).toBeInTheDocument()
})
