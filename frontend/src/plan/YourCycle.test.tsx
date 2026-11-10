import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import PlanEdit from './PlanEdit'
import { cycleOf, freeName, lengthLine, newKey, thenRest, weekLine } from './cycleDraft'

const SQUAT = {
  exercise: 'squat',
  name: 'Squat',
  sets: 3,
  rep_min: 8,
  rep_max: 12,
  per_side: false,
  pair: null,
}
const session = (slug: string, name: string, rest_after: number, more = {}) => ({
  slug,
  name,
  focus: 'x',
  kind: 'strength',
  rest_after,
  optional: false,
  next: false,
  logged: 0,
  home: [SQUAT],
  gym: [],
  away: [],
  ...more,
})
const PUSH = {
  slug: 'push-up',
  name: 'Push-up',
  kind: 'reps',
  per_side: false,
  muscles: { chest: 1 },
  pattern: 'horizontal push',
  places: ['home', 'gym', 'away'],
  range: null,
  first_step: 'Hands on a wall',
  levels: [1, 6],
  needs: [],
  lengthened: false,
}
const view = (sessions: unknown[]) => ({
  revision: 'abc',
  sessions,
  catalogue: [PUSH],
  limits: { max_sessions: 10, max_cycle_days: 14, max_rest: 6 },
})
const WEEK = view([
  session('legs', 'Legs', 1, { kind: 'conditioning' }),
  session('torso', 'Torso', 1, { next: true }),
  session('arms', 'Arms', 2),
])

const drafts: { cycle?: unknown }[] = []

/** The API with `first` loaded; a save answers `post` and the next load is `after`. */
function serve(first: unknown, post?: Response, after: unknown = first) {
  const sent: Record<string, unknown>[] = []
  drafts.length = 0
  let loaded = first
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/api/plan/coverage/draft') {
        drafts.push(JSON.parse(String(init?.body)))
        return new Response(null, { status: 401 })
      }
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        loaded = after
        return post ?? Response.json({ revision: 'def', version: 'Note', slugs: {} })
      }
      return Response.json(loaded)
    }),
  )
  return sent
}

const cycleCard = async () => within(await screen.findByRole('region', { name: 'Your cycle' }))
const saveWith = (text: string) => {
  fireEvent.change(screen.getByRole('textbox', { name: /What changed/ }), {
    target: { value: text },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save as a new version' }))
}

afterEach(() => vi.unstubAllGlobals())

test('the card lists the sessions in order, marks the next and says the week', async () => {
  serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  const rows = card.getAllByRole('listitem')
  expect(rows.map((r) => r.textContent)).toEqual([
    expect.stringContaining('LegsCardio · then 1 rest day'),
    expect.stringContaining('TorsoNextStrength · then 1 rest day'),
    expect.stringContaining('ArmsStrength · then 2 rest days'),
  ])
  expect(
    card.getByText('Your cycle: Legs, rest, Torso, rest, Arms, rest, rest. 7 days.'),
  ).toBeInTheDocument()
  expect(card.queryByText(/comes round/)).not.toBeInTheDocument()
})

test('rest days after − and + change the week, held to 0-6', async () => {
  const sent = serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  expect(
    card.getByText('Your cycle: Legs, rest, rest, Torso, rest, Arms, rest, rest. 8 days.'),
  ).toBeInTheDocument()
  expect(
    card.getByText('Each session comes round less often than once a week.'),
  ).toBeInTheDocument()
  const fewer = card.getByRole('button', { name: 'One rest day fewer after Torso' })
  fireEvent.click(fewer)
  expect(fewer).toBeDisabled()
  await vi.waitFor(() => expect(drafts.at(-1)?.cycle).toBeDefined(), { timeout: 2000 })
  saveWith('More rest after legs')
  await screen.findByText('Saved as a new version of your plan.')
  expect(sent[0]!.cycle).toEqual([
    { slug: 'legs', name: 'Legs', kind: 'conditioning', rest_after: 2 },
    { slug: 'torso', name: 'Torso', kind: 'strength', rest_after: 0 },
    { slug: 'arms', name: 'Arms', kind: 'strength', rest_after: 2 },
  ])
  expect(sent[0]!.versions).toEqual([])
})

test('an empty session goes after the suggestion, opens the picker and saves with its exercise', async () => {
  const saved = view([...WEEK.sessions, session('new-session', 'New session', 0)])
  const sent = serve(
    WEEK,
    Response.json({ revision: 'def', version: 'Note', slugs: { n1: 'new-session' } }),
    saved,
  )
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  expect(form.getByRole('textbox', { name: 'Name' })).toHaveValue('New session')
  expect(form.getByRole('radio', { name: 'Strength' })).toBeChecked()
  expect(form.getByRole('radio', { name: 'Recovery' })).toHaveAccessibleDescription(
    'No warm-up, and never cut short.',
  )
  expect(form.getByRole('combobox', { name: 'Goes after' })).toHaveDisplayValue('Arms')
  expect(
    form.getByText(
      'With it, your cycle: Legs, rest, Torso, rest, Arms, rest, New session. 7 days.',
    ),
  ).toBeInTheDocument()
  fireEvent.click(form.getByRole('button', { name: 'Add' }))
  expect(screen.getByRole('combobox', { name: 'Session' })).toHaveValue('new:n1')
  expect(screen.getByText('Add: what should it train?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Push-up' }))
  saveWith('Added a session')
  await screen.findByText('Saved as a new version of your plan.')
  expect(sent[0]!.cycle).toEqual([
    { slug: 'legs', name: 'Legs', kind: 'conditioning', rest_after: 1 },
    { slug: 'torso', name: 'Torso', kind: 'strength', rest_after: 1 },
    { slug: 'arms', name: 'Arms', kind: 'strength', rest_after: 1 },
    { new: 'n1', name: 'New session', kind: 'strength', rest_after: 0, copy_of: null },
  ])
  expect(sent[0]!.versions).toEqual([
    {
      slug: 'new:n1',
      place: 'home',
      items: [
        { exercise: 'push-up', sets: 3, rep_min: 8, rep_max: 12, per_side: false, pair: null },
      ],
    },
  ])
  expect(screen.getByRole('combobox', { name: 'Session' })).toHaveValue('new-session')
})

test('a copy is named, kinded and filled from its session, and goes where it is put', async () => {
  const sent = serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  fireEvent.change(form.getByRole('combobox', { name: 'Start from' }), {
    target: { value: 'legs' },
  })
  expect(form.getByRole('textbox', { name: 'Name' })).toHaveValue('Legs 2')
  expect(form.getByRole('radio', { name: 'Cardio' })).toBeChecked()
  fireEvent.change(form.getByRole('combobox', { name: 'Goes after' }), { target: { value: '0' } })
  fireEvent.click(form.getByRole('radio', { name: 'Recovery' }))
  fireEvent.click(form.getByRole('button', { name: 'Add' }))
  expect(
    card.getByText('Your cycle: Legs, Legs 2, Torso, rest, Arms, rest, rest. 7 days.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('Add: what should it train?')).not.toBeInTheDocument()
  expect(screen.getByRole('group', { name: 'Sets of Squat' })).toBeInTheDocument()
  saveWith('Second legs day')
  await screen.findByText('Saved as a new version of your plan.')
  expect((sent[0]!.cycle as unknown[])[1]).toEqual({
    new: 'n1',
    name: 'Legs 2',
    kind: 'recovery',
    rest_after: 0,
    copy_of: 'legs',
  })
  expect(sent[0]!.versions).toEqual([]) // the server copies its versions
})

test('the form can be cancelled, and refuses a cycle past 14 days', async () => {
  serve(view([session('a', 'A', 6), session('b', 'B', 5), session('c', 'C', 0)]))
  render(<PlanEdit />)
  const card = await cycleCard()
  expect(card.getByRole('button', { name: 'One rest day more after C' })).toBeDisabled()
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  fireEvent.change(form.getByRole('combobox', { name: 'Goes after' }), { target: { value: '2' } })
  expect(form.getByText('Your cycle would be 15 days; it can be at most 14.')).toBeInTheDocument()
  expect(form.getByRole('button', { name: 'Add' })).toBeDisabled()
  fireEvent.click(form.getByRole('button', { name: 'Cancel' }))
  expect(card.queryByRole('form')).not.toBeInTheDocument()
})

test('at 10 sessions Add is greyed with the reason', async () => {
  serve(view([...Array(10).keys()].map((i) => session(`s${i}`, `S${i}`, 0))))
  render(<PlanEdit />)
  const card = await cycleCard()
  expect(card.getByRole('button', { name: 'Add a session' })).toBeDisabled()
  expect(card.getByRole('button', { name: 'Add a session' })).toHaveAccessibleDescription(
    'You have 10 sessions, the most a cycle can have.',
  )
})

test('a rename is drafted, and the server’s refusal is shown in its words', async () => {
  const words = 'Squat is an exercise’s name; pick another for a session.'
  const sent = serve(WEEK, Response.json({ detail: words }, { status: 422 }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Rename Arms' }))
  fireEvent.click(card.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(card.getByRole('button', { name: 'Rename Torso' }))
  fireEvent.change(card.getByRole('textbox', { name: 'New name for Torso' }), {
    target: { value: ' Squat ' },
  })
  fireEvent.click(card.getByRole('button', { name: 'Done' }))
  expect(card.getByRole('button', { name: 'Rename Squat' })).toBeInTheDocument()
  saveWith('Renamed')
  expect(await screen.findByRole('status')).toHaveTextContent(words)
  expect((sent[0]!.cycle as { name: string }[])[1]!.name).toBe('Squat')
})

test('the week line, names and keys', () => {
  const cycle = cycleOf(WEEK.sessions as never)
  expect(weekLine(cycle.slice(2, 3).map((e) => ({ ...e, restAfter: 0 })))).toBe(
    'Your cycle: Arms. 1 day.',
  )
  expect(lengthLine(5)).toBe('Each session comes round more often than once a week.')
  expect(thenRest(0)).toBe('then no rest days')
  expect(freeName('Legs 2', [...cycle, { ...cycle[0]!, name: 'Legs 2' }], false)).toBe('Legs 3')
  expect(freeName('Legs', cycle, true)).toBe('Legs 2')
  expect(newKey([...cycle, { ...cycle[0]!, key: 'n1' }])).toBe('n2')
})
