import { useSyncExternalStore } from 'react'

/** Chrome's install offer (not in TypeScript's DOM types). */
interface InstallPrompt extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

/**
 * - installed: opened from the home screen, or just installed; nothing to offer.
 * - ready: the browser offered to install (Chrome on Android); a button can ask it.
 * - ios: Safari has no install button, only Share → Add to Home Screen.
 * - unavailable: anything else (already installed and opened in the browser, or no support).
 */
export type InstallState = 'installed' | 'ready' | 'ios' | 'unavailable'

let offer: InstallPrompt | null = null
let justInstalled = false
let listening = false
const listeners = new Set<() => void>()
const changed = () => listeners.forEach((listener) => listener())

/** Opened as an installed app, not in a browser tab. */
export function isStandalone(): boolean {
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches ?? false
  return standalone || (navigator as { standalone?: boolean }).standalone === true
}

/** An iPhone or iPad (iPadOS reports itself as a Mac with a touch screen). */
export function isIos(): boolean {
  const { userAgent, platform, maxTouchPoints } = navigator
  return /iPhone|iPad|iPod/.test(userAgent) || (platform === 'MacIntel' && maxTouchPoints > 1)
}

export function installState(): InstallState {
  if (justInstalled || isStandalone()) return 'installed'
  if (offer) return 'ready'
  if (isIos()) return 'ios'
  return 'unavailable'
}

/**
 * Keeps the browser's install offer for the button. Call once at start-up: Chrome makes the
 * offer soon after the page loads, before the Account page may be open.
 */
export function listenForInstall(): void {
  if (listening) return
  listening = true
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault() // the button asks instead of Chrome's own banner
    offer = event as InstallPrompt
    changed()
  })
  window.addEventListener('appinstalled', () => {
    offer = null
    justInstalled = true
    changed()
  })
}

/** Shows the browser's install question; true when the owner said yes. */
export async function install(): Promise<boolean> {
  if (!offer) return false
  const asked = offer
  offer = null // an offer can be used once
  await asked.prompt()
  const { outcome } = await asked.userChoice
  if (outcome === 'accepted') justInstalled = true
  changed()
  return outcome === 'accepted'
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useInstallState(): InstallState {
  return useSyncExternalStore(subscribe, installState)
}

/** For tests: forget any offer or install. */
export function resetInstall(): void {
  offer = null
  justInstalled = false
  changed()
}
