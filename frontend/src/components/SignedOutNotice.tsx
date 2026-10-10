import { primaryInline } from '../ui'

/** Shown when the sign-in ends while a page is open (a change answered 401): what was typed
 * stays on the page, so signing in again in another tab and retrying loses nothing. */
export default function SignedOutNotice() {
  const here = window.location.pathname
  return (
    <div role="alert" className="rounded-2xl border-2 border-[var(--bell-ink)] p-4">
      <p className="m-0 mb-3 text-[var(--bell-ink)]">
        Your sign-in has ended. Sign in again (it opens in a new tab), then try again here: nothing
        you entered is lost.
      </p>
      <a
        href={`/signin?next=${encodeURIComponent(here)}`}
        target="_blank"
        rel="noopener"
        className={`${primaryInline} inline-flex items-center no-underline`}
      >
        Sign in again
      </a>
    </div>
  )
}
