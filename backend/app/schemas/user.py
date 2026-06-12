from pydantic import BaseModel, EmailStr
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    spotify_connected: bool = False

    class Config:
        from_attributes = True

class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str