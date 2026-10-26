import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Equipment, KitItem } from '../api'
import { blank, bodyOf, draftOf, token } from './kit'
import MyEquipment from './MyEquipment'

const KINDS: Equipment['kinds'] = [
  { kit: 'kettlebell', name: 'kettlebell' },
  { kit: 'dumbbells', name: 'dumbbells' },
  { kit: 'backpack', name: 'weighted vest or backpack' },
  { kit: 'band', name: 'band' },
  { kit: 'pull-up bar', name: 'pull-up bar' },
  { kit: 'dip bars', name: 'dip bars or two chairs' },
  { kit: 'bench', name: 'bench, stools or bed to lie on' },
  { kit: 'rings', name: 'rings' },
  { kit: 'box', name: 'step or box' },
  { kit: 'mat', name: 'mat' },
  { kit: 'ab wheel', name: 'ab wheel' },
]

const kit = (items: KitItem[], listed = true): Equipment => ({
  listed,
  saved_at: listed ? '2026-10-25T20:00:00Z' : null,
  items,
  kinds: KINDS,
})

const BELL: KitItem = { kit: 'kettlebell', kg: 16, label: '16 kg kettlebell', note: '' }
const STOOLS: KitItem = {
  kit: 'bench',
  label: 'bench, stools or bed to lie on',
  note: 'two stools',
}
const RANGE: KitItem = {
  kit: 'dumbbells',
  kg: 24,
  min_kg: 2,
  label: 'adjustable dumbbells, 2-24 kg',
  note: '',
}
const BAND: KitItem = { kit: 'band', resistance: 'light', label: 'light band', note: '' }

const UNLOCKS = {
  item: '16 kg kettlebell',
  summary: '16 kg kettlebell: 2 new steps',
  steps: [
    { exercise: 'Swing', slug: 'swing', step: 'Two-hand, 16 kg' },
    { exercise: 'Goblet squat', slug: 'goblet-squat', step: 'Heavier kettlebell' },
  ],
}

type Reply = { status: number; body?: unknown }

/** Answers each route in turn (the last repeated) and records what was asked. */
function serve(routes: Record<string, Reply[]>) {
  const asked: { route: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push({ route, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const replies = routes[route] ?? [{ status: 500 }]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]
      const body = reply.body === undefined ? null : JSON.stringify(reply.body)
      return new Response(body, { status: reply.status })
    }),
  )
  return asked
}

const puts = (asked: { route: string; body: unknown }[]) =>
  asked.filter((a) => a.route === 'PUT /api/equipment').map((a) => a.body)

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

test('no kit listed: nothing is locked; saving none is bodyweight only', async () => {
  const asked = serve({
    'GET /api/equipment': [{ status: 200, body: kit([], false) }],
    'PUT /api/equipment': [{ status: 200, body: kit([]) }],
  })
  render(<MyEquipment />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading your kit…')
  expect(await screen.findByText('No kit listed: nothing is locked.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'I have no kit: bodyweight only' }))
  expect(await screen.findByText('Bodyweight only.')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Saved: bodyweight only.')
  expect(puts(asked)).toEqual([{ items: [] }])
  expect(screen.queryByRole('button', { name: /bodyweight only/ })).not.toBeInTheDocument()
})

test('adding a kettlebell shows what it unlocks first, then saves the whole list', async () => {
  const asked = serve({
    'GET /api/equipment': [{ status: 200, body: kit([STOOLS]) }],
    'GET /api/equipment/unlocks?add=kettlebell%3A16': [{ status: 200, body: UNLOCKS }],
    'PUT /api/equipment': [{ status: 200, body: kit([STOOLS, BELL]) }],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: '+ kettlebell' }))
  const form = screen.getByRole('group', { name: 'Add: kettlebell' })
  const add = within(form).getByRole('button', { name: 'Add to my kit' })
  expect(add).toBeDisabled() // no weight yet
  fireEvent.change(within(form).getByLabelText('Weight (kg)'), { target: { value: '16kg' } })
  expect(within(form).getByText('Checking what it unlocks…')).toBeInTheDocument()
  expect(await within(form).findByText('16 kg kettlebell: 2 new steps')).toBeInTheDocument()
  expect(within(form).getByRole('link', { name: 'Swing' })).toHaveAttribute(
    'href',
    '/plan?move=swing',
  )
  expect(within(form).getByText(/Two-hand, 16 kg/)).toBeInTheDocument()
  fireEvent.click(add)
  expect(await screen.findByText('16 kg kettlebell')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Added to your kit.')
  expect(screen.queryByRole('group')).not.toBeInTheDocument()
  expect(puts(asked)).toEqual([
    {
      items: [
        { kit: 'bench', kg: null, min_kg: null, resistance: null, note: 'two stools' },
        { kit: 'kettlebell', kg: 16, note: '' },
      ],
    },
  ])
})

test('a refused save shows the server’s reason and keeps the form', async () => {
  serve({
    'GET /api/equipment': [{ status: 200, body: kit([BELL]) }],
    'GET /api/equipment/unlocks?add=kettlebell%3A16': [{ status: 200, body: UNLOCKS }],
    'PUT /api/equipment': [{ status: 422, body: { detail: '16 kg kettlebell is listed twice' } }],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: '+ kettlebell' }))
  fireEvent.change(screen.getByLabelText('Weight (kg)'), { target: { value: '16' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add to my kit' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('16 kg kettlebell is listed twice')
  expect(screen.getByRole('group', { name: 'Add: kettlebell' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('the saved kit: a bench says to check it is stable; edit and remove save the list', async () => {
  const asked = serve({
    'GET /api/equipment': [{ status: 200, body: kit([STOOLS, RANGE, BAND]) }],
    'GET /api/equipment/unlocks?add=dumbbells%3A2-32': [
      {
        status: 200,
        body: { item: 'x', summary: 'adjustable dumbbells, 2-32 kg: no new steps', steps: [] },
      },
    ],
    'PUT /api/equipment': [
      {
        status: 200,
        body: kit([STOOLS, { ...RANGE, kg: 32, label: 'adjustable dumbbells, 2-32 kg' }, BAND]),
      },
      { status: 200, body: kit([STOOLS, RANGE]) },
    ],
  })
  render(<MyEquipment />)
  expect(await screen.findByText('two stools')).toBeInTheDocument()
  expect(screen.getByText('Check it’s stable before loading it.')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Edit adjustable dumbbells, 2-24 kg' }))
  const form = screen.getByRole('group', { name: 'Edit: dumbbells' })
  expect(within(form).getByRole('radio', { name: 'Adjustable, with a range' })).toBeChecked()
  expect(within(form).getByLabelText('Lightest (kg)')).toHaveValue('2')
  expect(within(form).queryByText(/Checking/)).not.toBeInTheDocument() // unchanged: nothing new
  fireEvent.change(within(form).getByLabelText('Heaviest (kg)'), { target: { value: '32' } })
  expect(await within(form).findByText(/2-32 kg: no new steps/)).toBeInTheDocument()
  fireEvent.click(within(form).getByRole('button', { name: 'Save changes' }))
  expect(await screen.findByText('adjustable dumbbells, 2-32 kg')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Saved.')

  fireEvent.click(screen.getByRole('button', { name: 'Remove light band' }))
  expect(await screen.findByText('Removed light band.')).toBeInTheDocument()
  const [edited, removed] = puts(asked) as { items: { kit: string; kg?: number }[] }[]
  expect(edited.items[1]).toEqual({ kit: 'dumbbells', kg: 32, min_kg: 2, note: '' })
  expect(removed.items.map((i) => i.kit)).toEqual(['bench', 'dumbbells'])
})

test('removing the last item leaves bodyweight only', async () => {
  serve({
    'GET /api/equipment': [{ status: 200, body: kit([BELL]) }],
    'PUT /api/equipment': [{ status: 200, body: kit([]) }],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove 16 kg kettlebell' }))
  expect(await screen.findByText('Bodyweight only.')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(
    'Removed 16 kg kettlebell. Saved: bodyweight only.',
  )
})

test('a band takes its strength; kit without a weight asks straight away', async () => {
  const asked = serve({
    'GET /api/equipment': [{ status: 200, body: kit([]) }],
    'GET /api/equipment/unlocks?add=band%3Amedium': [{ status: 200, body: UNLOCKS }],
    'GET /api/equipment/unlocks?add=pull-up%20bar': [{ status: 500 }],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: '+ band' }))
  fireEvent.click(screen.getByRole('radio', { name: 'Medium' }))
  expect(await screen.findByText('16 kg kettlebell: 2 new steps')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: '+ pull-up bar' }))
  expect(
    await screen.findByText("Couldn't check what it unlocks. You can still add it."),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Add to my kit' })).toBeEnabled()
  expect(asked.map((a) => a.route)).toContain('GET /api/equipment/unlocks?add=pull-up%20bar')
})

test('the bench, a vest and dumbbells say what to enter; a bad weight says why', async () => {
  serve({
    'GET /api/equipment': [{ status: 200, body: kit([]) }],
    'GET /api/equipment/unlocks?add=backpack%3A10.3': [
      {
        status: 422,
        body: { detail: 'weighted vest or backpack, up to 10.3 kg: a weight from 0.5 to 100 kg' },
      },
    ],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: '+ bench, stools or bed to lie on' }))
  expect(screen.getByText(/flat bench, stools or a bed\. Check it’s stable/)).toBeInTheDocument()
  expect(screen.getByLabelText('Note (optional)')).toHaveAttribute('placeholder', 'two stools')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: '+ dumbbells' }))
  expect(screen.getByLabelText('Each dumbbell (kg)')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: '+ weighted vest or backpack' }))
  fireEvent.change(screen.getByLabelText('Loads up to (kg)'), { target: { value: '10,3' } })
  expect(await screen.findByText(/a weight from 0\.5 to 100 kg/)).toBeInTheDocument()
})

test.each([
  [{ status: 401 }, 'Your sign-in ended. Sign in again, then retry.'],
  [{ status: 500 }, "That didn't work. Nothing was saved; check your connection and try again."],
  [{ status: 422, body: { detail: [{ msg: 'bad' }] } }, 'That kit can’t be saved.'],
])('a failed save says so', async (reply, text) => {
  serve({
    'GET /api/equipment': [{ status: 200, body: kit([], false) }],
    'PUT /api/equipment': [reply],
  })
  render(<MyEquipment />)
  fireEvent.click(await screen.findByRole('button', { name: 'I have no kit: bodyweight only' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
})

test('a load error offers Try again; signed out shows nothing', async () => {
  serve({
    'GET /api/equipment': [{ status: 500 }, { status: 200, body: kit([BELL]) }],
  })
  const { unmount } = render(<MyEquipment />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your kit.")
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('16 kg kettlebell')).toBeInTheDocument()
  unmount()
  serve({ 'GET /api/equipment': [{ status: 401 }] })
  const { container } = render(<MyEquipment />)
  await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
})

test('a link to #my-equipment scrolls to the card once it loads', async () => {
  window.history.replaceState(null, '', '/account#my-equipment')
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  serve({ 'GET /api/equipment': [{ status: 200, body: kit([]) }] })
  render(<MyEquipment />)
  expect(await screen.findByText('Bodyweight only.')).toBeInTheDocument()
  expect(scroll).toHaveBeenCalledOnce()
})

test('the short forms the unlocks question takes', () => {
  expect(bodyOf(blank('kettlebell'))).toBeNull()
  expect(bodyOf(blank('band'))).toBeNull()
  expect(bodyOf({ ...blank('dumbbells'), kg: '24', adjustable: true })).toBeNull() // no bottom
  expect(token(bodyOf({ ...blank('dumbbells'), kg: '12.5' })!)).toBe('dumbbells:12.5')
  expect(token(bodyOf({ ...blank('ab wheel'), note: ' old ' })!)).toBe('ab wheel')
  expect(token(bodyOf(draftOf(RANGE))!)).toBe('dumbbells:2-24')
  expect(bodyOf(draftOf(STOOLS))).toEqual({ kit: 'bench', note: 'two stools' })
})
