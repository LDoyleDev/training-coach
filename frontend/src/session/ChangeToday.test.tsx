import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Changed, Choices, Guided, TodayView, UndoState, Undone } from '../api'
import SessionPage from './SessionPage'

const LEGS: Guided = {
  day: '2026-10-12',
  template_id: 3,
  name: 'Legs',
  focus: 'Quads, hamstrings',
  kind: 'strength',
  warm_up: true,
  block: null,
  minutes: 45,
  rest_seconds: 60,
  after_run: false,
  items: [
    {
      slug: 'jump-squat',
      name: 'Jump squat',
      step: 'Bodyweight',
      summary: null,
      cue: null,
      unit: 'reps',
      per_side: false,
      pair: null,
      targets: [6],
      baseline: false,
      muscles: [],
      parts: [],
    },
  ],
  order: [{ item: 0, set_no: 1, target: 6, rest_seconds: 0, switch: false }],
}
const TORSO: Guided = { ...LEGS, template_id: 5, name: 'Torso + neck' }
const LEGS_TODAY: TodayView = { session: LEGS, progress: null }
const NOTHING_TODAY: TodayView = { session: null }
const REST_UNDO = { event_id: 41, what: 'the rest day for Legs' }

const CHOICES: Choices = {
  template_id: 3,
  next: { template_id: 4, name: 'Recovery + posture' },
  others: [
    { template_id: 4, name: 'Recovery + posture' },
    { template_id: 5, name: 'Torso + neck' },
  ],
}

type Reply = Response | (() => Response)

/** A fake API: replies by "METHOD path", the bodies sent kept the same way. */
function serve(replies: Record<string, Reply>) {
  const sent: Record<string, unknown[]> = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      ;(sent[route] ??= []).push(init?.body ? JSON.parse(String(init.body)) : null)
      const reply = replies[route]
      if (reply === undefined) {
        if (path === '/api/session/today') return Response.json(LEGS_TODAY)
        if (path === '/api/session/pending') return Response.json([])
        if (path === '/api/today/undo') return Response.json(none)
        if (path === '/api/day') return new Response(null, { status: 401 }) // no day card here
        return new Response(null, { status: 404 })
      }
      return typeof reply === 'function' ? reply() : reply.clone()
    }),
  )
  return sent
}

const none: UndoState = { offer: null, refused: 'Nothing to undo.' }
const changed = (body: Partial<Changed>): Response =>
  Response.json({ session: 'Legs', advanced: false, today: NOTHING_TODAY, undo: null, ...body })

afterEach(() => vi.unstubAllGlobals())

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

async function openChangeToday() {
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Change today' }))
}

test('Rest today updates the page in place and offers Undo', async () => {
  const sent = serve({ 'POST /api/today/rest': changed({ undo: REST_UNDO }) })
  await openChangeToday()
  expect(screen.getByRole('button', { name: 'Swap session' })).toBeInTheDocument()
  click('Rest today')
  expect(await screen.findByRole('heading', { name: 'Nothing left today' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(
    'Rest today. Legs moves to tomorrow and the rest of the week shifts a day.',
  )
  expect(sent['POST /api/today/rest']).toEqual([{ template_id: 3 }])
  expect(screen.getByRole('button', { name: 'Undo: the rest day for Legs' })).toBeInTheDocument()
  // The cardio card stays on every Today view.
  expect(screen.getByRole('button', { name: 'Log cardio' })).toBeInTheDocument()
})

test('Rest on the optional rest day says it counts as done', async () => {
  serve({ 'POST /api/today/rest': changed({ session: 'Recovery', advanced: true }) })
  await openChangeToday()
  click('Rest today')
  expect(await screen.findByText('Recovery logged as a rest day. Enjoy it.')).toBeInTheDocument()
})

test('Push to tomorrow, then Undo with a confirm tap brings the session back', async () => {
  const pushUndo = { event_id: 42, what: 'moving Legs to tomorrow' }
  const back: Undone = { what: pushUndo.what, next_session: 'Legs', today: LEGS_TODAY }
  const sent = serve({
    'POST /api/today/push': changed({ undo: pushUndo }),
    'POST /api/today/undo': Response.json(back),
  })
  await openChangeToday()
  click('Push to tomorrow')
  expect(
    await screen.findByText('Legs moves to tomorrow and the rest of the week shifts a day.'),
  ).toBeInTheDocument()

  click('Undo: moving Legs to tomorrow')
  const confirm = screen.getByRole('group', { name: 'Confirm undo' })
  expect(within(confirm).getByText('Undo moving Legs to tomorrow?')).toBeInTheDocument()
  fireEvent.click(within(confirm).getByRole('button', { name: 'Undo it' }))

  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(
    'Undone: moving Legs to tomorrow. Next up: Legs.',
  )
  expect(sent['POST /api/today/undo']).toEqual([{ event_id: 42 }])
  expect(screen.queryByRole('button', { name: /^Undo:/ })).not.toBeInTheDocument()
})

test('Keep it closes the confirm and changes nothing', async () => {
  const sent = serve({
    'GET /api/today/undo': Response.json({ offer: REST_UNDO, refused: null }),
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Undo: the rest day for Legs' }))
  click('Keep it')
  expect(screen.queryByRole('group', { name: 'Confirm undo' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Undo: the rest day for Legs' })).toBeInTheDocument()
  expect(sent['POST /api/today/undo']).toBeUndefined()
})

test('an undo refused with 409 says why and offers nothing more', async () => {
  serve({
    'GET /api/today/undo': Response.json({ offer: REST_UNDO, refused: null }),
    'POST /api/today/undo': Response.json(
      { detail: 'Something changed since then, so it can’t be undone safely.' },
      { status: 409 },
    ),
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Undo: the rest day for Legs' }))
  click('Undo it')
  expect(await screen.findByText(/Something changed since then/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Undo:/ })).not.toBeInTheDocument()
})

test('Swap lists the next session first and any other; picking one shows it', async () => {
  const sent = serve({
    'GET /api/today/choices': Response.json(CHOICES),
    'POST /api/today/pick': changed({
      session: 'Torso + neck',
      today: { session: TORSO, progress: null },
    }),
  })
  await openChangeToday()
  click('Swap session')
  expect(
    await screen.findByRole('button', { name: 'Do Recovery + posture first, Legs tomorrow' }),
  ).toBeInTheDocument()
  click('Torso + neck')
  expect(await screen.findByRole('heading', { name: 'Torso + neck' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(
    "Torso + neck today. The plan's next session stays next.",
  )
  expect(sent['POST /api/today/pick']).toEqual([{ template_id: 3, picked_id: 5 }])
})

test('after a pick, Rest and Push wait: the page offers going back to the planned one', async () => {
  const sent = serve({
    'GET /api/session/today': Response.json({
      session: TORSO,
      progress: null,
      planned: { template_id: 3, name: 'Legs' },
    }),
    'POST /api/today/pick': changed({ session: 'Legs', today: LEGS_TODAY }),
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Change today' }))
  expect(
    screen.getByText('You picked Torso + neck for today. Legs is still next in the plan.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Rest today' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Push to tomorrow' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Swap session' })).toBeInTheDocument()
  click('Back to Legs')
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Back to Legs for today.')
  expect(sent['POST /api/today/pick']).toEqual([{ template_id: 5, picked_id: 3 }])
  // Back on the planned session, Rest and Push are offered again.
  fireEvent.click(screen.getByRole('button', { name: 'Change today' }))
  expect(screen.getByRole('button', { name: 'Rest today' })).toBeInTheDocument()
})

test('Close folds the after-a-pick actions away', async () => {
  serve({
    'GET /api/session/today': Response.json({
      session: TORSO,
      progress: null,
      planned: { template_id: 3, name: 'Legs' },
    }),
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Change today' }))
  click('Close')
  expect(screen.getByRole('button', { name: 'Change today' })).toBeInTheDocument()
})

test('doing the next one first swaps the queue', async () => {
  const sent = serve({
    'GET /api/today/choices': Response.json({ ...CHOICES, next: CHOICES.next }),
    'POST /api/today/next': changed({
      session: 'Recovery + posture',
      today: { session: { ...LEGS, template_id: 4, name: 'Recovery + posture' } },
      undo: { event_id: 43, what: 'doing Recovery + posture before Legs' },
    }),
  })
  await openChangeToday()
  click('Swap session')
  fireEvent.click(await screen.findByRole('button', { name: /first, Legs tomorrow/ }))
  expect(
    await screen.findByText('Recovery + posture today. Legs moves to tomorrow.'),
  ).toBeInTheDocument()
  expect(sent['POST /api/today/next']).toEqual([{ template_id: 3 }])
  expect(
    screen.getByRole('button', { name: 'Undo: doing Recovery + posture before Legs' }),
  ).toBeInTheDocument()
})

test('Back leaves the swap list and Close folds the actions away', async () => {
  serve({ 'GET /api/today/choices': Response.json({ ...CHOICES, next: null }) })
  await openChangeToday()
  click('Swap session')
  fireEvent.click(await screen.findByRole('button', { name: 'Back' }))
  expect(screen.getByRole('button', { name: 'Rest today' })).toBeInTheDocument()
  click('Close')
  expect(screen.getByRole('button', { name: 'Change today' })).toBeInTheDocument()
})

test('a change from an out-of-date page (409) reloads today and says so', async () => {
  let today: TodayView = LEGS_TODAY
  serve({
    'GET /api/session/today': () => Response.json(today),
    'POST /api/today/push': () => {
      today = NOTHING_TODAY // pushed in Telegram meanwhile
      return new Response(null, { status: 409 })
    },
  })
  await openChangeToday()
  click('Push to tomorrow')
  expect(await screen.findByRole('heading', { name: 'Nothing left today' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent("Today's session changed")
})

test('Swap with nothing planned any more (409) reloads too', async () => {
  serve({ 'GET /api/today/choices': new Response(null, { status: 409 }) })
  await openChangeToday()
  click('Swap session')
  expect(await screen.findByText(/Today's session changed/)).toBeInTheDocument()
})

test('a signed-out or failed change says so and keeps the page', async () => {
  serve({
    'POST /api/today/rest': new Response(null, { status: 401 }),
    'POST /api/today/push': new Response(null, { status: 500 }),
    'GET /api/today/choices': new Response(null, { status: 500 }),
  })
  await openChangeToday()
  click('Rest today')
  expect(await screen.findByText(/sign-in has ended/i)).toBeInTheDocument()
  click('Push to tomorrow')
  expect(await screen.findByText(/Couldn't change today/)).toBeInTheDocument()
  click('Swap session')
  expect(await screen.findByText(/Couldn't load the sessions/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Legs' })).toBeInTheDocument()
})

test('a signed-out swap list says so', async () => {
  serve({ 'GET /api/today/choices': new Response(null, { status: 401 }) })
  await openChangeToday()
  click('Swap session')
  await waitFor(() => expect(screen.getByText(/sign-in has ended/i)).toBeInTheDocument())
})

test('a saved session offers Undo, which brings it back unsaved', async () => {
  const logUndo = { event_id: 44, what: 'the Legs log for Mon 12 Oct (1 sets)' }
  let saved = false
  const back: Undone = { what: logUndo.what, next_session: 'Legs', today: LEGS_TODAY }
  serve({
    'PUT /api/session/progress': Response.json({ revision: 1 }),
    'POST /api/session/save': () => {
      saved = true
      return Response.json({
        workout_id: 9,
        already_saved: false,
        next_session: 'Recovery + posture',
        earned: [],
        stretching: false,
      })
    },
    'GET /api/today/undo': () => Response.json(saved ? { offer: logUndo, refused: null } : none),
    'POST /api/today/undo': Response.json(back),
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start session' }))
  click('Confirm set')
  fireEvent.click(await screen.findByRole('button', { name: 'Save session' }))
  expect(await screen.findByRole('heading', { name: 'Legs done' })).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button', { name: `Undo: ${logUndo.what}` }))
  click('Undo it')
  expect(await screen.findByRole('heading', { name: 'Legs' })).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(`Undone: ${logUndo.what}.`)
})

test('a cardio day keeps Change today, and its saved screen holds the only Undo', async () => {
  const zone2: Guided = {
    ...LEGS,
    template_id: 8,
    name: 'Long zone 2',
    kind: 'conditioning',
    items: [{ ...LEGS.items[0], slug: 'zone2', name: 'Zone 2', unit: 'minutes', targets: [45] }],
  }
  const week = { zone2: 0, moderate: 0, zone2_target: null }
  let saved = false
  serve({
    'GET /api/session/today': Response.json({ session: zone2, progress: null }),
    'GET /api/cardio': Response.json({
      planned: { kind: 'zone2', session: 'Long zone 2', target: 45 },
      activities: ['walk'],
      week,
    }),
    'POST /api/cardio': () => {
      saved = true
      return Response.json({
        workout_id: 4,
        already_saved: false,
        planned: true,
        next_session: 'Legs',
        week,
      })
    },
    'GET /api/today/undo': () =>
      Response.json(saved ? { offer: { event_id: 9, what: 'the log' }, refused: null } : none),
  })
  render(<SessionPage />)
  expect(await screen.findByRole('button', { name: 'Change today' })).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button', { name: 'Done as planned: 45 min' }))
  expect(await screen.findByRole('heading', { name: 'Long zone 2 done' })).toBeInTheDocument()
  expect(await screen.findAllByRole('button', { name: 'Undo: the log' })).toHaveLength(1)
  expect(screen.queryByRole('button', { name: 'Change today' })).not.toBeInTheDocument()
  click('Log more')
  expect(await screen.findByRole('button', { name: 'Change today' })).toBeInTheDocument()
})

test('an undo that fails or finds the sign-in ended says so', async () => {
  let reply = new Response(null, { status: 500 })
  serve({
    'GET /api/today/undo': () => Response.json({ offer: REST_UNDO, refused: null }),
    'POST /api/today/undo': () => reply,
  })
  render(<SessionPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Undo: the rest day for Legs' }))
  click('Undo it')
  expect(await screen.findByText(/Couldn't undo/)).toBeInTheDocument()
  reply = new Response(null, { status: 401 })
  click('Undo it')
  expect(await screen.findByText(/sign-in has ended/i)).toBeInTheDocument()
})
