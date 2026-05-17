import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './i18n/config'
import './styles/global.css'
import App from './App'
import { queryClient } from './queryClient'
import { AppThemeProvider } from './theme/AppThemeProvider'
import { registerPushSoundListener } from './utils/registerPushSoundListener'

registerPushSoundListener()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AppThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
