import json
from typing import Any

from openai import OpenAI

from ai.gemini_provider import SqlProposal
from config import Settings


class OpenRouterProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_api_base,
        ) if self.configured else None

    @property
    def configured(self) -> bool:
        return bool(self.settings.openrouter_api_key)

    def _complete(self, prompt: str) -> str:
        if not self.configured or self.client is None:
            raise RuntimeError("OpenRouter is not configured. Add OPENROUTER_API_KEY to .env.")
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openrouter_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        except Exception as error:
            raise RuntimeError(
                f"OpenRouter request failed for model '{self.settings.openrouter_model}'. "
                "Check OPENROUTER_MODEL, your account credits, and the API key."
            ) from error
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise RuntimeError("OpenRouter returned an empty response.")
        return content

    def propose_sql(self, question: str, schema_description: str) -> SqlProposal:
        prompt = f"""Return JSON with exactly two fields: sql and rationale.
Write one read-only SELECT query only. Use the named parameter :business_id in a WHERE condition.
Never write, modify, delete, or expose credentials. Use only this schema:
{schema_description}
Question: {question}
"""
        raw = self._complete(prompt).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return SqlProposal.model_validate(json.loads(raw))
        except Exception as error:
            raise RuntimeError("OpenRouter returned an invalid SQL proposal format.") from error

    def explain(self, question: str, rows: list[dict[str, Any]]) -> str:
        return self._complete(
            "Explain these database results briefly. Do not invent values or causes. "
            f"Question: {question}\nResults: {json.dumps(rows, default=str)}"
        )