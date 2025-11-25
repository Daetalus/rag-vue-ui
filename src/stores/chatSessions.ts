import { computed, reactive, ref } from 'vue'
import { apiFetch, streamChat } from '@/lib/apiClient'

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  timestamp: Date
  status?: 'streaming' | 'completed' | 'error'
}

export interface ChatSession {
  id: string
  title: string
  lastActivity: Date
}

interface ApiSession {
  id: string
  title: string
  last_activity: string
}

interface ApiMessage {
  id: string
  sender: string
  text: string
  timestamp: string
}

interface ApiSessionWithMessages extends ApiSession {
  messages: ApiMessage[]
}

const sessions = ref<ChatSession[]>([])
const sessionsLoaded = ref(false)
const isLoadingSessions = ref(false)
const sessionsError = ref<string | null>(null)

const sessionMessages = reactive<Record<string, ChatMessage[]>>({})
const loadingSessionMessages = ref(new Set<string>())

function toDate(value: string | Date | number | undefined): Date {
  if (!value) return new Date()
  if (value instanceof Date) return value
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return new Date()
  }
  return parsed
}

function mapSession(payload: ApiSession): ChatSession {
  return {
    id: payload.id,
    title: payload.title || 'Untitled session',
    lastActivity: toDate(payload.last_activity),
  }
}

function mapMessage(payload: ApiMessage): ChatMessage {
  const sender = payload.sender ? payload.sender.toLowerCase() : ''
  const role: ChatRole =
    sender === 'bot' || sender === 'assistant' ? 'assistant' : 'user'
  return {
    id: payload.id,
    role,
    content: payload.text ?? '',
    timestamp: toDate(payload.timestamp),
    status: 'completed',
  }
}

function ensureMessages(sessionId: string) {
  if (!sessionMessages[sessionId]) {
    sessionMessages[sessionId] = []
  }
  return sessionMessages[sessionId]
}

function sortSessions() {
  sessions.value = [...sessions.value].sort(
    (a, b) => b.lastActivity.getTime() - a.lastActivity.getTime(),
  )
}

function upsertSession(next: ChatSession) {
  const existingIndex = sessions.value.findIndex(
    (session) => session.id === next.id,
  )

  if (existingIndex === -1) {
    sessions.value = [next, ...sessions.value]
  } else {
    sessions.value.splice(existingIndex, 1, next)
    sessions.value = [...sessions.value]
  }

  sortSessions()
}

function setSessionMessages(sessionId: string, messages: ChatMessage[]) {
  sessionMessages[sessionId] = messages
}

function markSessionLoading(sessionId: string, loading: boolean) {
  const current = new Set(loadingSessionMessages.value)
  if (loading) {
    current.add(sessionId)
  } else {
    current.delete(sessionId)
  }
  loadingSessionMessages.value = current
}

async function fetchSessions() {
  if (isLoadingSessions.value) return

  isLoadingSessions.value = true
  sessionsError.value = null

  try {
    const payload = await apiFetch<ApiSession[]>('/sessions')
    const nextSessions = payload.map(mapSession)
    sessions.value = nextSessions.sort(
      (a, b) => b.lastActivity.getTime() - a.lastActivity.getTime(),
    )
    sessionsLoaded.value = true
  } catch (error) {
    sessionsError.value =
      error instanceof Error ? error.message : 'Unable to load sessions.'
    throw error
  } finally {
    isLoadingSessions.value = false
  }
}

async function createSession(initialTitle?: string) {
  const title = initialTitle?.trim()
  const payload = await apiFetch<ApiSession>('/sessions', {
    method: 'POST',
    body: JSON.stringify(
      title
        ? {
            title,
          }
        : {},
    ),
  })

  const session = mapSession(payload)
  upsertSession(session)
  ensureMessages(session.id)
  return session
}

async function renameSession(sessionId: string, title: string) {
  const trimmed = title.trim()
  if (!trimmed) return

  await apiFetch(`/sessions/${sessionId}`, {
    method: 'PUT',
    body: JSON.stringify({ title: trimmed }),
  })

  const existing = sessions.value.find((session) => session.id === sessionId)
  if (existing) {
    existing.title = trimmed
    sessions.value = [...sessions.value]
  }
}

async function deleteSession(sessionId: string) {
  await apiFetch(`/sessions/${sessionId}`, {
    method: 'DELETE',
  })

  sessions.value = sessions.value.filter((session) => session.id !== sessionId)
  delete sessionMessages[sessionId]
}

async function loadSessionHistory(
  sessionId: string,
  { force = false }: { force?: boolean } = {},
) {
  const hasMessages = sessionMessages[sessionId]?.length
  if (hasMessages && !force) {
    return sessionMessages[sessionId]
  }

  markSessionLoading(sessionId, true)

  try {
    const payload = await apiFetch<ApiSessionWithMessages>(
      `/sessions/${sessionId}`,
    )

    const session = mapSession(payload)
    
    // Simply update the existing session without triggering re-sorting that 
    // would move it to the top based on current access time
    const existingIndex = sessions.value.findIndex(s => s.id === sessionId);
    if (existingIndex !== -1) {
      sessions.value.splice(existingIndex, 1, session);
      // Keep the original order - don't resort on view
    } else {
      sessions.value = [session, ...sessions.value];
      sortSessions(); // Only sort if it's a new session
    }

    const messages = payload.messages.map(mapMessage)
    messages.sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime(),
    )
    setSessionMessages(session.id, messages)
    return messages
  } finally {
    markSessionLoading(sessionId, false)
  }
}

function getSessionMessages(sessionId: string) {
  return sessionMessages[sessionId] ?? []
}

function getSessionById(sessionId: string) {
  return sessions.value.find((session) => session.id === sessionId)
}

function updateSessionActivity(sessionId: string, timestamp = new Date()) {
  const existing = sessions.value.find((session) => session.id === sessionId)
  if (existing) {
    existing.lastActivity = timestamp
    sessions.value = [...sessions.value]
    sortSessions()
  }
}

async function sendMessage(
  sessionId: string,
  content: string,
  {
    signal,
  }: {
    signal?: AbortSignal
  } = {},
) {
  const trimmed = content.trim()
  if (!trimmed) return

  const messages = ensureMessages(sessionId)
  const now = new Date()

  const userMessage: ChatMessage = {
    id: generateId('user'),
    role: 'user',
    content: trimmed,
    timestamp: now,
    status: 'completed',
  }

  messages.push(userMessage)
  updateSessionActivity(sessionId, now)

  let assistantMessage: ChatMessage = {
    id: generateId('assistant'),
    role: 'assistant',
    content: '',
    timestamp: now,
    status: 'streaming',
  }
  messages.push(assistantMessage)

  const commitAssistantUpdate = (
    updater: (message: ChatMessage) => void,
  ) => {
    const index = messages.indexOf(assistantMessage)
    if (index === -1) return
    updater(assistantMessage)
    assistantMessage = { ...assistantMessage }
    messages.splice(index, 1, assistantMessage)
  }

  try {
    await streamChat(sessionId, {
      payload: { sender: 'user', text: trimmed },
      signal,
      onEvent: ({ done, data }) => {
        if (done) {
          commitAssistantUpdate((draft) => {
            if (draft.status !== 'error') {
              draft.status = 'completed'
            }
            draft.timestamp = new Date()
          })
          updateSessionActivity(sessionId, assistantMessage.timestamp)
          return
        }

        if (data && typeof data === 'object') {
          const event = data as { type?: string; data?: unknown }
          if (typeof event.type === 'string') {
            if (event.type === 'token') {
              const chunk = event.data
              commitAssistantUpdate((draft) => {
                if (typeof chunk === 'string') {
                  draft.content += chunk
                } else if (chunk !== null && chunk !== undefined) {
                  draft.content += String(chunk)
                }
              })
              return
            }

            if (event.type === 'final') {
              const payload = event.data
              if (
                payload &&
                typeof payload === 'object' &&
                'answer' in (payload as { answer?: unknown })
              ) {
                const answer = (payload as { answer?: unknown }).answer
                if (
                  typeof answer === 'string' &&
                  assistantMessage.content.length === 0
                ) {
                  commitAssistantUpdate((draft) => {
                    draft.content = answer
                  })
                }
              }
              return
            }

            if (event.type === 'error') {
              commitAssistantUpdate((draft) => {
                draft.status = 'error'
                if (typeof event.data === 'string') {
                  draft.content = event.data
                } else if (!draft.content) {
                  draft.content = 'An error occurred.'
                }
              })
              return
            }
          }
        }

        const text = extractChunkText(data)
        if (text) {
          commitAssistantUpdate((draft) => {
            draft.content += text
          })
        }
      },
    })
  } catch (error) {
    commitAssistantUpdate((draft) => {
      draft.status = 'error'
      if (!draft.content) {
        draft.content =
          error instanceof Error
            ? error.message
            : 'Unable to complete the request.'
      }
    })
    throw error
  } finally {
    await loadSessionHistory(sessionId, { force: true }).catch(() => {
      // Non-blocking: keep optimistic messages if refresh fails.
    })
  }

  return { userMessage, assistantMessage }
}

function extractChunkText(data: unknown) {
  if (!data) return ''
  if (typeof data === 'string') {
    return data
  }
  if (typeof data === 'object') {
    if ('delta' in data && typeof (data as { delta: unknown }).delta === 'string') {
      return (data as { delta: string }).delta
    }
    if ('content' in data && typeof (data as { content: unknown }).content === 'string') {
      return (data as { content: string }).content
    }
    if ('text' in data && typeof (data as { text: unknown }).text === 'string') {
      return (data as { text: string }).text
    }
  }
  return ''
}

function generateId(prefix: string) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function resetSessions() {
  sessions.value = []
  sessionsLoaded.value = false
  sessionsError.value = null
  loadingSessionMessages.value = new Set()
  Object.keys(sessionMessages).forEach((key) => {
    delete sessionMessages[key]
  })
}

const orderedSessions = computed(() => sessions.value)

export function useChatSessions() {
  return {
    sessions,
    orderedSessions,
    sessionsLoaded,
    isLoadingSessions,
    sessionsError,
    loadingSessionMessages,
    fetchSessions,
    createSession,
    renameSession,
    deleteSession,
    loadSessionHistory,
    getSessionMessages,
    getSessionById,
    updateSessionActivity,
    sendMessage,
    resetSessions,
  }
}
