import { useState } from 'react'
import { card, primaryInline, small } from '../ui'
import { install, useInstallState } from './install'

const IOS = 'On iPhone or iPad: tap Share, then Add to Home Screen.'
const HINT_KEY = 'tc.install-hint-dismissed'

/** Account: put the app on the home screen. Hidden once installed, or where it can't be. */
export function InstallCard() {
  const state = useInstallState()
  const [declined, setDeclined] = useState(false)
  if (state === 'unavailable' && !declined) return null
  return (
    <section aria-labelledby="install" className={card}>
      <h2 id="install" className="mb-2 text-xl">
        Install the app
      </h2>
      {state === 'installed' && (
        <p className="m-0">Installed. Open Training Coach from your home screen.</p>
      )}
      {state === 'ready' && (
        <>
          <p className="mt-0">
            Put Training Coach on your home screen: it opens full screen, like any other app.
          </p>
          <button
            type="button"
            className={primaryInline}
            onClick={() => install().then((yes) => setDeclined(!yes))}
          >
            Install app
          </button>
        </>
      )}
      {state === 'ios' && <p className="m-0">{IOS}</p>}
      {declined && state !== 'installed' && (
        <p className="mb-0">Not installed. Your browser's menu can install it later.</p>
      )}
    </section>
  )
}

function seen(): boolean {
  try {
    return localStorage.getItem(HINT_KEY) === '1'
  } catch {
    return false
  }
}

/** Home: a one-time hint to install, until installed or closed. */
export function InstallHint() {
  const state = useInstallState()
  const [closed, setClosed] = useState(seen)
  if (closed || (state !== 'ready' && state !== 'ios')) return null
  const close = () => {
    try {
      localStorage.setItem(HINT_KEY, '1')
    } catch {
      // private browsing: the hint just comes back next time
    }
    setClosed(true)
  }
  return (
    <aside aria-label="Install the app" className={card + ' flex flex-col gap-2'}>
      <p className="m-0">
        Training Coach works best from your home screen.{' '}
        {state === 'ios' ? IOS : 'Install it to open it full screen.'}
      </p>
      <div className="flex flex-wrap gap-2">
        {state === 'ready' && (
          <button type="button" className={primaryInline} onClick={() => void install()}>
            Install app
          </button>
        )}
        <button type="button" className={small} onClick={close}>
          Not now
        </button>
      </div>
    </aside>
  )
}
