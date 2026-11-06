import { useEffect, useState } from 'react'
import { fetchPlanImport, savePlanImport, SignedOutError, type PlanImport } from '../api'
import { card, primaryInline } from '../ui'

/** A change to plan.toml waiting for the owner (ADR-0073): the seed no longer changes anyone's
 * sessions, so this lists what would change, and saving makes it one version. Hidden when
 * nothing waits, and for everyone else. */
export default function PlanImportCard() {
  const [found, setFound] = useState<PlanImport | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchPlanImport(controller.signal)
      .then(setFound)
      .catch(() => setFound(null)) // the plan below still shows
    return () => controller.abort()
  }, [])

  if (note === null && (found === null || found.changes.length === 0)) return null

  const save = async () => {
    setBusy(true)
    setNote(null)
    try {
      const saved = await savePlanImport()
      if (saved === 'blocked') {
        setFound(await fetchPlanImport())
        return
      }
      setFound(null)
      setNote('Saved. Your plan has the changes from today. Reload to see them below.')
    } catch (error) {
      setNote(
        error instanceof SignedOutError
          ? 'Your sign-in ended. Sign in again, then retry.'
          : "That didn't work. Check your connection and try again.",
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="plan-import" className={`${card} flex flex-col gap-3`}>
      <h2 id="plan-import" className="m-0 text-xl font-bold">
        Changes to your plan
      </h2>
      {found && found.changes.length > 0 && (
        <>
          <p className="m-0 text-[var(--slate)]">
            The plan file has changed. Nothing happens to your plan until you save.
          </p>
          <ul className="m-0 flex flex-col gap-1 pl-5">
            {found.changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
          {found.blocked ? (
            <p className="m-0">{found.blocked}</p>
          ) : (
            <button
              type="button"
              className={`${primaryInline} self-start`}
              disabled={busy}
              onClick={() => void save()}
            >
              Save as a new version
            </button>
          )}
        </>
      )}
      {note && (
        <p role="status" className="status m-0">
          {note}
        </p>
      )}
    </section>
  )
}
