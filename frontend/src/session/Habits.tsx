import { useEffect, useState } from 'react'
import { fetchHabits, markHabit, SignedOutError, type HabitKey, type Habits } from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { card } from '../ui'

const toggle =
  'flex min-h-12 w-full items-center gap-3 rounded-xl border-2 px-3 text-left font-bold disabled:opacity-60'
const on = ' border-[var(--ink)] bg-[var(--ink)] text-[var(--chalk)]'
const off = ' border-[var(--ink)] text-[var(--ink)]'

/** Today's habits (ux-flow-plan C5): one tap ticks, another unticks, the same check-offs as
 * the bot's buttons. Shows nothing until loaded, or when signed out or unreachable: it is an
 * extra on the page, never in the way of the session. */
export default function HabitsCard() {
  const [habits, setHabits] = useState<Habits | null>(null)
  const [busy, setBusy] = useState<HabitKey | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchHabits(controller.signal).then(setHabits, () => {}) // quiet: see above
    return () => controller.abort()
  }, [])

  if (habits === null) return null

  const tap = async (habit: HabitKey, done: boolean) => {
    setBusy(habit)
    setNote(null)
    setSignedOut(false) // a retry after signing in again
    try {
      setHabits(await markHabit(habit, done))
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't reach the coach. Check your connection and try again.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <section aria-labelledby="habits" className={card + ' flex flex-col gap-3'}>
      <h2 id="habits" className="text-lg font-bold">
        Habits today
      </h2>
      <p className="m-0 text-sm text-[var(--slate)]">
        Tap each one you did. Days this week: {habits.week_days} so far.
      </p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {habits.habits.map((habit) => (
          <li key={habit.key} className="flex flex-col gap-1">
            <button
              type="button"
              aria-pressed={habit.done}
              className={toggle + (habit.done ? on : off)}
              disabled={busy !== null}
              onClick={() => tap(habit.key, !habit.done)}
            >
              <span aria-hidden="true" className="w-5 text-center">
                {habit.done ? '✓' : '○'}
              </span>
              <span className="flex-1">{habit.label}</span>
              <span className="text-sm font-normal">
                {habit.week_done} of {habits.week_days}
              </span>
            </button>
            <details className="text-sm text-[var(--slate)]">
              <summary className="cursor-pointer">What counts</summary>
              <p className="m-0 mt-1">{habit.hint}</p>
            </details>
          </li>
        ))}
      </ul>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
    </section>
  )
}
