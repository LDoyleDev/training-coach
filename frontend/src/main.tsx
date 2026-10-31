import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Pages from './Pages.tsx'
import { startPwa } from './pwa'
import DailyCheckGate from './readiness/DailyCheckGate.tsx'
import ReadinessGate from './readiness/ReadinessGate.tsx'
import { watchRegion } from './region.ts'
import Unavailable from './Unavailable.tsx'

startPwa()

const root = createRoot(document.getElementById('root')!)
watchRegion(() => root.render(<Unavailable />))
root.render(
  <StrictMode>
    <ReadinessGate>
      <DailyCheckGate>
        <Pages />
      </DailyCheckGate>
    </ReadinessGate>
  </StrictMode>,
)
