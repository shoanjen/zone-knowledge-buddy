<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  Collection,
  DArrowLeft,
  Files,
  List,
  Monitor,
  Setting,
  SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from './stores/auth'
import CurrentModelBadge from './components/CurrentModelBadge.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ---- 侧栏收起/展开：记住偏好，窄屏自动收起 ----
const NAV_KEY = 'kb_nav_collapsed'
const navCollapsed = ref(
  localStorage.getItem(NAV_KEY) === '1' || window.innerWidth < 960,
)

function toggleNav() {
  navCollapsed.value = !navCollapsed.value
  localStorage.setItem(NAV_KEY, navCollapsed.value ? '1' : '0')
}

function onResize() {
  if (window.innerWidth < 960) navCollapsed.value = true
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const isLogin = computed(() => route.path === '/login')
// 问答页走"助手全屏"布局：无顶栏、内容零内边距，由页面自行管理滚动
const isChat = computed(() => route.path.startsWith('/chat'))
// 未登录时不要挂载应用壳：否则 /login 首次解析前会短暂渲染顶栏并触发 401 请求
const showShell = computed(() => !isLogin.value && !!auth.token)

const menu = [
  { path: '/', label: '工作台', icon: Monitor, tip: '知识工作流概览' },
]
const navGroups = [
  {
    label: '知识库',
    items: [
      { path: '/documents', label: '文档库', icon: Files, tip: '原始资料：导入、解析与向量化' },
      { path: '/chat', label: '问答', icon: ChatDotRound, tip: '向你的知识库提问' },
    ],
  },
  {
    label: '智能产出',
    items: [
      { path: '/assets', label: '产出', icon: Collection, tip: '你的知识资产：笔记与报告' },
      { path: '/tasks', label: '任务中心', icon: List, tip: 'Agent 执行留痕与草稿确认' },
    ],
  },
]

const active = computed(() => {
  if (route.path === '/') return '/'
  const seg = `/${route.path.split('/')[1]}`
  const all = [...menu, ...navGroups.flatMap((g) => g.items), { path: '/settings' }]
  return all.some((m) => m.path === seg) ? seg : route.path
})

const topbarTitle = computed(() => {
  const all = [...menu, ...navGroups.flatMap((g) => g.items), { path: '/settings', label: '设置' }]
  return all.find((m) => m.path === active.value)?.label || ''
})

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <router-view v-if="!showShell" />
  <div v-else class="app-shell">
    <aside class="sidebar" :class="{ collapsed: navCollapsed }">
      <button
        type="button"
        class="nav-toggle"
        :title="navCollapsed ? '展开菜单' : '收起菜单'"
        :aria-label="navCollapsed ? '展开菜单' : '收起菜单'"
        @click="toggleNav"
      >
        <el-icon :size="13" class="toggle-icon" :class="{ flipped: navCollapsed }">
          <DArrowLeft />
        </el-icon>
      </button>

      <router-link to="/" class="brand" title="知识伙伴">
        <span class="brand-mark">知</span>
        <span class="brand-text">
          <span class="brand-name">知识伙伴</span>
          <span class="brand-en">Knowledge Buddy</span>
        </span>
      </router-link>

      <nav class="nav">
        <router-link
          v-for="m in menu"
          :key="m.path"
          :to="m.path"
          class="nav-item"
          :class="{ active: active === m.path }"
          :title="m.tip"
        >
          <el-icon :size="17"><component :is="m.icon" /></el-icon>
          <span class="nav-label">{{ m.label }}</span>
        </router-link>

        <div v-for="g in navGroups" :key="g.label" class="nav-group">
          <div class="nav-group-label">{{ g.label }}</div>
          <router-link
            v-for="m in g.items"
            :key="m.path"
            :to="m.path"
            class="nav-item"
            :class="{ active: active === m.path }"
            :title="m.tip"
          >
            <el-icon :size="17"><component :is="m.icon" /></el-icon>
            <span class="nav-label">{{ m.label }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-foot">
        <router-link to="/settings" class="nav-item foot-link" :class="{ active: active === '/settings' }" title="模型供应商与数据管理">
          <el-icon :size="17"><Setting /></el-icon>
          <span class="nav-label">设置</span>
        </router-link>
        <div class="user-chip">
          <span class="avatar">{{ auth.username.slice(0, 1).toUpperCase() }}</span>
          <span class="user-name">{{ auth.username }}</span>
          <el-button link size="small" class="logout" :icon="SwitchButton" @click="logout">
            退出
          </el-button>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header v-if="!isChat" class="topbar">
        <span class="topbar-title">{{ topbarTitle }}</span>
        <CurrentModelBadge />
      </header>
      <main class="content" :class="{ bare: isChat }">
        <router-view v-slot="{ Component }">
          <transition name="route" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100%;
}

/* ---------- 侧边栏（与内容区同系的浅暖纸面，墨绿只做强调） ---------- */
.sidebar {
  position: relative;
  width: 216px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-strong);
  transition: width 0.3s var(--ease-out);
}

.sidebar.collapsed {
  width: 64px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 14px 14px;
  border-bottom: 1px solid var(--border);
  position: relative;
}

/* 品牌区底部渐变细线 */
.brand::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(15, 118, 110, 0.55), rgba(15, 118, 110, 0));
  opacity: 0.8;
  transition: left 0.3s var(--ease-out), right 0.3s var(--ease-out), opacity 0.3s;
}

.sidebar.collapsed .brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar.collapsed .brand::after {
  left: 10px;
  right: 10px;
  opacity: 0.45;
}

/* 品牌方块标识 */
.brand-mark {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #12897f 0%, #0b5f58 100%);
  color: #fff;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 3px 10px rgba(15, 118, 110, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  white-space: nowrap;
  transition: opacity 0.2s var(--ease-out);
}

.sidebar.collapsed .brand-text {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--fg-strong);
  letter-spacing: 0.04em;
  line-height: 1.25;
}

.brand-en {
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
  line-height: 1.2;
}

/* 收起/展开按钮：骑缝在侧栏右缘的悬浮圆钮 */
.nav-toggle {
  position: absolute;
  top: 20px;
  right: -13px;
  z-index: 30;
  width: 26px;
  height: 26px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  box-shadow: var(--shadow-lift);
  transition: color 0.18s var(--ease-out), border-color 0.18s var(--ease-out),
    background 0.18s var(--ease-out), transform 0.18s var(--ease-out);
}

.nav-toggle:hover {
  color: var(--accent);
  border-color: var(--accent-border);
  transform: scale(1.1);
}

.nav-toggle:active {
  transform: scale(0.94);
}

/* 图标随收起/展开翻转，替代两个图标硬切换 */
.toggle-icon {
  transition: transform 0.3s var(--ease-out);
}

.toggle-icon.flipped {
  transform: rotate(180deg);
}

.nav {
  flex: 1;
  padding: 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

/* 分组：知识库 / 智能产出 */
.nav-group {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-group-label {
  padding: 0 12px 5px;
  font-size: 10.5px;
  letter-spacing: 0.14em;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
  transition: opacity 0.18s var(--ease-out), height 0.3s var(--ease-out);
}

/* 收起态：分组标题淡出为细分隔线 */
.sidebar.collapsed .nav-group-label {
  opacity: 0;
  height: 0;
  padding-bottom: 0;
  overflow: hidden;
}

.sidebar.collapsed .nav-group {
  margin-top: 8px;
  position: relative;
}

.sidebar.collapsed .nav-group::before {
  content: '';
  position: absolute;
  top: -4px;
  left: 16px;
  right: 16px;
  height: 1px;
  background: var(--border-strong);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: var(--fg);
  font-size: 13.5px;
  white-space: nowrap;
  transition: background 0.18s var(--ease-out), color 0.18s var(--ease-out),
    transform 0.18s var(--ease-out), padding 0.3s var(--ease-out);
}

.nav-item:hover {
  background: rgba(15, 118, 110, 0.07);
  color: var(--fg-strong);
  transform: translateX(2px);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-weight: 600;
  box-shadow: inset 2.5px 0 0 var(--accent);
}

.nav-item.active :deep(.el-icon) {
  color: var(--accent);
}

/* 收起态：图标居中、文字淡出 */
.nav-label {
  transition: opacity 0.18s var(--ease-out);
}

.sidebar.collapsed .nav-label {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px 0;
}

.sidebar.collapsed .nav-item:hover {
  transform: none;
}

/* 导航入场：随侧栏级联浮现 */
.nav-item,
.nav-group-label {
  animation: rise-in 0.45s var(--ease-out) both;
}

.nav-group {
  animation: rise-in 0.45s var(--ease-out) both;
}

.sidebar-foot {
  padding: 8px 10px 12px 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.foot-link {
  padding: 8px 12px;
  white-space: nowrap;
}

.sidebar.collapsed .foot-link {
  justify-content: center;
  padding: 8px 0;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 2px 12px 0;
  white-space: nowrap;
}

.user-chip .logout {
  margin-left: auto;
}

.sidebar.collapsed .user-chip {
  justify-content: center;
  padding: 4px 0 0;
}

.avatar {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #12897f 0%, #0b5f58 100%);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
}

.user-name {
  font-size: 13px;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: opacity 0.18s var(--ease-out);
}

.sidebar.collapsed .user-name,
.sidebar.collapsed .user-chip .logout {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.logout {
  color: var(--muted);
  flex-shrink: 0;
}

.logout:hover {
  color: var(--danger);
}

/* ---------- 主区 ---------- */
.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.topbar {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: color-mix(in srgb, var(--bg) 72%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}

.topbar-title {
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--muted);
  text-transform: uppercase;
  font-weight: 500;
}

.content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px 26px 32px;
}

/* 问答页：助手式全屏，页面自管布局与滚动 */
.content.bare {
  padding: 0;
  overflow: hidden;
}

/* 窄屏兜底：resize 监听已自动置 collapsed，这里只保证极端情况下不出横向滚动 */
@media (max-width: 960px) {
  .sidebar {
    width: 64px;
  }
}
</style>
