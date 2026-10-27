import { afterEach, expect, test, vi } from 'vitest'
import type { MessageSettings } from '../api'
import type { Sound } from './sounds'

/** A stand-in for Web Audio, recording the oscillators it is asked to play: each one's
 * frequency, when it starts, and the bus (the gain node) its own gain feeds. */
function fakeAudio(state = 'suspended') {
  const frequencies: number[] = []
  const notes: { freq: number; at: number; bus: unknown }[] = []
  const gains: { gain: { value: number }; connect: ReturnType<typeof vi.fn> }[] = []
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
      const node = { gain: param(), connect: vi.fn() }
      gains.push(node)
      return node
    }
    createDynamicsCompressor() {
      const p = { threshold: param(), knee: param(), ratio: param(), attack: param() }
      return { ...p, release: param(), connect: vi.fn() }
    }
    createOscillator() {
      const frequency = param()
      const osc = {
        type: '',
        frequency,
        connect: vi.fn(),
        start: vi.fn((at: number) => {
          frequencies.push(frequency.value)
          const own = gains.find((g) => osc.connect.mock.calls[0]?.[0] === g)
          notes.push({ freq: frequency.value, at, bus: own?.connect.mock.calls[0]?.[0] })
        }),
        stop: vi.fn(),
      }
      return osc
    }
  }
  vi.stubGlobal('AudioContext', FakeContext)
  return { frequencies, notes, gains, resume }
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
    sounds.playSessionEnd('ring')
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
  expect(sounds.SOUNDS).toContain('none')
  for (const sound of sounds.SOUNDS.filter((s) => s !== 'none')) {
    for (const change of sounds.CHANGES) {
      const before = frequencies.length
      sounds.playChange(sound, change)
      expect(frequencies.length, `${sound} ${change}`).toBeGreaterThan(before)
    }
  }
  const before = frequencies.length
  sounds.playChange('none', 'next')
  expect(frequencies).toHaveLength(before)
})

test('the timer sounds match the API, with the boxing bell first and the default', async () => {
  type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false
  const sameAsApi: Same<Sound, MessageSettings['sound']> = true
  expect(sameAsApi).toBe(true)
  const sounds = await import('./sounds')
  expect(sounds.SOUNDS[0]).toBe('ring')
  expect(sounds.DEFAULT_SOUND).toBe('ring')
})

test('the boxing bell strikes once for a switch, ding-ding for next, three times at the end', async () => {
  const { frequencies } = fakeAudio('running')
  const sounds = await import('./sounds')
  const strikes = (change: 'count' | 'switch' | 'next' | 'finish') => {
    frequencies.length = 0
    sounds.playChange('ring', change)
    return frequencies.filter((f) => f === 1100).length // each strike's fundamental
  }
  expect(strikes('switch')).toBe(1)
  expect(frequencies).toHaveLength(6) // six partials a strike
  expect(strikes('next')).toBe(2)
  expect(strikes('finish')).toBe(3)
  expect(strikes('count')).toBe(1)
  expect(frequencies).toEqual([2550, 1100]) // the count is a soft tick, not a strike
})

test('every sound has a louder end of a session, and none plays nothing', async () => {
  const { notes, gains } = fakeAudio('running')
  const sounds = await import('./sounds')
  sounds.unlockAudio() // makes the buses: the timer's (0.35), then the loud one (0.5)
  const [timerBus, loudBus] = gains
  expect(timerBus.gain.value).toBe(0.35)
  expect(loudBus.gain.value).toBe(0.5)
  const limiter = loudBus.connect.mock.calls[0][0] as Record<string, { value: number }>
  expect(limiter.threshold.value).toBe(-6) // a limiter on the loud bus keeps it from clipping
  expect(limiter.ratio.value).toBe(20)
  for (const sound of sounds.SOUNDS.filter((s) => s !== 'none')) {
    notes.length = 0
    sounds.playSessionEnd(sound)
    expect(notes.length, sound).toBeGreaterThan(0)
    expect(
      notes.every((n) => n.bus === loudBus),
      sound,
    ).toBe(true)
  }
  notes.length = 0
  sounds.playSessionEnd('none')
  expect(notes).toEqual([])
  sounds.playChange('ring', 'finish') // a timer's own finish stays on the timer's bus
  expect(notes.every((n) => n.bus === timerBus)).toBe(true)
})

test("the boxing bell's end runs up a major chord, then ding-ding on the octave", async () => {
  const { notes } = fakeAudio('running')
  const sounds = await import('./sounds')
  sounds.playSessionEnd('ring')
  expect(notes).toHaveLength(36) // six strikes of six partials
  const strikes = notes.filter((_, i) => i % 6 === 0) // each strike's fundamental
  expect(strikes.map((n) => n.freq)).toEqual([880, 1100, 1320, 1760, 1760, 1760])
  expect(strikes.map((n) => Number(n.at.toFixed(2)))).toEqual([0, 0.11, 0.22, 0.33, 0.62, 0.79])
})
