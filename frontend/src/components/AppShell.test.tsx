import { render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import AppShell from './AppShell'

afterEach(() => window.history.replaceState(null, '', '/'))

test('the nav links every signed-in page and marks the one shown', () => {
  window.history.replaceState(null, '', '/tests')
  render(
    <AppShell>
      <p>content</p>
    </AppShell>,
  )
  const nav = screen.getByRole('navigation', { name: 'Pages' })
  const links = [...nav.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])
  expect(links).toEqual([
    ['Today', '/session'],
    ['Progress', '/progress'],
    ['Plan', '/plan'],
    ['Tests', '/tests'],
    ['Body', '/body'],
    ['Account', '/account'],
  ])
  expect(screen.getByRole('link', { name: 'Tests' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Body' })).not.toHaveAttribute('aria-current')
  expect(screen.getByRole('link', { name: 'Training Coach' })).toHaveAttribute('href', '/')
  expect(screen.getByText('content')).toBeInTheDocument()
})
