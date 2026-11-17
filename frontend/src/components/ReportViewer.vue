<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { downloadReport, fetchReportHtml } from '../api/reports'

// 规格：报告 HTML 沙箱预览；sandbox 仅 allow-scripts，不加 allow-same-origin
const props = defineProps({
  reportId: { type: [String, Number], required: true },
})

const loading = ref(false)
const loadFailed = ref(false)
const objectUrl = ref('')
const blobSize = ref(0)
let blobUrl = ''

const fileName = computed(() => `${props.reportId}.html`)

function revokeUrl() {
  if (blobUrl) {
    URL.revokeObjectURL(blobUrl)
    blobUrl = ''
    objectUrl.value = ''
    blobSize.value = 0
  }
}

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    const blob = await fetchReportHtml(props.reportId)
    revokeUrl()
    blobUrl = URL.createObjectURL(blob)
    objectUrl.value = blobUrl
    blobSize.value = blob.size
  } catch {
    // 错误提示由 http 拦截器统一弹出
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function download() {
  try {
    const blob = await downloadReport(props.reportId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.reportId}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch {
    // 错误提示由 http 拦截器统一弹出
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

onMounted(load)
watch(() => props.reportId, load)
onUnmounted(revokeUrl)
</script>

<template>
  <div v-loading="loading" class="report-viewer">
    <div class="viewer-toolbar">
      <span class="hint viewer-file">
        {{ fileName }}<template v-if="blobSize"> · {{ formatSize(blobSize) }}</template>
      </span>
      <span class="viewer-actions">
        <el-button size="small" plain @click="download">下载 HTML</el-button>
      </span>
    </div>
    <div class="viewer-body">
      <iframe
        v-if="objectUrl"
        :src="objectUrl"
        sandbox="allow-scripts"
        class="viewer-frame"
        title="报告预览"
      />
      <el-empty v-else-if="loadFailed" description="报告加载失败">
        <el-button size="small" @click="load">重新加载</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.report-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 420px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.viewer-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}

.viewer-file {
  min-width: 0;
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewer-actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}

.viewer-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.viewer-frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
  display: block;
  background: var(--surface);
}

.viewer-body :deep(.el-empty) {
  margin: auto;
}
</style>
