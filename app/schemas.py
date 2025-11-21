"""
Pydantic schemas for request and response validation, including admin RBAC and audit logs.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    """
    Credential payload used for login and registration requests.
    """

    username: str
    password: str


class UserRegisterRequest(BaseModel):
    """
    Registration payload for the JSON /auth/register route.
    """

    username: str
    password: str
    email: str


class UserCreate(BaseModel):
    """
    Input schema for registering a new user.
    """

    username: str
    hashed_password: str


class UserRead(BaseModel):
    """
    Response schema representing a user.
    """

    id: int
    username: str
    role: str = Field(default="user")

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    """
    Admin schema for updating a user's role.
    """

    role: str = Field(pattern="^(user|admin)$")


class ThreadCreate(BaseModel):
    """
    Input schema for creating a new conversation thread.
    """

    user_id: int
    title: Optional[str] = None
    figure_slug: Optional[str] = None
    age_profile: Optional[str] = None


class ThreadRead(ThreadCreate):
    """
    Response schema for an existing thread.
    """

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadReadWithPreview(ThreadRead):
    """Thread response enriched with the first user message for context previews."""

    first_user_message: Optional[str] = None
    first_message_at: Optional[datetime] = None


class ChatMessageCreate(BaseModel):
    """
    Input schema for creating a single message in a conversation.
    """

    user_id: Optional[int] = None
    role: str
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    thread_id: Optional[int] = None
    summary_of: Optional[int] = None


class ChatMessageRead(ChatMessageCreate):
    """
    Response schema for a stored chat message.
    """

    id: int
    timestamp: datetime
    sources_json: Optional[str] = None

    model_config = {"from_attributes": True}


class ChatCreateRequest(BaseModel):
    """
    Input schema for client-submitted chat creation.
    """

    message: str
    user_id: int
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    figure_slug: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """
    Input schema for requesting an assistant completion.
    """

    user_id: int
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    thread_id: Optional[int] = None


class AskRequest(BaseModel):
    """
    Input schema for 'ask a historical figure' endpoint.
    """

    user_id: int
    message: str
    figure_slug: Optional[str] = None
    source_page: Optional[str] = None
    model_used: Optional[str] = None
    thread_id: Optional[int] = None
    skip_llm: Optional[bool] = False
    age_profile: Optional[str] = None


class AskResponse(BaseModel):
    """
    Response schema returned by the /ask endpoint.
    """

    id: int
    user_id: int
    role: str
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    thread_id: Optional[int] = None
    timestamp: datetime
    # Optional signal to clients that user must verify email
    email_verification_required: bool | None = False

    model_config = {"from_attributes": True}


class FigureContextRead(BaseModel):
    """
    Schema for context entries tied to a historical figure.
    """

    id: int
    figure_slug: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    content_type: Optional[str] = None
    content: str
    is_manual: int

    model_config = {"from_attributes": True}


class HistoricalFigureRead(BaseModel):
    """
    Summary schema for listing historical figures.
    NOTE: includes persona_prompt (optional) so the admin editor can load it without a separate detail GET.
    """

    id: int
    name: str
    slug: str
    era: Optional[str] = None
    roles: Optional[str] = None
    image_url: Optional[str] = None
    short_summary: Optional[str] = None
    persona_prompt: Optional[str] = None

    model_config = {"from_attributes": True}


class HistoricalFigureDetail(HistoricalFigureRead):
    """
    Detailed schema for a single historical figure.
    """

    long_bio: Optional[str] = None
    echo_story: Optional[str] = None
    quote: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    main_site: Optional[str] = None
    related_sites: Optional[str] = None
    sources: Optional[str] = None
    wiki_links: Optional[str] = None
    verified: Optional[int] = None
    contexts: List[FigureContextRead] = Field(default_factory=list)

    @field_validator("birth_year", "death_year", mode="before")
    @classmethod
    def _normalize_year(cls, v: Any) -> Optional[int]:
        """
        Coerce empty strings to None and numeric strings to int.
        """
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if s.lstrip("-").isdigit():
                try:
                    return int(s)
                except ValueError:
                    return None
            return None
        return None

    model_config = {"from_attributes": True}


class HistoricalFigureUpdate(BaseModel):
    """Schema for partial updates to a historical figure."""

    name: Optional[str] = None
    slug: Optional[str] = None
    era: Optional[str] = None
    roles: Optional[str] = None
    image_url: Optional[str] = None
    short_summary: Optional[str] = None
    long_bio: Optional[str] = None
    echo_story: Optional[str] = None
    quote: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    main_site: Optional[str] = None
    related_sites: Optional[str] = None
    sources: Optional[str] = None
    wiki_links: Optional[str] = None
    verified: Optional[int] = None
    persona_prompt: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditLogRead(BaseModel):
    """
    Response schema for audit log entries.
    """

    id: int
    created_at: datetime
    actor_user_id: int
    action: str
    object_type: str
    object_id: Optional[str] = None
    diff_json: Optional[str] = None
    ip: Optional[str] = None

    model_config = {"from_attributes": True}


class FavoriteCreate(BaseModel):
    figure_slug: str


class FavoriteRead(BaseModel):
    id: int
    user_id: int
    figure_slug: str

    model_config = {"from_attributes": True}


class UserAdminRead(BaseModel):
    id: int
    username: str
    role: str
    email: str | None = None
    email_verified: bool = False


class AdminEmailRequest(BaseModel):
    subject: str
    body: str
