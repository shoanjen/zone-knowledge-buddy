<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useReportsStore } from '../stores/reports'
import { listDocuments } from '../api/documents'

const router = useRouter()
const store = useReportsStore()

const dialogVisible = ref(false)
const docLoading = ref(false)
const submitting = ref(false)
const readyDocs = ref([])
const form = reactive({
  doc_ids: [],
  intent: '',
  title: '',
})

function docKey(doc) {
  return doc.doc_id ?? doc.id
}

async function openDialog() {
  dialogVisible.value = true
  if (readyDocs.value.length) return
  docLoading.value = true
  try {
    const data = await listDocuments({ page_size: 100 })
    readyDocs.value = (data.items || []).filter((d) => d.status === 'ready')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    docLoading.value = false
  }
}

function resetForm() {
  form.doc_ids = []
  form.intent = ''
  form.title = ''
}

async function submitGenerate() {
  if (!form.doc_ids.length) {
    ElMessage.warning('请至少选择一个就绪文档')
    return
  }
  if (!form.intent.trim()) {
    ElMessage.warning('请填写报告意图')
    return
  }
  submitting.value = true
  try {
    await store.generate({
      doc_ids: form.doc_ids,
      intent: form.intent.trim(),
      title: form.title.trim() || undefined,
    })
    ElMessage.success('报告任务已提交')
    dialogVisible.value = false
    resetForm()
    router.push('/tasks')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    submitting.value = false
  }
}

function goPreview(row) {
  if (!row.has_html) return
  router.push(`/reports/${row.id}/preview`)
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

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(() => store.fetchList())
</script>

<template>
  <div class="reports-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">报告中心</h2>
        <p class="page-subtitle">基于选中文档生成的结构化报告</p>
      </div>
      <el-button type="primary" @click="openDialog">生成报告</el-button>
    </div>

    <el-table v-loading="store.loading" :data="store.list" class="reports-table">
      <el-table-column label="标题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.has_html" class="report-link" @click="goPreview(row)">{{ row.title }}</span>
          <span v-else class="report-title-plain">{{ row.title }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="intent" label="意图" min-width="240" show-overflow-tooltip />
      <el-table-column label="HTML" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.has_html ? 'success' : 'info'" size="small">
            {{ row.has_html ? '已生成' : '未生成' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
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

    <el-dialog
      v-model="dialogVisible"
      title="生成报告"
      width="560px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form label-position="top">
        <el-form-item label="选择文档（仅显示就绪文档）" required>
          <el-select
            v-model="form.doc_ids"
            multiple
            filterable
            :loading="docLoading"
            placeholder="请选择用于生成报告的文档"
            class="doc-select"
          >
            <el-option
              v-for="doc in readyDocs"
              :key="docKey(doc)"
              :label="doc.filename || String(docKey(doc))"
              :value="docKey(doc)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="报告意图" required>
          <el-input
            v-model="form.intent"
            type="textarea"
            :rows="3"
            placeholder="例如：总结所选文档的核心观点，输出一份结构化报告"
          />
        </el-form-item>
        <el-form-item label="报告标题（选填）">
          <el-input v-model="form.title" placeholder="不填则由系统自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitGenerate">提交生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.reports-page {
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

.reports-table {
  width: 100%;
}

.report-link {
  color: #409eff;
  cursor: pointer;
}

.report-link:hover {
  text-decoration: underline;
}

.report-title-plain {
  color: #909399;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
}

.doc-select {
  width: 100%;
}
</style>
