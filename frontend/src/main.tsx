import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Pages from './Pages.tsx'
import { startPwa } from './pwa'
import DailyCheckGate from './readiness/DailyCheckGate.tsx'
import ReadinessGate from './readiness/ReadinessGate.tsx'

startPwa()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ReadinessGate>
      <DailyCheckGate>
        <Pages />
      </DailyCheckGate>
    </ReadinessGate>
  </StrictMode>,
)
