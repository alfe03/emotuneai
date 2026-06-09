import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app.core.config import settings
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import RedirectResponse
from typing import cast
from sqlalchemy.orm import Session
from urllib.parse import unquote, urlparse, parse_qsl, urlencode, urlunparse
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.auth_service import create_user, authenticate_user, create_access_token, get_user_by_email
from app.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.models.models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_FRONTEND_URL = settings.FRONTEND_URL

def build_redirect_url(base_url: str, params: dict) -> str:
    if not base_url:
        base_url = DEFAULT_FRONTEND_URL

    try:
        parsed = urlparse(base_url)
        query = dict(parse_qsl(parsed.query))
        query.update(params)
        new_query = urlencode(query)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return DEFAULT_FRONTEND_URL

def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope="user-read-private user-read-email"
    )

@router.get("/spotify/login")
def spotify_login(request: Request):
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Spotify ayarları (CLIENT_ID/SECRET) yapılmamış.")
    sp_oauth = get_spotify_oauth()
    redirect_target = request.query_params.get("redirect") or DEFAULT_FRONTEND_URL
    state = redirect_target
    auth_url = sp_oauth.get_authorize_url(state=state)
    return RedirectResponse(url=auth_url)

@router.get("/spotify/callback")
def spotify_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    state = request.query_params.get("state")
    frontend_url = unquote(state) if state else DEFAULT_FRONTEND_URL
    if not (frontend_url.startswith("http://") or frontend_url.startswith("https://")):
        frontend_url = DEFAULT_FRONTEND_URL
    
    if error:
        logger.warning(f"Spotify'dan hata döndü: {error}")
        return RedirectResponse(url=build_redirect_url(frontend_url, {"error": error}))
        
    if not code:
        logger.warning("Spotify 'code' parametresi göndermedi!")
        return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "no_code"}))

    sp_oauth = get_spotify_oauth()
    try:
        logger.info("Token alınıyor...")
        token_info = sp_oauth.get_access_token(code)
        access_token = token_info.get("access_token")
        logger.info("Token başarıyla alındı.")
    except Exception as e:
        logger.error(f"Token alınırken hata: {str(e)}")
        return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "token_exception"}))

    try:
        sp = spotipy.Spotify(auth=access_token)
        user_info = sp.current_user()
        if user_info:
            logger.info(f"Spotify Kullanıcı Bilgisi: {user_info.get('id')} - {user_info.get('email')}")
        
        email = user_info.get("email") if user_info else None
        if not email:
            spotify_id = user_info.get('id') if user_info else None
            email = f"{spotify_id}@spotify.com"
            
        user_data = user_info or {}
        # Ensure username is always a string (fallback to email local-part or generic name)
        username = user_data.get("display_name") or user_data.get("id") or (email.split('@')[0] if email else "spotify_user")
        username = str(username)
        images = user_data.get("images") or []
        avatar_url = images[0].get("url") if images else None
        
        user = get_user_by_email(db, email)
        if not user:
            import secrets
            import string
            random_password = "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
            user = create_user(db, email=email, username=username, password=random_password)
            logger.info("Yeni kullanıcı veritabanına kaydedildi.")
        else:
            logger.info("Mevcut kullanıcı ile giriş yapıldı.")

        jwt_token = create_access_token(cast(int, user.id))
        
        params = {"token": jwt_token}
        if avatar_url:
            params["avatar"] = avatar_url
        redirect_url = build_redirect_url(frontend_url, params)
        logger.info(f"Frontend'e yönlendiriliyor: {redirect_url}")
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Kullanıcı işlemlerinde hata: {str(e)}")
        return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "user_creation_failed"}))

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, request.email):
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    user = create_user(db, request.email, request.username, request.password)
    token = create_access_token(cast(int, user.id))
    return {"access_token": token, "token_type": "bearer"}

from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, login_request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_request.email, login_request.password)
    if not user:
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    token = create_access_token(cast(int, user.id))
    return {"access_token": token}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
