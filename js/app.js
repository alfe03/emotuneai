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
let lastCapturedFaceBase64 = null;    // Son çekilen yüz fotoğrafı
let moodDistChartInstance = null;
let moodTrendChartInstance = null;


// ── Init ─────────────────────────────────────────────────────────────────────
async function initApp() {
  setupNavigation();
  setupAuthForms();
  setupMoodActions();
  setupCameraActions();
  setupLanguageFilter();
  setupAnalyticsTimeframe();
  setupVoiceActions();
  setupExportModalActions();

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

  setupTheme();

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
  
  const btnLogoutMobile = document.getElementById("btn-logout-mobile");
  if (btnLogoutMobile) {
    btnLogoutMobile.addEventListener("click", () => {
      api.logout();
      currentUser = null;
      localStorage.removeItem("lastPage");
      showAuth();
    });
  }
}

function switchPage(page) {
  localStorage.setItem("lastPage", page);
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  const el = document.getElementById(`page-${page}`);
  if (el) {
    el.classList.add("active");
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (page === "history") loadHistory();
    if (page === "liked") loadLikedTracks();
    if (page === "playlists") loadSavedPlaylists();
    if (page === "profile") loadProfilePage();
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
    
    // Sync avatar from backend user object if available
    if (currentUser.avatar_url) {
      api.setAvatar(currentUser.avatar_url);
    }

    const avatarUrl = api.getAvatar();
    const avatarEl = document.getElementById("user-avatar");
    
    if (avatarUrl) {
      if (avatarEl) {
        const fullUrl = avatarUrl.startsWith('data:') || avatarUrl.startsWith('http') ? avatarUrl : API_BASE + avatarUrl;
        avatarEl.innerHTML = `<img src="${fullUrl}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
      }
    } else {
      const initial = (currentUser.username || currentUser.email || "U").trim().charAt(0).toUpperCase();
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
    window.location.href = `${API_BASE}/api/auth/spotify/login?redirect=${redirect}`;
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

      const targetSource = tab.dataset.moodTab;
      const resultsSection = document.getElementById("results-section");

      // Eğer mevcut bir sonuç varsa ve bu sonucun kaynağı şu anki sekmeye aitse göster, değilse gizle
      if (currentResults && currentResults.source === targetSource) {
        if (resultsSection) {
          resultsSection.style.display = ""; // flex veya block'a döner
          resultsSection.classList.add("active");
        }
        // Temayı geri yükle
        document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
        document.body.classList.add('theme-' + currentResults.mood_category);
        document.body.setAttribute('data-mood', currentResults.mood_category);

        // Input alanlarını gizle ve Yeniden Analiz butonlarını göster
        if (targetSource === "text") {
          const tInput = document.getElementById("text-input-container");
          const tRestart = document.getElementById("text-restart-container");
          if (tInput) tInput.style.display = "none";
          if (tRestart) tRestart.style.display = "block";
        } else if (targetSource === "voice") {
          const vInput = document.getElementById("voice-input-container");
          const vRestart = document.getElementById("voice-restart-container");
          if (vInput) vInput.style.display = "none";
          if (vRestart) vRestart.style.display = "block";
        }
      } else {
        if (resultsSection) {
          resultsSection.style.display = "none";
          resultsSection.classList.remove("active");
        }
        // Temayı kaldır
        document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
        document.body.removeAttribute('data-mood');

        // Input alanlarını göster ve Yeniden Analiz butonlarını gizle
        if (targetSource === "text") {
          const tInput = document.getElementById("text-input-container");
          const tRestart = document.getElementById("text-restart-container");
          if (tInput) tInput.style.display = "block";
          if (tRestart) tRestart.style.display = "none";
        } else if (targetSource === "voice") {
          const vInput = document.getElementById("voice-input-container");
          const vRestart = document.getElementById("voice-restart-container");
          if (vInput) vInput.style.display = "flex";
          if (vRestart) vRestart.style.display = "none";
        }
      }
      
      // Metin kutusunu temizle (başka sekmeye geçince eski metin kalmasın)
      const textInput = document.getElementById("mood-text-input");
      if (textInput) textInput.value = "";

      // Kamerayı durdur veya sıfırla
      if (targetSource !== "face") {
        stopCamera();
      } else {
        const cameraArea = document.querySelector("#panel-face .camera-area");
        const cameraControls = document.querySelector("#panel-face .camera-controls");
        
        if (currentResults && currentResults.source === "face") {
            // Zaten yüzde analiz yapılmış, kamera gizli kalmalı
            if (cameraArea) cameraArea.style.display = "none";
            if (cameraControls) cameraControls.style.display = "none";
        } else {
            // Yüz sekmesinde analiz yok, kamerayı göster
            if (cameraArea) cameraArea.style.display = "";
            if (cameraControls) cameraControls.style.display = "";
        }
      }
      
      if (targetSource !== "voice") stopVoiceRecord(true);
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
  resultsSection.style.display = ""; // Daha önce gizlendiyse (display: none) temizle
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
    document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
    document.body.classList.add('theme-' + data.mood_category);
    document.body.setAttribute('data-mood', data.mood_category);

    if (data.source === "text") {
      const tInput = document.getElementById("text-input-container");
      const tRestart = document.getElementById("text-restart-container");
      if (tInput) tInput.style.display = "none";
      if (tRestart) tRestart.style.display = "block";
    } else if (data.source === "voice") {
      const vInput = document.getElementById("voice-input-container");
      const vRestart = document.getElementById("voice-restart-container");
      if (vInput) vInput.style.display = "none";
      if (vRestart) vRestart.style.display = "block";
    }

    renderResults(data);
  } catch (err) {
    const errDiv = document.createElement("div");
    errDiv.className = "error-state";
    const icon = document.createElement("span");
    icon.className = "error-icon";
    icon.textContent = "⚠️";
    const msg = document.createElement("p");
    msg.textContent = err.message || "Bilinmeyen bir hata oluştu.";
    errDiv.appendChild(icon);
    errDiv.appendChild(msg);
    resultsSection.innerHTML = "";
    resultsSection.appendChild(errDiv);
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
    const data = await api.manualMood(lastEmotion || lastMoodCategory, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre, lastRequestedArtist, true); // no_save=true: yenile/filtre için DB'ye kaydetme
    currentResults = data;
    // Tema rengi ve mood DEĞIŞTIRILMEZ — ruh hali değişmedi, sadece öneriler yenilendi
    // lastMoodCategory ve lastEmotion güncellenmez, sadece artist güncellenir
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

  const safeEmotion = DOMPurify.sanitize(data.emotion);
  const safeInputText = DOMPurify.sanitize(data.input_text || "");
  const safeExplanation = DOMPurify.sanitize(data.explanation || "");

  let polaroidHtml = "";
  if (data.source === "face" && lastCapturedFaceBase64) {
    polaroidHtml = `
      <div class="polaroid-wrapper">
        <div class="polaroid-card">
          <div class="polaroid-img-container">
            <img src="data:image/jpeg;base64,${lastCapturedFaceBase64}" class="polaroid-img" alt="Yüz Analizi">
            <div class="polaroid-tint" style="background-color: ${color}"></div>
          </div>
          <div class="polaroid-caption">
            <span>${data.emoji || '✨'}</span> ${safeEmotion}
          </div>
          <div style="display: flex; gap: 8px; margin-top: 12px; width: 100%;">
            <button class="btn btn-sm" onclick="downloadPolaroid(this)" style="flex: 1; background: #f0f0f0; color: #333; border: 1px dashed #ccc; padding: 6px; font-size: 0.85rem; cursor: pointer; border-radius: 4px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> İndir
            </button>
            <button class="btn btn-sm" onclick="resetFacePanel()" style="flex: 1; background: var(--primary); color: #fff; border: none; padding: 6px; font-size: 0.85rem; cursor: pointer; border-radius: 4px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg> Yeniden Çek
            </button>
          </div>
        </div>
      </div>
    `;
  }

  resultsSection.innerHTML = `
    ${polaroidHtml}
    <div class="results-header">
      <div class="mood-badge" style="--mood-color: ${color}">
        <div class="mood-text">
          <span class="mood-emotion">${safeEmotion}</span>
          <span class="mood-category-tag" style="background: ${color}">${label}</span>
        </div>
      </div>
      ${(data.source === 'voice' && data.input_text) ? `<p class="mood-transcript" style="margin-top: 1rem; font-style: italic; opacity: 0.85; background: rgba(255,255,255,0.05); padding: 0.75rem 1rem; border-left: 3px solid ${color}; border-radius: 4px;"><strong>Söyledikleriniz:</strong> "${safeInputText}"</p>` : ""}
      ${data.explanation ? `<p class="mood-explanation">${safeExplanation}</p>` : ""}
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
        <input type="text" id="results-search-input" class="form-input form-input-sm" placeholder="Sanatçı veya kelime (örn: Duman)..." value="${lastSearchQuery}">
        <button id="btn-results-search" class="btn btn-primary btn-sm">Ara</button>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group">
        <button class="filter-chip ${selectedContentType === 'track' ? 'active' : ''}" data-content="track">Şarkı</button>
        <button class="filter-chip ${selectedContentType === 'playlist' ? 'active' : ''}" data-content="playlist">Playlist</button>
        <button class="filter-chip ${selectedContentType === 'podcast' ? 'active' : ''}" data-content="podcast">Podcast</button>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group select-group" style="background: transparent; border: none; padding: 0;">
        <div class="custom-genre-dropdown" id="genre-custom-dropdown">
          <div class="dropdown-selected">
            <span id="genre-dropdown-text">Tüm Türler</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </div>
          <div class="dropdown-options">
            <div class="dropdown-option ${selectedGenre === '' ? 'active' : ''}" data-value="">Tüm Türler</div>
            <div class="dropdown-option ${selectedGenre === 'pop' ? 'active' : ''}" data-value="pop">Pop</div>
            <div class="dropdown-option ${selectedGenre === 'rap' ? 'active' : ''}" data-value="rap">Rap / Hip-Hop</div>
            <div class="dropdown-option ${selectedGenre === 'rock' ? 'active' : ''}" data-value="rock">Rock</div>
            <div class="dropdown-option ${selectedGenre === 'indie' ? 'active' : ''}" data-value="indie">Indie</div>
            <div class="dropdown-option ${selectedGenre === 'electronic' ? 'active' : ''}" data-value="electronic">Elektronik</div>
            <div class="dropdown-option ${selectedGenre === 'classical' ? 'active' : ''}" data-value="classical">Klasik</div>
            <div class="dropdown-option ${selectedGenre === 'jazz' ? 'active' : ''}" data-value="jazz">Caz (Jazz)</div>
            <div class="dropdown-option ${selectedGenre === 'blues' ? 'active' : ''}" data-value="blues">Blues</div>
            <div class="dropdown-option ${selectedGenre === 'metal' ? 'active' : ''}" data-value="metal">Metal</div>
            <div class="dropdown-option ${selectedGenre === 'r&b' ? 'active' : ''}" data-value="r&b">R&B / Soul</div>
          </div>
        </div>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-group">
        <button class="filter-chip ${selectedLanguage === 'tr' ? 'active' : ''}" data-lang="tr">Türkçe</button>
        <button class="filter-chip ${selectedLanguage === 'mixed' ? 'active' : ''}" data-lang="mixed">Karışık</button>
        <button class="filter-chip ${selectedLanguage === 'en' ? 'active' : ''}" data-lang="en">Yabancı</button>
      </div>
    </div>

    <div id="results-content-area" class="tracks-grid"></div>
    ${selectedContentType === 'track' ? `
      <div class="export-section" style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
        <button id="btn-export-spotify" class="btn-export-spotify">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="margin-right: 8px;"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
          Listeyi Kaydet / Aktar
        </button>
      </div>` : ''}
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

  // Custom Genre Dropdown logic
  const customDropdown = document.getElementById("genre-custom-dropdown");
  if (customDropdown) {
    const selectedText = document.getElementById("genre-dropdown-text");
    const options = customDropdown.querySelectorAll(".dropdown-option");
    
    // Set initial text
    const initialActive = customDropdown.querySelector(".dropdown-option.active");
    if (initialActive) selectedText.textContent = initialActive.textContent;

    customDropdown.querySelector(".dropdown-selected").addEventListener("click", (e) => {
      e.stopPropagation();
      customDropdown.classList.toggle("open");
    });

    options.forEach(opt => {
      opt.addEventListener("click", (e) => {
        e.stopPropagation();
        options.forEach(o => o.classList.remove("active"));
        opt.classList.add("active");
        selectedText.textContent = opt.textContent;
        customDropdown.classList.remove("open");
        
        selectedGenre = opt.dataset.value;
        refetchRecommendations();
      });
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

  const exportBtn = document.getElementById("btn-export-spotify");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      openExportModal(data.id, data.emotion);
    });
  }


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
        const safeName = DOMPurify.sanitize(item.name);
        const safeArtist = DOMPurify.sanitize(item.artist);
        const safeAlbum = DOMPurify.sanitize(item.album || "");
        const safeImageUrl = item.image_url ? DOMPurify.sanitize(item.image_url) : "";

        // Prepare object string safely to bind in HTML
        const trackObj = {
          spotify_id: item.id,
          track_name: safeName,
          artist_name: safeArtist,
          album_name: safeAlbum,
          image_url: safeImageUrl,
          spotify_url: item.spotify_url || ""
        };
        const trackJSON = encodeURIComponent(JSON.stringify(trackObj));

        return `
    <div class="track-card" style="animation-delay: ${i * 0.06}s">
      <div class="track-image">
        ${safeImageUrl ? `<img src="${safeImageUrl}" alt="${safeName}" loading="lazy">` : `<div class="track-placeholder"></div>`}
        <div class="track-actions">
          ${item.type === 'track' ? `<button class="btn-icon btn-like" onclick="toggleLike(this, '${trackJSON}')" title="Beğen"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></button>` : ""}
          ${item.preview_url ? `<button class="btn-icon btn-play" onclick="playPreview('${item.preview_url}', this)" title="Önizle"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>` : ""}
          <button class="btn-icon btn-spotify" onclick="playInSpotifyPlayer('${item.type}', '${item.id}')" title="Uygulama içinde oynat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
          </button>
        </div>
      </div>
      <div class="track-info">
        <h4 class="track-name">${safeName}</h4>
        <p class="track-artist">${safeArtist}</p>
        <p class="track-album">${safeAlbum}</p>
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
  } catch (err) {
    console.error("Camera access failed:", err.name, err.message);
    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
      showToast("Kamera/mikrofon izni reddedildi. Tarayıcı adres çubuğundaki kilit ikonuna tıklayıp izin ver.", "error");
    } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
      showToast("Kamera veya mikrofon bulunamadı. Cihazınızın bağlı olduğundan emin olun.", "error");
    } else if (err.name === "NotReadableError") {
      showToast("Kamera başka bir uygulama tarafından kullanılıyor. Diğer uygulamaları kapatıp tekrar deneyin.", "error");
    } else {
      showToast("Kamera/mikrofon erişim hatası: " + err.message, "error");
    }
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
  lastCapturedFaceBase64 = base64;
  
  const scanOverlay = document.querySelector(".scan-overlay");
  if (scanOverlay) scanOverlay.classList.add("scanning");
  video.pause();

  lastSearchQuery = ""; // Kameradan yüz arandığında aramayı sıfırla
  
  try {
    await performAnalysis(() => api.analyzeFace(base64, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
    // Başarılı analizden sonra kamera alanını gizle
    const cameraArea = document.querySelector("#panel-face .camera-area");
    const cameraControls = document.querySelector("#panel-face .camera-controls");
    if (cameraArea) cameraArea.style.display = "none";
    if (cameraControls) cameraControls.style.display = "none";
  } finally {
    if (scanOverlay) scanOverlay.classList.remove("scanning");
    stopCamera();
  }
}

function resetFacePanel() {
  const cameraArea = document.querySelector("#panel-face .camera-area");
  const cameraControls = document.querySelector("#panel-face .camera-controls");
  if (cameraArea) cameraArea.style.display = ""; // CSS'teki varsayılan (flex) değerine döner
  if (cameraControls) cameraControls.style.display = ""; // CSS'teki varsayılan (flex) değerine döner
  
  const resultsSection = document.getElementById("results-section");
  if (resultsSection) {
    resultsSection.innerHTML = "";
    resultsSection.classList.remove("active");
  }
  
  // Önemli: currentResults'ı temizle ki sekme geçişlerinde eski sonuç var sanılmasın
  currentResults = null;
  lastCapturedFaceBase64 = null;
  
  document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
  document.body.removeAttribute('data-mood');
  
  // Kamerayı otomatik başlatabiliriz
  startCamera();
}

window.resetTextPanel = function(clearText = true) {
  const tInput = document.getElementById("text-input-container");
  const tRestart = document.getElementById("text-restart-container");
  if (tInput) tInput.style.display = "block";
  if (tRestart) tRestart.style.display = "none";

  if (clearText) {
    const resultsSection = document.getElementById("results-section");
    if (resultsSection) {
      resultsSection.innerHTML = "";
      resultsSection.classList.remove("active");
    }
    
    currentResults = null;
    document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
    document.body.removeAttribute('data-mood');
    
    const textInputArea = document.getElementById("mood-text-input");
    if (textInputArea) {
      textInputArea.value = "";
      textInputArea.style.height = "auto";
    }
  }
};

window.resetVoicePanel = function() {
  const vInput = document.getElementById("voice-input-container");
  const vRestart = document.getElementById("voice-restart-container");
  if (vInput) vInput.style.display = "flex";
  if (vRestart) vRestart.style.display = "none";

  const resultsSection = document.getElementById("results-section");
  if (resultsSection) {
    resultsSection.innerHTML = "";
    resultsSection.classList.remove("active");
  }
  
  currentResults = null;
  document.body.classList.forEach(c => { if (c.startsWith('theme-')) document.body.classList.remove(c); });
  document.body.removeAttribute('data-mood');
  
  const statusLabel = document.getElementById("voice-status-label");
  if (statusLabel) statusLabel.textContent = "Sesinizi analiz etmek için mikrofona dokunun";
};


// ── History ──────────────────────────────────────────────────────────────────
let currentHistorySkip = 0;
const HISTORY_LIMIT = 5;

async function loadHistory(append = false) {
  const container = document.getElementById("history-list");
  const analyticsPanel = document.getElementById("analytics-panel");
  const listTitle = document.getElementById("history-list-title");

    if (!append) {
      currentHistorySkip = 0;
      container.innerHTML = `
        <div class="history-list">
          ${Array(HISTORY_LIMIT).fill(`
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
    } else {
      const loadBtn = document.getElementById("btn-load-more-history");
      if (loadBtn) loadBtn.textContent = "Yükleniyor...";
    }

  try {
    const history = await api.getHistory(currentHistorySkip, HISTORY_LIMIT);
    if (!append && !history.length) {
      if (analyticsPanel) analyticsPanel.style.display = "none";
      if (listTitle) listTitle.style.display = "none";
      
      container.innerHTML = `
        <div class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <p>Henüz bir geçmiş yok. Ruh halinizi analiz ettikçe geçmişiniz ve analitik grafikleriniz burada görünecektir.</p>
        </div>`;
      return;
    }

    if (!append) {
      if (analyticsPanel) analyticsPanel.style.display = "block";
      if (listTitle) listTitle.style.display = "block";

      const select = document.getElementById("analytics-days-select");
      const days = select ? parseInt(select.value, 10) : 30;
      loadAnalytics(days);
      
      container.innerHTML = '<div class="history-items-container"></div>';
    }

    const itemsContainer = container.querySelector('.history-items-container') || container;

    const moodIcons = { 
      energetic: "⚡", 
      calm: "🍃", 
      intense: "🔥", 
      chill: "🏝️", 
      melancholic: "🌧️" 
    };

    const htmlString = history.map((item, i) => {
          const safeEmotion = DOMPurify.sanitize(item.emotion);
          const safeSource = DOMPurify.sanitize(item.source);
          return `
      <div class="history-card" style="animation-delay: ${i * 0.05}s">
        <div class="history-mood">
          <span class="history-icon">${moodIcons[item.mood_category] || "🎵"}</span>
          <div>
            <strong>${safeEmotion}</strong>
            <span class="history-source">${item.source === 'face' ? 'Fotoğraf' : item.source === 'text' ? 'Metin' : item.source === 'manual' ? 'Manuel' : item.source === 'video' ? 'Sesli Video' : safeSource}</span>
          </div>
        </div>
        <div class="history-meta">
          <span class="history-confidence">%${item.confidence?.toFixed(1) || "N/A"}</span>
          <span class="history-date">${new Date(item.created_at).toLocaleDateString("tr-TR")}</span>
          <button class="btn-icon btn-delete" onclick="deleteHistoryItem(${item.id}, this)" title="Sil">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
          </button>
        </div>
      </div>`;
    }).join("");

    if (!append) {
      itemsContainer.innerHTML = htmlString;
    } else {
      itemsContainer.insertAdjacentHTML('beforeend', htmlString);
    }
    
    const oldBtn = document.getElementById("btn-load-more-history");
    if (oldBtn) oldBtn.remove();
    
    if (history.length === HISTORY_LIMIT) {
      const btnHtml = `<button id="btn-load-more-history" class="btn btn-outline" style="width: 100%; margin-top: 1rem;" onclick="loadMoreHistory()">Daha Fazla Yükle</button>`;
      container.insertAdjacentHTML('beforeend', btnHtml);
    }
  } catch (err) {
    if (!append) {
      container.innerHTML = `<div class="error-state"><span class="error-icon"></span><p>${err.message}</p></div>`;
    } else {
      showToast(err.message, "error");
      const loadBtn = document.getElementById("btn-load-more-history");
      if (loadBtn) loadBtn.textContent = "Daha Fazla Yükle";
    }
  }
}

function loadMoreHistory() {
  currentHistorySkip += HISTORY_LIMIT;
  loadHistory(true);
}

async function deleteHistoryItem(id, btn) {
  const card = btn.closest(".history-card");
  try {
    await api.deleteHistory(id);
    card.style.transform = "translateX(100%)";
    card.style.opacity = "0";
    setTimeout(() => {
      card.remove();
      // Silme sonrası listeyi ve istatistikleri güncelle
      loadHistory();
    }, 300);
    showToast("Kayıt silindi.", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function loadAnalytics(days = 30) {
  try {
    const data = await api.getHistoryAnalytics(days);
    
    const totalCount = data.length;
    document.getElementById("stat-total").textContent = totalCount;
    
    if (totalCount === 0) {
      document.getElementById("stat-common-mood").textContent = "-";
      document.getElementById("stat-avg-confidence").textContent = "%0";
      document.getElementById("stat-pref-source").textContent = "-";
      
      if (moodDistChartInstance) { moodDistChartInstance.destroy(); moodDistChartInstance = null; }
      if (moodTrendChartInstance) { moodTrendChartInstance.destroy(); moodTrendChartInstance = null; }
      return;
    }
    
    let totalConfidence = 0;
    const moodCounts = {};
    const sourceCounts = {};
    const dailyCounts = {};
    
    data.forEach(item => {
      totalConfidence += item.confidence || 0;
      moodCounts[item.mood_category] = (moodCounts[item.mood_category] || 0) + 1;
      sourceCounts[item.source] = (sourceCounts[item.source] || 0) + 1;
      dailyCounts[item.date] = (dailyCounts[item.date] || 0) + 1;
    });
    
    const avgConfidence = totalConfidence / totalCount;
    document.getElementById("stat-avg-confidence").textContent = `%${avgConfidence.toFixed(1)}`;
    
    const moodLabelsTR = {
      energetic: "Enerjik",
      calm: "Sakin",
      intense: "Yoğun",
      chill: "Rahat",
      melancholic: "Hüzünlü"
    };
    
    let mostCommonCategory = "-";
    let maxMoodCount = 0;
    Object.keys(moodCounts).forEach(m => {
      if (moodCounts[m] > maxMoodCount) {
        maxMoodCount = moodCounts[m];
        mostCommonCategory = moodLabelsTR[m] || m;
      }
    });
    document.getElementById("stat-common-mood").textContent = mostCommonCategory;
    
    const sourceLabelsTR = {
      text: "Metin",
      face: "Fotoğraf",
      video: "Sesli Video",
      manual: "Manuel"
    };
    let prefSource = "-";
    let maxSourceCount = 0;
    Object.keys(sourceCounts).forEach(s => {
      if (sourceCounts[s] > maxSourceCount) {
        maxSourceCount = sourceCounts[s];
        prefSource = sourceLabelsTR[s] || s;
      }
    });
    document.getElementById("stat-pref-source").textContent = prefSource;
    
    renderAnalyticsCharts(moodCounts, dailyCounts, days);
    
  } catch (err) {
    console.error("Analiz verisi yüklenirken hata:", err);
  }
}

function renderAnalyticsCharts(moodCounts, dailyCounts, days) {
  const moodColors = {
    energetic: "#e8a838",
    calm: "#5ba8c8",
    intense: "#d94040",
    chill: "#4aba7a",
    melancholic: "#6b8fd9"
  };
  
  const moodLabelsTR = {
    energetic: "Enerjik",
    calm: "Sakin",
    intense: "Yoğun",
    chill: "Rahat",
    melancholic: "Hüzünlü"
  };

  // 1. Ruh Hali Dağılımı (Doughnut)
  const distCanvas = document.getElementById("moodDistributionChart");
  if (distCanvas) {
    if (moodDistChartInstance) {
      moodDistChartInstance.destroy();
    }
    
    const categories = Object.keys(moodCounts);
    const counts = Object.values(moodCounts);
    const bgColors = categories.map(cat => moodColors[cat] || "#1db954");
    const labels = categories.map(cat => moodLabelsTR[cat] || cat);
    
    moodDistChartInstance = new Chart(distCanvas, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: counts,
          backgroundColor: bgColors,
          borderWidth: 1,
          borderColor: "rgba(255, 255, 255, 0.08)"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#e8e8e8",
              font: {
                family: "Inter",
                size: 11
              },
              padding: 15
            }
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const val = context.raw;
                const percentage = ((val / total) * 100).toFixed(1);
                return ` ${context.label}: ${val} adet (%${percentage})`;
              }
            }
          }
        },
        cutout: "60%"
      }
    });
  }

  // 2. Günlük Trend (Bar)
  const trendCanvas = document.getElementById("moodTrendChart");
  if (trendCanvas) {
    if (moodTrendChartInstance) {
      moodTrendChartInstance.destroy();
    }
    
    let labels = [];
    let dataPoints = [];
    
    // Son X günden geriye doğru tarihleri üretelim
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days + 1);
    
    const current = new Date(start);
    while (current <= end) {
      const dateStr = current.toISOString().split("T")[0];
      labels.push(current.toLocaleDateString("tr-TR", { month: "short", day: "numeric" }));
      dataPoints.push(dailyCounts[dateStr] || 0);
      current.setDate(current.getDate() + 1);
    }
    
    moodTrendChartInstance = new Chart(trendCanvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Analiz Sayısı",
          data: dataPoints,
          backgroundColor: "rgba(29, 185, 84, 0.45)",
          borderColor: "#1db954",
          borderWidth: 1.5,
          borderRadius: 4,
          hoverBackgroundColor: "#1db954"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: {
              display: false
            },
            ticks: {
              color: "#a0a0a0",
              font: {
                family: "Inter",
                size: 9
              }
            }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: "rgba(255, 255, 255, 0.05)"
            },
            ticks: {
              color: "#a0a0a0",
              stepSize: 1,
              font: {
                family: "Inter",
                size: 10
              }
            }
          }
        },
        plugins: {
          legend: {
            display: false
          }
        }
      }
    });
  }
}

function setupAnalyticsTimeframe() {
  const select = document.getElementById("analytics-days-select");
  if (select) {
    select.addEventListener("change", (e) => {
      const days = parseInt(e.target.value, 10);
      loadAnalytics(days);
    });
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
          const safeName = DOMPurify.sanitize(t.track_name);
          const safeArtist = DOMPurify.sanitize(t.artist_name);
          const safeAlbum = DOMPurify.sanitize(t.album_name || "");
          const safeImageUrl = t.image_url ? DOMPurify.sanitize(t.image_url) : "";

          const trackObj = {
            spotify_id: t.id,
            track_name: safeName,
            artist_name: safeArtist,
            album_name: safeAlbum,
            image_url: safeImageUrl,
            spotify_url: t.spotify_url || ""
          };
          const trackJSON = encodeURIComponent(JSON.stringify(trackObj));

          return `
      <div class="track-card" style="animation-delay: ${i * 0.06}s">
        <div class="track-image">
          ${safeImageUrl ? `<img src="${safeImageUrl}" alt="${safeName}" loading="lazy">` : '<div class="track-placeholder"></div>'}
          <div class="track-actions">
            <button class="btn-icon btn-like liked" onclick="toggleLike(this, '${trackJSON}')" title="Beğenmekten Vazgeç"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></button>
            <button class="btn-icon btn-spotify" onclick="playInSpotifyPlayer('track', '${t.spotify_url ? t.spotify_url.split('/').pop() : t.id}')" title="Uygulama içinde oynat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
            </button>
          </div>
        </div>
        <div class="track-info">
          <h4 class="track-name">${safeName}</h4>
          <p class="track-artist">${safeArtist}</p>
          <p class="track-album">${safeAlbum}</p>
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
  const msgSpan = document.createElement('span');
  msgSpan.textContent = message;
  toast.appendChild(msgSpan);
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}


// ── Ses Kayıt İşlemleri (Voice Recording) ──────────────────────────────────
let voiceRecorder = null;
let voiceChunks = [];
let voiceRecordInterval = null;
let voiceRecordTimeout = null;

// Audio Context for Visualizer
let audioContext = null;
let analyserNode = null;
let audioVisualizerFrame = null;
let audioSourceNode = null;

function setupVoiceActions() {
  const micBtn = document.getElementById("btn-mic-record");
  if (!micBtn) return;
  micBtn.addEventListener("click", () => {
    if (micBtn.classList.contains("recording")) {
      stopVoiceRecord(false);
    } else {
      startVoiceRecord();
    }
  });
}

async function startVoiceRecord() {
  const micBtn = document.getElementById("btn-mic-record");
  const statusLabel = document.getElementById("voice-status-label");
  const timerEl = document.getElementById("voice-record-timer");
  const visualizer = document.getElementById("voice-visualizer-bars");

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    voiceChunks = [];
    
    let options = { mimeType: 'audio/webm;codecs=opus' };
    try {
      voiceRecorder = new MediaRecorder(stream, options);
    } catch (e) {
      voiceRecorder = new MediaRecorder(stream);
    }

    voiceRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        voiceChunks.push(e.data);
      }
    };

    voiceRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      
      if (voiceChunks.length === 0) return;
      
      const blob = new Blob(voiceChunks, { type: (voiceRecorder && voiceRecorder.mimeType) ? voiceRecorder.mimeType : 'audio/webm' });
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64 = reader.result.split(',')[1];
        
        micBtn.classList.remove("recording");
        if (visualizer) visualizer.classList.remove("active");
        if (timerEl) timerEl.style.display = "none";
        statusLabel.textContent = "Sesiniz analiz ediliyor...";
        
        lastSearchQuery = "";
        await performAnalysis(() => api.analyzeAudio(base64, selectedLanguage, selectedContentType, lastSearchQuery, selectedGenre));
        statusLabel.textContent = "Sesinizi analiz etmek için mikrofona dokunun";
      };
      reader.readAsDataURL(blob);
    };

    micBtn.classList.add("recording");
    if (visualizer) visualizer.classList.add("active");
    if (timerEl) {
      timerEl.style.display = "block";
      timerEl.textContent = `0:00 / 0:10`;
    }
    statusLabel.textContent = "Dinliyorum... Erken bitirmek için tekrar dokunun";

    voiceRecorder.start();

    // Setup Web Audio API for Dynamic Visualizer
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 64;
      audioSourceNode = audioContext.createMediaStreamSource(stream);
      audioSourceNode.connect(analyserNode);

      const bufferLength = analyserNode.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      const bars = document.querySelectorAll(".visualizer-bar");

      function drawVisualizer() {
        if (!analyserNode) return;
        audioVisualizerFrame = requestAnimationFrame(drawVisualizer);
        analyserNode.getByteFrequencyData(dataArray);
        
        if (bars.length > 0) {
          const step = Math.max(1, Math.floor(bufferLength / bars.length));
          bars.forEach((bar, i) => {
            let sum = 0;
            for (let j = 0; j < step; j++) {
              sum += dataArray[i * step + j] || 0;
            }
            const avg = sum / step;
            const height = 6 + (avg / 255) * 34; // 6px to 40px
            bar.style.height = `${height}px`;
            bar.style.animation = 'none'; // Disable CSS animation
            bar.style.transition = 'height 0.05s ease';
          });
        }
      }
      drawVisualizer();
    } catch (e) {
      console.warn("Web Audio API visualizer could not be initialized:", e);
    }

    let seconds = 0;
    voiceRecordInterval = setInterval(() => {
      seconds += 1;
      if (timerEl) timerEl.textContent = `0:${String(seconds).padStart(2, '0')} / 0:10`;
      if (seconds >= 10) {
        stopVoiceRecord(false);
      }
    }, 1000);

    voiceRecordTimeout = setTimeout(() => {
      stopVoiceRecord(false);
    }, 10000);

  } catch (err) {
    console.error("Microphone access failed:", err);
    showToast("Mikrofon erişimi sağlanamadı: " + err.message, "error");
  }
}

function stopVoiceRecord(cancel = false) {
  if (voiceRecordInterval) {
    clearInterval(voiceRecordInterval);
    voiceRecordInterval = null;
  }
  if (voiceRecordTimeout) {
    clearTimeout(voiceRecordTimeout);
    voiceRecordTimeout = null;
  }
  
  if (audioVisualizerFrame) {
    cancelAnimationFrame(audioVisualizerFrame);
    audioVisualizerFrame = null;
  }
  if (audioSourceNode) {
    audioSourceNode.disconnect();
    audioSourceNode = null;
  }
  if (audioContext && audioContext.state !== "closed") {
    audioContext.close();
    audioContext = null;
  }
  analyserNode = null;
  
  // Reset bar heights
  const bars = document.querySelectorAll(".visualizer-bar");
  bars.forEach(bar => {
    bar.style.height = '';
    bar.style.animation = '';
    bar.style.transition = '';
  });

  if (voiceRecorder && voiceRecorder.state !== "inactive") {
    if (cancel) {
      voiceChunks = [];
    }
    voiceRecorder.stop();
    // Do not set voiceRecorder = null here, it breaks onstop execution.
  }

  const micBtn = document.getElementById("btn-mic-record");
  const timerEl = document.getElementById("voice-record-timer");
  const visualizer = document.getElementById("voice-visualizer-bars");
  const statusLabel = document.getElementById("voice-status-label");

  if (micBtn) micBtn.classList.remove("recording");
  if (visualizer) visualizer.classList.remove("active");
  if (timerEl) timerEl.style.display = "none";
  if (statusLabel && cancel) statusLabel.textContent = "Sesinizi analiz etmek için mikrofona dokunun";
}


// ── Spotify Bağlantı Yönetimi ────────────────────────────────────────────────
function updateSpotifyStatus() {
  const dot = document.getElementById("spotify-status-dot");
  const btn = document.getElementById("btn-sidebar-link-spotify");
  
  if (!currentUser || !dot || !btn) return;
  
  if (currentUser.spotify_connected) {
    dot.classList.add("linked");
    btn.classList.add("linked");
    btn.textContent = "Bağlı";
  } else {
    dot.classList.remove("linked");
    btn.classList.remove("linked");
    btn.textContent = "Bağla";
  }
  
  btn.onclick = () => {
    if (currentUser.spotify_connected) {
      showToast("Spotify hesabınız zaten bağlı.", "info");
    } else {
      const redirect = encodeURIComponent(window.location.origin + "/index.html");
      const token = api.token;
      window.location.href = `${API_BASE}/api/auth/spotify/login?redirect=${redirect}&token=${token}`;
    }
  };
}


// ── Spotify Çalma Listesi Aktarımı (Export Modal) ───────────────────────────
let activeMoodHistoryIdForExport = null;
const savedInternalPlaylistIds = new Set();
const exportedSpotifyPlaylistIds = new Set();

function setupExportModalActions() {
  const closeBtn = document.getElementById("btn-close-export-modal");
  const cancelBtn = document.getElementById("btn-cancel-export");
  const confirmBtn = document.getElementById("btn-confirm-export");
  const saveInternalBtn = document.getElementById("btn-save-internal");
  const copyTracksBtn = document.getElementById("btn-copy-tracks");
  
  if (closeBtn) closeBtn.addEventListener("click", closeExportModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeExportModal);
  
  if (copyTracksBtn) {
    copyTracksBtn.addEventListener("click", async () => {
      if (!activeMoodHistoryIdForExport) return;
      try {
        const historyData = await api.getMoodHistory();
        const historyItem = historyData.find(h => h.id === activeMoodHistoryIdForExport);
        if (historyItem && historyItem.recommended_tracks) {
            const textToCopy = historyItem.recommended_tracks.map((t, i) => `${i+1}. ${t.track_name} - ${t.artist_name}`).join("\n");
            try {
                await navigator.clipboard.writeText(textToCopy);
            } catch (e) {
                const textArea = document.createElement("textarea");
                textArea.value = textToCopy;
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
            showToast("Şarkı listesi başarıyla kopyalandı! 🎉", "success");
        } else {
            showToast("Kopyalanacak şarkı bulunamadı.", "warning");
        }
      } catch (err) {
          showToast("Kopyalama başarısız oldu.", "error");
      }
    });
  }
  
  if (saveInternalBtn) {
    saveInternalBtn.addEventListener("click", async () => {
      const nameInput = document.getElementById("playlist-name-input");
      const playlistName = nameInput ? nameInput.value.trim() : "";
      
      const errorEl = document.getElementById("modal-error-message");
      const showError = (msg) => { if (errorEl) { errorEl.textContent = msg; errorEl.style.display = "block"; } else showToast(msg, "warning"); };
      if (errorEl) errorEl.style.display = "none";

      if (!playlistName) {
        showError("Lütfen geçerli bir çalma listesi adı girin.");
        return;
      }
      
      if (!activeMoodHistoryIdForExport) {
        showError("Ruh hali geçmiş kaydı bulunamadı.");
        return;
      }

      if (savedInternalPlaylistIds.has(activeMoodHistoryIdForExport)) {
        showError("Bu çalma listesi zaten uygulamaya kaydedilmiş.");
        return;
      }
      
      saveInternalBtn.disabled = true;
      saveInternalBtn.innerHTML = '<span class="spinner"></span> Kaydediliyor...';
      
      try {
        await api.saveInternalPlaylist(activeMoodHistoryIdForExport, playlistName);
        savedInternalPlaylistIds.add(activeMoodHistoryIdForExport);
        showToast("Çalma listesi uygulamaya başarıyla kaydedildi! 🎉", "success");
        closeExportModal();
      } catch (err) {
        showToast("Kaydedilirken hata: " + err.message, "error");
      } finally {
        saveInternalBtn.disabled = false;
        saveInternalBtn.textContent = "Uygulamaya Kaydet";
      }
    });
  }

  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      const nameInput = document.getElementById("playlist-name-input");
      const playlistName = nameInput ? nameInput.value.trim() : "";
      
      const errorEl = document.getElementById("modal-error-message");
      const showError = (msg) => { if (errorEl) { errorEl.textContent = msg; errorEl.style.display = "block"; } else showToast(msg, "warning"); };
      if (errorEl) errorEl.style.display = "none";

      if (!playlistName) {
        showError("Lütfen geçerli bir çalma listesi adı girin.");
        return;
      }
      
      if (!currentUser || !currentUser.is_spotify_connected) {
        showError("Spotify hesabınız bağlı değil. Lütfen sol menüden Spotify hesabınızı bağlayın.");
        return;
      }
      
      if (!activeMoodHistoryIdForExport) {
        showError("Ruh hali geçmiş kaydı bulunamadı.");
        return;
      }
      
      if (exportedSpotifyPlaylistIds.has(activeMoodHistoryIdForExport)) {
        showError("Bu çalma listesi zaten Spotify'a aktarılmış.");
        return;
      }
      
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = '<span class="spinner"></span> Aktarılıyor...';
      
      try {
        const result = await api.exportPlaylist(activeMoodHistoryIdForExport, playlistName);
        exportedSpotifyPlaylistIds.add(activeMoodHistoryIdForExport);
        showToast("Çalma listesi Spotify kütüphanenize eklendi! 🎉", "success");
        closeExportModal();
        
        setTimeout(() => {
          if (result.playlist_url) {
            window.open(result.playlist_url, "_blank");
          }
        }, 1000);
      } catch (err) {
        if (err.message && err.message.includes("403")) {
          showError("⚠️ Spotify API Kısıtlaması: Spotify'ın 2024 geliştirici kuralları gereği, otomatik çalma listesi oluşturma işlemi yeni uygulamalar için reddedilmiştir (403 Forbidden). Lütfen 'Şarkıları Kopyala' butonunu kullanarak şarkıları manuel kopyalayınız.");
        } else {
          showToast("Çalma listesi aktarılırken hata: " + err.message, "error");
        }
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Oluştur ve Aktar";
      }
    });
  }
}

function openExportModal(moodHistoryId, emotion) {
  activeMoodHistoryIdForExport = moodHistoryId;
  const nameInput = document.getElementById("playlist-name-input");
  
  if (nameInput) {
    const today = new Date().toLocaleDateString("tr-TR", { month: "short", day: "numeric" });
    nameInput.value = `EmoTune - ${emotion || "Müzik"} [${today}]`;
  }
  
  const modal = document.getElementById("spotify-export-modal");
  if (modal) modal.classList.add("active");
}

function closeExportModal() {
  activeMoodHistoryIdForExport = null;
  const modal = document.getElementById("spotify-export-modal");
  if (modal) modal.classList.remove("active");
}

function loadProfilePage() {
  if (!currentUser) return;

  const usernameInput = document.getElementById("profile-username");
  const emailInput = document.getElementById("profile-email");
  const avatarFileInput = document.getElementById("profile-avatar-file");
  const avatarPreview = document.getElementById("profile-avatar-preview");
  
  usernameInput.value = currentUser.username || currentUser.email;
  if (emailInput) {
    emailInput.value = currentUser.email;
  }
  // File inputs cannot be pre-filled with a value for security reasons.
  
  const initial = (currentUser.username || currentUser.email || "U").trim().charAt(0).toUpperCase();
  
  function updateAvatarPreview(url) {
    if (url) {
      avatarPreview.innerHTML = `<img src="${API_BASE}${url}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
    } else {
      avatarPreview.textContent = initial;
    }
  }
  
  updateAvatarPreview(api.getAvatar() || currentUser.avatar_url);

  // Preview chosen file instantly
  avatarFileInput.onchange = () => {
    if (avatarFileInput.files && avatarFileInput.files[0]) {
      const reader = new FileReader();
      reader.onload = (e) => {
        avatarPreview.innerHTML = `<img src="${e.target.result}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
      };
      reader.readAsDataURL(avatarFileInput.files[0]);
    }
  };

  // Spotify status
  const spotDot = document.getElementById("profile-spotify-dot");
  const spotText = document.getElementById("profile-spotify-text");
  const spotBtn = document.getElementById("btn-profile-link-spotify");

  if (currentUser.spotify_connected) {
    spotDot.classList.add("linked");
    spotDot.style.background = "#1db954";
    spotDot.style.boxShadow = "0 0 10px rgba(29, 185, 84, 0.5)";
    spotText.textContent = "Spotify hesabınız bağlı.";
    spotBtn.style.display = "none";
  } else {
    spotDot.classList.remove("linked");
    spotDot.style.background = "#555";
    spotDot.style.boxShadow = "none";
    spotText.textContent = "Spotify bağlı değil.";
    spotBtn.style.display = "block";
    spotBtn.onclick = () => {
      const redirect = encodeURIComponent(window.location.origin + "/index.html");
      const token = api.token;
      window.location.href = `${API_BASE}/api/auth/spotify/login?redirect=${redirect}&token=${token}`;
    };
  }

  // Save Profile btn
  const saveProfileBtn = document.getElementById("btn-save-profile");
  saveProfileBtn.onclick = async () => {
    saveProfileBtn.disabled = true;
    saveProfileBtn.innerHTML = '<span class="spinner"></span> Kaydediliyor...';
    try {
      // Handle avatar upload if file is selected
      if (avatarFileInput.files && avatarFileInput.files[0]) {
        const uploadRes = await api.uploadAvatar(avatarFileInput.files[0]);
        currentUser.avatar_url = uploadRes.avatar_url;
        api.setAvatar(uploadRes.avatar_url || "");
      }
      
      // Handle username update
      const res = await api.updateProfile(usernameInput.value.trim(), currentUser.avatar_url || "");
      currentUser = res;
      api.setAvatar(res.avatar_url || "");
      
      showToast("Profil bilgileriniz güncellendi! 🎉", "success");
      
      // Update sidebar avatar
      document.getElementById("user-greeting").textContent = currentUser.username || currentUser.email;
      const avatarEl = document.getElementById("user-avatar");
      if (avatarEl) {
        if (res.avatar_url) {
          avatarEl.innerHTML = `<img src="${API_BASE}${res.avatar_url}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
        } else {
          avatarEl.textContent = initial;
        }
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      saveProfileBtn.disabled = false;
      saveProfileBtn.textContent = "Bilgileri Kaydet";
      avatarFileInput.value = ""; // clear file input
    }
  };

  // Password Update
  const pwdGroup = document.getElementById("profile-group-current-password");
  if (currentUser.spotify_connected) {
    pwdGroup.style.display = "none";
  } else {
    pwdGroup.style.display = "block";
  }

  const savePwdBtn = document.getElementById("btn-save-password");
  savePwdBtn.onclick = async () => {
    const currentPwd = document.getElementById("profile-current-password").value;
    const newPwd = document.getElementById("profile-new-password").value.trim();
    const errEl = document.getElementById("profile-password-error");
    
    errEl.textContent = "";
    if (newPwd.length < 6) {
      errEl.textContent = "Yeni şifre en az 6 karakter olmalıdır.";
      return;
    }
    
    savePwdBtn.disabled = true;
    savePwdBtn.innerHTML = '<span class="spinner"></span> Güncelleniyor...';
    try {
      await api.changePassword(currentPwd || null, newPwd);
      showToast("Şifreniz başarıyla güncellendi! 🎉", "success");
      document.getElementById("profile-current-password").value = "";
      document.getElementById("profile-new-password").value = "";
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      savePwdBtn.disabled = false;
      savePwdBtn.textContent = "Şifreyi Güncelle";
    }
  };
}

// ── Polaroid İndirme ─────────────────────────────────────────────────────────
window.downloadPolaroid = async function(btn) {
  if (typeof html2canvas === "undefined") {
    showToast("İndirme modülü yükleniyor, lütfen bekleyin.", "warning");
    return;
  }
  
  const card = btn.closest(".polaroid-card");
  if (!card) return;
  
  const originalDisplay = btn.style.display;
  btn.style.display = "none";
  
  const originalTransform = card.style.transform;
  card.style.transform = "none"; // Rotate iptal
  
  const originalBoxShadow = card.style.boxShadow;
  card.style.boxShadow = "none"; // İndirilen resimde gölge olmasın
  
  const originalPadding = card.style.padding;
  card.style.padding = "15px 15px 30px 15px"; // Kesin görünmesi için inline padding
  
  const tint = card.querySelector('.polaroid-tint');
  let originalMixBlend = '';
  let originalOpacity = '';
  if (tint) {
      // html2canvas mix-blend-mode desteklemediği için normal opacity ile sahte bir filtre oluşturuyoruz
      originalMixBlend = tint.style.mixBlendMode;
      originalOpacity = tint.style.opacity;
      tint.style.mixBlendMode = 'normal';
      tint.style.opacity = '0.2';
  }
  
  try {
    const canvas = await html2canvas(card, {
      scale: 3, // Daha yüksek çözünürlük
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false
    });
    
    const link = document.createElement("a");
    link.download = `emotuneai-hatira-${Date.now()}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    
    showToast("Hatıra kartı indirildi! 🎉", "success");
  } catch (err) {
    showToast("İndirme başarısız oldu.", "error");
    console.error("Polaroid indirme hatası:", err);
  } finally {
    btn.style.display = originalDisplay;
    card.style.transform = originalTransform;
    card.style.boxShadow = originalBoxShadow;
    card.style.padding = originalPadding;
    
    if (tint) {
        tint.style.mixBlendMode = originalMixBlend;
        tint.style.opacity = originalOpacity;
    }
  }
};
// ── Saved Playlists ──────────────────────────────────────────────────────────
async function loadSavedPlaylists() {
  const container = document.getElementById("saved-playlists-container");
  container.innerHTML = `
    <div class="skeleton-text skeleton" style="width: 100%; height: 100px; margin-bottom: 1rem;"></div>
    <div class="skeleton-text skeleton" style="width: 100%; height: 100px; margin-bottom: 1rem;"></div>
  `;

  try {
    const playlists = await api.getSavedPlaylists();
    
    if (!playlists || playlists.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.5; margin-bottom: 1rem;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
          <p>Henüz kaydedilmiş çalma listeniz yok.</p>
        </div>`;
      return;
    }

    container.innerHTML = playlists.map(p => {
      const date = new Date(p.created_at).toLocaleDateString("tr-TR", {
        year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });
      
      const safeName = DOMPurify.sanitize(p.name);
      
      let tracksHtml = p.tracks.map((t, index) => {
        const safeTrackName = DOMPurify.sanitize(t.track_name);
        const safeArtistName = DOMPurify.sanitize(t.artist_name);
        const safeImageUrl = t.image_url ? DOMPurify.sanitize(t.image_url) : 'https://placehold.co/50x50?text=🎵';
        
        return `
          <div style="display: flex; align-items: center; gap: 12px; font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background-color 0.2s ease; border-radius: 6px; padding: 6px;">
            <div style="opacity: 0.5; width: 20px; text-align: center; font-size: 0.8rem;">${index + 1}</div>
            <img src="${safeImageUrl}" alt="Album Art" style="width: 40px; height: 40px; border-radius: 4px; object-fit: cover; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
            <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
              <strong style="color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${safeTrackName}</strong>
              <span style="font-size: 0.8rem; opacity: 0.8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${safeArtistName}</span>
            </div>
            ${t.spotify_url ? `<a href="${DOMPurify.sanitize(t.spotify_url)}" target="_blank" title="Spotify'da Aç" style="color: var(--primary-color); opacity: 0.8; padding: 4px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            </a>` : ''}
          </div>`;
      }).join("");
      
      let exportBtnHtml = "";
      // If user is connected to Spotify, show Export button
      if (currentUser && currentUser.spotify_connected) {
        exportBtnHtml = `
          <button class="btn btn-primary" onclick="exportSavedPlaylistToSpotify(${p.id}, this)" style="margin-top: 1rem; width: 100%;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
            Spotify'a Aktar
          </button>
          <button class="btn btn-secondary" onclick="copyPlaylistTracks(${p.id}, this)" style="margin-top: 0.5rem; width: 100%; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border);">
            Şarkıları Kopyala
          </button>
        `;
      } else {
        exportBtnHtml = `
          <button class="btn btn-secondary" onclick="copyPlaylistTracks(${p.id}, this)" style="margin-top: 1rem; width: 100%; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border);">
            Şarkıları Kopyala
          </button>
          <button class="btn btn-secondary" onclick="showToast('Spotify hesabınızı bağlayarak bu listeyi aktarabilirsiniz.', 'info')" style="margin-top: 0.5rem; width: 100%; opacity: 0.7;">
            Spotify'a Aktarmak İçin Hesabınızı Bağlayın
          </button>
        `;
      }
      
      return `
        <div class="playlist-card" style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; position: relative;">
          <button class="btn-icon" onclick="deleteSavedPlaylist(${p.id}, this)" title="Sil" style="position: absolute; top: 1rem; right: 1rem; color: var(--error);">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
          </button>
          <h3 style="margin-bottom: 0.5rem; color: var(--text-primary); padding-right: 2rem;">${safeName}</h3>
          <p style="font-size: 0.8rem; color: var(--text-tertiary); margin-bottom: 1rem;">${date}</p>
          
          <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 1rem; max-height: 250px; overflow-y: auto;">
            ${tracksHtml}
          </div>
          
          ${exportBtnHtml}
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<p class="form-error">Yüklenirken hata oluştu: ${err.message}</p>`;
  }
}

async function deleteSavedPlaylist(id, btn) {
  if (!confirm("Bu çalma listesini silmek istediğinize emin misiniz?")) return;
  
  const card = btn.closest(".playlist-card");
  card.style.opacity = "0.5";
  btn.disabled = true;
  
  try {
    await api.deleteSavedPlaylist(id);
    showToast("Çalma listesi silindi.", "success");
    card.remove();
    
    const container = document.getElementById("saved-playlists-container");
    if (container.children.length === 0) {
      loadSavedPlaylists(); // reload empty state
    }
  } catch (err) {
    card.style.opacity = "1";
    btn.disabled = false;
    showToast("Silinirken hata: " + err.message, "error");
  }
}

async function exportSavedPlaylistToSpotify(id, btn) {
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Aktarılıyor...';
  
  try {
    const result = await api.exportSavedPlaylist(id);
    showToast("Çalma listesi Spotify kütüphanenize eklendi! 🎉", "success");
    
    setTimeout(() => {
      if (result.playlist_url) {
        window.open(result.playlist_url, "_blank");
      }
    }, 1000);
  } catch (err) {
    if (err.message && err.message.includes("403")) {
      showToast("⚠️ Spotify API Kısıtlaması (403 Forbidden). Lütfen 'Şarkıları Kopyala' butonunu kullanın.", "error");
    } else {
      showToast("Aktarılırken hata: " + err.message, "error");
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

async function copyPlaylistTracks(id, btn) {
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Kopyalanıyor...';
  try {
    const playlists = await api.getSavedPlaylists();
    const p = playlists.find(x => x.id === id);
    if (p && p.tracks) {
      const textToCopy = p.tracks.map((t, i) => `${i+1}. ${t.track_name} - ${t.artist_name}`).join("\\n");
      try {
        await navigator.clipboard.writeText(textToCopy);
      } catch (e) {
        const textArea = document.createElement("textarea");
        textArea.value = textToCopy;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      showToast("Şarkı listesi başarıyla kopyalandı! 🎉", "success");
    } else {
      showToast("Kopyalanacak şarkı bulunamadı.", "warning");
    }
  } catch (err) {
    showToast("Kopyalama başarısız oldu: " + err.message, "error");
  } finally {
    btn.innerHTML = originalText;
  }
}

// ── Theme Management ─────────────────────────────────────────────────────────
function setupTheme() {
  const toggleBtn = document.getElementById("btn-theme-toggle");
  const themeText = document.getElementById("theme-text");
  const themeIcon = document.getElementById("theme-icon");
  
  const toggleBtnMobile = document.getElementById("btn-theme-toggle-mobile");
  const themeTextMobile = document.getElementById("theme-text-mobile");
  const themeIconMobile = document.getElementById("theme-icon-mobile");
  
  // Load saved theme
  const savedTheme = localStorage.getItem("emotune_theme") || "dark";
  
  const applyTheme = (theme) => {
    if (theme === "light") {
      document.body.classList.add("theme-light");
      if (themeText) themeText.textContent = "Karanlık Mod";
      if (themeIcon) themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`; // Moon icon
      if (themeTextMobile) themeTextMobile.textContent = "Karanlık Mod";
      if (themeIconMobile) themeIconMobile.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
    } else {
      document.body.classList.remove("theme-light");
      if (themeText) themeText.textContent = "Aydınlık Mod";
      const sunSvg = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
      if (themeIcon) themeIcon.innerHTML = sunSvg;
      if (themeTextMobile) themeTextMobile.textContent = "Aydınlık Mod";
      if (themeIconMobile) themeIconMobile.innerHTML = sunSvg;
    }
  };
  
  applyTheme(savedTheme);
  
  const handleToggle = () => {
    const isLight = document.body.classList.contains("theme-light");
    const newTheme = isLight ? "dark" : "light";
    localStorage.setItem("emotune_theme", newTheme);
    applyTheme(newTheme);
  };

  if (toggleBtn) toggleBtn.addEventListener("click", handleToggle);
  if (toggleBtnMobile) toggleBtnMobile.addEventListener("click", handleToggle);
}

// Global click listener to close custom dropdowns
document.addEventListener('click', (e) => {
  const dropdowns = document.querySelectorAll('.custom-genre-dropdown.open');
  dropdowns.forEach(dropdown => {
    if (!dropdown.contains(e.target)) {
      dropdown.classList.remove('open');
    }
  });
});
