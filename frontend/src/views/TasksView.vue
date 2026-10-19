<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTasksStore } from '../stores/tasks'
import StatusBadge from '../components/StatusBadge.vue'
import TaskTimeline from '../components/TaskTimeline.vue'

const store = useTasksStore()

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '等待中' },
  { value: 'planning', label: '规划中' },
  { value: 'running', label: '执行中' },
  { value: 'reflecting', label: '反思中' },
  { value: 'paused', label: '待确认' },
  { value: 'done', label: '完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

const TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'note.generate', label: '笔记生成' },
  { value: 'report.generate', label: '报告生成' },
]

const TYPE_LABELS = {
  'note.generate': '笔记生成',
  'report.generate': '报告生成',
}

// 取消任务仅在任务尚未结束/暂停时可用
const CANCELABLE = ['pending', 'planning', 'running', 'reflecting']

const drawerVisible = ref(false)
const detailLoading = ref(false)
const actionLoading = ref(false)
const editedContent = ref('')

const current = computed(() => store.current)
const isPaused = computed(() => current.value?.status === 'paused')
const cancelable = computed(() => CANCELABLE.includes(current.value?.status))
const drawerTitle = computed(() =>
  current.value ? `任务详情 · ${shortId(current.value.id)}` : '任务详情',
)

function shortId(id) {
  return String(id ?? '').slice(0, 14)
}

function typeLabel(type) {
  return TYPE_LABELS[type] || type || '—'
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function onFilterChange() {
  store.page = 1
  store.fetchList()
}

function onPageChange(page) {
  store.page = page
  store.fetchList()
}

function onSizeChange(size) {
  store.pageSize = size
  store.page = 1
  store.fetchList()
}

async function openDetail(row) {
  drawerVisible.value = true
  detailLoading.value = true
  try {
    await store.fetchDetail(row.id)
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    detailLoading.value = false
  }
}

// paused 草稿的本地可编辑副本：仅在任务 id 或状态变化时同步，避免轮询刷新覆盖用户编辑
watch(
  () => [store.current?.id, store.current?.status],
  () => {
    const task = store.current
    if (task?.status === 'paused') {
      editedContent.value = task.draft?.content_md || ''
    }
  },
  { immediate: true },
)

// 轮询由 store 处理；列表每次刷新（含静默轮询）后，若抽屉开着则同步刷新详情
watch(
  () => store.list,
  () => {
    if (drawerVisible.value && store.current) {
      store.fetchDetail(store.current.id).catch(() => {})
    }
  },
)

async function approveDraft() {
  const task = store.current
  if (!task) return
  actionLoading.value = true
  try {
    await store.confirm(task.id, true, editedContent.value)
    ElMessage.success('草稿已批准并保存')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

async function rejectDraft() {
  const task = store.current
  if (!task) return
  try {
    await ElMessageBox.confirm('拒绝后任务将终止，且不可恢复。确定拒绝吗？', '拒绝确认', {
      type: 'warning',
      confirmButtonText: '确定拒绝',
      cancelButtonText: '再想想',
    })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await store.confirm(task.id, false)
    ElMessage.success('已拒绝该草稿')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

async function cancelTask() {
  const task = store.current
  if (!task) return
  try {
    await ElMessageBox.confirm('取消后任务将终止，且不可恢复。确定取消吗？', '取消任务', {
      type: 'warning',
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
    })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await store.cancel(task.id)
    ElMessage.success('任务已取消')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    actionLoading.value = false
  }
}

function onDrawerClosed() {
  store.current = null
  editedContent.value = ''
}

onMounted(() => store.fetchList())
</script>

<template>
  <div class="tasks-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">任务中心</h2>
        <p class="page-subtitle">笔记与报告生成任务，进行中的任务每 3 秒自动刷新</p>
      </div>
    </div>

    <div class="filter-bar">
      <el-select
        v-model="store.filterStatus"
        class="filter-select"
        placeholder="全部状态"
        @change="onFilterChange"
      >
        <el-option v-for="opt in STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-select
        v-model="store.filterType"
        class="filter-select"
        placeholder="全部类型"
        @change="onFilterChange"
      >
        <el-option v-for="opt in TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <el-table
      v-loading="store.loading"
      :data="store.list"
      class="tasks-table"
      @row-click="openDetail"
    >
      <el-table-column label="任务 ID" width="160">
        <template #default="{ row }">
          <span class="task-id">{{ shortId(row.id) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ typeLabel(row.type) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <StatusBadge :status="row.status" />
        </template>
      </el-table-column>
      <el-table-column prop="provider_name" label="模型" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.provider_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="错误" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.error ? 'error-text' : ''">{{ row.error || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="完成时间" width="170">
        <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :total="store.total"
        :current-page="store.page"
        :page-size="store.pageSize"
        :page-sizes="[10, 20, 50]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <el-drawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="50%"
      @closed="onDrawerClosed"
    >
      <div v-loading="detailLoading" class="drawer-body">
        <template v-if="current">
          <el-alert
            v-if="current.error"
            class="drawer-error"
            type="error"
            :title="current.error"
            :closable="false"
            show-icon
          />

          <div class="drawer-section">
            <h3 class="section-title">任务信息</h3>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="任务 ID" :span="2">{{ current.id }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ typeLabel(current.type) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <StatusBadge :status="current.status" />
              </el-descriptions-item>
              <el-descriptions-item label="模型">{{ current.provider_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="文档数量">
                {{ current.input?.doc_ids?.length ?? 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(current.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="完成时间">{{ formatTime(current.finished_at) }}</el-descriptions-item>
              <el-descriptions-item label="意图" :span="2">
                {{ current.input?.intent || '—' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div v-if="isPaused" class="drawer-section">
            <h3 class="section-title">草稿确认</h3>
            <el-input
              v-model="editedContent"
              type="textarea"
              :rows="12"
              placeholder="暂无草稿内容"
            />
            <div class="confirm-actions">
              <el-button type="primary" :loading="actionLoading" @click="approveDraft">
                批准并保存
              </el-button>
              <el-button type="danger" :loading="actionLoading" @click="rejectDraft">拒绝</el-button>
            </div>
          </div>

          <div v-if="cancelable" class="drawer-section">
            <el-button
              type="danger"
              plain
              :loading="actionLoading"
              @click="cancelTask"
            >
              取消任务
            </el-button>
          </div>

          <div class="drawer-section">
            <h3 class="section-title">执行过程</h3>
            <TaskTimeline :steps="current.steps || []" />
          </div>
        </template>
        <el-empty v-else-if="!detailLoading" description="任务详情加载失败" />
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.tasks-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #909399;
}

.filter-bar {
  display: flex;
  gap: 12px;
}

.filter-select {
  width: 160px;
}

.tasks-table {
  width: 100%;
}

.tasks-table :deep(.el-table__row) {
  cursor: pointer;
}

.task-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  color: #606266;
}

.error-text {
  color: #f56c6c;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 100%;
}

.drawer-error {
  margin-bottom: 4px;
}

.section-title {
  margin: 0 0 10px;
  font-size: 15px;
  color: #303133;
}

.confirm-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}
</style>
