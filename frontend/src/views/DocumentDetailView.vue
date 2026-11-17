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
  <div v-loading="loading" class="page detail-page">
    <el-empty v-if="!loading && !doc" description="未能加载文档">
      <el-button type="primary" @click="goBack">返回上页</el-button>
    </el-empty>

    <div v-else-if="!doc" class="loading-block"></div>

    <template v-else>
      <el-card class="meta-card">
        <el-button link size="small" class="back-btn" :icon="ArrowLeft" @click="goBack">
          返回
        </el-button>
        <div class="title-row">
          <h1 class="doc-title">{{ doc.title || doc.origin || doc.id }}</h1>
          <StatusBadge :status="doc.status" />
          <QualityTag
            v-if="doc.parse_quality === 'low'"
            :quality="doc.parse_quality"
            :reason="doc.low_reason"
          />
          <el-tag size="small" effect="plain" type="info">
            {{ typeMeta(doc.source_type).label }}
          </el-tag>
        </div>
        <div class="meta-line hint">
          <span class="meta-origin">{{ doc.origin || '—' }}</span>
          <span class="meta-dot">·</span>
          <span class="tnum">{{ formatTime(doc.imported_at) }}</span>
          <span class="meta-dot">·</span>
          <span>块数 <span class="tnum">{{ doc.block_count ?? 0 }}</span></span>
          <span class="meta-dot">·</span>
          <span>切片 <span class="tnum">{{ doc.chunk_count ?? 0 }}</span></span>
        </div>
        <el-alert
          v-if="doc.status === 'failed' && doc.error"
          class="error-alert"
          type="error"
          show-icon
          :closable="false"
          :title="doc.error"
        />
      </el-card>

      <el-alert
        v-if="doc.blocks_truncated"
        class="truncate-alert"
        type="warning"
        show-icon
        :closable="false"
        title="块数超过 5000 已截断"
      />

      <el-card class="content-card">
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
  min-height: 240px;
}

/* 页头卡：返回 + 标题徽标行 + 元信息行 */
.meta-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.back-btn {
  margin: 0 0 10px;
  color: var(--muted);
}

.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.doc-title {
  flex: 1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--fg-strong);
}

.meta-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.meta-origin {
  min-width: 0;
  max-width: 46%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-dot {
  color: var(--faint);
}

.error-alert {
  margin-top: 12px;
}

/* 截断 / 失败提示：紧凑尺寸 */
.truncate-alert,
.error-alert {
  padding: 6px 12px;
}

.truncate-alert :deep(.el-alert__title),
.error-alert :deep(.el-alert__title) {
  font-size: 12.5px;
}

/* 内容卡：全宽承载 BlockBrowser，阅读内边距 */
.content-card :deep(.el-card__body) {
  padding: 24px 28px;
}

.loading-block {
  height: 240px;
}
</style>
