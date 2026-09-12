import { defineStore } from "pinia";
import { api } from "../api/client";

export const EVENT_STYLES = {
  tick: { label: "心跳", color: "#909399", icon: "⏱" },
  system: { label: "系统", color: "#909399", icon: "⚙" },
  plan: { label: "规划", color: "#7c5cff", icon: "📋" },
  act: { label: "行动", color: "#3c8c5a", icon: "🏃" },
  move: { label: "移动", color: "#4a90d9", icon: "🚶" },
  chat: { label: "对话", color: "#e8734a", icon: "💬" },
  conversation_end: { label: "告别", color: "#b06a2c", icon: "🤝" },
  reflect: { label: "反思", color: "#d4380d", icon: "💭" },
};

const MAX_FEED = 200;

export const useSimStore = defineStore("sim", {
  state: () => ({
    state: { sim_time: "", tick: 0, speed: 1, running: false, sim_day: 1 },
    residents: [],
    feed: [],
    connected: false,
    _source: null,
    _refreshTimer: null,
  }),

  getters: {
    simClock: (s) => {
      if (!s.state.sim_time) return "—";
      const t = s.state.sim_time.slice(11, 16);
      return `第 ${s.state.sim_day} 天 ${t}`;
    },
  },

  actions: {
    async refreshState() {
      this.state = await api.simState();
    },
    async refreshResidents() {
      this.residents = await api.residents();
    },
    async refreshFeed() {
      const events = await api.events(60);
      this.feed = events.slice().reverse();
    },

    async control(action, value) {
      await api.simControl(action, value);
      await this.refreshState();
      if (action === "speed") await this.refreshState();
    },

    connectStream() {
      if (this._source) return;
      const source = new EventSource("/api/v1/stream/feed");
      this._source = source;

      source.addEventListener("open", () => {
        this.connected = true;
      });

      source.addEventListener("tick", (e) => {
        try {
          const data = JSON.parse(e.data);
          this.state = { ...this.state, ...data };
        } catch {
          /* ignore */
        }
      });

      source.addEventListener("ping", () => {
        this.connected = true;
      });

      for (const type of Object.keys(EVENT_STYLES)) {
        if (type === "tick") continue;
        source.addEventListener(type, (e) => this._ingest(type, e));
      }

      source.addEventListener("error", () => {
        this.connected = false;
      });
    },

    disconnectStream() {
      if (this._source) {
        this._source.close();
        this._source = null;
      }
      this.connected = false;
      if (this._refreshTimer) {
        clearTimeout(this._refreshTimer);
        this._refreshTimer = null;
      }
    },

    _ingest(type, e) {
      let data = {};
      try {
        data = JSON.parse(e.data);
      } catch {
        /* ignore */
      }
      this.feed.unshift({ ...data, type });
      if (this.feed.length > MAX_FEED) this.feed.length = MAX_FEED;
      if (type === "move" || type === "act") this._scheduleResidentRefresh();
    },

    // 移动/行动事件密集时合并刷新，避免打爆接口
    _scheduleResidentRefresh() {
      if (this._refreshTimer) return;
      this._refreshTimer = setTimeout(async () => {
        this._refreshTimer = null;
        try {
          await this.refreshResidents();
        } catch {
          /* 后端重启等场景下静默失败 */
        }
      }, 2500);
    },
  },
});
