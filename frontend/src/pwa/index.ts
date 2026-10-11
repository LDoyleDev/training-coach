import { listenForInstall } from './install'
import { registerServiceWorker } from './register'

/** Install as an app (D3): keep the browser's install offer and start the service worker. */
export function startPwa(): void {
  listenForInstall()
  void registerServiceWorker()
}
