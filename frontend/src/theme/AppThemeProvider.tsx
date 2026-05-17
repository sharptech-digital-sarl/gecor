import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles'
import useMediaQuery from '@mui/material/useMediaQuery'
import CssBaseline from '@mui/material/CssBaseline'
import { createAppTheme } from './createAppTheme'

const STORAGE_KEY = 'fpi_theme_preference'

export type ThemePreference = 'light' | 'dark' | 'system'

type AppThemeContextValue = {
  preference: ThemePreference
  setPreference: (p: ThemePreference) => void
  resolvedMode: 'light' | 'dark'
}

const AppThemeContext = createContext<AppThemeContextValue | null>(null)

function readStoredPreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    /* ignore */
  }
  return 'system'
}

export function useAppThemeMode(): AppThemeContextValue {
  const ctx = useContext(AppThemeContext)
  if (!ctx) {
    throw new Error('useAppThemeMode must be used within AppThemeProvider')
  }
  return ctx
}

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference)
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)', { noSsr: true })

  const resolvedMode: 'light' | 'dark' =
    preference === 'system' ? (prefersDark ? 'dark' : 'light') : preference

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, preference)
    } catch {
      /* ignore */
    }
  }, [preference])

  const setPreference = (p: ThemePreference) => setPreferenceState(p)

  const theme = useMemo(() => createAppTheme(resolvedMode), [resolvedMode])

  const value = useMemo(
    () => ({ preference, setPreference, resolvedMode }),
    [preference, resolvedMode],
  )

  return (
    <AppThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </AppThemeContext.Provider>
  )
}
