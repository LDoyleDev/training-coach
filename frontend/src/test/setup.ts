import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

// Consent is read once per page and shared (ADR-0090): each test starts unread. Imported late,
// so a test file's vi.mock of what the api imports still applies.
afterEach(async () => (await import('../consent/useConsent')).forgetConsents())
