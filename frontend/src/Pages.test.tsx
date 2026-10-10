import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Pages from './Pages'

vi.mock('./App', () => ({ default: () => <p>the plan</p> }))
vi.mock('./SignIn', () => ({ default: () => <p>sign in</p> }))
vi.mock('./Account', () => ({ default: () => <p>account</p> }))
vi.mock('./tests/TestsPage', () => ({ default: () => <p>tests</p> }))

afterEach(() => window.history.replaceState(null, '', '/'))

test.each([
  ['/', 'the plan'],
  ['/signin', 'sign in'],
  ['/account', 'account'],
  ['/tests', 'tests'],
])('%s shows %s', (path, text) => {
  window.history.replaceState(null, '', path)
  render(<Pages />)
  expect(screen.getByText(text)).toBeInTheDocument()
})
