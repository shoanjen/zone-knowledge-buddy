<script setup>
import { computed } from 'vue'

// 规格§13.3：pending/parsing/ready/failed 四色 + 任务状态复用
const props = defineProps({
  status: { type: String, required: true },
})

const MAP = {
  pending: { label: '等待中', type: 'info' },
  parsing: { label: '解析中', type: 'warning' },
  ready: { label: '就绪', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  planning: { label: '规划中', type: 'warning' },
  running: { label: '执行中', type: 'warning' },
  reflecting: { label: '反思中', type: 'warning' },
  paused: { label: '待确认', type: 'primary' },
  done: { label: '完成', type: 'success' },
  cancelled: { label: '已取消', type: 'info' },
}

const item = computed(() => MAP[props.status] || { label: props.status, type: 'info' })
</script>

<template>
  <el-tag :type="item.type" size="small">{{ item.label }}</el-tag>
</template>
