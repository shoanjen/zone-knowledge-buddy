<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Headset, MagicStick, Notebook } from '@element-plus/icons-vue'
import { useNotesStore } from '../stores/notes'
import { useReportsStore } from '../stores/reports'
import { usePodcastsStore } from '../stores/podcasts'
import { listDocuments } from '../api/documents'
import { listVoices } from '../api/podcasts'

/**
 * 共享「生成产出」对话框：工作台上传后的下一步引导、文档库行内生成共用。
 *
 * - mode 传 'note' | 'report' 直接进入对应表单；不传则先让用户选类型
 * - presetDocIds 预选文档（通常是刚上传、仍在解析中的），对话框轮询状态，
 *   全部所选文档 ready 之前提交按钮保持禁用，避免后端 400「文档不可用」
 */
const props = defineProps({
  modelValue: Boolean,
  mode: { type: String, default: '' }, // '' | 'note' | 'report'
  presetDocIds: { type: Array, default: () => [] },
  title: { type: String, default: '生成产出' },
})
const emit = defineEmits(['update:modelValue', 'submitted'])

const router = useRouter()
const notesStore = useNotesStore()
const reportsStore = useReportsStore()
const podcastsStore = usePodcastsStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// 产出类型目录：新增类型（如播客）只需在此追加一项，卡片自动排版
const MODES = [
  {
    key: 'note',
    label: '生成笔记',
    icon: Notebook,
    desc: '可溯源的结构化要点，逐条带回溯引用',
    tone: 'note',
  },
  {
    key: 'report',
    label: '生成报告',
    icon: DataAnalysis,
    desc: '自包含 HTML 结构化报告，可下载分享',
    tone: 'report',
  },
  {
    key: 'podcast',
    label: '生成播客',
    icon: Headset,
    desc: '把文档转成可收听的音频节目',
    tone: 'podcast',
  },
]

const chosen = ref('') // '' = 未选类型
const docs = ref([])
const docsLoading = ref(false)
const submitting = ref(false)
const form = reactive({
  intent: '',
  title: '',
  confirmRequired: false,
  style: '轻松闲聊',
  voiceA: 'zh-CN-XiaoxiaoNeural',
  voiceB: 'zh-CN-YunxiNeural',
})

// 播客音色/风格预设（后端 /podcasts/voices 下发；失败时用同款兜底）
const voiceOptions = ref([
  { id: 'zh-CN-XiaoxiaoNeural', label: '晓晓 · 女声 · 温暖' },
  { id: 'zh-CN-XiaoyiNeural', label: '晓伊 · 女声 · 活泼' },
  { id: 'zh-CN-YunjianNeural', label: '云健 · 男声 · 沉稳' },
  { id: 'zh-CN-YunxiNeural', label: '云希 · 男声 · 阳光' },
  { id: 'zh-CN-YunxiaNeural', label: '云夏 · 男声 · 少年' },
])
const styleOptions = ref(['轻松闲聊', '深度讲解', '快讯速览'])
let voicesLoaded = false

async function loadVoicePresets() {
  if (voicesLoaded) return
  try {
    const data = await listVoices()
    if (data?.voices?.length) voiceOptions.value = data.voices
    if (data?.styles?.length) styleOptions.value = data.styles
    voicesLoaded = true
  } catch {
    /* 拦截器已提示，保留兜底预设 */
  }
}

const sameVoice = computed(() => form.voiceA === form.voiceB)
let pollTimer = null

const presetSet = computed(() => new Set(props.presetDocIds))
const selectedIds = ref([])

// 预选文档的状态快照（轮询刷新），用于「等待解析」提示
const selectedDocs = computed(() => docs.value.filter((d) => selectedIds.value.includes(d.id)))
const pendingCount = computed(() => selectedDocs.value.filter((d) => d.status !== 'ready').length)
const readyCount = computed(() => selectedDocs.value.filter((d) => d.status === 'ready').length)
const anyFailed = computed(() => selectedDocs.value.some((d) => d.status === 'failed'))

const canSubmit = computed(() => {
  if (!chosen.value || docsLoading.value || submitting.value) return false
  if (!selectedIds.value.length || pendingCount.value > 0) return false
  if (form.intent.trim().length < 2) return false
  if (chosen.value === 'podcast' && sameVoice.value) return false
  return true
})

async function loadDocs() {
  docsLoading.value = true
  try {
    const data = await listDocuments({ page: 1, page_size: 100 })
    docs.value = data.items || []
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    docsLoading.value = false
  }
}

// 只轮询状态：轻量刷新列表，更新所选文档的解析进度
async function pollStatus() {
  try {
    const data = await listDocuments({ page: 1, page_size: 100 })
    docs.value = data.items || []
    if (pendingCount.value === 0) stopPolling()
  } catch {
    /* 网络抖动忽略，下轮再试 */
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollStatus, 2500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function reset() {
  stopPolling()
  chosen.value = props.mode || ''
  form.intent = ''
  form.title = ''
  form.confirmRequired = false
  form.style = styleOptions.value[0] || '轻松闲聊'
  form.voiceA = 'zh-CN-XiaoxiaoNeural'
  form.voiceB = 'zh-CN-YunxiNeural'
  selectedIds.value = []
}

watch(visible, (open) => {
  if (!open) {
    stopPolling()
    return
  }
  reset()
  if (chosen.value === 'podcast') loadVoicePresets()
  loadDocs().then(() => {
    // 预选：刚上传的文档（可能仍在解析）默认勾上，并轮询等待就绪
    const preset = docs.value.filter((d) => presetSet.value.has(d.id)).map((d) => d.id)
    selectedIds.value = preset.length ? preset : []
    if (pendingCount.value > 0) startPolling()
  })
})

function pick(mode) {
  const target = MODES.find((m) => m.key === mode)
  if (target?.upcoming) {
    ElMessage.info('该类型即将上线，敬请期待')
    return
  }
  chosen.value = mode
  if (mode === 'podcast') loadVoicePresets()
}

function docLabel(d) {
  return d.title || d.origin || d.id
}

const INTENT_LABELS = {
  note: '生成意图',
  report: '报告意图',
  podcast: '播客主题',
}
const INTENT_PLACEHOLDERS = {
  note: '例如：总结所选文档中关于 XX 的核心观点，整理成一份可复习的读书笔记',
  report: '例如：总结所选文档的核心观点，输出一份结构化报告',
  podcast: '例如：用轻松的对谈聊聊这几篇文档的核心内容，面向初次接触的听众',
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    if (chosen.value === 'note') {
      await notesStore.generate({
        doc_ids: selectedIds.value,
        intent: form.intent.trim(),
        confirm_required: form.confirmRequired,
      })
    } else if (chosen.value === 'podcast') {
      await podcastsStore.generate({
        doc_ids: selectedIds.value,
        intent: form.intent.trim(),
        title: form.title.trim() || undefined,
        style: form.style,
        voice_a: form.voiceA,
        voice_b: form.voiceB,
      })
    } else {
      await reportsStore.generate({
        doc_ids: selectedIds.value,
        intent: form.intent.trim(),
        title: form.title.trim() || undefined,
      })
    }
    const label = chosen.value === 'note' ? '笔记' : chosen.value === 'podcast' ? '播客' : '报告'
    ElMessage.success(`已提交${label}生成任务`)
    visible.value = false
    emit('submitted')
    router.push('/tasks')
  } catch {
    // 错误提示由 http 拦截器统一弹出，留在对话框内便于修改后重试
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="600px"
    :close-on-click-modal="false"
    append-to-body
    @closed="stopPolling"
  >
    <!-- 第一步：选产出类型（图形卡） -->
    <div v-if="!chosen" class="mode-pick">
      <div class="mode-hint">想基于所选文档得到什么？</div>
      <div class="mode-cards">
        <button
          v-for="m in MODES"
          :key="m.key"
          type="button"
          class="mode-card"
          :class="[m.tone, { upcoming: m.upcoming }]"
          :disabled="m.upcoming"
          @click="pick(m.key)"
        >
          <span class="m-badge">
            <el-icon :size="22"><component :is="m.icon" /></el-icon>
          </span>
          <span class="m-label">{{ m.label }}</span>
          <span class="m-desc">{{ m.desc }}</span>
          <span v-if="m.upcoming" class="m-soon">即将上线</span>
          <el-icon v-else class="m-go" :size="14"><MagicStick /></el-icon>
        </button>
      </div>
    </div>

    <!-- 第二步：表单 -->
    <el-form v-else label-position="top" @submit.prevent="submit">
      <el-form-item required>
        <template #label>
          <span>选择文档（仅解析就绪的文档可用于生成）</span>
        </template>
        <div v-loading="docsLoading" class="doc-list">
          <el-empty
            v-if="!docsLoading && !docs.length"
            description="知识库中还没有文档，请先在工作台上传"
            :image-size="60"
          />
          <el-checkbox-group v-else v-model="selectedIds">
            <el-checkbox v-for="d in docs" :key="d.id" :value="d.id" class="doc-item">
              <span class="doc-title" :title="docLabel(d)">{{ docLabel(d) }}</span>
              <span class="doc-origin" :title="d.origin">{{ d.origin || d.source_type }}</span>
              <span v-if="presetSet.has(d.id) && d.status !== 'ready'" class="doc-status parsing">
                解析中…
              </span>
              <span v-else-if="d.status === 'failed'" class="doc-status failed">解析失败</span>
            </el-checkbox>
          </el-checkbox-group>
        </div>
        <div v-if="pendingCount > 0" class="waiting-line">
          {{ readyCount }}/{{ selectedDocs.length }} 个所选文档已就绪，正在等待解析完成（自动刷新）…
        </div>
        <div v-else-if="anyFailed" class="waiting-line warn">
          有所选文档解析失败，请先在文档库删除或重试后再生成
        </div>
      </el-form-item>

      <el-form-item required>
        <template #label>
          <span>{{ INTENT_LABELS[chosen] || '生成意图' }}</span>
        </template>
        <el-input
          v-model="form.intent"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          :placeholder="INTENT_PLACEHOLDERS[chosen] || ''"
        />
      </el-form-item>

      <el-form-item v-if="chosen === 'report'" label="报告标题（选填）">
        <el-input v-model="form.title" placeholder="不填则由系统自动生成" />
      </el-form-item>

      <template v-if="chosen === 'podcast'">
        <el-form-item label="节目标题（选填）">
          <el-input v-model="form.title" placeholder="不填则由模型根据内容起名" />
        </el-form-item>
        <el-form-item label="节目风格">
          <el-radio-group v-model="form.style">
            <el-radio-button v-for="s in styleOptions" :key="s" :value="s">{{ s }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="主播音色">
          <div class="voice-row">
            <div class="voice-pick">
              <span class="voice-tag a">A 主讲</span>
              <el-select v-model="form.voiceA" :disabled="submitting">
                <el-option v-for="v in voiceOptions" :key="v.id" :value="v.id" :label="v.label" />
              </el-select>
            </div>
            <div class="voice-pick">
              <span class="voice-tag b">B 搭话</span>
              <el-select v-model="form.voiceB" :disabled="submitting">
                <el-option
                  v-for="v in voiceOptions"
                  :key="v.id"
                  :value="v.id"
                  :label="v.label"
                  :disabled="v.id === form.voiceA"
                />
              </el-select>
            </div>
          </div>
          <div v-if="sameVoice" class="voice-warn">两位主播不能选择同一音色</div>
        </el-form-item>
      </template>

      <el-form-item v-if="chosen === 'note'">
        <div class="confirm-line">
          <el-switch v-model="form.confirmRequired" />
          <span class="confirm-text">需要人工确认草稿（开启后任务暂停，在任务中心确认后落库）</span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <template v-if="chosen">
        <el-button text @click="chosen = ''">上一步</el-button>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
          {{ pendingCount > 0 ? '等待解析…' : '提交生成' }}
        </el-button>
      </template>
      <el-button v-else @click="visible = false">暂不生成</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* ---------- 类型选择（图形卡） ---------- */
.mode-pick {
  padding: 4px 2px 8px;
}

.mode-hint {
  margin-bottom: 14px;
  font-size: 13.5px;
  color: var(--muted);
}

.mode-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.mode-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 18px 16px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  animation: rise-in 0.4s var(--ease-out) both;
  transition: border-color 0.2s var(--ease-out), box-shadow 0.2s var(--ease-out),
    transform 0.2s var(--ease-out);
}

.mode-card:nth-child(2) {
  animation-delay: 0.07s;
}

.mode-card:nth-child(3) {
  animation-delay: 0.14s;
}

.mode-card:hover:not(:disabled) {
  border-color: var(--accent-border);
  transform: translateY(-3px);
  box-shadow: var(--shadow-lift);
}

/* 各类型主色徽章：同一墨绿体系下的可辨识差异 */
.m-badge {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
  margin-bottom: 8px;
  transition: transform 0.25s var(--ease-spring);
}

.mode-card:hover:not(:disabled) .m-badge {
  transform: scale(1.1) rotate(-4deg);
}

.mode-card.note .m-badge {
  background: var(--accent-soft);
  color: var(--accent);
}

.mode-card.report .m-badge {
  background: #f3efe4;
  color: var(--warn);
}

.mode-card.podcast .m-badge {
  background: #efe7f5;
  color: #7c5a9e;
}

.m-label {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--fg-strong);
}

.m-desc {
  font-size: 12px;
  line-height: 1.55;
  color: var(--muted);
}

.m-go {
  position: absolute;
  top: 14px;
  right: 14px;
  color: var(--faint);
  transition: color 0.16s ease, transform 0.16s ease;
}

.mode-card:hover:not(:disabled) .m-go {
  color: var(--accent);
  transform: translateX(2px);
}

/* 未上线：整体弱化 + 角标 */
.mode-card.upcoming {
  cursor: not-allowed;
  border-style: dashed;
  background: var(--surface-2);
}

.mode-card.upcoming .m-badge,
.mode-card.upcoming .m-label,
.mode-card.upcoming .m-desc {
  opacity: 0.55;
}

.m-soon {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  color: var(--muted);
  background: var(--surface);
}

/* ---------- 文档选择 ---------- */
.doc-list {
  width: 100%;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
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
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-origin {
  margin-left: 8px;
  color: var(--muted);
  font-size: 12px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-status {
  margin-left: 8px;
  font-size: 11.5px;
  flex-shrink: 0;
}

.doc-status.parsing {
  color: var(--warn);
}

.doc-status.failed {
  color: var(--danger);
}

.waiting-line {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--warn);
}

.waiting-line.warn {
  color: var(--danger);
}

.confirm-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.confirm-text {
  font-size: 13px;
  color: var(--fg);
}

/* ---------- 播客：风格 + 主播音色 ---------- */
.voice-row {
  display: flex;
  gap: 12px;
  width: 100%;
}

.voice-pick {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.voice-tag {
  font-size: 12px;
  font-weight: 600;
}

.voice-tag.a {
  color: var(--accent);
}

.voice-tag.b {
  color: #7c5a9e;
}

.voice-warn {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--danger);
}
</style>
