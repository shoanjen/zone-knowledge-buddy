<script setup>
// 规格：Agent 执行过程时间线，四类 step_type 分色节点
defineProps({
  steps: { type: Array, default: () => [] },
})

const TYPE_COLOR = {
  thought: '#409eff',
  tool: '#9a6fe0',
  observation: '#67c23a',
  reflection: '#e6a23c',
}

function colorOf(step) {
  return TYPE_COLOR[step?.step_type] || '#c0c4cc'
}

function contentOf(step) {
  const c = step?.content
  return c && typeof c === 'object' && !Array.isArray(c) ? c : {}
}

function titleOf(step) {
  const c = contentOf(step)
  switch (step?.step_type) {
    case 'thought':
      return '思考'
    case 'tool':
      return `工具调用：${c.tool ?? '未知'}`
    case 'observation':
      return `观察：${c.tool ?? '未知'}`
    case 'reflection':
      return '反思'
    default:
      return step?.step_type || '未知步骤'
  }
}

function thoughtText(step) {
  const t = contentOf(step).thought
  return typeof t === 'string' ? t : ''
}

function planSteps(step) {
  const c = contentOf(step)
  if (c.phase !== 'plan') return []
  return Array.isArray(c.steps) ? c.steps : []
}

function pretty(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function truncate(text, max = 1500) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}\n…` : text
}

function formatTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
</script>

<template>
  <el-timeline v-if="steps.length" class="task-timeline">
    <el-timeline-item
      v-for="(step, idx) in steps"
      :key="step.seq ?? idx"
      :color="colorOf(step)"
      :timestamp="formatTime(step.created_at)"
      placement="top"
    >
      <div class="step-card">
        <div class="step-title" :style="{ color: colorOf(step) }">{{ titleOf(step) }}</div>
        <div class="step-body">
          <template v-if="step.step_type === 'thought'">
            <p v-if="thoughtText(step)" class="step-text">{{ thoughtText(step) }}</p>
            <ol v-if="planSteps(step).length" class="plan-list">
              <li v-for="(p, i) in planSteps(step)" :key="i" class="plan-item">
                <span class="plan-no">{{ p.no ?? i + 1 }}.</span>{{ p.description }}
              </li>
            </ol>
            <pre v-if="!thoughtText(step) && !planSteps(step).length" class="step-pre">{{ pretty(step.content) }}</pre>
          </template>
          <template v-else-if="step.step_type === 'tool'">
            <pre class="step-pre">{{ pretty(contentOf(step).args) }}</pre>
          </template>
          <template v-else-if="step.step_type === 'observation'">
            <pre class="step-pre">{{ truncate(pretty(contentOf(step).result)) }}</pre>
          </template>
          <template v-else-if="step.step_type === 'reflection'">
            <pre class="step-pre">{{ pretty(contentOf(step).report) }}</pre>
          </template>
          <template v-else>
            <pre class="step-pre">{{ pretty(step.content) }}</pre>
          </template>
        </div>
      </div>
    </el-timeline-item>
  </el-timeline>
  <el-empty v-else description="暂无执行步骤" :image-size="72" />
</template>

<style scoped>
.task-timeline {
  padding-left: 4px;
}

.step-card {
  padding-bottom: 4px;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}

.step-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.plan-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
  color: #303133;
}

.plan-item .plan-no {
  font-weight: 600;
  margin-right: 4px;
}

.step-pre {
  margin: 0;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
