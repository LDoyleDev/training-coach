import { useEffect, useMemo, useRef, useState } from 'react'
import { card, danger, primary, primaryInline, secondary, small } from '../ui'
import {
  DEFAULTS,
  LIMITS,
  buildSchedule,
  formatClock,
  formatDuration,
  parseSetting,
  positionAt,
  roundsCompleted,
  workoutSeconds,
  type HiitSettings,
  type Phase,
} from './logic'
import { playBeep, playBell, playFinished, unlockAudio } from './sounds'

/** What `onFinish` gets: the rounds done (all of them, or fewer when stopped early). */
export type HiitResult = HiitSettings

export type HiitTimerProps = {
  /** Starting values for the setup step, e.g. the plan's target rounds. */
  defaults?: Partial<HiitSettings>
  /** Called once when the workout ends or is stopped after at least one round. */
  onFinish?: (result: HiitResult) => void
  /** Called when the user leaves with nothing: Cancel in setup, or Stop before round 1 ends. */
  onCancel?: () => void
}

const TICK_MS = 100

const NAMES: Record<keyof HiitSettings, string> = {
  rounds: 'Rounds',
  work: 'Work (seconds)',
  rest: 'Rest (seconds)',
}

const LOOK: Record<Phase, { label: string; className: string }> = {
  ready: { label: 'Get ready', className: 'bg-[var(--paper)] text-[var(--ink)]' },
  work: { label: 'Work', className: 'bg-[var(--bell-ink)] text-[var(--chalk)]' },
  rest: { label: 'Rest', className: 'bg-[var(--rec)] text-[var(--ink)]' },
}

type Stage = 'setup' | 'running' | 'finished'

function Stepper(props: {
  name: keyof HiitSettings
  value: string
  onChange: (value: string) => void
}) {
  const { name, value, onChange } = props
  const { min, max, step } = LIMITS[name]
  const id = `hiit-${name}`
  const current = parseSetting(name, value, min)
  const label = NAMES[name].split(' ')[0].toLowerCase()
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="font-bold">
        {NAMES[name]}
      </label>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className={small + ' min-w-11 text-xl'}
          aria-label={`Less ${label}`}
          disabled={current <= min}
          onClick={() => onChange(String(Math.max(min, current - step)))}
        >
          −
        </button>
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          value={value}
          className="min-w-0 flex-1 text-center text-xl font-bold"
          onChange={(e) => onChange(e.target.value)}
          onBlur={() => onChange(String(current))}
        />
        <button
          type="button"
          className={small + ' min-w-11 text-xl'}
          aria-label={`More ${label}`}
          disabled={current >= max}
          onClick={() => onChange(String(Math.min(max, current + step)))}
        >
          +
        </button>
      </div>
    </div>
  )
}

/** A HIIT interval timer: choose rounds, work and rest, then follow the clock and the bells. */
export default function HiitTimer({ defaults, onFinish, onCancel }: HiitTimerProps) {
  const start = { ...DEFAULTS, ...defaults }
  const [draft, setDraft] = useState({
    rounds: String(start.rounds),
    work: String(start.work),
    rest: String(start.rest),
  })
  const settings: HiitSettings = {
    rounds: parseSetting('rounds', draft.rounds, start.rounds),
    work: parseSetting('work', draft.work, start.work),
    rest: parseSetting('rest', draft.rest, start.rest),
  }
  const [stage, setStage] = useState<Stage>('setup')
  const [running, setRunning] = useState<HiitSettings>(settings)
  const [paused, setPaused] = useState(false)
  const [elapsed, setElapsed] = useState(0) // seconds, recomputed from timestamps
  const [result, setResult] = useState<{ done: HiitResult; early: boolean } | null>(null)
  const schedule = useMemo(() => buildSchedule(running), [running])

  // The clock: time banked before the last pause, plus time since the last (re)start.
  const banked = useRef(0)
  const since = useRef<number | null>(null)
  const lastSection = useRef(0)
  const lastBeep = useRef('')
  const wakeLock = useRef<WakeLockSentinel | null>(null)

  const now = () =>
    (banked.current + (since.current === null ? 0 : Date.now() - since.current)) / 1000

  const releaseWakeLock = () => {
    wakeLock.current?.release().catch(() => {})
    wakeLock.current = null
  }

  const end = (done: HiitResult, early: boolean) => {
    since.current = null
    releaseWakeLock()
    setResult({ done, early })
    setStage('finished')
    onFinish?.(done)
  }

  useEffect(() => releaseWakeLock, [])

  // One tick: recompute everything from the elapsed time, and play what is due.
  const tick = () => {
    const t = now()
    const at = positionAt(schedule, t)
    setElapsed(t)
    if (at.done) {
      playFinished()
      end(running, false)
      return
    }
    if (at.index !== lastSection.current) {
      lastSection.current = at.index
      if (at.section.phase !== 'ready') playBell(at.section.phase)
    }
    const secs = Math.ceil(at.remaining)
    const beepKey = `${at.index}:${secs}`
    if (secs <= 3 && beepKey !== lastBeep.current) {
      lastBeep.current = beepKey
      playBeep()
    }
  }
  const latestTick = useRef(tick)
  useEffect(() => {
    latestTick.current = tick
  })

  useEffect(() => {
    if (stage !== 'running' || paused) return
    latestTick.current()
    const id = setInterval(() => latestTick.current(), TICK_MS)
    return () => clearInterval(id)
  }, [stage, paused])

  const begin = () => {
    unlockAudio() // inside the click: browsers only allow audio after a gesture
    setRunning(settings)
    setDraft({
      rounds: String(settings.rounds),
      work: String(settings.work),
      rest: String(settings.rest),
    })
    banked.current = 0
    since.current = Date.now()
    lastSection.current = 0
    lastBeep.current = ''
    setElapsed(0)
    setPaused(false)
    setStage('running')
    try {
      navigator.wakeLock
        ?.request('screen')
        .then((lock) => {
          wakeLock.current = lock
        })
        .catch(() => {})
    } catch {
      // no wake lock: the screen may dim, the timer still works
    }
  }

  const togglePause = () => {
    if (paused) {
      since.current = Date.now()
    } else {
      banked.current = now() * 1000
      since.current = null
    }
    setPaused(!paused)
  }

  const stop = () => {
    const completed = roundsCompleted(schedule, now())
    if (completed > 0) {
      end({ ...running, rounds: completed }, true)
      return
    }
    since.current = null
    releaseWakeLock()
    setStage('setup')
    onCancel?.()
  }

  if (stage === 'setup') {
    return (
      <section aria-labelledby="hiit-title" className={card + ' flex flex-col gap-4'}>
        <h2 id="hiit-title">HIIT timer</h2>
        {(['rounds', 'work', 'rest'] as const).map((name) => (
          <Stepper
            key={name}
            name={name}
            value={draft[name]}
            onChange={(value) => setDraft({ ...draft, [name]: value })}
          />
        ))}
        <p className="text-[var(--slate)]">
          Total{' '}
          <span className="font-bold text-[var(--ink)]">
            {formatDuration(workoutSeconds(settings))}
          </span>
        </p>
        <button type="button" className={primary} onClick={begin}>
          Start
        </button>
        {onCancel && (
          <button type="button" className={secondary} onClick={onCancel}>
            Cancel
          </button>
        )}
      </section>
    )
  }

  if (stage === 'finished' && result) {
    const { done, early } = result
    return (
      <section aria-labelledby="hiit-title" className={card + ' flex flex-col gap-2'}>
        <h2 id="hiit-title">{early ? 'Stopped early' : 'Done!'}</h2>
        <p className="text-xl font-bold">
          {done.rounds} {done.rounds === 1 ? 'round' : 'rounds'} of {done.work} s on / {done.rest} s
          off
        </p>
      </section>
    )
  }

  const at = positionAt(schedule, elapsed)
  const { label, className } = LOOK[at.section.phase]
  const total = schedule[schedule.length - 1].end
  const progress = Math.min(100, Math.round((elapsed / total) * 100))
  return (
    <section aria-label="HIIT timer" className="flex flex-col gap-3">
      <div
        className={`flex flex-col items-center gap-1 rounded-2xl border-2 border-[var(--line)] p-4 text-center ${className}`}
      >
        <p aria-live="polite" className="text-3xl font-extrabold tracking-wide uppercase">
          {label}
        </p>
        <p className="text-lg font-bold">
          Round {at.section.round} of {running.rounds}
        </p>
        <p
          role="timer"
          aria-label="Seconds left"
          className="num text-[min(40vw,12rem)] leading-none font-extrabold [font-stretch:68%]"
        >
          {formatClock(at.remaining)}
        </p>
        {paused && <p className="font-bold">Paused</p>}
      </div>
      <div
        role="progressbar"
        aria-label="Workout progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        className="h-3 overflow-hidden rounded-full bg-[var(--line)]"
      >
        <div className="h-full bg-[var(--ink)]" style={{ width: `${progress}%` }} />
      </div>
      <div className="flex gap-2">
        <button type="button" className={primaryInline + ' min-h-14 flex-1'} onClick={togglePause}>
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button type="button" className={danger + ' min-h-14 flex-1'} onClick={stop}>
          Stop
        </button>
      </div>
    </section>
  )
}
