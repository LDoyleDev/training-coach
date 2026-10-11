import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { card, primary } from '../ui'
import HiitSetup from './HiitSetup'
import {
  DEFAULTS,
  activeSeconds,
  buildSchedule,
  cueFor,
  formatClock,
  formatDuration,
  fromDraft,
  positionAt,
  roundsCompleted,
  sanitize,
  skip,
  toDraft,
  totalSeconds,
  type Draft,
  type HiitSettings,
  type Phase,
} from './logic'
import { loadVoice, saveVoice } from './presets'
import { playBeep, playBell, playFinished, speak, unlockAudio, voiceSupported } from './sounds'

/** What `onFinish` gets. `rounds` is the work intervals completed across all sets. */
export type HiitResult = {
  rounds: number
  work: number
  rest: number
  sets: number
  /** Seconds of workout done, without the prepare count. */
  seconds: number
}

export type HiitTimerProps = {
  /** Starting values for the setup step. `rounds` (e.g. the plan's target) sets the cycles. */
  defaults?: Partial<HiitSettings> & { rounds?: number }
  /** Called once when the workout ends or is stopped after at least one round. */
  onFinish?: (result: HiitResult) => void
  /** Called when the user leaves with nothing: Cancel in setup, or Stop before a round is done. */
  onCancel?: () => void
}

const TICK_MS = 100

const LOOK: Record<Phase, { label: string; token: string }> = {
  prepare: { label: 'Get ready', token: 'prepare' },
  work: { label: 'Work', token: 'work' },
  rest: { label: 'Rest', token: 'rest' },
  setRest: { label: 'Rest between sets', token: 'set-rest' },
  coolDown: { label: 'Cool down', token: 'cool-down' },
}

/** Buttons on the phase colour: outlined in its ink, or filled with it. */
const outline =
  'min-h-14 rounded-2xl border-2 border-[var(--hiit-fg)] bg-transparent px-3 text-lg font-bold text-[var(--hiit-fg)]'
const filled =
  'min-h-14 rounded-2xl border-0 bg-[var(--hiit-fg)] px-3 text-lg font-bold text-[var(--hiit-bg)]'

type Stage = 'setup' | 'running' | 'finished'

/** A Tabata-style interval timer: prepare, sets of work/rest cycles, cool down, with bells. */
export default function HiitTimer({ defaults, onFinish, onCancel }: HiitTimerProps) {
  const [fallback] = useState(() => {
    const { rounds, ...rest } = defaults ?? {}
    return sanitize({ ...DEFAULTS, ...rest, ...(rounds === undefined ? {} : { cycles: rounds }) })
  })
  const [draft, setDraft] = useState<Draft>(() => toDraft(fallback))
  const [voice, setVoice] = useState<boolean | null>(() => (voiceSupported() ? loadVoice() : null))
  const [stage, setStage] = useState<Stage>('setup')
  const [running, setRunning] = useState<HiitSettings>(fallback)
  const [paused, setPaused] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [elapsed, setElapsed] = useState(0) // seconds, recomputed from timestamps
  const [result, setResult] = useState<{ done: HiitResult; early: boolean } | null>(null)
  const schedule = useMemo(() => buildSchedule(running), [running])
  const total = totalSeconds(schedule)

  // The clock: time banked before the last pause or skip, plus time since the last (re)start.
  const banked = useRef(0)
  const since = useRef<number | null>(null)
  const lastSection = useRef(-1)
  const lastBeep = useRef('')
  const skipped = useRef(new Set<number>()) // work sections skipped, which don't count
  const wasPaused = useRef(false)

  const now = () =>
    (banked.current + (since.current === null ? 0 : Date.now() - since.current)) / 1000

  const say = (text: string | null) => {
    if (voice && text) speak(text)
  }

  /** End the run at `t`: a summary and onFinish with the rounds done, or back to setup if none. */
  const end = (t: number, early: boolean) => {
    since.current = null
    setConfirming(false)
    const rounds = roundsCompleted(schedule, t, skipped.current)
    if (rounds === 0) {
      setStage('setup')
      onCancel?.()
      return
    }
    const done: HiitResult = {
      rounds,
      work: running.work,
      rest: running.rest,
      sets: running.sets,
      seconds: activeSeconds(schedule, t),
    }
    setResult({ done, early })
    setStage('finished')
    onFinish?.(done)
  }

  // Keep the screen awake while running. Browsers drop the lock when the page is hidden, so ask
  // again when it is visible; a lock that arrives after stop, finish or unmount is let go at once.
  useEffect(() => {
    if (stage !== 'running') return
    let live = true
    let lock: WakeLockSentinel | null = null
    const acquire = () => {
      try {
        navigator.wakeLock
          ?.request('screen')
          .then((next) => {
            if (!live) return void next.release().catch(() => {})
            lock?.release().catch(() => {})
            lock = next
          })
          .catch(() => {})
      } catch {
        // no wake lock: the screen may dim, the timer still works
      }
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') acquire()
    }
    acquire()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      live = false
      document.removeEventListener('visibilitychange', onVisible)
      lock?.release().catch(() => {})
    }
  }, [stage])

  // One tick: recompute everything from the elapsed time, and play what is due.
  const tick = () => {
    const t = now()
    const at = positionAt(schedule, t)
    setElapsed(t)
    if (at.done) {
      playFinished()
      say('Done')
      end(total, false)
      return
    }
    if (at.index !== lastSection.current) {
      lastSection.current = at.index
      const phase = at.section.phase
      if (phase === 'work') playBell('work')
      else if (phase !== 'prepare') playBell('rest')
      say(cueFor(schedule, at.index))
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
    const settings = fromDraft(draft, fallback)
    setRunning(settings)
    setDraft(toDraft(settings))
    banked.current = 0
    since.current = Date.now()
    lastSection.current = -1
    lastBeep.current = ''
    skipped.current = new Set()
    setElapsed(0)
    setPaused(false)
    setConfirming(false)
    setStage('running')
  }

  const pause = (on: boolean) => {
    if (on === paused) return
    if (on) {
      banked.current = now() * 1000
      since.current = null
    } else {
      since.current = Date.now()
    }
    setPaused(on)
  }

  const jump = (direction: 'back' | 'forward') => {
    const from = now()
    const at = positionAt(schedule, from)
    const to = skip(schedule, from, direction)
    if (direction === 'forward' && !at.done && at.section.phase === 'work') {
      skipped.current.add(at.index)
    }
    if (direction === 'back') {
      const index = positionAt(schedule, to).index
      skipped.current = new Set([...skipped.current].filter((i) => i < index))
    }
    banked.current = to * 1000
    since.current = paused ? null : Date.now()
    lastSection.current = -1 // ring the bell for wherever we land
    setElapsed(to)
    if (!paused || to >= total) latestTick.current() // skipping past the end finishes, paused or not
  }

  const askStop = () => {
    wasPaused.current = paused
    pause(true)
    setConfirming(true)
  }

  const keepGoing = () => {
    setConfirming(false)
    if (!wasPaused.current) pause(false)
  }

  if (stage === 'setup') {
    return (
      <HiitSetup
        draft={draft}
        fallback={fallback}
        onDraft={setDraft}
        voice={voice}
        onVoice={(on) => {
          setVoice(on)
          saveVoice(on)
        }}
        onStart={begin}
        onCancel={onCancel}
      />
    )
  }

  if (stage === 'finished' && result) {
    const { done, early } = result
    return (
      <section aria-labelledby="hiit-title" className={card + ' flex flex-col gap-3'}>
        <h2 id="hiit-title">{early ? 'Stopped early' : 'Done!'}</h2>
        <p className="text-xl font-bold">
          {done.rounds} {done.rounds === 1 ? 'round' : 'rounds'} in {formatDuration(done.seconds)}
        </p>
        <p className="text-[var(--slate)]">
          {done.work} s on / {done.rest} s off
          {done.sets > 1 ? `, ${done.sets} sets` : ''}
        </p>
        <button type="button" className={primary} onClick={() => setStage('setup')}>
          Back to the timer
        </button>
      </section>
    )
  }

  const at = positionAt(schedule, elapsed)
  const { label, token } = LOOK[at.section.phase]
  const progress = total ? Math.min(100, Math.round((elapsed / total) * 100)) : 100
  const colours = {
    '--hiit-bg': `var(--hiit-${token})`,
    '--hiit-fg': `var(--hiit-${token}-ink)`,
  } as CSSProperties
  return (
    <section
      aria-label="HIIT timer"
      style={colours}
      className="fixed inset-0 z-50 flex flex-col gap-3 overflow-hidden bg-[var(--hiit-bg)] px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))] text-[var(--hiit-fg)]"
    >
      <div className="flex items-baseline justify-between gap-2 text-lg font-bold">
        <p>
          Cycle {at.section.cycle}/{running.cycles}
          {running.sets > 1 && ` · Set ${at.section.set}/${running.sets}`}
        </p>
        <p className="num">{formatDuration(total - elapsed)} left</p>
      </div>
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center text-center">
        <p aria-live="polite" className="text-4xl font-extrabold tracking-wide uppercase">
          {label}
        </p>
        <p
          role="timer"
          aria-label="Seconds left"
          className="num text-[min(44vw,34vh)] leading-none font-extrabold [font-stretch:68%]"
        >
          {formatClock(at.remaining)}
        </p>
        <p className={'text-xl font-bold' + (paused && !confirming ? '' : ' invisible')}>Paused</p>
      </div>
      <div
        role="progressbar"
        aria-label="Workout progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        className="h-2 shrink-0 overflow-hidden rounded-full border border-[var(--hiit-fg)]"
      >
        <div className="h-full bg-[var(--hiit-fg)]" style={{ width: `${progress}%` }} />
      </div>
      {confirming ? (
        <div className="flex flex-col gap-2">
          <p className="text-center text-xl font-bold">Stop the workout?</p>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" className={outline} onClick={keepGoing}>
              Keep going
            </button>
            <button type="button" className={filled} onClick={() => end(now(), true)}>
              Stop
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-[1fr_1.4fr_1fr] gap-2">
            <button type="button" className={outline} onClick={() => jump('back')}>
              Back
            </button>
            <button type="button" className={filled} onClick={() => pause(!paused)}>
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button type="button" className={outline} onClick={() => jump('forward')}>
              Skip
            </button>
          </div>
          <button type="button" className={outline} onClick={askStop}>
            Stop
          </button>
        </div>
      )}
    </section>
  )
}
