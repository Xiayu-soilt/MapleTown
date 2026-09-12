const BASE = "/api/v1";

let token = localStorage.getItem("mapletown_token") || "";

export function setToken(value) {
  token = value || "";
  if (value) localStorage.setItem("mapletown_token", value);
  else localStorage.removeItem("mapletown_token");
}

export function getToken() {
  return token;
}

async function request(path, { method = "GET", body, params } = {}) {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  }
  const resp = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 401) {
    setToken("");
    window.location.href = "/login";
    throw new Error("未登录或登录已过期");
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      if (data.detail) detail = String(data.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export const api = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  simState: () => request("/sim/state"),
  simControl: (action, value) => request("/sim/control", { method: "POST", body: { action, value } }),
  residents: () => request("/residents"),
  events: (limit = 50) => request("/events", { params: { limit } }),
};
