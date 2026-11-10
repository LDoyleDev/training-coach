import { expect, test } from 'vitest'

// Read from disk (the tests run in frontend/), as colours.test.ts reads index.css.
const fs = 'node:fs'
const { readdirSync, readFileSync } = (await import(/* @vite-ignore */ fs)) as {
  readdirSync: (path: string, options: { recursive: true }) => string[]
  readFileSync: (path: string, encoding: 'utf8') => string
}

const sources = readdirSync('src', { recursive: true })
  .map((path) => path.replaceAll('\\', '/'))
  .filter((path) => path.endsWith('.tsx') && !path.endsWith('.test.tsx'))

/** index.css's `.block` is a page section, with a rule above it and 3rem of padding, and it wins
 * over Tailwind's `block` utility. So `block` belongs only on a section on its own: anything
 * else (a choice's second line, say) would sit far below a rule. */
test.each(sources)("%s uses index.css's block only for a page section", (path) => {
  // Plain class lists and template literals; a class list built elsewhere (a helper such as
  // a choice's) isn't seen here.
  const source = readFileSync(`src/${path}`, 'utf8')
  const misused = [...source.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)]
    .map((m) => (m[1] ?? m[2]).replace(/\$\{[^}]*\}/g, ' ').trim())
    .filter((names) => names.split(/\s+/).includes('block') && names !== 'block')
  expect(misused).toEqual([])
})
