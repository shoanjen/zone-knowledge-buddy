<script setup>
import { Picture } from '@element-plus/icons-vue'

// 契约：blocks 元素 { block_id, type, level, text, caption, data, ref }
// type ∈ heading / paragraph / table / image
defineProps({
  blocks: { type: Array, default: () => [] },
})

// heading 按 level 1-4 渲染 h1-h4，越界或缺失时收敛到合理档位
function headingLevel(level) {
  const n = Number(level)
  if (!Number.isFinite(n)) return 2
  return Math.min(4, Math.max(1, Math.round(n)))
}

// data 为二维数组：首行是表头
function tableColumns(block) {
  const data = block?.data
  return Array.isArray(data) && Array.isArray(data[0]) ? data[0] : []
}

// 行数据从 data.slice(1) 转对象，列键按序号生成（c0 / c1 / ...）
function tableRows(block) {
  const data = block?.data
  if (!Array.isArray(data) || !Array.isArray(data[0]) || data.length < 2) return []
  return data.slice(1).map((row) => {
    const item = {}
    data[0].forEach((_, i) => {
      item[`c${i}`] = Array.isArray(row) ? row[i] ?? '' : ''
    })
    return item
  })
}

// 图片块展示 ref 文件名（存档相对路径取末段）
function refName(block) {
  const ref = String(block?.ref || '')
  if (!ref) return '图片'
  return ref.split('/').pop() || ref
}
</script>

<template>
  <div class="block-browser">
    <el-empty v-if="!blocks.length" description="暂无内容块" :image-size="80" />

    <template v-else>
      <div v-for="block in blocks" :key="block.block_id" class="block">
        <component
          :is="`h${headingLevel(block.level)}`"
          v-if="block.type === 'heading'"
          class="heading"
        >
          {{ block.text }}
        </component>

        <p v-else-if="block.type === 'paragraph'" class="paragraph">{{ block.text }}</p>

        <div v-else-if="block.type === 'table'" class="table-block">
          <div v-if="block.caption" class="table-caption">{{ block.caption }}</div>
          <el-table :data="tableRows(block)" size="small" border>
            <el-table-column
              v-for="(head, i) in tableColumns(block)"
              :key="i"
              :prop="`c${i}`"
              :label="String(head ?? '')"
              min-width="90"
            />
          </el-table>
        </div>

        <div v-else-if="block.type === 'image'" class="image-block">
          <el-icon class="image-icon"><Picture /></el-icon>
          <span class="image-name">{{ refName(block) }}</span>
          <span v-if="block.caption" class="hint image-caption">{{ block.caption }}</span>
          <span class="hint image-note">图片已存档</span>
        </div>

        <p v-else-if="block.text" class="paragraph">{{ block.text }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.block-browser {
  line-height: 1.7;
}

/* 标题：衬线、无装饰线，按层级收敛字号 */
.heading {
  margin: 18px 0 8px;
  font-family: var(--font-display);
  font-weight: 600;
  color: var(--fg-strong);
  line-height: 1.45;
}

h1.heading {
  font-size: 19px;
}

h2.heading {
  font-size: 16.5px;
}

h3.heading {
  font-size: 15px;
}

h4.heading {
  font-size: 14px;
}

.block:first-child .heading {
  margin-top: 0;
}

/* 正文：适中的阅读行宽 */
.paragraph {
  margin: 0 0 10px;
  max-width: 74ch;
  font-size: 14px;
  line-height: 1.75;
  color: var(--fg);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 表格：弱化题注 */
.table-block {
  margin: 14px 0;
}

.table-caption {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--muted);
}

/* 图片占位：图标 + 文件名 + 存档说明，一行排开 */
.image-block {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0;
}

.image-icon {
  flex-shrink: 0;
  font-size: 18px;
  color: var(--muted);
}

.image-name {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--fg);
  word-break: break-all;
}

.image-caption {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-note {
  flex-shrink: 0;
}
</style>
