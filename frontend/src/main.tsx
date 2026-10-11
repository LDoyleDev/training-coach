import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Pages from './Pages.tsx'
import { startPwa } from './pwa'

startPwa()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Pages />
  </StrictMode>,
)
