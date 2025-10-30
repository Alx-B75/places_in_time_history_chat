from sqlalchemy.orm import Session
from app.models_llm_profile import LlmProfile

def list_profiles(db: Session):
    rows = db.query(LlmProfile).order_by(LlmProfile.name).all()
    active = next((r.name for r in rows if getattr(r, "is_active", False)), None)
    return active, rows

def upsert_profile(db: Session, name: str, config: dict) -> LlmProfile:
    row = db.get(LlmProfile, name)
    if not row:
        row = LlmProfile(name=name)
        db.add(row)
    for k in ("provider","model","temperature","top_p","max_tokens","api_base"):
        if k in config:
            setattr(row, k, config[k])
    db.flush()
    return row

def activate_profile(db: Session, name: str) -> LlmProfile | None:
    db.query(LlmProfile).update({LlmProfile.is_active: False})
    row = db.get(LlmProfile, name)
    if not row:
        return None
    setattr(row, "is_active", True)
    db.flush()
    return row
