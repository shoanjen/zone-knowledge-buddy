<script setup>
import { computed } from 'vue'

// 规格§13.3：low 显示黄色警示与原因 tooltip；high 不渲染
const props = defineProps({
  quality: { type: String, default: null },
  reason: { type: String, default: null },
})

const REASONS = {
  scanned: '疑似扫描件，未做 OCR，文本可能不完整',
  oversize: '数据量超限，已截断处理',
}

const reasonText = computed(() => REASONS[props.reason] || props.reason || '解析质量低')
</script>

<template>
  <el-tooltip v-if="quality === 'low'" :content="`低质量：${reasonText}`" placement="top">
    <el-tag type="warning" size="small" effect="plain">低质量</el-tag>
  </el-tooltip>
</template>
