import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles.css'
import { bootTheme } from './theme'

// Before the first paint. A stored dark choice applied in an effect shows the
// light theme for one frame first, which is the flash every themed site gets
// wrong exactly once.
bootTheme()

const el = document.getElementById('root')
if (el)
  createRoot(el).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>
  )
