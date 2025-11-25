<script setup lang="ts">
import { computed, ref } from 'vue'
import { NavigationFailureType, isNavigationFailure, useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from '@/components/prompt'
import { useChatSessions } from '@/stores/chatSessions'
import { Paperclip, Send } from 'lucide-vue-next'

const router = useRouter()
const chatStore = useChatSessions()

const promptValue = ref('')
const isNavigating = ref(false)
const errorMessage = ref<string | null>(null)

const isSendDisabled = computed(
  () => isNavigating.value || !promptValue.value.trim(),
)

async function goToChat() {
  const prompt = promptValue.value.trim()
  if (!prompt) return

  isNavigating.value = true
  errorMessage.value = null

  try {
    const title = prompt.length > 48 ? `${prompt.slice(0, 48)}…` : prompt
    const session = await chatStore.createSession(title)

    const sendPromise = chatStore
      .sendMessage(session.id, prompt)
      .catch((error) => {
        console.error('Failed to send initial prompt:', error)
        errorMessage.value =
          error instanceof Error
            ? error.message
            : 'Unable to send the initial prompt.'
      })

    const failure = await router
      .push({
        name: 'chat',
        params: {
          sessionId: session.id,
        },
      })
      .catch((error) => error)

    if (
      failure &&
      (!isNavigationFailure(failure) ||
        failure.type !== NavigationFailureType.duplicated)
    ) {
      errorMessage.value =
        failure instanceof Error
          ? failure.message
          : 'Unable to navigate to the chat session.'
      throw failure
    }

    promptValue.value = ''

    void sendPromise
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'Unable to create a new chat session.'
  } finally {
    isNavigating.value = false
  }
}

function handleSubmit() {
  if (isSendDisabled.value) return
  void goToChat()
}

</script>

<template>
  <div class="flex flex-1 items-center justify-center px-6 py-12">
    <div class="w-full max-w-3xl space-y-8">
      <div class="space-y-2 text-center">
        <h1 class="text-3xl font-semibold text-foreground">
          Nexedi RAG
        </h1>
        <p class="text-muted-foreground">
          Explore your knowledge base with conversational retrieval.
        </p>
        <p
          v-if="errorMessage"
          class="mx-auto max-w-md rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {{ errorMessage }}
        </p>
      </div>

      <PromptInput
        v-model="promptValue"
        :disabled="isNavigating"
        :max-height="144"
        @submit="handleSubmit"
      >
        <div class="flex flex-col gap-4">
          <PromptInputTextarea
            placeholder="Ask Nexedi RAG anything..."
            aria-label="Prompt"
          />
          <div class="flex items-center justify-between">
            <PromptInputActions class="gap-3">
              <PromptInputAction tooltip="Attach files">
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-11 w-11 rounded-full"
                  :disabled="isNavigating"
                >
                  <Paperclip class="size-4" />
                  <span class="sr-only">Attach files</span>
                </Button>
              </PromptInputAction>
            </PromptInputActions>
            <Button
              size="icon"
              class="h-11 w-11 rounded-full"
              :disabled="isSendDisabled"
              @click="handleSubmit"
            >
              <Send class="size-4" />
              <span class="sr-only">Send prompt</span>
            </Button>
          </div>
        </div>
      </PromptInput>
    </div>
  </div>
</template>

<style scoped>
</style>
