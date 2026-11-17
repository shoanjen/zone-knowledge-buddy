<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  ChatDotRound,
  DataAnalysis,
  Document,
  Files,
  Notebook,
} from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'
import { useNotesStore } from '../stores/notes'
import { useReportsStore } from '../stores/reports'
import { useTasksStore } from '../stores/tasks'
import { listDocuments } from '../api/documents'
import { listNotes } from '../api/notes'
import { listReports } from '../api/reports'
import { listTasks } from '../api/tasks'
import ImportPanel from '../components/ImportPanel.vue'
import GenerateDialog from '../components/GenerateDialog.vue'

const router = useRouter()
const documentsStore = useDocumentsStore()
const notesStore = useNotesStore()
const reportsStore = useReportsStore()
const tasksStore = useTasksStore()

// 与 tasks store 的 ACTIVE（轮询用，不含 paused）不同：工作台统计把「待确认」也算进行中
const ACTIVE_STATUSES = ['pending', 'planning', 'running', 'reflecting', 'paused']

const counts = ref({ documents: 0, notes: 0, reports: 0, activeTasks: 0 })

// 三步工作流：知识库 → 提问 → 产出
const flow = computed(() => [
  {
    step: '01',
    icon: Files,
    title: '知识库',
    desc: '导入 PDF / Word / Markdown / Excel 或网页，自动解析、切片与向量化',
    metric: `${counts.value.documents} 篇文档`,
    to: '/documents',
  },
  {
    step: '02',
    icon: ChatDotRound,
    title: '智能问答',
    desc: '就你的资料提问，回答只依据知识库生成、附可回溯引用',
    metric: '随时开始',
    to: '/chat',
  },
  {
    step: '03',
    icon: Notebook,
    title: '智能产出',
    desc: 'Agent 按你的意图，从文档提炼可溯源笔记与结构化报告',
    metric: `笔记 ${counts.value.notes} · 报告 ${counts.value.reports}`,
    to: '/assets',
  },
])

// 最近产出：笔记与报告合并时间线，带类型标记
const recentOutputs = computed(() => {
  const notes = notesStore.list.slice(0, 5).map((n) => ({
    id: n.id,
    kind: 'note',
    title: n.title || '（无标题）',
    time: n.updated_at,
    to: `/notes/${n.id}`,
  }))
  const reports = reportsStore.list.slice(0, 5).map((r) => ({
    id: r.id,
    kind: 'report',
    title: r.title || '（无标题）',
    time: r.created_at,
    to: `/reports/${r.id}/preview`,
  }))
  return [...notes, ...reports].sort((a, b) => String(b.time).localeCompare(String(a.time))).slice(0, 6)
})

function formatTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 统计卡与最近列表共用各 store 的同一次 fetchList 结果
async function refreshAll() {
  await Promise.allSettled([
    documentsStore.fetchList(),
    notesStore.fetchList(),
    reportsStore.fetchList(),
    tasksStore.fetchList(),
  ])
}

// 统计独立取数：不受文档/任务页当前筛选与分页影响
async function refreshCounts() {
  const [docs, notes, reports, tasks] = await Promise.allSettled([
    listDocuments({ page: 1, page_size: 1 }),
    listNotes({ page: 1, page_size: 1 }),
    listReports({ page: 1, page_size: 1 }),
    listTasks({ page: 1, page_size: 100 }),
  ])
  counts.value = {
    documents: docs.status === 'fulfilled' ? docs.value.total : 0,
    notes: notes.status === 'fulfilled' ? notes.value.total : 0,
    reports: reports.status === 'fulfilled' ? reports.value.total : 0,
    activeTasks:
      tasks.status === 'fulfilled'
        ? tasks.value.items.filter((t) => ACTIVE_STATUSES.includes(t.status)).length
        : 0,
  }
}

onMounted(() => {
  refreshAll()
  refreshCounts()
})

// ---- 上传后的下一步引导：基于刚导入的文档选择生成笔记 / 报告 ----
const genVisible = ref(false)
const genPreset = ref([])

function onImported(docIds) {
  refreshAll()
  refreshCounts()
  if (docIds && docIds.length) {
    genPreset.value = docIds
    genVisible.value = true
  }
}
</script>

<template>
  <div class="page workbench">
    <div class="page-head">
      <div>
        <h2 class="page-title">工作台</h2>
        <p class="page-sub">从沉淀资料到提问，再到可溯源的产出</p>
      </div>
      <router-link v-if="counts.activeTasks" to="/tasks" class="active-chip">
        <span class="pulse-dot" />
        {{ counts.activeTasks }} 个任务进行中
      </router-link>
    </div>

    <!-- 三步工作流 -->
    <div class="flow">
      <template v-for="(f, i) in flow" :key="f.step">
        <div
          class="flow-card rise-in"
          :class="'stagger-' + (i + 1)"
          role="link"
          :title="`前往${f.title}`"
          @click="router.push(f.to)"
        >
          <div class="flow-top">
            <span class="flow-step tnum">{{ f.step }}</span>
            <span class="flow-icon-badge">
              <el-icon :size="18"><component :is="f.icon" /></el-icon>
            </span>
          </div>
          <div class="flow-title">{{ f.title }}</div>
          <p class="flow-desc">{{ f.desc }}</p>
          <div class="flow-metric">
            <span>{{ f.metric }}</span>
            <el-icon :size="13"><ArrowRight /></el-icon>
          </div>
        </div>
        <el-icon v-if="i < flow.length - 1" class="flow-arrow" :size="16"><ArrowRight /></el-icon>
      </template>
    </div>

    <!-- 导入入口 -->
    <el-card class="block-card">
      <template #header>
        <div class="card-head">
          <span>导入新资料</span>
          <el-button link size="small" @click="router.push('/documents')">查看文档库</el-button>
        </div>
      </template>
      <ImportPanel @submitted="onImported" />
    </el-card>

    <!-- 最近产出（笔记 + 报告 合并时间线） -->
    <el-card class="block-card">
      <template #header>
        <div class="card-head">
          <span>最近产出</span>
          <div class="head-links">
            <el-button link size="small" @click="router.push('/assets?tab=notes')">笔记</el-button>
            <el-button link size="small" @click="router.push('/assets?tab=reports')">报告</el-button>
          </div>
        </div>
      </template>
      <div v-loading="notesStore.loading || reportsStore.loading" class="item-list">
        <template v-if="recentOutputs.length">
          <div v-for="o in recentOutputs" :key="o.kind + o.id" class="list-item" @click="router.push(o.to)">
            <span class="kind-tag" :class="o.kind">{{ o.kind === 'note' ? '笔记' : '报告' }}</span>
            <span class="item-title">{{ o.title }}</span>
            <span class="item-time tnum">{{ formatTime(o.time) }}</span>
          </div>
        </template>
        <el-empty
          v-else-if="!notesStore.loading && !reportsStore.loading"
          description="还没有产出：上传文档后按引导生成，或在文档库对某篇文档发起"
          :image-size="60"
        />
      </div>
    </el-card>

    <!-- 上传后的下一步：选择生成笔记 / 报告（等待解析就绪后自动放行） -->
    <GenerateDialog
      v-model="genVisible"
      :preset-doc-ids="genPreset"
      title="资料已提交 · 想生成什么？"
    />
  </div>
</template>

<style scoped>
/* ---------- 页头右侧：进行中任务 ---------- */
.active-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border: 1px solid var(--accent-border);
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12.5px;
  font-weight: 600;
  white-space: nowrap;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.6s ease infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

/* ---------- 三步工作流 ---------- */
.flow {
  display: flex;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 16px;
}

.flow-card {
  position: relative;
  flex: 1;
  min-width: 0;
  padding: 16px 18px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: border-color 0.22s var(--ease-out), box-shadow 0.22s var(--ease-out),
    transform 0.22s var(--ease-out);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 悬停时的墨绿光晕描边（用伪元素避免影响布局） */
.flow-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: inset 0 0 0 1px var(--accent-border);
  opacity: 0;
  transition: opacity 0.22s var(--ease-out);
  pointer-events: none;
}

.flow-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-float);
}

.flow-card:hover::before {
  opacity: 1;
}

.flow-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.flow-step {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--faint);
}

.flow-icon-badge {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--accent-grad);
  color: #fff;
  box-shadow: var(--accent-glow);
  transition: transform 0.25s var(--ease-spring);
}

.flow-card:hover .flow-icon-badge {
  transform: scale(1.08) rotate(-4deg);
}

.flow-title {
  margin-top: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--fg-strong);
}

.flow-desc {
  margin: 6px 0 12px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--muted);
  flex: 1;
}

.flow-metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--accent);
  transition: gap 0.2s var(--ease-out);
}

.flow-card:hover .flow-metric {
  gap: 6px;
}

.flow-arrow {
  align-self: center;
  flex-shrink: 0;
  color: var(--faint);
  animation: float-x 2.6s ease-in-out infinite;
}

@keyframes float-x {
  0%,
  100% {
    transform: translateX(0);
    opacity: 0.6;
  }
  50% {
    transform: translateX(3px);
    opacity: 1;
  }
}

/* ---------- 区块卡 ---------- */
.block-card {
  margin-bottom: 14px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.head-links .el-button + .el-button {
  margin-left: 8px;
}

/* ---------- 最近产出 ---------- */
.item-list {
  min-height: 120px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 2px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}

.list-item:last-child {
  border-bottom: none;
}

.kind-tag {
  flex-shrink: 0;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.kind-tag.note {
  background: var(--accent-soft);
  color: var(--accent);
}

.kind-tag.report {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--muted);
}

.item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 500;
  color: var(--fg);
  transition: color 0.15s ease;
}

.list-item:hover .item-title {
  color: var(--accent);
}

.item-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--muted);
}

/* 窄屏：流程卡纵向排列，箭头隐藏 */
@media (max-width: 900px) {
  .flow {
    flex-direction: column;
  }

  .flow-arrow {
    display: none;
  }
}
</style>
