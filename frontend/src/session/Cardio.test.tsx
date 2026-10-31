import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CardioLogged, CardioOptions } from '../api'
import type { HiitTimerProps } from '../hiit/HiitTimer'
import { playSessionEnd, unlockAudio } from '../hiit/sounds'
import { emptyWeek } from '../test/cardioWeek'
import Cardio from './Cardio'

vi.mock('../hiit/sounds', () => ({
  DEFAULT_SOUND: 'ring',
  unlockAudio: vi.fn(),
  playSessionEnd: vi.fn(),
}))

// The timer has its own tests; here it finishes (ringing the end), stops early or cancels.
vi.mock('../hiit/HiitTimer', () => ({
  default: ({ defaults, onFinish, onCancel, sound }: HiitTimerProps) => (
    <div>
      <p>Timer for {defaults?.rounds ?? 8} rounds</p>
      <p>Timer sound {sound}</p>
      <button
        type="button"
        onClick={() =>
          onFinish?.({ rounds: 6, work: 20, rest: 10, sets: 1, seconds: 230, early: false })
        }
      >
        Finish timer
      </button>
      <button
        type="button"
        onClick={() =>
          onFinish?.({ rounds: 3, work: 20, rest: 10, sets: 1, seconds: 90, early: true })
        }
      >
        Stop timer
      </button>
      <button type="button" onClick={() => onCancel?.()}>
        Cancel timer
      </button>
    </div>
  ),
}))

// Liam's week of 20-26 Oct (ADR-0079): Monday's 66-minute walk by heart rate, Thursday's typed
// 43-minute run with none.
const WEEK = emptyWeek({
  zone2: 35,
  moderate: 43,
  zone2_target: [45, 75],
  zone2_left: 10,
  total: 109,
  total_target: [75, 115],
  total_left: 0,
  zones: { below_zone1: 20, zone1: 7, zone2: 35, zone3: 4, zone3_up_no_hr: 43 },
})

const ZONE2_DAY: CardioOptions = {
  planned: { kind: 'zone2', session: 'Long zone 2', target: 45 },
  activities: ['walk', 'hike', 'bike'],
  week: WEEK,
}

const LOGGED: CardioLogged = {
  workout_id: 4,
  already_saved: false,
  planned: true,
  next_session: 'Legs',
  week: { ...WEEK, zone2: 80, zone2_left: 0, total: 154, zones: { ...WEEK.zones, zone2: 80 } },
}

type Server = {
  options?: CardioOptions | 'error'
  log?: CardioLogged | 'stale' | 'signed-out' | 'error'
}

function serve(server: Server = {}) {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        const log = server.log ?? LOGGED
        if (log === 'stale') return new Response(null, { status: 409 })
        if (log === 'signed-out') return new Response(null, { status: 401 })
        if (log === 'error') return new Response(null, { status: 500 })
        return Response.json(log)
      }
      const options = server.options ?? ZONE2_DAY
      return options === 'error' ? new Response(null, { status: 500 }) : Response.json(options)
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('a planned zone 2 day is done in one tap', async () => {
  const sent = serve()
  render(<Cardio featured />)
  expect(await screen.findByRole('heading', { name: 'Long zone 2' })).toBeInTheDocument()
  expect(screen.getByText(/^Cardio:/)).toHaveTextContent('Cardio: 109 of 75–115 min · on target')
  expect(screen.getByText(/^Zone 2:/)).toHaveTextContent('Zone 2: 35 of 45–75 min · 10 min left')
  expect(screen.getByRole('meter', { name: 'Zone 2 in the last 7 days' })).toBeInTheDocument()
  const zones = screen.getByRole('list', { name: 'Cardio minutes by heart-rate zone' })
  expect(
    within(zones)
      .getAllByRole('listitem')
      .map((row) => row.textContent),
  ).toEqual([
    'Easy (below zone 1)20 min',
    'Zone 17 min',
    'Zone 235 min',
    'Zone 34 min',
    'Zone 3+ (no heart rate) · logged as moderate43 min',
  ])
  click('Done as planned: 45 min')
  expect(await screen.findByRole('heading', { name: 'Long zone 2 done' })).toBeInTheDocument()
  expect(sent).toEqual([
    { token: expect.stringMatching(/^[0-9a-f]{32}$/), kind: 'zone2', value: 45, activity: null },
  ])
  expect(screen.getByText('Next up: Legs.')).toBeInTheDocument()
  expect(screen.getByText(/^Zone 2:/)).toHaveTextContent('Zone 2: 80 of 45–75 min · on target')
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
  expect(unlockAudio).toHaveBeenCalled() // inside the tap
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('ring') // the end of the session
})

test('with the talk test on, effort shows as the talk test; what is logged stays the same', async () => {
  const sent = serve({ log: { ...LOGGED, planned: false } })
  render(<Cardio featured talkTest />)
  expect(
    await screen.findByText('Talk test: Moderate: you can talk in full sentences.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Cardio minutes by heart-rate zone' })).toBeVisible()
  click(/different minutes/)
  expect(screen.queryByRole('button', { name: 'Easy (zone 2)' })).not.toBeInTheDocument()
  expect(screen.getByText('Easy: you can sing.')).toBeInTheDocument()
  expect(screen.getByText('Hard: you can say only a few words.')).toBeInTheDocument()
  click('A few words')
  click('Effort 7')
  click('Save 45 min')
  await screen.findByRole('heading', { name: 'Logged' })
  expect(sent).toEqual([expect.objectContaining({ kind: 'moderate-cardio', value: 45 })])
})

test('with the talk test off, effort shows as heart-rate zones', async () => {
  serve()
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  expect(screen.getByRole('button', { name: 'Easy (zone 2)' })).toBeInTheDocument()
  expect(screen.queryByText(/Talk test|you can sing/)).not.toBeInTheDocument()
})

test("the end of the session rings in the person's timer sound, and not for a repeat", async () => {
  serve({ log: { ...LOGGED, already_saved: true } })
  render(<Cardio featured sound="wood" />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  expect(await screen.findByText(/already saved/)).toBeInTheDocument()
  expect(playSessionEnd).not.toHaveBeenCalled() // saved before: it rang then
})

test('a failed save rings nothing', async () => {
  serve({ log: 'error' })
  render(<Cardio featured sound="wood" />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  expect(await screen.findByText(/Couldn't save/)).toBeInTheDocument()
  expect(playSessionEnd).not.toHaveBeenCalled()
})

test('the exact minutes, the effort and what it was', async () => {
  const sent = serve({ log: { ...LOGGED, planned: false } })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  const minutes = screen.getByLabelText('Minutes')
  expect(minutes).toHaveValue(45)
  fireEvent.change(minutes, { target: { value: '62' } })
  click('1 more')
  click('5 fewer')
  click('Harder (moderate)')
  click('Hike')
  expect(screen.getByRole('button', { name: 'Hike' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Pick how it felt to save' })).toBeDisabled()
  click('Effort 6')
  click('Save 58 min')
  expect(await screen.findByRole('heading', { name: 'Logged' })).toBeInTheDocument()
  expect(screen.getByText('58 min hike, moderate.')).toBeInTheDocument()
  expect(sent).toEqual([
    expect.objectContaining({ kind: 'moderate-cardio', value: 58, activity: 'hike', effort: 6 }),
  ])
  expect(screen.queryByText(/Next up/)).not.toBeInTheDocument()
})

test('minutes stay between 1 and 600', async () => {
  serve()
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  const minutes = screen.getByLabelText('Minutes')
  fireEvent.change(minutes, { target: { value: '9000' } })
  expect(minutes).toHaveValue(600)
  fireEvent.change(minutes, { target: { value: '' } })
  expect(minutes).toHaveValue(1)
  click('5 fewer')
  expect(minutes).toHaveValue(1)
})

test('under any other session it is a card with both choices', async () => {
  const sent = serve({ options: { ...ZONE2_DAY, planned: null } })
  render(<Cardio featured={false} />)
  expect(screen.getByRole('heading', { name: 'Cardio or HIIT' })).toBeInTheDocument()
  click('Log cardio')
  expect(screen.getByLabelText('Minutes')).toHaveValue(30)
  click('Cancel')
  click('Run a HIIT session')
  expect(screen.getByText('Timer for 8 rounds')).toBeInTheDocument()
  click('Cancel timer')
  expect(screen.getByRole('heading', { name: 'Cardio or HIIT' })).toBeInTheDocument()
  expect(sent).toEqual([])
})

test('a planned HIIT day: the timer, then save the rounds', async () => {
  const sent = serve({
    options: { ...ZONE2_DAY, planned: { kind: 'hiit', session: 'High intensity', target: 10 } },
  })
  render(<Cardio featured />)
  expect(await screen.findByText('Target 10 rounds')).toBeInTheDocument()
  click('Start HIIT timer')
  expect(screen.getByText('Timer for 10 rounds')).toBeInTheDocument()
  click('Finish timer')
  click('1 more')
  click('Save 7 rounds')
  expect(await screen.findByText('7 HIIT rounds.')).toBeInTheDocument()
  expect(sent).toEqual([expect.objectContaining({ kind: 'hiit', value: 7, activity: null })])
  expect(playSessionEnd).not.toHaveBeenCalled() // the timer rang the end; the save doesn't again
})

test('HIIT stopped early rings the end of the session when its rounds are saved', async () => {
  serve({
    options: { ...ZONE2_DAY, planned: { kind: 'hiit', session: 'High intensity', target: 10 } },
  })
  render(<Cardio featured sound="chime" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start HIIT timer' }))
  expect(screen.getByText('Timer sound chime')).toBeInTheDocument()
  click('Stop timer')
  click('Save 3 rounds')
  expect(await screen.findByText('3 HIIT rounds.')).toBeInTheDocument()
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('chime')
})

test('rounds can be logged without the timer, or not saved', async () => {
  const sent = serve({
    options: { ...ZONE2_DAY, planned: { kind: 'hiit', session: 'High intensity', target: 10 } },
  })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: 'Log rounds without the timer' }))
  expect(screen.getByLabelText('Rounds')).toHaveValue(10)
  click("Don't save")
  click('Log other cardio')
  expect(screen.getByLabelText('Minutes')).toHaveValue(30)
  expect(sent).toEqual([])
})

test('a changed day, a dropped sign-in and a failed save each say so', async () => {
  serve({ log: 'stale' })
  const { unmount } = render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  expect(await screen.findByText(/Today's session changed/)).toBeInTheDocument()
  unmount()

  serve({ log: 'signed-out' })
  const second = render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  expect(await screen.findByRole('link', { name: /sign in/i })).toBeInTheDocument()
  second.unmount()

  serve({ log: 'error' })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  expect(await screen.findByText(/Couldn't save/)).toBeInTheDocument()
})

test("without today's plan the card still works", async () => {
  serve({ options: 'error' })
  render(<Cardio featured />)
  expect(await screen.findByRole('heading', { name: 'Cardio or HIIT' })).toBeInTheDocument()
  click('Log cardio')
  expect(screen.getByRole('button', { name: 'Walk' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Stairs' })).toBeInTheDocument()
})

test('a retry after a failed save sends the same token, so it saves once', async () => {
  const sent = serve({ log: 'error' })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  await screen.findByText(/Couldn't save/)
  click(/Done as planned/)
  await waitFor(() => expect(sent).toHaveLength(2))
  const [first, again] = sent as { token: string }[]
  expect(again.token).toBe(first.token)
})

test('a new log starts afresh: no activity or token carried over', async () => {
  const sent = serve()
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  click('Hike')
  click('Effort 3')
  click('Save 45 min')
  fireEvent.click(await screen.findByRole('button', { name: 'Log more' }))
  click(/Done as planned/)
  await waitFor(() => expect(sent).toHaveLength(2))
  const [hike, planned] = sent as { token: string; activity: string | null }[]
  expect(hike.activity).toBe('hike')
  expect(planned.activity).toBeNull()
  expect(planned.token).not.toBe(hike.token)
})

test('a different log after a failed save gets a new token', async () => {
  const sent = serve({ log: 'error' })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /Done as planned/ }))
  await screen.findByText(/Couldn't save/)
  click(/different minutes/)
  click('5 more')
  click('Effort 5')
  click('Save 50 min')
  await waitFor(() => expect(sent).toHaveLength(2))
  const [planned, changed] = sent as { token: string; value: number }[]
  expect(changed.value).toBe(50)
  expect(changed.token).not.toBe(planned.token)
})

test('the saved screen offers Undo, and undoing goes back to the menu', async () => {
  const offer = { event_id: 7, what: 'the Long zone 2 log for Mon 12 Oct (1 sets)' }
  const sent: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      sent.push(`${init?.method ?? 'GET'} ${path}`)
      if (path === '/api/today/undo' && init?.method === 'POST')
        return Response.json({ what: offer.what, next_session: 'Long zone 2', today: {} })
      if (path === '/api/today/undo') return Response.json({ offer, refused: null })
      if (init?.method === 'POST') return Response.json(LOGGED)
      return Response.json(ZONE2_DAY)
    }),
  )
  const onChange = vi.fn()
  render(<Cardio featured onChange={onChange} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Done as planned: 45 min' }))
  expect(await screen.findByRole('heading', { name: 'Long zone 2 done' })).toBeInTheDocument()
  expect(onChange).toHaveBeenLastCalledWith('saved')
  fireEvent.click(await screen.findByRole('button', { name: `Undo: ${offer.what}` }))
  click('Undo it')
  expect(await screen.findByText(`Undone: ${offer.what}.`)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Done as planned: 45 min' })).toBeInTheDocument()
  expect(onChange).toHaveBeenLastCalledWith('undone')
  await waitFor(() => expect(sent.filter((s) => s === 'GET /api/cardio')).toHaveLength(2))
})

test('Log more closes the saved screen for the page', async () => {
  serve()
  const onChange = vi.fn()
  render(<Cardio featured onChange={onChange} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Done as planned: 45 min' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Log more' }))
  expect(onChange).toHaveBeenLastCalledWith('closed')
})

test('a ride shows its speed, not its pace', async () => {
  serve({ log: { ...LOGGED, planned: false, pace: 148 } })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  fireEvent.change(screen.getByLabelText('Minutes'), { target: { value: '90' } })
  click('Bike')
  click('Effort 5')
  fireEvent.change(screen.getByLabelText('Distance (km)'), { target: { value: '36.4' } })
  expect(screen.getByText('Speed 24.3 km/h')).toBeInTheDocument()
  click('Save 90 min')
  expect(await screen.findByText('effort 5/10 · 36.4 km · 24.3 km/h')).toBeInTheDocument()
})

test('details from a watch: distance gives the pace, and they are sent and shown', async () => {
  const sent = serve({ log: { ...LOGGED, planned: false, pace: 354 } })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  fireEvent.change(screen.getByLabelText('Minutes'), { target: { value: '43' } })
  click('Hike')
  click('Effort 6')
  fireEvent.change(screen.getByLabelText('Distance (km)'), { target: { value: '7,29' } })
  expect(screen.getByText('Pace 5:54 /km')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Average heart rate'), { target: { value: '139' } })
  fireEvent.change(screen.getByLabelText('Highest heart rate'), { target: { value: '160' } })
  fireEvent.change(screen.getByLabelText('Started at'), { target: { value: '16:26' } })
  click('Save 43 min')
  expect(
    await screen.findByText('effort 6/10 · 7.29 km · 5:54 /km · HR 139 avg, 160 max'),
  ).toBeInTheDocument()
  expect(sent).toEqual([
    expect.objectContaining({
      value: 43,
      activity: 'hike',
      effort: 6,
      distance_km: 7.29,
      avg_hr: 139,
      max_hr: 160,
      start: '16:26',
    }),
  ])
})

test('empty details are sent as not given', async () => {
  const sent = serve({ log: { ...LOGGED, planned: false } })
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  click('Effort 4')
  click('Save 45 min')
  await screen.findByRole('heading', { name: 'Logged' })
  expect(sent).toEqual([
    expect.objectContaining({
      effort: 4,
      distance_km: null,
      avg_hr: null,
      max_hr: null,
      start: null,
    }),
  ])
})

test('a log the server refuses says why', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? Response.json(
            { detail: "highest heart rate can't be below the average" },
            { status: 422 },
          )
        : Response.json(ZONE2_DAY),
    ),
  )
  render(<Cardio featured />)
  fireEvent.click(await screen.findByRole('button', { name: /different minutes/ }))
  click('Effort 7')
  click('Save 45 min')
  expect(
    await screen.findByText("Not saved: highest heart rate can't be below the average."),
  ).toBeInTheDocument()
})
