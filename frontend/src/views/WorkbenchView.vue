<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, DataAnalysis, Document, Notebook } from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'
import { useNotesStore } from '../stores/notes'
import { useReportsStore } from '../stores/reports'
import { useTasksStore } from '../stores/tasks'
import ImportPanel from '../components/ImportPanel.vue'

const router = useRouter()
const documentsStore = useDocumentsStore()
const notesStore = useNotesStore()
const reportsStore = useReportsStore()
const tasksStore = useTasksStore()

// 与 tasks store 的 ACTIVE（轮询用，不含 paused）不同：工作台统计把「待确认」也算进行中
const ACTIVE_STATUSES = ['pending', 'planning', 'running', 'reflecting', 'paused']

const activeTaskCount = computed(
  () => tasksStore.list.filter((t) => ACTIVE_STATUSES.includes(t.status)).length,
)

const stats = computed(() => [
  { label: '文档总数', value: documentsStore.total, icon: Document, color: '#409eff', bg: '#ecf5ff' },
  { label: '笔记总数', value: notesStore.total, icon: Notebook, color: '#67c23a', bg: '#f0f9eb' },
  { label: '报告总数', value: reportsStore.total, icon: DataAnalysis, color: '#e6a23c', bg: '#fdf6ec' },
  { label: '进行中任务数', value: activeTaskCount.value, icon: Clock, color: '#f56c6c', bg: '#fef0f0' },
])

const recentNotes = computed(() => notesStore.list.slice(0, 5))
const recentReports = computed(() => reportsStore.list.slice(0, 5))

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

onMounted(refreshAll)
</script>

<template>
  <div class="workbench">
    <div class="page-head">
      <h2 class="page-title">工作台</h2>
      <p class="page-sub">概览知识库，导入新内容</p>
    </div>

    <el-row :gutter="12" class="stat-row">
      <el-col v-for="s in stats" :key="s.label" :xs="12" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <span class="stat-icon" :style="{ color: s.color, background: s.bg }">
              <el-icon :size="22"><component :is="s.icon" /></el-icon>
            </span>
            <div class="stat-info">
              <div class="stat-num">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="block-card">
      <template #header>
        <div class="card-head"><span>导入文档</span></div>
      </template>
      <ImportPanel @submitted="refreshAll" />
    </el-card>

    <el-row :gutter="12">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="block-card">
          <template #header>
            <div class="card-head">
              <span>最近笔记</span>
              <el-button link type="primary" @click="router.push('/notes')">查看全部</el-button>
            </div>
          </template>
          <div v-loading="notesStore.loading" class="item-list">
            <template v-if="recentNotes.length">
              <div
                v-for="n in recentNotes"
                :key="n.id"
                class="list-item"
                @click="router.push(`/notes/${n.id}`)"
              >
                <span class="item-title">{{ n.title || '（无标题）' }}</span>
                <span class="item-time">{{ formatTime(n.updated_at) }}</span>
              </div>
            </template>
            <el-empty
              v-else-if="!notesStore.loading"
              description="暂无笔记，可从文档生成"
              :image-size="60"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="block-card">
          <template #header>
            <div class="card-head">
              <span>最近报告</span>
              <el-button link type="primary" @click="router.push('/reports')">查看全部</el-button>
            </div>
          </template>
          <div v-loading="reportsStore.loading" class="item-list">
            <template v-if="recentReports.length">
              <div
                v-for="r in recentReports"
                :key="r.id"
                class="list-item"
                @click="router.push(`/reports/${r.id}/preview`)"
              >
                <span class="item-title">{{ r.title || '（无标题）' }}</span>
                <span class="item-time">{{ formatTime(r.created_at) }}</span>
              </div>
            </template>
            <el-empty
              v-else-if="!reportsStore.loading"
              description="暂无报告，可从文档生成"
              :image-size="60"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.workbench {
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  margin: 0;
  font-size: 22px;
}

.page-sub {
  margin: 4px 0 0;
  color: #909399;
  font-size: 13px;
}

.stat-row {
  margin-bottom: 12px;
}

.stat-card {
  margin-bottom: 12px;
}

.stat-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  flex-shrink: 0;
}

.stat-num {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
}

.stat-label {
  margin-top: 2px;
  color: #909399;
  font-size: 13px;
}

.block-card {
  margin-bottom: 12px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.item-list {
  min-height: 120px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px;
  border-bottom: 1px dashed #ebeef5;
  cursor: pointer;
}

.list-item:last-child {
  border-bottom: none;
}

.list-item:hover .item-title {
  color: #409eff;
}

.item-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.item-time {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}
</style>
