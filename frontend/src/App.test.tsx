import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the app name', () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false })
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Training Coach' })).toBeInTheDocument()
  })
})
