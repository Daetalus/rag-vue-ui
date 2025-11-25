<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { nextTick, onUnmounted, provide, ref, useAttrs, watch } from 'vue'
import { useEventListener, useResizeObserver } from '@vueuse/core'
import { cn } from '@/lib/utils'
import { chatContainerKey, type ChatScrollOptions } from './context'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()

const attrs = useAttrs()

const containerRef = ref<HTMLDivElement | null>(null)
const contentRef = ref<HTMLDivElement | null>(null)
const isNearBottom = ref(true)
const reservedSpace = ref(0)

function applyReservePadding(value: number) {
  const content = contentRef.value
  if (!content) return
  content.style.paddingBottom = value > 0 ? `${value}px` : ''
}

function scrollToBottom(options: ChatScrollOptions = {}) {
  const el = containerRef.value
  if (!el) return

  const behavior = options.behavior ?? 'smooth'
  const reserve =
    typeof options.reserve === 'number'
      ? Math.max(options.reserve, 0)
      : Math.max(reservedSpace.value, 0)

  if (typeof options.reserve === 'number') {
    reservedSpace.value = reserve
  }

  applyReservePadding(reserve)

  const maxScrollTop = Math.max(el.scrollHeight - el.clientHeight, 0)
  const targetTop =
    typeof options.top === 'number'
      ? Math.max(Math.min(options.top, maxScrollTop), 0)
      : Math.max(maxScrollTop - reserve, 0)

  el.scrollTo({
    top: targetTop,
    behavior,
  })
}

function updateNearBottom() {
  const el = containerRef.value
  if (!el) return

  const threshold = 80
  const distance =
    el.scrollHeight - el.scrollTop - el.clientHeight - Math.max(reservedSpace.value, 0)
  isNearBottom.value = distance <= threshold

  if (!isNearBottom.value && reservedSpace.value !== 0) {
    reservedSpace.value = 0
    applyReservePadding(0)
  }
}

const { stop: stopResizeObserver } = useResizeObserver(contentRef, () => {
  if (isNearBottom.value) {
    scrollToBottom()
  }
})

let removeScrollListener: (() => void) | undefined

watch(
  () => containerRef.value,
  (el) => {
    removeScrollListener?.()
    if (el) {
      removeScrollListener = useEventListener(el, 'scroll', updateNearBottom, { passive: true })
      nextTick(() => {
        updateNearBottom()
        scrollToBottom({ behavior: 'auto' })
      })
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopResizeObserver()
  removeScrollListener?.()
})

provide(chatContainerKey, {
  containerRef,
  contentRef,
  isNearBottom,
  scrollToBottom,
})

defineExpose({
  containerRef,
  scrollToBottom,
})
</script>

<template>
  <div
    ref="containerRef"
    :class="cn('flex flex-1 overflow-y-auto', props.class)"
    role="log"
    v-bind="attrs"
  >
    <slot />
  </div>
</template>
