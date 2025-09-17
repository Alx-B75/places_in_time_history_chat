"""Unified prompt building utilities for historical figure chats.

This module centralizes all logic for composing prompts. It ensures
a consistent pipeline across user, guest, and system routes. Persona,
instruction contexts, and vector-based retrieval (RAG) are combined
to form the full prompt passed to the AI.
"""

from typing import Any, Dict, List, Optional, Tuple

from app import models
from app.vector.context_retriever import search_figure_context


def _extract_instruction_text(figure: Optional[models.HistoricalFigure]) -> str:
    """
    Return concatenated instruction text from a figure's contexts.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        Figure instance with contexts preloaded.

    Returns
    -------
    str
        Concatenated instruction text or an empty string.
    """
    if not figure or not getattr(figure, "contexts", None):
        return ""
    labels = {"instruction", "instructions", "persona", "system"}
    blocks: List[str] = []
    for ctx in figure.contexts:
        ctype = (ctx.content_type or "").strip().lower()
        if ctype in labels:
            text = (ctx.content or "").strip()
            if text:
                blocks.append(text)
    return "\n\n".join(blocks).strip()


def _build_system_prompt(
    figure: Optional[models.HistoricalFigure], db_instructions: str = ""
) -> str:
    """
    Compose the system prompt from persona, fallback text, and DB instructions.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        The historical figure associated with the request.
    db_instructions : str
        Instruction text retrieved from figure contexts.

    Returns
    -------
    str
        The system prompt text to seed the assistant.
    """
    if figure and getattr(figure, "persona_prompt", None):
        base = figure.persona_prompt
    elif figure:
        base = (
            f"You are {figure.name}, a historical figure. "
            "Answer clearly, accurately, and concisely. "
            "If something is uncertain or debated, state that explicitly."
        )
    else:
        base = (
            "You are a helpful and accurate historical guide. "
            "Answer clearly and concisely. If a fact is uncertain, say so."
        )
    db_instructions = (db_instructions or "").strip()
    if db_instructions:
        return f"{base}\n\n{db_instructions}"
    return base


def _compact_context(
    contexts: List[Dict[str, Any]], max_chars: int = 4000
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Compact context entries into a single string and return sources.

    Parameters
    ----------
    contexts : list[dict]
        List of context records.
    max_chars : int
        Character budget for the compacted context text.

    Returns
    -------
    tuple[str, list[dict]]
        The compacted context text and a list of source descriptors.
    """
    if not contexts:
        return "", []
    pieces: List[str] = []
    sources: List[Dict[str, Any]] = []
    total = 0
    for c in contexts:
        src = c.get("source_name") or "source"
        url = c.get("source_url")
        text = c.get("content") or ""
        snippet = text.strip()
        if not snippet:
            continue
        block = f"[{src}] {snippet}"
        if total + len(block) > max_chars and pieces:
            break
        pieces.append(block)
        total += len(block)
        sources.append({"source_name": src, "source_url": url})
    return "\n\n".join(pieces), sources


def _figure_context_payload(
    figure: Optional[models.HistoricalFigure],
) -> List[Dict[str, Any]]:
    """
    Convert a HistoricalFigure with contexts into a list of plain dicts.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        The historical figure instance.

    Returns
    -------
    list[dict]
        List of context dictionaries suitable for compaction.
    """
    results: List[Dict[str, Any]] = []
    if not figure or not getattr(figure, "contexts", None):
        return results
    for ctx in figure.contexts:
        results.append(
            {
                "figure_slug": ctx.figure_slug,
                "source_name": ctx.source_name,
                "source_url": ctx.source_url,
                "content_type": ctx.content_type,
                "content": ctx.content,
                "is_manual": ctx.is_manual,
            }
        )
    return results


def build_prompt(
    figure: Optional[models.HistoricalFigure],
    user_message: str,
    thread_history: List[Dict[str, str]],
    max_context_chars: int = 4000,
    use_rag: bool = True,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Build the full prompt messages and sources for the AI model.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        Historical figure associated with the chat.
    user_message : str
        The current user input.
    thread_history : list[dict]
        Prior messages in the thread.
    max_context_chars : int
        Character budget for context text.
    use_rag : bool
        Whether to call the vector retriever.

    Returns
    -------
    tuple[list[dict], list[dict]]
        The formatted messages for the AI and a list of sources.
    """
    instruction_text = _extract_instruction_text(figure)
    system_prompt = _build_system_prompt(figure, instruction_text)

    contexts: List[Dict[str, Any]] = []
    if use_rag and figure and getattr(figure, "slug", None):
        try:
            contexts = search_figure_context(user_message, figure.slug, top_k=5)
        except Exception:
            contexts = []
    if not contexts:
        contexts = _figure_context_payload(figure) if figure else []

    ctx_text, sources = _compact_context(contexts, max_chars=max_context_chars)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if ctx_text:
        messages.append({"role": "system", "content": f"Context for reference:\n{ctx_text}"})
    for m in thread_history:
        messages.append({"role": m["role"], "content": m["message"]})
    messages.append({"role": "user", "content": user_message})

    return messages, sources
