## Phase 1: Runtime LLM Switchability

### Switching Providers
PATCH /admin/llm with a JSON body to change provider, model, key, base, temperature, top_p, or max_tokens at runtime. No restart required.

### Health Check
GET /admin/health/llm returns provider, model, and usage for a minimal LLM call.

### Known Stubs
Gemini and Llama are stubbed (NotImplementedError).

### Future Phases
- Add more providers
- Support A/B testing
- Advanced admin controls

### Adapter
All LLM calls go through LLMClient().generate().
