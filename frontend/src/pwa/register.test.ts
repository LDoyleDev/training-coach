import { afterEach, expect, test, vi } from 'vitest'
import { startPwa } from '.'
import { canRegister, registerServiceWorker } from './register'

const https = { production: true, protocol: 'https:', hostname: 'coach.example', supported: true }

afterEach(() => {
  Reflect.deleteProperty(navigator, 'serviceWorker')
})

function worker(register = vi.fn(async () => ({}))) {
  Object.defineProperty(navigator, 'serviceWorker', { value: { register }, configurable: true })
  return register
}

test('only a production build over https, or on this computer, registers', () => {
  expect(canRegister(https)).toBe(true)
  expect(canRegister({ ...https, protocol: 'http:', hostname: 'localhost' })).toBe(true)
  expect(canRegister({ ...https, protocol: 'http:', hostname: '127.0.0.1' })).toBe(true)
  expect(canRegister({ ...https, production: false })).toBe(false) // npm run dev
  expect(canRegister({ ...https, protocol: 'http:' })).toBe(false) // plain http elsewhere
  expect(canRegister({ ...https, supported: false })).toBe(false)
})

test('registers /sw.js for the whole app', async () => {
  const register = worker()
  expect(await registerServiceWorker(true)).toBe(true) // jsdom runs on http://localhost
  expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' })
})

test('not in a development build', async () => {
  const register = worker()
  expect(await registerServiceWorker(false)).toBe(false)
  expect(register).not.toHaveBeenCalled()
})

test('a browser without service workers just skips it', async () => {
  expect(await registerServiceWorker(true)).toBe(false)
})

test('a failed registration is quiet', async () => {
  worker(vi.fn(async () => Promise.reject(new Error('blocked'))))
  expect(await registerServiceWorker(true)).toBe(false)
})

test('start-up never registers in tests (a development build)', () => {
  const register = worker()
  startPwa()
  expect(register).not.toHaveBeenCalled()
})
