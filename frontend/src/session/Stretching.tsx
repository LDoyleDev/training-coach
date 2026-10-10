import { useState } from 'react'
import { fetchStretching, logStretching, type Routine } from '../api'

const CHOICES = [10, 20, 30] // minutes, as the bot offers (ADR-0032)

const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'
const choice =
  'min-h-11 flex-1 rounded-xl border-2 border-[var(--ink)] px-4 font-bold text-[var(--ink)] disabled:opacity-60'
const primary =
  'min-h-14 w-full rounded-2xl bg-[var(--bell-ink)] px-4 text-lg font-bold text-white disabled:opacity-60'

type State =
  | { status: 'choose' }
  | { status: 'routine'; routine: Routine }
  | { status: 'done'; minutes: number; logged: boolean }

/** After a saved resistance session: pick a time, follow the stretches, log them (#135). */
export default function Stretching({ workoutId }: { workoutId: number }) {
  const [state, setState] = useState<State>({ status: 'choose' })
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setNote(null)
    try {
      await work()
    } catch {
      setNote("Couldn't reach the coach. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const choose = (minutes: number) =>
    run(async () => {
      const routine = await fetchStretching(workoutId, minutes)
      if (routine === null) setNote('No stretching for this workout.')
      else setState({ status: 'routine', routine })
    })

  const done = (minutes: number) =>
    run(async () => {
      setState({ status: 'done', minutes, logged: await logStretching(workoutId, minutes) })
    })

  return (
    <section aria-labelledby="stretching" className={card + ' flex flex-col gap-3'}>
      <h2 id="stretching" className="text-lg font-bold">
        Stretching
      </h2>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}

      {state.status === 'choose' && (
        <>
          <p className="text-[var(--slate)]">For the muscles you just worked. How long?</p>
          <div className="flex gap-3">
            {CHOICES.map((minutes) => (
              <button
                key={minutes}
                type="button"
                className={choice}
                disabled={busy}
                onClick={() => choose(minutes)}
              >
                {minutes} min
              </button>
            ))}
          </div>
        </>
      )}

      {state.status === 'routine' && (
        <>
          <p className="text-[var(--slate)]">
            Hold each stretch {state.routine.hold_seconds} s at a gentle pull, 3-4 out of 10, never
            pain.
          </p>
          <ol className="flex list-decimal flex-col gap-2 pl-5">
            {state.routine.steps.map((step) => (
              <li key={step.name}>
                <span className="font-bold">{step.name}</span>: {step.rounds} rounds of{' '}
                {state.routine.hold_seconds} s{step.per_side ? ' each side' : ''}
                <p className="text-[var(--slate)]">{step.cue}</p>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className={primary}
            disabled={busy}
            onClick={() => done(state.routine.minutes)}
          >
            Done stretching
          </button>
        </>
      )}

      {state.status === 'done' && (
        <p>
          {state.logged
            ? `Logged ${state.minutes} min of stretching.`
            : 'Stretching was already logged for this session.'}
        </p>
      )}
    </section>
  )
}
