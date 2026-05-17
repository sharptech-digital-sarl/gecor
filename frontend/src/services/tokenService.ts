/**
 * Token Service
 * Manages access tokens and refresh tokens storage and retrieval
 */

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export const tokenService = {
  /**
   * Get the stored access token
   */
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  },

  /**
   * Get the stored refresh token
   */
  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },

  /**
   * Store both access and refresh tokens
   */
  setTokens(accessToken: string, refreshToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  },

  /**
   * Update only the access token (keep refresh token)
   */
  setAccessToken(accessToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  },

  /**
   * Clear all tokens
   */
  clearTokens(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },

  /**
   * Check if user has tokens (is potentially authenticated)
   */
  hasTokens(): boolean {
    return !!this.getAccessToken() || !!this.getRefreshToken()
  },
}

