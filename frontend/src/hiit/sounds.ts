/**
 * The HIIT timer's sounds, synthesised with the Web Audio API: no audio files, no dependencies.
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

/** The bell at the start of a section: brighter for work, lower and softer for rest. */
export function playBell(phase: 'work' | 'rest'): void {
  if (phase === 'work') bell(784, 0.6, 1.5)
  else bell(587, 0.45, 1.6)
}

/** Three rising chimes when the workout is done. */
export function playFinished(): void {
  bell(659, 0.45, 0.8, 0)
  bell(784, 0.45, 0.8, 0.18)
  bell(1047, 0.5, 1.8, 0.36)
}
