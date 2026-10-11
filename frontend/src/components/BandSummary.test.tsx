import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BandSummary from './BandSummary'
import { hours } from './duration'

const NOTHING = {
  sleep: null,
  steps_today: null,
  steps_yesterday: null,
  resting: null,
  usual_resting: null,
}
const NIGHT = {
  start: '2026-10-10T21:30:00Z',
  end: '2026-10-11T05:00:00Z',
  asleep: 440,
  awake: 10,
  light: 250,
  deep: 90,
  rem: 100,
}

function serve(status: number, body?: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('sleep, steps and resting heart rate', async () => {
  serve(200, {
    sleep: NIGHT,
    steps_today: 812,
    steps_yesterday: 11234,
    resting: 52,
    usual_resting: 48,
  })
  render(<BandSummary />)
  expect(await screen.findByText('From your band')).toBeInTheDocument()
  expect(screen.getByText(/Slept 7 h 20 min/)).toBeInTheDocument()
  expect(screen.getByText(/deep 1 h 30 min · REM 1 h 40 min/)).toBeInTheDocument()
  expect(screen.getByText(/812 steps today/)).toBeInTheDocument()
  expect(screen.getByText('11,234 yesterday')).toBeInTheDocument()
  expect(screen.getByText(/Resting heart rate 52 bpm/)).toBeInTheDocument()
  expect(screen.getByText('(usually 48)')).toBeInTheDocument()
})

test('only what there is', async () => {
  serve(200, { ...NOTHING, steps_yesterday: 9000, resting: 48, usual_resting: 48 })
  render(<BandSummary />)
  expect(await screen.findByText('9,000 yesterday')).toBeInTheDocument()
  expect(screen.queryByText(/Slept/)).not.toBeInTheDocument()
  expect(screen.queryByText(/usually/)).not.toBeInTheDocument()
  expect(screen.queryByText(/today/)).not.toBeInTheDocument()
})

test('steps today alone', async () => {
  serve(200, { ...NOTHING, steps_today: 50 })
  render(<BandSummary />)
  expect(await screen.findByText('50 steps today')).toBeInTheDocument()
})

test.each([
  [200, NOTHING],
  [401, undefined],
  [500, undefined],
])('nothing shows without band data or on errors (%i)', async (status, body) => {
  serve(status, body)
  const { container } = render(<BandSummary />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})

test('hours', () => {
  expect([440, 420, 45, 0].map(hours)).toEqual(['7 h 20 min', '7 h', '45 min', '0 min'])
})
