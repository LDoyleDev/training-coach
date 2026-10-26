import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BodyFatTrend from './BodyFatTrend'

function serve(entries: unknown, estimates: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      if (status !== 200) return new Response(null, { status })
      if (path === '/api/body') return Response.json(entries)
      if (path === '/api/body/estimates') return Response.json(estimates)
      return new Response(null, { status: 404 })
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

test('the scale and the tape estimate, on one chart', async () => {
  serve(
    [
      { on: '2026-10-24', kind: 'body_fat_scale', value: 18.2 },
      { on: '2026-10-24', kind: 'waist', value: 93 },
      { on: '2026-10-10', kind: 'body_fat_scale', value: 19 },
    ],
    [{ on: '2026-10-24', value: 21.6 }],
  )
  render(<BodyFatTrend />)
  expect(await screen.findByRole('heading', { name: 'Body fat' })).toBeInTheDocument()
  expect(screen.getByText('Scale')).toBeInTheDocument()
  expect(screen.getByText('Tape, estimate from waist and neck, ±4%')).toBeInTheDocument()
  expect(screen.getByRole('img')).toHaveAccessibleName(
    'Body fat, %. Scale: 2 days, from 19.0 % to 18.2 %. Tape, estimate from waist and neck, ±4%: 1 day, 21.6 %',
  )
})

test('only the scale when the estimate is off', async () => {
  serve([{ on: '2026-10-24', kind: 'body_fat_scale', value: 18.2 }], [])
  render(<BodyFatTrend />)
  expect(await screen.findByText('Scale')).toBeInTheDocument()
  expect(screen.queryByText(/estimate from waist and neck/)).not.toBeInTheDocument()
})

test('nothing without body-fat data', async () => {
  serve([{ on: '2026-10-24', kind: 'waist', value: 93 }], [])
  const { container } = render(<BodyFatTrend />)
  await settle()
  expect(container).toBeEmptyDOMElement()
})

test.each([401, 500])('nothing when signed out or the server fails (%i)', async (status) => {
  serve([], [], status)
  const { container } = render(<BodyFatTrend />)
  await settle()
  expect(container).toBeEmptyDOMElement()
})
