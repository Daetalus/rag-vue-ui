<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { computed, provide, ref, watch } from 'vue'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { promptInputKey } from './context'
import type { PromptInputContext } from './context'

const props = withDefaults(defineProps<{
  modelValue?: string
  isLoading?: boolean
  maxHeight?: number | string
  disabled?: boolean
  class?: HTMLAttributes['class']
}>(), {
  isLoading: false,
  maxHeight: 240,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [string]
  submit: []
}>()

const internalValue = ref(props.modelValue ?? '')

watch(
  () => props.modelValue,
  (value) => {
    if (value !== undefined) {
      internalValue.value = value ?? ''
    }
  },
)

const value = computed({
  get: () => props.modelValue ?? internalValue.value,
  set: (next: string) => {
    if (props.modelValue === undefined) {
      internalValue.value = next
    }
    emit('update:modelValue', next)
  },
})

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const context: PromptInputContext = {
  isLoading: computed(() => props.isLoading),
  value,
  setValue: (next: string) => {
    value.value = next
  },
  maxHeight: computed(() => props.maxHeight),
  disabled: computed(() => props.disabled ?? false),
  textareaRef,
  submit: () => emit('submit'),
}

provide(promptInputKey, context)

function focusTextarea() {
  textareaRef.value?.focus()
}
</script>

<template>
  <TooltipProvider :delay-duration="0">
    <div
      :class="cn(
        'border-input bg-background cursor-text rounded-3xl border p-2 shadow-xs transition-colors focus-within:border-primary',
        props.class,
      )"
      @click="focusTextarea"
    >
      <slot />
    </div>
  </TooltipProvider>
</template>
