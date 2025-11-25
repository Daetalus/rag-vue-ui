<script lang="ts">
import type { Tokens } from 'marked'
import { marked } from 'marked'
import { computed, defineComponent, getCurrentInstance, h } from 'vue'
import { cn } from '@/lib/utils'
import CodeBlock from './CodeBlock.vue'
import CodeBlockCode from './CodeBlockCode.vue'

type MarkdownCodeRenderContext = {
  inline: boolean
  text: string
  className?: string
  language?: string
}

type MarkdownRenderer = (context: MarkdownCodeRenderContext) => ReturnType<typeof h>

type MarkdownComponents = {
  code?: MarkdownRenderer
}

const DEFAULT_INLINE_CODE_CLASS =
  'markdown-inline-code bg-primary-foreground rounded-sm px-1 font-mono text-sm'

const headingClassMap: Record<number, string> = {
  1: 'text-2xl font-semibold',
  2: 'text-xl font-semibold',
  3: 'text-lg font-semibold',
  4: 'text-base font-semibold',
  5: 'text-sm font-semibold',
  6: 'text-xs font-semibold uppercase tracking-wide',
}

const defaultComponents: Required<MarkdownComponents> = {
  code: ({ inline, text, className, language }) => {
    if (inline) {
      return h(
        'span',
        {
          class: cn(DEFAULT_INLINE_CODE_CLASS, className),
        },
        text,
      )
    }

    return h(
      CodeBlock,
      { class: className },
      {
        default: () =>
          h(CodeBlockCode, {
            code: text,
            language,
          }),
      },
    )
  },
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttribute(value?: string | null) {
  if (!value) return ''
  return escapeHtml(value)
}

const renderer = new marked.Renderer()
renderer.codespan = (code) =>
  `<span class="${DEFAULT_INLINE_CODE_CLASS}">${escapeHtml(code)}</span>`
renderer.link = (href, title, text) => {
  const safeHref = escapeAttribute(href)
  const safeTitle = escapeAttribute(title)
  const titleAttr = safeTitle ? ` title="${safeTitle}"` : ''
  if (safeHref.startsWith('#')) {
    return `<a href="${safeHref}"${titleAttr}>${text}</a>`
  }
  return `<a href="${safeHref}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`
}

marked.setOptions({
  gfm: true,
  breaks: true,
})

const parserOptions = { renderer }

function renderInlineTokens(
  tokens: Tokens.Generic[] | undefined,
  components: Required<MarkdownComponents>,
): Array<ReturnType<typeof h> | string> {
  if (!tokens) return []

  const nodes: Array<ReturnType<typeof h> | string> = []

  for (const token of tokens) {
    switch (token.type) {
      case 'text': {
        if (token.tokens) {
          nodes.push(...renderInlineTokens(token.tokens, components))
        } else {
          nodes.push(token.text)
        }
        break
      }
      case 'codespan': {
        nodes.push(
          components.code({
            inline: true,
            className: token.lang ? `language-${token.lang}` : undefined,
            language: token.lang ?? 'plaintext',
            text: token.text,
          }),
        )
        break
      }
      case 'strong': {
        nodes.push(h('strong', renderInlineTokens(token.tokens, components)))
        break
      }
      case 'em': {
        nodes.push(h('em', renderInlineTokens(token.tokens, components)))
        break
      }
      case 'del': {
        nodes.push(h('del', renderInlineTokens(token.tokens, components)))
        break
      }
      case 'link': {
        const children = renderInlineTokens(token.tokens, components)
        const href = token.href ? escapeAttribute(token.href) : ''
        const title = token.title ? escapeAttribute(token.title) : undefined
        const attrs: Record<string, string> = {}
        if (href) {
          attrs.href = href
          if (!href.startsWith('#')) {
            attrs.target = '_blank'
            attrs.rel = 'noopener noreferrer'
          }
        }
        if (title) {
          attrs.title = title
        }
        nodes.push(h('a', attrs, children.length > 0 ? children : token.text))
        break
      }
      case 'image': {
        const src = token.href ? escapeAttribute(token.href) : ''
        const title = token.title ? escapeAttribute(token.title) : undefined
        nodes.push(
          h('img', {
            src,
            alt: token.text,
            title,
          }),
        )
        break
      }
      case 'br': {
        nodes.push(h('br'))
        break
      }
      case 'html': {
        nodes.push(h('span', { innerHTML: token.text }))
        break
      }
      default: {
        nodes.push(token.raw ?? '')
      }
    }
  }

  return nodes
}

function renderListItems(
  items: Tokens.ListItem[],
  components: Required<MarkdownComponents>,
) {
  return items.map((item, index) =>
    h(
      'li',
      { key: index },
      item.tokens && item.tokens.length > 0
        ? renderTokens(item.tokens, components)
        : renderInlineTokens(marked.Lexer.lexInline(item.text ?? ''), components),
    ),
  )
}

function renderTokens(
  tokens: Tokens.Generic[],
  components: Required<MarkdownComponents>,
): ReturnType<typeof h>[] {
  const nodes: ReturnType<typeof h>[] = []

  tokens.forEach((token, index) => {
    if (token.type === 'space') {
      return
    }

    if (token.type === 'code') {
      const language = token.lang ?? 'plaintext'
      const className = token.lang ? `language-${language}` : undefined
      const node = components.code({
        inline: false,
        className,
        language,
        text: token.text,
      })
      if (node && node.key == null) {
        node.key = `code-${index}`
      }
      nodes.push(node)
      return
    }

    if (token.type === 'blockquote') {
      nodes.push(
        h(
          'blockquote',
          { key: `blockquote-${index}` },
          renderTokens(token.tokens ?? [], components),
        ),
      )
      return
    }

    if (token.type === 'list') {
      const tag = token.ordered ? 'ol' : 'ul'
      const attrs: Record<string, unknown> = {}
      if (token.start && token.start !== 1) {
        attrs.start = token.start
      }
      nodes.push(
        h(tag, { key: `list-${index}`, ...attrs }, renderListItems(token.items, components)),
      )
      return
    }

    if (token.type === 'heading') {
      const tag = `h${token.depth}`
      nodes.push(
        h(
          tag,
          {
            key: `heading-${index}`,
            class: headingClassMap[token.depth] ?? 'font-semibold',
          },
          renderInlineTokens(token.tokens, components),
        ),
      )
      return
    }

    if (token.type === 'hr') {
      nodes.push(h('hr', { key: `hr-${index}` }))
      return
    }

    if (token.type === 'table') {
      const headerCells = token.header.map((cell, cellIndex) =>
        h(
          'th',
          { key: `header-${cellIndex}`, align: token.align?.[cellIndex] ?? undefined },
          renderInlineTokens(cell.tokens, components),
        ),
      )

      const bodyRows = token.rows.map((row, rowIndex) =>
        h(
          'tr',
          { key: `row-${rowIndex}` },
          row.map((cell, cellIndex) =>
            h(
              'td',
              {
                key: `cell-${rowIndex}-${cellIndex}`,
                align: token.align?.[cellIndex] ?? undefined,
              },
              renderInlineTokens(cell.tokens, components),
            ),
          ),
        ),
      )

      nodes.push(
        h('table', { key: `table-${index}` }, [
          h('thead', { key: 'thead' }, [h('tr', { key: 'head-row' }, headerCells)]),
          h('tbody', { key: 'tbody' }, bodyRows),
        ]),
      )
      return
    }

    if (token.type === 'html') {
      nodes.push(
        h('div', {
          key: `html-${index}`,
          innerHTML: token.text,
        }),
      )
      return
    }

    if ('tokens' in token && token.tokens) {
      nodes.push(
        h(
          'p',
          { key: `paragraph-${index}` },
          renderInlineTokens(token.tokens, components),
        ),
      )
      return
    }

    const html = marked.parser([token], parserOptions)
    nodes.push(
      h('div', {
        key: `raw-${index}`,
        innerHTML: html,
      }),
    )
  })

  return nodes
}

export default defineComponent({
  name: 'Markdown',
  props: {
    content: {
      type: String,
      default: '',
    },
    id: {
      type: String,
      default: undefined,
    },
    class: {
      type: String,
      default: undefined,
    },
    components: {
      type: Object as () => Partial<MarkdownComponents>,
      default: undefined,
    },
  },
  setup(props, { slots }) {
    const instance = getCurrentInstance()
    const baseId = computed(
      () => props.id ?? `markdown-${instance?.uid ?? Math.random().toString(36).slice(2)}`,
    )

    const mergedComponents = computed<Required<MarkdownComponents>>(() => ({
      ...defaultComponents,
      ...props.components,
    }))

    const rawContent = computed(
      () =>
        props.content ??
        slots.default?.()
          .map((vnode) => (typeof vnode.children === 'string' ? vnode.children : ''))
          .join('') ??
        '',
    )

    const tokens = computed(() => marked.lexer(rawContent.value))

    const containerClass = computed(() => cn(props.class))

    return () =>
      h(
        'div',
        { class: containerClass.value, id: baseId.value },
        renderTokens(tokens.value, mergedComponents.value),
      )
  },
})
</script>

<style scoped>
:deep(.markdown-inline-code) {
  background-color: var(--primary-foreground);
  border-radius: 0.125rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.875rem;
  padding: 0.125rem 0.25rem;
}

:deep(pre) {
  margin: 0;
}

:deep(ul),
:deep(ol) {
  margin: 0;
  padding-left: 1.25rem;
}

:deep(blockquote) {
  border-left: 3px solid var(--border);
  margin: 0;
  padding-left: 1rem;
  color: var(--muted-foreground);
  font-style: italic;
}

:deep(table) {
  border-collapse: collapse;
  width: 100%;
}

:deep(th),
:deep(td) {
  border: 1px solid var(--border);
  padding: 0.5rem;
  text-align: left;
}
</style>
