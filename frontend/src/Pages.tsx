import Account from './Account'
import BodyTabs from './body/BodyTabs'
import ConnectPage from './connect/ConnectPage'
import HomePage from './home/HomePage'
import PlanPage from './plan/PlanPage'
import ProgressPage from './progress/ProgressPage'
import ReadinessPage from './readiness/ReadinessPage'
import ReviewPage from './review/ReviewPage'
import SessionPage from './session/SessionPage'
import SignIn from './SignIn'

/** The web app's pages by path; the server serves index.html for each (SPA_PAGES). */
export default function Pages() {
  if (window.location.pathname === '/signin') return <SignIn />
  if (window.location.pathname === '/account') return <Account />
  if (window.location.pathname === '/session') return <SessionPage />
  if (window.location.pathname === '/tests') {
    // Tests is a tab of Body now (ADR-0069); old links, bookmarks and the bot's land there.
    window.history.replaceState(null, '', '/body?tab=tests')
    return <BodyTabs />
  }
  if (window.location.pathname === '/body') return <BodyTabs />
  if (window.location.pathname === '/progress') {
    if (new URLSearchParams(window.location.search).get('tab') === 'plan') {
      // The Plan was a tab of Progress (ux-flow-plan D2); it is its own page now (ADR-0069).
      window.history.replaceState(null, '', '/plan')
      return <PlanPage />
    }
    return <ProgressPage />
  }
  if (window.location.pathname === '/plan') return <PlanPage />
  if (window.location.pathname === '/readiness') return <ReadinessPage />
  if (window.location.pathname === '/review') return <ReviewPage />
  if (window.location.pathname === '/connect') return <ConnectPage />
  if (window.location.pathname === '/') return <HomePage />
  return (
    <p className="status">
      There's no page here. <a href="/session">Go to today's session</a>
    </p>
  )
}
