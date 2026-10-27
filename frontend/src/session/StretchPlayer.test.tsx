import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Routine } from '../api'
import { playChange, playSessionEnd, unlockAudio } from '../hiit/sounds'
import { duration } from './flow'
import StretchPlayer from './StretchPlayer'

vi.mock('../hiit/sounds', () => ({
  DEFAULT_SOUND: 'ring',
  unlockAudio: vi.fn(),
  playChange: vi.fn(),
  playSessionEnd: vi.fn(),
}))

// Hip flexor, one-sided, 2 rounds: 0-15 into position, 15-45 hold, 45-50 let go, 50-80 hold;
// the other side 80-160. Fold, 1 round: 160-175 into position, 175-205 hold. 3:25 in all.
const ROUTINE: Routine = {
  session: 'Legs',
  minutes: 5,
  hold_seconds: 30,
  position_seconds: 15,
  release_seconds: 5,
  steps: [
    {
      slug: 'half-kneeling-hip-flexor',
      name: 'Hip flexor stretch',
      rounds: 2,
      per_side: true,
      cue: 'Squeeze the back glute.',
    },
    { slug: 'fold', name: 'Forward fold', rounds: 1, per_side: false, cue: 'Soft knees.' },
  ],
}

const played = (change: string) =>
  vi.mocked(playChange).mock.calls.filter(([, c]) => c === change).length
const vibrate = vi.fn()

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Response.json({ sound: 'bell' })),
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

function show() {
  const onLog = vi.fn()
  const onDiscard = vi.fn()
  render(<StretchPlayer routine={ROUTINE} busy={false} onLog={onLog} onDiscard={onDiscard} />)
  return { onLog, onDiscard }
}

async function start() {
  const handlers = show()
  await act(async () => {}) // the person's sound from Settings
  click('Start stretching')
  return handlers
}

test('the overview lists what is coming and the true total before anything starts', () => {
  show()
  expect(screen.getByText(/2 stretches, 3 min 25 s in all, the gaps included/)).toBeInTheDocument()
  expect(screen.getByText(/15 s to get into position/)).toBeInTheDocument()
  expect(screen.getByText('· 2 × 30 s each side')).toBeInTheDocument()
  expect(screen.getByText('· 1 × 30 s')).toBeInTheDocument()
  expect(screen.getByText('Soft knees.')).toBeInTheDocument()
  expect(screen.queryByRole('timer')).not.toBeInTheDocument()
})

test('Done stretching skips the player and logs the chosen minutes, ringing the end', () => {
  const { onLog } = show()
  click('Done stretching')
  expect(onLog).toHaveBeenCalledWith(5)
  expect(unlockAudio).toHaveBeenCalled() // inside the tap
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('ring') // before Settings answers
})

test('Start gives 15 s to get into position, with the cue and figure, and no bell', async () => {
  const wake = vi.fn(async () => ({ release: vi.fn(async () => {}) }))
  Object.defineProperty(navigator, 'wakeLock', { value: { request: wake }, configurable: true })
  await start()
  expect(unlockAudio).toHaveBeenCalled()
  expect(wake).toHaveBeenCalledWith('screen')
  expect(playChange).not.toHaveBeenCalled()
  expect(screen.getByRole('heading', { name: 'Hip flexor stretch' })).toBeInTheDocument()
  expect(screen.getByText('Get into position, first side')).toBeInTheDocument()
  expect(screen.getByText('Squeeze the back glute.')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /^Hip flexor stretch/ })).toBeInTheDocument()
  expect(screen.getByText('Then hold 30 s')).toBeInTheDocument()
  expect(timer()).toBe('0:15')
  expect(screen.getByText('1 of 2')).toBeInTheDocument()
})

test('the hold counts down after a bell, then a bell to let go and again to hold', async () => {
  await start()
  advance(15_200)
  expect(playChange).toHaveBeenLastCalledWith('bell', 'next')
  expect(vibrate).toHaveBeenLastCalledWith(400)
  expect(screen.getByText('Hold, first side')).toBeInTheDocument()
  expect(screen.getByText('Round 1 of 2')).toBeInTheDocument()
  expect(timer()).toBe('0:30')
  expect(screen.queryByRole('img')).not.toBeInTheDocument() // the figure is for getting in
  advance(30_000)
  expect(playChange).toHaveBeenLastCalledWith('bell', 'count')
  expect(screen.getByText('Let go, first side')).toBeInTheDocument()
  expect(timer()).toBe('0:05')
  advance(5_000)
  expect(screen.getByText('Round 2 of 2')).toBeInTheDocument()
  expect(played('next')).toBe(2)
})

test('the other side and the next stretch each ring, with "Next" over the last 5 s', async () => {
  await start()
  advance(80_200)
  expect(playChange).toHaveBeenLastCalledWith('bell', 'switch')
  expect(screen.getByText('Get into position, second side')).toBeInTheDocument()
  advance(75_000) // 155.2 s
  expect(screen.getByText('Next: Forward fold')).toBeInTheDocument()
  advance(5_000)
  expect(playChange).toHaveBeenLastCalledWith('bell', 'next')
  expect(screen.getByRole('heading', { name: 'Forward fold' })).toBeInTheDocument()
  expect(screen.getByText('Get into position')).toBeInTheDocument()
  expect(screen.getByText('2 of 2')).toBeInTheDocument()
})

test('pause stops the clock and the bells until Resume', async () => {
  await start()
  advance(5_000)
  click('Pause')
  expect(screen.getByText('Paused')).toBeInTheDocument()
  advance(60_000)
  expect(timer()).toBe('0:10')
  expect(playChange).not.toHaveBeenCalled()
  click('Resume')
  advance(10_200)
  expect(playChange).toHaveBeenLastCalledWith('bell', 'next')
})

test('Skip and Previous move a stretch at a time without ringing for what they skip', async () => {
  await start()
  click('Skip')
  expect(screen.getByRole('heading', { name: 'Forward fold' })).toBeInTheDocument()
  advance(400)
  expect(playChange).not.toHaveBeenCalled()
  advance(3_000)
  click('Previous')
  expect(screen.getByRole('heading', { name: 'Forward fold' })).toBeInTheDocument()
  expect(timer()).toBe('0:15')
  click('Previous') // only just started: the one before
  expect(screen.getByRole('heading', { name: 'Hip flexor stretch' })).toBeInTheDocument()
})

test('at the end the session-end bell rings once and the minutes log by themselves', async () => {
  const { onLog } = await start()
  advance(205_400)
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('bell')
  expect(played('finish')).toBe(0) // the end of stretching is the end of the session
  expect(vibrate).toHaveBeenLastCalledWith([300, 100, 300])
  expect(screen.getByText('Stretching done: 3 min.')).toBeInTheDocument()
  expect(onLog).toHaveBeenCalledTimes(1)
  expect(onLog).toHaveBeenCalledWith(3)
  expect(screen.queryByRole('button', { name: "Don't log it" })).not.toBeInTheDocument()
  click('Log 3 min') // still there if the log failed
  expect(onLog).toHaveBeenCalledTimes(2)
  expect(playSessionEnd).toHaveBeenCalledOnce() // not again
})

test('Skip past the last stretch is a stop, not a finish: nothing logs by itself', async () => {
  const { onLog } = await start()
  advance(30_000)
  click('Skip') // to the fold, the last stretch
  click('Skip') // past the end
  expect(screen.getByText(/Stopped early: log the 1 min you did, or nothing/)).toBeInTheDocument()
  expect(onLog).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: "Don't log it" })).toBeInTheDocument()
})

test('stopped early it offers to log the whole minutes done, or nothing', async () => {
  const { onLog, onDiscard } = await start()
  advance(100_000)
  click('Stop early')
  expect(screen.getByText(/Stopped early: log the 2 min you did, or nothing/)).toBeInTheDocument()
  expect(onLog).not.toHaveBeenCalled()
  expect(playSessionEnd).not.toHaveBeenCalled()
  click('Log 2 min')
  expect(onLog).toHaveBeenCalledWith(2)
  expect(playSessionEnd).toHaveBeenCalledExactlyOnceWith('bell') // logged: the end
  click("Don't log it")
  expect(onDiscard).toHaveBeenCalled()
})

test('stopped at once there is nothing to log, and it can start again', async () => {
  await start()
  click('Stop early')
  expect(screen.getByText('Nothing stretched yet.')).toBeInTheDocument()
  click('Start stretching')
  expect(timer()).toBe('0:15')
})

test('a few seconds stretched still log a minute', async () => {
  const { onLog } = await start()
  advance(20_000)
  click('Stop early')
  click('Log 1 min')
  expect(onLog).toHaveBeenCalledWith(1)
})

test('without Settings the default sound plays', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  await start()
  advance(15_200)
  expect(playChange).toHaveBeenLastCalledWith('ring', 'next')
})

test('a duration reads in minutes and seconds', () => {
  expect(duration(595)).toBe('9 min 55 s')
  expect(duration(600)).toBe('10 min')
  expect(duration(45)).toBe('45 s')
})
