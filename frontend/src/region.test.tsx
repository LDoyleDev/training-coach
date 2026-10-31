import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { watchRegion } from './region'
import Unavailable from './Unavailable'

afterEach(() => vi.unstubAllGlobals())

describe('watchRegion', () => {
  it('shows the region page when any API call answers 451', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 451 })))
    const show = vi.fn()
    watchRegion(show)
    const res = await fetch('/api/plan')
    expect(res.status).toBe(451)
    expect(show).toHaveBeenCalledTimes(1)
  })

  it('leaves every other answer alone', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
    const show = vi.fn()
    watchRegion(show)
    expect((await fetch('/api/plan')).status).toBe(401)
    expect(show).not.toHaveBeenCalled()
  })
})

describe('Unavailable', () => {
  it('says the app is not available here', () => {
    render(<Unavailable />)
    expect(
      screen.getByRole('heading', { name: 'Not available in your region' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/only for people in the EU and EEA/)).toBeInTheDocument()
  })
})
