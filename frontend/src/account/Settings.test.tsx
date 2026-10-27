import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { MessageSettings } from '../api'
import { playChange } from '../hiit/sounds'
import Settings from './Settings'

vi.mock('../hiit/sounds', () => ({ unlockAudio: vi.fn(), playChange: vi.fn() }))

const PREFS: MessageSettings = {
  morning_time: '07:30',
  nudge_time: '20:00',
  nudges_enabled: true,
  review_time: '19:00',
  habits_enabled: true,
  protein_g: null,
  blocks_since: null,
  pace: 'standard',
  sound: 'ring',
  extra_cardio_min: 0,
  paused: false,
  timezone: 'Europe/Berlin',
}

type Patch = 'ok' | 'invalid' | 'fail' | 'signed-out'

/** A fake API: GET answers ``prefs``; PATCH merges what was sent, or refuses. */
function serve(prefs: MessageSettings | 'error' = PREFS, patch: Patch = 'ok') {
  let current = prefs
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') {
        const change = JSON.parse(String(init.body)) as Record<string, unknown>
        sent.push(change)
        if (patch === 'invalid') return new Response(null, { status: 422 })
        if (patch === 'fail') return new Response(null, { status: 500 })
        if (patch === 'signed-out') return new Response(null, { status: 401 })
        const { blocks, protein_g, ...rest } = change
        current = { ...(current as MessageSettings), ...rest }
        if (blocks !== undefined) current.blocks_since = blocks ? '2026-10-12' : null
        if (protein_g !== undefined) current.protein_g = protein_g === 0 ? null : Number(protein_g)
        return Response.json(current)
      }
      if (current === 'error') return new Response(null, { status: 500 })
      return Response.json(current)
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

const button = (name: string | RegExp) => screen.getByRole('button', { name })

test('shows the current settings', async () => {
  serve({ ...PREFS, protein_g: 165, blocks_since: '2026-09-01', paused: true })
  render(<Settings />)
  expect(await screen.findByLabelText('Morning message')).toHaveValue('07:30')
  expect(screen.getByLabelText('Evening nudge')).toHaveValue('20:00')
  expect(screen.getByLabelText(/Protein target/)).toHaveValue(165)
  expect(screen.getByText(/Paused: no messages/)).toBeInTheDocument()
  expect(button('Resume messages')).toBeInTheDocument()
  expect(screen.getByText(/on since Tue 1 Sept/)).toBeInTheDocument()
  expect(screen.getByText('Times are Europe/Berlin time.')).toBeInTheDocument()
})

test('a new time is saved with its own Save, and says so next to it', async () => {
  const sent = serve()
  render(<Settings />)
  const morning = await screen.findByLabelText('Morning message')
  const save = screen.getAllByRole('button', { name: 'Save' })[0]
  expect(save).toBeDisabled() // nothing changed yet
  fireEvent.change(morning, { target: { value: '06:45' } })
  fireEvent.click(save)
  expect(await screen.findByText('Morning message: 06:45.')).toBeInTheDocument()
  expect(sent).toEqual([{ morning_time: '06:45' }])
  expect(save).toBeDisabled()
})

test('switches send the opposite of what is on', async () => {
  const sent = serve()
  render(<Settings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Turn nudges off' }))
  expect(await screen.findByText('Evening nudge: off')).toBeInTheDocument()
  fireEvent.click(button('Turn habits off'))
  fireEvent.click(await screen.findByRole('button', { name: 'Pause all messages' }))
  expect(await screen.findByText(/Paused: no messages/)).toBeInTheDocument()
  fireEvent.click(button('Train in blocks'))
  expect(await screen.findByText(/on since Mon 12 Oct/)).toBeInTheDocument()
  expect(sent).toEqual([
    { nudges_enabled: false },
    { habits_enabled: false },
    { paused: true },
    { blocks: true },
  ])
})

test('the pace is one of three, with a line saying what each means', async () => {
  const sent = serve()
  render(<Settings />)
  const standard = await screen.findByRole('button', { name: /^Standard/ })
  expect(standard).toHaveAttribute('aria-pressed', 'true')
  expect(standard).toHaveTextContent('About a tenth of the range at a time.')
  fireEvent.click(standard) // already chosen: nothing to save
  const steady = button(/^Steady/)
  expect(steady).toHaveTextContent('One rep at a time.')
  fireEvent.click(steady)
  expect(await screen.findByText('Pace: steady.')).toBeInTheDocument()
  expect(button(/^Steady/)).toHaveAttribute('aria-pressed', 'true')
  expect(button(/^Standard/)).toHaveAttribute('aria-pressed', 'false')
  fireEvent.click(button(/^Fast/))
  expect(await screen.findByText('Pace: fast.')).toBeInTheDocument()
  expect(button(/^Fast/)).toHaveTextContent('At least two reps at a time.')
  expect(sent).toEqual([{ pace: 'steady' }, { pace: 'fast' }])
})

test('the protein target is set and cleared', async () => {
  const sent = serve()
  render(<Settings />)
  fireEvent.change(await screen.findByLabelText(/Protein target/), { target: { value: '165' } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[3])
  expect(await screen.findByText('Protein target: 165 g a day.')).toBeInTheDocument()
  fireEvent.click(button('Clear'))
  expect(await screen.findByText('Protein target cleared.')).toBeInTheDocument()
  expect(sent).toEqual([{ protein_g: 165 }, { protein_g: 0 }])
})

test('a value the server refuses says why', async () => {
  serve(PREFS, 'invalid')
  render(<Settings />)
  fireEvent.change(await screen.findByLabelText(/Protein target/), { target: { value: '20' } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[3])
  expect(await screen.findByText(/between 40 and 400/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Evening nudge'), { target: { value: '21:00' } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[1])
  expect(await screen.findByText("That isn't a time like 07:30.")).toBeInTheDocument()
})

test.each([
  ['fail', /Check your connection/],
  ['signed-out', /Your sign-in ended/],
] as const)('a %s save says so', async (patch, text) => {
  serve(PREFS, patch)
  render(<Settings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Turn nudges off' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
  expect(button('Turn nudges off')).toBeEnabled()
})

test('stays hidden when it cannot load', async () => {
  serve('error')
  const { container } = render(<Settings />)
  await Promise.resolve()
  expect(container).toBeEmptyDOMElement()
})

test('the timer sound is one of six, the boxing bell first, played when tapped, and saved', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const sent = serve()
  render(<Settings />)
  const group = (await screen.findByRole('group', { name: 'Timer sound' })) as HTMLElement
  expect(
    within(group).getByText(/Every guided timer plays it: when a rest ends/),
  ).toBeInTheDocument()
  const names = within(group)
    .getAllByRole('button')
    .map((b) => b.textContent)
  expect(names).toEqual(['Boxing bell', 'Chime', 'Beep', 'Wood block', 'Bell', 'No sound'])
  expect(button('Boxing bell')).toHaveAttribute('aria-pressed', 'true') // the default
  fireEvent.click(button('Boxing bell'))
  expect(playChange).toHaveBeenCalledWith('ring', 'switch') // tapping the chosen one plays it
  vi.advanceTimersByTime(1000)
  expect(playChange).toHaveBeenCalledWith('ring', 'next')
  fireEvent.click(button('Wood block'))
  expect(playChange).toHaveBeenCalledWith('wood', 'switch')
  vi.advanceTimersByTime(1000)
  expect(playChange).toHaveBeenCalledWith('wood', 'next')
  expect(await screen.findByText('Timer sound: wood block.')).toBeInTheDocument()
  expect(button('Wood block')).toHaveAttribute('aria-pressed', 'true')
  vi.mocked(playChange).mockClear()
  fireEvent.click(button('No sound'))
  expect(playChange).not.toHaveBeenCalled()
  await screen.findByText('Timer sound: no sound.')
  expect(sent).toEqual([{ sound: 'wood' }, { sound: 'none' }]) // the default was never re-sent
  vi.useRealTimers()
})
