import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import SignIn from './SignIn.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>{window.location.pathname === '/signin' ? <SignIn /> : <App />}</StrictMode>,
)
