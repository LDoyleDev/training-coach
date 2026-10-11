import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import HiitTimer from './HiitTimer'
import { playBeep, playBell, playFinished, speak, unlockAudio, voiceSupported } from './sounds'

vi.mock('./sounds', () => ({
  unlockAudio: vi.fn(),
  playBeep: vi.fn(),
  playBell: vi.fn(),
  playFinished: vi.fn(),
  speak: vi.fn(),
  voiceSupported: vi.fn(),
}))

// prepare 0-3, work 3-8, rest 8-13, work 13-18.
const SHORT = { prepare: 3, rounds: 2, work: 5, rest: 5 }

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  vi.mocked(voiceSupported).mockReturnValue(false)
  localStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  Reflect.deleteProperty(navigator, 'wakeLock')
})

const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms))
const clock = () => screen.getByRole('timer').textContent
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const summary = () => screen.getByText(/intervals/).textContent

function start(props: Parameters<typeof HiitTimer>[0] = { defaults: SHORT }) {
  const onFinish = vi.fn()
  const onCancel = vi.fn()
  render(<HiitTimer onFinish={onFinish} onCancel={onCancel} {...props} />)
  click('Start')
  return { onFinish, onCancel }
}

const stop = () => {
  click('Stop')
  click('Stop') // confirm
}

test('setup starts from the Tabata defaults and shows the total time and intervals', () => {
  render(<HiitTimer />)
  const expected = {
    Prepare: 10,
    Work: 20,
    Rest: 10,
    Cycles: 8,
    Sets: 1,
    'Rest between sets': 60,
    'Cool down': 0,
  }
  for (const [label, value] of Object.entries(expected)) {
    expect(screen.getByLabelText(label)).toHaveValue(value)
  }
  expect(summary()).toBe('Total 4:00 · 16 intervals')
  expect(screen.getByRole('button', { name: /^Tabata/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Voice cues')).not.toBeInTheDocument() // no speech here
})

test("the plan's rounds set the cycles", () => {
  render(<HiitTimer defaults={{ rounds: 10 }} />)
  expect(screen.getByLabelText('Cycles')).toHaveValue(10)
  expect(screen.getByRole('button', { name: /^Tabata/ })).toHaveAttribute('aria-pressed', 'false')
})

test('− and + change a setting within its limits, and typing is clamped on blur', () => {
  render(<HiitTimer defaults={{ rounds: 4 }} />)
  expect(summary()).toBe('Total 2:00 · 8 intervals')
  click('More sets')
  expect(screen.getByLabelText('Sets')).toHaveValue(2)
  expect(summary()).toBe('Total 4:50 · 16 intervals') // 10 + 2 × 1:50 + 1:00 between
  click('Less rest')
  click('Less rest')
  expect(screen.getByLabelText('Rest')).toHaveValue(0)
  expect(screen.getByRole('button', { name: 'Less rest' })).toBeDisabled()
  const work = screen.getByLabelText('Work')
  fireEvent.change(work, { target: { value: '0' } })
  fireEvent.blur(work)
  expect(work).toHaveValue(1)
})

test('blurring an empty field restores the same default that Start would use', () => {
  render(<HiitTimer defaults={{ rounds: 4 }} />)
  const cycles = screen.getByLabelText('Cycles')
  fireEvent.change(cycles, { target: { value: '' } })
  expect(summary()).toBe('Total 2:00 · 8 intervals')
  fireEvent.blur(cycles)
  expect(cycles).toHaveValue(4)
})

test('Cancel in setup leaves with nothing', () => {
  const onCancel = vi.fn()
  render(<HiitTimer onCancel={onCancel} />)
  click('Cancel')
  expect(onCancel).toHaveBeenCalledOnce()
})

test('Start unlocks audio and counts in 3, 2, 1 with beeps, then rings the bell for work', () => {
  start()
  expect(unlockAudio).toHaveBeenCalledOnce()
  expect(screen.getByText('Get ready')).toBeInTheDocument()
  expect(screen.getByText('0:18 left')).toBeInTheDocument()
  expect(clock()).toBe('3')
  expect(playBeep).toHaveBeenCalledTimes(1)
  advance(1000)
  expect(clock()).toBe('2')
  advance(1000)
  expect(playBeep).toHaveBeenCalledTimes(3)
  expect(playBell).not.toHaveBeenCalled()
  advance(1000)
  expect(playBell).toHaveBeenCalledExactlyOnceWith('work')
  expect(screen.getByText('Work')).toBeInTheDocument()
  expect(screen.getByText('Cycle 1/2')).toBeInTheDocument()
  expect(clock()).toBe('5')
  expect(speak).not.toHaveBeenCalled() // voice is off
})

test('with no prepare the work bell rings at once', () => {
  start({ defaults: { ...SHORT, prepare: 0 } })
  expect(playBell).toHaveBeenCalledExactlyOnceWith('work')
  expect(screen.getByText('Work')).toBeInTheDocument()
})

test('beeps come at 3, 2 and 1 before each transition and the rest bell rings on time', () => {
  start()
  advance(4900) // t = 4.9, work has 3.1 s left
  expect(playBeep).toHaveBeenCalledTimes(3)
  advance(100) // 3 s left
  expect(playBeep).toHaveBeenCalledTimes(4)
  advance(2000)
  expect(playBeep).toHaveBeenCalledTimes(6)
  advance(1000) // t = 8: rest starts
  expect(playBell).toHaveBeenLastCalledWith('rest')
  expect(screen.getByText('Rest')).toBeInTheDocument()
})

test('the full workout ends with the finished sound, a summary and onFinish', () => {
  const { onFinish, onCancel } = start()
  advance(18_000)
  expect(playFinished).toHaveBeenCalledOnce()
  expect(playBell).toHaveBeenCalledTimes(3)
  expect(playBeep).toHaveBeenCalledTimes(12)
  expect(onFinish).toHaveBeenCalledExactlyOnceWith({
    rounds: 2,
    work: 5,
    rest: 5,
    sets: 1,
    seconds: 15,
  })
  expect(onCancel).not.toHaveBeenCalled()
  expect(screen.getByRole('heading', { name: 'Done!' })).toBeInTheDocument()
  expect(screen.getByText('2 rounds in 0:15')).toBeInTheDocument()
  click('Back to the timer')
  expect(screen.getByLabelText('Work')).toHaveValue(5)
})

test('sets: rest between sets, the set counter, cool down, and every round counted', () => {
  // prepare 0-3, w 3-8, r 8-13, w 13-18, between 18-22, w 22-27, r 27-32, w 32-37, cool 37-40
  const { onFinish } = start({ defaults: { ...SHORT, sets: 2, setRest: 4, coolDown: 3 } })
  expect(screen.getByText('Cycle 1/2 · Set 1/2')).toBeInTheDocument()
  advance(19_000)
  expect(screen.getByText('Rest between sets')).toBeInTheDocument()
  expect(playBell).toHaveBeenLastCalledWith('rest')
  advance(4000) // t = 23
  expect(screen.getByText('Cycle 1/2 · Set 2/2')).toBeInTheDocument()
  advance(15_000) // t = 38
  expect(screen.getByText('Cool down')).toBeInTheDocument()
  advance(2000)
  expect(onFinish).toHaveBeenCalledExactlyOnceWith({
    rounds: 4,
    work: 5,
    rest: 5,
    sets: 2,
    seconds: 37,
  })
  expect(screen.getByText('5 s on / 5 s off, 2 sets')).toBeInTheDocument()
})

test('pause stops the clock and resume carries on from the same second', () => {
  start()
  advance(4000)
  expect(clock()).toBe('4')
  click('Pause')
  advance(10_000)
  expect(clock()).toBe('4')
  expect(screen.getByText('Paused')).toBeVisible()
  expect(playBeep).toHaveBeenCalledTimes(3)
  click('Resume')
  advance(1000)
  expect(clock()).toBe('3')
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '28') // 5 of 18 s
})

test('skip forward and back move between sections; a skipped work does not count', () => {
  const { onFinish } = start()
  click('Skip') // prepare -> work 1
  expect(screen.getByText('Work')).toBeInTheDocument()
  expect(clock()).toBe('5')
  click('Skip') // work 1 skipped -> rest
  expect(screen.getByText('Rest')).toBeInTheDocument()
  expect(playBell).toHaveBeenLastCalledWith('rest')
  click('Back') // just started: back to work 1, which counts again if done
  expect(screen.getByText('Work')).toBeInTheDocument()
  advance(3000)
  click('Back') // 3 s in: restart it
  expect(clock()).toBe('5')
  advance(5000) // work 1 done
  click('Skip') // rest -> work 2
  click('Skip') // work 2 skipped -> the end
  expect(playFinished).toHaveBeenCalledOnce()
  expect(onFinish).toHaveBeenCalledWith(expect.objectContaining({ rounds: 1 }))
})

test('skipping while paused stays paused', () => {
  start()
  click('Pause')
  click('Skip')
  expect(screen.getByText('Work')).toBeInTheDocument()
  advance(3000)
  expect(clock()).toBe('5')
  click('Resume')
  expect(playBell).toHaveBeenCalledExactlyOnceWith('work')
})

test('Stop asks first; Keep going carries on from where it was', () => {
  const { onFinish, onCancel } = start()
  advance(4000)
  click('Stop')
  expect(screen.getByText('Stop the workout?')).toBeInTheDocument()
  advance(5000) // paused while asking
  expect(clock()).toBe('4')
  click('Keep going')
  advance(1000)
  expect(clock()).toBe('3')
  expect(onFinish).not.toHaveBeenCalled()
  expect(onCancel).not.toHaveBeenCalled()
})

test('Keep going after pausing first stays paused', () => {
  start()
  click('Pause')
  click('Stop')
  click('Keep going')
  expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument()
})

test('stopping mid-rest finishes with the rounds done', () => {
  const { onFinish, onCancel } = start()
  advance(10_000)
  stop()
  expect(onFinish).toHaveBeenCalledExactlyOnceWith({
    rounds: 1,
    work: 5,
    rest: 5,
    sets: 1,
    seconds: 7,
  })
  expect(onCancel).not.toHaveBeenCalled()
  expect(screen.getByText('Stopped early')).toBeInTheDocument()
  expect(screen.getByText('1 round in 0:07')).toBeInTheDocument()
  advance(20_000)
  expect(playFinished).not.toHaveBeenCalled()
})

test('stopping before the first round ends cancels and returns to setup', () => {
  const { onFinish, onCancel } = start()
  advance(6000) // mid-work, round 1
  stop()
  expect(onCancel).toHaveBeenCalledOnce()
  expect(onFinish).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument()
})

test('voice cues, when on, say work, rest, last round and done; the choice is remembered', () => {
  vi.mocked(voiceSupported).mockReturnValue(true)
  const { unmount } = render(<HiitTimer defaults={SHORT} />)
  const toggle = screen.getByLabelText('Voice cues')
  expect(toggle).not.toBeChecked()
  fireEvent.click(toggle)
  unmount()
  start()
  expect(screen.queryByText('Voice cues')).not.toBeInTheDocument()
  advance(3000)
  expect(speak).toHaveBeenLastCalledWith('Work')
  advance(5000)
  expect(speak).toHaveBeenLastCalledWith('Rest')
  advance(5000)
  expect(speak).toHaveBeenLastCalledWith('Last round')
  advance(5000)
  expect(speak).toHaveBeenLastCalledWith('Done')
})

test('save the settings as a named workout, pick it later, change it and delete it', () => {
  const { unmount } = render(<HiitTimer />)
  click('More cycles')
  expect(screen.getByRole('button', { name: /^Tabata/ })).toHaveAttribute('aria-pressed', 'true')
  click('Save changes to Tabata')
  click('Save as new')
  const name = screen.getByLabelText('Workout name')
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  fireEvent.change(name, { target: { value: 'Bike sprints' } })
  fireEvent.submit(name)
  expect(screen.getByRole('button', { name: /^Bike sprints/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  unmount()

  render(<HiitTimer />)
  click(/^Bike sprints/)
  expect(screen.getByLabelText('Cycles')).toHaveValue(9)
  click('Less cycles')
  click('Save changes to Bike sprints')
  click(/^Tabata/)
  expect(screen.getByLabelText('Cycles')).toHaveValue(9) // changed earlier
  click(/^Bike sprints/)
  expect(screen.getByLabelText('Cycles')).toHaveValue(8)
  click('Delete Bike sprints')
  click('Keep')
  click('Delete Bike sprints')
  click('Delete')
  expect(screen.queryByRole('button', { name: /^Bike sprints/ })).not.toBeInTheDocument()
  click(/^Tabata/)
  click('Delete Tabata')
  click('Delete')
  expect(screen.getByText('None saved yet.')).toBeInTheDocument()
})

test('naming a workout can be cancelled', () => {
  render(<HiitTimer />)
  click('Save as new')
  click('Cancel')
  expect(screen.queryByLabelText('Workout name')).not.toBeInTheDocument()
})

test('without storage the timer still works and saving does nothing', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  render(<HiitTimer defaults={SHORT} />)
  click('Save as new')
  fireEvent.change(screen.getByLabelText('Workout name'), { target: { value: 'Rower' } })
  click('Save')
  expect(screen.getByRole('button', { name: /^Rower/ })).toBeInTheDocument()
  click('Start')
  advance(4000)
  expect(clock()).toBe('4')
})

test('the screen is kept awake while running and released on stop', async () => {
  const release = vi.fn().mockResolvedValue(undefined)
  const request = vi.fn().mockResolvedValue({ release })
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  await act(async () => {})
  expect(request).toHaveBeenCalledWith('screen')
  stop()
  expect(release).toHaveBeenCalledOnce()
})

test('a wake lock granted after Stop is released at once', async () => {
  const release = vi.fn().mockResolvedValue(undefined)
  let grant: (lock: { release: typeof release }) => void = () => {}
  const request = vi.fn(() => new Promise((resolve) => (grant = resolve)))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  stop()
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
  stop()
  expect(release).toHaveBeenCalledTimes(2)
  await act(async () => document.dispatchEvent(new Event('visibilitychange')))
  expect(request).toHaveBeenCalledTimes(2) // not running any more
})

test('a refused wake lock does not stop the timer', async () => {
  const request = vi.fn().mockRejectedValue(new Error('denied'))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
  start()
  await act(async () => {})
  advance(1000)
  expect(clock()).toBe('2')
})
