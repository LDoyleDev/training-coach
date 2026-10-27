import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { emptyWeek } from '../test/cardioWeek'
import ExtraCardio from './ExtraCardio'

type Patch = 'ok' | 'invalid' | 'fail' | 'signed-out'

/** The cycle gives zone 2 45-75 and all cardio 75-115; extra cardio adds to both (ADR-0079). */
function serve(patch: Patch = 'ok', signedOut = false) {
  let extra = 0
  const sent: unknown[] = []
  const week = () =>
    emptyWeek({ zone2_target: [45 + extra, 75 + extra], total_target: [75 + extra, 115 + extra] })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (signedOut) return new Response(null, { status: 401 })
      if (path === '/api/cardio')
        return Response.json({ planned: null, activities: [], week: week() })
      if (init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as { extra_cardio_min: number }
        sent.push(body)
        if (patch === 'invalid') return new Response(null, { status: 422 })
        if (patch === 'fail') return new Response(null, { status: 500 })
        if (patch === 'signed-out') return new Response(null, { status: 401 })
        extra = body.extra_cardio_min
      }
      return Response.json({ extra_cardio_min: extra })
    }),
  )
  return sent
}

afterEach(() => vi.unstubAllGlobals())

test('a preset adds to both targets', async () => {
  const sent = serve()
  render(<ExtraCardio />)
  expect(await screen.findByRole('heading', { name: 'Extra cardio a week' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText(/^Targets for 7 days/)).toHaveTextContent(
    'Targets for 7 days: zone 2 45–75 min, all cardio 75–115 min.',
  )
  fireEvent.click(screen.getByRole('button', { name: '60 min' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Saved: 60 min a week.')
  expect(sent).toEqual([{ extra_cardio_min: 60 }])
  expect(screen.getByRole('button', { name: '60 min' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText(/^Targets for 7 days/)).toHaveTextContent(
    'Targets for 7 days: zone 2 105–135 min, all cardio 135–175 min.',
  )
  fireEvent.click(screen.getByRole('button', { name: '60 min' })) // already on: nothing sent
  fireEvent.click(screen.getByRole('button', { name: 'None' }))
  expect(await screen.findByText('Saved: none.')).toBeInTheDocument()
})

test('a number of its own', async () => {
  const sent = serve()
  render(<ExtraCardio />)
  const box = await screen.findByRole('textbox', { name: 'Or minutes a week' })
  const save = screen.getByRole('button', { name: 'Save' })
  // A space once saved 0 (review of #391): blank, not whole minutes or out of range never saves.
  for (const value of ['', ' ', '  \t', '4.5', '1e2', '-5', '601', 'abc', '30 min']) {
    fireEvent.change(box, { target: { value } })
    expect(save).toBeDisabled()
    fireEvent.submit(box.closest('form')!)
  }
  expect(sent).toEqual([])
  expect(screen.getByRole('status')).toHaveTextContent('Whole minutes from 0 to 600.')
  fireEvent.change(box, { target: { value: ' 45 ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Saved: 45 min a week.')).toBeInTheDocument()
  expect(sent).toEqual([{ extra_cardio_min: 45 }])
  expect(box).toHaveAttribute('placeholder', '45') // not a preset: shown in the box
  expect(screen.getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'false')
})

test.each([
  ['invalid', 'Whole minutes from 0 to 600.'],
  ['fail', "That didn't work. Check your connection and try again."],
  ['signed-out', 'Your sign-in ended. Sign in again, then retry.'],
] as const)('a refused save says why (%s)', async (patch, text) => {
  serve(patch)
  render(<ExtraCardio />)
  fireEvent.click(await screen.findByRole('button', { name: '30 min' }))
  expect(await screen.findByText(text)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true')
})

test('saved, but the targets could not be refreshed: the new setting still shows', async () => {
  serve()
  render(<ExtraCardio />)
  fireEvent.click(await screen.findByRole('button', { name: '30 min' }))
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 500 })),
  )
  expect(
    await screen.findByText("Couldn't refresh the targets. Reload the page to see them."),
  ).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Saved: 30 min a week.')
  expect(screen.getByRole('button', { name: '30 min' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.queryByText(/didn't work/)).not.toBeInTheDocument()
})

test('signed out, it stays hidden', async () => {
  serve('ok', true)
  const { container } = render(<ExtraCardio />)
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(container).toBeEmptyDOMElement()
})
