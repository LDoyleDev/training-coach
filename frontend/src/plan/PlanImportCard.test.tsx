import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import PlanImportCard from './PlanImportCard'

const WAITING = {
  changes: ['Legs: Squat, 3 x 8-12 becomes 4 x 8-12'],
  blocked: null,
  version: 'Heavier legs',
}

function serve(get: unknown, post: Response | null = null) {
  const sent: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        sent.push('POST')
        return post ?? Response.json(WAITING)
      }
      return get instanceof Response ? get : Response.json(get)
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test('nothing waiting shows nothing', async () => {
  serve({ changes: [], blocked: null, version: null })
  const { container } = render(<PlanImportCard />)
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})

test('signed out or a failed read shows nothing', async () => {
  serve(new Response(null, { status: 500 }))
  const { container } = render(<PlanImportCard />)
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})

test('lists what would change and saves it only on a tap', async () => {
  const sent = serve(WAITING)
  render(<PlanImportCard />)
  expect(await screen.findByRole('heading', { name: 'Changes to your plan' })).toBeInTheDocument()
  expect(screen.getByText(WAITING.changes[0]!)).toBeInTheDocument()
  expect(sent).toEqual([])
  fireEvent.click(screen.getByRole('button', { name: 'Save as a new version' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
  expect(sent).toEqual(['POST'])
  expect(screen.queryByRole('button', { name: 'Save as a new version' })).not.toBeInTheDocument()
})

test('a session in progress says why instead of offering to save', async () => {
  serve({ ...WAITING, blocked: 'Finish or discard your session in progress first.' })
  render(<PlanImportCard />)
  expect(await screen.findByText(/Finish or discard/)).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('a session started meanwhile shows why after the tap', async () => {
  let reads = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'POST') return new Response(null, { status: 409 })
      reads += 1
      return Response.json(reads === 1 ? WAITING : { ...WAITING, blocked: 'Finish it first.' })
    }),
  )
  render(<PlanImportCard />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save as a new version' }))
  expect(await screen.findByText('Finish it first.')).toBeInTheDocument()
})

test.each([
  [new Response(null, { status: 401 }), 'Your sign-in ended'],
  [new Response(null, { status: 500 }), "That didn't work"],
])('a failed save says so', async (post, message) => {
  serve(WAITING, post)
  render(<PlanImportCard />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save as a new version' }))
  expect(await screen.findByRole('status')).toHaveTextContent(message)
})

test('a file that is refused says why, with nothing listed or offered', async () => {
  const refusal = "Fix plan.toml first. Two sessions can't both be called Legs."
  serve({ changes: [], blocked: refusal, version: null })
  render(<PlanImportCard />)
  expect(await screen.findByText(refusal)).toBeInTheDocument()
  expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
