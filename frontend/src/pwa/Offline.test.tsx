import { act, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import OfflineNotice from './Offline'

function network(online: boolean) {
  Object.defineProperty(navigator, 'onLine', { value: online, configurable: true })
  act(() => {
    window.dispatchEvent(new Event(online ? 'online' : 'offline'))
  })
}

afterEach(() => network(true))

test('says so while offline, and goes away when back online', () => {
  render(<OfflineNotice />)
  expect(screen.queryByText(/You're offline/)).not.toBeInTheDocument()
  network(false)
  expect(screen.getByRole('status')).toHaveTextContent("You're offline")
  network(true)
  expect(screen.queryByText(/You're offline/)).not.toBeInTheDocument()
})
