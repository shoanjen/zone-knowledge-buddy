<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document,
  Files,
  Grid,
  Link,
  MagicStick,
  Menu,
  Notebook,
  RefreshRight,
  Search,
  Tickets,
  Delete as DeleteIcon,
  Upload,
} from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'
import GenerateDialog from '../components/GenerateDialog.vue'
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

// 类型徽章：图标 + 专属色（用于标题单元格，降低表格信息噪音）
const TYPE_ICON = {
  pdf: { icon: Document, cls: 'pdf' },
  word: { icon: Notebook, cls: 'word' },
  md: { icon: Files, cls: 'md' },
  excel: { icon: Tickets, cls: 'excel' },
  web: { icon: Link, cls: 'web' },
}

function iconMeta(sourceType) {
  return TYPE_ICON[sourceType] || { icon: Files, cls: 'md' }
}

// ---- 视图模式：卡片书架（默认）/ 列表，偏好持久化 ----
const VIEW_KEY = 'kb_docs_view'
const viewMode = ref(localStorage.getItem(VIEW_KEY) === 'list' ? 'list' : 'card')

function setView(mode) {
  viewMode.value = mode
  localStorage.setItem(VIEW_KEY, mode)
}

// 分段筛选的彩色圆点：与类型徽章同色系
const TYPE_DOT = {
  '': 'accent',
  pdf: 'pdf',
  word: 'word',
  md: 'md',
  excel: 'excel',
  web: 'web',
}

function pickType(v) {
  filterType.value = v
  applyFilter()
}

function staggerCls(i) {
  return `stagger-${(i % 8) + 1}`
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

// 重置：清空本地筛选值后复用 applyFilter 写回 store 并回第一页
function resetFilter() {
  filterType.value = ''
  keyword.value = ''
  applyFilter()
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

// ---- 行内生成：就绪文档可发起产出任务（笔记/报告/未来播客，对话框内选类型） ----
const genVisible = ref(false)
const genPreset = ref([])

function openGenerate(row) {
  genPreset.value = [row.id]
  genVisible.value = true
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
  <div class="page documents-page">
    <div class="page-head docs-head">
      <div class="head-text">
        <h2 class="page-title">文档库</h2>
        <p class="page-sub">你的原始资料 · 导入后自动解析、切片与向量化</p>
      </div>
      <el-button type="primary" :icon="Upload" class="upload-btn" @click="router.push('/')">
        上传资料
      </el-button>
    </div>

    <el-card class="list-card">
      <!-- 筛选条：彩色圆点分段器 + 搜索 + 视图切换 -->
      <div class="filter-bar">
        <div class="type-pills">
          <button
            v-for="t in SOURCE_TYPE_OPTIONS"
            :key="t.value"
            type="button"
            class="type-pill"
            :class="{ active: filterType === t.value }"
            @click="pickType(t.value)"
          >
            <span class="pill-dot" :class="TYPE_DOT[t.value] || 'accent'" />
            {{ t.label }}
          </button>
        </div>

        <el-input
          v-model="keyword"
          class="keyword-input"
          placeholder="搜索标题 / 来源"
          clearable
          :prefix-icon="Search"
          @keyup.enter="applyFilter"
          @clear="applyFilter"
        />

        <div class="filter-right">
          <span class="total-hint tnum">共 {{ store.total }} 篇</span>
          <div class="view-toggle" title="切换视图">
            <button
              type="button"
              class="vt-btn"
              :class="{ on: viewMode === 'card' }"
              title="卡片视图"
              @click="setView('card')"
            >
              <el-icon :size="14"><Grid /></el-icon>
            </button>
            <button
              type="button"
              class="vt-btn"
              :class="{ on: viewMode === 'list' }"
              title="列表视图"
              @click="setView('list')"
            >
              <el-icon :size="14"><Menu /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <!-- 卡片书架视图 -->
      <div v-if="viewMode === 'card'" v-loading="store.loading" class="doc-grid">
        <template v-if="store.list.length">
          <div
            v-for="(row, i) in store.list"
            :key="row.id"
            class="doc-card rise-in"
            :class="staggerCls(i)"
            @click="goDetail(row)"
          >
            <div class="dc-top">
              <span class="type-badge" :class="iconMeta(row.source_type).cls">
                <el-icon :size="16"><component :is="iconMeta(row.source_type).icon" /></el-icon>
              </span>
              <div class="dc-status">
                <StatusBadge :status="row.status" />
                <QualityTag :quality="row.parse_quality" :reason="row.low_reason" />
              </div>
            </div>
            <div class="dc-title" :title="docTitle(row)">{{ docTitle(row) }}</div>
            <div class="dc-origin" :title="row.origin">
              {{ typeMeta(row.source_type).label }}<template v-if="row.origin"> · {{ row.origin }}</template>
            </div>
            <div class="dc-stats tnum">
              <span>{{ row.block_count ?? 0 }} 块 · {{ row.chunk_count ?? 0 }} 切片</span>
              <span class="dc-time">{{ formatTime(row.imported_at) }}</span>
            </div>
            <div class="dc-actions" @click.stop>
              <button
                v-if="row.status === 'ready'"
                type="button"
                class="dc-act primary"
                title="选择产出类型：笔记 / 报告"
                @click="openGenerate(row)"
              >
                <el-icon :size="13"><MagicStick /></el-icon>生成
              </button>
              <button
                v-if="row.status === 'failed'"
                type="button"
                class="dc-act"
                @click="onRetry(row)"
              >
                <el-icon :size="13"><RefreshRight /></el-icon>重试
              </button>
              <button type="button" class="dc-act danger" @click="onDelete(row)">
                <el-icon :size="13"><DeleteIcon /></el-icon>删除
              </button>
            </div>
          </div>
          <!-- 书架空位：上传引导占位卡 -->
          <button type="button" class="doc-card upload-slot rise-in" :class="staggerCls(store.list.length)" @click="router.push('/')">
            <span class="slot-icon">
              <el-icon :size="20"><Upload /></el-icon>
            </span>
            <span class="slot-title">上传新资料</span>
            <span class="slot-desc">PDF · Word · Markdown · Excel · 网页</span>
          </button>
        </template>
        <el-empty
          v-else-if="!store.loading"
          class="grid-empty"
          description="书架空空 · 到工作台上传资料，解析后会陈列在这里"
          :image-size="88"
        />
      </div>

      <!-- 列表视图（紧凑表格） -->
      <el-table v-else v-loading="store.loading" :data="store.list" class="docs-table">
        <el-table-column label="文档" min-width="320">
          <template #default="{ row }">
            <div class="doc-cell" @click="goDetail(row)">
              <span class="type-badge" :class="iconMeta(row.source_type).cls">
                <el-icon :size="15"><component :is="iconMeta(row.source_type).icon" /></el-icon>
              </span>
              <span class="doc-meta">
                <span class="doc-link" :title="docTitle(row)">{{ docTitle(row) }}</span>
                <span class="doc-origin-s">
                  {{ typeMeta(row.source_type).label }}<template v-if="row.origin"> · {{ row.origin }}</template>
                </span>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150" align="center">
          <template #default="{ row }">
            <div class="status-cell">
              <StatusBadge :status="row.status" />
              <QualityTag :quality="row.parse_quality" :reason="row.low_reason" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="内容规模" width="130" align="center">
          <template #default="{ row }">
            <span class="scale-cell tnum" :title="`内容块 ${row.block_count ?? 0} · 检索切片 ${row.chunk_count ?? 0}`">
              {{ row.block_count ?? 0 }} 块 · {{ row.chunk_count ?? 0 }} 切片
            </span>
          </template>
        </el-table-column>
        <el-table-column label="导入时间" width="170">
          <template #default="{ row }">
            <span class="cell-time tnum">{{ formatTime(row.imported_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'ready'"
              link
              type="primary"
              size="small"
              title="选择产出类型：笔记 / 报告"
              @click="openGenerate(row)"
            >
              生成
            </el-button>
            <el-button v-if="row.status === 'failed'" link size="small" @click="onRetry(row)">
              重试
            </el-button>
            <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无文档 · 到工作台上传资料后，这里会显示解析结果" :image-size="72" />
        </template>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="store.page"
          v-model:page-size="store.pageSize"
          :total="store.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          size="small"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <GenerateDialog
      v-model="genVisible"
      :preset-doc-ids="genPreset"
      title="从这篇文档生成"
    />
  </div>
</template>

<style scoped>
/* 页头：左侧标题，右侧轻量上传跳转 */
.docs-head {
  align-items: center;
  flex-wrap: wrap;
}

.head-text {
  min-width: 0;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

/* ---------- 分段筛选器：彩色圆点胶囊 ---------- */
.type-pills {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 13px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.18s var(--ease-out), color 0.18s var(--ease-out),
    transform 0.18s var(--ease-out), box-shadow 0.18s var(--ease-out);
}

.type-pill:hover {
  color: var(--fg-strong);
  transform: translateY(-1px);
}

.type-pill.active {
  background: var(--surface);
  color: var(--fg-strong);
  font-weight: 600;
  box-shadow: var(--shadow-card);
}

.pill-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pill-dot.accent { background: var(--accent); }
.pill-dot.pdf { background: var(--danger); }
.pill-dot.word { background: var(--success); }
.pill-dot.md { background: var(--warn); }
.pill-dot.excel { background: var(--accent); }
.pill-dot.web { background: #7c5a9e; }

.keyword-input {
  width: 220px;
}

.filter-right {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.total-hint {
  font-size: 12.5px;
  color: var(--faint);
}

/* ---------- 视图切换 ---------- */
.view-toggle {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface-2);
}

.vt-btn {
  width: 30px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.18s var(--ease-out), color 0.18s var(--ease-out);
}

.vt-btn:hover {
  color: var(--fg-strong);
}

.vt-btn.on {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-card);
}

/* ---------- 卡片书架 ---------- */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 14px;
  min-height: 160px;
}

.grid-empty {
  grid-column: 1 / -1;
}

.doc-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 16px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  overflow: hidden;
  transition: border-color 0.22s var(--ease-out), box-shadow 0.22s var(--ease-out),
    transform 0.22s var(--ease-out);
}

/* 悬停墨绿描边 + 顶部渐变饰线 */
.doc-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2.5px;
  background: var(--accent-grad);
  opacity: 0;
  transition: opacity 0.22s var(--ease-out);
}

.doc-card:hover {
  transform: translateY(-3px);
  border-color: var(--accent-border);
  box-shadow: var(--shadow-float);
}

.doc-card:hover::before {
  opacity: 0.85;
}

.dc-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.dc-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* 解析中/执行中的卡片状态：呼吸提醒 */
.doc-card :deep(.el-tag--warning) {
  animation: pulse-soft 2s ease-in-out infinite;
}

@keyframes pulse-soft {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

.dc-title {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--fg-strong);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.18s var(--ease-out);
}

.doc-card:hover .dc-title {
  color: var(--accent);
}

.dc-origin {
  font-size: 11.5px;
  color: var(--faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dc-stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 2px;
  padding-top: 9px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
  color: var(--muted);
}

.dc-time {
  font-size: 11px;
  color: var(--faint);
}

/* 卡片操作行：常驻但轻量，悬停时强化 */
.dc-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

/* ---------- 上传占位卡：补齐书架空位 ---------- */
.upload-slot {
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-style: dashed;
  border-color: var(--border-strong);
  background: transparent;
  color: var(--muted);
  font-family: inherit;
  min-height: 178px;
}

.upload-slot::before {
  display: none;
}

.upload-slot:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  transform: translateY(-3px);
  box-shadow: none;
}

.slot-icon {
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--accent);
  transition: transform 0.22s var(--ease-spring);
}

.upload-slot:hover .slot-icon {
  transform: scale(1.1) rotate(-4deg);
}

.slot-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--fg);
}

.slot-desc {
  font-size: 11px;
  color: var(--faint);
}

.dc-act {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.18s var(--ease-out);
}

.dc-act:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent);
  transform: translateY(-1px);
}

.dc-act.primary {
  border-color: transparent;
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 2px 8px rgba(15, 118, 110, 0.24);
}

.dc-act.primary:hover {
  box-shadow: var(--accent-glow-strong);
  color: #fff;
}

.dc-act.danger:hover {
  border-color: rgba(194, 84, 80, 0.4);
  background: rgba(194, 84, 80, 0.08);
  color: var(--danger);
}

/* 上传按钮辉光 */
.upload-btn {
  border-radius: 999px;
  padding: 10px 22px;
}

/* ---------- 文档单元格：类型徽章 + 标题/来源双行 ---------- */
.doc-cell {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 4px 0;
  cursor: pointer;
}

.type-badge {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  transition: transform 0.2s var(--ease-spring);
}

.doc-cell:hover .type-badge {
  transform: scale(1.1) rotate(-4deg);
}

/* 各来源类型专属色（柔底 + 深字） */
.type-badge.pdf {
  background: rgba(194, 84, 80, 0.12);
  color: var(--danger);
}

.type-badge.word {
  background: rgba(61, 139, 95, 0.14);
  color: var(--success);
}

.type-badge.md {
  background: rgba(184, 134, 11, 0.13);
  color: var(--warn);
}

.type-badge.excel {
  background: var(--accent-soft);
  color: var(--accent);
}

.type-badge.web {
  background: rgba(124, 90, 158, 0.13);
  color: #7c5a9e;
}

.doc-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.doc-link {
  font-weight: 500;
  color: var(--fg);
  cursor: pointer;
  transition: color 0.15s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-link:hover {
  color: var(--accent);
}

.doc-origin-s {
  font-size: 11.5px;
  color: var(--faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 状态 + 质量并排 */
.status-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* 内容规模 */
.scale-cell {
  font-size: 12.5px;
  color: var(--muted);
}

.cell-time {
  font-size: 12px;
  color: var(--muted);
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
