import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Moved, Standing } from '../api'
import Levels from './Levels'
import { moveHref, nextRung, said, wanted } from './ladder'

const LADDER = [
  { id: 1, name: 'Slow negatives', cue: null, missing: [] },
  { id: 2, name: 'Strict pull-up', cue: null, missing: [] },
  { id: 3, name: 'Pause at top', cue: 'Hold two seconds with your chin over the bar', missing: [] },
  { id: 4, name: 'Weighted backpack', cue: null, missing: [] },
]

const make = (over: Partial<Standing> = {}): Standing => ({
  exercise: 'Pull-up',
  slug: 'pull-up',
  unit: 'reps',
  step: 'Strict pull-up',
  step_id: 2,
  step_number: 2,
  steps: 4,
  ladder: LADDER,
  last: [12, 12, 12, 12],
  best_set: 12,
  status: 'ready',
  retired: false,
  trend: [],
  unlock: null,
  ...over,
})

type Calls = { path: string; body: unknown }[]

/** Serves /api/progress (each answer in turn, the last repeated) and records each move. */
function serve(
  answers: ({ standings: Standing[]; strength_block?: boolean } | number)[],
  moved: Moved | number = {
    outcome: 'moved',
    exercise: 'Pull-up',
    step: 'Pause at top',
    warning: null,
  },
): Calls {
  const calls: Calls = []
  let n = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        calls.push({ path, body: JSON.parse(String(init.body)) })
        return typeof moved === 'number'
          ? new Response(null, { status: moved })
          : Response.json(moved)
      }
      const answer = answers[Math.min(n++, answers.length - 1)]
      return typeof answer === 'number'
        ? new Response(null, { status: answer })
        : Response.json({ today: '2026-10-25', strength_block: false, ...answer })
    }),
  )
  return calls
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

const open = async (name: RegExp) =>
  fireEvent.click(await screen.findByRole('button', { name, expanded: false }))

const showAll = async () =>
  fireEvent.click(await screen.findByRole('button', { name: /Show all exercises/ }))

test('a ready exercise offers Move up and Not yet, with its ladder, last, best and next', async () => {
  const calls = serve([
    { standings: [make()] },
    { standings: [make({ step: 'Pause at top', step_id: 3, step_number: 3, status: 'hold' })] },
  ])
  render(<Levels />)
  await open(/Pull-up/)
  const steps = screen.getAllByRole('listitem').filter((li) => li.closest('ol'))
  expect(steps.map((li) => li.textContent)).toEqual([
    'Slow negatives',
    'Strict pull-up (now)',
    'Pause at top',
    'Weighted backpack',
  ])
  expect(steps[1]).toHaveAttribute('aria-current', 'step')
  expect(screen.getByText('Last 12 · 12 · 12 · 12 · best 12')).toBeInTheDocument()
  expect(screen.getByText(/Hold two seconds with your chin over the bar/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Move up to Pause at top' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Moved up: Pull-up is now Pause at top.',
  )
  expect(calls).toEqual([{ path: '/api/progress/pull-up/move-up', body: { from_step_id: 2 } }])
  expect(await screen.findByText('Step 3 of 4: Pause at top')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Move up to/ })).not.toBeInTheDocument()
})

test('Not yet stays on the step the page showed', async () => {
  const calls = serve([{ standings: [make()] }], {
    outcome: 'stayed',
    warning: null,
    exercise: 'Pull-up',
    step: 'Strict pull-up',
  })
  render(<Levels />)
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Staying on Strict pull-up.')
  expect(calls).toEqual([{ path: '/api/progress/pull-up/not-yet', body: { step_id: 2 } }])
})

test('not ready: no Move up, but any level can be chosen, with a confirm', async () => {
  const calls = serve([{ standings: [make({ status: 'hold', last: [], best_set: null })] }], {
    outcome: 'level_set',
    warning: null,
    exercise: 'Pull-up',
    step: 'Slow negatives',
  })
  render(<Levels />)
  expect(await screen.findByText('Nothing is ready to move up right now.')).toBeInTheDocument()
  await showAll()
  await open(/Pull-up/)
  expect(screen.getByText('Not logged at this step yet')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Move up/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Change level' }))
  const choose = screen.getByRole('group', { name: 'Choose a level for Pull-up' })
  expect(within(choose).getByRole('button', { name: /Set level/ })).toBeDisabled() // still now
  fireEvent.click(within(choose).getByRole('radio', { name: 'Slow negatives' }))
  expect(
    within(choose).getByText('Targets for Slow negatives start fresh from its own history.'),
  ).toBeInTheDocument()
  fireEvent.click(within(choose).getByRole('button', { name: 'Set level to Slow negatives' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Pull-up is now on Slow negatives.')
  expect(calls).toEqual([{ path: '/api/progress/pull-up/level', body: { step_id: 1 } }])
})

test('Cancel puts the level choice away', async () => {
  serve([{ standings: [make({ status: 'hold' })] }])
  render(<Levels />)
  await showAll()
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Change level' }))
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('group')).not.toBeInTheDocument()
})

test('in a strength block Move up explains why it waits; choosing a level still works', async () => {
  serve([{ standings: [make()], strength_block: true }])
  render(<Levels />)
  expect(
    await screen.findByText('1 ready to move up when the hypertrophy block starts.'),
  ).toBeInTheDocument()
  await open(/Pull-up/)
  expect(screen.getByText(/Moving up waits for the hypertrophy block/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Move up to/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Change level' })).toBeEnabled()
})

test('a link with ?move= opens that exercise and scrolls to it', async () => {
  window.history.replaceState(null, '', moveHref('dip'))
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  serve([
    {
      standings: [
        make({ status: 'hold' }),
        make({ exercise: 'Dip', slug: 'dip', status: 'top_of_ladder', step_id: 4 }),
        make({ exercise: 'Goblet squat', slug: 'goblet', retired: true }),
      ],
    },
  ])
  render(<Levels />)
  expect(await screen.findByRole('button', { name: /Dip/, expanded: true })).toBeInTheDocument()
  expect(screen.getByText('This is the last step on the ladder.')).toBeInTheDocument()
  await waitFor(() => expect(scroll).toHaveBeenCalledOnce()) // the scroll runs after the render
  // Only the ready ones and the one asked for, until all are asked for.
  expect(screen.queryByRole('button', { name: /Pull-up/ })).not.toBeInTheDocument()
  await showAll()
  expect(screen.getByRole('button', { name: /Pull-up/, expanded: false })).toBeInTheDocument()
  expect(screen.queryByText(/Goblet squat/)).not.toBeInTheDocument() // retired: not in the plan
  fireEvent.click(screen.getByRole('button', { name: /Dip/ }))
  expect(screen.getByRole('button', { name: /Dip/, expanded: false })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Show only the ones ready' }))
  expect(screen.queryByRole('button', { name: /Dip/ })).not.toBeInTheDocument()
})

test('a refused or failed press says so and changes nothing on the page', async () => {
  serve([{ standings: [make()] }], 422)
  render(<Levels />)
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))
  expect(await screen.findByRole('status')).toHaveTextContent("isn't on this exercise's ladder")
})

test('a press after the sign-in ended says to sign in again', async () => {
  serve([{ standings: [make()] }], 401)
  render(<Levels />)
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Your sign-in has ended.')
})

test('a server error on a press says nothing changed', async () => {
  serve([{ standings: [make()] }], 500)
  render(<Levels />)
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Nothing changed.')
})

test('signed out shows nothing (the plan says to sign in); an error says so', async () => {
  serve([401])
  const { container, unmount } = render(<Levels />)
  await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  unmount()
  serve([500])
  render(<Levels />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your levels.")
})

test('every outcome is said in plain words', () => {
  const say = (outcome: Moved['outcome'], step: string | null = 'Pause at top') =>
    said({ outcome, exercise: 'Pull-up', step, warning: null })
  expect(say('already_moved')).toMatch(/already moved on/)
  expect(say('not_ready')).toBe("Pull-up doesn't meet the rule any more. Keep going.")
  expect(say('no_next_step')).toBe('Pull-up is on the last step in your plan.')
  expect(say('strength_block')).toMatch(/waits for the hypertrophy block/)
  expect(say('same_level')).toBe('Pull-up is already on Pause at top.')
  expect(say('level_set', null)).toMatch(/Targets for it start fresh/)
  expect(wanted('?move=pull-up')).toBe('pull-up')
  expect(wanted('')).toBeNull()
  expect(moveHref('a b')).toBe('/plan?move=a%20b')
  expect(nextRung(make({ step_id: 4 }))).toBeNull()
  expect(nextRung(make({ step_id: 99 }))).toBeNull()
})
