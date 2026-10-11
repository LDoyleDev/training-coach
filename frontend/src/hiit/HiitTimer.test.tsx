import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import HiitTimer from './HiitTimer'
import { playBeep, playBell, playFinished, unlockAudio } from './sounds'

vi.mock('./sounds', () => ({
  unlockAudio: vi.fn(),
  playBeep: vi.fn(),
  playBell: vi.fn(),
  playFinished: vi.fn(),
}))

// 2 rounds of 5 s on / 5 s off: ready 0-3, work 3-8, rest 8-13, work 13-18.
const SHORT = { rounds: 2, work: 5, rest: 5 }

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
  Reflect.deleteProperty(navigator, 'wakeLock')
})

const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms))
const clock = () => screen.getByRole('timer').textContent

function start(props: Parameters<typeof HiitTimer>[0] = { defaults: SHORT }) {
  const onFinish = vi.fn()
  const onCancel = vi.fn()
  render(<HiitTimer onFinish={onFinish} onCancel={onCancel} {...props} />)
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  return { onFinish, onCancel }
}

test('setup starts from the defaults and shows the total time', () => {
  render(<HiitTimer />)
  expect(screen.getByLabelText('Rounds')).toHaveValue(8)
  expect(screen.getByLabelText('Work (seconds)')).toHaveValue(20)
  expect(screen.getByLabelText('Rest (seconds)')).toHaveValue(10)
  expect(screen.getByText('3:50')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
})

test('− and + change a setting within its limits, and typing is clamped on blur', () => {
  render(<HiitTimer defaults={{ rounds: 4 }} />)
  expect(screen.getByText('1:50')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'More rounds' }))
  expect(screen.getByLabelText('Rounds')).toHaveValue(5)
  expect(screen.getByText('2:20')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Less rest' }))
  fireEvent.click(screen.getByRole('button', { name: 'Less rest' }))
  expect(screen.getByLabelText('Rest (seconds)')).toHaveValue(0)
  expect(screen.getByRole('button', { name: 'Less rest' })).toBeDisabled()
  const work = screen.getByLabelText('Work (seconds)')
  fireEvent.change(work, { target: { value: '2' } })
  fireEvent.blur(work)
  expect(work).toHaveValue(5)
})

test('blurring an empty field restores the same default that Start would use', () => {
  render(<HiitTimer defaults={{ rounds: 4 }} />)
  const rounds = screen.getByLabelText('Rounds')
  fireEvent.change(rounds, { target: { value: '' } })
  fireEvent.blur(rounds)
  expect(rounds).toHaveValue(4)
  const rest = screen.getByLabelText('Rest (seconds)')
  fireEvent.change(rest, { target: { value: '' } })
  fireEvent.blur(rest)
  expect(rest).toHaveValue(10)
  expect(screen.getByText('1:50')).toBeInTheDocument()
})

test('Cancel in setup leaves with nothing', () => {
  const onCancel = vi.fn()
  render(<HiitTimer onCancel={onCancel} />)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(onCancel).toHaveBeenCalledOnce()
})

test('Start unlocks audio and counts in 3, 2, 1 with beeps, then rings the bell for work', () => {
  start()
  expect(unlockAudio).toHaveBeenCalledOnce()
  expect(screen.getByText('Get ready')).toBeInTheDocument()
  expect(clock()).toBe('3')
  expect(playBeep).toHaveBeenCalledTimes(1)
  advance(1000)
  expect(clock()).toBe('2')
  expect(playBeep).toHaveBeenCalledTimes(2)
  advance(1000)
  expect(playBeep).toHaveBeenCalledTimes(3)
  expect(playBell).not.toHaveBeenCalled()
  advance(1000)
  expect(playBell).toHaveBeenCalledExactlyOnceWith('work')
  expect(screen.getByText('Work')).toBeInTheDocument()
  expect(screen.getByText('Round 1 of 2')).toBeInTheDocument()
  expect(clock()).toBe('5')
  expect(playBeep).toHaveBeenCalledTimes(3)
})

test('beeps come at 3, 2 and 1 before each transition and the rest bell rings on time', () => {
  start()
  advance(4900) // t = 4.9, work has 3.1 s left
  expect(playBeep).toHaveBeenCalledTimes(3)
  advance(100) // 3 s left
  expect(playBeep).toHaveBeenCalledTimes(4)
  advance(2000)
  expect(playBeep).toHaveBeenCalledTimes(6)
  advance(900)
  expect(playBell).toHaveBeenCalledTimes(1)
  advance(100) // t = 8: rest starts
  expect(playBell).toHaveBeenLastCalledWith('rest')
  expect(screen.getByText('Rest')).toBeInTheDocument()
})

test('the full workout ends with the finished sound, a summary and onFinish', () => {
  const { onFinish, onCancel } = start()
  advance(18_000)
  expect(playFinished).toHaveBeenCalledOnce()
  expect(playBell).toHaveBeenCalledTimes(3)
  expect(playBeep).toHaveBeenCalledTimes(12)
  expect(onFinish).toHaveBeenCalledExactlyOnceWith({ rounds: 2, work: 5, rest: 5 })
  expect(onCancel).not.toHaveBeenCalled()
  expect(screen.getByText('2 rounds of 5 s on / 5 s off')).toBeInTheDocument()
})

test('pause stops the clock and resume carries on from the same second', () => {
  start()
  advance(4000)
  expect(clock()).toBe('4')
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
  advance(10_000)
  expect(clock()).toBe('4')
  expect(screen.getByText('Paused')).toBeInTheDocument()
  expect(playBeep).toHaveBeenCalledTimes(3)
  fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
  advance(1000)
  expect(clock()).toBe('3')
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '28') // 5 of 18 s
})

test('stopping mid-rest finishes with the rounds done', () => {
  const { onFinish, onCancel } = start()
  advance(10_000)
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(onFinish).toHaveBeenCalledExactlyOnceWith({ rounds: 1, work: 5, rest: 5 })
  expect(onCancel).not.toHaveBeenCalled()
  expect(screen.getByText('Stopped early')).toBeInTheDocument()
  expect(screen.getByText('1 round of 5 s on / 5 s off')).toBeInTheDocument()
  advance(20_000)
  expect(playFinished).not.toHaveBeenCalled()
})

test('stopping before the first round ends cancels and returns to setup', () => {
  const { onFinish, onCancel } = start()
  advance(6000) // mid-work, round 1
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(onCancel).toHaveBeenCalledOnce()
  expect(onFinish).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument()
})

test('the screen is kept awake while running and released on stop', async () => {
  const release = vi.fn().mockResolvedValue(undefined)
  const request = vi.fn().mockResolvedValue({ release })
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  await act(async () => {})
  expect(request).toHaveBeenCalledWith('screen')
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(release).toHaveBeenCalledOnce()
})

test('a wake lock granted after Stop is released at once', async () => {
  const release = vi.fn().mockResolvedValue(undefined)
  let grant: (lock: { release: typeof release }) => void = () => {}
  const request = vi.fn(() => new Promise((resolve) => (grant = resolve)))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(release).not.toHaveBeenCalled()
  await act(async () => grant({ release }))
  expect(release).toHaveBeenCalledOnce()
})

test('the wake lock is asked for again when the page becomes visible while running', async () => {
  const release = vi.fn().mockResolvedValue(undefined)
  const request = vi.fn().mockResolvedValue({ release })
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  const visibility = vi.spyOn(document, 'visibilityState', 'get')
  start()
  await act(async () => {})
  expect(request).toHaveBeenCalledTimes(1)
  visibility.mockReturnValue('hidden')
  await act(async () => document.dispatchEvent(new Event('visibilitychange')))
  expect(request).toHaveBeenCalledTimes(1)
  visibility.mockReturnValue('visible')
  await act(async () => document.dispatchEvent(new Event('visibilitychange')))
  expect(request).toHaveBeenCalledTimes(2)
  expect(release).toHaveBeenCalledOnce() // the old lock, replaced by the new one
  fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(release).toHaveBeenCalledTimes(2)
  await act(async () => document.dispatchEvent(new Event('visibilitychange')))
  expect(request).toHaveBeenCalledTimes(2) // not running any more
  visibility.mockRestore()
})

test('a refused wake lock does not stop the timer', async () => {
  const request = vi.fn().mockRejectedValue(new Error('denied'))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  await act(async () => {})
  advance(1000)
  expect(clock()).toBe('2')
})
