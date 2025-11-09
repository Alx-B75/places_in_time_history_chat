"""Initialize chat_history.db with default users and optional sample data.

This script is safe to run multiple times; it creates users only if missing.
"""
import sys
from pathlib import Path

# Ensure repo root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app import crud, schemas
from app.utils.security import hash_password


def main() -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Admin user
        if not crud.get_user_by_username(db, username="admin@example.com"):
            admin_user = schemas.UserCreate(username="admin@example.com", hashed_password=hash_password("Admin!123"))
            user = crud.create_user(db, admin_user)
            user.role = "admin"
            db.add(user)
            print("Created admin@example.com (Admin!123)")
        else:
            print("Admin user already exists.")
        # Sample user
        if not crud.get_user_by_username(db, username="sample@example.com"):
            sample_user = schemas.UserCreate(username="sample@example.com", hashed_password=hash_password("Sample!123"))
            crud.create_user(db, sample_user)
            print("Created sample@example.com (Sample!123)")
        else:
            print("Sample user already exists.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
