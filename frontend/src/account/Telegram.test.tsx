import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Telegram from './Telegram'

type Reply = { status: number; body?: unknown }

function serve(routes: Record<string, Reply | Reply[]>) {
  const asked: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const route = `${init?.method ?? 'GET'} ${path}`
      asked.push(`${route} ${typeof init?.body === 'string' ? init.body : ''}`.trim())
      const found = routes[route]
      const reply = (Array.isArray(found)
        ? found.length > 1
          ? found.shift()
          : found[0]
        : found) ?? { status: 500 }
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status: reply.status,
      })
    }),
  )
  return asked
}

const STATUS = '/api/account/telegram'
const status = (over: Record<string, unknown> = {}): Reply => ({
  status: 200,
  body: {
    set_on_server: false,
    connected: false,
    name: null,
    since: null,
    pending: null,
    ...over,
  },
})
const pending = (claims: number) =>
  status({ pending: { expires_at: '2026-11-08T12:10:00Z', claims } })
const URL = 'https://t.me/tc_bot?start=' + 'ab'.repeat(20)

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

test.each([
  ['signed out', { status: 401 }],
  ['closed to members', { status: 403 }],
  ['a failure', { status: 500 }],
])('hidden when %s', async (_why, reply) => {
  serve({ [`GET ${STATUS}`]: reply })
  const { container } = render(<Telegram />)
  await new Promise((r) => setTimeout(r, 0))
  expect(container).toBeEmptyDOMElement()
})

test('the owner sees it is set on the server, with nothing to change', async () => {
  serve({ [`GET ${STATUS}`]: status({ set_on_server: true, connected: true }) })
  render(<Telegram />)
  expect(await screen.findByText('Your Telegram account is set on the server.')).toBeVisible()
  expect(screen.queryByRole('button')).toBeNull()
})

test('a member connects: link, code, name, Confirm', async () => {
  const asked = serve({
    [`GET ${STATUS}`]: [
      status(),
      pending(0),
      pending(1),
      status({ connected: true, name: 'Mum', since: '2026-11-08T12:00:00Z' }),
    ],
    [`POST ${STATUS}/link`]: { status: 200, body: { url: URL, expires_at: '2026-11-08T12:10Z' } },
    [`POST ${STATUS}/code`]: { status: 200, body: { name: 'Mum' } },
    [`POST ${STATUS}/confirm`]: { status: 204 },
  })
  render(<Telegram />)
  fireEvent.click(await screen.findByRole('button', { name: 'Connect Telegram' }))
  const open = await screen.findByRole('link', { name: 'Open Telegram' })
  expect(open).toHaveAttribute('href', URL)
  expect(screen.getByText(/Never type a code someone sends you/)).toBeVisible()
  expect(screen.getByText('Opened in Telegram: 0 times.')).toBeVisible()
  fireEvent(window, new Event('focus')) // back from Telegram
  expect(await screen.findByText('Opened in Telegram: 1 time.')).toBeVisible()
  const check = screen.getByRole('button', { name: 'Check the code' })
  expect(check).toBeDisabled()
  fireEvent.change(screen.getByRole('textbox', { name: 'Code from the bot' }), {
    target: { value: '12 34-56' },
  })
  fireEvent.click(check)
  expect(await screen.findByText('Mum')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  expect(await screen.findByText('Connected as Mum since 8 Nov 2026.')).toBeVisible()
  expect(asked).toContain(`POST ${STATUS}/code {"code":"123456"}`)
  expect(asked).toContain(`POST ${STATUS}/confirm {"code":"123456"}`)
})

test('with more than one claim Confirm is off', async () => {
  serve({ [`GET ${STATUS}`]: pending(2), [`DELETE ${STATUS}/link`]: { status: 204 } })
  render(<Telegram />)
  expect(
    await screen.findByText('Someone else used this link too: cancel it and make a new one.'),
  ).toBeVisible()
  expect(screen.queryByRole('textbox')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled()
})

test.each([
  [400, 'That’s not the code. Check the bot’s message and type it again.'],
  [410, 'Too many wrong codes, so that link has ended. Make a new one.'],
  [404, 'That link has expired. Make a new one.'],
  [409, 'That Telegram account can’t be connected. Cancel and make a new link.'],
])('a refused code (%i) says why', async (code, text) => {
  serve({ [`GET ${STATUS}`]: pending(1), [`POST ${STATUS}/code`]: { status: code } })
  render(<Telegram />)
  fireEvent.change(await screen.findByRole('textbox', { name: 'Code from the bot' }), {
    target: { value: '654321' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Check the code' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
  expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
})

test('cancel ends the link', async () => {
  const asked = serve({
    [`GET ${STATUS}`]: [pending(1), status()],
    [`DELETE ${STATUS}/link`]: { status: 204 },
  })
  render(<Telegram />)
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('button', { name: 'Connect Telegram' })).toBeVisible()
  expect(asked).toContain(`DELETE ${STATUS}/link`)
})

test('the bot being off is said plainly', async () => {
  serve({ [`GET ${STATUS}`]: status(), [`POST ${STATUS}/link`]: { status: 503 } })
  render(<Telegram />)
  fireEvent.click(await screen.findByRole('button', { name: 'Connect Telegram' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The Telegram bot is off just now.')
})

test('a stale sign-in asks to confirm it is you', async () => {
  serve({
    [`GET ${STATUS}`]: status(),
    [`POST ${STATUS}/link`]: { status: 403 },
    'POST /api/auth/passkeys/confirm/options': { status: 409 }, // no passkey here
  })
  render(<Telegram />)
  fireEvent.click(await screen.findByRole('button', { name: 'Connect Telegram' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('confirm it’s you')
})

test('a connected member unlinks after saying so', async () => {
  const asked = serve({
    [`GET ${STATUS}`]: [status({ connected: true, name: 'Mum', since: null }), status()],
    [`DELETE ${STATUS}`]: { status: 204 },
  })
  render(<Telegram />)
  expect(await screen.findByText('Connected as Mum.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Unlink' }))
  fireEvent.click(screen.getByRole('button', { name: 'Keep it' }))
  expect(asked).not.toContain(`DELETE ${STATUS}`)
  fireEvent.click(screen.getByRole('button', { name: 'Unlink' }))
  fireEvent.click(screen.getByRole('button', { name: 'Unlink Telegram' }))
  expect(await screen.findByRole('button', { name: 'Connect Telegram' })).toBeVisible()
  expect(asked).toContain(`DELETE ${STATUS}`)
})

test('a failed unlink says so', async () => {
  serve({
    [`GET ${STATUS}`]: status({ connected: true, name: 'Mum' }),
    [`DELETE ${STATUS}`]: { status: 401 },
  })
  render(<Telegram />)
  fireEvent.click(await screen.findByRole('button', { name: 'Unlink' }))
  fireEvent.click(screen.getByRole('button', { name: 'Unlink Telegram' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your sign-in ended.')
})
