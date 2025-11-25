<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <div
    :class="cn('h-px w-full shrink-0 scroll-mt-4', props.class)"
    aria-hidden="true"
  />
</template>
