import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import PlanPage from './PlanPage'

vi.mock('../App', () => ({ default: () => <p>the plan</p> }))

afterEach(() => vi.unstubAllGlobals())

test('the Plan page frames your levels and the plan with its own heading and the nav', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async (path: string) =>
        path === '/api/progress'
          ? Response.json({ today: '2026-10-25', strength_block: false, standings: [] })
          : new Response(null, { status: 401 }), // extra cardio stays hidden
    ),
  )
  window.history.replaceState(null, '', '/plan')
  render(<PlanPage />)
  expect(screen.getByRole('heading', { level: 1, name: 'Plan' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { level: 2, name: 'Your levels' })).toBeInTheDocument()
  expect(screen.getByText('the plan')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Plan' })).toHaveAttribute('aria-current', 'page')
  window.history.replaceState(null, '', '/')
})
