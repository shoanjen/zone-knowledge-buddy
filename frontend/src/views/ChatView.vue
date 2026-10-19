<script setup>
import { onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import ChatStream from '../components/ChatStream.vue'

const store = useChatStore()

onMounted(() => {
  store.loadSessions().catch(() => {})
})

function select(id) {
  if (id === store.currentSessionId) return
  store.loadSession(id).catch(() => {})
}

function fmt(dt) {
  if (!dt) return ''
  return String(dt).replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <div class="chat-view">
    <aside class="sessions">
      <div class="sessions-head">
        <span class="label">历史会话</span>
        <el-button size="small" type="primary" plain :icon="Plus" @click="store.newSession()">
          新会话
        </el-button>
      </div>
      <div class="session-list">
        <div v-if="!store.sessions.length" class="empty">暂无历史会话</div>
        <div
          v-for="s in store.sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === store.currentSessionId }"
          @click="select(s.id)"
        >
          <div class="title" :title="s.title">{{ s.title || '未命名会话' }}</div>
          <div class="time">{{ fmt(s.created_at) }}</div>
        </div>
      </div>
    </aside>
    <section class="stream-pane">
      <ChatStream />
    </section>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.sessions {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.sessions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #ebeef5;
}

.sessions-head .label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.empty {
  padding: 24px 0;
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
}

.session-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #ecf5ff;
}

.session-item .title {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item.active .title {
  color: #409eff;
  font-weight: 600;
}

.session-item .time {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}

.stream-pane {
  flex: 1;
  min-width: 0;
  display: flex;
}
</style>
