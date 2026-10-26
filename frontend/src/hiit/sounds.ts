/**
 * The timers' sounds (HIIT, and the timer sound the person chooses for every guided timer,
 * ADR-0062 and ADR-0074), synthesised with the Web Audio API: no audio files, no dependencies.
 * Every sound fades in and out (no clicks). Browsers only allow audio after a user gesture, so
 * `unlockAudio()` must be called from one (the Start button). Without Web Audio (jsdom, very old
 * browsers) every function does nothing.
 */

type Ctor = typeof AudioContext

let ctx: AudioContext | null = null
let master: GainNode | null = null

function audio(): { ctx: AudioContext; out: GainNode } | null {
  if (!ctx) {
    const scope = globalThis as unknown as { AudioContext?: Ctor; webkitAudioContext?: Ctor }
    const Context = scope.AudioContext ?? scope.webkitAudioContext
    if (!Context) return null
    ctx = new Context()
    master = ctx.createGain()
    master.gain.value = 0.35 // headroom: a bell's partials add up
    master.connect(ctx.destination)
  }
  return { ctx, out: master as GainNode }
}

/** Create the audio context (first call) and wake it. Call from a click or tap. */
export function unlockAudio(): void {
  const a = audio()
  if (a && a.ctx.state === 'suspended') a.ctx.resume().catch(() => {})
}

/** One sine partial: a short fade in, then an exponential decay to silence. */
function partial(freq: number, peak: number, decay: number, delay = 0, attack = 0.005): void {
  const a = audio()
  if (!a) return
  const t = a.ctx.currentTime + delay
  const osc = a.ctx.createOscillator()
  const gain = a.ctx.createGain()
  osc.type = 'sine'
  osc.frequency.value = freq
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.linearRampToValueAtTime(peak, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + decay)
  osc.connect(gain)
  gain.connect(a.out)
  osc.start(t)
  osc.stop(t + decay + 0.05)
}

/** The soft countdown beep for 3, 2, 1: 880 Hz, 120 ms. */
export function playBeep(): void {
  partial(880, 0.5, 0.12, 0, 0.012)
}

/** A struck bell: inharmonic partials, the high ones dying first. */
function bell(fundamental: number, loudness: number, length: number, delay = 0): void {
  const partials: [ratio: number, level: number, decay: number][] = [
    [1, 1, 1],
    [2.0, 0.5, 0.7],
    [2.76, 0.35, 0.5],
    [5.4, 0.15, 0.25],
  ]
  for (const [ratio, level, decay] of partials) {
    partial(fundamental * ratio, loudness * level, length * decay, delay)
  }
}

/** A struck bell when work starts; for any rest, a softer, rounder chime with a slow attack. */
export function playBell(phase: 'work' | 'rest'): void {
  if (phase === 'work') {
    bell(784, 0.6, 1.5)
    return
  }
  partial(523, 0.4, 1.4, 0, 0.04)
  partial(784, 0.18, 1.0, 0, 0.04)
}

/** Three rising chimes when the workout is done. */
export function playFinished(): void {
  bell(659, 0.45, 0.8, 0)
  bell(784, 0.45, 0.8, 0.18)
  bell(1047, 0.5, 1.8, 0.36)
}

/**
 * What every guided timer plays at each change; the person picks one in Settings (ADR-0062).
 * The boxing-ring bell comes first and is everyone's default (ADR-0074).
 */
export const SOUNDS = ['ring', 'chime', 'beep', 'wood', 'bell', 'none'] as const
export type Sound = (typeof SOUNDS)[number]
export const DEFAULT_SOUND: Sound = 'ring'

/**
 * The changes a guided timer marks: `count` for each of the last 3 s, `switch` for a side
 * switch (or any small change), `next` when the next thing starts (a movement, a set after a
 * rest), `finish` at the end.
 */
export const CHANGES = ['count', 'switch', 'next', 'finish'] as const
export type Change = (typeof CHANGES)[number]

/** A woodblock knock: a bright click with a quick body. */
function knock(freq: number, delay = 0): void {
  partial(freq, 0.6, 0.06, delay, 0.002)
  partial(freq * 2.4, 0.25, 0.03, delay, 0.002)
}

/** Strikes of the boxing-ring bell follow each other this far apart: "ding-ding". */
const RING_GAP = 0.17

/**
 * One strike of a boxing-ring bell: a bright brass dome, struck hard. A near-twin of the
 * fundamental beats against it for the shimmer; the high, clangy partials die within a
 * fraction of a second and the body rings on. The peaks add up to about 1.25 before the
 * master's headroom (0.35), and the next strike lands once the last has faded to a fifth, so
 * even three strikes stay well clear of clipping.
 */
function strike(delay: number, length: number): void {
  const partials: [ratio: number, level: number, decay: number][] = [
    [1, 1, 1],
    [1.006, 0.5, 0.9],
    [2.32, 0.6, 0.55],
    [4.25, 0.35, 0.3],
    [6.63, 0.2, 0.15],
    [9.38, 0.12, 0.06],
  ]
  for (const [ratio, level, decay] of partials) {
    partial(1100 * ratio, 0.45 * level, length * decay, delay, 0.002)
  }
}

/** `times` strikes of the boxing-ring bell, the last left to ring out longer. */
function ring(times: number): void {
  for (let i = 0; i < times; i++) strike(i * RING_GAP, i === times - 1 ? 1.8 : 1.0)
}

/** Each sound's voice for a count, a side switch, the next movement and the end. */
const VOICES: Record<Exclude<Sound, 'none'>, Record<Change, () => void>> = {
  ring: {
    count: () => {
      partial(2550, 0.18, 0.05, 0, 0.002) // a soft tick, a fingernail on the bell
      partial(1100, 0.1, 0.12, 0, 0.002)
    },
    switch: () => ring(1),
    next: () => ring(2), // ding-ding: the round starts
    finish: () => ring(3),
  },
  chime: {
    count: () => partial(1047, 0.25, 0.3, 0, 0.01),
    switch: () => {
      partial(659, 0.35, 0.9, 0, 0.03)
      partial(988, 0.2, 0.7, 0.12, 0.03)
    },
    next: () => playBell('rest'),
    finish: () => [523, 659, 784].forEach((f, i) => partial(f, 0.35, 1.2, i * 0.18, 0.03)),
  },
  beep: {
    count: () => playBeep(),
    switch: () => [0, 0.2].forEach((d) => partial(988, 0.5, 0.12, d, 0.01)),
    next: () => partial(1175, 0.5, 0.35, 0, 0.01),
    finish: () => [880, 1047, 1319].forEach((f, i) => partial(f, 0.5, 0.2, i * 0.18, 0.01)),
  },
  wood: {
    count: () => knock(1400),
    switch: () => [0, 0.15].forEach((d) => knock(1000, d)),
    next: () => {
      knock(700)
      knock(1050, 0.12)
    },
    finish: () => [700, 900, 1200].forEach((f, i) => knock(f, i * 0.15)),
  },
  bell: {
    count: () => playBeep(),
    switch: () => bell(659, 0.5, 1.0),
    next: () => playBell('work'),
    finish: () => playFinished(),
  },
}

/** Play `change` in the chosen sound; 'none' plays nothing. */
export function playChange(sound: Sound, change: Change): void {
  if (sound !== 'none') VOICES[sound][change]()
}

type Speech = {
  speechSynthesis?: SpeechSynthesis
  SpeechSynthesisUtterance?: typeof SpeechSynthesisUtterance
}

/** Whether this browser can speak the voice cues. */
export function voiceSupported(): boolean {
  const scope = globalThis as unknown as Speech
  return Boolean(scope.speechSynthesis && scope.SpeechSynthesisUtterance)
}

/** Say a short cue ("Work", "Rest", "Done"), cutting off any cue still being said. */
export function speak(text: string): void {
  const scope = globalThis as unknown as Speech
  if (!scope.speechSynthesis || !scope.SpeechSynthesisUtterance) return
  try {
    const utterance = new scope.SpeechSynthesisUtterance(text)
    utterance.rate = 1.05
    scope.speechSynthesis.cancel()
    scope.speechSynthesis.speak(utterance)
  } catch {
    // speech can fail on some systems; the bells still ring
  }
}
