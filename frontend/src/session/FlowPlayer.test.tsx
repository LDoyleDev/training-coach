import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Flow, FlowMove } from '../api'
import { playChange, unlockAudio } from '../hiit/sounds'
import FlowPlayer from './FlowPlayer'

vi.mock('../hiit/sounds', () => ({
  unlockAudio: vi.fn(),
  playChange: vi.fn(),
}))

const played = (change: string) =>
  vi.mocked(playChange).mock.calls.filter(([, c]) => c === change).length

const move = (slug: string, name: string, seconds: number, per_side = false): FlowMove => ({
  slug,
  name,
  seconds,
  per_side,
  target: `${name} target`,
  start: `${name} start`,
  end: `${name} end`,
  cues: [`${name} cue`],
  breathing: `${name} breathing`,
  easier: `${name} easier`,
  pacing: `${name} pacing`,
})

// Bridge 0-60, lunge 60-150 (switch at 105): two and a half minutes.
const FLOW: Flow = {
  seconds: 150,
  safety: 'If something hurts, stop.',
  moves: [move('glute-bridge', 'Glute bridge', 60), move('lunge', 'Kneeling lunge', 45, true)],
}

const vibrate = vi.fn()

let chosen: string | number = 'chime' // what /api/settings answers: a sound, or a status

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  chosen = 'chime'
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      typeof chosen === 'number'
        ? new Response(null, { status: chosen })
        : Response.json({ sound: chosen }),
    ),
  )
  Object.defineProperty(navigator, 'vibrate', { value: vibrate, configurable: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  Reflect.deleteProperty(navigator, 'vibrate')
  Reflect.deleteProperty(navigator, 'wakeLock')
})

const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms))
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const timer = () => screen.getByRole('timer').textContent

function start() {
  const onDone = vi.fn()
  render(<FlowPlayer flow={FLOW} busy={false} onDone={onDone} />)
  click('Start the flow')
  return onDone
}

test('before it starts it lists the movements, their times and the safety line', () => {
  render(<FlowPlayer flow={FLOW} busy={false} onDone={vi.fn()} />)
  expect(screen.getByText(/2 movements, 3 minutes/)).toBeInTheDocument()
  expect(screen.getByText('· 45 s each side')).toBeInTheDocument()
  expect(screen.getByText('If something hurts, stop.')).toBeInTheDocument()
})

test('one movement at a time: countdown, cues, then the next starts by itself', () => {
  start()
  expect(unlockAudio).toHaveBeenCalled()
  expect(screen.getByRole('heading', { name: 'Glute bridge' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Glute bridge, moving from/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Start and end' })).toBeInTheDocument()
  expect(screen.getByText('1 of 2')).toBeInTheDocument()
  expect(timer()).toBe('1:00')
  expect(screen.getByText('Glute bridge cue')).toBeInTheDocument()
  expect(screen.getByText('Glute bridge start')).toBeInTheDocument()
  expect(screen.getByText('Glute bridge end')).toBeInTheDocument()
  expect(screen.getByText('Glute bridge easier')).toBeInTheDocument() // in the disclosure
  advance(55_200)
  expect(screen.getByRole('status')).toHaveTextContent('Next: Kneeling lunge')
  advance(1_900)
  expect(played('count')).toBe(1) // 3 s left
  advance(3_000)
  expect(played('count')).toBe(3)
  expect(playChange).toHaveBeenLastCalledWith('chime', 'next') // the next movement
  expect(vibrate).toHaveBeenCalledWith(400)
  expect(screen.getByRole('heading', { name: 'Kneeling lunge' })).toBeInTheDocument()
  expect(screen.getByText('First side')).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument() // no figure for this slug
  expect(timer()).toBe('0:45')
})

test('a one-sided movement switches sides halfway with its own sound and buzz', () => {
  start()
  advance(105_200)
  expect(playChange).toHaveBeenLastCalledWith('chime', 'switch')
  expect(vibrate).toHaveBeenCalledWith([200, 100, 200])
  expect(screen.getByText('Second side')).toBeInTheDocument()
  expect(timer()).toBe('0:45')
})

test('at the end it finishes and logs the minutes moved, from when it started', () => {
  const started = Date.now()
  const onDone = start()
  advance(150_400)
  expect(playChange).toHaveBeenLastCalledWith('chime', 'finish')
  expect(screen.getByText('Flow done: 3 min of moving.')).toBeInTheDocument()
  click('Log 3 min')
  expect(onDone).toHaveBeenCalledWith(3, started)
})

test('pause stops the clock; paused time is not counted', () => {
  start()
  advance(10_000)
  click('Pause')
  expect(screen.getByText('Paused')).toBeInTheDocument()
  advance(60_000)
  expect(timer()).toBe('0:50')
  click('Resume')
  advance(1_000)
  expect(timer()).toBe('0:49')
})

test('Skip and Previous move a whole movement; skipped time is not logged', () => {
  const onDone = start()
  advance(10_000)
  click('Skip')
  expect(screen.getByRole('heading', { name: 'Kneeling lunge' })).toBeInTheDocument()
  advance(5_000)
  click('Previous')
  expect(screen.getByRole('heading', { name: 'Kneeling lunge' })).toBeInTheDocument()
  expect(timer()).toBe('0:45')
  advance(1_000)
  click('Previous') // just after a start: the one before
  expect(screen.getByRole('heading', { name: 'Glute bridge' })).toBeInTheDocument()
  click('Skip')
  click('Skip')
  expect(screen.getByText('Flow done: 1 min of moving.')).toBeInTheDocument() // 16 s moved
  click('Log 1 min')
  expect(onDone).toHaveBeenCalledWith(1, expect.any(Number))
})

test('finishing early before moving offers to start again', () => {
  const onDone = start()
  click('Finish early')
  expect(screen.getByText('Nothing moved yet.')).toBeInTheDocument()
  click('Start the flow')
  expect(timer()).toBe('1:00')
  expect(onDone).not.toHaveBeenCalled()
})

test('a long gap (a locked screen) plays only the latest sound', () => {
  start()
  advance(1_000)
  act(() => {
    vi.setSystemTime(Date.now() + 105_000) // the timer was throttled meanwhile
    document.dispatchEvent(new Event('visibilitychange'))
  })
  expect(playChange).toHaveBeenCalledTimes(1) // the counts and the next movement are past
  expect(playChange).toHaveBeenCalledWith('chime', 'switch') // the latest: switch sides
  expect(screen.getByText('Second side')).toBeInTheDocument()
})

test('the screen is kept on while it runs and let go after', async () => {
  const release = vi.fn(async () => {})
  const request = vi.fn(async () => ({ release }))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  expect(request).toHaveBeenCalledWith('screen')
  await act(async () => {})
  click('Finish early')
  await act(async () => {})
  expect(release).toHaveBeenCalled()
})

test('it plays the sound chosen in Settings', async () => {
  chosen = 'wood'
  start()
  await act(async () => {}) // the settings arrive
  advance(60_100)
  expect(playChange).toHaveBeenLastCalledWith('wood', 'next')
})

test('settings it cannot read leave the chime', async () => {
  chosen = 500
  start()
  await act(async () => {})
  advance(60_100)
  expect(playChange).toHaveBeenLastCalledWith('chime', 'next')
})
