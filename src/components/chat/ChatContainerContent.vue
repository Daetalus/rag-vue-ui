<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'
import { useChatContainer } from './context'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()

const attrs = useAttrs()
const { contentRef } = useChatContainer()

const setContentRef = (el: HTMLDivElement | null) => {
  contentRef.value = el
}

const classes = computed(() =>
  cn('flex w-full flex-col', props.class),
)
</script>

<template>
  <div
    :ref="setContentRef"
    :class="classes"
    v-bind="attrs"
  >
    <slot />
  </div>
</template>
