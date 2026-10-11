import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import {
  install,
  installState,
  isIos,
  isStandalone,
  listenForInstall,
  resetInstall,
} from './install'
import { InstallCard, InstallHint } from './InstallApp'

const realAgent = navigator.userAgent

function standalone(on: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({ matches: on && query === '(display-mode: standalone)' })),
  )
}

function agent(userAgent: string) {
  Object.defineProperty(navigator, 'userAgent', { value: userAgent, configurable: true })
}

/** Chrome offering to install; the owner answers `outcome`. */
function offer(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt', { cancelable: true })
  const prompt = vi.fn(async () => undefined)
  Object.assign(event, { prompt, userChoice: Promise.resolve({ outcome }) })
  act(() => {
    window.dispatchEvent(event)
  })
  return { event, prompt }
}

beforeEach(() => {
  listenForInstall()
  listenForInstall() // twice is harmless
  standalone(false)
  agent('Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/141.0 Mobile')
})

afterEach(() => {
  act(() => resetInstall())
  agent(realAgent)
  localStorage.clear()
  vi.unstubAllGlobals()
})

test('nothing to offer where the browser cannot install', () => {
  expect(installState()).toBe('unavailable')
  const { container } = render(
    <>
      <InstallCard />
      <InstallHint />
    </>,
  )
  expect(container).toBeEmptyDOMElement()
})

test('hidden when already opened as an installed app', () => {
  standalone(true)
  offer()
  expect(isStandalone()).toBe(true)
  render(<InstallHint />)
  expect(screen.queryByRole('button', { name: 'Install app' })).not.toBeInTheDocument()
})

test('iOS standalone counts as installed', () => {
  Object.defineProperty(navigator, 'standalone', { value: true, configurable: true })
  expect(installState()).toBe('installed')
  Object.defineProperty(navigator, 'standalone', { value: undefined, configurable: true })
})

test('works without matchMedia', () => {
  vi.stubGlobal('matchMedia', undefined)
  expect(isStandalone()).toBe(false)
})

test('the install button asks the browser, then says it is installed', async () => {
  render(<InstallCard />)
  const { event, prompt } = offer('accepted')
  expect(event.defaultPrevented).toBe(true) // Chrome's own banner stays away
  fireEvent.click(screen.getByRole('button', { name: 'Install app' }))
  expect(await screen.findByText(/Installed. Open Training Coach/)).toBeInTheDocument()
  expect(prompt).toHaveBeenCalledOnce()
  expect(screen.queryByRole('button', { name: 'Install app' })).not.toBeInTheDocument()
})

test('saying no keeps a note and drops the used offer', async () => {
  render(<InstallCard />)
  offer('dismissed')
  fireEvent.click(screen.getByRole('button', { name: 'Install app' }))
  expect(await screen.findByText(/Not installed/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Install app' })).not.toBeInTheDocument()
  expect(await install()).toBe(false) // no offer left
})

test('installing from the browser menu hides the offer', () => {
  render(<InstallCard />)
  offer()
  act(() => {
    window.dispatchEvent(new Event('appinstalled'))
  })
  expect(screen.getByText(/Installed/)).toBeInTheDocument()
})

test('on iPhone the card and hint say how to add it', () => {
  agent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1')
  expect(isIos()).toBe(true)
  render(
    <>
      <InstallCard />
      <InstallHint />
    </>,
  )
  expect(screen.getAllByText(/tap Share, then Add to Home Screen/)).toHaveLength(2)
  expect(screen.queryByRole('button', { name: 'Install app' })).not.toBeInTheDocument()
})

test('an iPad that reports itself as a Mac is still iOS', () => {
  agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15')
  Object.defineProperty(navigator, 'platform', { value: 'MacIntel', configurable: true })
  Object.defineProperty(navigator, 'maxTouchPoints', { value: 5, configurable: true })
  expect(isIos()).toBe(true)
  Object.defineProperty(navigator, 'maxTouchPoints', { value: 0, configurable: true })
  expect(isIos()).toBe(false)
})

test('the home hint installs, and once closed stays closed', async () => {
  const { unmount } = render(<InstallHint />)
  const { prompt } = offer()
  fireEvent.click(screen.getByRole('button', { name: 'Install app' }))
  await act(async () => {})
  expect(prompt).toHaveBeenCalledOnce()
  unmount()

  act(() => resetInstall())
  offer()
  const again = render(<InstallHint />)
  fireEvent.click(screen.getByRole('button', { name: 'Not now' }))
  expect(again.container).toBeEmptyDOMElement()
  again.unmount()
  render(<InstallHint />)
  expect(screen.queryByText(/works best from your home screen/)).not.toBeInTheDocument()
})

test('the hint still closes when storage is blocked', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  offer()
  const { container } = render(<InstallHint />)
  fireEvent.click(screen.getByRole('button', { name: 'Not now' }))
  expect(container).toBeEmptyDOMElement()
  vi.restoreAllMocks()
})
