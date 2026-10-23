import { useEffect, useState, type KeyboardEvent } from 'react'
import { fetchDay, type DayLog, type LoggedWorkout } from '../api'
import { day as dayName } from '../home/logic'
import { card, secondary } from '../ui'
import HabitsCard from './Habits'
import { details, shift } from './days'

type Exercise = LoggedWorkout['exercises'][number]
type LoggedSet = Exercise['sets'][number]

function heading(log: DayLog): string {
  if (log.day === log.today) return 'Today'
  if (log.day === shift(log.today, -1)) return 'Yesterday'
  return dayName(log.day)
}

const units: Record<string, string> = { reps: '', seconds: ' s', minutes: ' min' }

function one(value: number, unit: string): string {
  return `${value}${units[unit] ?? ''}`
}

/** "12" or "12/11" (left/right), with the unit for timed sets. */
function setText(set: LoggedSet, unit: string): string {
  if (set.right === null || set.right === undefined) return one(set.left, unit)
  return `${one(set.left, unit)}/${one(set.right, unit)}`
}

function title(workout: LoggedWorkout): string {
  if (workout.status === 'rest') return `${workout.name}: rest day`
  if (workout.status === 'skipped') return `${workout.name}: skipped`
  if (!workout.planned && workout.activity) return `Extra: ${workout.activity}`
  return workout.name
}

function Workout({ workout }: { workout: LoggedWorkout }) {
  const band = workout.band
  return (
    <li className="flex flex-col gap-1">
      <h3 className="m-0 text-base font-bold">{title(workout)}</h3>
      {band && (
        <p className="m-0 text-sm text-[var(--slate)]">
          Band: {band.minutes} min
          {band.avg_hr ? ` · avg ${band.avg_hr} bpm` : ''}
          {band.max_hr ? ` · max ${band.max_hr}` : ''}
        </p>
      )}
      {workout.cardio && (
        <p className="m-0 text-sm text-[var(--slate)]">{details(workout.cardio)}</p>
      )}
      {workout.exercises.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
          {workout.exercises.map((exercise, n) => (
            <li key={`${exercise.name}-${n}`}>
              <span className="font-bold">{exercise.name}</span>
              {exercise.step && (
                <span className="text-[var(--slate)]"> ({exercise.step})</span>
              )}: {exercise.sets.map((set) => setText(set, exercise.unit)).join(' · ')}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/** What was logged on a day, today or earlier, and that day's habits (ADR-0068). ‹ and ›
 * step a day back or forward, never past today or before the first day; the date goes back to
 * today. An earlier day's log is read-only, but its habits can still be ticked. The card shows
 * once loaded; until then, or when it can't load, today's habits still show. ``refresh``
 * changes after a log saved elsewhere. */
export default function DayCard({ refresh = 0 }: { refresh?: number }) {
  const [shown, setShown] = useState<string | undefined>(undefined) // none: today
  const [log, setLog] = useState<DayLog | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchDay(shown, controller.signal).then(
      (found) => {
        setLog(found)
        setFailed(false)
      },
      () => {
        if (!controller.signal.aborted) setFailed(true)
      },
    )
    return () => controller.abort()
  }, [shown, refresh])

  const note = failed && (
    <p role="status" className="status">
      Couldn't reach the coach. Check your connection and try again.
    </p>
  )
  // Today's habits stay on the page whatever the day card does (review of #298).
  if (log === null)
    return (
      <>
        {note}
        <HabitsCard />
      </>
    )
  const isToday = log.day === log.today
  const back = log.day > log.first ? shift(log.day, -1) : null
  const forward = isToday ? null : shift(log.day, 1)
  const go = (to: string | null) => {
    if (to === null) return
    setShown(to === log.today ? undefined : to)
  }
  const keys = (event: KeyboardEvent) => {
    if (event.key === 'ArrowLeft') go(back)
    if (event.key === 'ArrowRight') go(forward)
  }
  const name = heading(log)

  return (
    <>
      <section aria-labelledby="day" className={card + ' flex flex-col gap-3'}>
        <div className="flex items-center justify-between gap-2" onKeyDown={keys}>
          <button
            type="button"
            className={secondary}
            aria-label="Previous day"
            disabled={back === null}
            onClick={() => go(back)}
          >
            ‹
          </button>
          <h2 id="day" className="m-0 text-lg font-bold">
            <button
              type="button"
              className="bg-transparent font-bold"
              aria-label={isToday ? 'Logged today' : `Logged ${name}: back to today`}
              onClick={() => setShown(undefined)}
            >
              {isToday ? 'Logged today' : name}
            </button>
          </h2>
          <button
            type="button"
            className={secondary}
            aria-label="Next day"
            disabled={forward === null}
            onClick={() => go(forward)}
          >
            ›
          </button>
        </div>
        {log.workouts.length === 0 ? (
          <p className="m-0 text-sm text-[var(--slate)]">Nothing logged.</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {log.workouts.map((workout) => (
              <Workout key={workout.workout_id} workout={workout} />
            ))}
          </ul>
        )}
        {note}
      </section>
      <HabitsCard
        key={log.day} // another day starts afresh: never tick the last one's
        day={isToday ? undefined : log.day}
        label={isToday ? 'today' : `on ${name}`}
      />
    </>
  )
}
