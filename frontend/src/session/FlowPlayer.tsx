import { useEffect, useMemo, useRef, useState } from 'react'
import { type Flow, fetchSettings } from '../api'
import Figure from '../figures/Figure'
import { DEFAULT_SOUND, type Sound, playChange, unlockAudio } from '../hiit/sounds'
import { card, primary, secondary } from '../ui'
import { type Cue, at, clock, cues, jump, minutesDone, schedule, totalSeconds } from './flow'

const TICK_MS = 200
const CATCH_UP = 2 // seconds: after a longer gap (screen locked) only the latest sound plays

type Stage = 'ready' | 'running' | 'finished'

const BUZZ: Record<Cue, number | number[]> = {
  count: 60,
  switch: [200, 100, 200],
  next: 400,
  finish: [300, 100, 300],
}

/** The chosen sound for a change, and a buzz where the phone has one (ADR-0062). */
function play(sound: Sound, cue: Cue): void {
  playChange(sound, cue)
  navigator.vibrate?.(BUZZ[cue])
}

/** The mobility flow, one movement at a time (ADR-0062): a countdown per movement or side, a
 * sound and a buzz at each change, then the next starts by itself. Logs the minutes moved. */
export default function FlowPlayer({
  flow,
  busy,
  onDone,
}: {
  flow: Flow
  busy: boolean
  onDone: (minutes: number, startedAt: number) => void
}) {
  const sections = useMemo(() => schedule(flow.moves), [flow])
  const total = totalSeconds(sections)
  const [stage, setStage] = useState<Stage>('ready')
  const [paused, setPaused] = useState(false)
  const [t, setT] = useState(0) // where the flow is, in seconds
  const [moved, setMoved] = useState(0) // seconds actually moving, once finished
  const [sound, setSound] = useState<Sound>(DEFAULT_SOUND) // the person's choice, from Settings

  useEffect(() => {
    const ask = new AbortController()
    fetchSettings(ask.signal)
      .then((found) => found && setSound(found.sound))
      .catch(() => {}) // the default sound still plays
    return () => ask.abort()
  }, [])

  // Wall-clock times, not tick counts (a phone throttles timers): time run before the last
  // pause plus time since. Skip and Back move the flow without adding to the time moved.
  const banked = useRef(0)
  const since = useRef<number | null>(null)
  const offset = useRef(0)
  const last = useRef(0)
  const startedAt = useRef(0)
  const active = () =>
    (banked.current + (since.current === null ? 0 : Date.now() - since.current)) / 1000
  const position = () => Math.max(0, offset.current + active())

  const finish = () => {
    const seconds = active()
    banked.current = seconds * 1000
    since.current = null
    setMoved(seconds)
    setStage('finished')
  }

  const tick = () => {
    const now = position()
    const due = cues(sections, last.current, now)
    for (const cue of now - last.current > CATCH_UP ? due.slice(-1) : due) play(sound, cue)
    last.current = now
    setT(now)
    if (now >= total) finish()
  }
  const latestTick = useRef(tick)
  useEffect(() => {
    latestTick.current = tick
  })

  useEffect(() => {
    if (stage !== 'running' || paused) return
    const id = setInterval(() => latestTick.current(), TICK_MS)
    const onVisible = () => latestTick.current()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [stage, paused])

  // Keep the screen on while it runs, asking again when the page is visible (as the HIIT timer).
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
        // no wake lock here: the flow still runs
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

  const begin = () => {
    unlockAudio() // inside the tap: browsers only allow sound after a gesture
    startedAt.current = Date.now()
    banked.current = 0
    since.current = Date.now()
    offset.current = 0
    last.current = 0
    setT(0)
    setPaused(false)
    setStage('running')
  }

  const pause = () => {
    if (paused) since.current = Date.now()
    else {
      banked.current = active() * 1000
      since.current = null
    }
    setPaused(!paused)
  }

  const go = (direction: 'back' | 'forward') => {
    const from = position()
    const to = jump(sections, from, direction)
    offset.current += to - from
    last.current = to
    setT(to)
    if (to >= total) finish()
  }

  if (stage === 'ready')
    return (
      <section aria-label="Mobility flow" className="flex flex-col gap-3">
        <p className="m-0">
          {flow.moves.length} movements, {minutesDone(total)} minutes, standing to lying. Each one
          is timed and the next starts by itself; a sound and a buzz mark each change, so turn the
          sound up.
        </p>
        <ol className={card + ' m-0 flex flex-col gap-1 pl-8'}>
          {flow.moves.map((m) => (
            <li key={m.slug}>
              {m.name}
              <span className="text-[var(--slate)]">
                {` · ${m.seconds} s${m.per_side ? ' each side' : ''}`}
              </span>
            </li>
          ))}
        </ol>
        <p className="m-0 text-sm text-[var(--slate)]">{flow.safety}</p>
        <button type="button" className={primary} onClick={begin}>
          Start the flow
        </button>
      </section>
    )

  if (stage === 'finished') {
    const minutes = minutesDone(Math.round(moved))
    return (
      <section aria-label="Mobility flow" className="flex flex-col gap-3">
        <p className="m-0 text-2xl font-extrabold">
          {minutes > 0 ? `Flow done: ${minutes} min of moving.` : 'Nothing moved yet.'}
        </p>
        {minutes > 0 ? (
          <button
            type="button"
            className={primary}
            disabled={busy}
            onClick={() => onDone(minutes, startedAt.current)}
          >
            Log {minutes} min
          </button>
        ) : (
          <button type="button" className={primary} onClick={begin}>
            Start the flow
          </button>
        )}
      </section>
    )
  }

  const here = at(sections, t)
  const current = flow.moves[here.index]
  const next = flow.moves[here.index + 1]
  return (
    <section aria-labelledby="move" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between text-sm text-[var(--slate)]">
        <span>
          {here.index + 1} of {flow.moves.length}
        </span>
        <span>{clock(Math.ceil(total - t))} left in the flow</span>
      </div>
      <progress
        max={total}
        value={Math.min(t, total)}
        aria-label="Flow progress"
        className="w-full"
      />
      <Figure key={current.slug} slug={current.slug} name={current.name} />
      <div>
        <h2 id="move" className="m-0 text-3xl font-extrabold">
          {current.name}
        </h2>
        <p className="m-0 text-[var(--slate)]">{current.target}</p>
      </div>
      <div className={card + ' flex flex-col items-center gap-1'}>
        {here.side !== null && (
          <span className="font-bold text-[var(--bell-ink)]">
            {here.side === 1 ? 'First side' : 'Second side'}
          </span>
        )}
        <span role="timer" className="text-7xl font-extrabold tabular-nums">
          {clock(here.left)}
        </span>
        {here.side === 1 && <span className="text-sm text-[var(--slate)]">Then switch sides</span>}
        {paused && <span className="font-bold">Paused</span>}
      </div>
      {here.nextUp && next && (
        <p role="status" className="m-0 text-xl font-bold text-[var(--bell-ink)]">
          Next: {next.name}
        </p>
      )}
      <ul className="m-0 flex flex-col gap-1 pl-5">
        {current.cues.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <p className="m-0">
        <span className="font-bold">Breathing:</span> {current.breathing}
      </p>
      <p className="m-0 text-[var(--slate)]">{current.pacing}</p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="font-bold">Start</dt>
        <dd className="m-0">{current.start}</dd>
        <dt className="font-bold">End</dt>
        <dd className="m-0">{current.end}</dd>
      </dl>
      <details className={card}>
        <summary className="font-bold">Easier option</summary>
        <p className="mb-0">{current.easier}</p>
        <p className="mb-0 text-sm text-[var(--slate)]">{flow.safety}</p>
      </details>
      <div className="grid grid-cols-3 gap-2">
        <button type="button" className={secondary} onClick={() => go('back')}>
          Previous
        </button>
        <button type="button" className={secondary} aria-pressed={paused} onClick={pause}>
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button type="button" className={secondary} onClick={() => go('forward')}>
          Skip
        </button>
      </div>
      <button
        type="button"
        className="min-h-11 font-bold text-[var(--bell-ink)] underline"
        onClick={finish}
      >
        Finish early
      </button>
    </section>
  )
}
