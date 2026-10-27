import AppShell from '../components/AppShell'
import SignedOutNotice from '../components/SignedOutNotice'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchPending,
  fetchSettings,
  fetchToday,
  keepProgress,
  saveSession,
  SignedOutError,
  type Answer,
  type Clash,
  type Guided,
  type Pending,
  type Queued,
  type Saved,
  type TestDayDue,
  type Timing,
  type TodayView,
  type Undone,
  type UndoOffer,
  type GuidedItem,
} from '../api'
import {
  CARDIO,
  fromKept,
  saveChoice,
  savedChoice,
  key,
  kgText,
  loadFor,
  partnerOf,
  restTitle,
  stepOf,
  summary,
  chosenIn,
  shown,
  timed,
  toDone,
  unweighed,
  unitText,
  valueFor,
  versus,
  type Value,
  type Values,
} from './logic'
import FlowPlayer from './FlowPlayer'
import Stretching from './Stretching'
import Cardio, { type CardioChange } from './Cardio'
import ChangeToday from './ChangeToday'
import DayCard from './DayCard'
import Undo from './Undo'
import BandOffers from './BandOffers'
import Proposals from './Proposals'
import LogDay from './LogDay'
import ClashQuestion from './ClashQuestion'
import { ExerciseFigures } from '../bodymap/BodyMap'
import { worksLine } from '../bodymap/words'
import Movement from './Movement'
import { duration, soFar, times, type SetTime } from './times'
import useWakeLock from './useWakeLock'
import { DEFAULT_SOUND, type Sound, playChange, unlockAudio } from '../hiit/sounds'
import { card, primary, primaryInline, secondary } from '../ui'
import { KIT_HREF } from '../account/kit'

type Stage = 'overview' | 'set' | 'rest' | 'check' | 'saved'

type Loaded =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'error' }
  | { status: 'none' } // nothing planned left today
  | { status: 'ready'; session: Guided }

/**
 * /session: today's session one set at a time (D1, docs/specs/dashboard-design.md). Every
 * confirmed set is kept on the server (#117), so Leave keeps the place on any device; nothing
 * becomes a workout until Save session.
 */
export default function SessionPage() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [stage, setStage] = useState<Stage>('overview')
  const [position, setPosition] = useState(0)
  // The furthest set reached: Back fixes an earlier set, then Confirm returns here.
  const [furthest, setFurthest] = useState(0)
  const [values, setValues] = useState<Values>({})
  const [revision, setRevision] = useState(0)
  const [note, setNote] = useState<string | null>(null)
  const [saved, setSaved] = useState<Saved | null>(null)
  const [busy, setBusy] = useState(false)
  const [first, setFirst] = useState<number[]>([]) // pairs started with their second exercise
  // As the set screen shows it, once a suggested weight is taken (ADR-0072); null: as sent.
  const [view, setView] = useState<Guided | null>(null)
  // Clocks keep wall-clock times, not tick counts: a phone throttles timers while the screen
  // is locked, which is exactly when someone rests. Each tick just reads the time again.
  const [now, setNow] = useState(() => Date.now())
  const [restUntil, setRestUntil] = useState(0)
  const [watchFrom, setWatchFrom] = useState<number | null>(null) // stopwatch start while running
  const [shownAt, setShownAt] = useState(() => Date.now()) // when this set's screen appeared
  const [pending, setPending] = useState<Pending[]>([])
  const [saving, setSaving] = useState<string[]>([]) // earlier days being saved
  const [signedOut, setSignedOut] = useState(false) // the sign-in ended on the page
  const [testDay, setTestDay] = useState<TestDayDue | null>(null) // due in front (ADR-0038)
  const [readinessNote, setReadinessNote] = useState<string | null>(null) // hard days (ADR-0046)
  const [dailyCheck, setDailyCheck] = useState<string | null>(null) // today's answers (ADR-0053)
  // What Undo takes back: a change's answer, or undefined to ask the server (C3). The key
  // starts the Undo afresh whenever today changes.
  const [undoOffer, setUndoOffer] = useState<UndoOffer | null | undefined>(undefined)
  const [undoKey, setUndoKey] = useState(0)
  const [cardioSaved, setCardioSaved] = useState(false) // its own screen offers Undo then
  const [planned, setPlanned] = useState<Queued | null>(null) // still next, after a pick
  // A save that found its day already has a session (ADR-0060): asked before anything saves.
  // ``day`` is the earlier day being saved; empty for today's session.
  const [question, setQuestion] = useState<{
    clash: Clash
    taken: Clash | null
    day?: Pending
  } | null>(null)

  const [sound, setSound] = useState<Sound>(DEFAULT_SOUND) // the person's choice, from Settings
  const counting = useRef(0) // the last of a rest's final 3 seconds that sounded
  const rang = useRef(0) // the rest whose end has sounded, by its end time

  useEffect(() => {
    const ask = new AbortController()
    fetchSettings(ask.signal)
      .then((found) => found && setSound(found.sound))
      .catch(() => {}) // the default sound still plays
    return () => ask.abort()
  }, [])

  // The screen stays on through the sets and rests of a guided session.
  useWakeLock(loaded.status === 'ready' && (stage === 'set' || stage === 'rest'))

  const running = watchFrom !== null
  const resting = stage === 'rest'
  useEffect(() => {
    if (!resting && !running) return
    const tick = () => {
      const at = Date.now()
      setNow(at)
      if (!resting) return
      // A soft count for each of the rest's last 3 seconds (again after a "+ 15 s").
      const left = Math.ceil((restUntil - at) / 1000)
      if (left > 3) counting.current = 0
      else if (left >= 1 && counting.current !== left) {
        counting.current = left
        playChange(sound, 'count')
      }
      // The rest is over: the phone buzzes, the timer sound plays and the next set shows,
      // timed from the rest's end (the same on every tick that sees it, ADR-0061).
      if (at >= restUntil) {
        if (rang.current !== restUntil) {
          rang.current = restUntil
          navigator.vibrate?.(300)
          playChange(sound, 'next')
        }
        setShownAt(restUntil)
        setStage('set')
      }
    }
    const timer = window.setInterval(tick, 250)
    document.addEventListener('visibilitychange', tick)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', tick)
    }
  }, [resting, running, restUntil, sound])

  const restLeft = Math.max(0, Math.ceil((restUntil - now) / 1000))
  const startRest = (seconds: number) => {
    const at = Date.now()
    setNow(at)
    setRestUntil(at + seconds * 1000)
  }

  // The stopwatch for timed exercises.
  const watch = watchFrom === null ? null : Math.max(0, Math.floor((now - watchFrom) / 1000))
  const startWatch = () => {
    const at = Date.now()
    setNow(at)
    setWatchFrom(at)
  }

  useEffect(() => {
    fetchPending()
      .then(setPending)
      .catch(() => setPending([]))
  }, [])

  /** Show today as the server has it: loaded, or answered by a change or an undo. */
  const show = useCallback((today: TodayView) => {
    setTestDay(today.test_day ?? null)
    setReadinessNote(today.readiness_note ?? null)
    setDailyCheck(today.daily_check ?? null)
    setPlanned(today.planned ?? null)
    // An empty order can't be guided; treat it like nothing planned.
    if (!today.session || today.session.order.length === 0) return setLoaded({ status: 'none' })
    setLoaded({ status: 'ready', session: today.session })
    const kept = fromKept(today.progress)
    setValues(kept)
    setView(shown(today.session, savedChoice(today.session)))
    setPosition(today.progress?.position ?? 0)
    setFurthest(today.progress?.position ?? 0)
    setRevision(today.progress?.revision ?? 0)
    setFirst(today.progress?.first ?? [])
  }, [])

  const load = useCallback(() => {
    fetchToday()
      .then((today) => (today === null ? setLoaded({ status: 'signed-out' }) : show(today)))
      .catch(() => setLoaded({ status: 'error' }))
  }, [show])

  useEffect(load, [load])

  /** Ask the server again what Undo would take back. */
  const refreshUndo = (offer?: UndoOffer | null) => {
    setUndoOffer(offer)
    setUndoKey((k) => k + 1)
  }

  const changed = (today: TodayView, text: string, offer?: UndoOffer | null) => {
    show(today)
    setNote(text)
    setSaved(null)
    setStage('overview')
    refreshUndo(offer)
  }

  const undone = (done: Undone) =>
    changed(
      done.today,
      `Undone: ${done.what}.${done.next_session ? ` Next up: ${done.next_session}.` : ''}`,
      null, // one step only: nothing more to undo until the next change
    )

  const stale = () => {
    setNote("Today's session changed (on another device or in Telegram). Here it is now.")
    refreshUndo()
    load()
  }

  const cardioChange = (change: CardioChange) => {
    // The run of a session with more after it: on to the rest of it (ADR-0066).
    const onward =
      change === 'saved' && loaded.status === 'ready' && afterRun(loaded.session).length > 0
    setCardioSaved(change === 'saved' && !onward)
    if (change !== 'saved' || onward) refreshUndo()
    if (change === 'undone' || onward) load()
  }

  const counted = (text: string) => {
    setNote(text)
    refreshUndo()
    load()
  }
  const bandOffers = (
    <>
      <Proposals onSaved={counted} />
      <BandOffers onCounted={counted} />
    </>
  )

  const undoBar = !cardioSaved && <Undo key={undoKey} offer={undoOffer} onUndone={undone} />
  const noteBar = note && (
    <p role="status" className="status">
      {note}
    </p>
  )
  const dailyLine = dailyCheck && (
    <p className="m-0 text-sm text-[var(--slate)]">Today's check: {dailyCheck}.</p>
  )

  if (loaded.status !== 'ready')
    return (
      <AppShell>
        {loaded.status === 'none' && noteBar}
        {loaded.status === 'none' && dailyLine}
        {loaded.status === 'none' && readinessNote && <ReadinessNotice text={readinessNote} />}
        {loaded.status === 'none' && testDay && <TestDayNotice due={testDay} />}
        <Status loaded={loaded} />
        {loaded.status === 'none' && <DayCard refresh={undoKey} />}
        {loaded.status === 'none' && bandOffers}
        {loaded.status === 'none' && undoBar}
        {loaded.status === 'none' && <Cardio featured={false} onChange={cardioChange} />}
        {loaded.status === 'none' && <LogDay onSaved={counted} />}
      </AppShell>
    )
  const session = loaded.session
  const screen = view ?? session
  const total = session.order.length

  /** Keep the place and the sets; another device having moved on reloads its version. */
  const keep = async (
    nextPosition: number,
    nextValues: Values,
    nextFirst: number[] = first,
  ): Promise<boolean> => {
    setSignedOut(false) // a retry after signing in again
    setBusy(true)
    try {
      const result = await keepProgress({
        template_id: session.template_id,
        revision,
        position: nextPosition,
        first: nextFirst,
        sets: toDone(session, nextValues),
      })
      if (result === 'stale') {
        setNote('This session moved on from another device; here is where it is now.')
        load()
        return false
      }
      setRevision(result)
      return true
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't save that set. Check your connection and confirm again.")
      return false
    } finally {
      setBusy(false)
    }
  }

  const timesSoFar = stage === 'check' ? times(session, values) : null
  const step = screen.order[Math.min(position, total - 1)]
  const item = screen.items[step.item]
  const kg = loadFor(screen, values, step.item, step.set_no)
  const base = valueFor(values, step.item, step.set_no, step.target)
  const value = kg === undefined ? base : { ...base, load_kg: kg }
  const sentLoad = session.items[step.item].load // before a suggested weight is taken
  const change = (v: Value) => setValues({ ...values, [key(step.item, step.set_no)]: v })

  /** Confirm this set: the counter's value, or the clock's reading when it runs; the mobility
   * flow passes its minutes and when it started (ADR-0062). */
  const confirm = async (given?: Value, from: number = shownAt) => {
    unlockAudio() // inside the tap: browsers only allow sound after a gesture
    const reading = given ?? (watch === null ? value : { ...value, left: watch, right: watch })
    const done = { ...timed(reading, from, Date.now()), confirmed: true }
    const nextValues = { ...values, [key(step.item, step.set_no)]: done }
    const next = Math.max(position + 1, furthest) // a corrected set returns to where you were
    if (await keep(next, nextValues)) {
      setNote(null)
      setValues(nextValues)
      setPosition(next)
      setFurthest(next)
      setWatchFrom(null)
      if (next >= total) setStage('check')
      else {
        // The rest that leads into the next set: a 15 s move inside a pair, longer after it.
        startRest(session.order[next - 1].rest_seconds)
        setStage('rest')
      }
    }
  }

  /** "Do <partner> first": before a pair has started, swap its order for this session. */
  const pairStarted =
    item.pair !== null &&
    session.order.some(
      (s) => session.items[s.item].pair === item.pair && values[key(s.item, s.set_no)],
    )
  const partner = partnerOf(session, step.item)
  const swap = async () => {
    if (item.pair === null) return
    const nextFirst = first.includes(item.pair)
      ? first.filter((p) => p !== item.pair)
      : [...first, item.pair]
    if (await keep(position, values, nextFirst)) load()
  }

  /** Moving to another set or screen stops the clock: it belongs to the set it started on. A
   * set's time starts when its screen appears (ADR-0061). */
  const goTo = (nextStage: Stage, nextPosition: number = position) => {
    setNote(null)
    setWatchFrom(null)
    setPosition(nextPosition)
    if (nextStage === 'set') setShownAt(Date.now())
    setStage(nextStage)
  }

  const stopWatch = () => {
    // Both sides get the time: a one-sided timed hold is timed per side, the same each side.
    if (watch !== null) change({ ...value, left: watch, right: watch })
    setWatchFrom(null)
  }

  /** A save answered with a clash: ask, keeping the first question when only the day to move
   * to was taken. True when there is a question to answer. */
  const asked = (
    result: Saved | 'stale' | { clash: Clash } | { problem: string },
    day?: Pending,
  ): result is { clash: Clash } => {
    if (result === 'stale' || !('clash' in result)) return false
    if (result.clash.moving && question) setQuestion({ ...question, taken: result.clash })
    else setQuestion({ clash: result.clash, taken: null, day })
    return true
  }

  const saveEarlier = async (day: Pending, answer?: Answer) => {
    if (saving.includes(day.day)) return
    setSaving((days) => [...days, day.day])
    setSignedOut(false) // a retry after signing in again
    try {
      const result = await saveSession(day.day, answer)
      if (asked(result, day)) return
      if (result !== 'stale' && 'problem' in result) {
        // Refused, with the reason: still offered, and any question stays to answer otherwise.
        setNote(`${day.session} wasn't saved: ${result.problem}.`)
        return
      }
      setQuestion(null)
      setNote(
        result === 'stale'
          ? `${day.session} couldn't be saved: that day changed.`
          : `Saved ${day.session} for ${day.day}.`,
      )
      if (result !== 'stale') refreshUndo()
      setPending((days) => days.filter((p) => p.day !== day.day)) // settled: saved or stale
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't save. Check your connection and try again.") // still offered
    } finally {
      setSaving((days) => days.filter((d) => d !== day.day))
    }
  }

  const save = async (answer?: Answer) => {
    setNote(null)
    setSignedOut(false) // a retry after signing in again
    setBusy(true)
    try {
      const result = await saveSession(undefined, answer)
      if (asked(result)) return
      if (result !== 'stale' && 'problem' in result) {
        setNote(`Not saved: ${result.problem}.`) // the reason; any question stays to answer
        return
      }
      setQuestion(null)
      if (result === 'stale') {
        setNote("Today's session changed (a rest, swap or another log), so this wasn't saved.")
        return
      }
      setSaved(result)
      setStage('saved')
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't save. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell>
      {noteBar}
      {signedOut && <SignedOutNotice />}

      {stage === 'overview' && (
        <>
          {dailyLine}
          {readinessNote && <ReadinessNotice text={readinessNote} />}
          {testDay && <TestDayNotice due={testDay} />}
          {bandOffers}
          {question?.day && (
            <ClashQuestion
              clash={question.clash}
              taken={question.taken}
              busy={saving.length > 0}
              onAnswer={(answer) => question.day && saveEarlier(question.day, answer)}
              onCancel={() => setQuestion(null)}
            />
          )}
          {pending.map((day) => (
            <p key={day.day} className={card}>
              {day.session} on {day.day} wasn't saved ({day.sets} sets).{' '}
              <button
                type="button"
                className={secondary}
                disabled={saving.includes(day.day)}
                onClick={() => saveEarlier(day)}
              >
                Save it
              </button>
            </p>
          ))}
          {isCardio(session) ? (
            <>
              <Cardio featured onChange={cardioChange} />
              {afterRun(session).length > 0 && (
                <p className={card}>
                  After your run: {afterRun(session).join(', ')}. Log the run, then this opens.
                </p>
              )}
            </>
          ) : (
            <Overview
              session={session}
              resumeAt={position > 0 && position < total ? position : null}
              onStart={() => {
                unlockAudio() // so the rests can sound; nothing plays on Start
                goTo(position >= total ? 'check' : 'set')
              }}
            />
          )}
          {!cardioSaved && (
            <ChangeToday
              key={session.template_id}
              templateId={session.template_id}
              name={session.name}
              planned={planned}
              onChanged={(result, text) => changed(result.today, text, result.undo)}
              onStale={stale}
            />
          )}
          {undoBar}
          {!isCardio(session) && <Cardio featured={false} onChange={cardioChange} />}
          <LogDay onSaved={counted} />
          <DayCard refresh={undoKey} />
        </>
      )}

      {stage === 'set' && (
        <section aria-labelledby="exercise" className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <button type="button" className={secondary} onClick={() => goTo('overview')}>
              Leave
            </button>
            <span className="text-sm text-[var(--slate)]">
              Set {position + 1} of {total}
            </span>
            <button
              type="button"
              className={secondary}
              disabled={position === 0}
              onClick={() => goTo('set', position - 1)}
            >
              Back
            </button>
          </div>
          <progress
            max={total}
            value={position + 1}
            aria-label="Session progress"
            className="w-full"
          />
          <div>
            <p className="text-sm font-bold tracking-wide text-[var(--bell-ink)]">
              {partnerOf(session, step.item)
                ? `PAIR ${item.pair} · ALTERNATE WITH ${partnerOf(session, step.item)?.name.toUpperCase()}`
                : 'ON ITS OWN'}
            </p>
            <h1 id="exercise" className="text-4xl font-extrabold">
              {item.name}
            </h1>
            <p className="text-[var(--slate)]">{item.step}</p>
            {item.cue && <p className="text-[var(--slate)]">{item.cue}</p>}
            {item.baseline && (
              <p className="font-bold text-[var(--bell-ink)]">
                Baseline: first time at this step. Do what you can; targets grow from it.
              </p>
            )}
          </div>
          {item.flow ? (
            <FlowPlayer
              key={position}
              flow={item.flow}
              busy={busy}
              onDone={(minutes, startedAt) =>
                confirm({ left: minutes, right: minutes, split: false }, startedAt)
              }
            />
          ) : (
            <>
              {partner && !pairStarted && (
                <button
                  type="button"
                  className="min-h-11 rounded-xl border-2 border-dashed border-[var(--bell-ink)] font-bold text-[var(--bell-ink)]"
                  onClick={swap}
                >
                  Do {partner.name} first
                </button>
              )}
              <div className="flex items-baseline justify-between">
                <span className="text-lg font-bold">
                  Set {step.set_no} of {item.targets.length}
                </span>
                <span className="text-[var(--slate)]">
                  Target {unitText(item, step.target)}
                  {item.per_side ? ' each side' : ''}
                </span>
              </div>
              {item.unit === 'seconds' && (
                <div className={card + ' flex flex-col items-center gap-2'}>
                  <span aria-live="polite" className="text-6xl font-extrabold">
                    {running ? watch : value.left} s
                  </span>
                  <button
                    type="button"
                    className={primary}
                    onClick={running ? stopWatch : startWatch}
                  >
                    {running ? 'Stop' : 'Start clock'}
                  </button>
                </div>
              )}
              {item.per_side && value.split ? (
                <>
                  <Counter
                    label="Left"
                    value={value.left}
                    step={stepOf(item)}
                    target={step.target}
                    onChange={(left) => change({ ...value, left })}
                  />
                  <Counter
                    label="Right"
                    value={value.right}
                    step={stepOf(item)}
                    target={step.target}
                    onChange={(right) => change({ ...value, right })}
                  />
                </>
              ) : (
                <Counter
                  label={item.per_side ? 'Each side' : item.unit === 'reps' ? 'Reps' : item.unit}
                  value={value.left}
                  step={stepOf(item)}
                  target={step.target}
                  onChange={(v) => change({ ...value, left: v, right: v })}
                />
              )}
              {item.load && sentLoad && kg !== undefined && (
                <Weight
                  load={item.load}
                  sent={sentLoad}
                  kg={kg}
                  setNo={step.set_no}
                  onChange={(load_kg) => change({ ...value, load_kg })}
                  onChoose={(take) => {
                    const chosen = { ...chosenIn(session, screen), [step.item]: take }
                    saveChoice(session, chosen)
                    setValues(unweighed(values, step.item)) // a touched set starts afresh too
                    setView(shown(session, chosen))
                  }}
                />
              )}
              {item.per_side && (
                <button
                  type="button"
                  aria-pressed={value.split}
                  className="min-h-11 font-bold text-[var(--bell-ink)] underline"
                  onClick={() => change({ ...value, split: !value.split, right: value.left })}
                >
                  {value.split ? 'Same on both sides' : 'Left and right differ'}
                </button>
              )}
              <button type="button" className={primary} disabled={busy} onClick={() => confirm()}>
                Confirm set
              </button>
              {item.summary && <p className={card}>{item.summary}</p>}
              <Movement key={position} slug={item.slug} name={item.name} step={item.step} />
              {item.muscles.length > 0 && (
                <div className={card + ' flow-root'}>
                  <ExerciseFigures
                    muscles={item.muscles}
                    className="mb-2 justify-center min-[340px]:float-right min-[340px]:mb-1 min-[340px]:ml-3"
                  />
                  <p className="text-[var(--slate)]">{worksLine(item.muscles, item.parts)}</p>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {stage === 'rest' && (
        <section aria-labelledby="rest" className="flex flex-col items-center gap-4 text-center">
          <h1
            id="rest"
            className="text-lg font-bold tracking-wide text-[var(--bell-ink)] uppercase"
          >
            {restTitle(session.order[position - 1], item.name)}
          </h1>
          <p aria-live="polite" className="text-8xl font-extrabold">
            {Math.floor(restLeft / 60)}:{String(restLeft % 60).padStart(2, '0')}
          </p>
          <p className="text-[var(--slate)]">Your phone buzzes when it's time.</p>
          <p className={card + ' w-full'}>
            Next: <span className="font-bold">{item.name}</span>, set {step.set_no} of{' '}
            {item.targets.length}, target {unitText(item, step.target)}
            {item.per_side ? ' each side' : ''}
            {kg !== undefined ? ` at ${kgText(kg)}` : ''}
          </p>
          <div className="flex w-full gap-3">
            <button type="button" className={secondary} onClick={() => startRest(restLeft + 15)}>
              + 15 s
            </button>
            <button type="button" className={primary} onClick={() => goTo('set')}>
              Skip rest
            </button>
          </div>
        </section>
      )}

      {stage === 'check' && (
        <section aria-labelledby="check" className="flex flex-col gap-4">
          <h1 id="check" className="text-4xl font-extrabold">
            Check and save
          </h1>
          <p className="text-[var(--slate)]">Nothing is saved until you save.</p>
          {timesSoFar && <p className="font-bold">{soFar(timesSoFar)}</p>}
          <ul className={card}>
            {summary(screen, values).map((row, index) => (
              <li
                key={row.name}
                className="flex justify-between gap-3 border-b border-[var(--line)] py-2"
              >
                <span>
                  <span className="font-bold">{row.name}</span>
                  <br />
                  <span className="text-sm text-[var(--slate)]">target {row.target}</span>
                </span>
                <span className="flex flex-col items-end text-right">
                  <span className="font-bold">{row.done}</span>
                  <SetTimes sets={timesSoFar?.rows[index] ?? []} />
                </span>
              </li>
            ))}
          </ul>
          {question && !question.day && (
            <ClashQuestion
              clash={question.clash}
              taken={question.taken}
              busy={busy}
              onAnswer={save}
              onCancel={() => setQuestion(null)}
            />
          )}
          <div className="flex gap-3">
            <button type="button" className={secondary} onClick={() => goTo('set', total - 1)}>
              Back
            </button>
            <button type="button" className={primary} disabled={busy} onClick={() => save()}>
              Save session
            </button>
          </div>
        </section>
      )}

      {stage === 'saved' && saved && (
        <section aria-labelledby="saved" className="flex flex-col gap-4">
          <p className="font-bold text-[var(--ink)]">Saved</p>
          <h1 id="saved" className="text-4xl font-extrabold">
            {session.name} done
          </h1>
          {saved.timing && <p>{took(saved.timing)}</p>}
          {saved.next_session && <p>Next up: {saved.next_session}.</p>}
          {saved.earned.length > 0 && (
            <ul className={card}>
              {saved.earned.map((e) => (
                <li key={e.exercise}>
                  {e.exercise}
                  {e.best_set !== null ? `: new best ${e.best_set} in one set` : ''}
                  {e.next_step && (
                    <>
                      {' '}
                      ·{' '}
                      <a
                        href={`/plan?move=${encodeURIComponent(e.slug)}`}
                        className="font-bold underline"
                      >
                        ready to move up to {e.next_step}
                      </a>
                    </>
                  )}
                  {e.at_top && <TopNote unlock={e.unlock} />}
                </li>
              ))}
            </ul>
          )}
          {saved.stretching && <Stretching workoutId={saved.workout_id} />}
          <Undo onUndone={undone} />
          <div className="flex flex-wrap gap-2">
            <a
              href="/progress"
              className={`${primaryInline} inline-flex items-center no-underline`}
            >
              See my progress
            </a>
            <a
              href="/progress?tab=plan"
              className={`${secondary} inline-flex items-center no-underline`}
            >
              The week ahead
            </a>
          </div>
        </section>
      )}
    </AppShell>
  )
}

/** The ready rule met with no level to move to (ADR-0078): says so, and when the kit is what's
 * missing, what would open the next level (ADR-0071). The person decides; nothing moves. */
function TopNote({ unlock }: { unlock: string | null }) {
  if (!unlock) return <> · top of the range on the last level of its ladder.</>
  return (
    <>
      {' '}
      · top of the range on the last level your kit allows.{' '}
      {unlock[0].toUpperCase() + unlock.slice(1)}.{' '}
      <a href={KIT_HREF} className="font-bold underline">
        My equipment
      </a>
    </>
  )
}

/** Each set's time under its reps, "34s / 31s / 38s": a much slower set in bold, and a rest
 * that ran over its plan by its amount on the set after it. Nothing for sets without times. */
function SetTimes({ sets }: { sets: (SetTime | null)[] }) {
  const shown = sets.filter((set): set is SetTime => set !== null)
  if (shown.length === 0) return null
  return (
    <span className="text-sm text-[var(--slate)]">
      {shown.map((set, n) => (
        <span key={n}>
          {n > 0 && ' / '}
          <span className={set.slow ? 'font-bold text-[var(--ink)]' : ''}>
            {duration(set.seconds)}
            {set.slow && <span className="sr-only"> (slow)</span>}
          </span>
          {set.overran !== null && ` (+${duration(set.overran)} rest)`}
        </span>
      ))}
    </span>
  )
}

/** "Took 41 min: 22 on sets, 19 resting", and any breaks, which aren't in the total. */
function took(timing: Timing): string {
  const breaks =
    timing.breaks === 0 ? '' : `, plus ${timing.breaks} break${timing.breaks === 1 ? '' : 's'}`
  return `Took ${timing.minutes} min: ${timing.on_sets} on sets, ${timing.resting} resting${breaks}.`
}

/** Today's session is a single cardio exercise, or a conditioning session's cardio with more
 * after it: the cardio is logged in one step, not set by set (ADR-0066). */
function isCardio(session: Guided): boolean {
  if (session.items.length === 1) return CARDIO.includes(session.items[0].slug)
  const runs = session.items.filter((item) => CARDIO.includes(item.slug))
  return session.kind === 'conditioning' && !session.after_run && runs.length === 1
}

/** What a conditioning session has after its cardio, by name, until the cardio is logged. */
function afterRun(session: Guided): string[] {
  if (session.after_run || !isCardio(session)) return []
  return session.items.filter((item) => !CARDIO.includes(item.slug)).map((item) => item.name)
}

function Status({ loaded }: { loaded: Exclude<Loaded, { status: 'ready' }> }) {
  if (loaded.status === 'loading')
    return (
      <p className="status" role="status">
        Loading today's session…
      </p>
    )
  if (loaded.status === 'signed-out')
    return (
      <div className={card}>
        <p className="m-0 mb-3">Sign in to start today's session.</p>
        <a
          href="/signin?next=/session"
          className={`${primaryInline} inline-flex items-center no-underline`}
        >
          Sign in
        </a>
      </div>
    )
  if (loaded.status === 'none')
    return (
      <div className={`${card} flex flex-col gap-3`}>
        <h1 className="text-3xl font-extrabold">Nothing left today</h1>
        <p className="m-0">Today's training is done or rested. Enjoy the rest.</p>
        <div className="flex flex-wrap gap-2">
          <a href="/progress" className={`${primaryInline} inline-flex items-center no-underline`}>
            See my progress
          </a>
          <a
            href="/progress?tab=plan"
            className={`${secondary} inline-flex items-center no-underline`}
          >
            The week ahead
          </a>
        </div>
      </div>
    )
  return (
    <div className={card}>
      <p className="status-error m-0 mb-3" role="alert">
        Couldn't load today's session. Check your connection.
      </p>
      <button type="button" onClick={() => window.location.reload()}>
        Try again
      </button>
    </div>
  )
}

function Overview({
  session,
  resumeAt,
  onStart,
}: {
  session: Guided
  resumeAt: number | null
  onStart: () => void
}) {
  return (
    <section aria-labelledby="session" className="flex flex-col gap-4">
      <p className="text-sm text-[var(--slate)]">
        {session.usual_minutes
          ? `Usually ${session.usual_minutes} min` // from earlier timed sessions (ADR-0061)
          : `About ${session.minutes} min`}
      </p>
      <h1 id="session" className="text-5xl font-extrabold">
        {session.name}
      </h1>
      <p className="text-[var(--slate)]">{session.focus}</p>
      {session.after_run && (
        <p className={card}>After your run: it's logged, and these sets are saved with it.</p>
      )}
      {session.warm_up && <p className={card}>Warm up for about 10 minutes first.</p>}
      <p className="text-[var(--slate)]">
        Stop if you feel sharp pain, dizziness or chest tightness.
      </p>
      <ul className="flex flex-col gap-2">
        {session.items.map((item) => (
          <li key={item.slug} className={card + ' flex justify-between gap-3'}>
            <span>
              <span className="font-bold">{item.name}</span>
              <br />
              <span className="text-sm text-[var(--slate)]">
                {item.pair !== null ? `Pair ${item.pair} · ` : ''}
                {item.step}
                {item.baseline ? ' · baseline' : ''}
              </span>
            </span>
            <span className="font-bold whitespace-nowrap">
              {item.targets.length} × {unitText(item, item.targets[0])}
              {item.per_side ? ' each side' : ''}
            </span>
          </li>
        ))}
      </ul>
      <button type="button" className={primary} onClick={onStart}>
        {resumeAt !== null
          ? `Resume: set ${resumeAt + 1} of ${session.order.length}`
          : 'Start session'}
      </button>
    </section>
  )
}

function Counter({
  label,
  value,
  step,
  target,
  onChange,
}: {
  label: string
  value: number
  step: number
  target: number
  onChange: (value: number) => void
}) {
  return (
    <div className={card + ' flex flex-col items-center gap-2'} role="group" aria-label={label}>
      <span className="text-sm font-bold text-[var(--slate)]">{label}</span>
      <div className="flex items-center gap-5">
        <button
          type="button"
          aria-label={`${step} fewer`}
          className="size-16 rounded-full border-2 border-[var(--ink)] text-3xl"
          onClick={() => onChange(Math.max(0, value - step))}
        >
          −
        </button>
        <span aria-live="polite" className="min-w-24 text-center text-7xl font-extrabold">
          {value}
        </span>
        <button
          type="button"
          aria-label={`${step} more`}
          className="size-16 rounded-full border-2 border-[var(--ink)] text-3xl"
          onClick={() => onChange(value + step)}
        >
          +
        </button>
      </div>
      <span className="text-sm text-[var(--slate)]">{versus(value, target)}</span>
    </div>
  )
}

/** The weight on a loaded step (ADR-0072): − and + in the kit's increment, no typing. It says
 * where the weight came from; what to lift is the person's call. */
function LoadCounter({
  load,
  kg,
  last,
  onChange,
}: {
  load: NonNullable<GuidedItem['load']>
  kg: number
  last: number
  onChange: (kg: number) => void
}) {
  const label = load.kit === 'dumbbells' ? 'Each dumbbell, kg' : 'Weight, kg'
  const by = (sign: number) => onChange(Math.round((kg + sign * load.increment) * 100) / 100)
  const note = !load.carried
    ? 'First time at this step: set your weight'
    : kg === last
      ? 'Same as last time'
      : `Last time ${kgText(last)}`
  return (
    <div className={card + ' flex flex-col items-center gap-2'} role="group" aria-label={label}>
      <span className="text-sm font-bold text-[var(--slate)]">{label}</span>
      <div className="flex items-center gap-5">
        <button
          type="button"
          aria-label={`${load.increment} kg lighter`}
          disabled={kg - load.increment <= 0}
          className="size-14 rounded-full border-2 border-[var(--ink)] text-2xl disabled:opacity-40"
          onClick={() => by(-1)}
        >
          −
        </button>
        <span aria-live="polite" className="min-w-24 text-center text-5xl font-extrabold">
          {kg}
        </span>
        <button
          type="button"
          aria-label={`${load.increment} kg heavier`}
          disabled={kg + load.increment > 500}
          className="size-14 rounded-full border-2 border-[var(--ink)] text-2xl disabled:opacity-40"
          onClick={() => by(1)}
        >
          +
        </button>
      </div>
      <span className="text-sm text-[var(--slate)]">{note}</span>
    </div>
  )
}

/** The weight on a loaded step and, when there is one, the suggested next weight. */
function Weight({
  load,
  sent,
  kg,
  setNo,
  onChange,
  onChoose,
}: {
  load: NonNullable<GuidedItem['load']>
  sent: NonNullable<GuidedItem['load']>
  kg: number
  setNo: number
  onChange: (kg: number) => void
  onChoose: (take: boolean) => void
}) {
  return (
    <>
      <LoadCounter load={load} kg={kg} last={sent.kg[setNo - 1]} onChange={onChange} />
      {sent.suggested && <Suggested load={sent} taken={load !== sent} onChoose={onChoose} />}
    </>
  )
}

/** Double progression's suggestion (ADR-0072): every set reached the top last time, so the
 * next weight up is offered, reps from the bottom. A tap takes it or goes back. */
function Suggested({
  load,
  taken,
  onChoose,
}: {
  load: NonNullable<GuidedItem['load']>
  taken: boolean
  onChoose: (take: boolean) => void
}) {
  const up = load.suggested!
  const last = Math.max(...load.kg)
  return (
    <div className={card + ' flex flex-col gap-2'} role="group" aria-label="Next weight">
      <p className="m-0">
        {taken
          ? `Taking ${kgText(up.kg)}: reps start again from ${up.targets[0]}.`
          : `Every set reached the top of the range last time. Ready for ${kgText(up.kg)}? Reps start again from ${up.targets[0]}.`}
      </p>
      <button
        type="button"
        aria-pressed={taken}
        className="min-h-11 rounded-xl border-2 border-[var(--ink)] font-bold"
        onClick={() => onChoose(!taken)}
      >
        {taken ? `Stay at ${kgText(last)}` : `Use ${kgText(up.kg)}`}
      </button>
    </div>
  )
}

/** Advice before a hard day (ADR-0046): answer the readiness questions, or see a doctor. */
function ReadinessNotice({ text }: { text: string }) {
  return (
    <p role="note" className={card}>
      {text} <a href="/readiness">Readiness questions</a>
    </p>
  )
}

/** A test day due today stands in front of the session, which waits (ADR-0038). */
function TestDayNotice({ due }: { due: TestDayDue }) {
  return (
    <section aria-labelledby="test-day" className={card + ' flex flex-col gap-3'}>
      <h2 id="test-day" className="text-lg font-bold">
        Today: {due.name}
      </h2>
      <p>{due.tests.join(', ')}.</p>
      <p className="text-[var(--slate)]">The session below waits until they're done.</p>
      <a href="/tests" className={primary + ' flex items-center justify-center'}>
        Go to the tests
      </a>
    </section>
  )
}
