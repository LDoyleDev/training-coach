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
const DONE_TODAY = { kind: 'done', session: null, since_last: 0, picked: false }
const view = (sessions: unknown[], queue = {}) => ({
  revision: 'abc',
  sessions,
  catalogue: [PUSH],
  limits: { max_sessions: 10, max_cycle_days: 14, max_rest: 6 },
  last_done: null,
  queued: [],
  today: DONE_TODAY, // today is settled: no Today line unless a test says otherwise
  ...queue,
})
const WEEK = view([
  session('legs', 'Legs', 1, { kind: 'conditioning' }),
  session('torso', 'Torso', 1, { next: true }),
  session('arms', 'Arms', 2, { logged: 14 }),
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
    card.getByText('Your cycle, 7 days: Legs, rest, Torso, rest, Arms, rest, rest.'),
  ).toBeInTheDocument()
  expect(card.queryByText(/comes round/)).not.toBeInTheDocument()
})

test('rest days after − and + change the week, held to 0-6', async () => {
  const sent = serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  expect(
    card.getByText('Your cycle, 8 days: Legs, rest, rest, Torso, rest, Arms, rest, rest.'),
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
      'With it, your cycle, 7 days: Legs, rest, Torso, rest, Arms, rest, New session.',
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
    card.getByText('Your cycle, 7 days: Legs, Legs 2, Torso, rest, Arms, rest, rest.'),
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
    'Your cycle, 1 day: Arms.',
  )
  expect(lengthLine(5)).toBe('Each session comes round more often than once a week.')
  expect(thenRest(0)).toBe('then no rest days')
  expect(freeName('Legs 2', [...cycle, { ...cycle[0]!, name: 'Legs 2' }], false)).toBe('Legs 3')
  expect(freeName('Legs', cycle, true)).toBe('Legs 2')
  expect(newKey([...cycle, { ...cycle[0]!, key: 'n1' }])).toBe('n2')
})

const savingWill = () =>
  within(screen.getByRole('group', { name: 'Saving will' }))
    .getAllByRole('listitem')
    .map((li) => li.textContent)
const noteBox = () => screen.getByRole('textbox', { name: /What changed/ })

test('Remove asks first, in words by its history, and saves without it', async () => {
  const sent = serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Remove Legs' }))
  expect(card.getByRole('group', { name: 'Remove Legs' })).toHaveTextContent(
    'Remove Legs? Nothing is logged for it, so it goes.',
  )
  fireEvent.click(card.getByRole('button', { name: 'Keep it' }))
  expect(screen.queryByRole('group', { name: 'Saving will' })).not.toBeInTheDocument()
  fireEvent.click(card.getByRole('button', { name: 'Remove Arms' }))
  const ask = within(card.getByRole('group', { name: 'Remove Arms' }))
  expect(
    ask.getByText('Remove Arms? Its 14 logged days stay in your history under its name.'),
  ).toBeInTheDocument()
  fireEvent.click(ask.getByRole('button', { name: 'Remove' }))
  expect(
    card.getByText('Your cycle, 7 days: Legs, rest, Torso, rest, rest, rest, rest.'),
  ).toBeInTheDocument()
  expect(savingWill()).toEqual([
    'Give Torso 4 rest days after it',
    'Remove Arms',
    'Next stays Torso',
  ])
  expect(noteBox()).toHaveValue('Torso now has 4 rest days after it; removed Arms')
  fireEvent.click(screen.getByRole('button', { name: 'Save as a new version' }))
  await screen.findByText('Saved as a new version of your plan.')
  expect(sent[0]).toMatchObject({
    note: 'Torso now has 4 rest days after it; removed Arms',
    cycle: [
      { slug: 'legs', name: 'Legs', kind: 'conditioning', rest_after: 1 },
      { slug: 'torso', name: 'Torso', kind: 'strength', rest_after: 4 },
    ],
  })
})

test('the last session has no Remove', async () => {
  serve(view([session('only', 'Only', 6)]))
  render(<PlanEdit />)
  const card = await cycleCard()
  expect(card.getByRole('button', { name: 'Rename Only' })).toBeInTheDocument()
  expect(card.queryByRole('button', { name: 'Remove Only' })).not.toBeInTheDocument()
})

test('Up and Down move a session, held at the ends, and the list says so', async () => {
  serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  expect(card.getByRole('button', { name: 'Move Legs up' })).toBeDisabled()
  expect(card.getByRole('button', { name: 'Move Arms down' })).toBeDisabled()
  fireEvent.click(card.getByRole('button', { name: 'Move Arms up' }))
  expect(
    card.getByText('Your cycle, 7 days: Legs, rest, Arms, rest, rest, Torso, rest.'),
  ).toBeInTheDocument()
  expect(savingWill()).toEqual(['Move Arms to place 2', 'Next stays Torso'])
  expect(noteBox()).toHaveValue('Moved Arms')
  fireEvent.click(card.getByRole('button', { name: 'Move Arms down' }))
  expect(screen.queryByRole('group', { name: 'Saving will' })).not.toBeInTheDocument()
  expect(noteBox()).toHaveValue('')
})

test('what is next: kept, moved off a removed session, or turning on the last session', async () => {
  serve(WEEK)
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Remove Torso' }))
  fireEvent.click(
    within(card.getByRole('group', { name: 'Remove Torso' })).getByRole('button', {
      name: 'Remove',
    }),
  )
  expect(savingWill().at(-1)).toBe('Next: Arms, instead of Torso')
  fireEvent.change(noteBox(), { target: { value: 'My words' } })
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  fireEvent.change(form.getByRole('combobox', { name: 'Goes after' }), { target: { value: '0' } })
  fireEvent.click(form.getByRole('button', { name: 'Add' }))
  expect(savingWill()).toContain('Add New session after Legs, with 1 rest day after it')
  expect(savingWill().at(-1)).toBe('Next: Arms, instead of Torso') // nothing done yet
  expect(noteBox()).toHaveValue('My words') // typed words stay
})

test('a renamed or rekinded session is listed, and a long list makes a short note', async () => {
  serve(view([...Array(6).keys()].map((i) => session(`s${i}`, `Session number ${i + 1}`, 0))))
  render(<PlanEdit />)
  const card = await cycleCard()
  for (let i = 1; i <= 6; i++)
    fireEvent.click(
      card.getByRole('button', { name: `One rest day more after Session number ${i}` }),
    )
  expect(noteBox()).toHaveValue('6 changes to your sessions')
  fireEvent.click(card.getByRole('button', { name: 'Rename Session number 1' }))
  fireEvent.change(card.getByRole('textbox', { name: 'New name for Session number 1' }), {
    target: { value: 'First' },
  })
  fireEvent.click(card.getByRole('button', { name: 'Done' }))
  expect(savingWill()[0]).toBe('Rename Session number 1 to First')
})

const WEEK_ON = (queue: object) => view(WEEK.sessions, queue)
const removeSession = (card: ReturnType<typeof within>, name: string) => {
  fireEvent.click(card.getByRole('button', { name: `Remove ${name}` }))
  fireEvent.click(
    within(card.getByRole('group', { name: `Remove ${name}` })).getByRole('button', {
      name: 'Remove',
    }),
  )
}

test('a session added straight after the one done last is next, its split after it', async () => {
  serve(WEEK_ON({ last_done: 'legs' }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  fireEvent.change(form.getByRole('combobox', { name: 'Goes after' }), { target: { value: '0' } })
  fireEvent.click(form.getByRole('button', { name: 'Add' }))
  expect(savingWill()).toEqual([
    'Add New session after Legs, with no rest days after it',
    'Give Legs no rest days after it',
    'Next: New session, instead of Torso',
  ])
  expect(noteBox()).toHaveValue('Added New session; Legs now has no rest days after it')
})

test("a swap's queue is next when the next session goes", async () => {
  serve(WEEK_ON({ queued: ['legs'] }))
  render(<PlanEdit />)
  removeSession(await cycleCard(), 'Torso')
  expect(savingWill().at(-1)).toBe('Next: Legs, instead of Torso')
})

test('a rest day today becomes a session day when its rest days go', async () => {
  const rest = { kind: 'rest', session: null, since_last: 1, picked: false }
  serve(WEEK_ON({ last_done: 'legs', today: rest }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day fewer after Legs' }))
  expect(savingWill().slice(-2)).toEqual(['Next stays Torso', 'Today has a session: Torso'])
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  expect(savingWill().at(-1)).toBe('Next stays Torso') // still a rest day
})

test('a session day today becomes a rest day, or has another session', async () => {
  const offered = { kind: 'session', session: 'torso', since_last: 2, picked: false }
  serve(WEEK_ON({ last_done: 'legs', today: offered }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  expect(savingWill().at(-1)).toBe('Today becomes a rest day')
  fireEvent.click(card.getByRole('button', { name: 'One rest day fewer after Legs' }))
  fireEvent.click(card.getByRole('button', { name: 'Add a session' }))
  const form = within(card.getByRole('form', { name: 'Add a session' }))
  fireEvent.change(form.getByRole('combobox', { name: 'Goes after' }), { target: { value: '0' } })
  fireEvent.click(form.getByRole('button', { name: 'Add' }))
  expect(savingWill().slice(-2)).toEqual([
    'Next: New session, instead of Torso',
    'Today has a session: New session',
  ])
})

test('a pick today holds, unless its session goes; before the start nothing changes', async () => {
  const picked = { kind: 'session', session: 'arms', since_last: 1, picked: true }
  serve(WEEK_ON({ last_done: 'legs', today: picked }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day more after Legs' }))
  expect(savingWill().at(-1)).toBe('Next stays Torso')
  removeSession(card, 'Arms')
  expect(savingWill().at(-1)).toBe('Today becomes a rest day')
})

test('before the plan starts, a rest day stays one', async () => {
  const waiting = { kind: 'rest', session: null, since_last: null, picked: false }
  serve(WEEK_ON({ today: waiting }))
  render(<PlanEdit />)
  const card = await cycleCard()
  fireEvent.click(card.getByRole('button', { name: 'One rest day fewer after Legs' }))
  expect(savingWill().at(-1)).toBe('Next stays Torso')
})
