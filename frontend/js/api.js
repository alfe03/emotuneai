// Ortama göre API_BASE belirleme
let API_BASE = "";

if (window.location.hostname === "emotuneai.utkuaksu.com" || window.location.hostname.endsWith(".github.io")) {
    // UYARI: Github Pages sadece statik HTML sunar, backend barýndýrmaz!
    // Bu yüzden canlý site, sizin bilgisayarýnýzdaki backend'e baðlanmaya çalýþýyor.
    // Bilgisayarýnýzdaki tünel kapandýðýnda canlý site bozulur. Gerçek çözüm backend'i Render/Vercel/Heroku'ya yüklemektir.
    API_BASE = "https://a344f2855cc8ed.lhr.life"; // Geçici tünel adresi (Kapandýðý için þu an çalýþmýyor)
} else if ((window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") && window.location.port !== "8080" && window.location.port !== "") {
    API_BASE = "http://127.0.0.1:8000";
} else {
    // Local Nginx (8080) veya Expo Localtunnel (silver-readers-fold.loca.lt) kullanýrken
    // Nginx zaten /api isteklerini backend'e yönlendirdiði için API_BASE boþ býrakýlýr.
    API_BASE = "";
}

class EmoTuneAPI {
  constructor() {
    this.token = localStorage.getItem('token');
  }

  async register(username, email, password) {
    const res = await fetch(${API_BASE}/api/auth/register, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password })
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Kayýt baþarýsýz');
    }
    return res.json();
  }

  async login(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email); // OAuth2PasswordRequestForm expects 'username'
    formData.append('password', password);

    const res = await fetch(${API_BASE}/api/auth/login, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: formData
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Giriþ baþarýsýz');
    }
    const data = await res.json();
    this.token = data.access_token;
    localStorage.setItem('token', this.token);
    return data;
  }

  logout() {
    this.token = null;
    localStorage.removeItem('token');
  }

  // --- Profile / Check Auth ---
  async getMe() {
    if (!this.token) throw new Error("Token yok");
    const res = await fetch(${API_BASE}/api/auth/me, {
      headers: { 'Authorization': Bearer  }
    });
    if (!res.ok) throw new Error('Oturum geçersiz');
    return res.json();
  }

  // --- Mood Analysis ---
  async analyzeText(text) {
    const res = await fetch(${API_BASE}/api/mood/analyze/text, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': Bearer 
      },
      body: JSON.stringify({ text })
    });
    if (!res.ok) throw new Error('Metin analizi baþarýsýz');
    return res.json();
  }

  async analyzeFace(imageBlob) {
    const formData = new FormData();
    formData.append('file', imageBlob, 'face.jpg');
    
    const res = await fetch(${API_BASE}/api/mood/analyze/face, {
      method: 'POST',
      headers: {
        'Authorization': Bearer 
      },
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Yüz analizi baþarýsýz');
    }
    return res.json();
  }

  async analyzeVoice(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'voice.webm');
    
    const res = await fetch(${API_BASE}/api/mood/analyze/voice, {
      method: 'POST',
      headers: {
        'Authorization': Bearer 
      },
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Ses analizi baþarýsýz');
    }
    return res.json();
  }

  // --- Music Recommendation ---
  async getRecommendations(mood) {
    const res = await fetch(${API_BASE}/api/music/recommend?mood=, {
      headers: { 'Authorization': Bearer  }
    });
    if (!res.ok) throw new Error('Müzik önerileri alýnamadý');
    return res.json();
  }

  // --- History ---
  async getHistory() {
    const res = await fetch(${API_BASE}/api/history/, {
      headers: { 'Authorization': Bearer  }
    });
    if (!res.ok) throw new Error('Geçmiþ alýnamadý');
    return res.json();
  }
}

const api = new EmoTuneAPI();
