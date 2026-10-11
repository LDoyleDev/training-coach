import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { MessageSettings } from '../api'
import Settings from './Settings'

const PREFS: MessageSettings = {
  morning_time: '07:30',
  nudge_time: '20:00',
  nudges_enabled: true,
  review_time: '19:00',
  habits_enabled: true,
  protein_g: null,
  blocks_since: null,
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
