
import os
import httpx
from app.config.llm_config import llm_config


class LlmClient:
    def generate(self, messages, temperature=None, top_p=None, max_tokens=None, model=None):
        provider = (llm_config.provider or "openai").lower()
        if provider == "openrouter":
            return self._gen_openrouter(messages, temperature, top_p, max_tokens, model)
        else:
            return self._gen_openai(messages, temperature, top_p, max_tokens, model)

    def _gen_openrouter(self, messages, temperature, top_p, max_tokens, model):
        base = (llm_config.api_base or "https://openrouter.ai/api/v1").rstrip("/")
        url = f"{base}/chat/completions"
        api_key = os.getenv("OPENROUTER_API_KEY", llm_config.api_key)
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter recommends these two headers for identification/rate-limits:
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:8000"),
            "X-Title": os.getenv("OPENROUTER_X_TITLE", "Places-in-Time History Chat"),
        }
        payload = {
            "model": model if model is not None else llm_config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else llm_config.temperature,
            "top_p": top_p if top_p is not None else llm_config.top_p,
            "max_tokens": max_tokens if max_tokens is not None else llm_config.max_tokens,
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        return {
            "model": data.get("model", payload["model"]),
            "usage": data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            "choices": data.get("choices", []),
        }

    def _gen_openai(self, messages, temperature, top_p, max_tokens, model):
        base = (llm_config.api_base or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions"
        api_key = os.getenv("OPENAI_API_KEY", llm_config.api_key)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model if model is not None else llm_config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else llm_config.temperature,
            "top_p": top_p if top_p is not None else llm_config.top_p,
            "max_tokens": max_tokens if max_tokens is not None else llm_config.max_tokens,
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        return {
            "model": data.get("model", payload["model"]),
            "usage": data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            "choices": data.get("choices", []),
        }

llm_client = LlmClient()
 # This line is removed as it is a duplicate and invalid.
