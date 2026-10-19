<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'
import ImportPanel from '../components/ImportPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import QualityTag from '../components/QualityTag.vue'

const route = useRoute()
const router = useRouter()
const store = useDocumentsStore()

const SOURCE_TYPE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'pdf', label: 'PDF' },
  { value: 'word', label: 'Word' },
  { value: 'md', label: 'Markdown' },
  { value: 'excel', label: 'Excel' },
  { value: 'web', label: '网页' },
]

const TYPE_TAG = {
  pdf: { label: 'PDF', type: 'primary' },
  word: { label: 'Word', type: 'success' },
  md: { label: 'Markdown', type: 'warning' },
  excel: { label: 'Excel', type: 'danger' },
  web: { label: '网页', type: 'info' },
}

// 筛选值先落在本地，点「查询」才写入 store 并刷新，避免输入到一半的条件被 3s 轮询带走
const filterType = ref(store.filterSourceType)
const keyword = ref(store.keyword)

function typeMeta(sourceType) {
  return TYPE_TAG[sourceType] || { label: sourceType || '—', type: 'info' }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false })
}

function docTitle(row) {
  return row.title || row.origin || row.id
}

async function fetchList() {
  try {
    await store.fetchList()
  } catch {
    // 错误提示由 http 拦截器统一弹出
  }
}

function applyFilter() {
  store.filterSourceType = filterType.value
  store.keyword = keyword.value.trim()
  store.page = 1
  fetchList()
}

function onSubmitted() {
  // 导入提交后回到第一页，新文档按导入时间倒序排在最前
  store.page = 1
  fetchList()
}

function onPageChange() {
  fetchList()
}

function onSizeChange() {
  store.page = 1
  fetchList()
}

function goDetail(row) {
  router.push(`/documents/${row.id}`)
}

async function onRetry(row) {
  try {
    await store.retry(row.id)
    ElMessage.success('已重新提交解析')
  } catch {
    // 非 failed 状态等后端拒绝由拦截器统一弹出
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${docTitle(row)}」？删除后不可恢复。`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消删除
  }
  try {
    await store.remove(row.id)
    ElMessage.success('文档已删除')
  } catch {
    // 解析中不可删（409）等后端拒绝由拦截器统一弹出
  }
}

onMounted(fetchList)

// 当前路由未包 keep-alive，每次进入都会重新挂载并走 onMounted；
// 若将来加了 keep-alive，这里兜底在回到本页时刷新
watch(
  () => route.name,
  (name) => {
    if (name === 'documents') fetchList()
  },
)
</script>

<template>
  <div class="documents-page">
    <el-card shadow="never" class="card">
      <template #header>
        <span class="card-title">导入文档</span>
      </template>
      <ImportPanel @submitted="onSubmitted" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header>
        <span class="card-title">文档列表</span>
      </template>

      <div class="filter-bar">
        <el-select v-model="filterType" class="type-select">
          <el-option
            v-for="t in SOURCE_TYPE_OPTIONS"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
        <el-input
          v-model="keyword"
          class="keyword-input"
          placeholder="搜索标题 / 来源"
          clearable
          @keyup.enter="applyFilter"
          @clear="applyFilter"
        />
        <el-button type="primary" :icon="Search" :loading="store.loading" @click="applyFilter">
          查询
        </el-button>
      </div>

      <el-table v-loading="store.loading" :data="store.list" empty-text="暂无文档">
        <el-table-column label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row)">{{ docTitle(row) }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="来源类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="typeMeta(row.source_type).type" size="small" effect="plain">
              {{ typeMeta(row.source_type).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" prop="origin" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="质量" width="80" align="center">
          <template #default="{ row }">
            <QualityTag :quality="row.parse_quality" :reason="row.low_reason" />
            <span v-if="row.parse_quality !== 'low'" class="quality-dash">—</span>
          </template>
        </el-table-column>
        <el-table-column label="块 / 切片" width="100" align="center">
          <template #default="{ row }">
            {{ row.block_count ?? 0 }} / {{ row.chunk_count ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="导入时间" width="170">
          <template #default="{ row }">{{ formatTime(row.imported_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed'"
              link
              type="primary"
              size="small"
              @click="onRetry(row)"
            >
              重试
            </el-button>
            <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="store.page"
          v-model:page-size="store.pageSize"
          :total="store.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.documents-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

.card-title {
  font-weight: 600;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.type-select {
  width: 140px;
}

.keyword-input {
  width: 260px;
}

.quality-dash {
  color: #c0c4cc;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
