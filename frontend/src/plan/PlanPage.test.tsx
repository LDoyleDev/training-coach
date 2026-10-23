import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import PlanPage from './PlanPage'

vi.mock('../App', () => ({ default: () => <p>the plan</p> }))

test('the Plan page frames the plan with its own heading and the nav', () => {
  window.history.replaceState(null, '', '/plan')
  render(<PlanPage />)
  expect(screen.getByRole('heading', { level: 1, name: 'Plan' })).toBeInTheDocument()
  expect(screen.getByText('the plan')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Plan' })).toHaveAttribute('aria-current', 'page')
  window.history.replaceState(null, '', '/')
})
