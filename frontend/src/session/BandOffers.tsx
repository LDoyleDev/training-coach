import { useEffect, useState } from 'react'
import {
  type Answer,
  type BandOffer,
  type Clash,
  countBandOffer,
  dismissBandOffer,
  fetchBandOffers,
  SignedOutError,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import ClashQuestion from './ClashQuestion'
import { actions, card, primaryInline, secondary } from '../ui'

const day = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short' })

/**
 * Workouts from the band, to count as cardio with one tap (ADR-0055): "Walk, 46 min, 38 in
 * zone 2 - count it?". Counting goes through the cardio log, so Undo takes it back.
 * ``onCounted`` hears what to say; the page then reloads today and the Undo bar.
 */
export default function BandOffers({ onCounted }: { onCounted: (text: string) => void }) {
  const [today] = useState(() => new Date().toLocaleDateString('en-CA')) // YYYY-MM-DD, here
  const [offers, setOffers] = useState<BandOffer[]>([])
  const [busy, setBusy] = useState<number | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [loads, setLoads] = useState(0)
  // Counting it would complete a session on a day that has one (ADR-0060): asked first.
  const [question, setQuestion] = useState<{
    id: number
    clash: Clash
    taken: Clash | null
  } | null>(null)

  useEffect(() => {
    const abort = new AbortController()
    fetchBandOffers(abort.signal)
      .then(setOffers)
      .catch(() => {}) // the page works without them
    return () => abort.abort()
  }, [loads])

  const answer = async (offer: BandOffer, count: boolean, reply?: Answer) => {
    setBusy(offer.id)
    setNote(null)
    setSignedOut(false)
    try {
      if (!count) {
        await dismissBandOffer(offer.id)
        setOffers((all) => all.filter((o) => o.id !== offer.id))
        return
      }
      const result = await countBandOffer(offer.id, reply)
      if (typeof result === 'object' && 'clash' in result) {
        if (result.clash.moving && question) setQuestion({ ...question, taken: result.clash })
        else setQuestion({ id: offer.id, clash: result.clash, taken: null })
        return
      }
      if (typeof result === 'object' && 'problem' in result) {
        setNote(result.problem) // the question stays: pick another answer
        return
      }
      setQuestion(null)
      if (result === 'gone') setNote('That workout isn’t on offer any more.')
      else if (result === 'stale') setNote('Today’s session changed meanwhile. Try again.')
      else {
        const target = result.week.zone2_target
        const week = `Zone 2 this week: ${result.week.zone2}${target ? ` of ${target[0]}-${target[1]}` : ''} min.`
        onCounted(`Counted${result.planned ? ', and today’s session is done' : ''}. ${week}`)
      }
      setLoads((n) => n + 1)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("That didn't work. Check your connection and try again.")
    } finally {
      setBusy(null)
    }
  }

  if (offers.length === 0 && !note && !signedOut) return null
  return (
    <section aria-label="From your band" className="flex flex-col gap-2">
      {offers.map((offer) => (
        <div key={offer.id} className={card}>
          <p className="m-0">
            {offer.on === today ? '' : `${day(offer.on)}: `}
            {offer.text}
          </p>
          {question?.id === offer.id && (
            <div className="mt-2">
              <ClashQuestion
                clash={question.clash}
                taken={question.taken}
                busy={busy !== null}
                onAnswer={(reply) => void answer(offer, true, reply)}
                onCancel={() => setQuestion(null)}
              />
            </div>
          )}
          <p className={`${actions} mt-2 mb-0`}>
            <button
              type="button"
              className={primaryInline}
              disabled={busy !== null}
              onClick={() => void answer(offer, true)}
            >
              Count it
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy !== null}
              onClick={() => void answer(offer, false)}
            >
              Not this one
            </button>
          </p>
        </div>
      ))}
      {note && (
        <p role="status" className="status">
          {note}
        </p>
      )}
      {signedOut && <SignedOutNotice />}
    </section>
  )
}
