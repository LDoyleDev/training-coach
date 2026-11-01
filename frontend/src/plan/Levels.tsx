import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchProgress, moveOnLadder, SignedOutError, type LadderMove, type Standing } from '../api'
import { lastAndBest } from '../progress/logic'
import { actions, card, primaryInline, secondary } from '../ui'
import { KIT_HREF } from '../account/kit'
import {
  AVOIDED_NOW,
  WAITS,
  avoidedNow,
  confirmText,
  lockedText,
  needs,
  nextRung,
  said,
  topLabel,
  wanted,
} from './ladder'

type Loaded =
  | { status: 'loading' }
  | { status: 'hidden' } // signed out: the plan below says to sign in
  | { status: 'error' }
  | { status: 'ready'; standings: Standing[]; strength: boolean; kitListed: boolean }

/** Your level on each exercise's ladder (ADR-0075): Move up / Not yet when ready, as the bot's
 * prompt, and Change level to choose any step, up or down. `?move=<slug>` opens that one. Each
 * step shows its "Can you do ...?" question as a hint (G1); nothing sets a level from it. */
export default function Levels() {
  const [loaded, setLoaded] = useState<Loaded>({ status: 'loading' })
  const [open, setOpen] = useState<string | null>(() => wanted(window.location.search))
  const scrolled = useRef(false)

  const load = useCallback(
    () =>
      fetchProgress()
        .then((found) =>
          setLoaded(
            found === null
              ? { status: 'hidden' }
              : {
                  status: 'ready',
                  standings: found.standings.filter((s) => !s.retired),
                  strength: found.strength_block,
                  kitListed: found.kit_listed,
                },
          ),
        )
        .catch(() => setLoaded({ status: 'error' })),
    [],
  )

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (loaded.status !== 'ready' || scrolled.current || open === null) return
    scrolled.current = true
    document.getElementById(`move-${open}`)?.scrollIntoView?.({ block: 'start' })
  }, [loaded, open])

  if (loaded.status === 'hidden') return null
  return (
    <section aria-labelledby="levels" className="flex flex-col gap-3">
      <h2 id="levels" className="m-0 text-2xl font-extrabold">
        Your levels
      </h2>
      <p className="m-0 text-[var(--slate)]">
        Where you are on each exercise's ladder. Open one to move up, or to choose a different
        level.
      </p>
      {loaded.status === 'loading' && (
        <p className="status" role="status">
          Loading your levels…
        </p>
      )}
      {loaded.status === 'error' && (
        <p className="status status-error" role="alert">
          Couldn't load your levels. Check your connection, then reload the page.
        </p>
      )}
      {loaded.status === 'ready' && !loaded.kitListed && (
        <p className="m-0">
          No kit listed, so no step is locked.{' '}
          <a href={KIT_HREF} className="font-bold underline">
            List your kit in My equipment
          </a>{' '}
          to see which steps it allows.
        </p>
      )}
      {loaded.status === 'ready' && (
        <List
          standings={loaded.standings}
          strength={loaded.strength}
          open={open}
          setOpen={setOpen}
          onChanged={load}
        />
      )}
    </section>
  )
}

/** The ready ones (and the one open), then every exercise on request: the plan has dozens. */
function List({
  standings,
  strength,
  open,
  setOpen,
  onChanged,
}: {
  standings: Standing[]
  strength: boolean
  open: string | null
  setOpen: (f: (cur: string | null) => string | null) => void
  onChanged: () => Promise<void>
}) {
  const [all, setAll] = useState(false)
  const ready = standings.filter((s) => s.status === 'ready').length
  // A step the person now avoids is shown too, so they see it and can pick another.
  const shown = standings.filter(
    (s) => all || s.status === 'ready' || avoidedNow(s) || s.slug === open,
  )
  return (
    <>
      <p className="m-0 font-bold">
        {ready === 0
          ? 'Nothing is ready to move up right now.'
          : `${ready} ready to move up${strength ? ' when the hypertrophy block starts' : ''}.`}
      </p>
      {shown.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {shown.map((s) => (
            <Panel
              key={s.slug}
              standing={s}
              strength={strength}
              open={open === s.slug}
              onToggle={() => setOpen((cur) => (cur === s.slug ? null : s.slug))}
              onChanged={onChanged}
            />
          ))}
        </ul>
      )}
      <button
        type="button"
        className={secondary + ' self-start'}
        aria-expanded={all}
        onClick={() => setAll((cur) => !cur)}
      >
        {all ? 'Show only the ones ready' : `Show all exercises (${standings.length})`}
      </button>
    </>
  )
}

function Panel({
  standing: s,
  strength,
  open,
  onToggle,
  onChanged,
}: {
  standing: Standing
  strength: boolean
  open: boolean
  onToggle: () => void
  onChanged: () => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [choosing, setChoosing] = useState(false)
  const [picked, setPicked] = useState(s.step_id)
  const upcoming = nextRung(s)
  const ready = s.status === 'ready'
  const body = `move-${s.slug}-body`

  const press = async (move: LadderMove, stepId: number) => {
    setBusy(true)
    try {
      const done = await moveOnLadder(s.slug, move, stepId)
      setNote(typeof done === 'string' ? done : said(done))
      setChoosing(false)
      await onChanged()
    } catch (err) {
      setNote(
        err instanceof SignedOutError
          ? 'Your sign-in has ended. Sign in again, then try once more.'
          : "Couldn't reach the coach. Nothing changed. Try again.",
      )
    } finally {
      setBusy(false)
    }
  }

  const pickedRung = s.ladder.find((r) => r.id === picked)
  const pickedName = pickedRung?.name ?? s.step
  const pickedLocked = pickedRung ? lockedText(pickedName, pickedRung) : null
  return (
    <li id={`move-${s.slug}`} className={card + ' flex scroll-mt-4 flex-col gap-3'}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={body}
        onClick={onToggle}
        className="flex h-auto min-h-11 w-full items-center justify-between gap-3 border-0 p-0 text-left"
      >
        <span className="flex flex-col">
          <span>{s.exercise}</span>
          <span className="font-normal text-[var(--slate)]">
            Step {s.step_number} of {s.steps}: {s.step}
          </span>
          {ready && <span className="text-[var(--bell-ink)]">Ready to move up</span>}
          {topLabel(s) && <span>{topLabel(s)}</span>}
          {avoidedNow(s) && <span className="text-[var(--bell-ink)]">{AVOIDED_NOW}</span>}
        </span>
        <span aria-hidden="true" className="shrink-0 text-2xl">
          {open ? '−' : '+'}
        </span>
      </button>

      {open && (
        <div id={body} className="flex flex-col gap-3">
          <ol className="m-0 flex list-decimal flex-col gap-1 pl-6">
            {s.ladder.map((r) => {
              const now = r.id === s.step_id
              const locked = needs(r)
              return (
                <li
                  key={r.id}
                  aria-current={now ? 'step' : undefined}
                  className={now ? 'font-bold' : ''}
                >
                  {r.name}
                  {now && ' (now)'}
                  {locked && (
                    <span className="font-normal text-[var(--slate)]"> · Locked: {locked}</span>
                  )}
                  {r.question && (
                    <span className="flex text-sm font-normal text-[var(--slate)]">
                      Ready for this if yes: {r.question}
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
          <p className="m-0">{lastAndBest(s)}</p>
          {upcoming ? (
            <p className="m-0">
              Next: <span className="font-bold">{upcoming.name}</span>
              {upcoming.cue && `. ${upcoming.cue}`}
            </p>
          ) : s.unlock ? (
            <p className="m-0">
              <span className="font-bold">Top for your kit:</span> {s.unlock}.{' '}
              <a href={KIT_HREF} className="font-bold underline">
                My equipment
              </a>
            </p>
          ) : s.ladder[s.ladder.length - 1]?.id !== s.step_id ? (
            <p className="m-0">No step above this one is open to you: each says why above.</p>
          ) : (
            <p className="m-0">This is the last step on the ladder.</p>
          )}

          {ready && upcoming && strength && <p className="m-0">{WAITS}</p>}
          {ready && upcoming && !strength && (
            <div className={actions}>
              <button
                type="button"
                className={primaryInline}
                disabled={busy}
                onClick={() => void press('move-up', s.step_id)}
              >
                Move up to {upcoming.name}
              </button>
              <button
                type="button"
                className={secondary}
                disabled={busy}
                onClick={() => void press('not-yet', s.step_id)}
              >
                Not yet
              </button>
            </div>
          )}

          {!choosing ? (
            <button
              type="button"
              className={secondary + ' self-start'}
              disabled={busy}
              onClick={() => {
                setPicked(s.step_id)
                setNote(null)
                setChoosing(true)
              }}
            >
              Change level
            </button>
          ) : (
            <fieldset className="m-0 flex flex-col gap-2 rounded-xl border-2 border-[var(--line)] p-3">
              <legend className="px-1 font-bold">Choose a level for {s.exercise}</legend>
              {s.ladder.map((r) => (
                <label key={r.id} className="flex min-h-11 items-center gap-3">
                  <input
                    type="radio"
                    name={`level-${s.slug}`}
                    value={r.id}
                    checked={picked === r.id}
                    onChange={() => setPicked(r.id)}
                    className="size-5"
                  />
                  <span>
                    {r.name}
                    {r.id === s.step_id && ' (now)'}
                    {needs(r) && <span className="text-[var(--slate)]"> · Locked: {needs(r)}</span>}
                  </span>
                </label>
              ))}
              {picked !== s.step_id && <p className="m-0">{confirmText(pickedName)}</p>}
              {picked !== s.step_id && pickedLocked && (
                <p className="m-0">{pickedLocked} You can still choose it.</p>
              )}
              <div className={actions}>
                <button
                  type="button"
                  className={primaryInline}
                  disabled={busy || picked === s.step_id}
                  onClick={() => void press('level', picked)}
                >
                  Set level to {pickedName}
                </button>
                <button type="button" className={secondary} onClick={() => setChoosing(false)}>
                  Cancel
                </button>
              </div>
            </fieldset>
          )}
        </div>
      )}
      {note && (
        <p className="m-0" role="status">
          {note}
        </p>
      )}
    </li>
  )
}
