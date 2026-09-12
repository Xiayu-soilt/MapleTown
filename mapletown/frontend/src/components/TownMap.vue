<script setup>
import { computed, reactive, ref } from "vue";
import { useSimStore } from "../stores/sim";

const props = defineProps({
  residents: { type: Array, default: () => [] },
});

const emit = defineEmits(["select-resident"]);
const sim = useSimStore();

const W = 320;
const H = 200;

const PAL = {
  grass: "#7ab648",
  grassDark: "#6aa63e",
  forest: "#5e9c3c",
  forestDark: "#4f8a32",
  park: "#8cc63f",
  parkDark: "#79b534",
  leafO: "#e8933f",
  leafR: "#d9703a",
  leafY: "#f2b94c",
  path: "#e0c187",
  pathEdge: "#c4a06a",
  wall: "#f5e6c8",
  wallWhite: "#fdfaf2",
  roofRed: "#c8402e",
  roofRedD: "#a33322",
  roofOrange: "#e8734a",
  roofOrangeD: "#c85a35",
  roofPurple: "#8a6bb5",
  roofPurpleD: "#6e5392",
  roofGreen: "#5a8f5a",
  roofGreenD: "#477547",
  roofSlate: "#6b7f95",
  roofSlateD: "#55687c",
  window: "#7ec3e0",
  windowLit: "#ffe9a8",
  door: "#7a4a2b",
  doorD: "#5f3a20",
  wood: "#8a5a33",
  woodD: "#6b4226",
  water: "#6db3d9",
  waterD: "#4f95bd",
  waterLight: "#a5d8ef",
  stone: "#b8b0a0",
  stoneD: "#98907f",
  soil: "#c9a24a",
  soilD: "#a98734",
  crop: "#8cc63f",
  skin: "#f5cfa0",
  hair: "#4a3728",
  smoke: "#e8e2d8",
  flag: "#e8402a",
};

const LOCATIONS = [
  { name: "枫叶公寓", kind: "apartment", x: 44, y: 34, w: 30, h: 38, ly: 59 },
  { name: "社区诊所", kind: "clinic", x: 112, y: 38, w: 24, h: 20, ly: 53 },
  { name: "枫语咖啡馆", kind: "cafe", x: 208, y: 36, w: 26, h: 22, ly: 53 },
  { name: "图书馆", kind: "library", x: 266, y: 42, w: 28, h: 24, ly: 72 },
  { name: "枫林小径", kind: "forest", x: 40, y: 88, w: 56, h: 48, ly: 122, line: [40, 70, 36, 118] },
  { name: "老街市集", kind: "market", x: 126, y: 113, w: 60, h: 34, ly: 140, line: [102, 113, 150, 113] },
  { name: "镇广场", kind: "plaza", x: 196, y: 74, w: 44, h: 36, ly: 99 },
  { name: "律师事务所", kind: "office", x: 250, y: 108, w: 26, h: 20, ly: 123 },
  { name: "满堂香面包房", kind: "bakery", x: 196, y: 126, w: 26, h: 20, ly: 142 },
  { name: "白日梦想工作室", kind: "studio", x: 250, y: 158, w: 26, h: 18, ly: 181 },
  { name: "小学", kind: "school", x: 160, y: 160, w: 28, h: 20, ly: 185 },
  { name: "镇公园", kind: "park", x: 50, y: 150, w: 68, h: 46, ly: 183 },
  { name: "试验田", kind: "field", x: 112, y: 176, w: 48, h: 28, ly: 160 },
  { name: "河堤步道", kind: "walk", x: 292, y: 112, w: 8, h: 148, ly: 0, line: [292, 62, 292, 166] },
];

const LAMPS = [
  { x: 26, y: 56 }, { x: 92, y: 56 }, { x: 156, y: 56 }, { x: 222, y: 56 }, { x: 282, y: 56 },
  { x: 289, y: 44 }, { x: 289, y: 104 }, { x: 289, y: 164 },
  { x: 178, y: 60 }, { x: 212, y: 60 }, { x: 178, y: 86 }, { x: 212, y: 86 },
];

const SPARKLES = [
  { x: 308, y: 22 }, { x: 310, y: 66 }, { x: 306, y: 112 }, { x: 311, y: 150 }, { x: 307, y: 184 },
  { x: 195, y: 71 }, { x: 199, y: 75 }, { x: 30, y: 161 },
];

const TREES = [
  [20, 72, 0], [32, 68, 1], [50, 70, 2], [24, 84, 1], [44, 86, 0], [58, 80, 2],
  [28, 98, 2], [48, 100, 0], [62, 94, 1], [38, 108, 2],
  [24, 140, 0], [40, 136, 2], [60, 142, 0], [72, 156, 1], [30, 166, 2],
  [72, 52, 1], [132, 52, 0], [172, 40, 2], [284, 22, 0], [226, 128, 1],
  [222, 148, 0], [176, 144, 2], [136, 142, 0],
];

const LEAVES = [
  [16, 66], [26, 78], [42, 64], [56, 76], [64, 90], [50, 94], [34, 104], [46, 112],
  [66, 140], [34, 148], [56, 158], [74, 168], [90, 168], [128, 60], [168, 44],
  [228, 50], [230, 130], [216, 120], [178, 152], [140, 148],
];

// ---------- 昼夜 ----------
const phase = computed(() => {
  const t = sim.state.sim_time || "";
  const h = (parseInt(t.slice(11, 13), 10) || 0) + (parseInt(t.slice(14, 16), 10) || 0) / 60;
  if (h >= 7 && h < 17) return "day";
  if (h >= 17 && h < 19.5) return "dusk";
  return "night";
});
const isNight = computed(() => phase.value === "night");
const phaseMeta = { day: { icon: "☀", text: "白天" }, dusk: { icon: "🌇", text: "黄昏" }, night: { icon: "🌙", text: "夜晚" } };

// ---------- 像素场景 ----------
function buildScene(night) {
  const R = [];
  const px = (x, y, w, h, f) => R.push({ x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h), f });
  const win = (x, y) => px(x, y, 4, 4, night && (x * 7 + y * 13) % 5 !== 0 ? PAL.windowLit : PAL.window);

  // 草地与纹理
  px(0, 0, W, H, PAL.grass);
  [[10, 8], [58, 14], [128, 24], [200, 8], [268, 16], [96, 40], [160, 34], [240, 30],
   [16, 44], [70, 66], [140, 70], [216, 44], [286, 36], [12, 116], [80, 124], [150, 128],
   [210, 100], [280, 120], [60, 186], [150, 186], [230, 188], [110, 50]].forEach(([x, y]) => px(x, y, 3, 2, PAL.grassDark));

  // 森林/公园/田野/广场 地面
  px(12, 62, 56, 50, PAL.forest);
  px(16, 127, 68, 46, PAL.park);
  px(88, 162, 48, 28, PAL.soil);
  for (let ty = 56; ty < 92; ty += 4) {
    for (let tx = 174; tx < 218; tx += 4) {
      px(tx, ty, 4, 4, ((tx + ty) / 4) % 2 ? PAL.stone : PAL.stoneD);
    }
  }

  // 道路
  const road = (x, y, w, h) => {
    px(x, y - 1, w, 1, PAL.pathEdge);
    px(x, y + h, w, 1, PAL.pathEdge);
    px(x, y, w, h, PAL.path);
    if (w > h) {
      px(x, y - 1, 1, h + 2, PAL.pathEdge);
      px(x + w - 1, y - 1, 1, h + 2, PAL.pathEdge);
    }
  };
  road(20, 60, 276, 4);
  road(84, 110, 212, 4);
  road(42, 53, 4, 8);
  road(110, 48, 4, 13);
  road(220, 64, 4, 35);
  road(196, 92, 4, 25);
  road(250, 114, 4, 36);
  road(100, 114, 4, 49);
  road(158, 114, 4, 37);
  // 枫林小径蜿蜒土路
  px(44, 64, 4, 6, PAL.path);
  px(38, 72, 4, 8, PAL.path);
  px(36, 80, 4, 10, PAL.path);
  px(40, 92, 4, 10, PAL.path);
  px(42, 102, 4, 12, PAL.path);
  px(44, 114, 4, 13, PAL.path);

  // 河流 + 河堤步道
  px(298, 0, 2, H, PAL.stoneD);
  px(300, 0, 20, H, PAL.water);
  [[304, 18], [311, 34], [305, 58], [312, 80], [306, 102], [313, 128], [304, 152], [310, 176]].forEach(
    ([x, y]) => px(x, y, 3, 1, PAL.waterLight)
  );
  px(288, 20, 8, 170, PAL.stone);
  px(288, 20, 2, 170, PAL.stoneD);
  px(294, 94, 12, 8, PAL.wood);
  px(294, 94, 12, 1, PAL.woodD);
  // 小鸭
  px(307, 40, 3, 2, "#f5f0e0");
  px(309, 39, 2, 2, "#f5f0e0");
  px(311, 40, 1, 1, PAL.roofOrange);
  px(311, 90, 3, 2, "#f5f0e0");
  px(313, 89, 2, 2, "#f5f0e0");

  // 喷泉
  px(189, 67, 14, 14, PAL.stoneD);
  px(191, 69, 10, 10, PAL.water);
  px(195, 71, 2, 2, PAL.waterLight);
  // 公园池塘
  px(24, 156, 18, 12, PAL.stoneD);
  px(26, 158, 14, 8, PAL.water);
  // 公园长椅
  px(42, 150, 10, 2, PAL.wood);
  px(42, 152, 1, 3, PAL.woodD);
  px(51, 152, 1, 3, PAL.woodD);
  // 田野作物 + 稻草人
  for (let ry = 166; ry < 188; ry += 5) {
    for (let rx = 92; rx < 132; rx += 4) px(rx, ry, 2, 2, (rx + ry) % 3 ? PAL.crop : PAL.leafY);
  }
  px(129, 168, 1, 10, PAL.woodD);
  px(125, 172, 9, 1, PAL.woodD);
  px(127, 165, 5, 4, PAL.skin);
  px(126, 164, 7, 1, PAL.leafY);

  // 市集摊位
  const stall = (x, y, c) => {
    for (let i = 0; i < 7; i++) px(x + i * 2, y, 2, 3, i % 2 ? "#fdfaf2" : c);
    px(x, y + 3, 1, 6, PAL.woodD);
    px(x + 13, y + 3, 1, 6, PAL.woodD);
    px(x - 1, y + 7, 16, 4, PAL.wood);
    px(x + 1, y + 6, 2, 1, PAL.leafR);
    px(x + 6, y + 6, 2, 1, PAL.leafY);
    px(x + 10, y + 6, 2, 1, PAL.windowLit);
  };
  stall(100, 96, PAL.roofRed);
  stall(118, 96, PAL.roofOrange);
  stall(136, 96, PAL.leafY);
  stall(104, 118, PAL.roofPurple);
  stall(136, 118, PAL.roofGreen);
  px(154, 118, 4, 4, PAL.wood);
  px(158, 120, 4, 4, PAL.wood);

  // 建筑
  const gable = (cx, top, w, c, cd) => {
    for (let i = 0; i < 4; i++) {
      const rw = 2 * Math.round((w * (i + 1)) / 8);
      px(cx - rw / 2, top + i * 2, rw, 2, i === 3 ? cd : c);
    }
    px(cx - w / 2 - 1, top + 8, w + 2, 1, cd);
  };
  const doorOf = (cx, bottom) => {
    px(cx - 3, bottom - 6, 6, 6, PAL.door);
    px(cx + 1, bottom - 4, 1, 1, PAL.doorD);
  };

  for (const loc of LOCATIONS) {
    const { kind, x: cx, y: cy, w, h } = loc;
    const top = Math.round(cy - h / 2);
    const bottom = Math.round(cy + h / 2);
    const left = Math.round(cx - w / 2);

    if (kind === "apartment") {
      px(left - 1, top, w + 2, 3, PAL.roofRedD);
      px(left, top + 3, w, 2, PAL.roofRed);
      px(left, top + 5, w, h - 5, PAL.wall);
      for (const wy of [top + 8, top + 16, top + 24]) {
        win(left + 4, wy);
        win(left + 13, wy);
        win(left + 22, wy);
      }
      doorOf(cx, bottom);
      px(cx - 4, bottom, 8, 1, PAL.stone);
      continue;
    }

    if (kind === "cafe") {
      px(left, top + 8, w, h - 8, PAL.wall);
      gable(cx, top, w, PAL.roofOrange, PAL.roofOrangeD);
      for (let i = 0; i < 9; i++) px(left + 1 + i * 3, top + 9, 3, 3, i % 2 ? "#fdfaf2" : PAL.roofRed);
      win(left + 3, top + 14);
      win(left + w - 7, top + 14);
      doorOf(cx, bottom);
      px(198, 52, 5, 3, PAL.wood);
      px(195, 53, 2, 2, PAL.woodD);
      px(204, 53, 2, 2, PAL.woodD);
      continue;
    }

    if (kind === "clinic") {
      px(left, top + 8, w, h - 8, PAL.wallWhite);
      gable(cx, top, w, PAL.roofSlate, PAL.roofSlateD);
      px(cx - 3, top + 10, 6, 2, PAL.flag);
      px(cx - 1, top + 8, 2, 6, PAL.flag);
      win(left + 3, top + 14);
      win(left + w - 7, top + 14);
      doorOf(cx, bottom);
      continue;
    }

    if (kind === "library") {
      px(left, top + 8, w, h - 8, PAL.wall);
      gable(cx, top, w, PAL.roofPurple, PAL.roofPurpleD);
      for (const wx of [left + 4, cx - 2, left + w - 8]) px(wx, top + 12, 4, 6, night ? PAL.windowLit : PAL.window);
      px(left + 3, bottom - 8, 2, 8, PAL.stone);
      px(left + w - 5, bottom - 8, 2, 8, PAL.stone);
      doorOf(cx, bottom);
      continue;
    }

    if (kind === "office") {
      px(left, top + 8, w, h - 8, PAL.wall);
      gable(cx, top, w, PAL.roofSlate, PAL.roofSlateD);
      win(left + 3, top + 12);
      win(left + w - 7, top + 12);
      px(cx - 4, top + 12, 8, 2, PAL.roofSlateD);
      doorOf(cx, bottom);
      continue;
    }

    if (kind === "bakery") {
      px(left, top + 8, w, h - 8, PAL.wall);
      gable(cx, top, w, PAL.roofRed, PAL.roofRedD);
      px(202, top - 6, 4, 7, PAL.stoneD);
      win(left + 3, top + 12);
      win(left + w - 7, top + 12);
      doorOf(cx, bottom);
      px(left + 2, top + 19, w - 4, 1, PAL.leafY);
      continue;
    }

    if (kind === "studio") {
      px(left - 1, top, w + 2, 3, PAL.roofPurpleD);
      px(left, top + 3, w, h - 3, PAL.wall);
      win(left + 3, top + 7);
      win(left + w - 7, top + 7);
      px(left + 5, top + 13, 2, 2, PAL.roofRed);
      px(left + 12, top + 13, 2, 2, PAL.leafY);
      px(left + 19, top + 13, 2, 2, PAL.roofSlate);
      doorOf(cx, bottom);
      continue;
    }

    if (kind === "school") {
      px(left, top + 8, w, h - 8, PAL.wall);
      gable(cx, top, w, PAL.roofGreen, PAL.roofGreenD);
      for (const wx of [left + 4, cx - 2, left + w - 8]) win(wx, top + 12);
      doorOf(cx, bottom);
      px(143, 138, 1, 12, PAL.stoneD);
      px(144, 138, 5, 3, PAL.flag);
      continue;
    }
  }

  // 树
  const tree = (x, y, variant) => {
    const c = [PAL.leafO, PAL.leafR, PAL.leafY][variant];
    const cd = variant === 2 ? PAL.leafO : PAL.leafR;
    px(x - 4, y - 13, 9, 3, c);
    px(x - 5, y - 10, 11, 3, c);
    px(x - 5, y - 7, 11, 2, cd);
    px(x - 2, y - 12, 2, 2, variant === 2 ? "#fff3d9" : PAL.leafY);
    px(x - 1, y - 5, 2, 5, PAL.woodD);
  };
  TREES.forEach(([x, y, v]) => tree(x, y, v));

  // 落叶
  LEAVES.forEach(([x, y], i) => px(x, y, 1, 1, i % 2 ? PAL.leafO : PAL.leafR));

  // 路灯（灯杆，灯头夜间发光）
  for (const l of LAMPS) {
    px(l.x, l.y, 2, 5, PAL.stoneD);
    px(l.x - 1, l.y - 2, 4, 3, night ? PAL.windowLit : "#d8c9a8");
  }

  return R;
}

const scene = computed(() => buildScene(isNight.value));

// ---------- 居民像素小人 ----------
const HAIRS = ["#4a3728", "#2f2a26", "#6b4226", "#8a3b2a"];

function spriteRects(x, y, body, hair) {
  return [
    { x: x - 2, y: y - 11, w: 5, h: 2, f: hair },
    { x: x - 2, y: y - 9, w: 5, h: 3, f: PAL.skin },
    { x: x - 4, y: y - 6, w: 1, h: 3, f: PAL.skin },
    { x: x + 3, y: y - 6, w: 1, h: 3, f: PAL.skin },
    { x: x - 3, y: y - 6, w: 7, h: 4, f: body },
    { x: x - 2, y: y - 2, w: 2, h: 2, f: "#4a3728" },
    { x: x + 1, y: y - 2, w: 2, h: 2, f: "#4a3728" },
  ];
}

const locationMap = computed(() => new Map(LOCATIONS.map((l) => [l.name, l])));

const placed = computed(() => {
  const byLoc = new Map();
  for (const r of props.residents) {
    if (!locationMap.value.has(r.current_location)) continue;
    const list = byLoc.get(r.current_location) || [];
    list.push(r);
    byLoc.set(r.current_location, list);
  }
  const result = [];
  for (const [name, list] of byLoc) {
    const loc = locationMap.value.get(name);
    if (loc.line) {
      const [x1, y1, x2, y2] = loc.line;
      list.forEach((r, i) => {
        const t = list.length === 1 ? 0.5 : i / (list.length - 1);
        result.push({ resident: r, x: x1 + (x2 - x1) * t, y: y1 + (y2 - y1) * t });
      });
    } else {
      const radius = loc.kind === "plaza" ? 16 : loc.h >= 30 ? loc.h / 2 + 5 : Math.max(13, loc.h / 2 + 4);
      list.forEach((r, i) => {
        const angle = (i / list.length) * Math.PI * 2 - Math.PI / 2;
        result.push({
          resident: r,
          x: loc.x + Math.cos(angle) * radius * 0.85,
          y: loc.y + Math.sin(angle) * radius,
        });
      });
    }
  }
  return result;
});

// ---------- 视图：拖拽 / 缩放 / 分区导航 ----------
const viewport = ref(null);
const view = reactive({ z: 1, x: 0, y: 0 });
const dragging = ref(false);
const dragMoved = ref(0);
let last = null;

function clampView() {
  const el = viewport.value;
  if (!el) return;
  const { width, height } = el.getBoundingClientRect();
  const base = Math.min(width / W, height / H);
  const s = base * view.z;
  view.x = W * s <= width ? (width - W * s) / 2 : Math.max(width - W * s, Math.min(0, view.x));
  view.y = H * s <= height ? (height - H * s) / 2 : Math.max(height - H * s, Math.min(0, view.y));
}

function onPointerDown(e) {
  dragging.value = true;
  dragMoved.value = 0;
  last = { x: e.clientX, y: e.clientY };
  e.currentTarget.setPointerCapture?.(e.pointerId);
}
function onPointerMove(e) {
  if (!dragging.value || !last) return;
  const dx = e.clientX - last.x;
  const dy = e.clientY - last.y;
  dragMoved.value += Math.abs(dx) + Math.abs(dy);
  view.x += dx;
  view.y += dy;
  last = { x: e.clientX, y: e.clientY };
  clampView();
}
function onPointerUp() {
  dragging.value = false;
  last = null;
}
function onWheel(e) {
  const el = viewport.value.getBoundingClientRect();
  const mx = e.clientX - el.left;
  const my = e.clientY - el.top;
  const nz = Math.max(1, Math.min(4, view.z * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
  const k = nz / view.z;
  view.x = mx - k * (mx - view.x);
  view.y = my - k * (my - view.y);
  view.z = nz;
  clampView();
}
function focusDistrict(name) {
  const loc = locationMap.value.get(name);
  if (!loc || !viewport.value) return;
  const { width, height } = viewport.value.getBoundingClientRect();
  const base = Math.min(width / W, height / H);
  view.z = 1.9;
  const s = base * view.z;
  view.x = width / 2 - loc.x * s;
  view.y = height / 2 - loc.y * s;
  clampView();
}
function resetView() {
  view.z = 1;
  view.x = 0;
  view.y = 0;
  clampView();
}

const DISTRICTS = [
  { label: "镇中心", loc: "镇广场" },
  { label: "老街市集", loc: "老街市集" },
  { label: "河堤步道", loc: "河堤步道" },
  { label: "枫林小径", loc: "枫林小径" },
  { label: "镇公园", loc: "镇公园" },
];

function trySelect(r) {
  if (dragMoved.value < 5) emit("select-resident", r);
}
</script>

<template>
  <div class="map-wrap">
    <div
      ref="viewport"
      class="map-viewport"
      :class="{ grabbing: dragging }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @wheel.prevent="onWheel"
    >
      <svg
        viewBox="0 0 320 200"
        class="town-svg"
        shape-rendering="crispEdges"
        :style="{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})` }"
        role="img"
        aria-label="枫叶镇像素地图"
      >
        <rect v-for="(r, i) in scene" :key="i" :x="r.x" :y="r.y" :width="r.w" :height="r.h" :fill="r.f" />

        <!-- 动效：波光 / 喷泉 / 炊烟 -->
        <rect
          v-for="(s, i) in SPARKLES"
          :key="'sp' + i"
          class="twinkle"
          :x="s.x"
          :y="s.y"
          width="2"
          height="1"
          fill="#fff"
          :style="{ animationDelay: (i * 0.35) + 's' }"
        />
        <g class="smoke">
          <rect x="203" y="103" width="2" height="2" :fill="PAL.smoke" />
          <rect x="204" y="100" width="2" height="2" :fill="PAL.smoke" />
          <rect x="202" y="97" width="2" height="2" :fill="PAL.smoke" />
        </g>

        <!-- 昼夜光照 -->
        <rect v-if="phase === 'dusk'" x="0" y="0" width="320" height="200" fill="rgba(255,140,50,0.16)" pointer-events="none" />
        <rect v-if="isNight" x="0" y="0" width="320" height="200" fill="rgba(24,32,78,0.45)" pointer-events="none" />
        <g v-if="isNight" pointer-events="none">
          <circle v-for="(l, i) in LAMPS" :key="'gl' + i" :cx="l.x + 1" :cy="l.y - 1" r="11" fill="url(#lamp-glow)" opacity="0.55" />
        </g>

        <!-- 地点标签 -->
        <text
          v-for="loc in LOCATIONS.filter((l) => l.ly > 0)"
          :key="'lbl' + loc.name"
          :x="loc.x"
          :y="loc.ly"
          class="loc-label"
          pointer-events="none"
        >
          {{ loc.name }}
        </text>

        <!-- 居民像素小人 -->
        <g
          v-for="p in placed"
          :key="p.resident.id"
          class="resident"
          :style="{ transform: `translate(${p.x}px, ${p.y}px)` }"
          @click="trySelect(p.resident)"
        >
          <title>{{ p.resident.name }} · {{ p.resident.identity }} @ {{ p.resident.current_location }}</title>
          <rect x="-6" y="-14" width="12" height="16" fill="transparent" />
          <rect x="-3" y="1" width="7" height="1" fill="rgba(0,0,0,0.25)" />
          <g class="bob">
            <rect
              v-for="(r, i) in spriteRects(0, 0, p.resident.avatar_color, HAIRS[p.resident.id % HAIRS.length])"
              :key="i"
              :x="r.x"
              :y="r.y"
              :width="r.w"
              :height="r.h"
              :fill="r.f"
            />
          </g>
          <text y="8" class="resident-name" pointer-events="none">{{ p.resident.name }}</text>
        </g>

        <defs>
          <radialGradient id="lamp-glow">
            <stop offset="0%" stop-color="#ffe9a8" stop-opacity="0.9" />
            <stop offset="100%" stop-color="#ffe9a8" stop-opacity="0" />
          </radialGradient>
        </defs>
      </svg>
    </div>

    <!-- 地图工具条 -->
    <div class="map-toolbar">
      <div class="districts">
        <button v-for="d in DISTRICTS" :key="d.loc" class="district-btn" @click="focusDistrict(d.loc)">
          {{ d.label }}
        </button>
      </div>
      <div class="view-btns">
        <span class="phase-badge" :title="'当前时段：' + phaseMeta[phase].text">
          {{ phaseMeta[phase].icon }} {{ phaseMeta[phase].text }}
        </span>
        <button class="district-btn" @click="resetView">⟲ 复位</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-wrap {
  position: relative;
  height: 100%;
  background: #5e9c3c;
}

.map-viewport {
  height: 100%;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.map-viewport.grabbing {
  cursor: grabbing;
}

.town-svg {
  width: 100%;
  height: 100%;
  display: block;
  transform-origin: 0 0;
}

.loc-label {
  font-size: 5px;
  font-weight: 700;
  fill: #fff8ec;
  text-anchor: middle;
  paint-order: stroke;
  stroke: rgba(61, 43, 31, 0.9);
  stroke-width: 1.3px;
  font-family: "Microsoft YaHei", sans-serif;
}

.resident {
  cursor: pointer;
  transition: transform 1.4s ease-in-out;
}

.resident:hover {
  filter: drop-shadow(0 0 3px rgba(255, 233, 168, 0.9));
}

.resident-name {
  font-size: 4.2px;
  font-weight: 700;
  fill: #ffffff;
  text-anchor: middle;
  paint-order: stroke;
  stroke: rgba(45, 25, 10, 0.95);
  stroke-width: 1.1px;
  font-family: "Microsoft YaHei", sans-serif;
}

.bob {
  animation: bob 0.55s steps(1) infinite alternate;
}

@keyframes bob {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-1px);
  }
}

.twinkle {
  animation: twinkle 2.2s infinite;
}

@keyframes twinkle {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.smoke rect {
  animation: rise 3s infinite;
}

.smoke rect:nth-child(2) {
  animation-delay: 1s;
}

.smoke rect:nth-child(3) {
  animation-delay: 2s;
}

@keyframes rise {
  0% {
    transform: translateY(0);
    opacity: 0.85;
  }
  100% {
    transform: translateY(-6px);
    opacity: 0;
  }
}

.map-toolbar {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  pointer-events: none;
}

.districts,
.view-btns {
  display: flex;
  gap: 6px;
  pointer-events: auto;
}

.district-btn {
  font-size: 13px;
  font-weight: 600;
  color: #3d2b1f;
  background: rgba(255, 250, 240, 0.92);
  border: 2px solid #3d2b1f;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  box-shadow: 2px 2px 0 rgba(61, 43, 31, 0.8);
  transition: all 0.1s;
}

.district-btn:hover {
  background: #ffe9c8;
}

.district-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(61, 43, 31, 0.8);
}

.phase-badge {
  font-size: 13px;
  font-weight: 700;
  color: #fff8ec;
  background: rgba(45, 30, 18, 0.85);
  border-radius: 6px;
  padding: 6px 12px;
  border: 2px solid rgba(255, 248, 236, 0.5);
}
</style>
