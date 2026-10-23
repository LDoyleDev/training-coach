import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Pages from './Pages'

vi.mock('./SignIn', () => ({ default: () => <p>sign in</p> }))
vi.mock('./Account', () => ({ default: () => <p>account</p> }))
vi.mock('./tests/TestsPage', () => ({ default: () => <p>tests</p> }))
vi.mock('./body/BodyPage', () => ({ default: () => <p>body</p> }))
vi.mock('./plan/PlanPage', () => ({ default: () => <p>plan</p> }))
vi.mock('./progress/ProgressPage', () => ({ default: () => <p>progress</p> }))
vi.mock('./home/HomePage', () => ({ default: () => <p>home</p> }))
vi.mock('./review/ReviewPage', () => ({ default: () => <p>review</p> }))
vi.mock('./connect/ConnectPage', () => ({ default: () => <p>connect</p> }))

afterEach(() => window.history.replaceState(null, '', '/'))

test.each([
  ['/plan', 'plan'],
  ['/signin', 'sign in'],
  ['/account', 'account'],
  ['/body', 'body'],
  ['/progress', 'progress'],
  ['/review', 'review'],
  ['/connect', 'connect'],
  ['/', 'home'],
])('%s shows %s', (path, text) => {
  window.history.replaceState(null, '', path)
  render(<Pages />)
  expect(screen.getByText(text)).toBeInTheDocument()
})

test('the old Plan tab of Progress opens the Plan page', () => {
  window.history.replaceState(null, '', '/progress?tab=plan')
  render(<Pages />)
  expect(screen.getByText('plan')).toBeInTheDocument()
  expect(window.location.pathname + window.location.search).toBe('/plan')
})

test('/tests opens the Tests tab of Body', () => {
  window.history.replaceState(null, '', '/tests')
  render(<Pages />)
  expect(screen.getByText('tests')).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Tests' })).toHaveAttribute('aria-selected', 'true')
  expect(window.location.pathname + window.location.search).toBe('/body?tab=tests')
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
