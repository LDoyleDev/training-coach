import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Moved, Standing } from '../api'
import Levels from './Levels'
import { moveHref, nextRung, said, topLabel, wanted } from './ladder'

const LADDER = [
  { id: 1, name: 'Slow negatives', cue: null, missing: [], avoided: [], question: null },
  { id: 2, name: 'Strict pull-up', cue: null, missing: [], avoided: [], question: null },
  {
    id: 3,
    name: 'Pause at top',
    cue: 'Hold two seconds with your chin over the bar',
    missing: [],
    avoided: [],
    question: null,
  },
  { id: 4, name: 'Weighted backpack', cue: null, missing: [], avoided: [], question: null },
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
  last_kg: [],
  best_set: 12,
  best_kg: null,
  status: 'ready',
  retired: false,
  trend: [],
  unlock: null,
  step_down: null,
  ...over,
})

type Calls = { path: string; body: unknown }[]

/** Serves /api/progress (each answer in turn, the last repeated) and records each move. */
function serve(
  answers: ({ standings: Standing[]; strength_block?: boolean; kit_listed?: boolean } | number)[],
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
        : Response.json({ today: '2026-10-25', strength_block: false, kit_listed: true, ...answer })
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

test("each step's question is a hint under its name; nothing moves from it (G1)", async () => {
  const strict = 'Can you do 5 strict pull-ups, from a full hang to your chin over the bar?'
  const calls = serve([
    {
      standings: [
        make({
          status: 'hold',
          ladder: LADDER.map((r) => (r.id === 2 ? { ...r, question: strict } : r)),
        }),
      ],
    },
  ])
  render(<Levels />)
  await showAll()
  await open(/Pull-up/)
  const steps = screen.getAllByRole('listitem').filter((li) => li.closest('ol'))
  expect(steps[0]).toHaveTextContent(/^Slow negatives$/)
  expect(within(steps[1]).getByText(`Ready for this if yes: ${strict}`)).toBeInTheDocument()
  expect(calls).toEqual([])
})

test('a loaded exercise names its weights, as on Progress (ADR-0072)', async () => {
  serve([
    {
      standings: [
        make({
          exercise: 'Hammer curl',
          slug: 'hammer-curl',
          status: 'hold',
          last: [10, 9, 8],
          last_kg: [16, 18, null],
          best_set: 12,
          best_kg: 14.5,
        }),
      ],
    },
  ])
  render(<Levels />)
  await showAll()
  await open(/Hammer curl/)
  expect(
    screen.getByText('Last 10 · 9 · 8 at 16 / 18 / – kg · best 12 at 14.5 kg'),
  ).toBeInTheDocument()
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
  expect(say('no_next_step')).toBe(
    'Pull-up is on the last step in your plan, or the last one open to you.',
  )
  expect(say('strength_block')).toMatch(/waits for the hypertrophy block/)
  expect(say('same_level')).toBe('Pull-up is already on Pause at top.')
  expect(say('level_set', null)).toMatch(/Targets for it start fresh/)
  expect(say('stepped_down', 'Slow negatives')).toBe(
    'Pull-up is now on Slow negatives. Targets for Slow negatives start fresh from its own history.',
  )
  expect(say('no_step_below')).toMatch(/no step below/)
  expect(say('stayed_down')).toMatch(/^Staying on Pause at top\. You'll be asked again/)
  expect(wanted('?move=pull-up')).toBe('pull-up')
  expect(wanted('')).toBeNull()
  expect(moveHref('a b')).toBe('/plan?move=a%20b')
  expect(nextRung(make({ step_id: 4 }))).toBeNull()
  expect(nextRung(make({ step_id: 99 }))).toBeNull()
})

const LOCKED = [
  { id: 1, name: 'Two-hand, 8 kg', cue: null, missing: [], avoided: [], question: null },
  { id: 2, name: 'One-arm, 8 kg', cue: null, missing: [], avoided: [], question: null },
  {
    id: 3,
    name: 'Two-hand, 16 kg',
    cue: null,
    missing: ['a 16 kg kettlebell'],
    avoided: [],
    question: null,
  },
  {
    id: 4,
    name: 'One-arm, 16 kg',
    cue: null,
    missing: ['a 16 kg kettlebell'],
    avoided: [],
    question: null,
  },
]

const swing = (over: Partial<Standing> = {}) =>
  make({
    exercise: 'Swing',
    slug: 'swing',
    step: 'One-arm, 8 kg',
    ladder: LOCKED,
    status: 'top_of_ladder',
    unlock: 'a 16 kg kettlebell unlocks Two-hand, 16 kg',
    ...over,
  })

test('a locked step says what it needs; at the top for the kit, what unlocks the next', async () => {
  serve([{ standings: [swing()], kit_listed: true }])
  render(<Levels />)
  await showAll()
  expect(screen.getByRole('button', { name: /Swing.*Top for your kit/ })).toBeInTheDocument()
  expect(screen.queryByText(/No kit listed/)).not.toBeInTheDocument()
  await open(/Swing/)
  const steps = screen.getAllByRole('listitem').filter((li) => li.closest('ol'))
  expect(steps.map((li) => li.textContent)).toEqual([
    'Two-hand, 8 kg',
    'One-arm, 8 kg (now)',
    'Two-hand, 16 kg · Locked: needs a 16 kg kettlebell',
    'One-arm, 16 kg · Locked: needs a 16 kg kettlebell',
  ])
  expect(screen.getByText(/a 16 kg kettlebell unlocks Two-hand, 16 kg\./)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'My equipment' })).toHaveAttribute(
    'href',
    '/account#my-equipment',
  )
  expect(screen.queryByText('This is the last step on the ladder.')).not.toBeInTheDocument()
})

test('Move up goes past a locked step to the next one the kit allows', async () => {
  const ladder = [
    LOCKED[0],
    LOCKED[2],
    { id: 5, name: 'Two-hand, 12 kg', cue: null, missing: [], avoided: [], question: null },
  ]
  serve([
    {
      standings: [
        swing({ step: 'Two-hand, 8 kg', step_id: 1, ladder, status: 'ready', unlock: null }),
      ],
      kit_listed: true,
    },
  ])
  render(<Levels />)
  await open(/Swing/)
  expect(screen.getByRole('button', { name: 'Move up to Two-hand, 12 kg' })).toBeInTheDocument()
})

test('choosing a locked level by hand is allowed, with the warning', async () => {
  const calls = serve([{ standings: [swing({ status: 'hold' })], kit_listed: true }], {
    outcome: 'level_set',
    exercise: 'Swing',
    step: 'Two-hand, 16 kg',
    warning: 'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.',
  })
  render(<Levels />)
  await showAll()
  await open(/Swing/)
  fireEvent.click(screen.getByRole('button', { name: 'Change level' }))
  const choose = screen.getByRole('group', { name: 'Choose a level for Swing' })
  fireEvent.click(within(choose).getByRole('radio', { name: /Two-hand, 16 kg/ }))
  expect(
    within(choose).getByText(
      'Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit. You can still choose it.',
    ),
  ).toBeInTheDocument()
  const set = within(choose).getByRole('button', { name: 'Set level to Two-hand, 16 kg' })
  expect(set).toBeEnabled()
  fireEvent.click(set)
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Swing is now on Two-hand, 16 kg. Targets for Two-hand, 16 kg start fresh from its own history. Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.',
  )
  expect(calls).toEqual([{ path: '/api/progress/swing/level', body: { step_id: 3 } }])
})

test('no kit listed: says nothing is locked and links to My equipment', async () => {
  serve([{ standings: [make()], kit_listed: false }])
  render(<Levels />)
  expect(await screen.findByText(/No kit listed, so no step is locked/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'List your kit in My equipment' })).toHaveAttribute(
    'href',
    '/account#my-equipment',
  )
})

const HANG = "needs hanging from a bar — you've chosen not to hang"
const FLOOR = "needs the floor — you've chosen to keep off it"

test('a step the person avoids is locked with the reason, and Move up skips it', async () => {
  const ladder = [
    LADDER[0],
    LADDER[1],
    { ...LADDER[2], avoided: [HANG] },
    { ...LADDER[3], missing: ['a pull-up bar'], avoided: [FLOOR] },
    { id: 5, name: 'One-arm negatives', cue: null, missing: [], avoided: [], question: null },
  ]
  serve([{ standings: [make({ ladder, steps: 5 })], kit_listed: true }])
  render(<Levels />)
  await open(/Pull-up/)
  const steps = screen.getAllByRole('listitem').filter((li) => li.closest('ol'))
  expect(steps.map((li) => li.textContent)).toEqual([
    'Slow negatives',
    'Strict pull-up (now)',
    `Pause at top · Locked: ${HANG}`,
    `Weighted backpack · Locked: needs a pull-up bar; ${FLOOR}`,
    'One-arm negatives',
  ])
  expect(screen.getByRole('button', { name: 'Move up to One-arm negatives' })).toBeInTheDocument()
  expect(screen.queryByText(/You've chosen to avoid this/)).not.toBeInTheDocument()
})

test('a step someone is on and now avoids says so, and their level stays', async () => {
  const ladder = LADDER.map((r) => ({ ...r, avoided: [HANG] }))
  const calls = serve([{ standings: [make({ ladder, status: 'top_of_ladder' })] }])
  render(<Levels />)
  // Shown without "Show all", like a ready one, so it isn't missed.
  const panel = await screen.findByRole('button', { name: /Pull-up/, expanded: false })
  expect(panel).toHaveTextContent("You've chosen to avoid this; pick another step.")
  expect(panel).toHaveTextContent('Top of your open steps')
  expect(panel).not.toHaveTextContent('Top of the ladder')
  fireEvent.click(panel)
  expect(
    screen.getByText('No step above this one is open to you: each says why above.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Move up/ })).not.toBeInTheDocument()
  expect(calls).toEqual([]) // nothing moved by itself
})

test('choosing an avoided level by hand is allowed, with the reason', async () => {
  const ladder = [LADDER[0], LADDER[1], { ...LADDER[2], avoided: [HANG] }, LADDER[3]]
  serve([{ standings: [make({ ladder, status: 'hold' })] }])
  render(<Levels />)
  await showAll()
  await open(/Pull-up/)
  fireEvent.click(screen.getByRole('button', { name: 'Change level' }))
  const choose = screen.getByRole('group', { name: 'Choose a level for Pull-up' })
  fireEvent.click(within(choose).getByRole('radio', { name: /Pause at top/ }))
  expect(
    within(choose).getByText(`Pause at top ${HANG}. You can still choose it.`),
  ).toBeInTheDocument()
  expect(within(choose).getByRole('button', { name: 'Set level to Pause at top' })).toBeEnabled()
})

test('the top of the ladder is said only when there is no step above', () => {
  expect(topLabel(make({ status: 'top_of_ladder', step_id: 4 }))).toBe('Top of the ladder')
  expect(topLabel(make({ status: 'top_of_ladder', step_id: 99 }))).toBe('Top of the ladder')
  expect(topLabel(make({ status: 'hold' }))).toBeNull()
})
