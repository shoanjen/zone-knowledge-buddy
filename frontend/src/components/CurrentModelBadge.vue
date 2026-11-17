<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useSettingsStore } from '../stores/settings'

// 全局常驻顶栏：当前生效模型 + 健康红绿点（30s 心跳 test，规格 §13.3）
const settings = useSettingsStore()
const healthy = ref(null) // null 未知 / true 绿 / false 红
let timer = null

const provider = computed(() => settings.activeProvider)
const kindLabel = computed(() =>
  provider.value?.type === 'cloud' ? '云端' : '本地',
)
const label = computed(() =>
  provider.value ? `${provider.value.name} · ${provider.value.model}` : '未启用模型',
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
  <div
    class="model-badge"
    :title="provider ? provider.base_url : '尚未启用任何模型供应商，前往设置页配置'"
  >
    <span class="dot" :class="{ ok: healthy === true, bad: healthy === false }" />
    <template v-if="provider">
      <span class="kind">{{ kindLabel }}</span>
      <span class="name">{{ label }}</span>
    </template>
    <template v-else>
      <span class="name none">未启用模型</span>
    </template>
  </div>
</template>

<style scoped>
.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  cursor: default;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--faint);
  flex-shrink: 0;
}

.dot.ok {
  background: var(--success);
}

.dot.bad {
  background: var(--danger);
}

.kind {
  font-size: 11px;
  color: var(--faint);
  letter-spacing: 0.06em;
}

.name {
  color: var(--fg);
  font-variant-numeric: tabular-nums;
}

.name.none {
  color: var(--muted);
}
</style>
