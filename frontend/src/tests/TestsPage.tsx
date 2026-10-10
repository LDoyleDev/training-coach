import AppShell from '../components/AppShell'
import { useEffect, useState } from 'react'
import {
  fetchTests,
  saveTestDay,
  type FitnessTest,
  type TestDay,
  type TestDayDue,
  type TestResult,
} from '../api'
import {
  change,
  compare,
  conditionsChanged,
  newToken,
  previous,
  sideText,
  stepOf,
  steps,
  timeOfDay,
  toSave,
  unitText,
  type Step,
} from './logic'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; tests: FitnessTest[]; days: TestDay[]; due: TestDayDue | null }

type When = 'morning' | 'midday' | 'afternoon' | 'evening'
type Stage = 'list' | 'conditions' | 'test' | 'check' | 'saved'

const card = 'rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-4'
const primary =
  'min-h-14 w-full rounded-2xl bg-[var(--bell-ink)] px-4 text-lg font-bold text-white disabled:opacity-60'
const secondary =
  'min-h-11 rounded-xl border-2 border-[var(--ink)] px-4 font-bold text-[var(--ink)]'
const toggle = (on: boolean) =>
  'min-h-11 flex-1 rounded-xl border-2 px-3 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-white'
    : 'border-[var(--ink)] text-[var(--ink)]')

const TIMES: When[] = ['morning', 'midday', 'afternoon', 'evening']

/**
 * /tests: baseline tests and retests (2-A, ADR-0037). The conditions first, then one test (or
 * side) per screen; nothing is saved until Save (ADR-0007).
 */
export default function TestsPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [stage, setStage] = useState<Stage>('list')
  const [day, setDay] = useState(1)
  const [when, setWhen] = useState<When>(() => timeOfDay(new Date().getHours()))
  const [fed, setFed] = useState(true)
  const [slept, setSlept] = useState(true)
  const [position, setPosition] = useState(0)
  const [results, setResults] = useState<TestResult[]>([])
  const [value, setValue] = useState('')
  const [token, setToken] = useState(newToken)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [savedId, setSavedId] = useState<number | null>(null)

  const load = () =>
    fetchTests()
      .then((found) =>
        setLoaded(found === null ? { status: 'signed-out' } : { status: 'ready', ...found }),
      )
      .catch(() => setLoaded({ status: 'error' }))
  useEffect(() => {
    void load()
  }, [])

  if (loaded.status !== 'ready') return <AppShell>{<Status loaded={loaded} />}</AppShell>
  const { tests, days, due } = loaded
  const list = steps(tests, day)
  const step: Step | undefined = list[position]

  const show = (index: number, kept: TestResult[] = results) => {
    setPosition(index)
    const next = list[index]
    if (!next) return setStage('check')
    const done = kept.find((r) => r.test === next.test.slug && r.side === next.side)
    const last = previous(days, next.test.slug, next.side)
    setValue(String(done?.value ?? last ?? ''))
    setStage('test')
  }

  const start = (which: number) => {
    setDay(which)
    setResults([])
    setToken(newToken())
    setNote(null)
    setStage('conditions')
  }

  const record = (entry: TestResult | null) => {
    if (!step) return
    const others = results.filter((r) => !(r.test === step.test.slug && r.side === step.side))
    const kept = entry ? [...others, entry] : others
    setResults(kept)
    show(position + 1, kept)
  }

  const number = Number(value)
  const valid =
    value.trim() !== '' &&
    Number.isInteger(number) &&
    step !== undefined &&
    number >= step.test.low &&
    number <= step.test.high

  const save = async () => {
    setBusy(true)
    setNote(null)
    try {
      const answer = await saveTestDay({
        day,
        time_of_day: when,
        fed,
        slept_well: slept,
        results: toSave(tests, results),
        token,
      })
      if (typeof answer === 'number') {
        setSavedId(answer)
        setStage('saved')
        void load()
      } else setNote(answer)
    } catch {
      setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const saving = toSave(tests, results)
  const nameOf = (slug: string) => tests.find((t) => t.slug === slug)

  return (
    <AppShell>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}

      {stage === 'list' && (
        <section aria-labelledby="tests" className="flex flex-col gap-4">
          <h1 id="tests" className="text-3xl font-extrabold">
            Baseline tests
          </h1>
          <p className="text-[var(--slate)]">
            Two days of tests. Retest under the same conditions to see what changed.
          </p>
          {due && (
            <div className={card + ' flex flex-col gap-3 border-[var(--bell-ink)]'}>
              <p className="font-bold">Due today: {due.name}</p>
              <p className="text-[var(--slate)]">Your session waits until they're done.</p>
              <button type="button" className={primary} onClick={() => start(due.day)}>
                Start {due.name.toLowerCase()}
              </button>
            </div>
          )}
          {[1, 2].map((which) => (
            <div key={which} className={card + ' flex flex-col gap-3'}>
              <h2 className="font-bold">Day {which}</h2>
              <p className="text-[var(--slate)]">
                {tests
                  .filter((t) => t.day === which)
                  .map((t) => t.name)
                  .join(' · ')}
              </p>
              <button type="button" className={primary} onClick={() => start(which)}>
                Start day {which} tests
              </button>
            </div>
          ))}
          {days.length > 0 && (
            <>
              <h2 className="text-lg font-bold">Done so far</h2>
              {days.map((d, index) => (
                <DayResults key={d.id} tests={tests} days={days} index={index} />
              ))}
            </>
          )}
        </section>
      )}

      {stage === 'conditions' && (
        <section aria-labelledby="conditions" className="flex flex-col gap-4">
          <h1 id="conditions" className="text-3xl font-extrabold">
            Day {day}: conditions
          </h1>
          <p className="text-[var(--slate)]">
            Kept next to the results, so a retest can match them.
          </p>
          <fieldset className="flex flex-col gap-2">
            <legend className="font-bold">Time of day</legend>
            <div className="flex flex-wrap gap-2">
              {TIMES.map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={when === t}
                  className={toggle(when === t)}
                  onClick={() => setWhen(t)}
                >
                  {t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="font-bold">Eaten in the last 3 hours?</legend>
            <div className="flex gap-2">
              <button
                type="button"
                aria-pressed={fed}
                className={toggle(fed)}
                onClick={() => setFed(true)}
              >
                Fed
              </button>
              <button
                type="button"
                aria-pressed={!fed}
                className={toggle(!fed)}
                onClick={() => setFed(false)}
              >
                Fasted
              </button>
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="font-bold">Slept well last night?</legend>
            <div className="flex gap-2">
              <button
                type="button"
                aria-pressed={slept}
                className={toggle(slept)}
                onClick={() => setSlept(true)}
              >
                Yes
              </button>
              <button
                type="button"
                aria-pressed={!slept}
                className={toggle(!slept)}
                onClick={() => setSlept(false)}
              >
                No
              </button>
            </div>
          </fieldset>
          <button type="button" className={primary} onClick={() => show(0)}>
            Start the tests
          </button>
          <button type="button" className={secondary} onClick={() => setStage('list')}>
            Leave
          </button>
        </section>
      )}

      {stage === 'test' && step && (
        <section aria-labelledby="test" className="flex flex-col gap-4">
          <p className="text-sm font-bold tracking-wide text-[var(--bell-ink)]">
            DAY {day} · TEST {position + 1} OF {list.length}
          </p>
          <h1 id="test" className="text-4xl font-extrabold">
            {step.test.name}
            {step.side !== 'both' ? `: ${sideText(step.side)}` : ''}
          </h1>
          <p className={card}>{step.test.cue}</p>
          <label className="flex flex-col gap-2 font-bold">
            Result ({step.test.unit})
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label={`${stepOf(step.test)} less`}
                className={secondary + ' min-w-14 text-2xl'}
                onClick={() =>
                  setValue(
                    String(Math.max(step.test.low, (Number(value) || 0) - stepOf(step.test))),
                  )
                }
              >
                −
              </button>
              <input
                inputMode="numeric"
                className="min-h-14 w-full rounded-xl border-2 border-[var(--ink)] text-center text-3xl font-extrabold"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
              <button
                type="button"
                aria-label={`${stepOf(step.test)} more`}
                className={secondary + ' min-w-14 text-2xl'}
                onClick={() =>
                  setValue(
                    String(Math.min(step.test.high, (Number(value) || 0) + stepOf(step.test))),
                  )
                }
              >
                +
              </button>
            </div>
          </label>
          {previous(days, step.test.slug, step.side) !== null && (
            <p className="text-[var(--slate)]">
              Last time: {unitText(step.test, previous(days, step.test.slug, step.side) ?? 0)}
            </p>
          )}
          {!valid && value.trim() !== '' && (
            <p role="alert" className="status status-error">
              A whole number from {step.test.low} to {step.test.high}.
            </p>
          )}
          <button
            type="button"
            className={primary}
            disabled={!valid}
            onClick={() => record({ test: step.test.slug, side: step.side, value: number })}
          >
            Next
          </button>
          <div className="flex gap-3">
            <button
              type="button"
              className={secondary + ' flex-1'}
              onClick={() => (position === 0 ? setStage('conditions') : show(position - 1))}
            >
              Back
            </button>
            <button type="button" className={secondary + ' flex-1'} onClick={() => record(null)}>
              Skip
            </button>
          </div>
        </section>
      )}

      {stage === 'check' && (
        <section aria-labelledby="check" className="flex flex-col gap-4">
          <h1 id="check" className="text-3xl font-extrabold">
            Check and save
          </h1>
          <p className="text-[var(--slate)]">
            Day {day} · {when}, {fed ? 'fed' : 'fasted'}, {slept ? 'slept well' : 'slept badly'}
          </p>
          {saving.length === 0 ? (
            <p className={card}>Every test was skipped, so there's nothing to save.</p>
          ) : (
            <ul className={card}>
              {saving.map((r) => {
                const test = nameOf(r.test)
                return (
                  <li key={`${r.test}:${r.side}`}>
                    {test?.name ?? r.test}
                    {r.side !== 'both' ? ` (${sideText(r.side)})` : ''}:{' '}
                    {test ? unitText(test, r.value) : r.value}
                  </li>
                )
              })}
            </ul>
          )}
          {saving.length < results.length && (
            <p className="text-[var(--slate)]">
              A test done on one side only isn't saved: do both sides, or skip it.
            </p>
          )}
          <button
            type="button"
            className={primary}
            disabled={busy || saving.length === 0}
            onClick={save}
          >
            Save
          </button>
          <button type="button" className={secondary} onClick={() => show(list.length - 1)}>
            Back
          </button>
        </section>
      )}

      {stage === 'saved' && (
        <section aria-labelledby="saved" className="flex flex-col gap-4">
          <h1 id="saved" className="text-3xl font-extrabold">
            Day {day} tests saved
          </h1>
          {days.some((d) => d.id === savedId) && (
            <DayResults tests={tests} days={days} index={days.findIndex((d) => d.id === savedId)} />
          )}
          <button type="button" className={primary} onClick={() => setStage('list')}>
            Done
          </button>
        </section>
      )}
    </AppShell>
  )
}

function Status({ loaded }: { loaded: Exclude<Loaded, { status: 'ready' }> }) {
  if (loaded.status === 'loading')
    return (
      <p className="status" role="status">
        Loading the tests…
      </p>
    )
  if (loaded.status === 'signed-out')
    return (
      <p className="status">
        Sign in to see your tests. <a href="/signin">Sign in</a>
      </p>
    )
  return (
    <p className="status status-error" role="alert">
      Couldn't load the tests. Check your connection and reload the page.
    </p>
  )
}

/** One test day: its conditions, a note when they differ from last time, and each result
 * next to the first baseline and the previous test (#96). */
function DayResults({
  tests,
  days,
  index,
}: {
  tests: FitnessTest[]
  days: TestDay[]
  index: number
}) {
  const d = days[index]
  const changed = conditionsChanged(days, index)
  return (
    <div className={card + ' flex flex-col gap-2'}>
      <p className="font-bold">
        {d.on} · Day {d.day} · {d.time_of_day}, {d.fed ? 'fed' : 'fasted'},{' '}
        {d.slept_well ? 'slept well' : 'slept badly'}
      </p>
      {changed.length > 0 && (
        <p className="text-[var(--slate)]">Not quite comparable: {changed.join('; ')}.</p>
      )}
      <ul>
        {compare(days, index).map((r) => {
          const test = tests.find((t) => t.slug === r.test)
          const show = (v: number) => (test ? unitText(test, v) : String(v))
          return (
            <li key={`${r.test}:${r.side}`}>
              {test?.name ?? r.test}
              {r.side !== 'both' ? ` (${sideText(r.side)})` : ''}: {show(r.value)}
              {r.baseline !== null &&
                ` · baseline ${show(r.baseline)} (${change(r.value, r.baseline)})`}
              {r.last !== null && ` · last ${show(r.last)} (${change(r.value, r.last)})`}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
