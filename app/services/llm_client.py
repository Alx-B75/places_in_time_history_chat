import time
import logging
from typing import List, Dict, Any
from app.config.llm_config import llm_config



class LLMClient:
    def generate(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = None,
        top_p: float = None,
        max_tokens: int = None,
        model: str = None
    ) -> Dict[str, Any]:
        start = time.time()
        provider = llm_config.provider
        active_model = model or llm_config.model
        use_temp = llm_config.temperature if temperature is None else temperature
        use_top_p = llm_config.top_p if top_p is None else top_p
        use_max = llm_config.max_tokens if max_tokens is None else max_tokens

        if provider in ("openai", "openrouter"):
            from openai import OpenAI
            base_url = llm_config.api_base or (
                "https://openrouter.ai/api/v1" if provider == "openrouter" else "https://api.openai.com/v1"
            )
            client = OpenAI(api_key=llm_config.api_key, base_url=base_url)
            resp_obj = client.chat.completions.create(
                model=active_model,
                messages=messages,
                temperature=use_temp,
                top_p=use_top_p,
                max_tokens=use_max
            )
            resp = resp_obj.model_dump()
        elif provider == "gemini":
            raise NotImplementedError("Gemini integration pending.")
        elif provider == "llama":
            raise NotImplementedError("Llama integration pending.")
        else:
            raise ValueError(f"Unknown provider: {provider}")

        latency_ms = round((time.time() - start) * 1000)
        usage = resp.get("usage", {})
        logging.info(
            "LLM call provider=%s model=%s latency_ms=%s usage=%s",
            provider, active_model, latency_ms, usage
        )
        return resp


# Singleton instance for use throughout the app
llm_client = LLMClient()

# Singleton instance for use throughout the app
llm_client = LLMClient()

# Singleton instance for use throughout the app
llm_client = LLMClient()
