import Account from './Account'
import BodyPage from './body/BodyPage'
import App from './App'
import ProgressPage from './progress/ProgressPage'
import SessionPage from './session/SessionPage'
import SignIn from './SignIn'
import TestsPage from './tests/TestsPage'

/** The web app's pages by path; the server serves index.html for each (SPA_PAGES). */
export default function Pages() {
  if (window.location.pathname === '/signin') return <SignIn />
  if (window.location.pathname === '/account') return <Account />
  if (window.location.pathname === '/session') return <SessionPage />
  if (window.location.pathname === '/tests') return <TestsPage />
  if (window.location.pathname === '/body') return <BodyPage />
  if (window.location.pathname === '/progress') return <ProgressPage />
  if (window.location.pathname === '/plan') return <App />
  // The site is private (ADR-0041): the front door is today's session, or its sign-in.
  window.location.replace('/session')
  return null
}
