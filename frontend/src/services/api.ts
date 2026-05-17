import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { tokenService } from './tokenService'

/**
 * Normalize API URL to prevent duplication of /api/v1
 * This function extracts the base URL (protocol + host + port) and adds /api/v1 exactly once
 */
function normalizeApiUrl(url: string): string {
  if (!url) return 'http://localhost:8000/api/v1'
  
  // Remove trailing slashes
  url = url.replace(/\/+$/, '')
  
  // Extract protocol, host, and port using regex
  // Matches: http://localhost:8000 or https://example.com:443
  const match = url.match(/^(https?:\/\/[^\/]+)/)
  
  if (!match) {
    // Fallback if URL format is unexpected
    console.warn('Unexpected API URL format:', url)
    return 'http://localhost:8000/api/v1'
  }
  
  const baseUrl = match[1] // e.g., "http://localhost:8000"
  
  // Check if /api/v1 is already in the URL and remove it
  //const pathAfterBase = url.substring(match[1].length)
  //const normalizedPath = pathAfterBase.replace(/^\/api\/v1\/?/, '')
  
  // Always construct with /api/v1 exactly once
  // This ensures baseURL is always http://localhost:8000/api/v1
  return `${baseUrl}/api/v1`
}

// Get and normalize the API URL
// Handle both cases: with or without /api/v1 in the environment variable
const originalApiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
let rawApiUrl = originalApiUrl
// Remove /api/v1 if present, we'll add it back in normalizeApiUrl
rawApiUrl = rawApiUrl.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '')
const API_URL = normalizeApiUrl(rawApiUrl)

// Debug logs
if (import.meta.env.DEV) {
  console.log('Original VITE_API_URL:', originalApiUrl)
  console.log('Normalized API Base URL:', API_URL)
}

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Flag to prevent infinite refresh loops
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: any) => void
  reject: (error?: any) => void
}> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Request interceptor to add auth token and fix any URL duplication
api.interceptors.request.use(
  (config) => {
    const token = tokenService.getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    // Fix any URL duplication: baseURL already contains /api/v1, so remove it from the path if present
    if (config.url) {
      // Remove /api/v1 from the beginning of the URL path if it exists
      // This prevents duplication since baseURL already has /api/v1
      // Handle both /api/v1/ and api/v1/ (with or without leading slash)
      config.url = config.url.replace(/^\/?api\/v1\/?/, '')
      
      // Ensure the URL starts with / (axios requires absolute paths)
      if (!config.url.startsWith('/')) {
        config.url = '/' + config.url
      }
    }
    
    // Debug: Log the final URL in development
    if (import.meta.env.DEV && config.url) {
      const finalUrl = (config.baseURL || '') + config.url
      console.log('Request URL:', finalUrl)
      if (finalUrl.includes('/api/v1/api/v1')) {
        console.warn('⚠️ URL duplication detected!', finalUrl)
        console.warn('BaseURL:', config.baseURL)
        console.warn('Path:', config.url)
      }
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle errors and refresh tokens
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`
            }
            return api(originalRequest)
          })
          .catch((err) => {
            return Promise.reject(err)
          })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = tokenService.getRefreshToken()

      if (!refreshToken) {
        processQueue(error, null)
        isRefreshing = false
        try {
          await axios.post(`${API_URL}/auth/logout`, {}, {
            withCredentials: true,
            headers: { 'Content-Type': 'application/json' },
          })
        } catch {
          /* ignore */
        }
        tokenService.clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        // Try to refresh the access token (cookie httpOnly + corps si présent en localStorage)
        const response = await axios.post(
          `${API_URL}/auth/refresh`,
          { refresh_token: refreshToken },
          {
            headers: {
              'Content-Type': 'application/json',
            },
            withCredentials: true,
          }
        )

        const { access_token, refresh_token: newRefreshToken } = response.data

        // Update tokens
        if (newRefreshToken) {
          tokenService.setTokens(access_token, newRefreshToken)
        } else {
          tokenService.setAccessToken(access_token)
        }

        // Update the original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`
        }

        // Process queued requests
        processQueue(null, access_token)
        isRefreshing = false

        // Retry the original request
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        isRefreshing = false
        try {
          await axios.post(
            `${API_URL}/auth/logout`,
            { refresh_token: refreshToken },
            { withCredentials: true, headers: { 'Content-Type': 'application/json' } }
          )
        } catch {
          /* ignore */
        }
        tokenService.clearTokens()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    // For other errors, just reject
    return Promise.reject(error)
  }
)

/** Base `.../api/v1` pour les appels hors axios (ex. SSE). */
export { API_URL }

export default api

