import { useEffect, useState } from 'react'
import { fetchUndo, SignedOutError, undoChange, type Undone, type UndoOffer } from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import { card, danger, secondary, small } from '../ui'

/**
 * Undo the last change (ux-flow-plan C3, ADR-0048): a rest day, a push, a swap or a saved
 * log. "Undo: <what>" asks for a confirm tap first, and sends the change's id, so an old
 * page can't take back a newer change. ``offer`` is what a change just answered; without
 * it, the component asks the server. Nothing shows when there is nothing to undo.
 */
export default function Undo({
  offer: given,
  onUndone,
}: {
  offer?: UndoOffer | null
  onUndone: (done: Undone) => void
}) {
  const [offer, setOffer] = useState<UndoOffer | null>(given ?? null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [refused, setRefused] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)

  useEffect(() => {
    if (given !== undefined) return
    let live = true
    fetchUndo()
      .then((found) => live && setOffer(found.offer ?? null))
      .catch(() => {}) // no offer: the page works without it
    return () => {
      live = false
    }
  }, [given])

  const undo = async () => {
    if (offer === null || busy) return
    setBusy(true)
    setSignedOut(false)
    try {
      const result = await undoChange(offer.event_id)
      setConfirming(false)
      setOffer(null)
      if (typeof result === 'string') setRefused(result)
      else onUndone(result)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setRefused("Couldn't undo. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {refused && (
        <p role="status" className="status">
          {refused}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
      {offer && !confirming && (
        <button
          type="button"
          className={`${small} self-start text-left`}
          onClick={() => {
            setRefused(null)
            setConfirming(true)
          }}
        >
          Undo: {offer.what}
        </button>
      )}
      {offer && confirming && (
        <div role="group" aria-label="Confirm undo" className={`${card} flex flex-col gap-3`}>
          <p className="m-0 font-bold">Undo {offer.what}?</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={danger} disabled={busy} onClick={undo}>
              Undo it
            </button>
            <button type="button" className={secondary} onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        </div>
      )}
    </>
  )
}
