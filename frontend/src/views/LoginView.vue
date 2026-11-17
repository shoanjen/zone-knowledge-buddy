<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, DataAnalysis, Files, Lock, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名与密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.push(String(route.query.redirect || '/'))
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    loading.value = false
  }
}

const FEATURES = [
  { icon: Files, title: '多格式沉淀', desc: 'PDF · Word · Markdown · Excel · 网页，一站式解析入库' },
  { icon: ChatDotRound, title: '可溯源问答', desc: '回答只依据你的知识库生成，每个结论可回溯原文' },
  { icon: DataAnalysis, title: 'Agent 产出', desc: '笔记与报告自动生成，过程留痕、随时查看' },
]
</script>

<template>
  <div class="login-page">
    <!-- 氛围光 -->
    <div class="orb orb-a" />
    <div class="orb orb-b" />
    <div class="orb orb-c" />

    <div class="login-wrap">
      <!-- 左：品牌叙事 -->
      <div class="brand-panel rise-in">
        <div class="brand-row">
          <span class="brand-mark">知</span>
          <div class="brand-name-wrap">
            <span class="brand-name">知识伙伴</span>
            <span class="brand-en">KNOWLEDGE BUDDY</span>
          </div>
        </div>
        <h1 class="slogan">让每一条知识，<br />都有来处。</h1>
        <p class="slogan-sub">基于大模型 Agent 的多格式个人知识管理系统</p>
        <ul class="features">
          <li v-for="(f, i) in FEATURES" :key="f.title" class="feature rise-in" :style="{ animationDelay: 0.15 + i * 0.1 + 's' }">
            <span class="f-icon">
              <el-icon :size="15"><component :is="f.icon" /></el-icon>
            </span>
            <span class="f-body">
              <span class="f-title">{{ f.title }}</span>
              <span class="f-desc">{{ f.desc }}</span>
            </span>
          </li>
        </ul>
      </div>

      <!-- 右：登录卡片 -->
      <div class="login-card pop-in stagger-2">
        <h2 class="card-title">欢迎回来</h2>
        <p class="card-sub">登录以继续你的知识工作</p>
        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="默认 admin" :prefix-icon="User" size="large" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="默认 admin123（请尽快修改）"
              :prefix-icon="Lock"
              size="large"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button type="primary" class="login-btn" size="large" :loading="loading" @click="submit">
            进入知识库
          </el-button>
        </el-form>
        <p class="card-hint">默认账号 admin · 初始密码 admin123</p>
      </div>
    </div>

    <p class="footer-note fade-in stagger-4">知识伙伴 · 个人知识管理 · 引用可溯源</p>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background:
    radial-gradient(1100px 520px at 12% -8%, rgba(15, 118, 110, 0.07), transparent 62%),
    radial-gradient(900px 480px at 100% 0%, rgba(184, 134, 11, 0.055), transparent 58%),
    radial-gradient(1200px 800px at 50% 115%, rgba(15, 118, 110, 0.045), transparent 65%),
    var(--bg);
}

/* 漂浮氛围光球 */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  pointer-events: none;
}

.orb-a {
  width: 380px;
  height: 380px;
  left: 6%;
  top: 8%;
  background: radial-gradient(circle, rgba(15, 118, 110, 0.16), transparent 68%);
  animation: drift-a 22s ease-in-out infinite alternate;
}

.orb-b {
  width: 300px;
  height: 300px;
  right: 8%;
  bottom: 10%;
  background: radial-gradient(circle, rgba(184, 134, 11, 0.12), transparent 68%);
  animation: drift-b 26s ease-in-out infinite alternate;
}

.orb-c {
  width: 220px;
  height: 220px;
  right: 22%;
  top: 12%;
  background: radial-gradient(circle, rgba(15, 118, 110, 0.1), transparent 68%);
  animation: drift-a 30s ease-in-out infinite alternate-reverse;
}

@keyframes drift-a {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(50px, 34px) scale(1.12);
  }
}

@keyframes drift-b {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(-44px, -30px) scale(1.15);
  }
}

/* ---------- 布局 ---------- */
.login-wrap {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 72px;
  padding: 24px;
}

/* ---------- 品牌叙事面板 ---------- */
.brand-panel {
  max-width: 400px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 30px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, #2f9e8f 0%, #147a6e 100%);
  color: #fff;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  box-shadow: var(--accent-glow);
}

.brand-name {
  display: block;
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 700;
  color: var(--fg-strong);
  letter-spacing: 0.05em;
  line-height: 1.3;
}

.brand-en {
  font-size: 10px;
  letter-spacing: 0.22em;
  color: var(--faint);
}

.slogan {
  margin: 0;
  font-family: var(--font-display);
  font-size: 38px;
  font-weight: 700;
  line-height: 1.42;
  color: var(--fg-strong);
  letter-spacing: 0.03em;
}

.slogan-sub {
  margin: 14px 0 0;
  font-size: 14px;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.features {
  list-style: none;
  margin: 38px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feature {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.f-icon {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--accent);
  box-shadow: var(--shadow-card);
}

.f-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.f-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--fg-strong);
}

.f-desc {
  font-size: 12.5px;
  color: var(--muted);
}

/* ---------- 登录卡片 ---------- */
.login-card {
  width: 360px;
  padding: 34px 32px 26px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--surface) 82%, transparent);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: var(--shadow-pop-premium);
}

.card-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--fg-strong);
}

.card-sub {
  margin: 5px 0 20px;
  font-size: 13px;
  color: var(--muted);
}

.login-btn {
  width: 100%;
  margin-top: 4px;
  border-radius: 12px;
  letter-spacing: 0.12em;
}

.card-hint {
  margin: 14px 0 0;
  text-align: center;
  font-size: 11.5px;
  color: var(--faint);
}

.footer-note {
  position: absolute;
  bottom: 18px;
  z-index: 1;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--faint);
}

/* ---------- 响应式：窄屏隐藏品牌面板 ---------- */
@media (max-width: 860px) {
  .brand-panel {
    display: none;
  }

  .login-card {
    width: min(400px, calc(100vw - 40px));
  }
}
</style>
