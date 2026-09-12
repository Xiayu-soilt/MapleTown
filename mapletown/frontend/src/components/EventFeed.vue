<script setup>
import { computed } from "vue";
import { useSimStore, EVENT_STYLES } from "../stores/sim";

const sim = useSimStore();

const styled = computed(() =>
  sim.feed.slice(0, 80).map((e) => ({
    ...e,
    style: EVENT_STYLES[e.type] || { label: e.type, color: "#909399", icon: "•" },
  }))
);

function timeOf(e) {
  return (e.sim_time || "").slice(11, 16);
}
</script>

<template>
  <div class="feed">
    <div class="feed-head">
      <span class="dot" :class="{ live: sim.connected }" />
      <span class="feed-title">实时事件流</span>
      <el-tag size="small" :type="sim.connected ? 'danger' : 'info'" effect="plain">
        {{ sim.connected ? "LIVE" : "连接中" }}
      </el-tag>
    </div>

    <el-empty v-if="!styled.length" description="小镇很安静，等待模拟启动…" :image-size="70" />

    <transition-group v-else name="event" tag="div" class="feed-list">
      <div v-for="e in styled" :key="e.id ?? `${e.tick}-${e.type}-${e.content}`" class="event-item">
        <span class="event-time">{{ timeOf(e) }}</span>
        <span
          class="event-type"
          :style="{ color: e.style.color, borderColor: e.style.color, background: e.style.color + '14' }"
        >
          {{ e.style.icon }} {{ e.style.label }}
        </span>
        <span class="event-content">
          {{ e.content }}
          <em v-if="e.location" class="event-loc">@{{ e.location }}</em>
        </span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.feed {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.feed-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px 12px;
  border-bottom: 1px dashed rgba(232, 64, 42, 0.2);
  margin-bottom: 10px;
}

.feed-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--maple-ink);
  flex: 1;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c0c4cc;
}

.dot.live {
  background: var(--maple-red);
  animation: pulse 1.6s infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(232, 64, 42, 0.5);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(232, 64, 42, 0);
  }
}

.feed-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 4px;
}

.event-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.65);
  font-size: 14px;
  line-height: 1.5;
}

.event-time {
  font-variant-numeric: tabular-nums;
  color: #a08b76;
  font-size: 13px;
  flex-shrink: 0;
}

.event-type {
  flex-shrink: 0;
  font-size: 12.5px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 10px;
  border: 1px solid;
}

.event-content {
  color: var(--maple-ink);
  word-break: break-all;
}

.event-loc {
  color: #a08b76;
  font-style: normal;
  font-size: 12.5px;
  margin-left: 4px;
}

.event-enter-active {
  transition: all 0.4s ease;
}

.event-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
