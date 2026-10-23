import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import AppShell from './AppShell'

afterEach(() => {
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})

test('the nav links every signed-in page and marks the one shown', () => {
  window.history.replaceState(null, '', '/plan')
  render(
    <AppShell>
      <p>content</p>
    </AppShell>,
  )
  const nav = screen.getByRole('navigation', { name: 'Pages' })
  const links = [...nav.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])
  expect(links).toEqual([
    ['Home', '/'],
    ['Plan', '/plan'],
    ['Progress', '/progress'],
    ['Today', '/session'],
    ['Body', '/body'],
    ['Account', '/account'],
  ])
  expect(screen.getByRole('link', { name: 'Plan' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Body' })).not.toHaveAttribute('aria-current')
  expect(screen.getByRole('link', { name: 'Training Coach' })).toHaveAttribute('href', '/')
  // Six tabs, all on a phone too; Tests is a tab of Body (ADR-0069).
  expect(screen.getByRole('link', { name: 'Home' }).closest('li')).not.toHaveClass('hidden')
  expect(screen.queryByRole('link', { name: 'Tests' })).toBeNull()
  expect(screen.getByText('content')).toBeInTheDocument()
})

test('every page can sign out, then goes to the sign-in page', async () => {
  const fetch = vi.fn(async () => new Response(null, { status: 204 }))
  const assign = vi.fn()
  vi.stubGlobal('fetch', fetch)
  vi.stubGlobal('location', { ...window.location, pathname: '/progress', assign })
  render(
    <AppShell>
      <p>content</p>
    </AppShell>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/signin'))
  expect(fetch).toHaveBeenCalledWith('/api/auth/signout', {
    method: 'POST',
    credentials: 'same-origin',
  })
})
