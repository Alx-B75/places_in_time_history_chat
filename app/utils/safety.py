"""Minimal safety and age-profile utilities.

This module provides:
- map_interaction_mode_to_age: maps UI interaction mode to age profile key.
- pre_filter: checks a user message for disallowed content per age profile.
- post_filter: optional sanitization on model output.

Feature flag: controlled by Settings.safety_enabled; callers should gate usage.
"""
from __future__ import annotations

import re
from typing import Literal, Optional, Tuple

AgeProfile = Literal["kids", "teen", "general"]

# Very lightweight keyword patterns; can be expanded later
_PROFANITY = re.compile(r"\b(fuck|shit|bitch|bastard|asshole)\b", re.IGNORECASE)
_SEXUAL = re.compile(r"\b(sex|porn|nude|explicit|erotic)\b", re.IGNORECASE)
_GRAPHIC_VIOLENCE = re.compile(r"\b(gore|decapitat|dismember|bloodbath)\b", re.IGNORECASE)
_SELF_HARM = re.compile(r"\b(kill myself|suicide|self-harm|cutting)\b", re.IGNORECASE)
_HATE = re.compile(r"\b(?:nazi|white power|kill (?:jews|muslims|blacks))\b", re.IGNORECASE)

_REFUSAL = (
    "Sorry, I can't assist with that."
)


def map_interaction_mode_to_age(mode: Optional[str]) -> AgeProfile:
    key = (mode or "").strip().lower()
    if key.startswith("young learner"):
        return "kids"
    if key.startswith("young adult"):
        return "teen"
    if key.startswith("student"):
        return "general"
    if key.startswith("master"):
        return "general"
    return "general"


def _blocked_for_kids(text: str) -> bool:
    if _PROFANITY.search(text):
        return True
    if _SEXUAL.search(text):
        return True
    if _GRAPHIC_VIOLENCE.search(text):
        return True
    if _SELF_HARM.search(text):
        return True
    if _HATE.search(text):
        return True
    return False


def _blocked_for_teen(text: str) -> bool:
    # Teens: allow mild mentions, block explicit sexual content, hate, self-harm guidance, graphic gore
    if _SEXUAL.search(text):
        return True
    if _GRAPHIC_VIOLENCE.search(text):
        return True
    if _HATE.search(text):
        return True
    if _SELF_HARM.search(text):
        return True
    return False


def pre_filter(message: str, age_profile: AgeProfile) -> Tuple[bool, str]:
    """Return (blocked, safe_message). If blocked, safe_message is the refusal copy.
    """
    text = message or ""
    ap = (age_profile or "general").lower()
    if ap == "kids":
        return (_blocked_for_kids(text), _REFUSAL)
    if ap == "teen":
        return (_blocked_for_teen(text), _REFUSAL)
    # general: only extreme content blockers (hate/self-harm instructions)
    if _HATE.search(text) or _SELF_HARM.search(text):
        return (True, _REFUSAL)
    return (False, "")


def post_filter(answer: str, age_profile: AgeProfile) -> str:
    """Optionally sanitize an answer based on age profile.
    Currently minimal: if kids and profanity slips through, replace with ***.
    """
    ap = (age_profile or "general").lower()
    if ap == "kids":
        return _PROFANITY.sub("***", answer or "")
    return answer or ""
