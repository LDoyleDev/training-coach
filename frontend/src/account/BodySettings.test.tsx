import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BodySettings from './BodySettings'

const DEFAULT = { height_cm: null, thigh_offset_cm: 15, body_fat_estimate: 'off' }

type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply[]>) {
  const asked: { route: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push({ route, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      const replies = routes[route] ?? [{ status: 500 }]
      const reply = replies.length > 1 ? replies.shift()! : replies[0]
      const body = reply.body === undefined ? null : JSON.stringify(reply.body)
      return new Response(body, { status: reply.status })
    }),
  )
  return asked
}

afterEach(() => vi.unstubAllGlobals())

test('shows the saved settings, the default thigh landmark and why', async () => {
  serve({ 'GET /api/account/body': [{ status: 200, body: DEFAULT }] })
  render(<BodySettings />)
  expect(await screen.findByRole('heading', { name: 'Body' })).toBeInTheDocument()
  expect(screen.getByLabelText('Height (cm)')).toHaveValue('')
  expect(screen.getByLabelText(/cm above the top of the kneecap/)).toHaveValue('15')
  expect(screen.getByText(/The same spot every time/)).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: 'Off' })).toBeChecked()
  expect(screen.getByText(/An estimate from waist and neck, ±4%/)).toBeInTheDocument()
  expect(screen.getByText(/a waist and a neck measured on the same day/)).toBeInTheDocument()
})

test('turns the estimate on with a height and a thigh landmark', async () => {
  const saved = { height_cm: 182, thigh_offset_cm: 18, body_fat_estimate: 'navy_male' }
  const asked = serve({
    'GET /api/account/body': [{ status: 200, body: DEFAULT }],
    'PUT /api/account/body': [{ status: 200, body: saved }],
  })
  render(<BodySettings />)
  fireEvent.click(await screen.findByRole('radio', { name: 'On (US Navy formula for men)' }))
  expect(screen.getByText('Add your height to see it.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Height (cm)'), { target: { value: '18x2' } })
  expect(screen.queryByText('Add your height to see it.')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText(/above the top of the kneecap/), {
    target: { value: '18' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(asked[1]).toEqual({ route: 'PUT /api/account/body', body: saved })
  expect(screen.getByRole('radio', { name: 'On (US Navy formula for men)' })).toBeChecked()
})

test('an empty height is sent as none; an empty thigh is caught first', async () => {
  const asked = serve({
    'GET /api/account/body': [
      { status: 200, body: { ...DEFAULT, height_cm: 182, body_fat_estimate: 'navy_male' } },
    ],
    'PUT /api/account/body': [{ status: 200, body: DEFAULT }],
  })
  render(<BodySettings />)
  expect(await screen.findByLabelText('Height (cm)')).toHaveValue('182')
  fireEvent.change(screen.getByLabelText(/above the top of the kneecap/), { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(screen.getByText(/how far above the kneecap/)).toBeInTheDocument()
  expect(asked).toHaveLength(1)
  fireEvent.change(screen.getByLabelText(/above the top of the kneecap/), {
    target: { value: '15' },
  })
  fireEvent.change(screen.getByLabelText('Height (cm)'), { target: { value: '' } })
  fireEvent.click(screen.getByRole('radio', { name: 'Off' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved.')).toBeInTheDocument()
  expect(asked[1].body).toEqual(DEFAULT)
})

test.each([
  [{ status: 422, body: { detail: 'Height must be from 120 to 230 cm.' } }, /from 120 to 230 cm/],
  [{ status: 422, body: { detail: [{ msg: 'bad' }] } }, /Check the numbers/],
  [{ status: 401 }, /Your sign-in ended/],
  [{ status: 500 }, /That didn't work/],
])('a refused save says why', async (reply, text) => {
  serve({
    'GET /api/account/body': [{ status: 200, body: DEFAULT }],
    'PUT /api/account/body': [reply],
  })
  render(<BodySettings />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
})

test.each([401, 500])('hidden when signed out or the server fails (%i)', async (status) => {
  serve({ 'GET /api/account/body': [{ status }] })
  const { container } = render(<BodySettings />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})
