import { useCallback, useEffect, useRef, useState } from 'react'
import {
  answeredReadiness,
  type Equipment,
  fetchEquipment,
  fetchSettings,
  fetchWalkthrough,
  type Walkthrough,
} from '../api'
import { bodyFromItem } from '../account/kit'
import Residence from '../account/Residence'
import { RetryCard, SignInCard } from '../components/StateCards'
import { ConsentCard } from '../consent/Consented'
import { QUESTIONS, VERSION } from '../readiness/questions'
import { card, primary, secondary } from '../ui'
import {
  after,
  CHOICES,
  COUNTS,
  type Draft,
  type Known,
  LAST,
  ladderAt,
  MINUTES,
  numberOf,
  SAFETY,
  WALKED_FROM,
} from './flow'
import { NOTHING_ANSWERED } from './level'
import { DoneScreen, PlanScreen } from './PlanScreen'
import {
  AvoidScreen,
  ChoiceScreen,
  DaysScreen,
  KitScreen,
  LadderScreen,
  PlacesScreen,
  SafetyNote,
  SafetyQuestion,
  Welcome,
} from './Screens'

interface Ready {
  who: Walkthrough['who'] // the owner's is a try-out: nothing changes his plan (ADR-0092)
  known: Known
  starters: Walkthrough['starters']
  revision: string // the plan's as it loaded: Save sends it back
  consented: boolean // the walkthrough category was open as it loaded
  answeredAt: string | null // when the health questions were last answered
  kinds: Equipment['kinds']
  draft: Draft
}

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'ready'; ready: Ready }

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

async function load(signal: AbortSignal): Promise<Ready | null> {
  const [walkthrough, settings, equipment] = await Promise.all([
    fetchWalkthrough(signal),
    fetchSettings(signal),
    fetchEquipment(signal),
  ])
  if (!walkthrough || !settings || !equipment) return null
  const { readiness } = walkthrough
  return {
    who: walkthrough.who,
    known: {
      consent: !walkthrough.consent_open,
      residence: !walkthrough.country,
      safety: readiness.due,
      ladders: walkthrough.ladders,
    },
    starters: walkthrough.starters,
    revision: walkthrough.revision,
    consented: walkthrough.consent_open,
    answeredAt: readiness.answered_at,
    kinds: equipment.kinds,
    draft: {
      about: NOTHING_ANSWERED,
      safety: {},
      // What Account holds now: off for someone new, until tapped.
      avoid: {
        avoid_floor: settings.avoid_floor,
        avoid_kneeling: settings.avoid_kneeling,
        avoid_impact: settings.avoid_impact,
        avoid_hanging: settings.avoid_hanging,
        avoid_knees: settings.avoid_knees,
      },
      places: settings.places,
      kit: equipment.listed ? equipment.items.map(bodyFromItem) : null,
      placement: {},
      days: [],
      // What Account holds now, so Save keeps them unless they're changed here.
      minutes: settings.session_minutes,
      count: settings.session_exercises,
      chosen: {},
      putBack: false,
    },
  }
}

/**
 * /start, the walk-through (ADR-0092): one question per screen, Back on each, and a progress
 * line. Every answer is held here in memory, never in device storage, so a reload starts again;
 * nothing is saved to the plan until Save at the end. The screens the server already has an
 * answer for (consent, where you live, the health questions while current) are skipped. The
 * owner gets a try-out: every screen, and his plan never changes.
 */
export default function StartPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [trail, setTrail] = useState<string[]>(['welcome'])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [consented, setConsented] = useState<boolean | null>(null) // null: as it loaded
  const [startsOn, setStartsOn] = useState<string | null>(null) // saved: the first session's day
  const main = useRef<HTMLElement>(null)
  const moved = useRef(false)
  const told = useRef(false)
  // Once a walk-through: the server hears only that this version of the questions was answered.
  const tell = useCallback(() => {
    if (told.current) return null
    told.current = true
    return answeredReadiness(VERSION)
  }, [])
  const here = trail[trail.length - 1]

  useEffect(() => {
    const ctrl = new AbortController()
    load(ctrl.signal)
      .then((ready) => {
        if (!ready) return setLoaded({ status: 'signed-out' })
        setLoaded({ status: 'ready', ready })
        setDraft(ready.draft)
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setLoaded({ status: 'error' })
      })
    return () => ctrl.abort()
  }, [])

  // Each new screen's heading takes the focus, so a screen reader starts there.
  useEffect(() => {
    if (!moved.current) return
    const heading = main.current?.querySelector<HTMLElement>('h1, h2')
    heading?.setAttribute('tabindex', '-1')
    heading?.focus()
  }, [here])

  const frame = (children: React.ReactNode) => (
    <div className="page">
      <header className="masthead">
        <a href="/" className="wordmark no-underline">
          Training Coach
        </a>
      </header>
      <main ref={main} className="flex flex-col gap-4">
        {children}
      </main>
    </div>
  )

  if (loaded.status === 'loading')
    return frame(
      <p className="status" role="status">
        Loading…
      </p>,
    )
  if (loaded.status === 'signed-out')
    return frame(<SignInCard text="Sign in to set up your plan." />)
  if (loaded.status === 'error' || !draft)
    return frame(<RetryCard text="Couldn't load the walk-through. Check your connection." />)
  if (loaded.ready.who === 'closed')
    return frame(
      <div className={card}>
        <h1 className="m-0 mb-2 text-2xl">Your plan is under way</h1>
        <p className="m-0 mb-3">
          You've logged a workout, so the walk-through is closed. Change your minutes, kit and the
          rest on Account, and each exercise's step on Plan.
        </p>
        <a href="/account">Go to Account</a>
      </div>,
    )

  const { who, known, answeredAt, kinds, starters, revision } = loaded.ready
  const owner = who === 'owner_try_out'
  /** A change to what the ladder walk depends on starts its answers again; the same answer
   * given again (a new object, the same values) keeps them. */
  const change = (part: Partial<Draft>): Draft => {
    const same = (key: keyof Draft) => JSON.stringify(part[key]) === JSON.stringify(draft[key])
    const restart = WALKED_FROM.some((key) => key in part && !same(key))
    return { ...draft, ...part, ...(restart && { placement: {}, chosen: {}, putBack: false }) }
  }
  const go = (next: Draft = draft) => {
    const to = after(here, known, next)
    setDraft(next)
    moved.current = true
    if (to) setTrail([...trail, to])
  }
  const back = () => {
    moved.current = true
    setTrail(trail.slice(0, -1))
  }
  const n = numberOf(here)
  const safety = SAFETY.indexOf(here)
  const question = CHOICES[here]
  const rung = ladderAt(here, known, draft)

  return frame(
    <>
      {owner && (
        <p className={`${card} m-0 font-bold`} role="note">
          This is a try-out: your plan won't change.
        </p>
      )}
      {n > 0 && n <= LAST && (
        <p className="m-0 text-sm text-[var(--slate)]">
          {n} of {LAST}
        </p>
      )}
      {!known.safety && answeredAt && here === after('residence', known, draft) && (
        <p className="m-0 text-[var(--slate)]">
          You answered the health questions on {day(answeredAt)}.
        </p>
      )}
      {here === 'welcome' && <Welcome onStart={() => go()} />}
      {here === 'consent' && (
        <ConsentCard
          category="walkthrough"
          onGiven={() => {
            setConsented(true)
            go()
          }}
          onNotNow={() => go()}
        />
      )}
      {here === 'residence' && (
        <>
          <Residence />
          <button type="button" className={primary} onClick={() => go()}>
            Next
          </button>
        </>
      )}
      {safety >= 0 && (
        <SafetyQuestion
          index={safety}
          value={draft.safety[QUESTIONS[safety].key]}
          onAnswer={(answer) =>
            go({ ...draft, safety: { ...draft.safety, [QUESTIONS[safety].key]: answer } })
          }
          onSkip={() => {
            // Not told to the server, so the app asks them again next time it opens.
            const to = after('safety-note', known, draft)
            moved.current = true
            if (to) setTrail([...trail, to])
          }}
        />
      )}
      {here === 'safety-note' && (
        <SafetyNote answers={draft.safety} tell={tell} onNext={() => go()} />
      )}
      {question && (
        <ChoiceScreen
          question={question}
          value={draft.about[question.key]}
          onAnswer={(value) => go(change({ about: { ...draft.about, [question.key]: value } }))}
          onSkip={() => go(change({ about: { ...draft.about, [question.key]: null } }))}
        />
      )}
      {here === 'avoid' && (
        <AvoidScreen
          draft={draft}
          onChange={(avoid) => setDraft(change({ avoid }))}
          onNext={() => go()}
        />
      )}
      {here === 'places' && (
        <PlacesScreen value={draft.places} onAnswer={(places) => go(change({ places }))} />
      )}
      {here === 'kit' && (
        <KitScreen
          kinds={kinds}
          kit={draft.kit}
          onChange={(kit) => setDraft(change({ kit }))}
          onNext={() => go()}
        />
      )}
      {rung && (
        <LadderScreen
          key={here}
          ladder={rung.ladder}
          step={rung.step}
          index={known.ladders.indexOf(rung.ladder)}
          of={known.ladders.length}
          value={draft.placement[rung.ladder.slug]?.[rung.k]}
          onAnswer={(answer) => {
            const before = (draft.placement[rung.ladder.slug] ?? []).slice(0, rung.k)
            // A new answer places the exercise again: a step picked on the plan screen goes.
            const { [rung.ladder.slug]: _, ...chosen } = draft.chosen
            go({
              ...draft,
              placement: { ...draft.placement, [rung.ladder.slug]: [...before, answer] },
              chosen,
            })
          }}
        />
      )}
      {here === 'days' && (
        <DaysScreen
          days={draft.days}
          onChange={(days) => setDraft({ ...draft, days })}
          onNext={() => go()}
        />
      )}
      {here === 'minutes' && (
        <ChoiceScreen
          question={{ title: 'How long can a session be?', options: MINUTES }}
          value={draft.minutes}
          onAnswer={(minutes) => go({ ...draft, minutes })}
          onSkip={() => go()}
        />
      )}
      {here === 'count' && (
        <ChoiceScreen
          question={{ title: 'How many exercises in a session?', options: COUNTS }}
          value={draft.count}
          onAnswer={(count) => go({ ...draft, count })}
          onSkip={() => go()}
        />
      )}
      {here === 'plan' && (
        <PlanScreen
          who={who}
          known={known}
          starters={starters}
          revision={revision}
          consented={consented ?? loaded.ready.consented}
          draft={draft}
          onChange={setDraft}
          onSaved={(on) => {
            setStartsOn(on)
            moved.current = true
            setTrail(['done']) // saved: nothing to go back to
          }}
        />
      )}
      {here === 'done' && startsOn && <DoneScreen startsOn={startsOn} />}
      {trail.length > 1 && (
        <button type="button" className={`${secondary} self-start`} onClick={back}>
          Back
        </button>
      )}
    </>,
  )
}
