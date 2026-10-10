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

/**
 * The frame of every signed-in page: the wordmark, the pages and sign out. On a phone the
 * pages are a tab bar along the bottom, in thumb reach, with 56px targets; sign out is then
 * on the Account page. From 640px up they sit in the header.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const here = window.location.pathname
  return (
    <div className="page">
      <header className="masthead flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <a href="/" className="wordmark no-underline">
          Training Coach
        </a>
        <nav
          aria-label="Pages"
          className="fixed inset-x-0 bottom-0 z-20 border-t-2 border-[var(--ink)] bg-[var(--paper)] pb-[env(safe-area-inset-bottom)] sm:static sm:border-0 sm:bg-transparent sm:pb-0"
        >
          <ul className="m-0 grid list-none grid-cols-6 p-0 sm:flex sm:flex-wrap sm:items-center sm:gap-x-4 sm:gap-y-1">
            {PAGES.map((page) => (
              <li key={page.path}>
                <a
                  href={page.path}
                  aria-current={here === page.path ? 'page' : undefined}
                  className={
                    'flex min-h-14 items-center justify-center px-1 text-[0.8125rem] no-underline sm:min-h-11 sm:px-0 sm:text-base ' +
                    (here === page.path
                      ? 'font-bold text-[var(--bell-ink)] shadow-[inset_0_3px_0_var(--bell-ink)] sm:shadow-none'
                      : 'text-[var(--ink)]')
                  }
                >
                  {page.label}
                </a>
              </li>
            ))}
            <li className="hidden sm:block">
              <button type="button" onClick={leave}>
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
