import { useState, useEffect } from 'react'
import api from '../services/api'
import { tokenService } from '../services/tokenService'
import { queryClient } from '../queryClient'
import {
  syncSoundPrefsFromServer,
  type NotificationSoundPresetId,
} from '../utils/notificationSoundPreferences'

interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: string
  is_mfa_enabled?: boolean
  google_account_email?: string | null
  /** Langue des e-mails (fr | en), alignée avec l’UI si synchronisée */
  preferred_locale?: 'en' | 'fr' | null
  /** Effective permission keys from GET /auth/me */
  permissions?: string[]
  /** Forcer le changement de mot de passe à la prochaine connexion (réinitialisation admin). */
  password_must_change?: boolean
  /** Préférences sons (compte), alignées avec le stockage local après GET /auth/me */
  notification_sound_prefs?: {
    enabled: boolean
    mail: NotificationSoundPresetId
    appointment: NotificationSoundPresetId
    other: NotificationSoundPresetId
  }
}

interface LoginResponse {
  mfa_required?: boolean
  mfa_session_id?: string
  access_token?: string
  refresh_token?: string
  token_type?: string
  password_change_required?: boolean
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = tokenService.getAccessToken()
    if (token) {
      fetchUser()
    } else {
      setLoading(false)
    }
  }, [])

  const fetchUser = async () => {
    try {
      const response = await api.get('/auth/me')
      setUser(response.data)
      syncSoundPrefsFromServer(response.data?.notification_sound_prefs)
      setIsAuthenticated(true)
    } catch (error) {
      tokenService.clearTokens()
      setIsAuthenticated(false)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Initial login with username and password
   * Returns LoginResponse which may indicate MFA is required
   */
  const login = async (username: string, password: string): Promise<LoginResponse> => {
    // Send as JSON instead of FormData
    const response = await api.post<LoginResponse>('/auth/login', {
      username: username.trim(),
      password: password.trim(),
    })

    const data = response.data

    // If MFA is required, return the response without storing tokens
    if (data.mfa_required) {
      return data
    }

    // If we have tokens, store them and authenticate
    if (data.access_token) {
      if (data.refresh_token) {
        tokenService.setTokens(data.access_token, data.refresh_token)
      } else {
        tokenService.setAccessToken(data.access_token)
      }
      setIsAuthenticated(true)
      setLoading(false)
      // Fetch user details (this can happen async, don't block)
      fetchUser().catch(() => {
        // If fetchUser fails, we still have the token, so keep authenticated
        // but clear user data
        setUser(null)
      })
    }

    return data
  }

  /**
   * Verify MFA code after initial login
   * @param mfaSessionId - The MFA session ID from the login response
   * @param mfaCode - The 6-digit MFA code
   */
  const verifyMFA = async (mfaSessionId: string, mfaCode: string): Promise<LoginResponse> => {
    // Normalize the code: remove any whitespace and ensure it's exactly 6 digits
    const normalizedCode = mfaCode.replace(/\s/g, '').trim()
    
    // Debug logging in development
    if (import.meta.env.DEV) {
      console.log('🔐 MFA Verification Request:', {
        mfa_session_id: mfaSessionId,
        code: normalizedCode,
        code_length: normalizedCode.length,
        timestamp: new Date().toISOString(),
      })
    }

    try {
      const response = await api.post<LoginResponse>('/auth/mfa/verify', {
        mfa_session_id: mfaSessionId,
        code: normalizedCode,
      })

      const data = response.data

      if (import.meta.env.DEV) {
        console.log('✅ MFA Verification Success:', {
          has_access_token: !!data.access_token,
          has_refresh_token: !!data.refresh_token,
        })
      }

      // Store tokens after successful MFA verification
      if (data.access_token) {
        if (data.refresh_token) {
          tokenService.setTokens(data.access_token, data.refresh_token)
        } else {
          tokenService.setAccessToken(data.access_token)
        }
        setIsAuthenticated(true)
        setLoading(false)
        // Fetch user details
        fetchUser().catch(() => {
          setUser(null)
        })
      }

      return data
    } catch (error: any) {
      // Enhanced error logging
      if (import.meta.env.DEV) {
        console.error('❌ MFA Verification Failed:', {
          status: error.response?.status,
          statusText: error.response?.statusText,
          detail: error.response?.data?.detail,
          message: error.message,
          code_sent: normalizedCode,
        })
      }
      throw error
    }
  }

  /**
   * Setup MFA - Get secret and QR code URL
   */
  const setupMFA = async (): Promise<{ secret: string; otpauth_url: string }> => {
    const response = await api.post('/auth/mfa/setup')
    return response.data
  }

  /**
   * Activate MFA - Enable MFA with verification code
   * @param code - The 6-digit TOTP code from authenticator app
   */
  const activateMFA = async (code: string): Promise<{ message: string }> => {
    const response = await api.post('/auth/mfa/activate', { code })
    // Refresh user data to get updated is_mfa_enabled status
    await fetchUser()
    return response.data
  }

  /**
   * Disable MFA - Disable MFA with verification code
   * @param code - The 6-digit TOTP code from authenticator app
   */
  const disableMFA = async (code: string): Promise<{ message: string }> => {
    const response = await api.post('/auth/mfa/disable', { code })
    // Refresh user data to get updated is_mfa_enabled status
    await fetchUser()
    return response.data
  }

  /**
   * Déconnexion : révoque le refresh côté API (cookie + corps), puis efface stockage et cache React Query.
   */
  const logout = async () => {
    try {
      await api.post('/auth/logout', {
        refresh_token: tokenService.getRefreshToken() || undefined,
      })
    } catch {
      /* ignorer : on nettoie quand même localement */
    } finally {
      tokenService.clearTokens()
      queryClient.clear()
      setUser(null)
      setIsAuthenticated(false)
    }
  }

  const refreshUser = async () => {
    await fetchUser()
  }

  return {
    user,
    isAuthenticated,
    loading,
    login,
    verifyMFA,
    setupMFA,
    activateMFA,
    disableMFA,
    logout,
    refreshUser,
  }
}

