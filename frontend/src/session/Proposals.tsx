import { useEffect, useState } from 'react'
import {
  type Answer,
  type Clash,
  discardProposal,
  fetchProposals,
  type Proposal,
  type ProposalKind,
  saveProposal,
  SignedOutError,
} from '../api'
import SignedOutNotice from '../components/SignedOutNotice'
import ClashQuestion from './ClashQuestion'
import { actions, card, primaryInline, secondary } from '../ui'

const chip = (on: boolean) =>
  'min-h-11 rounded-full border-2 px-2 font-bold ' +
  (on
    ? 'border-[var(--bell-ink)] bg-[var(--bell-ink)] text-[var(--chalk)]'
    : 'border-[var(--ink)] text-[var(--ink)]')

/** The two kinds a cardio proposal can be saved as; the person picks one (ADR-0067). */
const KINDS: { kind: ProposalKind; label: string }[] = [
  { kind: 'zone2', label: 'Zone 2' },
  { kind: 'moderate-cardio', label: 'Moderate' },
]

/** A kind's button: filled once picked, a dashed outline while it is only suggested. */
const kindChip = (on: boolean, suggested: boolean) =>
  on
    ? chip(true)
    : 'min-h-11 rounded-full border-2 px-2 font-bold ' +
      (suggested
        ? 'border-dashed border-[var(--bell-ink)] text-[var(--bell-ink)]'
        : 'border-[var(--ink)] text-[var(--ink)]')

const GONE = 'That proposal has gone: it expired after 24 hours, or its app was disconnected.'

/**
 * Logs a connected AI proposed (ADR-0058): "From “Claude”: ..." with Save and Discard. Nothing
 * is saved until Save; the same proposal in Telegram is then answered "already saved". The
 * app's name is its own claim, shown as text. A body measurement it would overwrite is named
 * here (and in Telegram), never to the AI. Saving goes through the normal log, so Undo
 * takes a workout back: ``onSaved`` hears what to say and the page reloads today and Undo.
 * One for a day that already has its session asks first (ADR-0060); it waits until answered.
 * A cardio one (a run read from a screenshot, say) asks how it felt, 1 to 10, before Save, as
 * the cardio form does: the AI never sends that, only the person knows it (ADR-0067). The person
 * also picks zone 2 or moderate: the coach only suggests one, from their own heart-rate zones
 * or the AI's hint, and says why (ADR-0067, 2026-10-24).
 */
export default function Proposals({ onSaved }: { onSaved: (text: string) => void }) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const [loads, setLoads] = useState(0)
  const [efforts, setEfforts] = useState<Record<string, number>>({})
  const [kinds, setKinds] = useState<Record<string, ProposalKind>>({})
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
        const result = await saveProposal(proposal.token, reply, {
          effort: efforts[proposal.token],
          cardio: kinds[proposal.token],
        })
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

  /** What a cardio one still needs before Save, as the button's words; null when ready. */
  const unpicked = (proposal: Proposal): string | null => {
    if (proposal.kind !== 'cardio') return null
    if (!kinds[proposal.token]) return 'Pick zone 2 or moderate to save'
    return efforts[proposal.token] ? null : 'Pick how it felt to save'
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
          {proposal.kind === 'cardio' && (
            <fieldset className="mt-2 flex flex-col gap-2 border-0 p-0">
              <legend className="mb-2 font-bold">Zone 2 or moderate: you pick</legend>
              {proposal.suggestion && <p className="m-0">{proposal.suggestion}.</p>}
              <div className="grid grid-cols-2 gap-2">
                {KINDS.map(({ kind, label }) => (
                  <button
                    key={kind}
                    type="button"
                    aria-pressed={kinds[proposal.token] === kind}
                    className={kindChip(
                      kinds[proposal.token] === kind,
                      !kinds[proposal.token] && proposal.suggested === kind,
                    )}
                    onClick={() => setKinds({ ...kinds, [proposal.token]: kind })}
                  >
                    {label}
                    {proposal.suggested === kind ? ' (suggested)' : ''}
                  </button>
                ))}
              </div>
            </fieldset>
          )}
          {proposal.kind === 'cardio' && (
            <fieldset className="mt-2 flex flex-col gap-2 border-0 p-0">
              <legend className="mb-2 font-bold">How it felt, 1 (very easy) to 10 (all out)</legend>
              <div className="grid grid-cols-5 gap-2">
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    type="button"
                    aria-pressed={efforts[proposal.token] === n}
                    aria-label={`Effort ${n}`}
                    className={chip(efforts[proposal.token] === n)}
                    onClick={() => setEfforts({ ...efforts, [proposal.token]: n })}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </fieldset>
          )}
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
              disabled={busy !== null || unpicked(proposal) !== null}
              onClick={() => void answer(proposal, true)}
            >
              {unpicked(proposal) ?? 'Save'}
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
