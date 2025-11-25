import { useAuthStore } from '@/stores/auth'

const DEFAULT_API_BASE_URL = 'http://0.0.0.0:8000'

export const API_BASE_URL =
  typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL
    : DEFAULT_API_BASE_URL

export interface ApiRequestOptions extends RequestInit {
  auth?: boolean
  parseJson?: boolean
}

async function extractErrorMessage(response: Response) {
  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    try {
      const payload = await response.json()
      if (typeof payload === 'string') {
        return payload
      }
      if (payload?.detail) {
        if (typeof payload.detail === 'string') {
          return payload.detail
        }
        if (Array.isArray(payload.detail) && payload.detail.length) {
          const first = payload.detail[0]
          if (typeof first === 'string') return first
          if (first?.msg) return first.msg
        }
      }
      if (payload?.message) {
        return payload.message
      }
      return JSON.stringify(payload)
    } catch {
      // fall through
    }
  }

  const text = await response.text()
  return text || response.statusText || 'Request failed'
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    auth = true,
    parseJson = true,
    headers: incomingHeaders,
    ...rest
  } = options

  const authStore = useAuthStore()
  const headers = new Headers(incomingHeaders ?? {})

  const isFormData =
    rest.body instanceof FormData || rest.body instanceof URLSearchParams

  if (!headers.has('Content-Type') && rest.body && !isFormData) {
    headers.set('Content-Type', 'application/json')
  }

  if (auth && authStore.token.value) {
    const type = authStore.tokenType.value || 'Bearer'
    headers.set('Authorization', `${type} ${authStore.token.value}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
  })

  if (response.status === 401) {
    authStore.logout()
    throw new Error('Session expired. Please sign in again.')
  }

  if (!response.ok) {
    const message = await extractErrorMessage(response)
    throw new Error(message)
  }

  if (!parseJson) {
    return response as unknown as T
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

interface StreamChunkEvent {
  done: boolean
  data?: unknown
}

export interface StreamChatOptions {
  signal?: AbortSignal
  onEvent: (event: StreamChunkEvent) => void
  payload: Record<string, unknown>
}

export async function streamChat(
  sessionId: string,
  { payload, onEvent, signal }: StreamChatOptions,
) {
  const authStore = useAuthStore()
  const headers = new Headers({
    Accept: 'text/event-stream',
  })

  if (authStore.token.value) {
    const type = authStore.tokenType.value || 'Bearer'
    headers.set('Authorization', `${type} ${authStore.token.value}`)
  }

  const body =
    payload instanceof FormData || payload instanceof URLSearchParams
      ? payload
      : JSON.stringify(payload)

  if (!(payload instanceof FormData) && !(payload instanceof URLSearchParams)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}/chat/${sessionId}`, {
    method: 'POST',
    headers,
    body,
    signal,
  })

  if (response.status === 401) {
    authStore.logout()
    throw new Error('Session expired. Please sign in again.')
  }

  if (!response.ok || !response.body) {
    const message = await extractErrorMessage(response)
    throw new Error(message)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finished = false

  while (!finished) {
    const { done, value } = await reader.read()
    if (done) {
      finished = true
      break
    }

    buffer += decoder.decode(value, { stream: true })

    while (true) {
      // Handle both \n\n and \r\n\r\n line endings as well as partial chunks
      let separatorIndex = -1
      let separatorLength = 0

      // First check for \r\n\r\n (CRLF)
      const crlfIndex = buffer.indexOf('\r\n\r\n')
      if (crlfIndex !== -1) {
        separatorIndex = crlfIndex
        separatorLength = 4
      }

      // Then check for \n\n (LF) but only if it's before the CRLF
      const lfIndex = buffer.indexOf('\n\n')
      if (lfIndex !== -1 && (separatorIndex === -1 || lfIndex < separatorIndex)) {
        separatorIndex = lfIndex
        separatorLength = 2
      }

      if (separatorIndex === -1) break

      const rawEvent = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + separatorLength)
      const parsed = parseSseEvent(rawEvent)

      if (!parsed) continue

      if (parsed === '[DONE]') {
        onEvent({ done: true })
        return
      }

      onEvent({ done: false, data: parsed })
    }
  }

  // Process any remaining data in the buffer
  if (buffer.trim()) {
    // The SSE spec allows a final event without a trailing newline
    // Try to parse any remaining data
    const parsed = parseSseEvent(buffer)
    if (parsed === '[DONE]') {
      onEvent({ done: true })
    } else if (parsed) {
      onEvent({ done: false, data: parsed })
      onEvent({ done: true })
    } else {
      // If it's incomplete, wait for more data
      // Or treat as the end of stream
      onEvent({ done: true })
    }
  } else {
    onEvent({ done: true })
  }
}

function parseSseEvent(rawEvent: string): unknown {
  if (!rawEvent.trim()) return undefined

  const lines = rawEvent.split('\n')
  const dataLines = lines
    .map((line) => line.replace(/\r$/, ''))
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.replace(/^data:\s*/, ''))

  if (!dataLines.length) return undefined

  const payload = dataLines.join('\n')
  if (!payload) return undefined

  if (payload === '[DONE]') {
    return '[DONE]'
  }

  try {
    return JSON.parse(payload)
  } catch {
    return payload
  }
}
