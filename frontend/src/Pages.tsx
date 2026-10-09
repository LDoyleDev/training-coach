import Account from './Account'
import App from './App'
import SignIn from './SignIn'

/** The web app's pages by path; the server serves index.html for each (SPA_PAGES). */
export default function Pages() {
  if (window.location.pathname === '/signin') return <SignIn />
  if (window.location.pathname === '/account') return <Account />
  return <App />
}
