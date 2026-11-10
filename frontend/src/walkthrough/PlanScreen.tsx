import { useEffect, useState } from 'react'
import {
  type Coverage,
  type Fitted,
  fetchWalkthrough,
  type Place,
  type Preview,
  previewWalkthrough,
  saveWalkthrough,
  type Walkthrough,
} from '../api'
import { BodyMap } from '../bodymap/BodyMap'
import { MapPlace } from '../bodymap/MapPlace'
import { AllStopSigns } from '../session/StopSigns'
import { card, primary, secondary } from '../ui'
import { COUNTS, type Draft, type Known, MINUTES, openSteps, WEEKDAYS } from './flow'
import { weekday } from './days'
import { suggestedLevel } from './level'
import { answersOf, iso, LEFT_OUT, local, pick, stepsOf } from './outcomes'
import { tight } from './choice'

/** "Monday 16 November" */
const longDay = (day: string) =>
  local(day).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
/** "Mon 16 Nov" */
const shortDay = (day: string) =>
  local(day).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const and = (names: string[]) =>
  names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`

/** Why Save was refused, in words. Consent withdrawn is said where it happens. */
const REFUSED = {
  closed:
    "You've logged a workout since this opened, so the walk-through is closed. Change your minutes, kit and the rest on Account.",
  'in-progress': 'A session is under way. Finish or end it on Today, then save.',
  stale: 'Your plan changed somewhere else since this opened. Check this one, then save again.',
}

type Shown =
  | { status: 'loading' }
  | { status: 'ready'; preview: Preview; for: string } // `for`: the choices it was made from
  | { status: 'problem'; text: string; for: string }
  | { status: 'error'; for: string }

/** One session's version, trimmed: each exercise at its step, and what the trim drops. */
function Version({ fitted, label }: { fitted: Fitted; label?: string }) {
  const kept = fitted.items.filter((i) => i.kept > 0)
  return (
    <div className="flex flex-col gap-1">
      {label && <p className="m-0 font-bold">{label}</p>}
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {kept.map((i) => (
          <li key={i.exercise}>
            {i.name}: {i.step}, {i.kept} {i.kept === 1 ? 'set' : 'sets'}
          </li>
        ))}
      </ul>
      <p className="m-0 text-sm text-[var(--slate)]">
        About {fitted.minutes} minutes.
        {fitted.dropped.length > 0 && ` Dropped to fit: ${and(fitted.dropped)}.`}
      </p>
    </div>
  )
}

/**
 * Screen 13, "Your plan" (ADR-0092): the starter the tapped days pick, each exercise at its
 * step, trimmed to the minutes and count, the week, the body map and the notes. Any open step,
 * the days, minutes and count can be changed here, and each change asks for the plan again;
 * nothing is saved until Save. The owner's try-out sees it all, without Save.
 */
export function PlanScreen({
  who,
  known,
  starters,
  revision,
  consented,
  draft,
  onChange,
  onSaved,
}: {
  who: Walkthrough['who']
  known: Known
  starters: Walkthrough['starters']
  revision: string
  consented: boolean // the answers may be sent
  draft: Draft
  onChange: (draft: Draft) => void
  onSaved: (startsOn: string) => void
}) {
  const [shown, setShown] = useState<Shown>({ status: 'loading' })
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState<string | null>(null)
  const [keep, setKeep] = useState(consented)
  const [plan, setPlan] = useState(revision)
  const [place, setPlace] = useState<Place>('home')
  const [today] = useState(() => new Date())
  const { starter, start, leftOut, body } = pick(known, starters, draft, today)
  const asked = JSON.stringify(body)

  useEffect(() => {
    const ctrl = new AbortController()
    previewWalkthrough(JSON.parse(asked) as typeof body, ctrl.signal)
      .then((found) =>
        setShown(
          'problem' in found
            ? { status: 'problem', text: found.problem, for: asked }
            : { status: 'ready', preview: found, for: asked },
        ),
      )
      .catch(() => {
        if (!ctrl.signal.aborted) setShown({ status: 'error', for: asked })
      })
    return () => ctrl.abort()
  }, [asked])

  const save = async () => {
    setBusy(true)
    setSaid(null)
    try {
      const found = await saveWalkthrough({
        ...body,
        revision: plan,
        ...(keep && { answers: answersOf(known, draft) }),
      })
      if (typeof found === 'object' && 'revision' in found) return onSaved(found.starts_on)
      if (found === 'consent_needed') {
        setKeep(false)
        setSaid(
          "Your yes to keeping your answers was taken back, so they weren't sent. Save again to make your plan without them.",
        )
      } else if (typeof found === 'object') setSaid(found.problem)
      else {
        if (found === 'stale') {
          // The revision now, so the next tap saves over it; failing that, the next tap asks again.
          const now = await fetchWalkthrough().catch(() => null)
          if (now) setPlan(now.revision)
        }
        setSaid(REFUSED[found])
      }
    } catch {
      setSaid("Couldn't save. Check your connection and try again.")
    }
    setBusy(false)
  }

  const level = suggestedLevel(draft.about)
  const days = draft.days.length
  const steps = stepsOf(known, draft)
  const mine = new Set(starter.sessions.flatMap((s) => s.items.map((i) => i.exercise)))
  const ladders = known.ladders.filter((l) => mine.has(l.slug))
  const preview = shown.status === 'ready' ? shown.preview : null // the last, while the next loads
  const waiting = shown.status === 'loading' || shown.for !== asked // the next is on its way
  const current = shown.status === 'ready' && !waiting
  const names = new Map(starter.sessions.map((s) => [s.slug, s.name]))
  const landed = new Set(preview?.week.flatMap((d) => (d.session ? [weekday(local(d.date))] : [])))
  const missed = draft.days.filter((d) => !landed.has(d)).map((d) => WEEKDAYS[d])
  const maps = preview?.coverage ?? []
  const map: Coverage | undefined = maps.find((c) => c.place === place) ?? maps[0]
  const toggle = (day: number) =>
    onChange({
      ...draft,
      days: draft.days.includes(day)
        ? draft.days.filter((d) => d !== day)
        : [...draft.days, day].sort((a, b) => a - b),
    })

  return (
    <>
      <h1 className="m-0 text-2xl">Your plan</h1>
      <p className="m-0">
        {starter.name}, from {iso(start.on) === iso(today) ? 'today' : longDay(iso(start.on))}.
        Change anything below; nothing is saved until you save it.
      </p>

      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {days === 1 && (
          <li className={card}>
            One day a week gets the 2-day plan. Each session waits for you, so you do
            {` ${starter.sessions[0].name} one week and ${starter.sessions.at(-1)?.name} the next.`}
          </li>
        )}
        {days >= 5 && (
          <li className={card}>
            {days} days a week get the 4-day plan. On the other days, some cardio: aim for 150
            minutes a week in all, and walking counts.
          </li>
        )}
        {level === 1 && (
          <li className={`${card} flex flex-col gap-2`}>
            {leftOut.length > 0
              ? 'Left out for now: the Bulgarian split squat. The other exercises come first.'
              : 'The Bulgarian split squat is back in.'}
            <button
              type="button"
              className={`${secondary} self-start`}
              onClick={() => onChange({ ...draft, putBack: leftOut.length > 0 })}
            >
              {leftOut.length > 0 ? 'Put it back' : 'Leave it out'}
            </button>
          </li>
        )}
        {(draft.about.age === '65-74' || draft.about.age === '75+') && (
          <li className={card}>
            Worth doing most days too: a balance and sit-to-stand snack. Stand on one leg holding a
            counter, then stand up from a chair and sit down a few times. It isn't tracked here.
          </li>
        )}
      </ul>

      <h2 className="m-0 text-xl">Your week</h2>
      {preview && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {preview.week.map((d) => (
            <li key={d.date} className="flex justify-between gap-3">
              <span>{shortDay(d.date)}</span>
              <span className={d.session ? 'font-bold' : 'text-[var(--slate)]'}>
                {d.session ? names.get(d.session) : 'Rest'}
              </span>
            </li>
          ))}
        </ul>
      )}
      {/* Not while the next plan loads (the week is the last one's), and not at 5 days or more,
          where the cardio note says what the other days are for. */}
      {preview && !waiting && days < 5 && missed.length > 0 && (
        <p className="m-0">
          {and(missed)} {missed.length === 1 ? "doesn't" : "don't"} get a session, to keep the rest
          days between them.
        </p>
      )}
      <div role="group" aria-label="Your days" className="grid grid-cols-7 gap-1">
        {WEEKDAYS.map((name, day) => (
          <button
            key={name}
            type="button"
            aria-label={name}
            aria-pressed={draft.days.includes(day)}
            className={tight(draft.days.includes(day))}
            onClick={() => toggle(day)}
          >
            {name.slice(0, 2)}
          </button>
        ))}
      </div>

      {(
        [
          ['Minutes per session', MINUTES, 'minutes'],
          ['Exercises per session', COUNTS, 'count'],
        ] as const
      ).map(([title, options, key]) => (
        <div key={key} role="group" aria-label={title} className="flex flex-col gap-2">
          <h2 className="m-0 text-xl">{title}</h2>
          <div className="grid grid-cols-2 gap-2">
            {options.map((o) => (
              <button
                key={String(o.value)}
                type="button"
                aria-pressed={draft[key] === o.value}
                className={tight(draft[key] === o.value)}
                onClick={() => onChange({ ...draft, [key]: o.value })}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      {waiting && (
        <p className="status" role="status">
          Making your plan…
        </p>
      )}
      {shown.status === 'problem' && (
        <p className="status-error m-0" role="alert">
          {shown.text}
        </p>
      )}
      {shown.status === 'error' && (
        <p className="status-error m-0" role="alert">
          Couldn't make your plan. Check your connection, then change anything to try again.
        </p>
      )}

      {preview && (
        <>
          <h2 className="m-0 text-xl">The sessions</h2>
          {preview.sessions.map((s) => (
            <section key={s.slug} className={`${card} flex flex-col gap-2`}>
              <h3 className="m-0 text-lg">
                {s.name} <span className="font-normal">· first on {shortDay(s.on)}</span>
              </h3>
              {draft.places === 'gym' ? (
                <Version fitted={s.gym ?? s.home} />
              ) : (
                <>
                  <Version fitted={s.home} label={s.gym ? 'At home' : undefined} />
                  {s.gym && <Version fitted={s.gym} label="At the gym" />}
                </>
              )}
            </section>
          ))}
        </>
      )}

      <h2 className="m-0 text-xl">Where each exercise starts</h2>
      <p className="m-0 text-[var(--slate)]">
        From your answers. Pick another step if you like: only the ones open to you are listed.
      </p>
      {ladders.map((l) => (
        <label key={l.slug} className="flex flex-col gap-1 font-bold">
          {l.name}
          {l.slug === LEFT_OUT && leftOut.length > 0 && (
            <span className="font-normal text-[var(--slate)]">Left out for now</span>
          )}
          <select
            className="min-h-11 rounded-xl border-2 border-[var(--line)] px-3 font-normal"
            value={steps[l.slug]}
            onChange={(e) =>
              onChange({ ...draft, chosen: { ...draft.chosen, [l.slug]: Number(e.target.value) } })
            }
          >
            {openSteps(l, draft).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      ))}

      {map && (
        <>
          <h2 className="m-0 text-xl">What the week gives each muscle</h2>
          {maps.length > 1 && <MapPlace place={map.place} onChoose={setPlace} />}
          <BodyMap state={{ status: 'ready', coverage: map }} />
        </>
      )}

      {said && (
        <p className="status-error m-0" role="alert">
          {said}
        </p>
      )}
      {who === 'owner_try_out' ? (
        <p className={`${card} m-0 font-bold`}>This is a try-out: your plan won't change.</p>
      ) : (
        <button
          type="button"
          className={primary}
          disabled={busy || !current}
          onClick={() => void save()}
        >
          {busy ? 'Saving…' : 'Save my plan'}
        </button>
      )}
    </>
  )
}

/** Screen 14, "Done": the first session's day, then Today and the stop signs. */
export function DoneScreen({ startsOn }: { startsOn: string }) {
  const [today] = useState(() => startsOn === iso(new Date()))
  return (
    <>
      <h1 className="m-0 text-2xl">
        {today ? 'Your first session is today' : `Your first session is on ${longDay(startsOn)}`}
      </h1>
      <p className="m-0">
        Your plan is saved. Change your minutes, kit and the rest on Account, and each exercise's
        step on Plan.
      </p>
      <a href="/session" className={primary + ' flex items-center justify-center no-underline'}>
        Go to today
      </a>
      <div className={card}>
        <p className="m-0 mb-2">Before your first session, read the stop signs.</p>
        <AllStopSigns />
      </div>
    </>
  )
}
