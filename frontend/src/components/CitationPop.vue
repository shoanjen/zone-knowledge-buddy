<script setup>
import { computed } from 'vue'

// 引用弹层内容（CitationPopover 与问答 markdown 内联引用共用）
const props = defineProps({
  // { doc_id, block_id, text?, origin?, title?, broken? }；骨架态仅含 doc_id/block_id
  citation: { type: Object, required: true },
})

// 来源不可用：显式 broken，或原文缺失（含骨架态）
const unavailable = computed(() => !!props.citation.broken || !props.citation.text)

// 原文截断 300 字；容器限高可滚动
const quote = computed(() => {
  const text = String(props.citation.text || '')
  return text.length > 300 ? `${text.slice(0, 300)}…` : text
})
</script>

<template>
  <div class="citation-pop">
    <div v-if="citation.title || citation.origin" class="meta">
      <div v-if="citation.title" class="meta-title" :title="citation.title">
        {{ citation.title }}
      </div>
      <div v-if="citation.origin" class="meta-origin" :title="citation.origin">
        {{ citation.origin }}
      </div>
    </div>
    <el-alert
      v-if="unavailable"
      class="warn"
      type="warning"
      :closable="false"
      show-icon
      title="来源文档已删除或块不存在"
    />
    <div v-else class="quote">{{ quote }}</div>
  </div>
</template>

<style scoped>
.citation-pop {
  font-size: 12.5px;
}

.meta {
  margin-bottom: 8px;
}

.meta-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-origin {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warn {
  margin-bottom: 4px;
}

.quote {
  max-height: 200px;
  padding: 10px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--fg);
  font-size: 12.5px;
  line-height: 1.6;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
