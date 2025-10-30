from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, func
from app.database import Base as ChatBase  # chat DB Base

class LlmProfile(ChatBase):
    __tablename__ = "llm_profiles"
    name = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    temperature = Column(Float, nullable=True)
    top_p = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    api_base = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
