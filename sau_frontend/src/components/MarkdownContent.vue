<template>
  <div class="markdown-content" v-html="rendered" />
</template>

<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({ content: { type: String, default: '' } })
const rendered = computed(() => DOMPurify.sanitize(renderMarkdown(props.content), {
  USE_PROFILES: { html: true },
  ADD_ATTR: ['target', 'rel'],
  FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe']
}))
</script>

<style scoped>
.markdown-content { white-space: normal; overflow-wrap: anywhere; overflow-x: auto; line-height: 1.8; }
.markdown-content :deep(> :first-child) { margin-top: 0; }
.markdown-content :deep(> :last-child) { margin-bottom: 0; }
.markdown-content :deep(h1), .markdown-content :deep(h2), .markdown-content :deep(h3),
.markdown-content :deep(h4), .markdown-content :deep(h5), .markdown-content :deep(h6) { margin: 1.2em 0 .5em; font-weight: 600; line-height: 1.5; color: #263b56; }
.markdown-content :deep(h1) { font-size: 1.6em; }
.markdown-content :deep(h2) { font-size: 1.35em; }
.markdown-content :deep(h3) { font-size: 1.15em; }
.markdown-content :deep(p) { margin: .7em 0; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { margin: .7em 0; padding-left: 1.8em; }
.markdown-content :deep(ul) { list-style: disc; }
.markdown-content :deep(ol) { list-style: decimal; }
.markdown-content :deep(li) { margin: .25em 0; }
.markdown-content :deep(blockquote) { margin: 1em 0; padding: .4em 1em; border-left: 3px solid #8ab7ed; background: #f3f7fc; color: #63758d; }
.markdown-content :deep(a) { color: #286fc5; text-decoration: underline; text-underline-offset: 3px; }
.markdown-content :deep(code) { padding: .15em .4em; border-radius: 4px; background: #edf1f6; font-family: Consolas, Monaco, monospace; font-size: .9em; }
.markdown-content :deep(pre) { margin: 1em 0; padding: 14px 16px; border-radius: 8px; background: #f3f5f8; overflow-x: auto; white-space: pre; line-height: 1.6; }
.markdown-content :deep(pre code) { padding: 0; background: transparent; border-radius: 0; }
.markdown-content :deep(table) { border-collapse: collapse; margin: 1em 0; min-width: 260px; max-width: 100%; }
.markdown-content :deep(th), .markdown-content :deep(td) { padding: 8px 12px; border: 1px solid #dfe6ef; text-align: left; }
.markdown-content :deep(th) { background: #f3f6fa; font-weight: 600; }
.markdown-content :deep(hr) { margin: 1.2em 0; border: 0; border-top: 1px solid #e3e9f1; }
.markdown-content :deep(img) { max-width: 100%; height: auto; border-radius: 6px; }
</style>
