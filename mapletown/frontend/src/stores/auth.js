import { defineStore } from "pinia";
import { api, setToken, getToken } from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: getToken(),
    username: localStorage.getItem("mapletown_username") || "",
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    async login(username, password) {
      const data = await api.login({ username, password });
      this._save(data.access_token, username);
    },
    async register(username, email, password) {
      await api.register({ username, email, password });
      const data = await api.login({ username, password });
      this._save(data.access_token, username);
    },
    logout() {
      setToken("");
      this.token = "";
      this.username = "";
      localStorage.removeItem("mapletown_username");
    },
    _save(token, username) {
      setToken(token);
      this.token = token;
      this.username = username;
      localStorage.setItem("mapletown_username", username);
    },
  },
});
