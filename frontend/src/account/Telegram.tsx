import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelTelegramLink,
  checkTelegramCode,
  type CodeRefusal,
  confirmTelegram,
  fetchTelegram,
  makeTelegramLink,
  SignedOutError,
  StaleSignInError,
  type TelegramStatus,
  unlinkTelegram,
} from '../api'
import { card, danger, primaryInline, small } from '../ui'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

const REFUSED: Record<CodeRefusal, string> = {
  wrong: 'That’s not the code. Check the bot’s message and type it again.',
  ended: 'Too many wrong codes, so that link has ended. Make a new one.',
  gone: 'That link has expired. Make a new one.',
  conflict: 'That Telegram account can’t be connected. Cancel and make a new link.',
}

const stateOf = (status: TelegramStatus | null) =>
  !status
    ? null
    : status.set_on_server
      ? 'server'
      : status.connected
        ? 'connected'
        : status.pending
          ? `pending:${status.pending.expires_at}:${status.pending.claims}`
          : 'none'

/**
 * Telegram on Account (ADR-0089). A member connects it: Connect makes a link that opens the bot,
 * the bot sends a code, and the code typed here shows the Telegram name before Confirm. A link
 * someone else opened too can't be confirmed. The owner's account is set on the server.
 */
export default function Telegram() {
  const [found, setFound] = useState<TelegramStatus | null>(null)
  const [url, setUrl] = useState<string | null>(null) // the link, shown only when made
  const [code, setCode] = useState('')
  const [name, setName] = useState<string | null>(null) // whose code it is, once it matches
  const [unlinking, setUnlinking] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const shown = useRef<string | null>(null) // which of the card's states is showing
  const load = useCallback((signal?: AbortSignal, back = false) => {
    fetchTelegram(signal)
      .then((status) => {
        // Back on the page and the card has moved on (the link expired, say): an error from
        // before is about something no longer there.
        if (back && stateOf(status) !== shown.current) setNote(null)
        shown.current = stateOf(status)
        setFound(status)
        if (!status?.pending) setUrl(null)
      })
      .catch(() => {}) // the section stays as it was; the rest of the page still works
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    // Back from Telegram: how many opened the link may have changed.
    const back = () => load(undefined, true)
    window.addEventListener('focus', back)
    return () => {
      controller.abort()
      window.removeEventListener('focus', back)
    }
  }, [load])

  if (!found) return null

  const failed = (error: unknown) =>
    setNote(
      error instanceof SignedOutError
        ? 'Your sign-in ended. Sign in again, then retry.'
        : error instanceof StaleSignInError
          ? 'For safety, this needs you to confirm it’s you. Try again and confirm with your ' +
            'fingerprint when your phone asks.'
          : "That didn't work. Check your connection and try again.",
    )

  const act = async (step: () => Promise<void>) => {
    if (busy) return
    setBusy(true)
    setNote(null)
    try {
      await step()
    } catch (error) {
      failed(error)
    } finally {
      setBusy(false)
    }
  }

  const refused = (why: CodeRefusal) => {
    setName(null)
    setNote(REFUSED[why])
    if (why !== 'wrong') load()
  }

  const connect = () =>
    act(async () => {
      const made = await makeTelegramLink()
      if (made === 'off') return setNote('The Telegram bot is off just now. Try again later.')
      if (made !== 'connected') setUrl(made.url)
      setCode('')
      setName(null)
      load()
    })

  const cancel = () =>
    act(async () => {
      await cancelTelegramLink()
      setCode('')
      setName(null)
      load()
    })

  const check = (event: FormEvent) => {
    event.preventDefault()
    void act(async () => {
      const answer = await checkTelegramCode(code)
      if (typeof answer === 'string') return refused(answer)
      setName(answer.name)
    })
  }

  const confirm = () =>
    act(async () => {
      const answer = await confirmTelegram(code)
      if (answer !== 'connected') return refused(answer)
      setCode('')
      setName(null)
      load()
    })

  const unlink = () =>
    act(async () => {
      await unlinkTelegram()
      setUnlinking(false)
      load()
    })

  const pending = found.pending
  const shared = (pending?.claims ?? 0) > 1

  return (
    <section aria-labelledby="telegram" className={card}>
      <h2 id="telegram" className="mb-2 text-xl">
        Telegram
      </h2>
      {found.set_on_server ? (
        <p className="m-0">Your Telegram account is set on the server.</p>
      ) : found.connected ? (
        <div className="flex flex-col gap-2">
          <p className="m-0">
            Connected as {found.name ?? 'your Telegram account'}
            {found.since ? ` since ${day(found.since)}` : ''}.
          </p>
          {unlinking ? (
            <>
              <p className="m-0">
                Unlink Telegram? The bot stops answering you there and sends no more reminders.
              </p>
              <span className="flex gap-2">
                <button type="button" className={danger} disabled={busy} onClick={unlink}>
                  Unlink Telegram
                </button>
                <button type="button" className={small} onClick={() => setUnlinking(false)}>
                  Keep it
                </button>
              </span>
            </>
          ) : (
            <button
              type="button"
              className={`${small} self-start`}
              onClick={() => setUnlinking(true)}
            >
              Unlink
            </button>
          )}
        </div>
      ) : pending ? (
        <div className="flex flex-col gap-2">
          {url ? (
            <a href={url} target="_blank" rel="noopener noreferrer" className="self-start">
              Open Telegram
            </a>
          ) : (
            pending.claims === 0 && (
              // Back on the page (a reload): only the link's hash is kept, so it can't be shown
              // again. Nobody has opened it, so a new one replaces it.
              <>
                <p className="m-0">
                  The link to the bot is shown only once, when it&apos;s made. If you didn&apos;t
                  open it, make a new one.
                </p>
                <button
                  type="button"
                  className={`${primaryInline} self-start`}
                  disabled={busy}
                  onClick={connect}
                >
                  Make a new link
                </button>
              </>
            )
          )}
          <p className="m-0">
            The bot sends you a 6-digit code. Type it here. Type only the code the bot sent you
            after you tapped the link yourself. Never type a code someone sends you. If you
            didn&apos;t open the bot just now, tap Cancel.
          </p>
          <p className="m-0">
            Opened in Telegram: {pending.claims} {pending.claims === 1 ? 'time' : 'times'}.
          </p>
          {shared ? (
            <p role="alert" className="status-error m-0">
              Someone else used this link too: cancel it and make a new one.
            </p>
          ) : (
            <form onSubmit={check} className="flex flex-col gap-2">
              <label className="flex flex-col gap-1">
                <span>Code from the bot</span>
                <input
                  value={code}
                  onChange={(event) => {
                    setCode(event.target.value.replace(/\D/g, '').slice(0, 6))
                    setName(null)
                  }}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                />
              </label>
              {name === null ? (
                <button
                  type="submit"
                  className={`${small} self-start`}
                  disabled={code.length !== 6 || busy}
                >
                  Check the code
                </button>
              ) : (
                <>
                  <p className="m-0">
                    That code went to the Telegram account named <strong>{name}</strong>. Is that
                    you?
                  </p>
                  <button
                    type="button"
                    className={`${primaryInline} self-start`}
                    disabled={busy}
                    onClick={confirm}
                  >
                    Confirm
                  </button>
                </>
              )}
            </form>
          )}
          <button type="button" className={`${small} self-start`} disabled={busy} onClick={cancel}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="m-0">
            Connect Telegram to get your reminders there and log by message or voice.
          </p>
          <button
            type="button"
            className={`${primaryInline} self-start`}
            disabled={busy}
            onClick={connect}
          >
            Connect Telegram
          </button>
        </div>
      )}
      {note && (
        <p role="alert" className="status-error mb-0">
          {note}
        </p>
      )}
    </section>
  )
}
