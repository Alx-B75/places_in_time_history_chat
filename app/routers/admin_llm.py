"""
Admin LLM configuration and health endpoints.

Exposes:
- PATCH /admin/llm
- GET   /admin/llm/health
- GET   /admin/health/llm (compat)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.llm_config import llm_config
import app.services.llm_client as llm_mod
from app.utils.security import admin_required

router = APIRouter(prefix="/admin", tags=["Admin LLM"])


@router.patch("/llm")
def patch_llm(payload: dict, _=Depends(admin_required)):
    provider = (payload.get("provider") or llm_config.provider)
    model = (payload.get("model") or llm_config.model)
    llm_config.provider = provider
    llm_config.model = model
    return {"active": {"provider": llm_config.provider, "model": llm_config.model}}


@router.get("/llm/health")
def llm_health(_=Depends(admin_required)):
    # Minimal probe; tests monkeypatch llm_client.generate
    resp = llm_mod.llm_client.generate(messages=[{"role": "system", "content": "ping"}], temperature=0.0, max_tokens=5, model=llm_config.model)
    return {"provider": llm_config.provider, "model": resp.get("model", llm_config.model), "usage": resp.get("usage")}


@router.get("/health/llm")
def llm_health_compat(_=Depends(admin_required)):
    # Alias for older path used in tests
    return llm_health()
