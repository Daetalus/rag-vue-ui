import type { InjectionKey, Ref } from 'vue'
import { inject } from 'vue'

export type ChatScrollOptions = ScrollToOptions & {
  reserve?: number
  top?: number
}

export interface ChatContainerContext {
  containerRef: Ref<HTMLDivElement | null>
  contentRef: Ref<HTMLDivElement | null>
  isNearBottom: Ref<boolean>
  scrollToBottom: (options?: ChatScrollOptions) => void
}

export const chatContainerKey: InjectionKey<ChatContainerContext> = Symbol('ChatContainerContext')

export function useChatContainer() {
  const context = inject(chatContainerKey)
  if (!context) {
    throw new Error('Chat container components must be used within ChatContainerRoot')
  }
  return context
}
