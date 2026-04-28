import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.core.database import SessionLocal, engine
from app.models import models
from app.schemas.user import RegisterRequest
from app.routers.auth import register

# Create tables
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    req = RegisterRequest(email="test@test.com", username="test", password="password")
    res = register(req, db)
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
