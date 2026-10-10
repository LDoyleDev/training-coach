import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { PhotoView } from '../api'
import Photos from './Photos'

vi.mock('./shrink', () => ({
  shrink: vi.fn(async () => new Blob(['small'], { type: 'image/jpeg' })),
}))

type Server = { photos?: PhotoView[]; upload?: 'refuse' | 'too-large' | 'fail' | 'signed-out' }

/** A fake API; returns the requests that change something. */
function serve(server: Server = {}) {
  const sent: { method: string; path: string }[] = []
  let photos = server.photos ?? []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (method === 'GET') return Response.json(photos)
      sent.push({ method, path })
      if (method === 'DELETE') {
        photos = photos.filter((p) => path !== `/api/photos/${p.id}`)
        return new Response(null, { status: 204 })
      }
      if (server.upload === 'signed-out') return new Response(null, { status: 401 })
      if (server.upload === 'too-large') return new Response(null, { status: 413 })
      if (server.upload === 'refuse')
        return Response.json({ detail: "the photo isn't a JPEG" }, { status: 422 })
      if (server.upload === 'fail') return new Response(null, { status: 500 })
      photos = [{ id: 9, on: path.split('/')[3], pose: 'front', size: 5 }, ...photos]
      return Response.json({ id: 9 })
    }),
  )
  return sent
}

const choose = async (label: string) => {
  const input = await screen.findByLabelText(label)
  fireEvent.change(input, { target: { files: [new File(['raw'], 'me.jpg')] } })
}

afterEach(() => vi.unstubAllGlobals())

test('a photo taken today is shrunk, uploaded and shown', async () => {
  const sent = serve()
  render(<Photos />)
  await choose('Front photo for today')
  expect(await screen.findByText('Photo saved.')).toBeInTheDocument()
  expect(sent).toHaveLength(1)
  expect(sent[0].method).toBe('PUT')
  expect(sent[0].path).toMatch(/^\/api\/photos\/\d{4}-\d{2}-\d{2}\/front$/)
  expect(await screen.findByRole('img', { name: /front on/ })).toHaveAttribute(
    'src',
    '/api/photos/9',
  )
})

test('photos are listed by day and can be removed', async () => {
  const sent = serve({
    photos: [
      { id: 2, on: '2026-10-10', pose: 'front', size: 5 },
      { id: 3, on: '2026-10-10', pose: 'side', size: 5 },
      { id: 1, on: '2026-09-29', pose: 'front', size: 5 },
    ],
  })
  render(<Photos />)
  expect(await screen.findByText('2026-09-29')).toBeInTheDocument()
  expect(screen.getAllByRole('img')).toHaveLength(3)
  fireEvent.click(screen.getByRole('button', { name: 'Remove the side photo on 2026-10-10' }))
  await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(2))
  expect(sent).toEqual([{ method: 'DELETE', path: '/api/photos/3' }])
})

test.each([
  ['refuse', "the photo isn't a JPEG"],
  ['too-large', 'That photo is too large.'],
  ['fail', /Check your connection/],
] as const)('an upload that %s says so', async (upload, message) => {
  serve({ upload })
  render(<Photos />)
  await choose('Back photo for today')
  expect(await screen.findByText(message)).toBeInTheDocument()
})

test('an ended sign-in points to sign in', async () => {
  serve({ upload: 'signed-out' })
  render(<Photos />)
  await choose('Side photo for today')
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})

test('choosing nothing does nothing, and a failed list says so', async () => {
  const sent = serve()
  render(<Photos />)
  fireEvent.change(await screen.findByLabelText('Front photo for today'), {
    target: { files: [] },
  })
  expect(sent).toEqual([])
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  render(<Photos />)
  expect(await screen.findByText("Couldn't load your photos.")).toBeInTheDocument()
})

test('a failed remove says so', async () => {
  serve({ photos: [{ id: 2, on: '2026-10-10', pose: 'front', size: 5 }] })
  render(<Photos />)
  const button = await screen.findByRole('button', { name: 'Remove the front photo on 2026-10-10' })
  vi.unstubAllGlobals()
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  fireEvent.click(button)
  expect(await screen.findByText(/Couldn't remove it/)).toBeInTheDocument()
})
