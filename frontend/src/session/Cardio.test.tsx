import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { CardioLogged, CardioOptions } from '../api'
import type { HiitTimerProps } from '../hiit/HiitTimer'
import Cardio from './Cardio'

// The timer has its own tests; here it finishes or cancels on a click.
vi.mock('../hiit/HiitTimer', () => ({
  default: ({ defaults, onFinish, onCancel }: HiitTimerProps) => (
    <div>
      <p>Timer for {defaults?.rounds ?? 8} rounds</p>
      <button
        type="button"
        onClick={() => onFinish?.({ rounds: 6, work: 20, rest: 10, sets: 1, seconds: 230 })}
      >
        Finish timer
      </button>
      <button type="button" onClick={() => onCancel?.()}>
        Cancel timer
      </button>
    </div>
  ),
}))

const WEEK = { zone2: 40, moderate: 0, zone2_target: [180, 200] }

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
  week: { ...WEEK, zone2: 85 },
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

afterEach(() => vi.unstubAllGlobals())

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

test('a planned zone 2 day is done in one tap', async () => {
  const sent = serve()
  render(<Cardio featured />)
  expect(await screen.findByRole('heading', { name: 'Long zone 2' })).toBeInTheDocument()
  expect(screen.getByText(/This week:/)).toHaveTextContent('This week: 40 of 180–200 zone 2 min')
  click('Done as planned: 45 min')
  expect(await screen.findByRole('heading', { name: 'Long zone 2 done' })).toBeInTheDocument()
  expect(sent).toEqual([
    { token: expect.stringMatching(/^[0-9a-f]{32}$/), kind: 'zone2', value: 45, activity: null },
  ])
  expect(screen.getByText('Next up: Legs.')).toBeInTheDocument()
  expect(screen.getByText(/This week:/)).toHaveTextContent('This week: 85 of 180–200 zone 2 min')
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
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
  click('Save 58 min')
  expect(await screen.findByRole('heading', { name: 'Logged' })).toBeInTheDocument()
  expect(screen.getByText('58 min hike, moderate.')).toBeInTheDocument()
  expect(sent).toEqual([
    expect.objectContaining({ kind: 'moderate-cardio', value: 58, activity: 'hike' }),
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
  click('Save 50 min')
  await waitFor(() => expect(sent).toHaveLength(2))
  const [planned, changed] = sent as { token: string; value: number }[]
  expect(changed.value).toBe(50)
  expect(changed.token).not.toBe(planned.token)
})
