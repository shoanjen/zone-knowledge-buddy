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
  router.push('/assets?tab=reports')
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
    <div class="preview-head">
      <el-button link class="back-link" @click="goBack">← 返回</el-button>
      <h2 class="preview-title">{{ report?.title || '报告预览' }}</h2>
      <span v-if="report && hasHtml" class="hint preview-meta tnum">
        {{ sectionCount }} 章 · {{ formatSize(report.size_bytes) }}
      </span>
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

.preview-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-link {
  flex-shrink: 0;
  color: var(--muted);
}

.back-link:hover {
  color: var(--accent);
}

.preview-title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--fg-strong);
  letter-spacing: 0.01em;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-meta {
  flex-shrink: 0;
  white-space: nowrap;
}

/* ReportViewer 撑满剩余高度（约 calc(100vh - 190px) 区间） */
.preview-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.preview-body > :deep(.report-viewer) {
  flex: 1;
  min-height: 0;
}

.preview-body :deep(.el-empty) {
  margin: auto;
}
</style>
