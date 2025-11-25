<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()

const attrs = useAttrs()

const classes = computed(() =>
  cn(
    'not-prose flex w-full flex-col overflow-clip rounded-xl border border-border bg-card text-card-foreground',
    props.class,
  ),
)
</script>

<template>
  <div
    :class="classes"
    v-bind="attrs"
  >
    <slot />
  </div>
</template>

