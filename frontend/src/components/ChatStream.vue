<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ChatDotRound, Promotion, WarningFilled } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import { renderMarkdownWithCitations } from '../composables/useMarkdown'
import CitationPop from './CitationPop.vue'

const store = useChatStore()

const NO_BASIS_TEXT = '知识库中未找到依据。'

const inputRef = ref(null)
const scrollRef = ref(null)
const alertVisible = ref(true)

// ---- markdown 渲染（按内容缓存，避免流式期间重复解析旧消息） ----
const mdCache = new Map()

function rendered(msg) {
  const key = String(msg.content || '')
  if (!mdCache.has(key)) {
    if (mdCache.size > 80) mdCache.clear()
    mdCache.set(key, renderMarkdownWithCitations(key))
  }
  return mdCache.get(key).html
}

function citesOf(msg) {
  const key = String(msg.content || '')
  if (!mdCache.has(key)) rendered(msg)
  return mdCache.get(key).cites
}

// ---- 引用弹层：markdown 内 chip 的事件委托 + 单实例虚拟锚点弹层 ----
const citeAnchor = ref(null)
const activeCitation = ref(null)
const popVisible = ref(false)

function onBodyClick(e, msg) {
  const ref = e.target.closest?.('.cite-ref')
  if (!ref) return
  e.stopPropagation()
  const c = citesOf(msg)[Number(ref.dataset.cite)]
  if (!c) return
  if (popVisible.value && citeAnchor.value === ref) {
    popVisible.value = false
    return
  }
  citeAnchor.value = ref
  activeCitation.value = citationOf(msg, c.doc_id, c.block_id)
  popVisible.value = true
}

function onDocClickCapture(e) {
  if (e.target.closest?.('.cite-ref') || e.target.closest?.('.el-popover')) return
  popVisible.value = false
}

onMounted(() => document.addEventListener('click', onDocClickCapture, true))
onUnmounted(() => document.removeEventListener('click', onDocClickCapture, true))

// 空态示例问题：点击直接填入输入框
const exampleQuestions = ['这几份文档的核心结论是什么？', '文档中有哪些关键数据或风险提示？']

// 底部小字：模型供应商 + 本轮召回块数
const providerLabel = computed(() => {
  const p = store.provider
  if (!p) return '默认模型'
  if (p.name && p.model) return `${p.name} / ${p.model}`
  return p.name || p.model || '默认模型'
})

// citation 片段 → 消息 citations 里按 doc_id:block_id 匹配；匹配不到给骨架
function citationOf(msg, docId, blockId) {
  const key = `${docId}:${blockId}`
  return (
    msg.citations.find((c) => `${c.doc_id}:${c.block_id}` === key) || {
      doc_id: docId,
      block_id: blockId,
    }
  )
}

// 该条是否为流式中的最后一条 assistant 消息
function isStreamingTail(msg) {
  return (
    store.streaming && msg.role === 'assistant' && store.messages[store.messages.length - 1] === msg
  )
}

// ---- 回答阶段提示：检索中 / 思考中（流式开始后由内容+光标接管） ----
const PHASE_TEXT = {
  retrieving: '正在检索知识库…',
  thinking: '正在思考…',
}

const phaseText = computed(() => PHASE_TEXT[store.phase] || '')

function isPhaseHint(msg) {
  return (
    store.streaming &&
    store.phase !== 'streaming' &&
    msg.role === 'assistant' &&
    store.messages[store.messages.length - 1] === msg
  )
}

// 失败态：最后一条 assistant 为空且流已结束、有错误 → 气泡内错误提示
function isErrorTail(msg) {
  return (
    !store.streaming &&
    !!store.error &&
    msg.role === 'assistant' &&
    !msg.content &&
    store.messages[store.messages.length - 1] === msg
  )
}

// 重试：重新发送最后一条用户提问
function retryLast() {
  if (store.streaming) return
  const lastUser = [...store.messages].reverse().find((m) => m.role === 'user')
  if (!lastUser) return
  store.error = null
  store.send(lastUser.content)
}

// 无依据回答：整条弱化
function isDimmed(msg) {
  return msg.role === 'assistant' && String(msg.content || '').trim() === NO_BASIS_TEXT
}

const errorText = computed(() => store.error?.message || '问答失败，请重试')

watch(
  () => store.error,
  () => {
    alertVisible.value = true
  },
)

// 新会话重置后聚焦输入框（sessionSeq 每次新会话自增）
watch(
  () => store.sessionSeq,
  () => inputRef.value?.focus(),
)

// 自动滚到底部：关注消息条数与最后一条内容（流式逐 token 触发）
watch(
  () => [store.messages.length, store.messages[store.messages.length - 1]?.content],
  () => scrollToBottom(),
  { flush: 'post' },
)

function scrollToBottom() {
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(scrollToBottom)

// 回车发送、Shift+回车换行；中文输入法组合中不发送
function onEnter(e) {
  if (e.shiftKey || e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  send()
}

async function send() {
  const text = store.draft.trim()
  if (!text || store.streaming) return
  store.draft = ''
  await store.send(text)
}

function stop() {
  store.abort()
}
</script>

<template>
  <div class="chat-stream">
    <!-- 消息区 -->
    <div ref="scrollRef" class="messages">
      <!-- 错误条：浮于消息区顶部居中 -->
      <div v-if="store.error && alertVisible" class="error-float">
        <el-alert type="error" :title="errorText" show-icon closable @close="alertVisible = false" />
      </div>

      <!-- 空会话欢迎态 -->
      <div v-if="!store.messages.length" class="welcome">
        <div class="welcome-mark">
          <el-icon :size="26"><ChatDotRound /></el-icon>
        </div>
        <h1 class="welcome-title">你好，我是知识伙伴</h1>
        <p class="welcome-sub">基于你的知识库回答问题，每个结论都附引用、可回溯原文</p>
        <div class="examples">
          <button
            v-for="q in exampleQuestions"
            :key="q"
            type="button"
            class="example-chip"
            @click="store.draft = q"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <!-- 消息列 -->
      <div v-else class="message-col">
        <div
          v-for="(msg, idx) in store.messages"
          :key="msg.id || `${msg.role}-${idx}`"
          class="msg-row"
          :class="msg.role"
        >
          <div v-if="msg.role === 'assistant'" class="ai-badge">AI</div>
          <div class="msg-body" :class="{ dim: isDimmed(msg) }">
            <template v-if="msg.role === 'assistant'">
              <!-- 检索/思考阶段：内容尚未产生，显示阶段提示 -->
              <div v-if="isPhaseHint(msg)" class="phase-hint">
                <span class="phase-dots"><i /><i /><i /></span>
                <span class="phase-text">{{ phaseText }}</span>
              </div>
              <!-- 失败：气泡内显式错误态 + 重试，避免留下永久空泡 -->
              <div v-else-if="isErrorTail(msg)" class="phase-hint error-hint">
                <el-icon :size="14"><WarningFilled /></el-icon>
                <span class="phase-text">回答失败：{{ store.error?.message || '请稍后重试' }}</span>
                <button type="button" class="retry-btn" @click="retryLast">重试</button>
              </div>
              <!-- markdown 渲染；引用 chip 点击冒泡到容器统一处理 -->
              <div
                v-else
                class="md-body"
                @click="onBodyClick($event, msg)"
                v-html="rendered(msg)"
              />
              <span v-if="isStreamingTail(msg) && store.phase === 'streaming'" class="cursor" />
            </template>
            <template v-else>{{ msg.content }}</template>
          </div>
        </div>
      </div>
    </div>

    <!-- markdown 内联引用弹层（单实例，锚定被点 chip） -->
    <el-popover
      :virtual-ref="citeAnchor"
      virtual-triggering
      :visible="popVisible"
      placement="top"
      :width="340"
    >
      <CitationPop v-if="activeCitation" :citation="activeCitation" />
    </el-popover>

    <!-- 底部输入区 -->
    <div class="composer-zone">
      <div class="composer" :class="{ streaming: store.streaming }">
        <el-input
          ref="inputRef"
          v-model="store.draft"
          type="textarea"
          class="composer-input"
          :autosize="{ minRows: 2, maxRows: 6 }"
          resize="none"
          placeholder="向知识库提问…"
          @keydown.enter="onEnter"
        />
        <div class="composer-foot">
          <span class="hint">回车发送 · Shift+回车换行</span>
          <div class="composer-actions">
            <el-button v-if="store.streaming" plain type="danger" size="small" @click="stop">
              停止
            </el-button>
            <button
              type="button"
              class="send-btn"
              :disabled="store.streaming || !store.draft.trim()"
              @click="send"
            >
              <el-icon :size="15"><Promotion /></el-icon>
              <span>发送</span>
            </button>
          </div>
        </div>
      </div>
      <div class="meta-line">
        模型 {{ providerLabel }} · 本轮检索 {{ store.retrieved.length }} 条 · 回答仅依据知识库内容生成
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-stream {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* ---------- 消息区 ---------- */
.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 20px 18px;
  display: flex;
  flex-direction: column;
  scroll-behavior: smooth;
}

/* 错误条：浮于顶部居中，不占布局 */
.error-float {
  position: sticky;
  top: 6px;
  z-index: 5;
  width: min(560px, 86%);
  margin: 0 auto 14px;
}

.error-float :deep(.el-alert) {
  border-radius: 10px;
  box-shadow: var(--shadow-pop);
}

/* 空会话欢迎态 */
.welcome {
  margin: auto;
  padding: 20px 0 36px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}

.welcome-mark {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: var(--accent-grad);
  color: #fff;
  box-shadow: var(--accent-glow);
  margin-bottom: 12px;
  animation: float-y 3.2s ease-in-out infinite;
}

.welcome-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 27px;
  font-weight: 700;
  color: var(--fg-strong);
  letter-spacing: 0.02em;
  animation: rise-in 0.55s var(--ease-out) 0.08s both;
}

.welcome-sub {
  margin: 2px 0 0;
  font-size: 13.5px;
  color: var(--muted);
  animation: rise-in 0.55s var(--ease-out) 0.16s both;
}

.examples {
  margin-top: 26px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  animation: rise-in 0.55s var(--ease-out) 0.24s both;
}

.example-chip {
  padding: 9px 18px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--fg);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  box-shadow: var(--shadow-card);
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.example-chip:hover {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  transform: translateY(-1px);
}

/* 消息列：限宽居中 */
.message-col {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-top: 10px;
}

/* 新消息入场：淡入 + 轻微上移 */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  animation: rise-in 0.38s var(--ease-out) both;
}

.msg-body {
  font-size: 14.5px;
  line-height: 1.75;
  word-break: break-word;
}

/* ---------- markdown 正文排版 ---------- */
.md-body :deep(p) {
  margin: 0 0 10px;
}

.md-body :deep(p:last-child) {
  margin-bottom: 0;
}

.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 20px 0 8px;
  font-family: var(--font-display);
  font-weight: 700;
  color: var(--fg-strong);
  line-height: 1.4;
}

.md-body :deep(h1) {
  font-size: 19px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.md-body :deep(h2) {
  font-size: 17px;
}

.md-body :deep(h3) {
  font-size: 15px;
}

.md-body :deep(h1:first-child),
.md-body :deep(h2:first-child),
.md-body :deep(h3:first-child) {
  margin-top: 0;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}

.md-body :deep(li) {
  margin: 3px 0;
}

.md-body :deep(li > p) {
  margin: 0;
}

.md-body :deep(blockquote) {
  margin: 10px 0;
  padding: 2px 14px;
  border-left: 3px solid var(--accent-border);
  color: var(--muted);
}

.md-body :deep(blockquote p) {
  margin: 6px 0;
}

/* 表格：限宽可横向滚动，风格与全站一致 */
.md-body :deep(table) {
  display: block;
  width: max-content;
  max-width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
  overflow-x: auto;
}

.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--border);
  padding: 7px 14px;
  font-size: 13px;
  text-align: left;
}

.md-body :deep(th) {
  background: var(--surface-2);
  font-weight: 600;
  color: var(--fg-strong);
  white-space: nowrap;
}

.md-body :deep(code) {
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 12.5px;
}

.md-body :deep(pre) {
  margin: 10px 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  overflow-x: auto;
}

.md-body :deep(pre code) {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--fg);
}

.md-body :deep(hr) {
  margin: 16px 0;
  border: none;
  border-top: 1px dashed var(--border);
}

.md-body :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* markdown 内联引用 chip：与 CitationPopover 同款式 */
.md-body :deep(.cite-ref) {
  display: inline-block;
  position: relative;
  top: -1px;
  margin: 0 2px;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--fg);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 16px;
  cursor: pointer;
  user-select: none;
  vertical-align: baseline;
  white-space: nowrap;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.md-body :deep(.cite-ref:hover) {
  border-color: var(--accent-border);
  color: var(--accent);
}

/* user：右侧软色气泡 */
.msg-row.user {
  justify-content: flex-end;
}

.msg-row.user .msg-body {
  max-width: 76%;
  padding: 11px 15px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  border-top-right-radius: 5px;
  box-shadow: var(--shadow-card);
  white-space: pre-wrap;
}

/* assistant：无气泡，纸面阅读感 */
.ai-badge {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--accent-grad);
  color: #fff;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  user-select: none;
  box-shadow: 0 2px 8px rgba(15, 118, 110, 0.22);
}

.msg-row.assistant .msg-body {
  flex: 1;
  min-width: 0;
}

/* 拒答话术整条弱化 */
.msg-body.dim {
  color: var(--muted);
  font-style: italic;
}

/* 流式光标 */
.cursor {
  display: inline-block;
  width: 1.5px;
  height: 1.05em;
  margin-left: 3px;
  background: var(--fg-strong);
  vertical-align: text-bottom;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

/* ---------- 回答阶段提示：跳动圆点 + 阶段文案 ---------- */
.phase-hint {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  animation: fade-in 0.3s var(--ease-out) both;
}

.phase-dots {
  display: inline-flex;
  gap: 4px;
}

.phase-dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.phase-dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.phase-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dot-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

.phase-text {
  font-size: 13px;
  color: var(--muted);
}

/* 失败态变体：暖色警示 + 重试按钮 */
.error-hint {
  border-color: color-mix(in srgb, var(--warn) 35%, var(--border));
  background: color-mix(in srgb, var(--warn) 7%, var(--surface));
}

.error-hint .phase-text {
  color: var(--warn);
}

.retry-btn {
  padding: 3px 12px;
  border: 1px solid var(--warn);
  border-radius: 999px;
  background: transparent;
  color: var(--warn);
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s var(--ease-out), color 0.15s var(--ease-out),
    transform 0.15s var(--ease-out);
}

.retry-btn:hover {
  background: var(--warn);
  color: #fff;
  transform: translateY(-1px);
}

/* ---------- 底部输入区 ---------- */
.composer-zone {
  flex-shrink: 0;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  padding: 0 20px 8px;
}

.composer {
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  padding: 10px 12px 8px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.composer:focus-within {
  border-color: var(--accent-border);
  box-shadow: 0 2px 6px rgba(30, 30, 25, 0.05), 0 0 0 3px var(--accent-soft);
}

/* 流式生成中：边框轻微提示 */
.composer.streaming {
  border-color: color-mix(in srgb, var(--warn) 45%, var(--border-strong));
}

/* 无边框 textarea */
.composer-input :deep(.el-textarea__inner) {
  padding: 4px 4px 6px;
  font-size: 14.5px;
  line-height: 1.6;
  background: transparent;
  box-shadow: none !important;
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  border: none;
  border-radius: 999px;
  background: var(--accent-grad);
  color: #fff;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--accent-glow);
  transition: box-shadow 0.2s var(--ease-out), opacity 0.2s var(--ease-out),
    transform 0.16s var(--ease-out);
}

.send-btn:hover:not(:disabled) {
  box-shadow: var(--accent-glow-strong);
  transform: translateY(-1px);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

/* 输入区下方状态小字 */
.meta-line {
  margin-top: 9px;
  text-align: center;
  font-size: 11.5px;
  color: var(--faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
