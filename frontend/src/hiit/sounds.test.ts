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

test('without speech synthesis the voice is unsupported and speaking does nothing', async () => {
  vi.stubGlobal('speechSynthesis', undefined)
  const sounds = await import('./sounds')
  expect(sounds.voiceSupported()).toBe(false)
  expect(() => sounds.speak('Work')).not.toThrow()
})

test('a cue cuts off the one before it and is spoken', async () => {
  const spoken: string[] = []
  const synth = { cancel: vi.fn(), speak: vi.fn((u: { text: string }) => spoken.push(u.text)) }
  class Utterance {
    rate = 1
    text: string
    constructor(text: string) {
      this.text = text
    }
  }
  vi.stubGlobal('speechSynthesis', synth)
  vi.stubGlobal('SpeechSynthesisUtterance', Utterance)
  const sounds = await import('./sounds')
  expect(sounds.voiceSupported()).toBe(true)
  sounds.speak('Rest')
  expect(synth.cancel).toHaveBeenCalledOnce()
  expect(spoken).toEqual(['Rest'])
  synth.speak.mockImplementation(() => {
    throw new Error('no voices')
  })
  expect(() => sounds.speak('Done')).not.toThrow()
})

test('unlocking resumes a suspended context', async () => {
  const { resume } = fakeAudio()
  const sounds = await import('./sounds')
  sounds.unlockAudio()
  expect(resume).toHaveBeenCalledOnce()
})

test('the beep is one 880 Hz tone; work is a four-partial bell, rest a softer, lower chime', async () => {
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
  expect(frequencies).toEqual([523, 784])
  frequencies.length = 0
  sounds.playFinished()
  expect(frequencies).toHaveLength(12)
})

test('each timer sound plays every change, and none plays nothing', async () => {
  const { frequencies } = fakeAudio('running')
  const sounds = await import('./sounds')
  for (const sound of ['chime', 'beep', 'wood', 'bell'] as const) {
    for (const change of ['count', 'switch', 'next', 'finish'] as const) {
      const before = frequencies.length
      sounds.playChange(sound, change)
      expect(frequencies.length, `${sound} ${change}`).toBeGreaterThan(before)
    }
  }
  const before = frequencies.length
  sounds.playChange('none', 'next')
  expect(frequencies).toHaveLength(before)
})
