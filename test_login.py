import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.core.database import SessionLocal
from app.schemas.user import LoginRequest
from app.routers.auth import login

db = SessionLocal()
try:
    req = LoginRequest(email="test@test.com", password="password")
    res = login(req, db)
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
