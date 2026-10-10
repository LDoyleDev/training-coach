import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Readiness } from '../api'
import ReadinessPage from './ReadinessPage'

const QUESTIONS = [
  { key: 'heart', text: 'Heart condition?' },
  { key: 'joints', text: 'Joint problem?' },
]
const DUE: Readiness = {
  questions: QUESTIONS,
  status: 'due',
  answers: null,
  answered_at: null,
  ask_again_after: null,
}

function serve(readiness: Readiness | null | 'error', saved: string | number = 'clear') {
  const sent: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        sent.push(JSON.parse(String(init.body)))
        if (typeof saved === 'number') return new Response(null, { status: saved })
        return Response.json({ status: saved })
      }
      if (readiness === 'error') return new Response(null, { status: 500 })
      if (readiness === null) return new Response(null, { status: 401 })
      return Response.json(readiness)
    }),
  )
  return sent
}

afterEach(() => {
  vi.unstubAllGlobals()
})

/** The Yes or No radio of one question (a fieldset named by its question). */
function within(question: string, value: 'Yes' | 'No'): HTMLElement {
  const group = screen.getByRole('group', { name: question })
  const radio = Array.from(group.querySelectorAll('label')).find((l) => l.textContent === value)
  if (!radio) throw new Error(`no ${value} for ${question}`)
  return radio.querySelector('input') as HTMLElement
}

test('saving needs every question answered, then says what the answers mean', async () => {
  const sent = serve(DUE, 'see_doctor')
  render(<ReadinessPage />)
  const save = await screen.findByRole('button', { name: 'Save my answers' })
  expect(save).toBeDisabled()
  fireEvent.click(within('Heart condition?', 'Yes'))
  expect(save).toBeDisabled()
  fireEvent.click(within('Joint problem?', 'No'))
  fireEvent.click(save)
  expect(await screen.findByText(/Check with a doctor before hard efforts/)).toBeInTheDocument()
  expect(sent).toEqual([{ answers: { heart: true, joints: false } }])
})

test('all no says nothing holds you back', async () => {
  serve(DUE, 'clear')
  render(<ReadinessPage />)
  await screen.findByRole('group', { name: 'Heart condition?' })
  fireEvent.click(within('Heart condition?', 'No'))
  fireEvent.click(within('Joint problem?', 'No'))
  fireEvent.click(screen.getByRole('button', { name: 'Save my answers' }))
  expect(await screen.findByText(/Nothing in your answers says to hold back/)).toBeInTheDocument()
})

test('earlier answers are filled in, with when they are asked again', async () => {
  serve({
    ...DUE,
    status: 'clear',
    answers: { heart: false, joints: true },
    answered_at: '2026-10-10T12:00:00Z',
    ask_again_after: '2027-04-10T12:00:00Z',
  })
  render(<ReadinessPage />)
  expect(
    await screen.findByText(/Answered 10 Oct 2026; asked again after 10 Apr 2027/),
  ).toBeInTheDocument()
  expect(within('Joint problem?', 'Yes')).toBeChecked()
  expect(screen.getByRole('button', { name: 'Save my answers' })).toBeEnabled()
})

test('signed out, it points to sign in', async () => {
  serve(null)
  render(<ReadinessPage />)
  expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute(
    'href',
    expect.stringMatching(/^\/signin\?next=/),
  )
})

test('a failed load says so', async () => {
  serve('error')
  render(<ReadinessPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load the questions")
})

test('a sign-in that ended while saving points to sign in again', async () => {
  serve(DUE, 401)
  render(<ReadinessPage />)
  await screen.findByRole('group', { name: 'Heart condition?' })
  fireEvent.click(within('Heart condition?', 'No'))
  fireEvent.click(within('Joint problem?', 'No'))
  fireEvent.click(screen.getByRole('button', { name: 'Save my answers' }))
  expect(await screen.findByRole('link', { name: 'Sign in again' })).toBeInTheDocument()
})

test('a failed save says so', async () => {
  serve(DUE, 500)
  render(<ReadinessPage />)
  await screen.findByRole('group', { name: 'Heart condition?' })
  fireEvent.click(within('Heart condition?', 'No'))
  fireEvent.click(within('Joint problem?', 'No'))
  fireEvent.click(screen.getByRole('button', { name: 'Save my answers' }))
  expect(await screen.findByText(/Couldn't save/)).toBeInTheDocument()
})
