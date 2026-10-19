<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useDocumentsStore } from '../stores/documents'

// 规格：两条导入路径成功后 emit('submitted', docIds)
const emit = defineEmits(['submitted'])

const store = useDocumentsStore()

const ALLOWED_EXT = ['.pdf', '.docx', '.md', '.xlsx']
const MAX_SIZE_MB = 100
const MAX_FILES = 20 // 与后端 kb_max_upload_files 一致

const fileList = ref([])
const rejects = ref([]) // 未入队文件提示：[{ name, reason }]
const uploading = ref(false)

const url = ref('')
const urlSubmitting = ref(false)

const uploadBtnText = computed(() =>
  fileList.value.length ? `上传并解析（${fileList.value.length} 个文件）` : '上传并解析'
)

function fileExt(name) {
  const n = String(name || '')
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i).toLowerCase() : ''
}

// 逐文件预校验：扩展名白名单 + 单文件大小；返回空串表示合格
function validateFile(raw) {
  if (!raw) return '无法读取文件内容'
  if (!ALLOWED_EXT.includes(fileExt(raw.name))) {
    return `不支持的格式，仅支持 ${ALLOWED_EXT.join(' / ')}`
  }
  if (raw.size > MAX_SIZE_MB * 1024 * 1024) {
    return `文件超过 ${MAX_SIZE_MB}MB 上限`
  }
  return ''
}

// 文件加入队列时逐个校验：不合格的弹出提示并从队列移除（不入队）
function onFileChange(file) {
  const reason = validateFile(file?.raw)
  if (!reason) return
  fileList.value = fileList.value.filter((f) => f.uid !== file.uid)
  rejects.value.push({ name: file.name, reason })
  ElMessage.warning(`${file.name}：${reason}`)
}

function removeReject(index) {
  rejects.value.splice(index, 1)
}

async function submitFiles() {
  const files = fileList.value.map((f) => f.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  if (files.length > MAX_FILES) {
    ElMessage.warning(`单次最多上传 ${MAX_FILES} 个文件，请分批上传`)
    return
  }
  uploading.value = true
  try {
    const data = await store.upload(files)
    const docIds = (data.items || []).map((item) => item.doc_id).filter(Boolean)
    fileList.value = []
    rejects.value = []
    if (docIds.length) {
      emit('submitted', docIds)
      ElMessage.success(`已提交 ${docIds.length} 个文件，正在解析`)
    }
  } catch {
    // 失败提示由 http 拦截器统一弹出，保留队列便于重新提交
  } finally {
    uploading.value = false
  }
}

async function submitUrl() {
  const value = url.value.trim()
  if (!/^https?:\/\//i.test(value)) {
    ElMessage.warning('URL 必须以 http:// 或 https:// 开头')
    return
  }
  urlSubmitting.value = true
  try {
    const data = await store.importUrl(value)
    url.value = ''
    emit('submitted', [data.doc_id])
    ElMessage.success('已提交网页，正在解析')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    urlSubmitting.value = false
  }
}
</script>

<template>
  <div class="import-panel">
    <el-upload
      v-model:file-list="fileList"
      class="uploader"
      drag
      multiple
      :auto-upload="false"
      accept=".pdf,.docx,.md,.xlsx"
      :on-change="onFileChange"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">
          支持 .pdf / .docx / .md / .xlsx，单文件不超过 100MB，可多选，单次最多 20 个
        </div>
      </template>
    </el-upload>

    <div v-if="rejects.length" class="rejects">
      <div v-for="(item, i) in rejects" :key="i" class="reject-item">
        <span class="reject-name">{{ item.name }}</span>
        <span class="reject-reason">{{ item.reason }}</span>
        <el-button link type="danger" size="small" @click="removeReject(i)">移除提示</el-button>
      </div>
    </div>

    <el-button
      class="upload-btn"
      type="primary"
      :loading="uploading"
      :disabled="!fileList.length"
      @click="submitFiles"
    >
      {{ uploadBtnText }}
    </el-button>

    <el-divider class="divider">或导入网页</el-divider>

    <div class="url-row">
      <el-input
        v-model="url"
        placeholder="https://example.com/article"
        clearable
        :disabled="urlSubmitting"
        @keyup.enter="submitUrl"
      />
      <el-button type="primary" plain :loading="urlSubmitting" @click="submitUrl">
        导入网页
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.import-panel {
  width: 100%;
}

.uploader {
  width: 100%;
}

.uploader :deep(.el-upload) {
  width: 100%;
}

.uploader :deep(.el-upload-dragger) {
  width: 100%;
}

.uploader :deep(.el-icon--upload) {
  font-size: 46px;
  color: #c0c4cc;
  margin-bottom: 8px;
}

.rejects {
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid #f3d19e;
  border-radius: 4px;
  background: #fdf6ec;
}

.reject-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 24px;
}

.reject-name {
  color: #303133;
  word-break: break-all;
}

.reject-reason {
  flex: 1;
  color: #b88230;
}

.upload-btn {
  margin-top: 12px;
}

.divider {
  margin: 20px 0 16px;
}

.url-row {
  display: flex;
  gap: 8px;
}
</style>
