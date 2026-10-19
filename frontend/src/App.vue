<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import CurrentModelBadge from './components/CurrentModelBadge.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLogin = computed(() => route.path === '/login')
const active = computed(() =>
  route.path === '/' ? '/' : `/${route.path.split('/')[1]}`,
)

const menu = [
  { path: '/', label: '工作台' },
  { path: '/documents', label: '文档' },
  { path: '/notes', label: '笔记' },
  { path: '/chat', label: '问答' },
  { path: '/reports', label: '报告' },
  { path: '/tasks', label: '任务' },
  { path: '/settings', label: '设置' },
]

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container v-if="!isLogin" class="layout">
    <el-header class="header">
      <div class="brand">知识伙伴</div>
      <el-menu mode="horizontal" :default-active="active" router class="menu" :ellipsis="false">
        <el-menu-item v-for="m in menu" :key="m.path" :index="m.path">
          {{ m.label }}
        </el-menu-item>
      </el-menu>
      <div class="right">
        <CurrentModelBadge />
        <span class="username">{{ auth.username }}</span>
        <el-button link type="danger" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
  <router-view v-else />
</template>

<style scoped>
.layout {
  height: 100%;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.brand {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
  white-space: nowrap;
}

.menu {
  flex: 1;
  border-bottom: none;
}

.right {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.username {
  color: #606266;
  font-size: 13px;
}

.main {
  padding: 16px 20px;
  overflow-y: auto;
}
</style>
