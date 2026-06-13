// Ortama göre API_BASE belirleme
let API_BASE = "";
if (window.location.hostname === "silver-readers-fold.loca.lt") {
    // Mobil test tüneli
    API_BASE = "https://a344f2855cc8ed.lhr.life";
} else if (window.location.hostname === "emotuneai.utkuaksu.com" || window.location.hostname.endsWith(".github.io")) {
    // GitHub Pages üzerinden çalışıyorsak ve backend localde tünelle çalışıyorsa
    // NOT: Tünel kapandığında/yeniden başlatıldığında bu adresi güncellemeniz gerekir.
    API_BASE = "https://a344f2855cc8ed.lhr.life";
} else if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.hostname.startsWith("192.") || window.location.hostname.startsWith("10.")) {
    // Local ortam (Frontend 8080, Backend 8000'de ise)
    if (window.location.port === "8080" || window.location.port === "3000") {
        API_BASE = `http://${window.location.hostname}:8000`;
    }
} else {
    // Canlı Sunucu (Nginx proxy kullanılan VPS'ler için)
    API_BASE = "";
}

class EmoTuneAPI {
  constructor() {
    this.token = localStorage.getItem("emotune_token") || null;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  setToken(token) {
    this.token = token;
    localStorage.setItem("emotune_token", token);
  }

  setAvatar(url) {
    localStorage.setItem("emotune_avatar", url);
  }

  getAvatar() {
    return localStorage.getItem("emotune_avatar") || null;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem("emotune_token");
    localStorage.removeItem("emotune_avatar");
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

  async changePassword(currentPassword, newPassword) {
    return this.request("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
  }

  async updateProfile(username, avatarUrl) {
    return this.request("/api/auth/update-profile", {
      method: "PUT",
      body: JSON.stringify({ username, avatar_url: avatarUrl }),
    });
  }

  async uploadAvatar(file) {
    const formData = new FormData();
    formData.append("file", file);
    
    const headers = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    
    const res = await fetch(`${API_BASE}/api/auth/upload-avatar`, {
      method: "POST",
      headers,
      body: formData
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Bir hata oluştu." }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    
    return res.json();
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

  async analyzeVideo(videoBase64, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/analyze/video", {
      method: "POST",
      body: JSON.stringify({ video_base64: videoBase64, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  async analyzeAudio(audioBase64, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/analyze/audio", {
      method: "POST",
      body: JSON.stringify({ audio_base64: audioBase64, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  async analyzeText(text, language = "mixed", contentType = "track", searchQuery = "", genre = "") {
    return this.request("/api/mood/analyze/text", {
      method: "POST",
      body: JSON.stringify({ text, language, content_type: contentType, search_query: searchQuery, genre }),
    });
  }

  async manualMood(mood, language = "mixed", contentType = "track", searchQuery = "", genre = "", requestedArtist = null, noSave = false) {
    return this.request("/api/mood/manual", {
      method: "POST",
      body: JSON.stringify({ mood, language, content_type: contentType, search_query: searchQuery, genre, requested_artist: requestedArtist, no_save: noSave }),
    });
  }

  // ── Music ────────────────────────────────────────────────────────────────────
  async likeTrack(trackObj, action) {
    // trackObj expects: { spotify_id, track_name, artist_name, album_name, image_url, spotify_url }
    return this.request("/api/music/like", {
      method: "POST",
      body: JSON.stringify({ ...trackObj, action }),
    });
  }

  async getLikedTracks() {
    return this.request("/api/music/liked");
  }

  async exportPlaylist(moodHistoryId, playlistName) {
    return this.request("/api/music/export-playlist", {
      method: "POST",
      body: JSON.stringify({ mood_history_id: moodHistoryId, playlist_name: playlistName }),
    });
  }

  async saveInternalPlaylist(moodHistoryId, playlistName) {
    return this.request("/api/music/save-internal-playlist", {
      method: "POST",
      body: JSON.stringify({ mood_history_id: moodHistoryId, playlist_name: playlistName }),
    });
  }

  async saveInternalPlaylist(moodHistoryId, playlistName) {
    return this.request("/api/music/save-internal-playlist", {
      method: "POST",
      body: JSON.stringify({ mood_history_id: moodHistoryId, playlist_name: playlistName }),
    });
  }

  async getSavedPlaylists() {
    return this.request("/api/music/saved-playlists");
  }

  async deleteSavedPlaylist(id) {
    return this.request(`/api/music/saved-playlists/${id}`, { method: "DELETE" });
  }

  async exportSavedPlaylist(savedPlaylistId) {
    return this.request("/api/music/export-saved-playlist", {
      method: "POST",
      body: JSON.stringify({ saved_playlist_id: savedPlaylistId }),
    });
  }

  // ── History ──────────────────────────────────────────────────────────────────
  async getHistory(skip = 0, limit = 5) {
    return this.request(`/api/history/?skip=${skip}&limit=${limit}`);
  }

  async getMoodGraph(days = 7) {
    return this.request(`/api/history/graph?days=${days}`);
  }

  async getHistoryAnalytics(days = 30) {
    return this.request(`/api/history/analytics?days=${days}`);
  }

  async deleteHistory(id) {
    return this.request(`/api/history/${id}`, { method: "DELETE" });
  }
}

const api = new EmoTuneAPI();
