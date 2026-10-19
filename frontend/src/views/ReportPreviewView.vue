<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useReportsStore } from '../stores/reports'
import ReportViewer from '../components/ReportViewer.vue'

const route = useRoute()
const router = useRouter()
const store = useReportsStore()

const loading = ref(false)
const loadFailed = ref(false)

const report = computed(() => store.current)

// 规格：无 html 时 getReport 可能不带 sections，此时提示「报告 HTML 未生成」
const hasHtml = computed(() => {
  const r = report.value
  if (!r) return false
  if (typeof r.has_html === 'boolean') return r.has_html
  return Array.isArray(r.sections) && r.sections.length > 0
})

const sectionCount = computed(() => report.value?.sections?.length ?? 0)

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    await store.fetchDetail(route.params.id)
  } catch {
    // 错误提示由 http 拦截器统一弹出
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

function formatSize(bytes) {
  if (bytes === null || bytes === undefined) return '—'
  const n = Number(bytes)
  if (Number.isNaN(n) || n < 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

function goBack() {
  router.push('/reports')
}

onMounted(load)
watch(
  () => route.params.id,
  (id) => {
    if (id) load()
  },
)
</script>

<template>
  <div class="report-preview-page">
    <div class="preview-header">
      <el-button @click="goBack">返回</el-button>
      <div class="preview-meta">
        <h2 class="preview-title">{{ report?.title || '报告预览' }}</h2>
        <template v-if="report && hasHtml">
          <el-divider direction="vertical" />
          <span class="meta-item">章节 {{ sectionCount }}</span>
          <span class="meta-item">大小 {{ formatSize(report.size_bytes) }}</span>
        </template>
      </div>
    </div>

    <div v-loading="loading" class="preview-body">
      <template v-if="report">
        <ReportViewer v-if="hasHtml" :report-id="route.params.id" />
        <el-empty v-else description="报告 HTML 未生成" />
      </template>
      <el-empty v-else-if="loadFailed" description="报告加载失败">
        <el-button size="small" @click="load">重新加载</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.report-preview-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.preview-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.preview-title {
  margin: 0;
  font-size: 18px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-item {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
}

.preview-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.preview-body > :deep(.report-viewer) {
  flex: 1;
}
</style>
