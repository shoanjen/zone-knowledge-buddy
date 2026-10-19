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
          <div class="image-meta">
            <div class="image-name">{{ refName(block) }}</div>
            <div v-if="block.caption" class="image-caption">{{ block.caption }}</div>
            <div class="image-note">图片已存档</div>
          </div>
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

.block {
  margin-bottom: 4px;
}

.block:first-child .heading {
  margin-top: 0;
}

.heading {
  color: #303133;
  font-weight: 600;
  line-height: 1.4;
}

h1.heading {
  margin: 24px 0 12px;
  font-size: 22px;
}

h2.heading {
  margin: 20px 0 10px;
  font-size: 19px;
}

h3.heading {
  margin: 18px 0 8px;
  font-size: 16px;
}

h4.heading {
  margin: 16px 0 8px;
  font-size: 14px;
}

.paragraph {
  margin: 0 0 10px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.table-block {
  margin: 12px 0;
}

.table-caption {
  margin-bottom: 6px;
  font-size: 13px;
  color: #606266;
  text-align: center;
}

.image-block {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 10px 0;
  padding: 12px 16px;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  background: #fafbfc;
}

.image-icon {
  font-size: 26px;
  color: #909399;
}

.image-meta {
  min-width: 0;
}

.image-name {
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.image-caption {
  font-size: 12px;
  color: #909399;
}

.image-note {
  margin-top: 2px;
  font-size: 12px;
  color: #67c23a;
}
</style>
