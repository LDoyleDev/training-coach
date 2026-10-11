import { useState } from 'react'
import {
  changeToday,
  fetchChoices,
  pickToday,
  SignedOutError,
  type Changed,
  type Choices,
  type TodayChange,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { actions, card, secondary, small } from '../ui'

/** What a change did, in the words the bot uses for the same buttons. */
function changedText(change: TodayChange | 'pick', result: Changed, shown: string): string {
  const name = result.session
  if (change === 'rest' && result.advanced) return `${name} logged as a rest day. Enjoy it.`
  if (change === 'rest')
    return `Rest today. ${name} moves to tomorrow and the rest of the week shifts a day.`
  if (change === 'push') return `${name} moves to tomorrow and the rest of the week shifts a day.`
  if (change === 'next') return `${name} today. ${shown} moves to tomorrow.`
  return `${name} today. The plan's next session stays next.`
}

/**
 * "Change today" (ux-flow-plan C2): Rest today, Swap or Push to tomorrow for the session the
 * page shows, the same as the morning message's buttons. One tap opens it; the page updates
 * in place with what the server answers.
 */
export default function ChangeToday({
  templateId,
  name,
  onChanged,
  onStale,
}: {
  templateId: number
  name: string
  onChanged: (result: Changed, text: string) => void
  onStale: () => void
}) {
  const [open, setOpen] = useState(false)
  const [choices, setChoices] = useState<Choices | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)

  const run = async (change: TodayChange | 'pick', send: () => Promise<Changed | 'stale'>) => {
    if (busy) return
    setBusy(true)
    setNote(null)
    setSignedOut(false)
    try {
      const result = await send()
      if (result === 'stale') return onStale()
      onChanged(result, changedText(change, result, name))
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't change today. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const swap = async () => {
    setNote(null)
    setSignedOut(false)
    try {
      const found = await fetchChoices()
      if (found === 'stale') return onStale()
      setChoices(found)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("Couldn't load the sessions. Check your connection and try again.")
    }
  }

  if (!open)
    return (
      <button
        type="button"
        className={`${secondary} w-full`}
        aria-expanded={false}
        onClick={() => setOpen(true)}
      >
        Change today
      </button>
    )

  return (
    <section aria-labelledby="change-today" className={`${card} flex flex-col gap-3`}>
      <h2 id="change-today" className="m-0 text-lg font-bold">
        Change today
      </h2>
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
      {choices === null ? (
        <>
          <div className="grid grid-cols-1 gap-2 min-[360px]:grid-cols-3">
            <button
              type="button"
              className={small}
              disabled={busy}
              onClick={() => run('rest', () => changeToday('rest', templateId))}
            >
              Rest today
            </button>
            <button type="button" className={small} disabled={busy} onClick={swap}>
              Swap session
            </button>
            <button
              type="button"
              className={small}
              disabled={busy}
              onClick={() => run('push', () => changeToday('push', templateId))}
            >
              Push to tomorrow
            </button>
          </div>
          <button
            type="button"
            className="min-h-11 font-bold text-[var(--bell-ink)] underline"
            aria-expanded
            onClick={() => setOpen(false)}
          >
            Close
          </button>
        </>
      ) : (
        <>
          {choices.next && (
            <button
              type="button"
              className={small}
              disabled={busy}
              onClick={() => run('next', () => changeToday('next', templateId))}
            >
              Do {choices.next.name} first, {name} tomorrow
            </button>
          )}
          <p className="m-0 text-sm text-[var(--slate)]">Or do another session today:</p>
          <div className={actions}>
            {choices.others.map((choice) => (
              <button
                key={choice.template_id}
                type="button"
                className={small}
                disabled={busy}
                onClick={() => run('pick', () => pickToday(templateId, choice.template_id))}
              >
                {choice.name}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="min-h-11 font-bold text-[var(--bell-ink)] underline"
            onClick={() => setChoices(null)}
          >
            Back
          </button>
        </>
      )}
    </section>
  )
}
