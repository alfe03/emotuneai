// ─── EmoTuneAI Main Application ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

// ── State ────────────────────────────────────────────────────────────────────
let currentUser = null;
let currentResults = null;
let cameraStream = null;

// ── Init ─────────────────────────────────────────────────────────────────────
async function initApp() {
  setupNavigation();
  setupAuthForms();
  setupMoodActions();
  setupCameraActions();

  if (api.isLoggedIn()) {
    if (api.token === "demo-token") {
      currentUser = { id: 1, email: "demo@emotune.com", username: "Demo" };
      showApp();
    } else {
      try {
        currentUser = await api.getMe();
        showApp();
      } catch {
        api.logout();
        showAuth();
      }
    }
  } else {
    showAuth();
  }
}

// ── Navigation ───────────────────────────────────────────────────────────────
function setupNavigation() {
  document.querySelectorAll("[data-nav]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.nav;
      switchPage(target);
      // Active state
      document.querySelectorAll("[data-nav]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  document.getElementById("btn-logout").addEventListener("click", () => {
    api.logout();
    currentUser = null;
    showAuth();
  });
}

function switchPage(page) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  const el = document.getElementById(`page-${page}`);
  if (el) {
    el.classList.add("active");
    if (page === "history") loadHistory();
    if (page === "liked") loadLikedTracks();
  }
}

// ── Auth ─────────────────────────────────────────────────────────────────────
function showAuth() {
  document.getElementById("auth-screen").classList.add("active");
  document.getElementById("app-screen").classList.remove("active");
}

function showApp() {
  document.getElementById("auth-screen").classList.remove("active");
  document.getElementById("app-screen").classList.add("active");
  if (currentUser) {
    document.getElementById("user-greeting").textContent = currentUser.username || currentUser.email;
  }
  switchPage("mood");
  document.querySelector('[data-nav="mood"]').classList.add("active");
}

function setupAuthForms() {
  // Toggle between login/register
  document.getElementById("show-register").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("login-form").classList.remove("active");
    document.getElementById("register-form").classList.add("active");
  });
  document.getElementById("show-login").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("register-form").classList.remove("active");
    document.getElementById("login-form").classList.add("active");
  });

  // Login
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    const btn = e.target.querySelector("button[type=submit]");
    const errEl = document.getElementById("login-error");
    errEl.textContent = "";
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Giriş yapılıyor...';

    try {
      // Demo hesap kontrolü
      if (email === "demo@emotune.com" && password === "demo123") {
        api.setToken("demo-token");
        currentUser = { id: 1, email: "demo@emotune.com", username: "Demo" };
        showApp();
      } else {
        await api.login(email, password);
        currentUser = await api.getMe();
        showApp();
      }
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Giriş Yap";
    }
  });

  // Register
  document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("reg-email").value;
    const name = document.getElementById("reg-name").value;
    const password = document.getElementById("reg-password").value;
    const btn = e.target.querySelector("button[type=submit]");
    const errEl = document.getElementById("reg-error");
    errEl.textContent = "";
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Kayıt olunuyor...';

    try {
      await api.register(email, name, password);
      currentUser = await api.getMe();
      showApp();
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Kayıt Ol";
    }
  });
}

// ── Mood Analysis ────────────────────────────────────────────────────────────
function setupMoodActions() {
  // Tab switching
  document.querySelectorAll("[data-mood-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("[data-mood-tab]").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".mood-panel").forEach((p) => p.classList.remove("active"));
      document.getElementById(`panel-${tab.dataset.moodTab}`).classList.add("active");

      // Stop camera if switching away
      if (tab.dataset.moodTab !== "face") stopCamera();
    });
  });

  // Text analysis
  document.getElementById("btn-analyze-text").addEventListener("click", async () => {
    const text = document.getElementById("mood-text-input").value.trim();
    if (text.length < 3) {
      showToast("Lütfen en az 3 karakter girin.", "warning");
      return;
    }
    await performAnalysis(() => api.analyzeText(text));
  });

  // Manual mood
  document.querySelectorAll("[data-mood]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mood = btn.dataset.mood;
      await performAnalysis(() => api.manualMood(mood));
    });
  });
}

async function performAnalysis(analysisFn) {
  const resultsSection = document.getElementById("results-section");
  resultsSection.innerHTML = `
    <div class="loading-state">
      <div class="pulse-ring"></div>
      <p>Ruh haliniz analiz ediliyor...</p>
    </div>`;
  resultsSection.classList.add("active");

  try {
    const data = await analysisFn();
    currentResults = data;
    renderResults(data);
  } catch (err) {
    resultsSection.innerHTML = `
      <div class="error-state">
        <span class="error-icon">⚠️</span>
        <p>${err.message}</p>
      </div>`;
  }
}

function renderResults(data) {
  const moodIcons = {
    energetic: "⚡",
    calm: "🌊",
    intense: "🔥",
    chill: "😌",
  };
  const moodLabels = {
    energetic: "Enerjik",
    calm: "Sakin",
    intense: "Yoğun",
    chill: "Rahat",
  };
  const moodColors = {
    energetic: "var(--accent-energetic)",
    calm: "var(--accent-calm)",
    intense: "var(--accent-intense)",
    chill: "var(--accent-chill)",
  };

  const resultsSection = document.getElementById("results-section");
  const icon = moodIcons[data.mood_category] || "🎵";
  const label = moodLabels[data.mood_category] || data.mood_category;
  const color = moodColors[data.mood_category] || "var(--primary)";

  let tracksHTML = "";
  if (data.recommendations && data.recommendations.length > 0) {
    tracksHTML = data.recommendations
      .map(
        (track, i) => `
      <div class="track-card" style="animation-delay: ${i * 0.06}s">
        <div class="track-image">
          ${track.image_url ? `<img src="${track.image_url}" alt="${track.name}" loading="lazy">` : '<div class="track-placeholder">🎵</div>'}
        </div>
        <div class="track-info">
          <h4 class="track-name">${track.name}</h4>
          <p class="track-artist">${track.artist}</p>
          <p class="track-album">${track.album}</p>
        </div>
        <div class="track-actions">
          ${track.preview_url ? `<button class="btn-icon btn-play" onclick="playPreview('${track.preview_url}', this)" title="Önizle"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>` : ""}
          <a href="${track.spotify_url}" target="_blank" class="btn-icon btn-spotify" title="Spotify'da aç"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg></a>
        </div>
      </div>`
      )
      .join("");
  }

  resultsSection.innerHTML = `
    <div class="results-header">
      <div class="mood-badge" style="--mood-color: ${color}">
        <span class="mood-icon">${icon}</span>
        <div>
          <span class="mood-emotion">${data.emotion}</span>
          <span class="mood-label">${label}</span>
        </div>
        <div class="mood-confidence">
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${data.confidence}%; background: ${color}"></div>
          </div>
          <span>%${data.confidence.toFixed(1)}</span>
        </div>
      </div>
    </div>
    <h3 class="section-title">🎵 Önerilen Şarkılar</h3>
    <div class="tracks-grid">${tracksHTML}</div>
  `;
}

// ── Audio Preview ────────────────────────────────────────────────────────────
let currentAudio = null;
let currentPlayBtn = null;

function playPreview(url, btn) {
  // Stop existing
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
    if (currentPlayBtn) {
      currentPlayBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
      currentPlayBtn.classList.remove("playing");
    }
    if (currentPlayBtn === btn) {
      currentPlayBtn = null;
      return;
    }
  }

  currentAudio = new Audio(url);
  currentPlayBtn = btn;
  btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
  btn.classList.add("playing");

  currentAudio.play();
  currentAudio.addEventListener("ended", () => {
    btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
    btn.classList.remove("playing");
    currentAudio = null;
    currentPlayBtn = null;
  });
}

// ── Camera ───────────────────────────────────────────────────────────────────
function setupCameraActions() {
  document.getElementById("btn-start-camera").addEventListener("click", startCamera);
  document.getElementById("btn-capture").addEventListener("click", captureAndAnalyze);
}

async function startCamera() {
  const video = document.getElementById("camera-video");
  const placeholder = document.getElementById("camera-placeholder");

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 640, height: 480 } });
    video.srcObject = cameraStream;
    video.classList.add("active");
    placeholder.classList.remove("active");
    document.getElementById("btn-start-camera").style.display = "none";
    document.getElementById("btn-capture").style.display = "inline-flex";
  } catch {
    showToast("Kamera erişimi reddedildi.", "error");
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop());
    cameraStream = null;
  }
  const video = document.getElementById("camera-video");
  video.classList.remove("active");
  video.srcObject = null;
  document.getElementById("camera-placeholder").classList.add("active");
  document.getElementById("btn-start-camera").style.display = "inline-flex";
  document.getElementById("btn-capture").style.display = "none";
}

async function captureAndAnalyze() {
  const video = document.getElementById("camera-video");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  const base64 = canvas.toDataURL("image/jpeg").split(",")[1];
  stopCamera();
  await performAnalysis(() => api.analyzeFace(base64));
}

// ── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  const container = document.getElementById("history-list");
  container.innerHTML = '<div class="loading-state"><div class="pulse-ring"></div><p>Yükleniyor...</p></div>';

  try {
    const history = await api.getHistory();
    if (!history.length) {
      container.innerHTML = '<div class="empty-state"><span>📭</span><p>Henüz bir geçmiş yok.</p></div>';
      return;
    }

    const moodIcons = { energetic: "⚡", calm: "🌊", intense: "🔥", chill: "😌" };

    container.innerHTML = history
      .map(
        (item, i) => `
      <div class="history-card" style="animation-delay: ${i * 0.05}s">
        <div class="history-mood">
          <span class="history-icon">${moodIcons[item.mood_category] || "🎵"}</span>
          <div>
            <strong>${item.emotion}</strong>
            <span class="history-source">${item.source}</span>
          </div>
        </div>
        <div class="history-meta">
          <span class="history-confidence">%${item.confidence?.toFixed(1) || "N/A"}</span>
          <span class="history-date">${new Date(item.created_at).toLocaleDateString("tr-TR")}</span>
          <button class="btn-icon btn-delete" onclick="deleteHistoryItem(${item.id}, this)" title="Sil">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
          </button>
        </div>
      </div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<div class="error-state"><span class="error-icon">⚠️</span><p>${err.message}</p></div>`;
  }
}

async function deleteHistoryItem(id, btn) {
  const card = btn.closest(".history-card");
  try {
    await api.deleteHistory(id);
    card.style.transform = "translateX(100%)";
    card.style.opacity = "0";
    setTimeout(() => card.remove(), 300);
    showToast("Kayıt silindi.", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ── Liked Tracks ─────────────────────────────────────────────────────────────
async function loadLikedTracks() {
  const container = document.getElementById("liked-list");
  container.innerHTML = '<div class="loading-state"><div class="pulse-ring"></div><p>Yükleniyor...</p></div>';

  try {
    const tracks = await api.getLikedTracks();
    if (!tracks.length) {
      container.innerHTML = '<div class="empty-state"><span>💚</span><p>Henüz beğenilen şarkı yok.</p></div>';
      return;
    }

    container.innerHTML = tracks
      .map(
        (t, i) => `
      <div class="track-card" style="animation-delay: ${i * 0.06}s">
        <div class="track-image">
          ${t.image_url ? `<img src="${t.image_url}" alt="${t.track_name}" loading="lazy">` : '<div class="track-placeholder">🎵</div>'}
        </div>
        <div class="track-info">
          <h4 class="track-name">${t.track_name}</h4>
          <p class="track-artist">${t.artist_name}</p>
          <p class="track-album">${t.album_name || ""}</p>
        </div>
        <div class="track-actions">
          <a href="${t.spotify_url}" target="_blank" class="btn-icon btn-spotify" title="Spotify'da aç">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
          </a>
        </div>
      </div>`
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<div class="error-state"><span class="error-icon">⚠️</span><p>${err.message}</p></div>`;
  }
}

// ── Toast ────────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
  toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
