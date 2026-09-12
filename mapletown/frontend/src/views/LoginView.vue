<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";
import MapleLogo from "../components/MapleLogo.vue";

const router = useRouter();
const auth = useAuthStore();

const BG_PROMPTS = [
  "像素风格游戏插画，16-bit 复古 RPG 像素美术，秋日枫叶小镇街道，红橙色枫树成排，落叶飘落，暖色像素游戏场景，精细像素画",
  "像素风格游戏插画，复古 RPG 像素美术，温馨咖啡馆内景，木质桌椅与暖黄灯光，窗外枫叶飘落，暖橙色调像素游戏场景",
  "像素风格游戏插画，16-bit 像素美术，枫树林间小路，夕阳红橙渐变天空，金色落叶铺满小路，唯美像素游戏场景",
  "像素风格游戏插画，复古像素美术，欧式小镇黄昏街道，暖黄灯光的窗户与飘落枫叶，治愈系像素游戏场景",
];

const IMAGE_API = "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image";
const backgrounds = BG_PROMPTS.map(
  (p) => `${IMAGE_API}?prompt=${encodeURIComponent(p)}&image_size=landscape_16_9`
);

const mode = ref("login");
const loading = ref(false);
const form = ref({ username: "", email: "", password: "" });
const formRef = ref(null);

const current = ref(Math.floor(Math.random() * backgrounds.length));
let timer = null;

const rules = computed(() => ({
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 2, max: 24, message: "用户名 2~24 个字符", trigger: "blur" },
  ],
  email:
    mode.value === "register"
      ? [
          { required: true, message: "请输入邮箱", trigger: "blur" },
          { type: "email", message: "邮箱格式不正确", trigger: "blur" },
        ]
      : [],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, max: 32, message: "密码至少 6 位", trigger: "blur" },
  ],
}));

function switchTo(next) {
  mode.value = next;
  formRef.value?.clearValidate();
}

function selectBg(index) {
  current.value = index;
  restartTimer();
}

function restartTimer() {
  if (timer) clearInterval(timer);
  timer = setInterval(() => {
    current.value = (current.value + 1) % backgrounds.length;
  }, 10000);
}

async function submit() {
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  loading.value = true;
  try {
    if (mode.value === "login") {
      await auth.login(form.value.username, form.value.password);
      ElMessage.success(`欢迎回来，${form.value.username}`);
    } else {
      await auth.register(form.value.username, form.value.email, form.value.password);
      ElMessage.success("注册成功，欢迎来到枫叶镇");
    }
    router.push("/town");
  } catch (err) {
    ElMessage.error(err.message || "操作失败");
  } finally {
    loading.value = false;
  }
}

onMounted(restartTimer);
onBeforeUnmount(() => timer && clearInterval(timer));
</script>

<template>
  <div class="login-page">
    <div class="bg-stage">
      <div
        v-for="(bg, i) in backgrounds"
        :key="i"
        class="bg-slide"
        :class="{ active: i === current }"
        :style="{ backgroundImage: `url(${bg})` }"
      />
      <div class="bg-mask" />
      <div class="bg-dots">
        <span
          v-for="(bg, i) in backgrounds"
          :key="i"
          class="dot"
          :class="{ active: i === current }"
          :title="`背景 ${i + 1}`"
          @click="selectBg(i)"
        />
      </div>
    </div>

    <div class="login-card">
      <MapleLogo :size="72" />
      <h1 class="title">枫叶镇</h1>
      <p class="subtitle">AI 小镇观测站 · 一群会记忆、会反思的 AI 居民</p>

      <el-tabs :model-value="mode" class="tabs" @tab-click="(t) => switchTo(t.props.name)">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" autocomplete="username" />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" prop="email">
          <el-input v-model="form.email" placeholder="邮箱" autocomplete="email" />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            show-password
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </el-form-item>

        <el-button class="btn-maple submit" size="large" :loading="loading" @click="submit">
          {{ mode === "login" ? "进入小镇" : "成为观测者" }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.bg-stage {
  position: absolute;
  inset: 0;
}

.bg-slide {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0;
  transition: opacity 1.6s ease-in-out;
  transform: scale(1.04);
}

.bg-slide.active {
  opacity: 1;
}

.bg-mask {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(40, 18, 10, 0.28),
    rgba(40, 18, 10, 0.52)
  );
}

.bg-dots {
  position: absolute;
  bottom: 26px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 14px;
  z-index: 3;
}

.dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.45);
  border: 2px solid rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.25s;
}

.dot:hover {
  transform: scale(1.25);
}

.dot.active {
  background: var(--maple-orange);
  border-color: #fff;
  box-shadow: 0 0 10px rgba(245, 166, 35, 0.8);
}

.login-card {
  position: relative;
  z-index: 2;
  width: 420px;
  padding: 42px 44px 38px;
  border-radius: 24px;
  background: rgba(255, 252, 247, 0.92);
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 60px rgba(60, 25, 10, 0.35);
  text-align: center;
}

.title {
  margin: 12px 0 4px;
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 6px;
  background: linear-gradient(135deg, var(--maple-red), var(--maple-orange));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.subtitle {
  margin: 0 0 18px;
  font-size: 14px;
  color: var(--maple-warm);
}

.tabs {
  margin-bottom: 6px;
}

.tabs :deep(.el-tabs__item) {
  font-size: 16px;
}

.submit {
  width: 100%;
  height: 48px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 4px;
  margin-top: 6px;
}
</style>
