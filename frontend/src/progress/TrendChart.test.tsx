import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Standing } from '../api'
import TrendChart from './TrendChart'

const today = new Date(2026, 9, 21)

const standing = (trend: Standing['trend'], unit: Standing['unit'] = 'reps'): Standing => ({
  exercise: 'Pull-up',
  unit,
  slug: 'pull-up',
  step: 'Strict',
  step_id: 2,
  ladder: [],
  step_number: 1,
  steps: 4,
  last: [],
  best_set: null,
  status: 'hold',
  retired: false,
  trend,
})

/** Each polyline's x values, left to right. */
const lines = (svg: Element) =>
  [...svg.querySelectorAll('polyline')].map((l) =>
    l
      .getAttribute('points')!
      .split(' ')
      .map((p) => Number(p.split(',')[0])),
  )

test('each step is its own period, labelled with its step and an arrow, and said in words', () => {
  const { container } = render(
    <TrendChart
      standing={standing([
        { day: '2026-10-01', best: 12, step_number: 1 },
        { day: '2026-10-03', best: 12, step_number: 1 },
        { day: '2026-10-05', best: 7, step_number: 2 },
        { day: '2026-10-12', best: 8, step_number: 2 },
        { day: '2026-10-16', best: 10, step_number: 1 },
        { day: '2026-10-20', best: 11, step_number: 1 },
      ])}
      today={today}
    />,
  )
  const chart = screen.getByRole('img')
  expect(chart).toHaveAccessibleName(
    'Best set per session, last 6 weeks: 6 sessions, from 12 to 11' +
      '. Moved up to step 2 on 5 Oct; best 12 to 7' +
      '. Moved down to step 1 on 16 Oct; best 8 to 10',
  )
  expect(chart).toHaveTextContent('Step 2 ↑')
  expect(chart).toHaveTextContent('Step 1 ↓')
  // The line breaks at each change: one line per period, two sessions each, none joining them.
  const xs = lines(chart)
  expect(xs.map((l) => l.length)).toEqual([2, 2, 2])
  expect(xs[0][1]).toBeLessThan(xs[1][0])
  expect(xs[1][1]).toBeLessThan(xs[2][0])
  // Plain, tinted, plain: the one tint lies between the first period's sessions and the second's.
  const tints = container.querySelectorAll('[data-period-tint]')
  expect(tints).toHaveLength(1)
  const edge = Number(tints[0].getAttribute('x'))
  expect(edge).toBeGreaterThan(xs[0][1])
  expect(edge).toBeLessThan(xs[1][0])
  // No dashed marker any more: the period's edge marks the change.
  expect(container.querySelector('[stroke-dasharray]')).toBeNull()
})

test('one step all along: one line, no labels, no tint, no moves to describe', () => {
  const { container } = render(
    <TrendChart
      standing={standing(
        [
          { day: '2026-10-10', best: 40, step_number: 3 },
          { day: '2026-10-17', best: 45, step_number: 3 },
        ],
        'seconds',
      )}
      today={today}
    />,
  )
  const chart = screen.getByRole('img')
  expect(chart).toHaveAccessibleName(
    'Best set per session, last 6 weeks: 2 sessions, from 40 s to 45 s',
  )
  expect(lines(chart)).toHaveLength(1)
  expect(chart).not.toHaveTextContent(/[↑↓]/)
  expect(container.querySelector('[data-period-tint]')).toBeNull()
})

test('a narrow period gets the short label and keeps its change in the description', () => {
  render(
    <TrendChart
      standing={standing([
        { day: '2026-10-10', best: 10, step_number: 2 },
        { day: '2026-10-20', best: 12, step_number: 1 },
      ])}
      today={today}
    />,
  )
  const chart = screen.getByRole('img')
  expect(chart).toHaveTextContent(/↓︎1/) // text style, never a coloured emoji
  expect(chart).not.toHaveTextContent('Step 1 ↓')
  expect(chart).toHaveAccessibleName(/\. Moved down to step 1 on 20 Oct; best 10 to 12$/)
  // Two one-session periods: two dots and no line between them.
  expect(lines(chart)).toHaveLength(0)
  expect(chart.querySelectorAll('circle')).toHaveLength(2)
})
