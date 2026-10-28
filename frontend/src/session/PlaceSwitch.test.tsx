import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Guided, TodayView } from '../api'
import PlaceSwitch from './PlaceSwitch'

const SESSION = {
  template_id: 1,
  name: 'Torso + neck',
  place: 'home',
  place_choice: true,
} as Guided
const AT_GYM: TodayView = { session: { ...SESSION, place: 'gym' }, progress: null }

/** A fake PUT /api/session/place: each call takes the next answer; returns the bodies sent. */
function serve(...answers: Response[]) {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      sent.push(JSON.parse(String(init?.body)))
      return answers.shift() ?? new Response(null, { status: 500 })
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

function show(session: Guided = SESSION) {
  const onChanged = vi.fn()
  const onStale = vi.fn()
  render(<PlaceSwitch session={session} onChanged={onChanged} onStale={onStale} />)
  return { onChanged, onStale }
}

const button = (name: string | RegExp) => screen.getByRole('button', { name })

test('starts at the place shown, marked in words as well as colour', () => {
  serve()
  show()
  expect(screen.getByRole('group', { name: 'Where are you training today?' })).toBeInTheDocument()
  expect(button('Home')).toHaveAttribute('aria-pressed', 'true')
  expect(button('Home')).toHaveTextContent('✓ Home')
  expect(button('Gym')).toHaveAttribute('aria-pressed', 'false')
  fireEvent.click(button('Home')) // already there: nothing is sent
  expect(fetch).not.toHaveBeenCalled()
})

test('a tap switches before anything is kept', async () => {
  const sent = serve(Response.json(AT_GYM))
  const { onChanged } = show()
  fireEvent.click(button('Gym'))
  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled())
  expect(sent).toEqual([{ place: 'gym', confirm: false }])
  expect(onChanged).toHaveBeenCalledWith(AT_GYM, 'Torso + neck at the gym: its gym version.')
})

test('with sets kept it asks first, and Keep my sets changes nothing', async () => {
  const sent = serve(
    Response.json({ kept_sets: 3 }, { status: 409 }),
    Response.json({ kept_sets: 3 }, { status: 409 }),
    Response.json(AT_GYM),
  )
  const { onChanged } = show()
  fireEvent.click(button('Gym'))
  expect(
    await screen.findByText(
      "You've kept 3 sets of the home version. Switch to the gym version? They are dropped; nothing saved changes.",
    ),
  ).toBeInTheDocument()
  fireEvent.click(button('Keep my sets'))
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  fireEvent.click(button('Gym'))
  fireEvent.click(await screen.findByRole('button', { name: 'Switch to gym' }))
  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled())
  expect(sent).toEqual([
    { place: 'gym', confirm: false },
    { place: 'gym', confirm: false },
    { place: 'gym', confirm: true },
  ])
})

test('one kept set is said as one', async () => {
  serve(Response.json({ kept_sets: 1 }, { status: 409 }))
  show({ ...SESSION, place: 'gym' })
  fireEvent.click(button('Home'))
  expect(
    await screen.findByText(
      "You've kept 1 set of the gym version. Switch to the home version? It is dropped; nothing saved changes.",
    ),
  ).toBeInTheDocument()
  expect(
    screen.getByText('The gym version, with weights that carry over from last time.'),
  ).toBeInTheDocument()
})

test('a day with no choice any more reloads; a failure and a lost sign-in say so', async () => {
  serve(
    Response.json({ detail: "today's session has one place" }, { status: 409 }),
    new Response(null, { status: 500 }),
    new Response(null, { status: 401 }),
  )
  const { onStale, onChanged } = show()
  fireEvent.click(button('Gym'))
  await vi.waitFor(() => expect(onStale).toHaveBeenCalled())
  fireEvent.click(button('Gym'))
  expect(
    await screen.findByText("That didn't work. Check your connection and try again."),
  ).toBeInTheDocument()
  fireEvent.click(button('Gym'))
  expect(await screen.findByText(/Your sign-in has ended/)).toBeInTheDocument()
  expect(onChanged).not.toHaveBeenCalled()
})
