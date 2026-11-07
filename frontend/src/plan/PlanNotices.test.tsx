import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import PlanNotices from './PlanNotices'

const NOTICES = [{ id: 7, text: 'Reverse fly: "8 kg one arm" is now "dumbbells".' }]

function serve(get: Response | object[], post: Response = new Response(null, { status: 204 })) {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        sent.push(JSON.parse(String(init.body)))
        return post
      }
      return get instanceof Response ? get : Response.json(get)
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test.each([
  ['none', [] as object[]],
  ['signed out', new Response(null, { status: 401 })],
  ['a failed read', new Response(null, { status: 500 })],
])('%s shows nothing', async (_name, answer) => {
  serve(answer)
  const { container } = render(<PlanNotices />)
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})

test('says what changed until Got it', async () => {
  const sent = serve(NOTICES)
  const { container } = render(<PlanNotices />)
  expect(
    await screen.findByRole('heading', { name: 'Something changed in your plan' }),
  ).toBeInTheDocument()
  expect(screen.getByText(NOTICES[0]!.text)).toBeInTheDocument()
  expect(screen.getByText('Your levels stay where they are.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
  await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  expect(sent).toEqual([{ ids: [7] }])
})

test('a failed Got it keeps it and says so', async () => {
  serve(NOTICES, new Response(null, { status: 500 }))
  render(<PlanNotices />)
  fireEvent.click(await screen.findByRole('button', { name: 'Got it' }))
  expect(await screen.findByRole('status')).toHaveTextContent("That didn't work")
  expect(screen.getByText(NOTICES[0]!.text)).toBeInTheDocument()
})
