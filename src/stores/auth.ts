import { computed, ref } from 'vue'
import { API_BASE_URL } from '@/lib/apiClient'

const TOKEN_STORAGE_KEY = 'rag-ui-token'

interface LoginCredentials {
  username: string
  password: string
}

interface AccessTokenPayload {
  access_token: string
  token_type?: string
}

const token = ref<string | null>(getInitialToken())
const tokenType = ref<string>('Bearer')
const isAuthenticating = ref(false)
const authError = ref<string | null>(null)

function getInitialToken() {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

function persistToken(value: string | null, type = 'Bearer') {
  token.value = value
  tokenType.value = type ?? 'Bearer'

  if (typeof window === 'undefined') return

  try {
    if (value) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, value)
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // Ignore persistence errors (e.g., private browsing)
  }
}

function normalizeCredential(value: unknown) {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  if (
    value &&
    typeof value === 'object' &&
    'value' in (value as Record<string, unknown>) &&
    typeof (value as Record<string, unknown>).value === 'string'
  ) {
    return (value as Record<string, unknown>).value as string
  }
  if (value instanceof Date) return value.toISOString()
  return value != null ? String(value) : ''
}

async function login(credentials: LoginCredentials) {
  isAuthenticating.value = true
  authError.value = null

  try {
    const username = normalizeCredential(credentials.username).trim()
    const password = normalizeCredential(credentials.password)

    const response = await fetch(`${API_BASE_URL}/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
      }),
    })

    if (!response.ok) {
      const message = await extractAuthError(response)
      throw new Error(message)
    }

    const payload = (await response.json()) as AccessTokenPayload
    if (!payload?.access_token) {
      throw new Error('Token not returned by server.')
    }

    persistToken(payload.access_token, payload.token_type ?? 'Bearer')
    return payload
  } catch (error) {
    authError.value =
      error instanceof Error ? error.message : 'Failed to sign in.'
    throw error
  } finally {
    isAuthenticating.value = false
  }
}

async function register(credentials: LoginCredentials) {
  isAuthenticating.value = true
  authError.value = null

  try {
    const username = normalizeCredential(credentials.username).trim()
    const password = normalizeCredential(credentials.password)

    const response = await fetch(`${API_BASE_URL}/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
      }),
    })

    if (!response.ok) {
      const message = await extractAuthError(response)
      throw new Error(message)
    }

    await login({ username: username, password: password })
  } catch (error) {
    authError.value =
      error instanceof Error ? error.message : 'Registration failed.'
    throw error
  } finally {
    isAuthenticating.value = false
  }
}

function logout() {
  persistToken(null)
}

async function extractAuthError(response: Response) {
  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    try {
      const payload = await response.json()
      if (payload?.detail) {
        if (typeof payload.detail === 'string') return payload.detail
        if (Array.isArray(payload.detail) && payload.detail.length) {
          const first = payload.detail[0]
          if (first?.msg) return first.msg
        }
      }
      if (payload?.message) return payload.message
      if (typeof payload === 'string') return payload
      return JSON.stringify(payload)
    } catch {
      // fall through if JSON parsing fails
    }
  }

  const text = await response.text()
  return text || 'Authentication failed.'
}

const isAuthenticated = computed(() => Boolean(token.value))

export function useAuthStore() {
  return {
    token,
    tokenType,
    isAuthenticated,
    isAuthenticating,
    authError,
    login,
    register,
    logout,
    persistToken,
  }
}
