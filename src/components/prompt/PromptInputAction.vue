<script setup lang="ts">
import type { HTMLAttributes, VNodeChild } from 'vue'
import { computed, useAttrs } from 'vue'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { usePromptInputContext } from './context'

const props = withDefaults(defineProps<{
  tooltip: VNodeChild
  contentClass?: HTMLAttributes['class']
  side?: 'top' | 'bottom' | 'left' | 'right'
}>(), {
  side: 'top',
})

const attrs = useAttrs()
const prompt = usePromptInputContext()

const tooltipContentClass = computed(() =>
  cn('', props.contentClass),
)
</script>

<template>
  <Tooltip v-bind="attrs">
    <TooltipTrigger
      as-child
      :disabled="prompt.disabled.value"
      @click.stop
    >
      <span class="inline-flex">
        <slot />
      </span>
    </TooltipTrigger>
    <TooltipContent
      :side="props.side"
      :class="tooltipContentClass"
    >
      <slot name="tooltip">
        {{ props.tooltip }}
      </slot>
    </TooltipContent>
  </Tooltip>
</template>
