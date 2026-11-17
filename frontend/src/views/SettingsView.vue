<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { useSettingsStore } from '../stores/settings'
import { exportData } from '../api/data'
import ProviderSwitch from '../components/ProviderSwitch.vue'

const settings = useSettingsStore()

// 后端默认值：{ extract: 0.2, chat: 0.3, report: 0.4 }（docs/04 §12）
const DEFAULT_PARAMS = { extract: 0.2, chat: 0.3, report: 0.4 }

const paramForm = reactive({ ...DEFAULT_PARAMS })
const embeddingForm = reactive({ base_url: '', model: '' })
const savingParams = ref(false)
const savingEmbedding = ref(false)
const exporting = ref(false)

const embeddingLocked = computed(() => !!settings.settings.embedding_locked)

const EMBEDDING_TYPES = {
  cloud: '云端',
  'local-ollama': '本地 Ollama',
  'local-lmstudio': '本地 LM Studio',
}

const embeddingTypeLabel = computed(() => {
  const t = settings.settings.embedding?.provider_type
  return EMBEDDING_TYPES[t] || t || '—'
})

// 生成参数是否有改动（按两位小数比较，规避滑块浮点步进误差）；仅控制保存按钮可点性
const paramsDirty = computed(() => {
  const p = settings.settings.generation_params || {}
  const src = [
    p.extract ?? DEFAULT_PARAMS.extract,
    p.chat ?? DEFAULT_PARAMS.chat,
    p.report ?? DEFAULT_PARAMS.report,
  ]
  const form = [paramForm.extract, paramForm.chat, paramForm.report]
  return form.some((v, i) => Number(v).toFixed(2) !== Number(src[i]).toFixed(2))
})

function syncForm() {
  const p = settings.settings.generation_params || {}
  paramForm.extract = p.extract ?? DEFAULT_PARAMS.extract
  paramForm.chat = p.chat ?? DEFAULT_PARAMS.chat
  paramForm.report = p.report ?? DEFAULT_PARAMS.report
  const e = settings.settings.embedding || {}
  embeddingForm.base_url = e.base_url || ''
  embeddingForm.model = e.model || ''
}

async function saveParams() {
  savingParams.value = true
  try {
    await settings.saveSettings({
      generation_params: {
        extract: paramForm.extract,
        chat: paramForm.chat,
        report: paramForm.report,
      },
    })
    ElMessage.success('生成参数已保存')
  } catch {
    // 错误提示由 http 拦截器统一弹出
  } finally {
    savingParams.value = false
  }
}

async function saveEmbedding() {
  if (!embeddingForm.base_url || !embeddingForm.model) {
    ElMessage.warning('请填写向量服务地址与模型')
    return
  }
  savingEmbedding.value = true
  try {
    await settings.saveSettings({
      embedding: {
        provider_type: settings.settings.embedding?.provider_type,
        base_url: embeddingForm.base_url,
        model: embeddingForm.model,
      },
    })
    ElMessage.success('向量模型配置已保存')
  } catch {
    // 409 EMBEDDING_LOCKED 等错误由 http 拦截器统一提示
  } finally {
    savingEmbedding.value = false
  }
}

function pad(n) {
  return String(n).padStart(2, '0')
}

async function exportBackup() {
  exporting.value = true
  try {
    const blob = await exportData()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const d = new Date()
    link.href = url
    link.download = `zone-kb-backup-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('备份已开始下载')
  } catch {
    // 错误提示由 http 拦截器统一弹出（blob 错误体同样会被解析）
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  await settings.fetchAll().catch(() => {})
  syncForm()
})
</script>

<template>
  <div class="page settings-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">设置</h2>
        <p class="page-sub">模型供应商、生成参数、向量模型与数据管理</p>
      </div>
    </div>

    <el-card class="section-card">
      <template #header>
        <div class="card-head">
          <span>模型供应商</span>
        </div>
      </template>
      <ProviderSwitch />
    </el-card>

    <el-card class="section-card">
      <template #header>
        <div class="card-head"><span>生成参数</span></div>
      </template>
      <div class="param-row">
        <span class="param-label">信息抽取（extract）</span>
        <el-slider v-model="paramForm.extract" :min="0" :max="1" :step="0.05" class="param-slider" />
        <span class="param-value tnum">{{ paramForm.extract.toFixed(2) }}</span>
      </div>
      <div class="param-row">
        <span class="param-label">问答（chat）</span>
        <el-slider v-model="paramForm.chat" :min="0" :max="1" :step="0.05" class="param-slider" />
        <span class="param-value tnum">{{ paramForm.chat.toFixed(2) }}</span>
      </div>
      <div class="param-row">
        <span class="param-label">报告（report）</span>
        <el-slider v-model="paramForm.report" :min="0" :max="1" :step="0.05" class="param-slider" />
        <span class="param-value tnum">{{ paramForm.report.toFixed(2) }}</span>
      </div>
      <div class="section-foot">
        <span class="hint">温度越低输出越稳定，越高越发散</span>
        <el-button type="primary" :loading="savingParams" :disabled="!paramsDirty" @click="saveParams">
          保存
        </el-button>
      </div>
    </el-card>

    <el-card class="section-card">
      <template #header>
        <div class="card-head">
          <span>向量模型</span>
          <el-tag v-if="embeddingLocked" type="danger" effect="plain" size="small">已锁定</el-tag>
        </div>
      </template>

      <div class="info-grid">
        <div class="info-item">
          <div class="info-label">供应商类型</div>
          <div class="info-value">{{ embeddingTypeLabel }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">服务地址</div>
          <div class="info-value info-mono">{{ settings.settings.embedding?.base_url || '—' }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">模型</div>
          <div class="info-value info-mono">{{ settings.settings.embedding?.model || '—' }}</div>
        </div>
      </div>

      <p v-if="embeddingLocked" class="hint lock-hint">
        向量库已建立，向量模型已锁定；如需更换，需先清空全部文档后重建。
      </p>
      <template v-else>
        <p class="hint lock-hint">尚未建立向量库，仍可调整以下配置；首条向量写入后将自动锁定。</p>
        <el-form label-position="top" class="embed-form" @submit.prevent="saveEmbedding">
          <el-form-item label="服务地址（Base URL）">
            <el-input v-model="embeddingForm.base_url" placeholder="例如 http://127.0.0.1:11434/v1" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="embeddingForm.model" placeholder="例如 bge-m3" />
          </el-form-item>
        </el-form>
        <div class="section-foot">
          <span class="hint">建库前仅可调整服务地址与模型</span>
          <el-button plain :loading="savingEmbedding" @click="saveEmbedding">保存</el-button>
        </div>
      </template>
    </el-card>

    <el-card class="section-card">
      <template #header>
        <div class="card-head"><span>数据管理</span></div>
      </template>
      <p class="hint data-desc">
        备份内容包含数据库、向量库与全部原始文件，导出为 zip
        压缩包。恢复为手动操作：停止服务后用备份内容替换 data 目录，再重新启动。
      </p>
      <el-button type="primary" plain :loading="exporting" :icon="Download" @click="exportBackup">
        导出备份 zip
      </el-button>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
}

.section-card {
  margin-bottom: 16px;
}

.section-card:last-child {
  margin-bottom: 0;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.param-row + .param-row {
  margin-top: 14px;
}

.param-label {
  width: 90px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--fg);
}

.param-slider {
  width: 260px;
  flex-shrink: 0;
}

.param-value {
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--fg-strong);
}

.section-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.info-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 36px;
}

.info-label {
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 12px;
}

.info-value {
  color: var(--fg);
  font-size: 12.5px;
  word-break: break-all;
}

.info-mono {
  font-family: var(--font-mono);
}

.lock-hint {
  margin: 14px 0 0;
  line-height: 1.7;
}

.embed-form {
  margin-top: 14px;
}

.embed-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.embed-form :deep(.el-form-item__label) {
  font-size: 13px;
}

.data-desc {
  margin: 0 0 14px;
  line-height: 1.7;
}
</style>
