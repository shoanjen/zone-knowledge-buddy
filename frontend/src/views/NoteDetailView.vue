<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, EditPen } from '@element-plus/icons-vue'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useNotesStore } from '../stores/notes'
import CitationPopover from '../components/CitationPopover.vue'

const route = useRoute()
const router = useRouter()
const store = useNotesStore()

const loading = ref(false)
const deleting = ref(false)
const saving = ref(false)
const editing = ref(false)

// 编辑态本地副本
const form = ref({ title: '', contentMd: '', tags: [] })
const tagInputVisible = ref(false)
const tagValue = ref('')
const tagInputRef = ref(null)

// 当前路由对应的笔记（防止切换时短暂展示旧数据）
const note = computed(() =>
  store.current && store.current.id === route.params.id ? store.current : null,
)
const citations = computed(() => note.value?.citations || [])

// 精简工具栏
const editorToolbars = [
  'bold',
  'underline',
  'italic',
  '-',
  'title',
  'strikeThrough',
  'quote',
  'unorderedList',
  'orderedList',
  'task',
  '-',
  'codeRow',
  'code',
  'link',
  'table',
  '-',
  'revoke',
  'next',
  '-',
  'preview',
  'pageFullscreen',
]

async function load() {
  loading.value = true
  try {
    await store.fetchDetail(route.params.id)
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(
  () => route.params.id,
  () => {
    if (route.name === 'note-detail') {
      editing.value = false
      load()
    }
  },
)

function fmt(dt) {
  if (!dt) return ''
  return String(dt).replace('T', ' ').slice(0, 16)
}

function back() {
  router.push('/assets?tab=notes')
}

// ---- 编辑 / 保存 ----
function startEdit() {
  form.value = {
    title: note.value?.title || '',
    contentMd: note.value?.content_md || '',
    tags: [...(note.value?.tags || [])],
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function save() {
  const title = form.value.title.trim()
  if (!title) {
    ElMessage.warning('标题不能为空')
    return
  }
  saving.value = true
  try {
    await store.update(route.params.id, {
      title,
      content_md: form.value.contentMd,
      tags: form.value.tags,
    })
    ElMessage.success('已保存')
    editing.value = false
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    saving.value = false
  }
}

// ---- 动态标签编辑 ----
function removeTag(index) {
  form.value.tags.splice(index, 1)
}

async function showTagInput() {
  tagInputVisible.value = true
  await nextTick()
  tagInputRef.value?.focus()
}

function confirmTag() {
  const v = tagValue.value.trim()
  if (v && !form.value.tags.includes(v)) form.value.tags.push(v)
  tagInputVisible.value = false
  tagValue.value = ''
}

// ---- 删除 ----
async function removeNote() {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确定删除该笔记吗？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await store.remove(route.params.id)
    router.push('/assets?tab=notes')
  } catch {
    deleting.value = false
  }
}

// 笔记引用（后端 block_text/claim_text）→ popover 数据（text）
function toPopoverCitation(c) {
  return {
    doc_id: c.doc_id,
    block_id: c.block_id,
    text: c.block_text ?? c.text,
    origin: c.origin,
    title: c.title,
    broken: !!c.broken,
  }
}
</script>

<template>
  <div v-loading="loading" class="page note-detail">
    <template v-if="note">
      <div class="detail-top">
        <el-button link :icon="ArrowLeft" class="back-btn" @click="back">返回列表</el-button>
        <span class="hint tnum">更新于 {{ fmt(note.updated_at) }}</span>
      </div>

      <div class="page-head detail-head">
        <div class="head-main">
          <h2 v-if="!editing" class="page-title detail-title">{{ note.title || '无标题' }}</h2>
          <el-input
            v-else
            v-model="form.title"
            class="title-input"
            maxlength="256"
            show-word-limit
            placeholder="笔记标题"
          />
          <div v-if="!editing" class="tags">
            <template v-if="note.tags && note.tags.length">
              <el-tag v-for="t in note.tags" :key="t" size="small" effect="plain" type="info">
                {{ t }}
              </el-tag>
            </template>
            <span v-else class="hint">暂无标签</span>
          </div>
          <div v-else class="tags">
            <el-tag
              v-for="(t, i) in form.tags"
              :key="t"
              size="small"
              effect="plain"
              type="info"
              closable
              @close="removeTag(i)"
            >
              {{ t }}
            </el-tag>
            <el-input
              v-if="tagInputVisible"
              ref="tagInputRef"
              v-model="tagValue"
              class="tag-input"
              size="small"
              placeholder="标签名"
              @keyup.enter="confirmTag"
              @blur="confirmTag"
            />
            <el-button v-else size="small" plain @click="showTagInput">+ 添加标签</el-button>
          </div>
        </div>

        <div class="head-actions">
          <template v-if="editing">
            <el-button @click="cancelEdit">取消</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </template>
          <template v-else>
            <el-button type="primary" plain :icon="EditPen" @click="startEdit">编辑</el-button>
            <el-button link type="danger" :loading="deleting" @click="removeNote">删除</el-button>
          </template>
        </div>
      </div>

      <!-- 正文：只读预览 / 编辑器 -->
      <div v-if="editing" class="content-card is-editing">
        <MdEditor
          v-model="form.contentMd"
          :toolbars="editorToolbars"
          :style="{ height: '480px' }"
          placeholder="支持 Markdown；插入引用标记 [d_xxx:bN] 可关联来源块"
        />
      </div>
      <div v-else class="content-card">
        <MdPreview :model-value="note.content_md" />
        <div v-if="!note.content_md" class="hint empty-content">正文为空，点击「编辑」开始撰写</div>
      </div>

      <!-- 引用区 -->
      <div class="citations-card">
        <div class="card-head citation-head">
          <span>引用 <span class="tnum count">{{ citations.length }}</span></span>
        </div>
        <div v-if="!citations.length" class="hint no-cite">正文暂无引用标记</div>
        <div v-else class="citation-list">
          <div
            v-for="c in citations"
            :key="`${c.doc_id}:${c.block_id}`"
            class="citation-item"
          >
            <CitationPopover :citation="toPopoverCitation(c)" />
            <span class="claim" :title="c.claim_text || ''">{{ c.claim_text }}</span>
            <el-tag v-if="c.broken" type="danger" effect="plain" size="small" class="broken-tag">
              已失效
            </el-tag>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="笔记不存在或已被删除">
      <el-button type="primary" @click="back">返回列表</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.note-detail {
  max-width: 960px;
  min-height: 240px;
}

/* ---------- 面包屑行 ---------- */
.detail-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.back-btn {
  color: var(--muted);
}

.back-btn:hover {
  color: var(--accent);
}

/* ---------- 页头 ---------- */
.detail-head {
  align-items: flex-start;
  margin-bottom: 16px;
}

.head-main {
  flex: 1;
  min-width: 0;
}

.detail-title {
  margin: 0;
  font-size: 19px;
  word-break: break-word;
}

.title-input {
  max-width: 560px;
}

.tags {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 24px;
}

.tag-input {
  width: 140px;
}

.head-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.head-actions .el-button + .el-button {
  margin-left: 0;
}

/* ---------- 正文卡片 ---------- */
.content-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  padding: 20px 26px;
}

.content-card.is-editing {
  padding: 12px;
}

.content-card.is-editing :deep(.md-editor) {
  border-radius: var(--radius-sm);
}

.content-card :deep(.md-editor-preview) {
  font-size: 14px;
  color: var(--fg);
}

.empty-content {
  padding: 8px 0;
}

/* ---------- 引用区卡片 ---------- */
.citations-card {
  margin-top: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  padding: 16px 20px;
}

.citation-head {
  font-size: 13px;
}

.count {
  color: var(--muted);
  font-weight: 600;
}

.no-cite {
  margin-top: 10px;
}

.citation-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.citation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.claim {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.broken-tag {
  flex-shrink: 0;
}
</style>
