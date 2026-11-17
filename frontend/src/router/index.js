import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// 规格§13.1 路由与守卫
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  { path: '/', name: 'workbench', component: () => import('../views/WorkbenchView.vue') },
  { path: '/documents', name: 'documents', component: () => import('../views/DocumentsView.vue') },
  {
    path: '/documents/:id',
    name: 'document-detail',
    component: () => import('../views/DocumentDetailView.vue'),
  },
  { path: '/assets', name: 'assets', component: () => import('../views/AssetsView.vue') },
  // 旧列表入口并入「产出」双 Tab；详情路由保留
  { path: '/notes', redirect: '/assets?tab=notes' },
  { path: '/notes/:id', name: 'note-detail', component: () => import('../views/NoteDetailView.vue') },
  { path: '/chat', name: 'chat', component: () => import('../views/ChatView.vue') },
  { path: '/reports', redirect: '/assets?tab=reports' },
  {
    path: '/reports/:id/preview',
    name: 'report-preview',
    component: () => import('../views/ReportPreviewView.vue'),
  },
  { path: '/tasks', name: 'tasks', component: () => import('../views/TasksView.vue') },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.token) {
    return { path: '/' }
  }
  return true
})

export default router
