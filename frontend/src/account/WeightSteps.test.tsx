import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import WeightSteps from './WeightSteps'

type Patch = 'ok' | 'invalid' | 'fail' | 'signed-out'
const DEFAULTS = { barbell: 2.5, dumbbells: 2, machine: 5 }

/** A fake settings API: PATCH merges the steps sent; the default value is the default again. */
function serve(patch: Patch = 'ok', status = 200) {
  let steps = { ...DEFAULTS }
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (status !== 200) return new Response(null, { status })
      if (init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as { increments: Partial<typeof steps> }
        sent.push(body)
        if (patch === 'invalid') return new Response(null, { status: 422 })
        if (patch === 'fail') return new Response(null, { status: 500 })
        if (patch === 'signed-out') return new Response(null, { status: 401 })
        steps = { ...steps, ...body.increments }
      }
      return Response.json({ increments: steps, default_increments: DEFAULTS })
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test('a step of their own replaces the default', async () => {
  const sent = serve()
  render(<WeightSteps />)
  const barbell = await screen.findByRole('textbox', { name: /Barbell/ })
  expect(barbell).toHaveAttribute('placeholder', '2.5')
  const save = screen.getByRole('button', { name: 'Save' })
  expect(save).toBeDisabled() // nothing typed yet
  fireEvent.change(barbell, { target: { value: '1,25' } })
  fireEvent.click(save)
  expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
  expect(sent).toEqual([{ increments: { barbell: 1.25 } }])
  expect(screen.getByRole('textbox', { name: /Barbell/ })).toHaveAttribute('placeholder', '1.25')
  expect(screen.getByText('default 2.5 kg')).toBeInTheDocument()
  expect(screen.getAllByText('the default')).toHaveLength(2) // dumbbells and machine
})

test.each(['1.3', '0', '20.25', 'two', '1.333'])(
  'a step the server would refuse is never sent (%s)',
  async (typed) => {
    const sent = serve()
    render(<WeightSteps />)
    fireEvent.change(await screen.findByRole('textbox', { name: /Dumbbells/ }), {
      target: { value: typed },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByRole('status')).toHaveTextContent('From 0.25 to 20 kg, in steps of 0.25.')
    expect(sent).toEqual([])
  },
)

test.each([
  ['invalid', 'From 0.25 to 20 kg, in steps of 0.25.'],
  ['fail', "That didn't work. Check your connection and try again."],
  ['signed-out', 'Your sign-in ended. Sign in again, then retry.'],
] as const)('a save that fails says so (%s)', async (patch, text) => {
  serve(patch)
  render(<WeightSteps />)
  fireEvent.change(await screen.findByRole('textbox', { name: /Machine/ }), {
    target: { value: '2.5' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('status')).toHaveTextContent(text)
})

test.each([401, 500])('hidden when the settings do not load (%i)', async (status) => {
  serve('ok', status)
  const { container } = render(<WeightSteps />)
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
  await Promise.resolve()
  expect(container).toBeEmptyDOMElement()
})
