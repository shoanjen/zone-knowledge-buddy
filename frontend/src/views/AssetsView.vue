<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useNotesStore } from '../stores/notes'
import { useReportsStore } from '../stores/reports'
import { usePodcastsStore } from '../stores/podcasts'
import PodcastDetailDialog from '../components/PodcastDetailDialog.vue'

/**
 * 产出（资产）页：笔记 / 报告 / 播客三 Tab 的只读资产视图。
 * 生成入口不在这里——统一收敛到「工作台上传后的引导」与「文档库行内生成」。
 */
const route = useRoute()
const router = useRouter()
const notesStore = useNotesStore()
const reportsStore = useReportsStore()
const podcastsStore = usePodcastsStore()

const activeTab = computed({
  get: () => (['reports', 'podcasts'].includes(route.query.tab) ? route.query.tab : 'notes'),
  set: (tab) => router.replace({ query: { ...route.query, tab } }),
})

// 播客详情播放对话框
const podcastDialogVisible = ref(false)
const activePodcastId = ref('')

function playPodcast(row) {
  activePodcastId.value = row.id
  podcastDialogVisible.value = true
}

async function removePodcast(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除播客「${row.title || '无标题'}」吗？音频文件将一并删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await podcastsStore.remove(row.id).catch(() => {})
}

function searchNotes() {
  notesStore.page = 1
  notesStore.fetchList().catch(() => {})
}

function resetNotes() {
  notesStore.keyword = ''
  notesStore.tag = ''
  searchNotes()
}

async function removeNote(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除笔记「${row.title || '无标题'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await notesStore.remove(row.id).catch(() => {})
}

function goNote(id) {
  router.push(`/notes/${id}`)
}

function goReport(row) {
  if (!row.has_html) return
  router.push(`/reports/${row.id}/preview`)
}

function onPageChange() {
  notesStore.fetchList().catch(() => {})
}

function onReportPageChange(page) {
  reportsStore.page = page
  reportsStore.fetchList()
}

function onReportSizeChange(size) {
  reportsStore.pageSize = size
  reportsStore.page = 1
  reportsStore.fetchList()
}

function fmt(dt) {
  if (!dt) return '—'
  return String(dt).replace('T', ' ').slice(0, 16)
}

function fmtReport(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtPodcastDuration(s) {
  if (!s || s <= 0) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

onMounted(() => {
  notesStore.fetchList().catch(() => {})
  reportsStore.fetchList().catch(() => {})
  podcastsStore.fetchList().catch(() => {})
})
</script>

<template>
  <div class="page assets-view">
    <div class="page-head">
      <div>
        <h2 class="page-title">产出</h2>
        <p class="page-sub">你的知识资产 · Agent 生成的可溯源笔记、报告与播客</p>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab" class="asset-tabs">
        <!-- ========== 笔记 ========== -->
        <el-tab-pane name="notes">
          <template #label>
            笔记<span class="tab-count tnum">{{ notesStore.total }}</span>
          </template>

          <div class="filter-bar">
            <el-input
              v-model="notesStore.keyword"
              class="filter-q"
              placeholder="按标题 / 正文关键词搜索"
              clearable
              :prefix-icon="Search"
              @keyup.enter="searchNotes"
              @clear="searchNotes"
            />
            <el-input
              v-model="notesStore.tag"
              class="filter-tag"
              placeholder="按标签过滤"
              clearable
              @keyup.enter="searchNotes"
              @clear="searchNotes"
            />
            <el-button type="primary" :icon="Search" :loading="notesStore.loading" @click="searchNotes">
              搜索
            </el-button>
            <el-button plain @click="resetNotes">重置</el-button>
          </div>

          <el-table v-loading="notesStore.loading" :data="notesStore.list">
            <el-table-column label="标题" min-width="240">
              <template #default="{ row }">
                <el-link :underline="false" class="note-link" @click="goNote(row.id)">
                  {{ row.title || '无标题' }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="180">
              <template #default="{ row }">
                <template v-if="row.tags && row.tags.length">
                  <el-tag
                    v-for="t in row.tags"
                    :key="t"
                    size="small"
                    effect="plain"
                    type="info"
                    class="tag"
                  >
                    {{ t }}
                  </el-tag>
                </template>
                <span v-else class="hint">-</span>
              </template>
            </el-table-column>
            <el-table-column label="来源文档数" width="110" align="center">
              <template #default="{ row }">
                <span class="tnum">{{ (row.source_doc_ids || []).length }}</span>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="170">
              <template #default="{ row }">
                <span class="time-cell tnum">{{ fmt(row.updated_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="removeNote(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无笔记 · 可在工作台上传后生成，或在文档库对某篇文档发起" :image-size="80" />
            </template>
          </el-table>

          <div class="pagination-row">
            <el-pagination
              v-model:current-page="notesStore.page"
              small
              layout="total, prev, pager, next"
              :total="notesStore.total"
              :page-size="notesStore.pageSize"
              @current-change="onPageChange"
            />
          </div>
        </el-tab-pane>

        <!-- ========== 报告 ========== -->
        <el-tab-pane name="reports">
          <template #label>
            报告<span class="tab-count tnum">{{ reportsStore.total }}</span>
          </template>

          <el-table v-loading="reportsStore.loading" :data="reportsStore.list" class="reports-table">
            <el-table-column label="标题" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.has_html" class="report-link" @click="goReport(row)">{{ row.title }}</span>
                <template v-else>
                  <span class="report-title-plain">{{ row.title }}</span>
                  <span class="report-flag">未生成</span>
                </template>
              </template>
            </el-table-column>
            <el-table-column prop="intent" label="意图" min-width="240" show-overflow-tooltip />
            <el-table-column label="HTML" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.has_html ? 'success' : 'info'" size="small" effect="plain">
                  {{ row.has_html ? '已生成' : '未生成' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">
                <span class="time-cell tnum">{{ fmtReport(row.created_at) }}</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无报告 · 可在工作台上传后生成，或在文档库对某篇文档发起" :image-size="80" />
            </template>
          </el-table>

          <div class="pagination-row">
            <el-pagination
              small
              background
              layout="total, sizes, prev, pager, next"
              :total="reportsStore.total"
              :current-page="reportsStore.page"
              :page-size="reportsStore.pageSize"
              :page-sizes="[10, 20, 50]"
              @current-change="onReportPageChange"
              @size-change="onReportSizeChange"
            />
          </div>
        </el-tab-pane>

        <!-- ========== 播客 ========== -->
        <el-tab-pane name="podcasts">
          <template #label>
            播客<span class="tab-count tnum">{{ podcastsStore.total }}</span>
          </template>

          <el-table v-loading="podcastsStore.loading" :data="podcastsStore.list" class="podcasts-table">
            <el-table-column label="标题" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="podcast-link" @click="playPodcast(row)">
                  <span class="play-dot">▶</span>{{ row.title || '未命名播客' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="风格" width="110">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" type="info">{{ row.style }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时长" width="90" align="center">
              <template #default="{ row }">
                <span class="time-cell tnum">{{ fmtPodcastDuration(row.duration_s) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="音频" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.has_audio ? 'success' : 'info'" size="small" effect="plain">
                  {{ row.has_audio ? '可播放' : '缺失' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">
                <span class="time-cell tnum">{{ fmtReport(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :disabled="!row.has_audio" @click="playPodcast(row)">
                  播放
                </el-button>
                <el-button link type="danger" @click="removePodcast(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无播客 · 可在工作台或文档库选择文档后生成「播客」" :image-size="80" />
            </template>
          </el-table>

          <div class="pagination-row">
            <el-pagination
              small
              background
              layout="total, prev, pager, next"
              :total="podcastsStore.total"
              :current-page="podcastsStore.page"
              :page-size="podcastsStore.pageSize"
              @current-change="() => podcastsStore.fetchList()"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <PodcastDetailDialog v-model="podcastDialogVisible" :podcast-id="activePodcastId" />
  </div>
</template>

<style scoped>
.asset-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.tab-count {
  margin-left: 6px;
  font-size: 11.5px;
  color: var(--faint);
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.filter-q {
  width: 220px;
}

.filter-tag {
  width: 140px;
}

.note-link {
  font-weight: 500;
}

.note-link :deep(.el-link__inner) {
  color: var(--fg-strong);
  transition: color 0.15s ease;
}

.note-link:hover :deep(.el-link__inner) {
  color: var(--accent);
}

.tag {
  margin-right: 6px;
}

.time-cell {
  font-size: 12px;
  color: var(--muted);
}

.report-link {
  font-weight: 500;
  color: var(--fg-strong);
  cursor: pointer;
}

.report-link:hover {
  color: var(--accent);
}

.report-title-plain {
  font-weight: 500;
  color: var(--muted);
}

.report-flag {
  margin-left: 6px;
  font-size: 12px;
  color: var(--faint);
}

.podcast-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--fg-strong);
  cursor: pointer;
}

.podcast-link:hover {
  color: var(--accent);
}

.play-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #efe7f5;
  color: #7c5a9e;
  font-size: 10px;
  transition: transform 0.2s ease;
}

.podcast-link:hover .play-dot {
  transform: scale(1.12);
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
