import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BodyTabs from './BodyTabs'

vi.mock('./BodyPage', () => ({
  default: ({ embedded }: { embedded?: boolean }) => <p>measurements {String(embedded)}</p>,
}))
vi.mock('../tests/TestsPage', () => ({
  default: ({ embedded }: { embedded?: boolean }) => <p>tests {String(embedded)}</p>,
}))

afterEach(() => window.history.replaceState(null, '', '/'))

test('Body opens on measurements, and Tests is its second tab, kept in the address', () => {
  window.history.replaceState(null, '', '/body')
  render(<BodyTabs />)
  expect(screen.getByRole('heading', { level: 1, name: 'Body' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Measurements' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('measurements true')).toBeInTheDocument() // inside this page's frame
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))
  expect(screen.getByText('tests true')).toBeInTheDocument()
  expect(window.location.pathname + window.location.search).toBe('/body?tab=tests')
  fireEvent.click(screen.getByRole('tab', { name: 'Measurements' }))
  expect(window.location.pathname + window.location.search).toBe('/body')
})

test('?tab=tests opens on the tests', () => {
  window.history.replaceState(null, '', '/body?tab=tests')
  render(<BodyTabs />)
  expect(screen.getByRole('tab', { name: 'Tests' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('tests true')).toBeInTheDocument()
})
