<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="title">知识伙伴</h1>
      <p class="subtitle">基于大模型 Agent 的多格式个人知识管理系统</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="默认 admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="默认 admin123（请尽快修改）"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" class="login-btn" :loading="loading" @click="submit">
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1ff 0%, #f5f7fa 60%);
}

.login-card {
  width: 380px;
  padding: 8px 12px;
}

.title {
  margin: 4px 0 4px;
  font-size: 24px;
  text-align: center;
}

.subtitle {
  margin: 0 0 18px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.login-btn {
  width: 100%;
}
</style>
