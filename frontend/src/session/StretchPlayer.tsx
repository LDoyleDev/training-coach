import { useEffect, useMemo, useRef, useState } from 'react'
import { type Routine, fetchSettings } from '../api'
import Figure from '../figures/Figure'
import { type Sound, playChange } from '../hiit/sounds'
import { card, primary, secondary } from '../ui'
import {
  type Cue,
  at,
  clock,
  duration,
  jump,
  minutesDone,
  stretchCues,
  stretchSchedule,
  totalSeconds,
} from './flow'
import { useGuidedClock } from './guidedClock'

const BUZZ: Record<Cue, number | number[]> = {
  count: 60,
  switch: [200, 100, 200],
  next: 400,
  finish: [300, 100, 300],
}

const PHASE = { position: 'Get into position', hold: 'Hold', release: 'Let go' } as const

/** Guided stretching (ADR-0032 addendum): the overview, then each stretch timed with a bell at
 * every change, so the phone can sit on the floor. 15 s to get into position before each
 * stretch and side, the hold counted down, 5 s to let go between rounds. At the end it logs
 * the minutes done by itself; stopped early, the person logs what was done or nothing. */
export default function StretchPlayer({
  routine,
  busy,
  onLog,
  onDiscard,
}: {
  routine: Routine
  busy: boolean
  onLog: (minutes: number) => void
  onDiscard: () => void
}) {
  const { parts, stretches } = useMemo(
    () =>
      stretchSchedule(routine.steps, {
        hold: routine.hold_seconds,
        position: routine.position_seconds,
        release: routine.release_seconds,
      }),
    [routine],
  )
  const total = totalSeconds(parts)
  const [sound, setSound] = useState<Sound>('chime') // the person's choice, from Settings

  useEffect(() => {
    const ask = new AbortController()
    fetchSettings(ask.signal)
      .then((found) => found && setSound(found.sound))
      .catch(() => {}) // the default sound still plays
    return () => ask.abort()
  }, [])

  const clockState = useGuidedClock(
    total,
    (from, to) => stretchCues(parts, from, to),
    (cue) => {
      playChange(sound, cue)
      navigator.vibrate?.(BUZZ[cue])
    },
  )
  const { stage, paused, t, ran, begin, pause, jumpTo, finish, position } = clockState

  // Whole minutes done, never more than chosen (Back can repeat a stretch).
  const minutes = Math.min(minutesDone(Math.round(ran)), routine.minutes)
  const completed = stage === 'finished' && t >= total

  // Finished on its own: log it, once. A failed log leaves the Log button to try again.
  const logged = useRef(false)
  useEffect(() => {
    if (completed && minutes > 0 && !logged.current) {
      logged.current = true
      onLog(minutes)
    }
  }, [completed, minutes, onLog])

  if (stage === 'ready')
    return (
      <div className="flex flex-col gap-3">
        <p className="m-0">
          {routine.steps.length} stretches, {duration(total)} in all, the gaps included. Each one
          starts with {routine.position_seconds} s to get into position. A bell rings at every
          change (hold, let go, switch sides, next stretch), so turn the sound up and follow the
          bells.
        </p>
        <ol className="m-0 flex list-decimal flex-col gap-2 pl-5">
          {routine.steps.map((step) => (
            <li key={step.slug}>
              <span className="font-bold">{step.name}</span>
              <span className="whitespace-nowrap text-[var(--slate)]">
                {` · ${step.rounds} × ${routine.hold_seconds} s${step.per_side ? ' each side' : ''}`}
              </span>
              <p className="m-0 text-[var(--slate)]">{step.cue}</p>
            </li>
          ))}
        </ol>
        <p className="m-0 text-sm text-[var(--slate)]">
          Hold at a gentle pull, 3-4 out of 10, never pain. Breathe slowly.
        </p>
        <button type="button" className={primary} onClick={begin}>
          Start stretching
        </button>
        <p className="m-0 text-sm text-[var(--slate)]">
          Stretching without the phone? Log the {routine.minutes} min when you're done.
        </p>
        <button
          type="button"
          className={secondary}
          disabled={busy}
          onClick={() => onLog(routine.minutes)}
        >
          Done stretching
        </button>
      </div>
    )

  if (stage === 'finished')
    return (
      <div className="flex flex-col gap-3">
        <p className="m-0 text-2xl font-extrabold">
          {minutes > 0 ? `Stretching done: ${minutes} min.` : 'Nothing stretched yet.'}
        </p>
        {!completed && minutes > 0 && (
          <p className="m-0">Stopped early: log the {minutes} min you did, or nothing.</p>
        )}
        {minutes > 0 ? (
          <button type="button" className={primary} disabled={busy} onClick={() => onLog(minutes)}>
            Log {minutes} min
          </button>
        ) : (
          <button type="button" className={primary} onClick={begin}>
            Start stretching
          </button>
        )}
        {!completed && (
          <button type="button" className={secondary} disabled={busy} onClick={onDiscard}>
            Don't log it
          </button>
        )}
      </div>
    )

  const now = at(parts, t)
  const part = parts[now.index]
  const step = routine.steps[part.stretch]
  const next = routine.steps[part.stretch + 1]
  const nextUp = at(stretches, t).nextUp // the last seconds of a stretch with one after it
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between text-sm text-[var(--slate)]">
        <span>
          {part.stretch + 1} of {routine.steps.length}
        </span>
        <span>{clock(Math.ceil(total - t))} left</span>
      </div>
      <progress
        max={total}
        value={Math.min(t, total)}
        aria-label="Stretching progress"
        className="w-full"
      />
      <h3 className="m-0 text-3xl font-extrabold">{step.name}</h3>
      {part.kind === 'position' && <Figure key={step.slug} slug={step.slug} name={step.name} />}
      <div className={card + ' flex flex-col items-center gap-1'}>
        <span className="text-xl font-bold text-[var(--bell-ink)]">
          {PHASE[part.kind]}
          {part.side !== null && (part.side === 1 ? ', first side' : ', second side')}
        </span>
        <span role="timer" className="text-7xl font-extrabold tabular-nums">
          {clock(now.left)}
        </span>
        <span className="text-sm text-[var(--slate)]">
          {part.kind === 'position'
            ? `Then hold ${routine.hold_seconds} s`
            : `Round ${part.round} of ${step.rounds}`}
        </span>
        {paused && <span className="font-bold">Paused</span>}
      </div>
      {nextUp && next && (
        <p role="status" className="m-0 text-xl font-bold text-[var(--bell-ink)]">
          Next: {next.name}
        </p>
      )}
      <p className="m-0">{step.cue}</p>
      <div className="grid grid-cols-3 gap-2">
        <button
          type="button"
          className={secondary}
          onClick={() => jumpTo(jump(stretches, position(), 'back'))}
        >
          Previous
        </button>
        <button type="button" className={secondary} aria-pressed={paused} onClick={pause}>
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button
          type="button"
          className={secondary}
          onClick={() => jumpTo(jump(stretches, position(), 'forward'))}
        >
          Skip
        </button>
      </div>
      <button
        type="button"
        className="min-h-11 font-bold text-[var(--bell-ink)] underline"
        onClick={finish}
      >
        Stop early
      </button>
    </div>
  )
}
