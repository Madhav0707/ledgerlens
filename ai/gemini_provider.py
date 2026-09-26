import json
from typing import Any

from pydantic import BaseModel, Field

from config import Settings


class SqlProposal(BaseModel):
    sql: str = Field(min_length=1)
    rationale: str = ""


class GeminiProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.gemini_api_key)

    def propose_sql(self, question: str, schema_description: str) -> SqlProposal:
        if not self.configured:
            raise RuntimeError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
        from google import genai
        from google.genai import errors

        client = genai.Client(api_key=self.settings.gemini_api_key)
        prompt = f"""You are a read-only business data analyst for a small business.
Return JSON with exactly: sql and rationale.
    Write one PostgreSQL/SQLite-compatible SELECT query only that answers the user's question directly.
Use the named parameter :business_id in a WHERE condition for every query.
Never write, modify, delete, or expose credentials. Use only this schema:
{schema_description}
    Interpret common business questions as follows:
    - Current stock means products.stock_quantity, and low stock means stock_quantity <= low_stock_threshold.
    - Lifetime or "till now" means do not add a date filter; use confirmed records unless the user says otherwise.
    - Gross profit means SUM((sale_items.unit_price - sale_items.unit_cost) * sale_items.quantity) for confirmed sales, excluding rows where unit_cost is NULL.
    - Receivables mean confirmed sales total minus payments linked to those sales; payables mean confirmed purchases total minus payments linked to those purchases.
    - Always scope the business through a business_id filter on a business-owned table, including when joining child tables.
Question: {question}
"""
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
        except errors.APIError as error:
            raise RuntimeError(
                f"Gemini request failed for model '{self.settings.gemini_model}'. "
                "Check GEMINI_MODEL and the models enabled for your API key."
            ) from error
        payload: Any = json.loads(response.text)
        return SqlProposal.model_validate(payload)

    def explain(self, question: str, rows: list[dict[str, Any]]) -> str:
        if not self.configured:
            return "Gemini is not configured, so only the database result is shown."
        from google import genai
        from google.genai import errors

        client = genai.Client(api_key=self.settings.gemini_api_key)
        try:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=(
                    "Explain these database results briefly. Do not invent values or causes. "
                    f"Question: {question}\nResults: {json.dumps(rows, default=str)}"
                ),
            )
        except errors.APIError as error:
            raise RuntimeError(
                f"Gemini explanation failed for model '{self.settings.gemini_model}'."
            ) from error
        return response.text or "The query returned results, but no explanation was generated."