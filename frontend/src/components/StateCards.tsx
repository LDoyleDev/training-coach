import { card, primaryInline } from '../ui'

/** Signed out: what to do, as a button that comes back to this page after signing in. */
export function SignInCard({ text }: { text: string }) {
  const here = window.location.pathname
  return (
    <div className={card}>
      <p className="m-0 mb-3">{text}</p>
      <a
        href={`/signin?next=${encodeURIComponent(here)}`}
        className={`${primaryInline} inline-flex items-center no-underline`}
      >
        Sign in
      </a>
    </div>
  )
}

/** Couldn't load: say so, with a button to try again. */
export function RetryCard({ text }: { text: string }) {
  return (
    <div className={card}>
      <p className="status-error m-0 mb-3" role="alert">
        {text}
      </p>
      <button type="button" onClick={() => window.location.reload()}>
        Try again
      </button>
    </div>
  )
}
