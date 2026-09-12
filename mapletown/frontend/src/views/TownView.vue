<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useSimStore } from "../stores/sim";
import TownMap from "../components/TownMap.vue";
import EventFeed from "../components/EventFeed.vue";

const sim = useSimStore();
const selected = ref(null);

async function toggleRun() {
  const action = sim.state.running ? "pause" : "start";
  try {
    await sim.control(action);
    ElMessage.success(action === "start" ? "小镇苏醒了" : "小镇暂停");
  } catch (err) {
    ElMessage.error(err.message);
  }
}

async function setSpeed(speed) {
  try {
    await sim.control("speed", speed);
  } catch (err) {
    ElMessage.error(err.message);
  }
}

onMounted(async () => {
  try {
    await Promise.all([sim.refreshState(), sim.refreshResidents(), sim.refreshFeed()]);
  } catch (err) {
    ElMessage.error(`加载失败：${err.message}`);
    return;
  }
  sim.connectStream();
});
</script>

<template>
  <div class="page town-page">
    <div class="control-bar">
      <div class="control-left">
        <el-button class="btn-maple" size="large" round @click="toggleRun">
          {{ sim.state.running ? "⏸ 暂停模拟" : "▶ 启动模拟" }}
        </el-button>
        <el-radio-group
          :model-value="sim.state.speed"
          size="large"
          @update:model-value="setSpeed"
        >
          <el-radio-button :value="1">1x</el-radio-button>
          <el-radio-button :value="2">2x</el-radio-button>
          <el-radio-button :value="5">5x</el-radio-button>
        </el-radio-group>
      </div>
      <div class="control-stat">
        <span class="stat"><b>{{ sim.state.sim_day }}</b> 模拟日</span>
        <span class="stat">Tick <b>{{ sim.state.tick }}</b></span>
        <span class="stat"><b>{{ sim.residents.length }}</b> 位居民</span>
        <span class="stat">模式时间 <b>{{ sim.simClock }}</b></span>
      </div>
    </div>

    <div class="town-grid">
      <el-card class="map-card" shadow="never" :body-style="{ padding: '10px', height: '100%' }">
        <TownMap :residents="sim.residents" @select-resident="selected = $event" />
      </el-card>

      <el-card class="feed-card" shadow="never" :body-style="{ padding: '16px', height: '100%' }">
        <EventFeed />
      </el-card>
    </div>

    <el-drawer v-model="selected" :title="selected?.name" size="360px" with-header>
      <template v-if="selected">
        <div class="drawer-body">
          <div class="avatar" :style="{ background: selected.avatar_color }">
            {{ selected.name.slice(0, 1) }}
          </div>
          <div class="info-row"><label>身份</label><span>{{ selected.identity }}</span></div>
          <div class="info-row"><label>年龄</label><span>{{ selected.age }} 岁</span></div>
          <div class="info-row"><label>工作地</label><span>{{ selected.workplace }}</span></div>
          <div class="info-row"><label>当前所在</label><span>{{ selected.current_location }}</span></div>
          <div class="info-col"><label>正在做什么</label><p>{{ selected.current_activity }}</p></div>
          <el-alert type="info" :closable="false" show-icon title="M5 观测站开发中"
            description="居民详情页（记忆观测器 / 反思树 / 日程 / 关系）将在下一个里程碑开放。"
          />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.town-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.control-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.control-stat {
  display: flex;
  gap: 22px;
  color: var(--maple-warm);
  font-size: 15px;
}

.control-stat b {
  font-size: 18px;
  color: var(--maple-red);
  font-variant-numeric: tabular-nums;
}

.town-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 14px;
}

.map-card,
.feed-card {
  min-height: 0;
  overflow: hidden;
}

.feed-card {
  max-height: 100%;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  color: #fff;
  font-size: 26px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: center;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 15px;
  padding: 8px 4px;
  border-bottom: 1px dashed rgba(122, 92, 68, 0.2);
}

.info-row label {
  color: var(--maple-warm);
}

.info-col label {
  display: block;
  color: var(--maple-warm);
  font-size: 14px;
  margin-bottom: 6px;
}

.info-col p {
  margin: 0;
  background: rgba(245, 166, 35, 0.1);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 15px;
  line-height: 1.6;
}

@media (max-width: 1100px) {
  .town-grid {
    grid-template-columns: 1fr;
  }
}
</style>
