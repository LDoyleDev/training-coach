import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { MeasureKind, Measurement } from '../api'
import BodyPage from './BodyPage'

const KINDS: MeasureKind[] = [
  { kind: 'bodyweight', label: 'Bodyweight', unit: 'kg', decimals: 1, low: 30, high: 250 },
  { kind: 'waist', label: 'Waist', unit: 'cm', decimals: 1, low: 40, high: 200 },
]

type Server = {
  entries?: Measurement[]
  signedIn?: boolean
  save?: 'refuse' | 'fail'
  remove?: 'fail'
}

/** A fake API; returns the requests sent that change something. */
function serve(server: Server = {}) {
  const sent: { method: string; path: string; body: unknown }[] = []
  let entries = server.entries ?? []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (server.signedIn === false) return new Response(null, { status: 401 })
      const method = init?.method ?? 'GET'
      if (method !== 'GET') {
        sent.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null })
        if (method === 'DELETE') {
          if (server.remove === 'fail') return new Response(null, { status: 500 })
          entries = entries.filter((e) => path !== `/api/body/${e.on}/${e.kind}`)
          return new Response(null, { status: 204 })
        }
        if (server.save === 'refuse')
          return Response.json({ detail: 'Waist must be from 40 to 200 cm' }, { status: 422 })
        if (server.save === 'fail') return new Response(null, { status: 500 })
        return new Response(null, { status: 204 })
      }
      if (path === '/api/body/kinds') return Response.json(KINDS)
      return Response.json(entries)
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test('the latest values compare with the first and the last', async () => {
  serve({
    entries: [
      { on: '2026-10-10', kind: 'bodyweight', value: 83.1 },
      { on: '2026-10-03', kind: 'bodyweight', value: 83.6 },
      { on: '2026-09-28', kind: 'bodyweight', value: 84.2 },
    ],
  })
  render(<BodyPage />)
  expect(
    await screen.findByText(/83.1 kg · since first -1.1 · since last -0.5/),
  ).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
})

test('filled-in values are saved for the chosen day', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Bodyweight'), { target: { value: '83,4' } })
  fireEvent.change(screen.getByLabelText('Day'), { target: { value: '2026-10-08' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(sent).toEqual([
    { method: 'PUT', path: '/api/body', body: { on: '2026-10-08', values: { bodyweight: 83.4 } } },
  ])
  expect(screen.getByLabelText('Bodyweight')).toHaveValue('')
})

test('nothing typed, or not a number, is caught before sending', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  expect(screen.getByText('Fill in at least one.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Waist'), { target: { value: 'big' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(screen.getByText("Waist isn't a number.")).toBeInTheDocument()
  expect(sent).toEqual([])
})

test('a refused or failed save says so and keeps what was typed', async () => {
  serve({ save: 'refuse' })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '820' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Waist must be from 40 to 200 cm')).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve({ save: 'fail' })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText(/Check your connection/)).toBeInTheDocument()
  expect(screen.getByLabelText('Waist')).toHaveValue('820')
})

test('a measurement can be removed', async () => {
  const sent = serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove Waist on 2026-10-10' }))
  await screen.findByRole('heading', { name: 'Add measurements' })
  expect(sent).toEqual([{ method: 'DELETE', path: '/api/body/2026-10-10/waist', body: null }])
  expect(await screen.findByRole('heading', { name: 'Body' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'History' })).not.toBeInTheDocument()
})

test('a failed remove says so', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'mystery' as never, value: 1 }], remove: 'fail' })
  render(<BodyPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Remove mystery on 2026-10-10' }))
  expect(await screen.findByText(/Couldn't remove it/)).toBeInTheDocument()
})

test('signed out, or the server down', async () => {
  serve({ signedIn: false })
  const { unmount } = render(<BodyPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  unmount()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  render(<BodyPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your measurements.")
})

test('an ended sign-in points to sign in and keeps what was typed', async () => {
  const sent = serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '85' } })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toHaveAttribute(
    'href',
    '/signin',
  )
  expect(screen.getByLabelText('Waist')).toHaveValue('85')
  expect(sent).toEqual([])
})

test('a remove after an ended sign-in points to sign in too', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  const button = await screen.findByRole('button', { name: 'Remove Waist on 2026-10-10' })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(button)
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})

test('removing clears an earlier note', async () => {
  serve({ entries: [{ on: '2026-10-10', kind: 'waist', value: 85 }] })
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Bodyweight'), { target: { value: '83' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Waist on 2026-10-10' }))
  await waitFor(() => expect(screen.queryByText('Saved.')).not.toBeInTheDocument())
})

test('a retry after signing in again clears the notice', async () => {
  serve()
  render(<BodyPage />)
  fireEvent.change(await screen.findByLabelText('Waist'), { target: { value: '85' } })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 401 })),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
  vi.unstubAllGlobals()
  serve() // signed in again in another tab
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Sign in again' })).not.toBeInTheDocument()
})
