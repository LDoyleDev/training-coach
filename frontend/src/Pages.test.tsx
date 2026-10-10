import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Pages from './Pages'

vi.mock('./App', () => ({ default: () => <p>the plan</p> }))
vi.mock('./SignIn', () => ({ default: () => <p>sign in</p> }))
vi.mock('./Account', () => ({ default: () => <p>account</p> }))
vi.mock('./tests/TestsPage', () => ({ default: () => <p>tests</p> }))
vi.mock('./body/BodyPage', () => ({ default: () => <p>body</p> }))
vi.mock('./progress/ProgressPage', () => ({ default: () => <p>progress</p> }))

afterEach(() => window.history.replaceState(null, '', '/'))

test.each([
  ['/plan', 'the plan'],
  ['/signin', 'sign in'],
  ['/account', 'account'],
  ['/tests', 'tests'],
  ['/body', 'body'],
  ['/progress', 'progress'],
])('%s shows %s', (path, text) => {
  window.history.replaceState(null, '', path)
  render(<Pages />)
  expect(screen.getByText(text)).toBeInTheDocument()
})

test('the front door goes to the session page', () => {
  const replace = vi.fn()
  vi.stubGlobal('location', { ...window.location, pathname: '/', replace })
  const { container } = render(<Pages />)
  expect(replace).toHaveBeenCalledWith('/session')
  expect(container).toBeEmptyDOMElement()
  vi.unstubAllGlobals()
})
