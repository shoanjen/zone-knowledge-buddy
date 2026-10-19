<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useSettingsStore } from '../stores/settings'

// 规格§13.3：全局常驻顶栏；☁ 云端 / 🖥 本地 + 健康红绿点（30s 心跳 test）
const settings = useSettingsStore()
const healthy = ref(null) // null 未知 / true 绿 / false 红
let timer = null

const provider = computed(() => settings.activeProvider)
const icon = computed(() => (provider.value?.type === 'cloud' ? '☁' : '🖥'))
const label = computed(() =>
  provider.value ? `${provider.value.name} / ${provider.value.model}` : '未启用模型',
)

async function heartbeat() {
  if (!provider.value) {
    healthy.value = null
    return
  }
  try {
    const result = await settings.testProvider(provider.value.id)
    healthy.value = !!result.ok
  } catch {
    healthy.value = false
  }
}

onMounted(async () => {
  if (!settings.loaded) {
    await settings.fetchAll().catch(() => {})
  }
  await heartbeat()
  timer = setInterval(heartbeat, 30000)
})

onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="model-badge" :title="provider ? `${provider.base_url}` : '尚未启用任何模型供应商'">
    <span class="dot" :class="{ ok: healthy === true, bad: healthy === false }" />
    <span class="label">{{ icon }} {{ label }}</span>
  </div>
</template>

<style scoped>
.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  background: #f0f2f5;
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
}

.dot.ok {
  background: #67c23a;
}

.dot.bad {
  background: #f56c6c;
}
</style>
