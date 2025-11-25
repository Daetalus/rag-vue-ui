<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { codeToHtml } from 'shiki'
import { cn } from '@/lib/utils'

const props = defineProps<{
  code: string | string[]
  language?: string
  theme?: string
  class?: string
}>()

const highlightedHtml = ref<string | null>(null)

const normalizedCode = computed(() => {
  if (Array.isArray(props.code)) {
    return props.code.join('')
  }
  return props.code ?? ''
})

const language = computed(() => props.language ?? 'tsx')
const theme = computed(() => props.theme ?? 'github-light')

const containerClass = computed(() =>
  cn('w-full overflow-x-auto text-[13px] [&>pre]:px-4 [&>pre]:py-4', props.class),
)

let isMounted = true

async function highlight() {
  const content = normalizedCode.value

  if (!content) {
    highlightedHtml.value = '<pre><code></code></pre>'
    return
  }

  const html = await codeToHtml(content, {
    lang: language.value,
    theme: theme.value,
  })

  if (isMounted) {
    highlightedHtml.value = html
  }
}

watch([normalizedCode, language, theme], () => {
  void highlight()
}, { immediate: true })

onBeforeUnmount(() => {
  isMounted = false
})
</script>

<template>
  <div
    v-if="highlightedHtml"
    :class="containerClass"
    v-html="highlightedHtml"
  />
  <div
    v-else
    :class="containerClass"
  >
    <pre>
      <code>{{ normalizedCode }}</code>
    </pre>
  </div>
</template>
