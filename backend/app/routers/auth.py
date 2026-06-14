import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app.core.config import settings
from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse
import os
import shutil
import uuid
from typing import cast
from sqlalchemy.orm import Session
from urllib.parse import unquote, urlparse, parse_qsl, urlencode, urlunparse
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.auth_service import create_user, authenticate_user, create_access_token, get_user_by_email, get_user_by_id, decode_access_token, get_user_by_username, hash_password, verify_password
from app.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserResponse, ChangePasswordRequest, UpdateProfileRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.services.email_service import send_welcome_email, send_reset_password_email
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
        scope="user-read-private user-read-email playlist-modify-public playlist-modify-private",
        show_dialog=True
    )

@router.get("/spotify/login")
def spotify_login(request: Request):
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Spotify ayarları (CLIENT_ID/SECRET) yapılmamış.")
    sp_oauth = get_spotify_oauth()
    redirect_target = request.query_params.get("redirect") or DEFAULT_FRONTEND_URL
    token = request.query_params.get("token")
    
    # Eğer token varsa state'e ekle: "redirect|token"
    if token:
        state = f"{redirect_target}|{token}"
    else:
        state = redirect_target
        
    auth_url = sp_oauth.get_authorize_url(state=state)
    return RedirectResponse(url=auth_url)

@router.get("/spotify/callback")
def spotify_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    state = request.query_params.get("state")
    
    frontend_url = DEFAULT_FRONTEND_URL
    linking_token = None
    
    if state:
        unquoted_state = unquote(state)
        if "|" in unquoted_state:
            parts = unquoted_state.split("|", 1)
            frontend_url = parts[0]
            linking_token = parts[1]
        else:
            frontend_url = unquoted_state
            
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
        refresh_token = token_info.get("refresh_token")
        expires_in = token_info.get("expires_in", 3600)
        import time
        expires_at = int(time.time() + expires_in)
        logger.info("Token başarıyla alındı.")
    except Exception as e:
        logger.error(f"Token alınırken hata: {str(e)}")
        return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "token_exception"}))

    try:
        sp = spotipy.Spotify(auth=access_token)
        user_info = sp.current_user()
        if user_info:
            logger.info(f"Spotify kullanıcısı alındı: {user_info.get('id')}")
        
        email = user_info.get("email") if user_info else None
        if not email:
            spotify_id = user_info.get('id') if user_info else None
            email = f"{spotify_id}@spotify.com"
            
        user_data = user_info or {}
        username = user_data.get("display_name") or user_data.get("id") or (email.split('@')[0] if email else "spotify_user")
        username = str(username)
        images = user_data.get("images") or []
        avatar_url = images[0].get("url") if images else None
        
        # HESAP BAĞLAMA (LINKING FLOW)
        if linking_token:
            user_id = decode_access_token(linking_token)
            if not user_id:
                logger.warning("Geçersiz linking token'ı ile hesap bağlama denendi.")
                return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "invalid_linking_token"}))
                
            user = get_user_by_id(db, user_id)
            if not user:
                logger.warning(f"Bağlanmak istenen user_id={user_id} bulunamadı.")
                return RedirectResponse(url=build_redirect_url(frontend_url, {"error": "user_not_found"}))
                
            logger.info(f"Spotify hesabı mevcut kullanıcıya ({user.username}) bağlanıyor.")
        else:
            # NORMAL GİRİŞ/KAYIT AKIŞI
            user = get_user_by_email(db, email)
            if not user:
                import secrets
                import string
                random_password = "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
                user = create_user(db, email=email, username=username, password=random_password)
                logger.info("Yeni kullanıcı veritabanına kaydedildi.")
            else:
                logger.info("Mevcut kullanıcı ile giriş yapıldı.")
        
        # Token bilgilerini kullanıcının veritabanı satırına kaydet/güncelle
        user.spotify_access_token = access_token
        if refresh_token:
            user.spotify_refresh_token = refresh_token
        user.spotify_token_expires_at = expires_at
        db.commit()

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
def register(request: RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if get_user_by_email(db, request.email):
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    if get_user_by_username(db, request.username):
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten alınmış")
    user = create_user(db, request.email, request.username, request.password)
    token = create_access_token(cast(int, user.id))
    
    # Send welcome email in the background
    background_tasks.add_task(send_welcome_email, user.email, user.username)
    
    return {"access_token": token, "token_type": "bearer"}

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = get_user_by_email(db, request.email)
    if not user:
        # We still return 200 so we don't leak which emails exist
        return {"message": "Eğer e-posta sistemde kayıtlıysa, şifre sıfırlama bağlantısı gönderildi."}
        
    reset_token = create_access_token(cast(int, user.id))
    background_tasks.add_task(send_reset_password_email, user.email, reset_token)
    
    return {"message": "Eğer e-posta sistemde kayıtlıysa, şifre sıfırlama bağlantısı gönderildi."}

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user_id = decode_access_token(request.token)
        if not user_id:
            raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş bağlantı.")
            
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş bağlantı.")
            
        if len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="Yeni şifre en az 6 karakter olmalıdır.")
            
        user.hashed_password = hash_password(request.new_password)
        db.commit()
        return {"message": "Şifreniz başarıyla değiştirildi. Yeni şifrenizle giriş yapabilirsiniz."}
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş bağlantı.")

from app.core.limiter import limiter

@router.post("/login", response_model=TokenResponse)
@limiter.limit("50/minute")
def login(request: Request, login_request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_request.email, login_request.password)
    if not user:
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    token = create_access_token(cast(int, user.id))
    return {"access_token": token}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(request: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Spotify kullanan ve henüz kendi şifresini belirlememiş kullanıcılar (yani mevcut şifreyi bilmeyenler)
    # için mevcut şifre doğrulamasını atlıyoruz.
    if current_user.spotify_connected and not request.current_password:
        pass
    else:
        if not request.current_password:
            raise HTTPException(status_code=400, detail="Mevcut şifrenizi girmelisiniz.")
        if not verify_password(request.current_password, str(current_user.hashed_password)):
            raise HTTPException(status_code=400, detail="Mevcut şifre hatalı.")
            
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 6 karakter olmalıdır.")
        
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()
    return {"message": "Şifre başarıyla güncellendi."}

@router.put("/update-profile", response_model=UserResponse)
def update_profile(request: UpdateProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if request.username != current_user.username:
        if get_user_by_username(db, request.username):
            raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten alınmış")
        current_user.username = request.username
    
    if request.avatar_url is not None:
        current_user.avatar_url = request.avatar_url

    db.commit()
    db.refresh(current_user)
    return current_user

AVATAR_DIR = "static/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

@router.post("/upload-avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Sadece resim dosyaları yüklenebilir.")
    
    filename_str = file.filename or "avatar.png"
    ext = filename_str.split(".")[-1] if "." in filename_str else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(AVATAR_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    avatar_url = f"/static/avatars/{filename}"
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)
    
    return current_user

