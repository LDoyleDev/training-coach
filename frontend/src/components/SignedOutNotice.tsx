/** Shown when the sign-in ends while a page is open (a change answered 401): what was typed
 * stays on the page, so signing in again in another tab and retrying loses nothing. */
export default function SignedOutNotice() {
  return (
    <p role="alert" className="status status-error">
      Your sign-in has ended.{' '}
      <a href="/signin" target="_blank" rel="noopener">
        Sign in again
      </a>{' '}
      (it opens in a new tab), then try again here: nothing you entered is lost.
    </p>
  )
}
