import { signOut } from '../api'

/** The signed-in pages, in the order the nav shows them. */
const PAGES = [
  { path: '/session', label: 'Today' },
  { path: '/progress', label: 'Progress' },
  { path: '/plan', label: 'Plan' },
  { path: '/tests', label: 'Tests' },
  { path: '/body', label: 'Body' },
  { path: '/account', label: 'Account' },
] as const

/** Sign out here: the server ends this browser's session, then the sign-in page. */
function leave() {
  signOut().finally(() => window.location.assign('/signin'))
}

/** The frame of every signed-in page: the wordmark, a nav between the pages and sign out. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const here = window.location.pathname
  return (
    <div className="page">
      <header className="masthead flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <a href="/" className="wordmark no-underline">
          Training Coach
        </a>
        <nav aria-label="Pages">
          <ul className="flex gap-4">
            {PAGES.map((page) => (
              <li key={page.path}>
                <a
                  href={page.path}
                  aria-current={here === page.path ? 'page' : undefined}
                  className={
                    here === page.path
                      ? 'font-bold text-[var(--bell-ink)] no-underline'
                      : 'text-[var(--ink)] no-underline'
                  }
                >
                  {page.label}
                </a>
              </li>
            ))}
            <li>
              <button type="button" onClick={leave} className="text-[var(--ink)]">
                Sign out
              </button>
            </li>
          </ul>
        </nav>
      </header>
      <main className="mt-4 flex flex-col gap-4">{children}</main>
    </div>
  )
}
