import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { Closing } from './Closing'

vi.mock('./account/Leave', () => ({ default: () => <p>leave</p> }))

const ME = { user_id: 2, role: 'member' as const, closed: true, closing_on: '2026-12-07' }

afterEach(() => vi.unstubAllGlobals())

test('says when their data goes and offers only download and leave', () => {
  render(<Closing me={ME} />)
  expect(
    screen.getByRole('heading', { name: 'Training Coach is closing to members' }),
  ).toBeVisible()
  expect(screen.getByText(/erased on 7 December 2026/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Download my data' })).toBeInTheDocument()
  expect(screen.getByText('leave')).toBeInTheDocument()
})

test('before the night has set the day, it says 30 days', () => {
  render(<Closing me={{ ...ME, closing_on: null }} />)
  expect(screen.getByText(/erased 30 days from now/)).toBeInTheDocument()
})

test('downloading says so, and a failure says to try again', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(new Blob(['zip']), { status: 200 })),
  )
  vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
  render(<Closing me={ME} />)
  fireEvent.click(screen.getByRole('button', { name: 'Download my data' }))
  expect(await screen.findByText('Your data is downloading.')).toBeInTheDocument()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Download my data' }))
  expect(await screen.findByText(/That didn't work/)).toBeInTheDocument()
})
