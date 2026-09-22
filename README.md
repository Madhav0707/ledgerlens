# LedgerLens

LedgerLens is a Streamlit finance and operations copilot for small businesses. Phase 1 establishes a database-backed foundation for Mehta Electronics in Jaipur.

## Phase 1 scope

- SQLAlchemy models with business-owned records and foreign-key relationships
- SQLite by default for a simple local start; PostgreSQL is the target database
- Streamlit dashboard shell with honest empty states
- First-owner setup and bcrypt password hashing for local development
- Gemini configuration via `GEMINI_API_KEY` and `GEMINI_MODEL` (no API call in Phase 1)
- Product creation, business-scoped SKU validation, stock adjustments, and movement history
- Atomic sales, partial payments, customer receivables, and duplicate sale-reference protection
- Supplier records, atomic purchases, weighted inventory cost updates, supplier payments, and payables
- Date-filtered reports for revenue, collections, receivables, payables, inventory value, gross profit, and CSV export
- Gemini AI analyst with read-only SQL validation, business scoping, row limits, and provenance labels
- Local PDF/CSV document upload, text extraction, chunking, and business-scoped search
- Ranked document retrieval with source metadata and prompt-injection-resistant context formatting
- Employee roles, user-attributed audit logs, returns/refunds, and owner-controlled sale cancellations
- Environment-based configuration
- Initial database smoke test

Sales workflows, customer balances, supplier purchases, documents, reports, and Gemini analysis are intentionally introduced in later phases. No financial values are hardcoded into the application.

## Setup on Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Run the foundation test:

```powershell
pytest -q
```

For PostgreSQL, set `DATABASE_URL` in `.env` to a `postgresql+psycopg://...` URL before starting the app. A PostgreSQL database and user must already exist. For Gemini or OpenRouter, configure the selected provider key; AI is optional for the local business workflows.

## Local PostgreSQL with Docker

```powershell
docker compose up --build
```

Then open `http://localhost:8501`. The included Compose file is a development convenience, not a production deployment: change every password and secret before sharing it, add migrations, and configure backups.

For a production database, run the migration before starting the app:

```powershell
alembic upgrade head
```

If the local network cannot reach Supabase PostgreSQL, generate `schema.sql` with `python scripts/export_schema_sql.py` and run it in the Supabase SQL Editor instead. This is a browser-based alternative to the Alembic connection.

## Initial schema

Every business-owned table stores `business_id` directly so authorization checks do not depend only on joins. The relationships are:

- `businesses` owns users through `business_memberships`, and owns products, customers, suppliers, sales, purchases, and inventory movements.
- `sales` contain `sale_items`; `payments` belong to a business and may be linked to a sale.
- `purchases` contain `purchase_items`; purchase confirmation creates inventory movements.
- `products` optionally reference categories and suppliers. SKU is unique within a business.
- Historical financial records use restrictive relationships and are not silently deleted.

The schema currently includes returns, refunds, documents, document chunks, audit logs, and workflow-ready business ownership fields. Additional workflow proposals and vector embeddings remain optional future extensions.

## Required and optional services

Required for Phase 1: Python 3.11+, the Python packages in `requirements.txt`, and a writable local directory. PostgreSQL is required for a production-like deployment but not for the local smoke test.

Optional later: an LLM provider API key, pgvector-enabled PostgreSQL for RAG, Docker Desktop, and an OCR/PDF extraction service. None of these credentials are needed to run Phase 1.

## Development boundaries

This is not yet production-ready or tax-compliant invoicing. Before using real financial records, complete PostgreSQL backup and restore testing, HTTPS deployment, production session hardening, login rate limiting, a GST/tax review, a read-only database role for AI queries, secret rotation, and a formal security review. Run acceptance tests with demo records in the deployed environment first.
