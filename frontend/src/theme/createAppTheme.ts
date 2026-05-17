import { alpha, createTheme, ThemeOptions } from '@mui/material/styles'

const sharedTypography = {
  fontFamily: [
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
  ].join(','),
  h4: {
    fontWeight: 700,
    letterSpacing: '-0.02em',
  },
  h5: {
    fontWeight: 600,
    letterSpacing: '-0.01em',
  },
  h6: {
    fontWeight: 600,
  },
  button: {
    textTransform: 'none' as const,
    fontWeight: 600,
  },
}

const sharedShape = { borderRadius: 8 }

const sharedComponents: ThemeOptions['components'] = {
  MuiButton: {
    styleOverrides: {
      root: {
        borderRadius: 8,
        padding: '10px 22px',
        boxShadow: 'none',
        fontWeight: 600,
        textTransform: 'none',
        transition: 'background-color 0.2s ease, box-shadow 0.2s ease',
        '&:hover': {
          boxShadow: 'none',
        },
      },
      contained: {
        '&:hover': {
          boxShadow: '0 4px 14px rgba(21, 101, 192, 0.28)',
        },
      },
    },
  },
  MuiCard: {
    styleOverrides: {
      root: ({ theme }) => ({
        borderRadius: 8,
        boxShadow:
          theme.palette.mode === 'dark'
            ? '0 1px 3px rgba(0, 0, 0, 0.4)'
            : '0 1px 3px rgba(0, 0, 0, 0.08)',
        border: `1px solid ${theme.palette.divider}`,
        transition: 'box-shadow 0.2s ease',
        '&:hover': {
          boxShadow:
            theme.palette.mode === 'dark'
              ? '0 4px 12px rgba(0, 0, 0, 0.45)'
              : '0 4px 12px rgba(0, 0, 0, 0.08)',
        },
      }),
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        borderRadius: 12,
        backgroundImage: 'none',
      },
      elevation1: {
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
      },
      elevation3: {
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)',
      },
    },
  },
  MuiTextField: {
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-root': {
          borderRadius: 8,
        },
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: 6,
        fontWeight: 500,
      },
    },
  },
  MuiLink: {
    styleOverrides: {
      root: {
        fontWeight: 500,
      },
    },
  },
  MuiTableCell: {
    styleOverrides: {
      head: ({ theme }) => ({
        backgroundColor:
          theme.palette.mode === 'dark'
            ? alpha(theme.palette.common.white, 0.08)
            : theme.palette.grey[100],
        color: theme.palette.text.primary,
        fontWeight: 700,
        borderBottom: `2px solid ${theme.palette.divider}`,
      }),
    },
  },
  MuiTableSortLabel: {
    styleOverrides: {
      root: ({ theme }) => ({
        color: theme.palette.text.secondary,
        '&:hover': { color: theme.palette.text.primary },
        '&.Mui-active': { color: theme.palette.text.primary },
      }),
      icon: { color: 'inherit', opacity: 0.65 },
    },
  },
}

export function createAppTheme(mode: 'light' | 'dark') {
  const palette: ThemeOptions['palette'] =
    mode === 'light'
      ? {
          mode: 'light',
          primary: {
            main: '#1565c0',
            light: '#42a5f5',
            dark: '#0d47a1',
            contrastText: '#ffffff',
          },
          secondary: {
            main: '#00838f',
            light: '#4fb3bf',
            dark: '#005662',
            contrastText: '#ffffff',
          },
          success: {
            main: '#2e7d32',
            light: '#4caf50',
            dark: '#1b5e20',
          },
          warning: {
            main: '#ef6c00',
            light: '#ff9800',
            dark: '#e65100',
          },
          error: {
            main: '#c62828',
            light: '#ef5350',
            dark: '#b71c1c',
          },
          info: {
            main: '#0277bd',
            light: '#039be5',
            dark: '#01579b',
          },
          background: {
            default: '#e8eef5',
            paper: '#ffffff',
          },
          text: {
            primary: '#1c2836',
            secondary: '#546e7a',
          },
          divider: 'rgba(21, 101, 192, 0.12)',
        }
      : {
          mode: 'dark',
          primary: {
            main: '#64b5f6',
            light: '#90caf9',
            dark: '#42a5f5',
            contrastText: '#0a1929',
          },
          secondary: {
            main: '#4fb3bf',
            light: '#80cbc4',
            dark: '#00838f',
            contrastText: '#000000',
          },
          success: {
            main: '#66bb6a',
            light: '#81c784',
            dark: '#388e3c',
          },
          warning: {
            main: '#ffa726',
            light: '#ffb74d',
            dark: '#f57c00',
          },
          error: {
            main: '#ef5350',
            light: '#e57373',
            dark: '#c62828',
          },
          info: {
            main: '#29b6f6',
            light: '#4fc3f7',
            dark: '#0277bd',
          },
          background: {
            default: '#0f1419',
            paper: '#1a222c',
          },
          text: {
            primary: '#e8eef5',
            secondary: '#9eacb8',
          },
          divider: 'rgba(144, 202, 249, 0.14)',
        }

  return createTheme({
    palette,
    typography: sharedTypography,
    shape: sharedShape,
    components: sharedComponents,
  })
}
