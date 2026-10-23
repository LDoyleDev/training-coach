import { useState } from 'react'
import AppShell from '../components/AppShell'
import TestsPage from '../tests/TestsPage'
import BodyPage from './BodyPage'

type Tab = 'body' | 'tests'

const TABS: [Tab, string][] = [
  ['body', 'Measurements'],
  ['tests', 'Tests'],
]

const tab =
  'min-h-11 flex-1 rounded-xl border-2 border-[var(--ink)] px-3 font-bold text-[var(--ink)] aria-selected:bg-[var(--ink)] aria-selected:text-[var(--chalk)]'

/** /body: measurements and photos, and the fitness tests as its second tab (ADR-0069; /tests
 * opens it as ?tab=tests). */
export default function BodyTabs() {
  const [shown, setShown] = useState<Tab>(() =>
    new URLSearchParams(window.location.search).get('tab') === 'tests' ? 'tests' : 'body',
  )
  const show = (next: Tab) => {
    setShown(next)
    window.history.replaceState(null, '', next === 'tests' ? '/body?tab=tests' : '/body')
  }
  return (
    <AppShell>
      <h1 className="text-3xl font-extrabold">Body</h1>
      <div role="tablist" aria-label="Body" className="flex gap-2">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={shown === key}
            className={tab}
            onClick={() => show(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="flex flex-col gap-4">
        {shown === 'tests' ? <TestsPage embedded /> : <BodyPage embedded />}
      </div>
    </AppShell>
  )
}
