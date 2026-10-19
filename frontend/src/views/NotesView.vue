<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useNotesStore } from '../stores/notes'
import { listDocuments } from '../api/documents'

const router = useRouter()
const store = useNotesStore()

// ---- 筛选与分页 ----
function search() {
  store.page = 1
  store.fetchList().catch(() => {})
}

function onPageChange() {
  store.fetchList().catch(() => {})
}

function fmt(dt) {
  if (!dt) return ''
  return String(dt).replace('T', ' ').slice(0, 16)
}

function goDetail(id) {
  router.push(`/notes/${id}`)
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除笔记「${row.title || '无标题'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await store.remove(row.id).catch(() => {})
}

// ---- 生成笔记对话框 ----
const dialog = ref(false)
const docsLoading = ref(false)
const submitting = ref(false)
const readyDocs = ref([])
const genForm = reactive({ docIds: [], intent: '', confirmRequired: false })

// 进入对话框时拉一次文档列表，只列就绪文档
async function loadReadyDocs() {
  docsLoading.value = true
  try {
    const data = await listDocuments({ page_size: 100 })
    readyDocs.value = (data.items || []).filter((d) => d.status === 'ready')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    docsLoading.value = false
  }
}

function openGenerate() {
  dialog.value = true
}

function resetGenerate() {
  genForm.docIds = []
  genForm.intent = ''
  genForm.confirmRequired = false
}

async function submitGenerate() {
  if (!genForm.docIds.length) {
    ElMessage.warning('请至少选择一个就绪文档')
    return
  }
  const intent = genForm.intent.trim()
  if (intent.length < 2) {
    ElMessage.warning('请填写生成意图（至少 2 个字）')
    return
  }
  submitting.value = true
  try {
    await store.generate({
      doc_ids: genForm.docIds,
      intent,
      confirm_required: genForm.confirmRequired,
    })
    ElMessage.success('已提交生成任务')
    dialog.value = false
    router.push('/tasks')
  } catch {
    // 错误提示由 http 拦截器统一弹出，留在对话框内便于修改后重试
  } finally {
    submitting.value = false
  }
}

onMounted(() => store.fetchList().catch(() => {}))
</script>

<template>
  <div class="notes-view">
    <div class="page-head">
      <h2 class="page-title">笔记</h2>
      <el-button type="primary" :icon="Plus" @click="openGenerate">生成笔记</el-button>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="store.keyword"
        class="filter-input"
        placeholder="按标题 / 正文关键词搜索"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-input
        v-model="store.tag"
        class="filter-input"
        placeholder="按标签过滤"
        clearable
        @keyup.enter="search"
        @clear="search"
      />
      <el-button type="primary" plain @click="search">查询</el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="store.loading" :data="store.list">
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row.id)">
              {{ row.title || '无标题' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <template v-if="row.tags && row.tags.length">
              <el-tag v-for="t in row.tags" :key="t" size="small" class="tag">{{ t }}</el-tag>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="来源文档数" width="110" align="center">
          <template #default="{ row }">{{ (row.source_doc_ids || []).length }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ fmt(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无笔记，点击右上角「生成笔记」创建" :image-size="80" />
        </template>
      </el-table>
      <div class="pagination-row">
        <el-pagination
          v-model:current-page="store.page"
          layout="total, prev, pager, next"
          :total="store.total"
          :page-size="store.pageSize"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialog"
      title="生成笔记"
      width="560px"
      @open="loadReadyDocs"
      @closed="resetGenerate"
    >
      <el-form label-position="top" @submit.prevent="submitGenerate">
        <el-form-item required>
          <template #label>
            <span>选择文档（仅显示解析就绪的文档）</span>
          </template>
          <div v-loading="docsLoading" class="doc-list">
            <el-empty
              v-if="!docsLoading && !readyDocs.length"
              description="暂无就绪文档，请先在「文档」页上传并解析"
              :image-size="60"
            />
            <el-checkbox-group v-else v-model="genForm.docIds">
              <el-checkbox v-for="d in readyDocs" :key="d.id" :value="d.id" class="doc-item">
                <span class="doc-title" :title="d.title">{{ d.title || d.id }}</span>
                <span class="doc-origin" :title="d.origin">{{ d.origin || d.source_type }}</span>
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item required>
          <template #label>
            <span>生成意图</span>
          </template>
          <el-input
            v-model="genForm.intent"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="例如：总结所选文档中关于 XX 的核心观点，整理成一份可复习的读书笔记"
          />
        </el-form-item>
        <el-form-item>
          <div class="confirm-line">
            <el-switch v-model="genForm.confirmRequired" />
            <span class="confirm-text">需要人工确认草稿（开启后任务暂停，等待你在任务中心确认草稿再落库）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitGenerate">
          提交生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.notes-view {
  max-width: 1100px;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.filter-input {
  width: 240px;
}

.table-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
}

.tag {
  margin-right: 6px;
}

.muted {
  color: #c0c4cc;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.doc-list {
  width: 100%;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 12px;
}

.doc-item {
  display: flex;
  width: 100%;
  height: auto;
  margin-right: 0;
  padding: 4px 0;
}

.doc-title {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-origin {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.confirm-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.confirm-text {
  font-size: 13px;
  color: #606266;
}
</style>
