import { useState } from 'react'
import { fetchAiSummary, SignedOutError, type SummaryPeriod } from '../api'
import { card, primaryInline } from '../ui'

export const QUESTION =
  'Review my training over this period: what is working, what is stalling, and what would you ' +
  'change in the next 4 weeks, and why?'

const PERIODS: { value: SummaryPeriod; label: string }[] = [
  { value: '4w', label: 'Last 4 weeks' },
  { value: '12w', label: 'Last 12 weeks' },
  { value: 'all', label: 'Everything' },
]

/**
 * "Copy for my AI" (ADR-0047): a question the person can edit, then their training as Markdown
 * with a link to the guide, for pasting into whichever AI they use. Health data only when
 * ticked. Where the clipboard isn't allowed, the text is shown to copy by hand.
 */
export default function CopyForAI() {
  const [question, setQuestion] = useState(QUESTION)
  const [period, setPeriod] = useState<SummaryPeriod>('4w')
  const [body, setBody] = useState(false)
  const [readiness, setReadiness] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [manual, setManual] = useState<string | null>(null)

  const copy = async () => {
    setNote(null)
    setManual(null)
    let text: string
    try {
      text = `${question.trim()}\n\n${await fetchAiSummary(period, body, readiness)}`
    } catch (error) {
      return setNote(
        error instanceof SignedOutError
          ? 'Your sign-in ended. Sign in again, then copy.'
          : "Couldn't get your training. Check your connection and try again.",
      )
    }
    try {
      await navigator.clipboard.writeText(text)
      setNote('Copied. Paste it into your AI.')
    } catch {
      setManual(text) // no clipboard here (or not allowed): select and copy by hand
    }
  }

  return (
    <section aria-labelledby="your-ai" className={card}>
      <h2 id="your-ai" className="mb-2 text-xl">
        Your AI
      </h2>
      <p>
        Ask the AI you already use about your training. This copies a question and a summary of your
        training, with a link that explains the numbers to it. What you paste is stored by that AI's
        provider, not by us.
      </p>
      <label className="flex flex-col gap-1">
        Question
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
      </label>
      <label className="flex flex-col gap-1">
        Period
        <select value={period} onChange={(e) => setPeriod(e.target.value as SummaryPeriod)}>
          {PERIODS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={body} onChange={(e) => setBody(e.target.checked)} />
        Include body measurements (health data)
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={readiness}
          onChange={(e) => setReadiness(e.target.checked)}
        />
        Include readiness answers (health data)
      </label>
      <p>
        <button type="button" onClick={() => void copy()} className={primaryInline}>
          Copy for my AI
        </button>
      </p>
      {note && <p role="status">{note}</p>}
      {manual && (
        <label className="flex flex-col gap-1">
          Copying isn't allowed here: select all of this and copy it.
          <textarea readOnly value={manual} rows={8} onFocus={(e) => e.target.select()} />
        </label>
      )}
    </section>
  )
}
