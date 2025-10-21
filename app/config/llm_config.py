from pydantic import BaseModel, Field
from typing import Optional

class LLMRuntimeConfig(BaseModel):
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4")
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.3
    top_p: float = 1.0
    max_tokens: int = 1024

import os
llm_config = LLMRuntimeConfig(
    api_key=os.environ.get("OPENAI_API_KEY"),
    api_base=os.environ.get("OPENAI_API_BASE")
)
