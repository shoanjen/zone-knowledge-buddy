<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Delete, Expand, Fold, Plus } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import ChatStream from '../components/ChatStream.vue'
import CurrentModelBadge from '../components/CurrentModelBadge.vue'

const store = useChatStore()

// 会话栏折叠状态：记住用户偏好，窄屏默认收起
const RAIL_KEY = 'kb_chat_rail_collapsed'
const railCollapsed = ref(
  localStorage.getItem(RAIL_KEY) === '1' || window.innerWidth < 960,
)

function toggleRail() {
  railCollapsed.value = !railCollapsed.value
  localStorage.setItem(RAIL_KEY, railCollapsed.value ? '1' : '0')
}

// ---- 会话批量管理 ----
const batchMode = ref(false)
const selectedIds = ref([])

function toggleBatch() {
  batchMode.value = !batchMode.value
  selectedIds.value = []
}

function isSelected(id) {
  return selectedIds.value.includes(id)
}

function toggleSelect(id) {
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(id)
}

function selectAll() {
  selectedIds.value = store.sessions.map((s) => s.id)
}

function exitBatch() {
  toggleBatch()
}

async function removeSessions(ids) {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 个会话吗？删除后不可恢复。`,
      '删除会话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  const n = await store.removeSessions(ids).catch(() => 0)
  if (n) {
    ElMessage.success(`已删除 ${n} 个会话`)
    selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
    if (batchMode.value && !store.sessions.length) toggleBatch()
  }
}

function removeOne(session) {
  removeSessions([session.id])
}

onMounted(() => {
  store.loadSessions().catch(() => {})
})

// 离开问答页即中止 SSE，避免后端流继续、返回后发送按钮被 streaming 锁死
onUnmounted(() => store.abort())

function select(id) {
  if (id === store.currentSessionId) return
  store.loadSession(id).catch(() => {})
}

function onSessionClick(s) {
  if (batchMode.value) toggleSelect(s.id)
  else select(s.id)
}

function fmt(dt) {
  if (!dt) return ''
  return String(dt).replace('T', ' ').slice(5, 16)
}
</script>

<template>
  <div class="chat-view" :class="{ 'rail-collapsed': railCollapsed }">
    <!-- 左：会话栏（轻盈无卡片，可折叠） -->
    <aside class="sessions">
      <button type="button" class="new-chat" @click="store.newSession()">
        <el-icon :size="15"><Plus /></el-icon>
        <span>新会话</span>
      </button>

      <div class="rail-head">
        <template v-if="!batchMode">
          <span class="rail-label">历史会话</span>
          <button
            type="button"
            class="rail-act"
            :disabled="!store.sessions.length"
            title="批量管理"
            @click="toggleBatch"
          >
            管理
          </button>
        </template>
        <template v-else>
          <span class="rail-label">已选 {{ selectedIds.length }}</span>
          <span class="rail-head-actions">
            <button type="button" class="rail-act" :disabled="!store.sessions.length" @click="selectAll">
              全选
            </button>
            <button
              type="button"
              class="rail-act danger"
              :disabled="!selectedIds.length"
              @click="removeSessions(selectedIds)"
            >
              删除
            </button>
            <button type="button" class="rail-act" @click="exitBatch">完成</button>
          </span>
        </template>
      </div>

      <div class="session-list">
        <div v-if="!store.sessions.length" class="empty">还没有对话记录</div>
        <button
          v-for="s in store.sessions"
          :key="s.id"
          type="button"
          class="session-item"
          :class="{
            active: !batchMode && s.id === store.currentSessionId,
            selected: batchMode && isSelected(s.id),
          }"
          @click="onSessionClick(s)"
        >
          <span v-if="batchMode" class="check-box" :class="{ on: isSelected(s.id) }" />
          <el-icon v-else :size="14" class="s-icon"><ChatDotRound /></el-icon>
          <span class="s-body">
            <span class="title" :title="s.title">{{ s.title || '未命名会话' }}</span>
            <span class="time">{{ fmt(s.created_at) }}</span>
          </span>
          <span
            v-if="!batchMode"
            class="s-del"
            title="删除会话"
            @click.stop="removeOne(s)"
          >
            <el-icon :size="13"><Delete /></el-icon>
          </span>
        </button>
      </div>
    </aside>

    <!-- 右：对话主区 -->
    <section class="stream-pane">
      <div class="chat-toolbar">
        <button type="button" class="rail-toggle" :title="railCollapsed ? '展开会话栏' : '收起会话栏'" @click="toggleRail">
          <el-icon :size="16">
            <Expand v-if="railCollapsed" />
            <Fold v-else />
          </el-icon>
        </button>
        <span class="toolbar-title">知识伙伴 · 问答</span>
        <CurrentModelBadge class="toolbar-badge" />
      </div>
      <ChatStream />
    </section>
  </div>
</template>

<style scoped>
.chat-view {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  background: var(--bg);
}

/* ---------- 左侧会话栏 ---------- */
.sessions {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 14px 10px 10px 12px;
  border-right: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg) 55%, var(--surface));
  transition: width 0.22s ease, padding 0.22s ease, opacity 0.18s ease;
  overflow: hidden;
}

.rail-collapsed .sessions {
  width: 0;
  padding-left: 0;
  padding-right: 0;
  opacity: 0;
  border-right-color: transparent;
  pointer-events: none;
}

.new-chat {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-radius: 10px;
  background: var(--accent-grad);
  color: #fff;
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--accent-glow);
  transition: box-shadow 0.2s var(--ease-out), transform 0.16s var(--ease-out);
  white-space: nowrap;
}

.new-chat:hover {
  box-shadow: var(--accent-glow-strong);
  transform: translateY(-1px);
}

.new-chat:active {
  transform: scale(0.97);
}

/* 栏头：标题 + 管理/批量操作 */
.rail-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin: 14px 8px 6px;
  white-space: nowrap;
}

.rail-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--faint);
}

.rail-head-actions {
  display: inline-flex;
  gap: 2px;
}

.rail-act {
  border: none;
  background: transparent;
  padding: 2px 5px;
  border-radius: 6px;
  color: var(--muted);
  font-family: inherit;
  font-size: 11.5px;
  cursor: pointer;
  transition: color 0.15s var(--ease-out), background 0.15s var(--ease-out);
}

.rail-act:hover:not(:disabled) {
  color: var(--accent);
  background: var(--accent-soft);
}

.rail-act.danger {
  color: var(--danger);
}

.rail-act.danger:hover:not(:disabled) {
  color: var(--danger);
  background: rgba(194, 84, 80, 0.08);
}

.rail-act:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.empty {
  padding: 18px 10px;
  font-size: 12.5px;
  color: var(--faint);
  text-align: center;
  white-space: nowrap;
}

.session-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 9px;
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s var(--ease-out), transform 0.18s var(--ease-out);
  white-space: nowrap;
}

.session-item:hover {
  background: var(--surface);
  transform: translateX(2px);
}

.session-item.active {
  background: var(--surface);
  box-shadow: inset 2px 0 0 var(--accent);
}

/* 批量选中态 */
.session-item.selected {
  background: var(--accent-soft);
}

.check-box {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--border-strong);
  border-radius: 5px;
  background: var(--surface);
  transition: background 0.15s var(--ease-out), border-color 0.15s var(--ease-out);
}

.check-box.on {
  background: var(--accent);
  border-color: var(--accent);
}

.check-box.on::after {
  content: '';
  width: 4px;
  height: 8px;
  margin-top: -2px;
  border: solid #fff;
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}

.s-icon {
  margin-top: 3px;
  color: var(--faint);
  flex-shrink: 0;
}

.session-item.active .s-icon {
  color: var(--accent);
}

.s-body {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.session-item .title {
  font-size: 13px;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item.active .title {
  color: var(--fg-strong);
  font-weight: 600;
}

.session-item .time {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}

/* 单条删除：悬停浮现 */
.s-del {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--faint);
  opacity: 0;
  transition: opacity 0.15s var(--ease-out), color 0.15s var(--ease-out),
    background 0.15s var(--ease-out);
}

.session-item:hover .s-del {
  opacity: 1;
}

.s-del:hover {
  color: var(--danger);
  background: rgba(194, 84, 80, 0.1);
}

/* ---------- 右侧对话区 ---------- */
.stream-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-toolbar {
  flex-shrink: 0;
  height: 50px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
}

.rail-toggle {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.rail-toggle:hover {
  background: var(--surface-2);
  color: var(--fg);
}

.toolbar-title {
  font-family: var(--font-display);
  font-size: 14.5px;
  font-weight: 600;
  color: var(--fg-strong);
  letter-spacing: 0.02em;
}

.toolbar-badge {
  margin-left: auto;
}

/* 窄屏：会话栏浮层化，不挤压对话区 */
@media (max-width: 960px) {
  .sessions {
    position: absolute;
    z-index: 20;
    top: 0;
    bottom: 0;
    left: 0;
    background: var(--surface);
    box-shadow: var(--shadow-pop);
  }

  .rail-collapsed .sessions {
    box-shadow: none;
  }
}
</style>
