import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BodyTabs from './BodyTabs'

vi.mock('./BodyPage', () => ({
  default: ({ embedded }: { embedded?: boolean }) => <p>measurements {String(embedded)}</p>,
}))
vi.mock('../tests/TestsPage', () => ({
  default: ({ embedded }: { embedded?: boolean }) => <p>tests {String(embedded)}</p>,
}))

const view = (asked: boolean, open: boolean) => ({
  asked,
  categories: [{ category: 'body', version: 1, open, answer: null, at: null }],
})
const consents = (body: unknown) =>
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Response.json(body)),
  )

afterEach(() => {
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})

test('Body opens on measurements, and Tests is its second tab, kept in the address', async () => {
  consents(view(false, true)) // the owner
  window.history.replaceState(null, '', '/body')
  render(<BodyTabs />)
  expect(screen.getByRole('heading', { level: 1, name: 'Body' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Measurements' })).toHaveAttribute('aria-selected', 'true')
  expect(await screen.findByText('measurements true')).toBeInTheDocument() // inside the frame
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

test('a member who hasn’t said yes is asked before the measurements, but not for the tests', async () => {
  consents(view(true, false))
  window.history.replaceState(null, '', '/body')
  render(<BodyTabs />)
  expect(
    await screen.findByRole('heading', { name: 'Keep your measurements and photos?' }),
  ).toBeInTheDocument()
  expect(screen.queryByText('measurements true')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))
  expect(screen.getByText('tests true')).toBeInTheDocument()
})
