import type { ComputedRef, InjectionKey, Ref } from 'vue'
import { inject } from 'vue'

export interface PromptInputContext {
  isLoading: ComputedRef<boolean>
  value: Ref<string>
  setValue: (value: string) => void
  maxHeight: ComputedRef<number | string>
  disabled: ComputedRef<boolean>
  textareaRef: Ref<HTMLTextAreaElement | null>
  submit: () => void
}

export const promptInputKey: InjectionKey<PromptInputContext> = Symbol('PromptInputContext')

export function usePromptInputContext() {
  const context = inject(promptInputKey)
  if (!context) {
    throw new Error('usePromptInputContext must be used within PromptInput')
  }
  return context
}
