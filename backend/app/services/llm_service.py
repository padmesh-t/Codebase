import asyncio
from app.config import settings
from app.logging_config import get_logger
from app.exceptions import LLMServiceException

logger = get_logger("llm_service")


class LLMService:
    def __init__(self):
        self._client = None

    def _get_headers(self) -> dict:
        api_key = settings.OPENROUTER_API_KEY.strip() if settings.OPENROUTER_API_KEY else ""
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://codebase-intelligence.local",
            "X-Title": "Codebase Intelligence",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @property
    def client(self):
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(
                    base_url=settings.OPENROUTER_BASE_URL,
                    headers=self._get_headers(),
                    timeout=120.0,
                )
                logger.info(f"Initialized OpenRouter client: {settings.OPENROUTER_MODEL}")
            except Exception as e:
                raise LLMServiceException(f"Failed to initialize OpenRouter client: {e}")
        return self._client

    def _ensure_headers(self):
        if self._client is not None:
            self._client.headers.update(self._get_headers())

    async def generate(self, prompt: str) -> str:
        self._ensure_headers()
        try:
            payload = {
                "model": settings.OPENROUTER_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": settings.LLM_TEMPERATURE,
                "max_tokens": settings.LLM_MAX_TOKENS,
            }
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMServiceException(f"OpenRouter generation failed: {e}")

    async def generate_with_system(self, system_prompt: str, user_prompt: str) -> str:
        self._ensure_headers()
        try:
            payload = {
                "model": settings.OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": settings.LLM_TEMPERATURE,
                "max_tokens": settings.LLM_MAX_TOKENS,
            }
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMServiceException(f"OpenRouter generation failed: {e}")

    async def check_health(self) -> dict:
        result = {"connected": False, "api_key_set": False, "error": None}
        try:
            api_key = settings.OPENROUTER_API_KEY.strip() if settings.OPENROUTER_API_KEY else ""
            result["api_key_set"] = bool(api_key)
            if not api_key:
                result["error"] = "OPENROUTER_API_KEY not set in backend/.env"
                return result
            response = await self.client.get("/models")
            result["connected"] = response.status_code == 200
            if response.status_code != 200:
                result["error"] = f"API returned status {response.status_code}"
        except Exception as e:
            result["error"] = str(e)
        return result

    async def get_available_models(self) -> list[str]:
        try:
            response = await self.client.get("/models")
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
            return []
        except Exception:
            return []


llm_service = LLMService()
