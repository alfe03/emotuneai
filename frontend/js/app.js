// ─── EmoTuneAI Main Application ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

// ── State ────────────────────────────────────────────────────────────────────
let currentUser = null;
let currentResults = null;
let cameraStream = null;
let selectedLanguage = "mixed";       // "tr" | "en" | "mixed"
let selectedContentType = "track";    // "track" | "playlist" | "podcast"
let selectedGenre = "";               // "" (Tümü) | "pop" | "rap" | "rock" vs.
let lastMoodCategory = null;          // Son analiz edilen mood (filtre değişince tekrar fetch için)
let lastEmotion = null;
let lastSearchQuery = "";             // Sonuçlar içinde arama yapmak için (örn: "Duman")
let lastRequestedArtist = null;       // Son algılanan veya filtrelenen sanatçı ismi


// ── Init ─────────────────────────────────────────────────────────────────────
async function initApp() {
  setupNavigation();
  setupAuthForms();
  setupMoodActions();
  setupCameraActions();
  setupLanguageFilter();

  // Check URL for token (from Spotify OAuth redirect)
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  const errorFromUrl = urlParams.get('error');
  const avatarFromUrl = urlParams.get('avatar');

  if (errorFromUrl) {
    setTimeout(() => {
      showToast("Spotify girişi iptal edildi veya bir hata oluştu.", "error");
    }, 500);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (tokenFromUrl) {
    api.setToken(tokenFromUrl);
    if (avatarFromUrl) {
      api.setAvatar(avatarFromUrl);
    }
    // Remove token from URL for cleaner history
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (api.isLoggedIn()) {
    try {
      currentUser = await api.getMe();
      const storedAvatar = api.getAvatar();
      if (storedAvatar) {
        setUserAvatar(storedAvatar);
      }
      showApp();
    } catch {
      api.logout();
      showAuth();
    }
  } else {
    showAuth();
  }
}

function setUserAvatar(avatarUrl) {
  const avatarEl = document.getElementById("user-avatar");
  if (!avatarEl) return;
  if (avatarUrl) {
    avatarEl.style.backgroundImage = `url('${avatarUrl}')`;
    avatarEl.classList.add("has-image");
    avatarEl.textContent = "";
  } else {
    avatarEl.style.backgroundImage = "";
    avatarEl.classList.remove("has-image");
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

  // Sidebar toggle
  const toggleBtn = document.getElementById("btn-toggle-sidebar");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      document.getElementById("sidebar").classList.toggle("collapsed");
      const isCollapsed = document.getElementById("sidebar").classList.contains("collapsed");
      localStorage.setItem("sidebarCollapsed", isCollapsed);
    });
    
    // Yükleme sırasında localStorage kontrolü
    if (localStorage.getItem("sidebarCollapsed") === "true") {
      document.getElementById("sidebar").classList.add("collapsed");
    }
  }

  document.getElementById("btn-logout").addEventListener("click", () => {
    api.logout();
    currentUser = null;
    localStorage.removeItem("lastPage");
    showAuth();
  });
}

function switchPage(page) {
  localStorage.setItem("lastPage", page);
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
    if (!api.getAvatar()) {
      const initial = (currentUser.username || currentUser.email || "U").trim().charAt(0).toUpperCase();
      const avatarEl = document.getElementById("user-avatar");
      if (avatarEl) {
        avatarEl.textContent = initial || "U";
      }
    }
  }
  const lastPage = localStorage.getItem("lastPage") || "mood";
  switchPage(lastPage);
  document.querySelectorAll("[data-nav]").forEach((b) => b.classList.remove("active"));
  const activeNav = document.querySelector(`[data-nav="${lastPage}"]`);
  if (activeNav) {
    activeNav.classList.add("active");
  }
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

  // Spotify Login redirects
  const spotifyLoginFn = () => {
    const redirect = encodeURIComponent(window.location.origin + "/index.html");
    window.location.href = `http://127.0.0.1:8000/api/auth/spotify/login?redirect=${redirect}`;
  };
  const spotifyBtn = document.getElementById("btn-spotify-login");
  if(spotifyBtn) spotifyBtn.addEventListener("click", spotifyLoginFn);

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
      await api.login(email, password);
      currentUser = await api.getMe();
      showApp();
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
  const moodTextarea = document.getElementById("mood-text-input");
  if (moodTextarea) {
    const autoResize = () => {
      moodTextarea.style.height = "auto";
      moodTextarea.style.height = `${moodTextarea.scrollHeight}px`;
    };
    autoResize();
    moodTextarea.addEventListener("input", autoResize);
  }

  document.getElementById("btn-analyze-text").addEventListener("click", async () => {
    const text = document.getElementById("mood-text-input").value.trim();
    if (text.length < 3) {
      showToast("Lütfen en az 3 karakter girin.", "warning");
      return;
    }
    await performAnalysis(() => api.analyzeText(text, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
  });

  // Manual mood
  document.querySelectorAll("[data-mood]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mood = btn.dataset.mood;
      lastSearchQuery = ""; // Yeni mood seçildiğinde aramayı sıfırla
      await performAnalysis(() => api.manualMood(mood, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
    });
  });
}

// ── Language Filter ──────────────────────────────────────────────────────────
function setupLanguageFilter() {
  // Bu fonksiyon artık boş — filtreler sonuç barında dinamik olarak oluşturuluyor
}

async function performAnalysis(analysisFn) {
  const resultsSection = document.getElementById("results-section");
  resultsSection.innerHTML = `
    <div class="tracks-grid">
      ${Array(5).fill(`
        <div class="track-card">
          <div class="skeleton-image skeleton"></div>
          <div class="track-info">
            <div class="skeleton-text skeleton"></div>
            <div class="skeleton-text short skeleton"></div>
          </div>
        </div>
      `).join('')}
    </div>`;
  resultsSection.classList.add("active");

  try {
    const data = await analysisFn();
    currentResults = data;
    lastMoodCategory = data.mood_category;
    lastEmotion = data.emotion;
    renderResults(data);
  } catch (err) {
    resultsSection.innerHTML = `
      <div class="error-state">
        <span class="error-icon">⚠️</span>
        <p>${err.message}</p>
      </div>`;
  }
}

// Filtre değiştiğinde sadece önerileri yeniden çek (mood badge'i koru)
async function refetchRecommendations() {
  if (!lastMoodCategory) return;

  const contentArea = document.getElementById("results-content-area");
  if (contentArea) {
    contentArea.innerHTML = `
      <div class="tracks-grid">
        ${Array(5).fill(`
          <div class="track-card">
            <div class="skeleton-image skeleton"></div>
            <div class="track-info">
              <div class="skeleton-text skeleton"></div>
              <div class="skeleton-text short skeleton"></div>
            </div>
          </div>
        `).join('')}
      </div>`;
  }

  try {
    const data = await api.manualMood(lastEmotion || lastMoodCategory, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre, lastRequestedArtist);
    currentResults = data;
    // Update lastRequestedArtist from response to keep it in sync
    lastRequestedArtist = data.requested_artist || null;
    renderContentList(data.recommendations);
  } catch (err) {
    if (contentArea) {
      contentArea.innerHTML = `
        <div class="error-state">
          <span class="error-icon"></span>
          <p>${err.message}</p>
        </div>`;
    }
  }
}

function renderResults(data) {
  // Sync the last requested artist from the analysis results
  lastRequestedArtist = data.requested_artist || null;

  const moodIcons = {
    energetic: "",
    calm: "",
    intense: "",
    chill: "",
    melancholic: "",
  };
  const moodLabels = {
    energetic: "Enerjik",
    calm: "Sakin",
    intense: "Yoğun",
    chill: "Rahat",
    melancholic: "Hüzünlü",
  };
  const moodColors = {
    energetic: "var(--accent-energetic)",
    calm: "var(--accent-calm)",
    intense: "var(--accent-intense)",
    chill: "var(--accent-chill)",
    melancholic: "var(--accent-melancholic)",
  };

  const resultsSection = document.getElementById("results-section");
  const icon = "";
  const label = moodLabels[data.mood_category] || data.mood_category;
  const color = moodColors[data.mood_category] || "var(--primary)";

  const contentTypeLabels = {
    track: "Şarkılar",
    playlist: "Playlistler",
    podcast: "Podcastler",
  };
  const sectionTitle = contentTypeLabels[selectedContentType] || "Şarkılar";

  resultsSection.innerHTML = `
    <div class="results-header">
      <div class="mood-badge" style="--mood-color: ${color}">
        <div class="mood-text">
          <span class="mood-emotion">${data.emotion}</span>
          <span class="mood-category-tag" style="background: ${color}">${label}</span>
        </div>
      </div>
      ${(data.source === 'video' && data.input_text) ? `<p class="mood-transcript" style="margin-top: 1rem; font-style: italic; opacity: 0.85; background: rgba(255,255,255,0.05); padding: 0.75rem 1rem; border-left: 3px solid ${color}; border-radius: 4px;"><strong>Söyledikleriniz:</strong> "${data.input_text}"</p>` : ""}
      ${data.explanation ? `<p class="mood-explanation">${data.explanation}</p>` : ""}
    </div>

    <div class="results-header-row">
      <h3 class="section-title">${sectionTitle}</h3>
      <button id="btn-refresh-results" class="btn-refresh" title="Yeni öneriler getir">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.27l-5.34 5.34"/>
        </svg>
        <span>Yenile</span>
      </button>
    </div>

    <div class="results-filter-bar">
      <div class="results-search-box">
        <input type="text" id="results-search-input" class="form-input form-input-sm" placeholder="Sanatçı veya kelime ekle (örn: Duman)..." value="${lastSearchQuery}">
        <button id="btn-results-search" class="btn btn-primary btn-sm">Ara</button>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group">
        <button class="filter-chip ${selectedContentType === 'track' ? 'active' : ''}" data-content="track">Şarkı</button>
        <button class="filter-chip ${selectedContentType === 'playlist' ? 'active' : ''}" data-content="playlist">Playlist</button>
        <button class="filter-chip ${selectedContentType === 'podcast' ? 'active' : ''}" data-content="podcast">Podcast</button>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group">
        <select id="results-genre-select" class="form-input form-input-sm" style="width: auto; height: 32px; padding-top: 0; padding-bottom: 0;">
          <option value="">Tüm Türler</option>
          <option value="pop" ${selectedGenre === 'pop' ? 'selected' : ''}>Pop</option>
          <option value="rap" ${selectedGenre === 'rap' ? 'selected' : ''}>Rap / Hip-Hop</option>
          <option value="rock" ${selectedGenre === 'rock' ? 'selected' : ''}>Rock</option>
          <option value="indie" ${selectedGenre === 'indie' ? 'selected' : ''}>Indie</option>
          <option value="electronic" ${selectedGenre === 'electronic' ? 'selected' : ''}>Elektronik</option>
          <option value="classical" ${selectedGenre === 'classical' ? 'selected' : ''}>Klasik</option>
        </select>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group">
        <button class="filter-chip ${selectedLanguage === 'tr' ? 'active' : ''}" data-lang="tr">Türkçe</button>
        <button class="filter-chip ${selectedLanguage === 'mixed' ? 'active' : ''}" data-lang="mixed">Karışık</button>
        <button class="filter-chip ${selectedLanguage === 'en' ? 'active' : ''}" data-lang="en">Yabancı</button>
      </div>
    </div>

    <div id="results-content-area" class="tracks-grid"></div>
  `;

  // Render content
  renderContentList(data.recommendations);

  // Refresh button listener
  const refreshBtn = document.getElementById("btn-refresh-results");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshBtn.classList.add("spinning");
      refetchRecommendations().finally(() => {
        refreshBtn.classList.remove("spinning");
      });
    });
  }

  // Search event listeners
  const resultsSearchInput = document.getElementById("results-search-input");
  const btnResultsSearch = document.getElementById("btn-results-search");
  
  if(resultsSearchInput && btnResultsSearch) {
    resultsSearchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        lastSearchQuery = resultsSearchInput.value.trim();
        lastRequestedArtist = null; // Clear artist filter when manual search is used
        refetchRecommendations();
      }
    });
    btnResultsSearch.addEventListener("click", () => {
      lastSearchQuery = resultsSearchInput.value.trim();
      lastRequestedArtist = null; // Clear artist filter when manual search is used
      refetchRecommendations();
    });
  }

  // Genre event listener
  const genreSelect = document.getElementById("results-genre-select");
  if (genreSelect) {
    genreSelect.addEventListener("change", (e) => {
      selectedGenre = e.target.value;
      refetchRecommendations();
    });
  }

  // Filter event listeners
  resultsSection.querySelectorAll("[data-content]").forEach((btn) => {
    btn.addEventListener("click", () => {
      resultsSection.querySelectorAll("[data-content]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedContentType = btn.dataset.content;
      // Başlığı güncelle
      const titleMap = { track: "Şarkılar", playlist: "Playlistler", podcast: "Podcastler" };
      resultsSection.querySelector(".section-title").textContent = titleMap[selectedContentType] || "Şarkılar";
      refetchRecommendations();
    });
  });

  resultsSection.querySelectorAll("[data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => {
      resultsSection.querySelectorAll("[data-lang]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedLanguage = btn.dataset.lang;
      refetchRecommendations();
    });
  });
}

function renderContentList(items) {
  const container = document.getElementById("results-content-area");
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <p>Sonuç bulunamadı. Farklı bir filtre deneyin.</p>
      </div>`;
    return;
  }

  // Define liked memory client-side if needed, but we can just toggle heart
  container.innerHTML = items
    .map(
      (item, i) => {
        // Prepare object string safely to bind in HTML
        const trackObj = {
          spotify_id: item.id,
          track_name: item.name,
          artist_name: item.artist,
          album_name: item.album || "",
          image_url: item.image_url || "",
          spotify_url: item.spotify_url || ""
        };
        const trackJSON = encodeURIComponent(JSON.stringify(trackObj));

        return `
    <div class="track-card" style="animation-delay: ${i * 0.06}s">
      <div class="track-image">
        ${item.image_url ? `<img src="${item.image_url}" alt="${item.name}" loading="lazy">` : `<div class="track-placeholder"></div>`}
        <div class="track-actions">
          ${item.type === 'track' ? `<button class="btn-icon btn-like" onclick="toggleLike(this, '${trackJSON}')" title="Beğen"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></button>` : ""}
          ${item.preview_url ? `<button class="btn-icon btn-play" onclick="playPreview('${item.preview_url}', this)" title="Önizle"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>` : ""}
          <button class="btn-icon btn-spotify" onclick="playInSpotifyPlayer('${item.type}', '${item.id}')" title="Uygulama içinde oynat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
          </button>
        </div>
      </div>
      <div class="track-info">
        <h4 class="track-name">${item.name}</h4>
        <p class="track-artist">${item.artist}</p>
        <p class="track-album">${item.album || ''}</p>
      </div>
    </div>`;
      }
    )
    .join("");
}

// ── Like / Dislike Toggle ──────────────────────────────────────────────────
async function toggleLike(btnElement, trackJSONEncoded) {
  try {
    const trackObj = JSON.parse(decodeURIComponent(trackJSONEncoded));
    const isLiked = btnElement.classList.contains("liked");
    const action = isLiked ? "dislike" : "like";
    
    await api.likeTrack(trackObj, action);
    
    if (action === "like") {
      btnElement.classList.add("liked");
      btnElement.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>';
      showToast("Şarkı beğenilenlere eklendi", "success");
    } else {
      btnElement.classList.remove("liked");
      btnElement.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>';
      showToast("Şarkı beğenilenlerden çıkarıldı", "info");
      
      // If we are currently on the liked page, remove the card from UI
      if (document.getElementById("page-liked").classList.contains("active")) {
        btnElement.closest(".track-card").remove();
        // check if empty
        const list = document.getElementById("liked-list");
        if (list.children.length === 0) {
          list.innerHTML = `
            <div class="empty-state">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
              <p>Henüz beğenilen şarkı yok.</p>
            </div>`;
        }
      }
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ── Audio Preview ────────────────────────────────────────────────────────────
let currentAudio = null;
let currentPlayBtn = null;

function playInSpotifyPlayer(type, id) {
  const container = document.getElementById('spotify-player-container');
  const iframe = document.getElementById('spotify-iframe');
  
  // type = 'track', 'playlist', 'show' (podcast)
  let embedType = type;
  if(type === 'podcast') embedType = 'show';
  else if(type === 'playlist') embedType = 'playlist';
  else embedType = 'track';

  iframe.src = `https://open.spotify.com/embed/${embedType}/${id}?utm_source=generator&theme=0`;
  container.classList.add('active');

  // Mevcut çalan bir müzik önizlemesi varsa durdur.
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
    if (currentPlayBtn) {
      currentPlayBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
      currentPlayBtn.classList.remove("playing");
      currentPlayBtn = null;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('close-player-btn');
  if(closeBtn) {
    closeBtn.addEventListener('click', () => {
      document.getElementById('spotify-player-container').classList.remove('active');
      document.getElementById('spotify-iframe').src = "";
    });
  }
});

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
  const recordBtn = document.getElementById("btn-record-video");
  if (recordBtn) recordBtn.addEventListener("click", recordVideoAndAnalyze);
}

async function startCamera() {
  const video = document.getElementById("camera-video");
  const placeholder = document.getElementById("camera-placeholder");

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ 
      video: { facingMode: "user", width: 640, height: 480 },
      audio: true
    });
    video.srcObject = cameraStream;
    video.classList.add("active");
    placeholder.classList.remove("active");
    document.getElementById("btn-start-camera").style.display = "none";
    document.getElementById("btn-capture").style.display = "inline-flex";
    const recordBtn = document.getElementById("btn-record-video");
    if (recordBtn) recordBtn.style.display = "inline-flex";
  } catch (err) {
    console.error("Camera access failed:", err);
    showToast("Kamera veya mikrofon erişimi reddedildi.", "error");
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
  const recordBtn = document.getElementById("btn-record-video");
  if (recordBtn) recordBtn.style.display = "none";
}

async function captureAndAnalyze() {
  const video = document.getElementById("camera-video");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  const base64 = canvas.toDataURL("image/jpeg").split(",")[1];
  stopCamera();
  lastSearchQuery = ""; // Kameradan yüz arandığında aramayı sıfırla
  await performAnalysis(() => api.analyzeFace(base64, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
}

async function recordVideoAndAnalyze() {
  if (!cameraStream) {
    showToast("Kamera akışı aktif değil.", "error");
    return;
  }

  const btn = document.getElementById("btn-record-video");
  const captureBtn = document.getElementById("btn-capture");
  btn.disabled = true;
  captureBtn.disabled = true;

  try {
    const chunks = [];
    const options = { mimeType: 'video/webm;codecs=vp8,opus' };
    
    let recorder;
    try {
      recorder = new MediaRecorder(cameraStream, options);
    } catch (e) {
      console.warn("MimeType not supported, falling back to default recorder options");
      recorder = new MediaRecorder(cameraStream);
    }

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        chunks.push(e.data);
      }
    };

    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'video/webm' });
      
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64 = reader.result.split(',')[1];
        stopCamera();
        lastSearchQuery = "";
        btn.disabled = false;
        captureBtn.disabled = false;
        btn.innerHTML = 'Sesli Video Analizi (3sn - Gemini AI)';
        
        await performAnalysis(() => api.analyzeVideo(base64, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
      };
      reader.readAsDataURL(blob);
    };

    // Start recording
    recorder.start();
    
    let secondsLeft = 3;
    btn.innerHTML = `Kayıt yapılıyor... (${secondsLeft}sn) 🎙️`;
    
    const interval = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        clearInterval(interval);
      } else {
        btn.innerHTML = `Kayıt yapılıyor... (${secondsLeft}sn) 🎙️`;
      }
    }, 1000);

    setTimeout(() => {
      clearInterval(interval);
      recorder.stop();
    }, 3000); // Record for 3 seconds

  } catch (err) {
    showToast("Video kaydı başlatılamadı: " + err.message, "error");
    btn.disabled = false;
    captureBtn.disabled = false;
    btn.innerHTML = 'Sesli Video Analizi (3sn - Gemini AI)';
  }
}

// ── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  const container = document.getElementById("history-list");
  container.innerHTML = `
    <div class="history-list">
      ${Array(4).fill(`
        <div class="history-card">
          <div class="history-mood" style="flex: 1;">
            <div class="skeleton-image skeleton" style="border-radius: 50%; width: 40px; height: 40px;"></div>
            <div style="flex: 1; margin-left: 1rem;">
              <div class="skeleton-text skeleton"></div>
              <div class="skeleton-text short skeleton"></div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>`;

  try {
    const history = await api.getHistory();
    if (!history.length) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <p>Henüz bir geçmiş yok.</p>
        </div>`;
      return;
    }

    const moodIcons = { energetic: "", calm: "", intense: "", chill: "" };

    container.innerHTML = history
      .map(
        (item, i) => `
      <div class="history-card" style="animation-delay: ${i * 0.05}s">
        <div class="history-mood">
          <span class="history-icon">${moodIcons[item.mood_category] || ""}</span>
          <div>
            <strong>${item.emotion}</strong>
            <span class="history-source">${item.source === 'face' ? 'Fotoğraf' : item.source === 'text' ? 'Metin' : item.source === 'manual' ? 'Manuel' : item.source === 'video' ? 'Sesli Video' : item.source}</span>
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
    container.innerHTML = `<div class="error-state"><span class="error-icon"></span><p>${err.message}</p></div>`;
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
  container.innerHTML = `
    <div class="tracks-grid">
      ${Array(5).fill(`
        <div class="track-card">
          <div class="skeleton-image skeleton"></div>
          <div class="track-info">
            <div class="skeleton-text skeleton"></div>
            <div class="skeleton-text short skeleton"></div>
          </div>
        </div>
      `).join('')}
    </div>`;

  try {
    const tracks = await api.getLikedTracks();
    if (!tracks.length) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
          <p>Henüz beğenilen şarkı yok.</p>
        </div>`;
      return;
    }

    container.innerHTML = tracks
      .map(
        (t, i) => {
          const trackObj = {
            spotify_id: t.id,
            track_name: t.track_name,
            artist_name: t.artist_name,
            album_name: t.album_name || "",
            image_url: t.image_url || "",
            spotify_url: t.spotify_url || ""
          };
          const trackJSON = encodeURIComponent(JSON.stringify(trackObj));

          return `
      <div class="track-card" style="animation-delay: ${i * 0.06}s">
        <div class="track-image">
          ${t.image_url ? `<img src="${t.image_url}" alt="${t.track_name}" loading="lazy">` : '<div class="track-placeholder"></div>'}
          <div class="track-actions">
            <button class="btn-icon btn-like liked" onclick="toggleLike(this, '${trackJSON}')" title="Beğenmekten Vazgeç"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></button>
            <button class="btn-icon btn-spotify" onclick="playInSpotifyPlayer('track', '${t.spotify_url ? t.spotify_url.split('/').pop() : t.id}')" title="Uygulama içinde oynat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
            </button>
          </div>
        </div>
        <div class="track-info">
          <h4 class="track-name">${t.track_name}</h4>
          <p class="track-artist">${t.artist_name}</p>
          <p class="track-album">${t.album_name || ""}</p>
        </div>
      </div>`;
        }
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<div class="error-state"><span class="error-icon"></span><p>${err.message}</p></div>`;
  }
}

// ── Toast ────────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span></span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
