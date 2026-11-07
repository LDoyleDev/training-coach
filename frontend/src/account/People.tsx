import { type FormEvent, useCallback, useEffect, useState } from 'react'
import {
  fetchPeople,
  makeInvite,
  makeRecoveryLink,
  type People as Found,
  removeMember,
  revokeInvite,
  SignedOutError,
  StaleSignInError,
} from '../api'
import { card, danger, primaryInline, small } from '../ui'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

/**
 * People (ADR-0059), for the admin while invites are on: members by label and the day they
 * joined, nothing of their data; open invites, each revocable; and a one-time link to make, shown
 * once, to send by any messenger. Removing a member (ADR-0088) deletes everything of theirs, so it
 * asks whether they were told and offered their export, and for the word typed. Hidden for anyone
 * else and while invites are off.
 */
export default function People() {
  const [found, setFound] = useState<Found | null>(null)
  const [label, setLabel] = useState('')
  const [link, setLink] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [removing, setRemoving] = useState<number | null>(null)
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false) // one removal at a time
  const [recovery, setRecovery] = useState<{ name: string; link: string } | null>(null)

  const load = useCallback((signal?: AbortSignal) => {
    fetchPeople(signal)
      .then(setFound)
      .catch(() => {}) // the section stays hidden; the rest of the page still works
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  if (!found) return null
  const full = found.members.length + found.invites.length >= found.max_members

  const failed = (error: unknown) =>
    setNote(
      error instanceof SignedOutError
        ? 'Your sign-in ended. Sign in again, then retry.'
        : error instanceof StaleSignInError
          ? 'For safety, removing someone needs you to confirm it’s you. Try again and confirm ' +
            'with your fingerprint when your phone asks.'
          : "That didn't work. Check your connection and try again.",
    )

  const make = async (event: FormEvent) => {
    event.preventDefault()
    setNote(null)
    try {
      const made = await makeInvite(label.trim())
      if (made === 'full') return setNote('There is no room for another member.')
      setLink(`${window.location.origin}/join#${made.token}`)
      setLabel('')
      load()
    } catch (error) {
      failed(error)
    }
  }

  const remove = async (event: FormEvent, id: number) => {
    event.preventDefault()
    if (busy) return
    setNote(null)
    setBusy(true)
    try {
      setNote((await removeMember(id, confirm)) ? 'Removed.' : 'They had already gone.')
      setRemoving(null)
      setConfirm('')
      load()
    } catch (error) {
      failed(error)
    } finally {
      setBusy(false)
    }
  }

  const recover = async (id: number, name: string) => {
    setNote(null)
    try {
      const made = await makeRecoveryLink(id)
      if (!made) return setNote('They had already gone.')
      setRecovery({ name, link: `${window.location.origin}/signin#${made.token}` })
    } catch (error) {
      failed(error)
    }
  }

  const revoke = async (id: number) => {
    setNote(null)
    try {
      setNote((await revokeInvite(id)) ? 'Invite revoked.' : 'That invite was already used.')
      load()
    } catch (error) {
      failed(error)
    }
  }

  return (
    <section aria-labelledby="people" className={`${card} flex flex-col gap-3`}>
      <h2 id="people" className="m-0 text-xl">
        People
      </h2>
      <p className="m-0">
        {found.members.length} of {found.max_members} members. You see their names and when they
        joined, nothing of their training or health.
      </p>
      {found.members.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {found.members.map((m) => {
            const name = m.label ?? 'No name given'
            return (
              <li key={m.id} className="flex flex-col gap-2">
                <span className="flex items-center gap-2">
                  <span className="flex-1">
                    {name}, joined {day(m.joined)}
                  </span>
                  <button
                    type="button"
                    className={small}
                    onClick={() => void recover(m.id, m.label ?? 'them')}
                  >
                    Recovery link for {m.label ?? 'member'}
                  </button>
                  {removing !== m.id && (
                    <button
                      type="button"
                      className={small}
                      onClick={() => {
                        setRemoving(m.id)
                        setConfirm('')
                      }}
                    >
                      Remove {m.label ?? 'member'}
                    </button>
                  )}
                </span>
                {removing === m.id && (
                  <form onSubmit={(e) => void remove(e, m.id)} className="flex flex-col gap-2">
                    <p className="m-0">
                      Have you told {m.label ?? 'them'} and offered them their export first?
                      Removing deletes their account and everything of theirs at once.
                    </p>
                    <label className="flex flex-col gap-1">
                      <span>
                        Type <strong>remove</strong> to confirm
                      </span>
                      <input
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        autoComplete="off"
                        autoCapitalize="none"
                        spellCheck={false}
                      />
                    </label>
                    <span className="flex gap-2">
                      <button
                        type="submit"
                        disabled={confirm !== 'remove' || busy}
                        className={danger}
                      >
                        Remove {m.label ?? 'member'}
                      </button>
                      <button type="button" className={small} onClick={() => setRemoving(null)}>
                        Keep them
                      </button>
                    </span>
                  </form>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {recovery && (
        <div className="flex flex-col gap-1">
          <p className="m-0">
            Hand this to {recovery.name} yourself, the way you sent the invite, only if they asked
            for it. It works once, for 24 hours, on their own device, and signs out their other
            devices. They are told it was made, and Account shows them it was used.
          </p>
          <input readOnly value={recovery.link} aria-label="Recovery link" className="min-h-11" />
          <button
            type="button"
            className={`${small} self-start`}
            onClick={() => void navigator.clipboard?.writeText(recovery.link)}
          >
            Copy the recovery link
          </button>
        </div>
      )}
      {found.invites.length > 0 && (
        <>
          <h3 className="m-0 text-lg">Open invites</h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {found.invites.map((i) => (
              <li key={i.id} className="flex items-center gap-2">
                <span className="flex-1">
                  {i.label ?? 'No name given'}, until {day(i.expires_at)}
                </span>
                <button type="button" className={small} onClick={() => void revoke(i.id)}>
                  Revoke {i.label ?? 'invite'}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {link && (
        <div className="flex flex-col gap-1">
          <p className="m-0">
            Send this link yourself, by any messenger. It works once, for 72 hours, and is shown
            only now.
          </p>
          <input readOnly value={link} aria-label="Invite link" className="min-h-11" />
          <button
            type="button"
            className={`${small} self-start`}
            onClick={() => void navigator.clipboard?.writeText(link)}
          >
            Copy the link
          </button>
        </div>
      )}
      {!full && (
        <form onSubmit={(e) => void make(e)} className="flex flex-col gap-2">
          <label className="flex flex-col gap-1">
            <span>Who is it for? Only you see this name.</span>
            <input
              type="text"
              maxLength={40}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="min-h-11"
            />
          </label>
          <button type="submit" className={`${primaryInline} self-start`}>
            Make an invite
          </button>
        </form>
      )}
      {note && <p role="status">{note}</p>}
    </section>
  )
}
