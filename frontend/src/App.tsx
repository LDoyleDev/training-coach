import { useEffect, useState } from 'react'

type Health = { status: string; version: string; bot_enabled: boolean }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    fetch('/healthz')
      .then((res) => (res.ok ? (res.json() as Promise<Health>) : null))
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  return (
    <main className="flex min-h-dvh items-center justify-center bg-neutral-50 p-6 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Training Coach</h1>
        <p className="mt-2 text-sm text-neutral-500">
          {health ? `v${health.version} · API ${health.status}` : 'Connecting…'}
        </p>
      </div>
    </main>
  )
}
