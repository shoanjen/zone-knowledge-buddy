<script setup>
// 规格：Agent 执行过程时间线，四类 step_type 分色节点（降饱和）
defineProps({
  steps: { type: Array, default: () => [] },
})

const TYPE_COLOR = {
  thought: 'var(--accent)',
  tool: '#7c6cb0',
  observation: 'var(--success)',
  reflection: 'var(--warn)',
}

function colorOf(step) {
  return TYPE_COLOR[step?.step_type] || 'var(--faint)'
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
      return `工具调用 · ${c.tool ?? '未知'}`
    case 'observation':
      return `观察 · ${c.tool ?? c.phase ?? '结果'}`
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
    >
      <div class="step-item">
        <div class="step-head">
          <span class="step-title">{{ titleOf(step) }}</span>
          <span class="step-time tnum">{{ formatTime(step.created_at) }}</span>
        </div>
        <div class="step-body">
          <template v-if="step.step_type === 'thought'">
            <p v-if="thoughtText(step)" class="step-text">{{ thoughtText(step) }}</p>
            <ol v-if="planSteps(step).length" class="plan-list">
              <li v-for="(p, i) in planSteps(step)" :key="i" class="plan-item">
                <span class="tnum plan-no">{{ p.no ?? i + 1 }}.</span>
                <span class="plan-desc">{{ p.description }}</span>
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

.step-item {
  min-width: 0;
}

.step-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.step-title {
  min-width: 0;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fg-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-time {
  flex-shrink: 0;
  font-size: 11.5px;
  color: var(--muted);
}

.step-text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--fg);
  white-space: pre-wrap;
  word-break: break-word;
}

.plan-list {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.plan-item {
  display: flex;
  gap: 6px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--fg);
}

.plan-no {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--muted);
}

.plan-desc {
  min-width: 0;
  word-break: break-word;
}

.step-pre {
  margin: 0;
  padding: 10px 12px;
  background: var(--surface-2);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--fg);
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
