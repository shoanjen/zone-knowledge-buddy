<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { downloadPodcast, fetchPodcastAudio, listVoices } from '../api/podcasts'
import { usePodcastsStore } from '../stores/podcasts'

/**
 * 播客详情对话框：音频播放（blob 直链，带鉴权拉取）+ 双主播脚本逐轮展示。
 */
const props = defineProps({
  modelValue: Boolean,
  podcastId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'deleted'])

const podcastsStore = usePodcastsStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const audioUrl = ref('')
const audioLoading = ref(false)
const voiceLabels = ref({})
const downloading = ref(false)
let objectUrl = ''

const podcast = computed(() => podcastsStore.current)

function fmtDuration(s) {
  if (!s || s <= 0) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

function fmtTime(dt) {
  if (!dt) return '—'
  return String(dt).replace('T', ' ').slice(0, 16)
}

function voiceName(vid) {
  return voiceLabels.value[vid] || vid
}

function revokeAudio() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
    audioUrl.value = ''
  }
}

async function loadAudio(id) {
  audioLoading.value = true
  try {
    const blob = await fetchPodcastAudio(id)
    objectUrl = URL.createObjectURL(blob)
    audioUrl.value = objectUrl
  } catch {
    /* 错误提示由 http 拦截器统一弹出 */
  } finally {
    audioLoading.value = false
  }
}

async function download() {
  if (!podcast.value) return
  downloading.value = true
  try {
    const blob = await downloadPodcast(podcast.value.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${podcast.value.title || podcast.value.id}.mp3`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    /* 拦截器已提示 */
  } finally {
    downloading.value = false
  }
}

async function remove() {
  if (!podcast.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除播客「${podcast.value.title || '无标题'}」吗？音频文件将一并删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await podcastsStore.remove(podcast.value.id).catch(() => {})
  ElMessage.success('播客已删除')
  emit('deleted')
  visible.value = false
}

watch(
  visible,
  async (open) => {
    if (!open) {
      revokeAudio()
      return
    }
    if (!props.podcastId) return
    loading.value = true
    try {
      const [detail, voicesData] = await Promise.all([
        podcastsStore.fetchDetail(props.podcastId),
        listVoices().catch(() => null),
      ])
      if (voicesData?.voices) {
        voiceLabels.value = Object.fromEntries(voicesData.voices.map((v) => [v.id, v.label]))
      }
      if (detail?.has_audio) await loadAudio(detail.id)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="podcast?.title || '播客'"
    width="640px"
    :close-on-click-modal="false"
    append-to-body
    @closed="revokeAudio"
  >
    <div v-loading="loading" class="podcast-body">
      <template v-if="podcast">
        <div class="meta-row">
          <el-tag size="small" effect="plain">{{ podcast.style }}</el-tag>
          <span class="meta-item">时长 {{ fmtDuration(podcast.duration_s) }}</span>
          <span class="meta-item">{{ podcast.turns?.length || 0 }} 轮对话</span>
          <span class="meta-item">{{ fmtTime(podcast.created_at) }}</span>
        </div>
        <div class="hosts">
          <div class="host">
            <span class="host-badge a">A</span>{{ voiceName(podcast.voice_a) }}
          </div>
          <div class="host">
            <span class="host-badge b">B</span>{{ voiceName(podcast.voice_b) }}
          </div>
        </div>

        <div v-loading="audioLoading" class="player-box">
          <audio v-if="audioUrl" :src="audioUrl" controls preload="metadata" class="player" />
          <div v-else-if="!audioLoading" class="player-missing">音频不存在（可能生成失败后已失效）</div>
        </div>

        <div class="script">
          <div
            v-for="(turn, i) in podcast.turns || []"
            :key="i"
            class="turn"
            :class="turn.speaker === 'A' ? 'from-a' : 'from-b'"
          >
            <span class="speaker">{{ turn.speaker }}</span>
            <div class="bubble">{{ turn.text }}</div>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button :icon="Download" :loading="downloading" :disabled="!podcast?.has_audio" @click="download">
        下载 MP3
      </el-button>
      <el-button type="danger" plain @click="remove">删除</el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.podcast-body {
  min-height: 120px;
}

.meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: var(--muted);
}

.hosts {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--fg);
}

.host {
  display: flex;
  align-items: center;
  gap: 6px;
}

.host-badge {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.host-badge.a {
  background: var(--accent-soft, #e5efe9);
  color: var(--accent);
}

.host-badge.b {
  background: #efe7f5;
  color: #7c5a9e;
}

.player-box {
  margin-bottom: 14px;
}

.player {
  width: 100%;
}

.player-missing {
  padding: 14px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  text-align: center;
  font-size: 12.5px;
  color: var(--faint);
}

.script {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.turn {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.turn.from-b {
  flex-direction: row-reverse;
}

.speaker {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-2, #f5f4f1);
  color: var(--muted);
}

.from-a .speaker {
  background: var(--accent-soft, #e5efe9);
  color: var(--accent);
}

.from-b .speaker {
  background: #efe7f5;
  color: #7c5a9e;
}

.bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--fg);
}

.from-b .bubble {
  background: var(--surface-2, #f5f4f1);
}
</style>
