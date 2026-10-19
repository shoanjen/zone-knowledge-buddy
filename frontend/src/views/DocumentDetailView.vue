<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'
import BlockBrowser from '../components/BlockBrowser.vue'
import StatusBadge from '../components/StatusBadge.vue'
import QualityTag from '../components/QualityTag.vue'

const route = useRoute()
const router = useRouter()
const store = useDocumentsStore()

const TYPE_TAG = {
  pdf: { label: 'PDF', type: 'primary' },
  word: { label: 'Word', type: 'success' },
  md: { label: 'Markdown', type: 'warning' },
  excel: { label: 'Excel', type: 'danger' },
  web: { label: '网页', type: 'info' },
}

const loading = ref(false)
let loadSeq = 0

// store.current 在文档间切换时会被复用：仅当其 id 与路由参数一致时才认作当前文档，
// 加载下一份文档期间不会渲染上一份的残留数据
const docId = computed(() => String(route.params.id ?? ''))
const doc = computed(() =>
  store.current && String(store.current.id) === docId.value ? store.current : null
)
const blocks = computed(() => doc.value?.blocks || [])

function typeMeta(sourceType) {
  return TYPE_TAG[sourceType] || { label: sourceType || '—', type: 'info' }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  if (!docId.value) return
  const seq = ++loadSeq
  loading.value = true
  try {
    await store.fetchDetail(docId.value)
  } catch {
    // 404（文档不存在）等错误由拦截器统一弹出
  } finally {
    // 快速切换文档时，只让最后一次请求控制 loading
    if (seq === loadSeq) loading.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(load)

// /documents/:id 之间跳转会复用组件实例，参数变化时重新拉取
watch(docId, load)
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="topbar">
      <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
      <span class="doc-title">
        {{ doc ? doc.title || doc.origin || doc.id : '文档详情' }}
      </span>
    </div>

    <el-empty v-if="!loading && !doc" description="未能加载文档">
      <el-button type="primary" @click="goBack">返回上页</el-button>
    </el-empty>

    <div v-else-if="!doc" class="loading-block"></div>

    <template v-else>
      <el-card shadow="never" class="meta-card">
        <template #header>
          <span class="card-title">文档信息</span>
        </template>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="标题" :span="2">
            {{ doc.title || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="来源类型">
            <el-tag :type="typeMeta(doc.source_type).type" size="small" effect="plain">
              {{ typeMeta(doc.source_type).label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="来源" :span="2">
            <span class="origin-text">{{ doc.origin || '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusBadge :status="doc.status" />
          </el-descriptions-item>
          <el-descriptions-item label="解析质量">
            <QualityTag
              v-if="doc.parse_quality === 'low'"
              :quality="doc.parse_quality"
              :reason="doc.low_reason"
            />
            <span v-else>{{ doc.parse_quality === 'high' ? '正常' : '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="块数">{{ doc.block_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="切片数">{{ doc.chunk_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="导入时间">
            {{ formatTime(doc.imported_at) }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="doc.status === 'failed' && doc.error"
            label="失败原因"
            :span="3"
          >
            <span class="error-text">{{ doc.error }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-alert
        v-if="doc.blocks_truncated"
        class="truncate-alert"
        type="warning"
        show-icon
        :closable="false"
        title="块数超过 5000 已截断"
      />

      <el-card shadow="never" class="content-card">
        <template #header>
          <span class="card-title">内容预览</span>
        </template>
        <BlockBrowser :blocks="blocks" />
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1000px;
  margin: 0 auto;
  min-height: 240px;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.doc-title {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-title {
  font-weight: 600;
}

.origin-text {
  word-break: break-all;
}

.error-text {
  color: #f56c6c;
  word-break: break-all;
}

.loading-block {
  height: 240px;
}

.content-card :deep(.el-card__body) {
  padding: 20px 28px;
}
</style>
