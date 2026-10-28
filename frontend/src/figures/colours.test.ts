import { expect, test } from 'vitest'

// Read from disk (the tests run in frontend/): Vitest hands a CSS import over empty, even as ?raw.
const fs = 'node:fs'
const { readFileSync } = (await import(/* @vite-ignore */ fs)) as {
  readFileSync: (path: string, encoding: 'utf8') => string
}
const css = readFileSync('src/index.css', 'utf8')

/** The tokens set in ``block`` (the light :root, or the dark one), by name. */
function tokens(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]),
  )
}
const dark = tokens(css.slice(css.indexOf('@media (prefers-color-scheme: dark)')))
const light = tokens(css.slice(0, css.indexOf('@media (prefers-color-scheme: dark)')))

/** WCAG contrast between two colours, 1 to 21. */
function contrast(a: string, b: string) {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test('in dark mode a bench, a bar or a frame stands out from the paper', () => {
  // Wood and pads by their fill; iron by its light edge, as its fill stays darker than the body.
  for (const name of ['fig-prop-base', 'fig-bell-line'])
    expect(contrast(dark[name], dark.paper), name).toBeGreaterThanOrEqual(3)
  // and their shaded sides, where a gradient ends
  for (const name of ['fig-prop-dark', 'fig-bell-base'])
    expect(contrast(dark[name], dark.paper), name).toBeGreaterThanOrEqual(2.5)
  expect(
    contrast(dark['fig-bell-base'], dark['fig-near-base']),
    'iron against the body',
  ).toBeGreaterThan(1.8)
})

test('light mode keeps its props as they were', () => {
  expect([light['fig-prop-base'], light['fig-bell-base'], light['fig-bell-line']]).toEqual([
    '#cbbca5',
    '#464b4f',
    '#1b1d1f',
  ])
})
