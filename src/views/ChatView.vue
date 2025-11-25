<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWindowSize } from '@vueuse/core'
import { Button } from '@/components/ui/button'
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from '@/components/prompt'
import {
  ChatContainerContent,
  ChatContainerRoot,
  ChatContainerScrollAnchor,
} from '@/components/chat'
import { Markdown } from '@/components/prompt-kit'
import { useChatSessions } from '@/stores/chatSessions'
import { Paperclip, Send } from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const chatStore = useChatSessions()

const sessionId = computed(() => route.params.sessionId as string | undefined)
const promptValue = ref('')
const isSubmitting = ref(false)
const isWaitingForResponse = ref(false)
const errorMessage = ref<string | null>(null)
const activeController = ref<AbortController | null>(null)

// 滚动容器引用
const scrollContainerEl = ref<HTMLDivElement | null>(null)

// 滚动控制状态
const isStreamingLocked = ref(false)  // 流式期间锁定滚动
const assistantMinHeight = ref(0)     // 流式期间的最小高度
const reservedAssistantSpace = ref(0) // 记录预留的视口空间
const assistantPlaceholderHeight = ref(0)  // 助手消息补偿占位高度
const placeholderMessageId = ref<string | null>(null)  // 当前补偿占位的消息 ID

// 消息元素映射
const messageElements = new Map<string, HTMLDivElement>()

// 响应式宽度计算（保持原有逻辑）
const { width: windowWidth } = useWindowSize()
const maxObservedWidth = ref(windowWidth.value)
watch(windowWidth, (v) => { 
  if (v > maxObservedWidth.value) maxObservedWidth.value = v 
})

const preferredMidWidth = computed(() => maxObservedWidth.value * 0.6)
const minMidWidth = 320
const midWidth = computed(() => {
  const desired = Math.max(preferredMidWidth.value, minMidWidth)
  const current = windowWidth.value
  return desired > current ? current : desired
})

const sideWidth = computed(() => Math.max((windowWidth.value - midWidth.value) / 2, 0))

const containerPaddingStyle = computed(() => ({ 
  paddingLeft: `${sideWidth.value}px`, 
  paddingRight: `${sideWidth.value}px` 
}))

const midContainerStyle = computed(() => ({
  maxWidth: `${midWidth.value}px`,
  width: '100%',
  margin: '0 auto',
}))

const isSendDisabled = computed(() => isSubmitting.value || !promptValue.value.trim())
const messages = computed(() => sessionId.value ? chatStore.getSessionMessages(sessionId.value) : [])
const hasStreamingMessage = computed(() => messages.value.some(m => m.status === 'streaming'))

// 获取滚动容器
function getScrollContainer(): HTMLElement {
  return scrollContainerEl.value || document.documentElement
}

// 将指定元素滚动到容器顶部
function scrollElementToTop(el: HTMLElement, behavior: ScrollBehavior = 'smooth', offsetTop = 24) {
  const container = getScrollContainer()
  const elementRect = el.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()
  
  // 计算元素相对于容器顶部的偏移
  const relativeTop = elementRect.top - containerRect.top
  const targetScrollTop = container.scrollTop + relativeTop - offsetTop
  
  container.scrollTo({
    top: Math.max(targetScrollTop, 0),
    behavior
  })
}

// 注册/注销消息元素
function setMessageElement(id: string, el: HTMLDivElement | null) {
  if (el) {
    messageElements.set(id, el)
  } else {
    messageElements.delete(id)
  }
}

// 查找消息元素
function findMessageElement(id: string): HTMLDivElement | null {
  return messageElements.get(id) || null
}

function clearAssistantPlaceholder() {
  placeholderMessageId.value = null
  assistantPlaceholderHeight.value = 0
}

function resetAssistantSpace() {
  assistantMinHeight.value = 0
  reservedAssistantSpace.value = 0
  clearAssistantPlaceholder()
}

async function applyAssistantPlaceholder(messageId: string) {
  const reserved = reservedAssistantSpace.value
  if (reserved <= 0) {
    assistantMinHeight.value = 0
    return
  }

  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(resolve))

  const messageEl = findMessageElement(messageId)
  if (!messageEl) {
    assistantMinHeight.value = 0
    clearAssistantPlaceholder()
    return
  }

  const bubbleEl = messageEl.querySelector('.message-bubble') as HTMLElement | null
  if (!bubbleEl) {
    assistantMinHeight.value = 0
    clearAssistantPlaceholder()
    return
  }

  const messageHeight =
    messageEl.offsetHeight || messageEl.getBoundingClientRect().height || 0
  const bubbleHeight = bubbleEl.offsetHeight || bubbleEl.getBoundingClientRect().height || 0
  const footprint = Math.max(messageHeight, bubbleHeight)
  const placeholderHeight = Math.max(reserved - footprint, 0)

  if (placeholderHeight > 0) {
    placeholderMessageId.value = messageId
    assistantPlaceholderHeight.value = placeholderHeight
  } else {
    clearAssistantPlaceholder()
  }

  assistantMinHeight.value = 0
}

// 计算并预留视口空间
function reserveViewportSpace(userMessageEl: HTMLElement) {
  const container = getScrollContainer()
  const containerHeight = container.clientHeight
  const messageHeight = userMessageEl.offsetHeight || userMessageEl.getBoundingClientRect().height
  
  // 预留空间 = 容器高度 - 用户消息高度 - 一些边距
  const reservedHeight = Math.max(containerHeight - messageHeight - 100, 200)
  assistantMinHeight.value = reservedHeight
  reservedAssistantSpace.value = reservedHeight
  
  return reservedHeight
}

// 核心：用户消息发送后的滚动逻辑
async function scrollAfterUserMessage(userMessageId: string, attempts = 5) {
  // 等待用户消息 DOM 挂载
  for (let i = 0; i < attempts; i++) {
    await nextTick()
    const userEl = findMessageElement(userMessageId)
    
    if (userEl) {
      // 1. 计算并设置预留空间
      reserveViewportSpace(userEl)
      
      // 2. 等待一帧确保 DOM 更新完成
      await new Promise(resolve => requestAnimationFrame(resolve))
      
      // 3. 将用户消息滚动到顶部
      scrollElementToTop(userEl, 'smooth', 24)
      
      // 4. 锁定滚动（直到流式结束）
      isStreamingLocked.value = true
      return true
    }
    
    // 如果未找到，等待一小段时间后重试
    await new Promise(resolve => setTimeout(resolve, 50))
  }
  
  return false
}

// 格式化时间戳
function formatTimestamp(date: Date) {
  return new Intl.DateTimeFormat(undefined, { 
    hour: 'numeric', 
    minute: '2-digit' 
  }).format(date)
}

// 加载会话历史
async function ensureHistoryLoaded(id: string) {
  try { 
    await chatStore.loadSessionHistory(id) 
  } catch (e) { 
    errorMessage.value = e instanceof Error ? e.message : 'Unable to load chat history.' 
  }
}

// 会话切换时的处理
watch(sessionId, (id, _, onCleanup) => {
  if (!id) { 
    router.replace({ name: 'landing' })
    return 
  }
  
  // 清理状态
  activeController.value?.abort()
  messageElements.clear()
  resetAssistantSpace()
  isStreamingLocked.value = false
  errorMessage.value = null

  let cancelled = false
  onCleanup(() => { cancelled = true })

  // 加载历史并滚动到底部
  ;(async () => {
    await ensureHistoryLoaded(id)
    if (cancelled) return
    
    await nextTick()
    const container = getScrollContainer()
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'auto'
    })
  })()
}, { immediate: true })

// 监听流式消息状态变化
watch(
  () => {
    const streaming = messages.value.find(m => m.role === 'assistant' && m.status === 'streaming')
    return streaming ? streaming.id : null
  },
  (streamingId, previousStreamingId) => {
    if (streamingId) {
      clearAssistantPlaceholder()
      return
    }

    if (!streamingId && previousStreamingId) {
      const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant')
      if (lastAssistant) {
        void applyAssistantPlaceholder(lastAssistant.id)
      } else {
        resetAssistantSpace()
      }
    }
  }
)

// 发送消息
async function sendPrompt(prompt: string, { restoreOnError = false } = {}) {
  if (!sessionId.value) return

  const controller = new AbortController()
  activeController.value = controller
  isSubmitting.value = true
  isWaitingForResponse.value = true
  errorMessage.value = null

  // 记录发送前的消息 ID
  const beforeMessageIds = new Set(messages.value.map(m => m.id))

  try {
    // 发送消息
    const sendOperation = chatStore.sendMessage(
      sessionId.value, 
      prompt, 
      { signal: controller.signal }
    )
    
    // 等待用户消息添加到列表
    await nextTick()
    
    // 查找新添加的用户消息
    const newUserMessage = messages.value
      .filter(m => !beforeMessageIds.has(m.id))
      .find(m => m.role === 'user')
    
    if (newUserMessage) {
      // 执行滚动逻辑
      await scrollAfterUserMessage(newUserMessage.id)
    }
    
    // 等待 AI 响应完成
    await sendOperation

    const lastAssistant = [...messages.value].reverse().find(
      (m) => m.role === 'assistant' && m.status !== 'streaming'
    )
    if (lastAssistant) {
      await applyAssistantPlaceholder(lastAssistant.id)
    }
    
  } catch (error) {
    if (controller.signal.aborted) {
      if (restoreOnError) {
        errorMessage.value = 'Request cancelled.'
      }
    } else {
      errorMessage.value = error instanceof Error 
        ? error.message 
        : 'Unable to complete the request.'
      if (restoreOnError) {
        promptValue.value = prompt
      }
    }
  } finally {
    isSubmitting.value = false
    activeController.value = null
    isWaitingForResponse.value = false
  }
}

// 处理表单提交
function handleSubmit() {
  if (isSendDisabled.value || !sessionId.value) return
  
  const prompt = promptValue.value.trim()
  if (!prompt) return
  
  // 清空输入框
  promptValue.value = ''
  
  // 解锁滚动（新一轮对话）
  isStreamingLocked.value = false
  resetAssistantSpace()

  // 发送消息
  void sendPrompt(prompt, { restoreOnError: true })
}

const promptTextareaRef = ref<InstanceType<typeof PromptInputTextarea> | null>(null)

onBeforeUnmount(() => {
  activeController.value?.abort()
})
</script>

<template>
  <div class="flex min-h-screen flex-col overflow-hidden" style="height: 100dvh;">
    <!-- 聊天内容滚动区域 -->
    <div
      ref="scrollContainerEl"
      class="min-h-0 flex-1 overflow-y-auto"
      :style="containerPaddingStyle"
    >
      <ChatContainerRoot class="min-h-0">
        <ChatContainerContent
          class="gap-6 px-4 py-8 md:px-6"
          :style="midContainerStyle"
        >
          <!-- 错误提示 -->
          <div
            v-if="errorMessage"
            class="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {{ errorMessage }}
          </div>

          <!-- 消息列表 -->
          <div
            v-for="message in messages"
            :key="message.id"
            :class="[
              'flex flex-col gap-1',
              message.role === 'user' ? 'items-end' : 'items-start'
            ]"
            :ref="(el) => setMessageElement(message.id, el as HTMLDivElement | null)"
          >
            <!-- 消息气泡 -->
            <span
              v-if="message.role === 'assistant' && message.status === 'streaming' && !message.content"
              class="text-xs uppercase tracking-wide text-muted-foreground"
            >
              Assistant · Generating…
            </span>
            <div
              :class="[
                'message-bubble',
                'max-w-2xl rounded-2xl px-4 py-3 text-base leading-relaxed text-foreground',
                message.role === 'assistant' ? 'bg-background shadow-none ring-0' : 'bg-muted shadow-sm',
                message.status === 'error' ? 'border border-destructive/40 bg-destructive/15 text-destructive' : '',
              ]"
              :style="{
                minHeight: (
                  message.role === 'assistant' && 
                  message.status === 'streaming' && 
                  assistantMinHeight > 0
                ) ? `${assistantMinHeight}px` : undefined
              }"
              >
              <Markdown
                :content="message.content"
                class="flex flex-col gap-3 break-words text-base leading-relaxed [&>*]:m-0 [&>ul]:list-disc [&>ol]:list-decimal [&_li]:mb-1 [&_li]:marker:text-muted-foreground [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2"
              />
            </div>

            <!-- 消息元信息 -->
            <span
              v-if="message.role !== 'assistant' || message.status !== 'streaming'"
              class="text-xs uppercase tracking-wide text-muted-foreground"
            >
              {{ message.role === 'user' ? 'You' : 'Assistant' }} ·
              <template v-if="message.status === 'error'">Failed</template>
              <template v-else-if="message.status === 'streaming'">Generating…</template>
              <template v-else>{{ formatTimestamp(message.timestamp) }}</template>
            </span>

            <div
              v-if="message.id === placeholderMessageId && assistantPlaceholderHeight > 0"
              :style="{
                height: `${assistantPlaceholderHeight}px`,
                width: '100%',
              }"
              aria-hidden="true"
            />
          </div>

          <ChatContainerScrollAnchor />
        </ChatContainerContent>
      </ChatContainerRoot>
    </div>

    <!-- 输入区域 -->
    <div
      class="flex-none bg-background/95 px-4 py-6 backdrop-blur md:px-6"
      :style="containerPaddingStyle"
    >
      <div class="w-full px-4 md:px-6" :style="midContainerStyle">
        <PromptInput
          v-model="promptValue"
          :is-loading="isSubmitting"
          :disabled="isSubmitting"
          :max-height="144"
          @submit="handleSubmit"
        >
          <div class="flex flex-col gap-4">
            <PromptInputTextarea
              ref="promptTextareaRef"
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
                    :disabled="isSubmitting"
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
  </div>
</template>

<style scoped>
/* 确保平滑滚动 */
:deep(*) {
  scroll-behavior: smooth;
}
</style>
