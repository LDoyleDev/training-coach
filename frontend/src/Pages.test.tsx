import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Pages from './Pages'

vi.mock('./SignIn', () => ({ default: () => <p>sign in</p> }))
vi.mock('./Account', () => ({ default: () => <p>account</p> }))
vi.mock('./tests/TestsPage', () => ({ default: () => <p>tests</p> }))
vi.mock('./body/BodyPage', () => ({ default: () => <p>body</p> }))
vi.mock('./progress/ProgressPage', () => ({ default: () => <p>progress</p> }))
vi.mock('./home/HomePage', () => ({ default: () => <p>home</p> }))
vi.mock('./review/ReviewPage', () => ({ default: () => <p>review</p> }))

afterEach(() => window.history.replaceState(null, '', '/'))

test.each([
  ['/plan', 'progress'],
  ['/signin', 'sign in'],
  ['/account', 'account'],
  ['/tests', 'tests'],
  ['/body', 'body'],
  ['/progress', 'progress'],
  ['/review', 'review'],
  ['/', 'home'],
])('%s shows %s', (path, text) => {
  window.history.replaceState(null, '', path)
  render(<Pages />)
  expect(screen.getByText(text)).toBeInTheDocument()
})

test('/plan becomes the Plan tab of Progress', () => {
  window.history.replaceState(null, '', '/plan')
  render(<Pages />)
  expect(screen.getByText('progress')).toBeInTheDocument()
  expect(window.location.pathname + window.location.search).toBe('/progress?tab=plan')
})

test('an unknown page says so instead of redirecting', () => {
  const replace = vi.fn()
  vi.stubGlobal('location', { ...window.location, pathname: '/plans', replace })
  render(<Pages />)
  expect(screen.getByRole('link', { name: "Go to today's session" })).toHaveAttribute(
    'href',
    '/session',
  )
  expect(replace).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})
