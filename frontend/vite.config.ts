/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'

/**
 * Writes dist/sw.js from src/pwa/sw.js with this build's version and app shell (index.html and
 * the hashed scripts and styles), so each deploy ships a new worker that caches the new files.
 */
function serviceWorker(): Plugin {
  return {
    name: 'training-coach:sw',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const template = readFileSync(new URL('./src/pwa/sw.js', import.meta.url), 'utf8')
      const files = Object.keys(bundle)
        .filter((name) => /^assets\/.+\.(js|css)$/.test(name))
        .sort()
      const shell = ['/index.html', ...files.map((name) => `/${name}`)]
      const version = createHash('sha256')
        .update(template + shell.join('\n'))
        .digest('hex')
        .slice(0, 12)
      const source = template
        .replace(/^const VERSION = .*$/m, `const VERSION = '${version}'`)
        .replace(/^const SHELL = .*$/m, `const SHELL = ${JSON.stringify(shell)}`)
      if (!source.includes(version) || shell.length < 2) throw new Error('sw.js was not filled in')
      this.emitFile({ type: 'asset', fileName: 'sw.js', source })
    },
  }
}

// The backend (FastAPI) serves the built app from /; in dev, API calls are proxied to it.
export default defineConfig({
  plugins: [react(), tailwindcss(), serviceWorker()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/healthz': 'http://localhost:8080',
    },
    // Besides the app, only the seed: a figures test checks step names against plan.toml.
    fs: {
      allow: [
        fileURLToPath(new URL('.', import.meta.url)),
        fileURLToPath(new URL('../backend/src/training_coach/seed/', import.meta.url)),
      ],
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // CLAUDE.md: coverage >= 80%, same floor as the backend.
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/test/**', 'src/**/*.test.{ts,tsx}', 'src/**/*.d.ts'],
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
})
