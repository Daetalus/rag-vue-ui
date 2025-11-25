<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL } from '@/lib/apiClient'

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const manualToken = ref('')
const localError = ref<string | null>(null)
const isSubmitting = ref(false)

const authStore = useAuthStore()

const isBusy = computed(() => isSubmitting.value)
const errorMessage = computed(() => localError.value)

async function parseError(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    try {
      const payload = await response.json()
      if ((payload as Record<string, unknown>)?.detail) {
        const detail = (payload as Record<string, unknown>).detail
        if (typeof detail === 'string') return detail
        if (Array.isArray(detail) && detail.length) {
          const firstEntry = detail[0]
          if (typeof firstEntry === 'string') return firstEntry
          if (firstEntry && typeof firstEntry === 'object') {
            const record = firstEntry as Record<string, unknown>
            const message = record['msg']
            if (typeof message === 'string') {
              return message
            }
          }
        }
      }
      if ((payload as Record<string, unknown>)?.message && typeof (payload as Record<string, unknown>).message === 'string') {
        return (payload as Record<string, string>).message
      }
      if (typeof payload === 'string') return payload
      return JSON.stringify(payload)
    } catch {
      // fall back to text parsing
    }
  }

  try {
    const text = await response.text()
    if (text) return text
  } catch {
    // ignore
  }

  return 'Request failed.'
}

async function submitLogin(formUsername: string, formPassword: string) {
  const response = await fetch(`${API_BASE_URL}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: formUsername,
      password: formPassword,
    }),
  });

  if (!response.ok) {
    const message = await parseError(response);
    throw new Error(message);
  }

  const data = await response.json();
  const { access_token: accessToken, token_type: tokenType } = data ?? {};
  if (!accessToken) throw new Error('Token not returned by server.');
  authStore.persistToken(accessToken, tokenType ?? 'Bearer');
}

async function submitRegistration(formUsername: string, formPassword: string) {
  const response = await fetch(`${API_BASE_URL}/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: formUsername,
      password: formPassword,
    }),
  })

  if (!response.ok) {
    const message = await parseError(response)
    throw new Error(message)
  }

  await submitLogin(formUsername, formPassword)
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  localError.value = null
}

async function handleSubmit() {
  localError.value = null

  const trimmedUsername = username.value.trim()

  if (!trimmedUsername || !password.value) {
    localError.value = 'Username and password are required.'
    return
  }

  if (mode.value === 'register' && password.value !== confirmPassword.value) {
    localError.value = 'Passwords do not match.'
    return
  }

  try {
    isSubmitting.value = true
    if (mode.value === 'login') {
      await submitLogin(trimmedUsername, password.value)
    } else {
      await submitRegistration(trimmedUsername, password.value)
    }

    username.value = ''
    password.value = ''
    confirmPassword.value = ''
  } catch (error) {
    localError.value =
      error instanceof Error ? error.message : 'Unable to complete the request.'
  } finally {
    isSubmitting.value = false
  }
}

function handleUseToken() {
  localError.value = null
  const token = manualToken.value.trim()
  if (!token) {
    localError.value = 'Enter a token before applying it.'
    return
  }

  authStore.persistToken(token)
  manualToken.value = ''
}
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-background via-background to-muted px-6 py-12">
    <div class="w-full max-w-md rounded-3xl border border-border/60 bg-background/95 p-8 shadow-2xl backdrop-blur">
      <div class="space-y-3 text-center">
        <h1 class="text-2xl font-semibold tracking-tight text-foreground">
          Nexedi RAG
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ mode === 'login' ? 'Sign in to continue your conversations.' : 'Create an account to start chatting.' }}
        </p>
      </div>

      <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
        <div class="space-y-2">
          <label class="text-sm font-medium text-foreground" for="username">
            Username
          </label>
          <Input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            :disabled="isBusy"
          />
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-foreground" for="password">
            Password
          </label>
          <Input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            :disabled="isBusy"
          />
        </div>

        <div
          v-if="mode === 'register'"
          class="space-y-2"
        >
          <label class="text-sm font-medium text-foreground" for="confirm-password">
            Confirm password
          </label>
          <Input
            id="confirm-password"
            v-model="confirmPassword"
            type="password"
            autocomplete="new-password"
            :disabled="isBusy"
          />
        </div>

        <p
          v-if="errorMessage"
          class="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {{ errorMessage }}
        </p>

        <Button
          type="submit"
          class="w-full"
          :disabled="isBusy"
        >
          {{ mode === 'login' ? (isBusy ? 'Signing in…' : 'Sign in') : (isBusy ? 'Creating account…' : 'Create account') }}
        </Button>
      </form>

      <div class="mt-6 flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {{ mode === 'login' ? "Don't have an account?" : 'Already have an account?' }}
        </span>
        <button
          type="button"
          class="font-medium text-primary underline-offset-4 hover:underline"
          @click="toggleMode"
        >
          {{ mode === 'login' ? 'Register' : 'Sign in' }}
        </button>
      </div>

      <div class="mt-8 space-y-3 rounded-2xl border border-dashed border-muted-foreground/40 p-4">
        <h2 class="text-sm font-semibold text-foreground">
          Have an existing token?
        </h2>
        <p class="text-xs leading-relaxed text-muted-foreground">
          Paste a valid bearer token from the API and jump straight into your sessions.
        </p>
        <div class="flex flex-col gap-2">
          <Input
            v-model="manualToken"
            placeholder="Paste JWT token…"
            :disabled="isBusy"
          />
          <Button
            variant="secondary"
            :disabled="isBusy"
            @click="handleUseToken"
          >
            Use token
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
