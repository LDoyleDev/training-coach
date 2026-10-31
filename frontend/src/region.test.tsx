import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { watchRegion } from './region'
import Unavailable from './Unavailable'

afterEach(() => vi.unstubAllGlobals())

const answer = (status: number, body: string) =>
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status })))

describe('watchRegion', () => {
  it("shows the region page with the server's reason when any API call answers 451", async () => {
    answer(451, JSON.stringify({ detail: 'Not available in your region', reason: 'Why.' }))
    const show = vi.fn()
    watchRegion(show)
    const res = await fetch('/api/plan')
    expect(res.status).toBe(451)
    expect(await res.json()).toEqual({ detail: 'Not available in your region', reason: 'Why.' })
    expect(show).toHaveBeenCalledExactlyOnceWith('Why.')
  })

  it('shows the page without a reason when the answer has none', async () => {
    answer(451, 'not json')
    const show = vi.fn()
    watchRegion(show)
    await fetch('/api/plan')
    expect(show).toHaveBeenCalledExactlyOnceWith(undefined)
  })

  it('leaves every other answer alone', async () => {
    answer(401, '{}')
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

  it("gives the server's reason when there is one", () => {
    render(<Unavailable reason="We can't tell where you are." />)
    expect(screen.getByText("We can't tell where you are.")).toBeInTheDocument()
  })
})
