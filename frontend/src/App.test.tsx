import { render, screen } from '@testing-library/react'
import App from './App'

function mockFetch(impl: () => Promise<unknown>) {
  globalThis.fetch = vi.fn(impl) as unknown as typeof fetch
}

describe('App', () => {
  it('renders the app name', () => {
    mockFetch(() => Promise.resolve({ ok: false }))
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Training Coach' })).toBeInTheDocument()
  })

  it('shows the API version once healthy', async () => {
    mockFetch(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'ok', version: '1.2.3', bot_enabled: false }),
      }),
    )
    render(<App />)
    expect(await screen.findByText('v1.2.3 · API ok')).toBeInTheDocument()
  })

  it('keeps showing connecting when the API is unreachable', async () => {
    mockFetch(() => Promise.reject(new Error('offline')))
    render(<App />)
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(screen.getByText('Connecting…')).toBeInTheDocument()
  })
})
