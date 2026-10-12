import { useEffect, useState } from 'react'
import {
  type Answer,
  type Clash,
  discardProposal,
  fetchProposals,
  type Proposal,
  saveProposal,
  SignedOutError,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import ClashQuestion from './ClashQuestion'
import { actions, card, primaryInline, secondary } from '../ui'

const GONE = 'That proposal has gone: it expired after 24 hours, or its app was disconnected.'

/**
 * Logs a connected AI proposed (ADR-0058): "From “Claude”: ..." with Save and Discard. Nothing
 * is saved until Save; the same proposal in Telegram is then answered "already saved". The
 * app's name is its own claim, shown as text. A body measurement it would overwrite is named
 * here (and in Telegram), never to the AI. Saving goes through the normal log, so Undo
 * takes a workout back: ``onSaved`` hears what to say and the page reloads today and Undo.
 * One for a day that already has its session asks first (ADR-0060); it waits until answered.
 */
export default function Proposals({ onSaved }: { onSaved: (text: string) => void }) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [loads, setLoads] = useState(0)
  const [question, setQuestion] = useState<{
    token: string
    clash: Clash
    taken: Clash | null
  } | null>(null)

  useEffect(() => {
    const abort = new AbortController()
    fetchProposals(abort.signal)
      .then(setProposals)
      .catch(() => {}) // the page works without them
    return () => abort.abort()
  }, [loads])

  const answer = async (proposal: Proposal, save: boolean, reply?: Answer) => {
    setBusy(proposal.token)
    setNote(null)
    setSignedOut(false)
    try {
      if (!save) {
        await discardProposal(proposal.token)
        setNote('Discarded. Nothing was saved.')
      } else {
        const result = await saveProposal(proposal.token, reply)
        if (typeof result === 'object' && 'clash' in result) {
          if (result.clash.moving && question) setQuestion({ ...question, taken: result.clash })
          else setQuestion({ token: proposal.token, clash: result.clash, taken: null })
          return
        }
        if (typeof result === 'object' && 'problem' in result) {
          setNote(result.problem) // the question stays: pick another answer
          return
        }
        setQuestion(null)
        if (result === 'gone') setNote(GONE)
        else if (result === 'saved') setNote('That was already saved.')
        else if (result === 'discarded') setNote('That was already discarded. Nothing was saved.')
        else if ('changed' in result)
          setNote(`Not saved: ${result.changed}. Ask your AI again if you want it.`)
        else onSaved(`Saved: ${result.summary}.`)
      }
      setLoads((n) => n + 1)
    } catch (error) {
      if (error instanceof SignedOutError) setSignedOut(true)
      else setNote("That didn't work. Check your connection and try again.")
    } finally {
      setBusy(null)
    }
  }

  if (proposals.length === 0 && !note && !signedOut) return null
  return (
    <section aria-label="Proposed by your AI" className="flex flex-col gap-2">
      {proposals.map((proposal) => (
        <div key={proposal.token} className={card}>
          <p className="m-0 break-words">
            From <strong>“{proposal.source}”</strong>: {proposal.summary}
          </p>
          {proposal.replaces && <p className="m-0 mt-1 font-bold">{proposal.replaces}.</p>}
          {question?.token === proposal.token && (
            <div className="mt-2">
              <ClashQuestion
                clash={question.clash}
                taken={question.taken}
                busy={busy !== null}
                onAnswer={(reply) => void answer(proposal, true, reply)}
                onCancel={() => setQuestion(null)}
              />
            </div>
          )}
          <p className="m-0 mt-1 text-sm text-[var(--slate)]">
            Nothing is saved until you tap Save.
          </p>
          <p className={`${actions} mt-2 mb-0`}>
            <button
              type="button"
              className={primaryInline}
              disabled={busy !== null}
              onClick={() => void answer(proposal, true)}
            >
              Save
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy !== null}
              onClick={() => void answer(proposal, false)}
            >
              Discard
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
