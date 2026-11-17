<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSettingsStore } from '../stores/settings'

const store = useSettingsStore()

const GROUPS = [
  { type: 'cloud', label: '云端' },
  { type: 'local-ollama', label: '本地 Ollama' },
  { type: 'local-lmstudio', label: '本地 LM Studio' },
]

const groups = computed(() =>
  GROUPS.map((g) => ({ ...g, providers: store.providers.filter((p) => p.type === g.type) })),
)

const testingId = ref(null)
const activatingId = ref(null)
const deletingId = ref(null)

async function handleTest(p) {
  testingId.value = p.id
  try {
    const result = await store.testProvider(p.id) // 失败也是 200，靠 ok 字段区分
    if (result.ok) {
      ElMessage.success(
        `连接正常，延迟 ${result.latency_ms}ms，模型 ${result.models?.length ?? 0} 个`,
      )
    } else {
      ElMessage.error(result.error || '连接失败')
    }
  } catch {
    // 网络层错误由 http 拦截器统一提示
  } finally {
    testingId.value = null
  }
}

async function handleActivate(p) {
  if (p.type === 'cloud') {
    try {
      await ElMessageBox.confirm('切换后你的内容将发送到该云端服务，是否继续？', '切换确认', {
        type: 'warning',
        confirmButtonText: '继续',
        cancelButtonText: '取消',
      })
    } catch {
      return // 用户取消
    }
  }
  activatingId.value = p.id
  try {
    await store.activateProvider(p.id)
    ElMessage.success(`已启用「${p.name}」`)
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    activatingId.value = null
  }
}

const editVisible = ref(false)
const editSaving = ref(false)
const editForm = reactive({
  id: null,
  name: '',
  base_url: '',
  model: '',
  api_key: '',
  existingHint: null, // 已配置 Key 的掩码提示（不回传明文）
})

function openEdit(p) {
  editForm.id = p.id
  editForm.name = p.name || ''
  editForm.base_url = p.base_url || ''
  editForm.model = p.model || ''
  editForm.api_key = ''
  editForm.existingHint = p.api_key_hint || null
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.name || !editForm.base_url || !editForm.model) {
    ElMessage.warning('请完整填写名称、服务地址与模型')
    return
  }
  editSaving.value = true
  try {
    const payload = { name: editForm.name, base_url: editForm.base_url, model: editForm.model }
    if (editForm.api_key) payload.api_key = editForm.api_key // 留空保留原值
    await store.updateProvider(editForm.id, payload)
    ElMessage.success('供应商已更新')
    editVisible.value = false
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    editSaving.value = false
  }
}

const createVisible = ref(false)
const createSaving = ref(false)
const createForm = reactive({ type: 'cloud', name: '', base_url: '', model: '', api_key: '' })

function openCreate() {
  createForm.type = 'cloud'
  createForm.name = ''
  createForm.base_url = ''
  createForm.model = ''
  createForm.api_key = ''
  createVisible.value = true
}

async function saveCreate() {
  if (!createForm.name || !createForm.base_url || !createForm.model) {
    ElMessage.warning('请完整填写名称、服务地址与模型')
    return
  }
  if (createForm.type === 'cloud' && !createForm.api_key) {
    ElMessage.warning('云端供应商必须填写 API Key')
    return
  }
  createSaving.value = true
  try {
    const payload = {
      type: createForm.type,
      name: createForm.name,
      base_url: createForm.base_url,
      model: createForm.model,
    }
    if (createForm.api_key) payload.api_key = createForm.api_key
    await store.createProvider(payload)
    ElMessage.success('供应商已添加')
    createVisible.value = false
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    createSaving.value = false
  }
}

async function handleRemove(p) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${p.name}」？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  deletingId.value = p.id
  try {
    await store.removeProvider(p.id)
    ElMessage.success('已删除')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  if (!store.loaded) {
    store.fetchAll().catch(() => {})
  }
})
</script>

<template>
  <div class="provider-switch">
    <div class="toolbar">
      <span class="muted">管理模型接入配置，启用后全局生效</span>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增供应商</el-button>
    </div>

    <div v-for="g in groups" :key="g.type" class="group">
      <div class="group-title">{{ g.label }}</div>
      <el-empty v-if="!g.providers.length" description="暂无供应商" :image-size="48" />
      <el-row v-else :gutter="12">
        <el-col v-for="p in g.providers" :key="p.id" :xs="24" :sm="12" :md="8">
          <el-card shadow="hover" class="provider-card" :class="{ active: p.is_active }">
            <div class="p-head">
              <span class="p-name" :title="p.name">{{ p.name }}</span>
              <el-tag v-if="p.is_active" type="success" size="small">当前生效</el-tag>
              <el-tag
                v-if="p.type === 'cloud' && !p.has_api_key"
                type="danger"
                size="small"
              >未配置 Key</el-tag>
              <el-tag v-else-if="p.has_api_key" type="info" size="small">已配置 Key</el-tag>
            </div>
            <div class="p-line">
              <span class="p-label">模型</span>
              <span class="p-value" :title="p.model">{{ p.model || '—' }}</span>
            </div>
            <div class="p-line">
              <span class="p-label">地址</span>
              <span class="p-value" :title="p.base_url">{{ p.base_url || '—' }}</span>
            </div>
            <div class="p-actions">
              <el-button
                link
                type="primary"
                size="small"
                :loading="testingId === p.id"
                @click="handleTest(p)"
              >测试</el-button>
              <el-button
                link
                type="success"
                size="small"
                :disabled="p.is_active"
                :loading="activatingId === p.id"
                @click="handleActivate(p)"
              >启用</el-button>
              <el-button link size="small" @click="openEdit(p)">编辑</el-button>
              <el-button
                v-if="!p.is_active"
                link
                type="danger"
                size="small"
                :loading="deletingId === p.id"
                @click="handleRemove(p)"
              >删除</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="editVisible" title="编辑供应商" width="480px">
      <el-form label-position="top" @submit.prevent="saveEdit">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="例如 Qwen 云端 / 本地 Ollama" />
        </el-form-item>
        <el-form-item label="服务地址（Base URL）">
          <el-input v-model="editForm.base_url" placeholder="例如 https://api.example.com/v1" />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="editForm.model" placeholder="例如 qwen-plus / qwen3:4b" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="editForm.api_key"
            type="password"
            show-password
            placeholder="留空则保留原 Key"
          />
          <div v-if="editForm.existingHint" class="key-hint">
            <span class="key-dot" />已配置 Key：<code>{{ editForm.existingHint }}</code>
            <span class="key-note">（留空保持不变；填写新 Key 将覆盖）</span>
          </div>
          <div v-else class="key-hint none">尚未配置 API Key</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="新增供应商" width="480px">
      <el-form label-position="top" @submit.prevent="saveCreate">
        <el-form-item label="类型">
          <el-select v-model="createForm.type" style="width: 100%">
            <el-option v-for="g in GROUPS" :key="g.type" :label="g.label" :value="g.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="给这个供应商起个名字" />
        </el-form-item>
        <el-form-item label="服务地址（Base URL）">
          <el-input
            v-model="createForm.base_url"
            placeholder="例如 https://api.example.com/v1 或 http://127.0.0.1:11434/v1"
          />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="createForm.model" placeholder="例如 qwen-plus / qwen3:4b" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="createForm.api_key"
            type="password"
            show-password
            :placeholder="createForm.type === 'cloud' ? '云端供应商必填' : '本地服务通常无需填写'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSaving" @click="saveCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.muted {
  color: #909399;
  font-size: 13px;
}

.group {
  margin-bottom: 16px;
}

.group-title {
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
  font-weight: 600;
}

.provider-card {
  margin-bottom: 12px;
}

.provider-card.active {
  border-color: #95d475;
}

.p-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.p-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 600;
}

.p-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 2px 0;
  color: #606266;
  font-size: 13px;
}

.p-label {
  flex-shrink: 0;
  color: #909399;
}

.p-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.p-actions {
  display: flex;
  align-items: center;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
}
/* 已配置 Key 掩码提示 */
.key-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 7px;
  font-size: 12px;
  color: var(--success);
  line-height: 1.5;
}

.key-hint.none {
  color: var(--faint);
}

.key-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success);
  flex-shrink: 0;
}

.key-hint code {
  padding: 1px 7px;
  border-radius: 5px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--fg);
}

.key-note {
  color: var(--faint);
}
</style>
