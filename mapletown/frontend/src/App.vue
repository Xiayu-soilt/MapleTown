<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { useSimStore } from "./stores/sim";
import MapleLogo from "./components/MapleLogo.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const sim = useSimStore();

const isLogin = computed(() => route.name === "login");

function handleLogout() {
  sim.disconnectStream();
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <router-view v-if="isLogin" />

  <div v-else class="shell">
    <header class="shell-header">
      <div class="brand" @click="router.push('/town')">
        <MapleLogo :size="34" />
        <div class="brand-text">
          <span class="brand-name">枫叶镇</span>
          <span class="brand-sub">AI 小镇观测站</span>
        </div>
      </div>

      <div class="header-right">
        <div class="clock" :class="{ paused: !sim.state.running }">
          {{ sim.simClock }}
          <el-tag v-if="!sim.state.running" size="small" type="info" effect="plain">已暂停</el-tag>
          <el-tag v-else size="small" type="danger" effect="plain">{{ sim.state.speed }}x</el-tag>
        </div>
        <el-dropdown @command="handleLogout">
          <span class="user-chip">
            {{ auth.username || "观测者" }}
            <span class="caret">▾</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="shell-body">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(1200px 400px at 80% -10%, rgba(245, 166, 35, 0.12), transparent),
    var(--maple-cream);
}

.shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 28px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(232, 64, 42, 0.12);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.brand-name {
  font-size: 21px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--maple-red), var(--maple-orange));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.brand-sub {
  font-size: 12px;
  color: var(--maple-warm);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 18px;
}

.clock {
  font-size: 17px;
  font-weight: 600;
  color: var(--maple-warm);
  display: flex;
  align-items: center;
  gap: 8px;
  font-variant-numeric: tabular-nums;
}

.clock.paused {
  color: #909399;
}

.user-chip {
  font-size: 15px;
  color: var(--maple-warm);
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 20px;
  background: rgba(232, 64, 42, 0.06);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  outline: none;
}

.caret {
  font-size: 12px;
  color: #a08b76;
}

.shell-body {
  flex: 1;
  overflow: auto;
}
</style>
