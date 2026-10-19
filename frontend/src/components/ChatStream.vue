<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Promotion, VideoPause } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import { splitByCitations } from '../composables/useCitation'
import CitationPopover from './CitationPopover.vue'

const store = useChatStore()

const NO_BASIS_TEXT = '知识库中未找到依据。'

const draft = ref('')
const scrollRef = ref(null)
const alertVisible = ref(true)

// 顶部小条：模型供应商 + 本轮召回块数
const providerLabel = computed(() => {
  const p = store.provider
  if (!p) return '默认模型'
  if (p.name && p.model) return `${p.name} / ${p.model}`
  return p.name || p.model || '默认模型'
})

// 正文片段：text / citation 交替
function fragmentsOf(msg) {
  return splitByCitations(msg.content)
}

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
  const text = draft.value.trim()
  if (!text || store.streaming) return
  draft.value = ''
  await store.send(text)
}

function stop() {
  store.abort()
}
</script>

<template>
  <div class="chat-stream">
    <div class="stream-top">
      <span class="provider" :title="providerLabel">模型：{{ providerLabel }}</span>
      <span class="retrieved">召回 {{ store.retrieved.length }} 块</span>
    </div>

    <div ref="scrollRef" class="messages">
      <div v-if="!store.messages.length" class="empty-hint">
        向知识库提问，回答中的引用标记可点击查看原文
      </div>
      <div
        v-for="(msg, idx) in store.messages"
        :key="msg.id || `${msg.role}-${idx}`"
        class="msg-row"
        :class="msg.role"
      >
        <div class="bubble" :class="{ dim: isDimmed(msg) }">
          <template v-if="msg.role === 'assistant'">
            <template v-for="(frag, fi) in fragmentsOf(msg)" :key="fi">
              <span v-if="frag.type === 'text'" class="text">{{ frag.text }}</span>
              <CitationPopover
                v-else
                :citation="citationOf(msg, frag.docId, frag.blockId)"
              />
            </template>
            <span v-if="isStreamingTail(msg)" class="cursor" />
          </template>
          <template v-else>{{ msg.content }}</template>
        </div>
      </div>
    </div>

    <div class="composer">
      <el-alert
        v-if="store.error && alertVisible"
        class="error-bar"
        type="error"
        :title="errorText"
        show-icon
        closable
        @close="alertVisible = false"
      />
      <div class="input-row">
        <el-input
          v-model="draft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          resize="none"
          placeholder="输入问题，回车发送，Shift+回车换行"
          @keydown.enter="onEnter"
        />
        <div class="actions">
          <el-button
            type="primary"
            :icon="Promotion"
            :loading="store.streaming"
            :disabled="store.streaming"
            @click="send"
          >
            发送
          </el-button>
          <el-button :icon="VideoPause" :disabled="!store.streaming" @click="stop">
            停止
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-stream {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.stream-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
  color: #909399;
  font-size: 12px;
}

.messages {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-hint {
  margin: auto;
  color: #c0c4cc;
  font-size: 13px;
}

.msg-row {
  display: flex;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 76%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.msg-row.user .bubble {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
  white-space: pre-wrap;
}

.msg-row.assistant .bubble {
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #303133;
  border-top-left-radius: 4px;
}

.msg-row.assistant .bubble .text {
  white-space: pre-wrap;
}

/* 无依据回答整体弱化 */
.bubble.dim {
  color: #909399;
  font-style: italic;
  background: #fafafa;
}

/* 打字光标 */
.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  background: #409eff;
  vertical-align: text-bottom;
  animation: blink-cursor 1s steps(2, start) infinite;
}

@keyframes blink-cursor {
  to {
    visibility: hidden;
  }
}

.composer {
  border-top: 1px solid #ebeef5;
  padding: 12px 14px;
}

.error-bar {
  margin-bottom: 10px;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.input-row .el-input {
  flex: 1;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.actions .el-button {
  margin-left: 0;
}
</style>
