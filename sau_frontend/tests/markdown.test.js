import { test } from 'node:test'
import assert from 'node:assert/strict'
import { renderMarkdown } from '../src/utils/markdown.js'

test('renders headings, lists, tables and fenced code', () => {
  const html = renderMarkdown('# 结果\n\n- **账号**\n\n| 名称 | 状态 |\n| --- | --- |\n| 测试 | 正常 |\n\n```python\nprint("ok")\n```')
  for (const tag of ['<h1>', '<ul>', '<strong>', '<table>', '<pre>', 'language-python']) assert.ok(html.includes(tag), tag)
})

test('escapes raw HTML and code instead of executing it', () => {
  const html = renderMarkdown('<script>alert(1)</script>\n\n```html\n<img src=x onerror=alert(1)>\n```')
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('<img'))
  assert.ok(html.includes('&lt;script&gt;'))
  assert.ok(html.includes('&lt;img'))
})

test('rejects executable link protocols and protects external links', () => {
  assert.ok(!renderMarkdown('[bad](javascript:alert(1))').includes('href='))
  assert.ok(!renderMarkdown('[bad](data:text/html,hello)').includes('href='))
  const html = renderMarkdown('[文档](https://example.com)')
  assert.ok(html.includes('target="_blank"'))
  assert.ok(html.includes('rel="noopener noreferrer"'))
})

test('renders line breaks, inline code and empty content', () => {
  assert.ok(renderMarkdown('第一行\n第二行 `code`').includes('<br>'))
  assert.ok(renderMarkdown('`code`').includes('<code>code</code>'))
  assert.equal(renderMarkdown(null), '')
})
