// ─── EmoTuneAI API Layer ─────────────────────────────────────────────────────
const API_BASE = "http://127.0.0.1:8000";

class EmoTuneAPI {
  constructor() {
    this.token = localStorage.getItem("emotune_token") || null;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  setToken(token) {
    this.token = token;
    localStorage.setItem("emotune_token", token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem("emotune_token");
  }

  isLoggedIn() {
    return !!this.token;
  }

  async request(endpoint, options = {}) {
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Bir hata oluştu." }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  // ── Auth ─────────────────────────────────────────────────────────────────────
  async register(email, name, password) {
    const data = await this.request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, username: name, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async login(email, password) {
    const data = await this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe() {
    return this.request("/api/auth/me");
  }

  logout() {
    this.clearToken();
  }

  // ── Mood ─────────────────────────────────────────────────────────────────────
  async analyzeFace(imageBase64, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/analyze/face", {
      method: "POST",
      body: JSON.stringify({ image_base64: imageBase64, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  async analyzeText(text, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/analyze/text", {
      method: "POST",
      body: JSON.stringify({ text, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  async manualMood(mood, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/manual", {
      method: "POST",
      body: JSON.stringify({ mood, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  // ── Music ────────────────────────────────────────────────────────────────────
  async likeTrack(trackId, action) {
    return this.request("/api/music/like", {
      method: "POST",
      body: JSON.stringify({ track_id: trackId, action }),
    });
  }

  async getLikedTracks() {
    return this.request("/api/music/liked");
  }

  // ── History ──────────────────────────────────────────────────────────────────
  async getHistory(limit = 20) {
    return this.request(`/api/history/?limit=${limit}`);
  }

  async getMoodGraph(days = 7) {
    return this.request(`/api/history/graph?days=${days}`);
  }

  async deleteHistory(id) {
    return this.request(`/api/history/${id}`, { method: "DELETE" });
  }
}

const api = new EmoTuneAPI();
