<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { nextTick, useAttrs, watch, withDefaults } from 'vue'
import { cn } from '@/lib/utils'
import { usePromptInputContext } from './context'

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(defineProps<{
  class?: HTMLAttributes['class']
  disableAutosize?: boolean
}>(), {
  disableAutosize: false,
})

const emit = defineEmits<{
  keydown: [KeyboardEvent]
}>()

const attrs = useAttrs()
const prompt = usePromptInputContext()

const assignTextareaRef = (el: HTMLTextAreaElement | null) => {
  prompt.textareaRef.value = el
}

async function adjustTextareaHeight() {
  if (props.disableAutosize) return
  await nextTick()

  const textarea = prompt.textareaRef.value
  if (!textarea) return

  if (textarea.scrollTop === 0) {
    textarea.style.height = 'auto'
  }

  if (typeof prompt.maxHeight.value === 'number') {
    textarea.style.height = `${Math.min(textarea.scrollHeight, prompt.maxHeight.value)}px`
  } else {
    textarea.style.height = `min(${textarea.scrollHeight}px, ${prompt.maxHeight.value})`
  }
}

watch(
  () => [prompt.value.value, prompt.maxHeight.value, props.disableAutosize],
  () => {
    void adjustTextareaHeight()
  },
  { immediate: true },
)

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    prompt.submit()
  }
  emit('keydown', event)
}

function updateValue(next: string) {
  prompt.setValue(next)
}

defineExpose({
  focus() {
    nextTick(() => {
      prompt.textareaRef.value?.focus()
    })
  },
})
</script>

<template>
  <textarea
    :ref="assignTextareaRef"
    :value="prompt.value.value"
    :disabled="prompt.disabled.value"
    rows="1"
    :class="cn(
      'text-primary min-h-[44px] w-full resize-none border-none bg-transparent px-3 py-2 shadow-none outline-none focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
      props.class,
    )"
    @input="updateValue(($event.target as HTMLTextAreaElement).value)"
    @keydown="handleKeydown"
    v-bind="attrs"
  />
</template>
