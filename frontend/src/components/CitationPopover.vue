<script setup>
import { computed } from 'vue'

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

// 来源不可用：显式 broken，或原文缺失（含骨架态）
const unavailable = computed(() => !!props.citation.broken || !props.citation.text)

// 原文截断 300 字；容器限高可滚动
const quote = computed(() => {
  const text = String(props.citation.text || '')
  return text.length > 300 ? `${text.slice(0, 300)}…` : text
})
</script>

<template>
  <el-popover placement="top" trigger="click" :width="340">
    <template #reference>
      <span class="citation-chip" :class="{ broken: unavailable }">{{ chipLabel }}</span>
    </template>
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
  </el-popover>
</template>

<style scoped>
.citation-chip {
  display: inline-block;
  margin: 0 2px;
  padding: 0 6px;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  line-height: 18px;
  cursor: pointer;
  user-select: none;
  vertical-align: baseline;
  white-space: nowrap;
}

.citation-chip:hover {
  background: #d9ecff;
}

.citation-chip.broken {
  border-color: #faecd8;
  background: #fdf6ec;
  color: #e6a23c;
}

.citation-chip.broken:hover {
  background: #faecd8;
}

.citation-pop {
  font-size: 13px;
}

.meta {
  margin-bottom: 8px;
}

.meta-title {
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-origin {
  margin-top: 2px;
  color: #909399;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warn {
  margin-bottom: 4px;
}

.quote {
  max-height: 200px;
  padding: 8px 10px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
  line-height: 1.6;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
