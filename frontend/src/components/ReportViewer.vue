<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { downloadReport, fetchReportHtml } from '../api/reports'

// 规格：报告 HTML 沙箱预览；sandbox 仅 allow-scripts，不加 allow-same-origin
const props = defineProps({
  reportId: { type: [String, Number], required: true },
})

const loading = ref(false)
const loadFailed = ref(false)
const objectUrl = ref('')
let blobUrl = ''

function revokeUrl() {
  if (blobUrl) {
    URL.revokeObjectURL(blobUrl)
    blobUrl = ''
    objectUrl.value = ''
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

onMounted(load)
watch(() => props.reportId, load)
onUnmounted(revokeUrl)
</script>

<template>
  <div v-loading="loading" class="report-viewer">
    <div class="viewer-header">
      <span class="viewer-label">报告内容</span>
      <el-button size="small" type="primary" plain @click="download">下载 HTML</el-button>
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
  min-height: 70vh;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
}

.viewer-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.viewer-body {
  flex: 1;
  display: flex;
  min-height: 70vh;
}

.viewer-frame {
  flex: 1;
  width: 100%;
  min-height: 70vh;
  border: none;
  background: #fff;
}
</style>
