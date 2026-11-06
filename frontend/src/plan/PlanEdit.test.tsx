import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import PlanEdit from './PlanEdit'

const PULL = {
  exercise: 'pull-up',
  name: 'Pull-up',
  sets: 4,
  rep_min: 5,
  rep_max: 12,
  per_side: false,
  pair: null,
}
const DIP = { ...PULL, exercise: 'dip', name: 'Dip', sets: 3, rep_min: 8, rep_max: 15 }
const VIEW = {
  revision: 'abc',
  sessions: [
    { slug: 'upper', name: 'Upper', focus: 'x', home: [PULL, DIP], gym: [], away: [] },
    { slug: 'arms', name: 'Arms', focus: 'x', home: [DIP], gym: [], away: [] },
  ],
  catalogue: [
    {
      slug: 'push-up',
      name: 'Push-up',
      kind: 'reps',
      per_side: false,
      muscles: { chest: 1 },
      pattern: 'horizontal push',
      places: ['home', 'gym', 'away'],
      range: null,
    },
    {
      slug: 'lat-pulldown',
      name: 'Lat pulldown',
      kind: 'reps',
      per_side: false,
      muscles: { lats: 1 },
      pattern: 'vertical pull',
      places: ['gym'],
      range: [8, 12],
    },
  ],
}

const drafts: unknown[] = []
let map = new Response(null, { status: 401 })

function serve(post: Response = Response.json({ revision: 'def', version: 'Note' })) {
  const sent: unknown[] = []
  drafts.length = 0
  map = new Response(null, { status: 401 })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (_path === '/api/plan/coverage/draft') {
        drafts.push(JSON.parse(String(init?.body)))
        return map
      }
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        return post
      }
      return Response.json(VIEW)
    }),
  )
  return sent
}

const save = () => screen.getByRole('button', { name: 'Save as a new version' })
const note = () => screen.getByRole('textbox', { name: /What changed/ })

afterEach(() => vi.unstubAllGlobals())

test('nothing can be saved until something changed and a note is written', async () => {
  serve()
  render(<PlanEdit />)
  expect(await screen.findByRole('heading', { name: 'Edit your plan' })).toBeInTheDocument()
  expect(save()).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'One set more of Pull-up' }))
  expect(save()).toBeDisabled()
  fireEvent.change(note(), { target: { value: 'More pull-ups' } })
  expect(save()).toBeEnabled()
})

test('saves only the versions that changed, with the revision and note', async () => {
  const sent = serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'One set more of Pull-up' }))
  fireEvent.change(note(), { target: { value: ' More pull-ups ' } })
  fireEvent.click(save())
  expect(await screen.findByRole('status')).toHaveTextContent('Saved as a new version')
  expect(sent).toEqual([
    {
      revision: 'abc',
      note: 'More pull-ups',
      versions: [
        {
          slug: 'upper',
          place: 'home',
          items: [
            { exercise: 'pull-up', sets: 5, rep_min: 5, rep_max: 12, per_side: false, pair: null },
            { exercise: 'dip', sets: 3, rep_min: 8, rep_max: 15, per_side: false, pair: null },
          ],
        },
      ],
    },
  ])
})

test('moving, removing and changing a range change the list', async () => {
  const sent = serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'Move Dip up' }))
  const rows = screen.getAllByRole('listitem').filter((row) => within(row).queryByText('Pull-up'))
  fireEvent.change(within(rows[0]!).getByRole('spinbutton', { name: 'To' }), {
    target: { value: '10' },
  })
  fireEvent.change(note(), { target: { value: 'Dips first' } })
  fireEvent.click(save())
  await screen.findByRole('status')
  const body = sent[0] as { versions: { items: { exercise: string; rep_max: number }[] }[] }
  expect(body.versions[0]!.items.map((i) => [i.exercise, i.rep_max])).toEqual([
    ['dip', 15],
    ['pull-up', 10],
  ])
})

test('a blank range box is ignored, not saved as nothing', async () => {
  serve()
  render(<PlanEdit />)
  await screen.findByRole('heading', { name: 'Edit your plan' })
  fireEvent.change(screen.getAllByRole('spinbutton', { name: 'From' })[0]!, {
    target: { value: '' },
  })
  expect(screen.getAllByRole('spinbutton', { name: 'From' })[0]).toHaveValue(5)
})

test('adding from the picker offers only what can be done at this place', async () => {
  const sent = serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'Add an exercise' }))
  expect(screen.getByRole('button', { name: 'Push-up' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Lat pulldown' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Push-up' }))
  fireEvent.change(note(), { target: { value: 'Add push-ups' } })
  fireEvent.click(save())
  await screen.findByRole('status')
  const body = sent[0] as { versions: { items: { exercise: string; sets: number }[] }[] }
  expect(body.versions[0]!.items.at(-1)).toMatchObject({ exercise: 'push-up', sets: 3 })
})

test('the gym tab starts empty, and its picker has the gym exercises', async () => {
  serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'Gym' }))
  expect(screen.getByText('Done the same way at the gym.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Add an exercise' }))
  fireEvent.click(screen.getByRole('button', { name: 'Lat pulldown' }))
  expect(screen.getByRole('spinbutton', { name: 'To' })).toHaveValue(12)
})

test('swapping keeps the sets and range', async () => {
  serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'Swap Dip' }))
  expect(screen.getByText(/Swap Dip: what should it train/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Push-up' }))
  expect(screen.queryByRole('button', { name: 'Swap Dip' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Swap Push-up' })).toBeInTheDocument()
  expect(screen.getByRole('group', { name: 'Sets of Push-up' })).toHaveTextContent('3 sets')
})

test('the picker filters by muscle and can be closed', async () => {
  serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'Add an exercise' }))
  fireEvent.change(screen.getByRole('combobox', { name: /what should it train/ }), {
    target: { value: 'lats' },
  })
  expect(screen.queryByRole('button', { name: 'Push-up' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.getByRole('button', { name: 'Add an exercise' })).toBeInTheDocument()
})

test('alternating pairs an item with the next', async () => {
  const sent = serve()
  render(<PlanEdit />)
  const pair = await screen.findByRole('button', { name: 'Alternate Pull-up with the next' })
  fireEvent.click(pair)
  expect(pair).toHaveAttribute('aria-pressed', 'true')
  fireEvent.change(note(), { target: { value: 'Superset' } })
  fireEvent.click(save())
  await screen.findByRole('status')
  const body = sent[0] as { versions: { items: { pair: number | null }[] }[] }
  expect(body.versions[0]!.items.map((i) => i.pair)).toEqual([1, 1])
})

test('another session has its own list', async () => {
  serve()
  render(<PlanEdit />)
  fireEvent.change(await screen.findByRole('combobox', { name: 'Session' }), {
    target: { value: 'arms' },
  })
  expect(screen.queryByText('Pull-up')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Dip' }))
  expect(screen.getByRole('button', { name: 'Add an exercise' })).toBeInTheDocument()
})

test.each([
  [new Response(JSON.stringify({ detail: 'stale' }), { status: 409 }), 'Your plan changed'],
  [
    new Response(JSON.stringify({ detail: 'in-progress' }), { status: 409 }),
    'Finish or discard your session',
  ],
  [
    new Response(JSON.stringify({ detail: 'A session needs at least one exercise.' }), {
      status: 422,
    }),
    'at least one exercise',
  ],
  [new Response(null, { status: 401 }), 'Your sign-in ended'],
  [new Response(null, { status: 500 }), "That didn't work"],
])('a refused or failed save says why', async (post, message) => {
  serve(post)
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'One set more of Pull-up' }))
  fireEvent.change(note(), { target: { value: 'Note' } })
  fireEvent.click(save())
  expect(await screen.findByRole('status')).toHaveTextContent(message)
})

test('the map is asked for with the draft, after the tapping stops', async () => {
  serve()
  render(<PlanEdit />)
  fireEvent.click(await screen.findByRole('button', { name: 'One set more of Pull-up' }))
  fireEvent.click(screen.getByRole('button', { name: 'One set more of Pull-up' }))
  await vi.waitFor(() => expect(drafts.length).toBeGreaterThan(0), { timeout: 2000 })
  const last = drafts.at(-1) as { place: string; versions: { items: { sets: number }[] }[] }
  expect(last.place).toBe('home')
  expect(last.versions[0]!.items[0]!.sets).toBe(6)
})

test('a failed map says so and the editor still works', async () => {
  serve()
  map = new Response(null, { status: 500 })
  render(<PlanEdit />)
  expect(await screen.findByRole('alert', {}, { timeout: 2000 })).toHaveTextContent(
    "Couldn't load the body map",
  )
  expect(screen.getByRole('button', { name: 'One set more of Pull-up' })).toBeEnabled()
})

test('signed out and a failed load say so', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  const { unmount } = render(<PlanEdit />)
  expect(await screen.findByText('Sign in to edit your plan.')).toBeInTheDocument()
  unmount()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  render(<PlanEdit />)
  expect(await screen.findByText(/Couldn't load your plan/)).toBeInTheDocument()
})
