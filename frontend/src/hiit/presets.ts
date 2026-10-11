/**
 * Saved HIIT workouts and the voice setting, kept in this browser's localStorage. Storage can be
 * missing or throw (private mode, blocked site data), so every read falls back to the defaults
 * and every write may quietly do nothing: the timer works the same, it just forgets.
 */
import { DEFAULTS, sanitize, type HiitSettings } from './logic'

export type Preset = { id: string; name: string; settings: HiitSettings }

const WORKOUTS_KEY = 'training-coach:hiit-workouts'
const VOICE_KEY = 'training-coach:hiit-voice'

/** What a new browser starts with. */
export const DEFAULT_PRESETS: Preset[] = [{ id: 'tabata', name: 'Tabata', settings: DEFAULTS }]

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage full or blocked: nothing is saved, nothing breaks
  }
}

/** The saved workouts; the defaults if nothing is saved or what is saved is unreadable. */
export function loadPresets(): Preset[] {
  const raw = read(WORKOUTS_KEY)
  if (raw === null) return DEFAULT_PRESETS
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return DEFAULT_PRESETS
    return parsed.flatMap((item: unknown) => {
      const p = item as Partial<Preset> | null
      if (!p || typeof p.id !== 'string' || typeof p.name !== 'string' || !p.name.trim()) return []
      return [{ id: p.id, name: p.name.trim().slice(0, 40), settings: sanitize(p.settings) }]
    })
  } catch {
    return DEFAULT_PRESETS
  }
}

export function savePresets(presets: Preset[]): void {
  write(WORKOUTS_KEY, JSON.stringify(presets))
}

export function newId(): string {
  return `w${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

export function loadVoice(): boolean {
  return read(VOICE_KEY) === 'on'
}

export function saveVoice(on: boolean): void {
  write(VOICE_KEY, on ? 'on' : 'off')
}
