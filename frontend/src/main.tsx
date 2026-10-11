import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Pages from './Pages.tsx'
import ReadinessGate from './readiness/ReadinessGate.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ReadinessGate>
      <Pages />
    </ReadinessGate>
  </StrictMode>,
)
