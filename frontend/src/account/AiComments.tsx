import { type FormEvent, useEffect, useState } from 'react'
import {
  type AiOptions,
  type AiStatus,
  fetchAiStatus,
  type KeyCheck,
  removeAiKey,
  setAiOptions,
  SignedOutError,
  StaleSignInError,
  storeAiKey,
  testAiKey,
} from '../api'

const CHECKS: Record<KeyCheck, string> = {
  works: 'The key works.',
  refused: "Groq didn't accept that key. Copy it again from console.groq.com/keys.",
  unreachable: "Couldn't reach Groq to check the key. Try again in a minute.",
}

function failure(error: unknown): string {
  if (error instanceof SignedOutError) return 'Your sign-in ended. Sign in again, then retry.'
  if (error instanceof StaleSignInError)
    return 'Sign in again to add a key (it needs a fresh sign-in).'
  return "That didn't work. Check your connection and try again."
}

/**
 * AI comments from the person's own Groq key (ADR-0047 B). The key goes in once: it is checked
 * with Groq, stored encrypted and never shown again, only its last four characters. Health
 * data stays out of comments unless ticked.
 */
export default function AiComments() {
  const [ai, setAi] = useState<AiStatus | null>(null)
  const [key, setKey] = useState('')
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchAiStatus(controller.signal)
      .then(setAi)
      .catch(() => {}) // the section stays hidden; the rest of the page still works
    return () => controller.abort()
  }, [])

  if (!ai) return null

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setNote(null)
    try {
      const result = await storeAiKey(key.trim())
      if (typeof result === 'string') return setNote(CHECKS[result])
      setAi(result)
      setKey('')
      setNote('Saved. Your key is stored encrypted and won’t be shown again.')
    } catch (error) {
      setNote(failure(error))
    }
  }

  const choose = async (change: Partial<AiOptions>) => {
    setNote(null)
    try {
      setAi(
        await setAiOptions({
          enabled: ai.enabled,
          body: ai.body,
          readiness: ai.readiness,
          ...change,
        }),
      )
    } catch (error) {
      setNote(failure(error))
    }
  }

  const test = async () => {
    setNote(null)
    try {
      setNote(CHECKS[await testAiKey()])
      setAi((await fetchAiStatus()) ?? ai) // a refused key is now marked, a working one cleared
    } catch (error) {
      setNote(failure(error))
    }
  }

  const remove = async () => {
    setNote(null)
    try {
      await removeAiKey()
      setAi({ ...ai, connected: false, ends_in: null, enabled: false, failed: false })
      setNote('Removed. Delete the key at console.groq.com/keys too if you no longer use it.')
    } catch (error) {
      setNote(failure(error))
    }
  }

  return (
    <section aria-labelledby="ai-comments">
      <h2 id="ai-comments">AI comments from your own key</h2>
      {!ai.available ? (
        <p>AI comments aren’t set up on this server yet.</p>
      ) : (
        <>
          <p>
            Get a short AI comment with your weekly review, from your own free Groq key. Your
            training summary is sent to Groq under your account; nothing is sent with anyone else’s
            key. Comments are suggestions: they never change your plan.
          </p>
          {ai.connected && (
            <>
              <p>
                Key ending in <strong>…{ai.ends_in}</strong>
                {ai.failed && ' stopped working. Enter it again, or a new one.'}
              </p>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ai.enabled}
                  onChange={(e) => void choose({ enabled: e.target.checked })}
                />
                Send me AI comments
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ai.body}
                  onChange={(e) => void choose({ body: e.target.checked })}
                />
                Comments may see body measurements (health data)
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={ai.readiness}
                  onChange={(e) => void choose({ readiness: e.target.checked })}
                />
                Comments may see readiness answers (health data)
              </label>
              <p className="flex gap-2">
                <button type="button" onClick={() => void test()}>
                  Test the key
                </button>
                <button type="button" onClick={() => void remove()}>
                  Remove the key
                </button>
              </p>
            </>
          )}
          <form onSubmit={(e) => void save(e)} className="flex flex-col gap-1">
            <label className="flex flex-col gap-1">
              {ai.connected
                ? 'Replace with a new Groq key'
                : 'Groq API key (from console.groq.com/keys)'}
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="gsk_…"
              />
            </label>
            <p>
              <button type="submit" disabled={!key.trim()}>
                Check and save the key
              </button>
            </p>
          </form>
        </>
      )}
      {note && <p role="status">{note}</p>}
    </section>
  )
}
