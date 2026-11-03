import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Residence, { NOT_FOR_YOU } from './Residence'

const CHOICES = ['DE', 'IE', 'NO']
const GET = 'GET /api/account/residence'
const PUT = 'PUT /api/account/residence'
type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply>) {
  const asked: string[] = []
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    const route = `${init?.method ?? 'GET'} ${path}`
    asked.push(`${route} ${typeof init?.body === 'string' ? init.body : ''}`.trim())
    const reply = routes[route] ?? { status: 500 }
    const body = reply.body === undefined ? null : JSON.stringify(reply.body)
    return new Response(body, { status: reply.status })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { asked, fetchMock }
}

afterEach(() => vi.unstubAllGlobals())

test('lists the countries by name, and somewhere else', async () => {
  serve({ [GET]: { status: 200, body: { country: null, choices: CHOICES } } })
  render(<Residence />)
  expect(await screen.findByLabelText('Country')).toHaveValue('')
  const options = screen.getAllByRole('option').map((o) => o.textContent)
  expect(options).toEqual(['Choose your country', 'Germany', 'Ireland', 'Norway', 'Somewhere else'])
})

test('saves a country from the list', async () => {
  const { asked } = serve({
    [GET]: { status: 200, body: { country: null, choices: CHOICES } },
    [PUT]: { status: 200, body: { country: 'IE', choices: CHOICES } },
  })
  render(<Residence />)
  fireEvent.change(await screen.findByLabelText('Country'), { target: { value: 'IE' } })
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(screen.getByLabelText('Country')).toHaveValue('IE')
  expect(asked).toContain(`${PUT} {"country":"IE"}`)
})

test('somewhere else is refused with the reason and nothing is sent', async () => {
  const { asked } = serve({ [GET]: { status: 200, body: { country: 'DE', choices: CHOICES } } })
  render(<Residence />)
  fireEvent.change(await screen.findByLabelText('Country'), { target: { value: 'elsewhere' } })
  expect(screen.getByRole('status')).toHaveTextContent(NOT_FOR_YOU)
  expect(screen.getByLabelText('Country')).toHaveValue('DE')
  expect(asked).toEqual([GET])
})

test("the server's refusal is shown", async () => {
  serve({
    [GET]: { status: 200, body: { country: null, choices: CHOICES } },
    [PUT]: { status: 422, body: { detail: 'Not on the list.' } },
  })
  render(<Residence />)
  fireEvent.change(await screen.findByLabelText('Country'), { target: { value: 'NO' } })
  expect(await screen.findByText('Not on the list.')).toBeInTheDocument()
})

test('a sign-in that ended, or a failure, says so', async () => {
  serve({
    [GET]: { status: 200, body: { country: null, choices: CHOICES } },
    [PUT]: { status: 401 },
  })
  render(<Residence />)
  fireEvent.change(await screen.findByLabelText('Country'), { target: { value: 'NO' } })
  expect(await screen.findByText(/Your sign-in ended/)).toBeInTheDocument()
})

test('a network failure says to try again', async () => {
  serve({
    [GET]: { status: 200, body: { country: null, choices: CHOICES } },
    [PUT]: { status: 500 },
  })
  render(<Residence />)
  fireEvent.change(await screen.findByLabelText('Country'), { target: { value: 'NO' } })
  expect(await screen.findByText(/That didn't work/)).toBeInTheDocument()
})

test('stays hidden when it cannot load', async () => {
  const { fetchMock } = serve({ [GET]: { status: 500 } })
  const { container } = render(<Residence />)
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})
