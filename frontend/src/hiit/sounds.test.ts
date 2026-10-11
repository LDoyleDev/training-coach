import { afterEach, expect, test, vi } from 'vitest'

/** A stand-in for Web Audio, recording the oscillators it is asked to play. */
function fakeAudio(state = 'suspended') {
  const frequencies: number[] = []
  const param = () => ({
    value: 0,
    setValueAtTime: vi.fn(),
    linearRampToValueAtTime: vi.fn(),
    exponentialRampToValueAtTime: vi.fn(),
  })
  const resume = vi.fn().mockResolvedValue(undefined)
  class FakeContext {
    state = state
    currentTime = 0
    destination = {}
    resume = resume
    createGain() {
      return { gain: param(), connect: vi.fn() }
    }
    createOscillator() {
      const frequency = param()
      return {
        type: '',
        frequency,
        connect: vi.fn(),
        start: vi.fn(() => frequencies.push(frequency.value)),
        stop: vi.fn(),
      }
    }
  }
  vi.stubGlobal('AudioContext', FakeContext)
  return { frequencies, resume }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

test('without Web Audio every sound is silent and nothing throws', async () => {
  vi.stubGlobal('AudioContext', undefined)
  const sounds = await import('./sounds')
  expect(() => {
    sounds.unlockAudio()
    sounds.playBeep()
    sounds.playBell('work')
    sounds.playFinished()
  }).not.toThrow()
})

test('unlocking resumes a suspended context', async () => {
  const { resume } = fakeAudio()
  const sounds = await import('./sounds')
  sounds.unlockAudio()
  expect(resume).toHaveBeenCalledOnce()
})

test('the beep is one 880 Hz tone; bells are four inharmonic partials, rest lower than work', async () => {
  const { frequencies } = fakeAudio('running')
  const sounds = await import('./sounds')
  sounds.unlockAudio()
  sounds.playBeep()
  expect(frequencies).toEqual([880])
  frequencies.length = 0
  sounds.playBell('work')
  expect(frequencies).toEqual([784, 1568, 784 * 2.76, 784 * 5.4])
  frequencies.length = 0
  sounds.playBell('rest')
  expect(frequencies[0]).toBe(587)
  frequencies.length = 0
  sounds.playFinished()
  expect(frequencies).toHaveLength(12)
})
