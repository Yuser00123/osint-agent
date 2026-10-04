import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("osint.llm")

class LLMRouter:
    """
    Unified multi-provider AI gateway.
    Supports Google Gemini, Groq, OpenRouter, OpenAI, and Anthropic Claude
    with zero external heavy SDK bloat and automatic fallback on rate limits/failures.
    """

    def __init__(self):
        self.providers = ["gemini", "groq", "openrouter", "openai", "anthropic"]
        self.default_provider = settings.DEFAULT_LLM_PROVIDER.lower()

    def get_available_providers(self) -> List[str]:
        available = []
        if settings.GEMINI_API_KEY:
            available.append("gemini")
        if settings.GROQ_API_KEY:
            available.append("groq")
        if settings.OPENROUTER_API_KEY:
            available.append("openrouter")
        if settings.OPENAI_API_KEY:
            available.append("openai")
        if settings.ANTHROPIC_API_KEY:
            available.append("anthropic")
        return available

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Executes a prompt across the chosen provider with automatic fallback.
        Returns a dict: {"text": str, "provider_used": str, "model_used": str}
        """
        requested_provider = provider or self.default_provider
        available = self.get_available_providers()
        
        # Priority order: requested first, then rest of available
        ordered_providers = [requested_provider] if requested_provider in available else []
        for p in available:
            if p not in ordered_providers:
                ordered_providers.append(p)
                
        if not ordered_providers:
            # If no provider API key configured, provide clear message
            return {
                "text": "No AI API key is configured. Please provide a GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in your .env file.",
                "provider_used": "none",
                "model_used": "none",
                "error": "Missing API keys"
            }

        last_error = None
        for prov in ordered_providers:
            try:
                if prov == "gemini":
                    text = await self._call_gemini(messages, system_prompt, temperature, max_tokens)
                    return {"text": text, "provider_used": "gemini", "model_used": settings.GEMINI_MODEL}
                elif prov == "groq":
                    text = await self._call_groq(messages, system_prompt, temperature, max_tokens)
                    return {"text": text, "provider_used": "groq", "model_used": settings.GROQ_MODEL}
                elif prov == "openrouter":
                    text = await self._call_openrouter(messages, system_prompt, temperature, max_tokens)
                    return {"text": text, "provider_used": "openrouter", "model_used": settings.OPENROUTER_MODEL}
                elif prov == "openai":
                    text = await self._call_openai(messages, system_prompt, temperature, max_tokens)
                    return {"text": text, "provider_used": "openai", "model_used": settings.OPENAI_MODEL}
                elif prov == "anthropic":
                    text = await self._call_anthropic(messages, system_prompt, temperature, max_tokens)
                    return {"text": text, "provider_used": "anthropic", "model_used": settings.ANTHROPIC_MODEL}
            except Exception as e:
                logger.warning(f"Provider {prov} failed: {e}. Attempting fallback...")
                last_error = str(e)
                continue

        raise RuntimeError(f"All available LLM providers failed. Last error: {last_error}")

    # --- GEMINI IMPLEMENTATION ---
    async def _call_gemini(self, messages, system_prompt, temperature, max_tokens) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
            
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    # --- GROQ IMPLEMENTATION ---
    async def _call_groq(self, messages, system_prompt, temperature, max_tokens) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        formatted_msgs = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        formatted_msgs.extend(messages)

        payload = {
            "model": settings.GROQ_MODEL,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # --- OPENROUTER IMPLEMENTATION ---
    async def _call_openrouter(self, messages, system_prompt, temperature, max_tokens) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://super-osint-agent.internal",
            "X-Title": "Super OSINT AI Agent"
        }
        formatted_msgs = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        formatted_msgs.extend(messages)

        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # --- OPENAI IMPLEMENTATION ---
    async def _call_openai(self, messages, system_prompt, temperature, max_tokens) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        formatted_msgs = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        formatted_msgs.extend(messages)

        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # --- ANTHROPIC IMPLEMENTATION ---
    async def _call_anthropic(self, messages, system_prompt, temperature, max_tokens) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        # Anthropic messages only allow user & assistant
        anthro_msgs = []
        for m in messages:
            role = "assistant" if m.get("role") == "assistant" else "user"
            anthro_msgs.append({"role": role, "content": m.get("content", "")})

        payload = {
            "model": settings.ANTHROPIC_MODEL,
            "messages": anthro_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

llm_router = LLMRouter()
