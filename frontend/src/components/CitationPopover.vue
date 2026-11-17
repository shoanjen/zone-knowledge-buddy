<script setup>
import { computed } from 'vue'
import CitationPop from './CitationPop.vue'

// 规格§9.2：内联引用 chip，点击弹出来源原文；来源不可用时黄色警示
const props = defineProps({
  // { doc_id, block_id, text?, origin?, title?, broken? }；骨架态仅含 doc_id/block_id
  citation: { type: Object, required: true },
})

// chip 文案：[doc_id 前 8 位…:block_id]
const chipLabel = computed(() => {
  const doc = String(props.citation.doc_id || '')
  const short = doc.length > 8 ? `${doc.slice(0, 8)}…` : doc
  return `[${short}:${props.citation.block_id ?? ''}]`
})
</script>

<template>
  <el-popover placement="top" trigger="click" :width="340">
    <template #reference>
      <span class="citation-chip" :class="{ broken: !!citation.broken || !citation.text }">
        {{ chipLabel }}
      </span>
    </template>
    <CitationPop :citation="citation" />
  </el-popover>
</template>

<style scoped>
/* 内联引用 chip：等宽小徽标，基线对齐正文 */
.citation-chip {
  display: inline-block;
  position: relative;
  top: -1px;
  margin: 0 2px;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--fg);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 16px;
  cursor: pointer;
  user-select: none;
  vertical-align: baseline;
  white-space: nowrap;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.citation-chip:hover {
  border-color: var(--accent-border);
  color: var(--accent);
}

/* 来源不可用：暖色警示弱化 */
.citation-chip.broken {
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 30%, var(--border));
}

.citation-chip.broken:hover {
  border-color: color-mix(in srgb, var(--warn) 55%, var(--border));
}
</style>
