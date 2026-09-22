# LedgerLens Deployment

## Local verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
streamlit run app.py --server.port 8504
```

Open `http://localhost:8504`.

## Streamlit Community Cloud

1. Push the complete project root to a GitHub repository.
2. Create an app with main file `app.py`.
3. In app Settings, add Secrets. Do not commit `.env`.
4. Use PostgreSQL for deployed data; do not use the local `ledgerlens.db` file for a real business.

Example secrets:

```toml
APP_ENV = "production"
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/ledgerlens"
APP_SECRET_KEY = "a-long-random-production-secret"
AUTO_CREATE_SCHEMA = "false"
AI_PROVIDER = "openrouter"
OPENROUTER_API_KEY = "your-new-key"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
```

The deployed source must include `config.py` containing `validate_runtime`. After pushing changes, use **Reboot app** or redeploy so the host does not run a stale source snapshot.

Implemented controls include Alembic migrations, employee roles, user-attributed audit records, returns/refunds, owner-controlled cancellations, and validated read-only AI queries.

## Vercel

Do not deploy this Streamlit application directly to Vercel. Vercel is designed primarily for serverless and web-framework deployments, while Streamlit requires a persistent Python process and WebSocket connection. Use Streamlit Community Cloud, Render, Railway, or a VPS for this app. Vercel could host a separate future frontend/API, but that would require changing the architecture.

## Production warning

The current project still needs Alembic migrations, production session security, employee authorization, audit logs, returns/cancellations, backup/restore testing, HTTPS, and a security review before real financial records are entered.
