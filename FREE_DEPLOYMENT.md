# Free Pilot Deployment

This is a free pilot path for demo or low-volume business testing. Free-service limits and policies can change, so confirm current limits before relying on it for important records.

## Services

- **App and HTTPS:** Streamlit Community Cloud. It provides an HTTPS app URL.
- **Database:** Supabase free PostgreSQL project. Use the PostgreSQL connection string from Supabase.
- **AI:** OpenRouter or Gemini only if the account/key has usable credits or free quota. AI is optional for sales and inventory.
- **Source:** GitHub repository. Never commit `.env` or API keys.

## 1. Create PostgreSQL

1. Create a Supabase project.
2. Open the project database connection details.
3. In **Connect**, choose **Session pooler** rather than Direct connection when your network is IPv4-only. Copy its host, port, and user exactly. Session pooler commonly uses port `6543` and a username like `postgres.PROJECT_REF`.
4. Keep the database password private.

Example format (replace every placeholder with values from Supabase):

```text
postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres
```

Session pooler format is commonly:

```text
postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:6543/postgres
```

## 2. Prepare production settings

Use these as Streamlit Cloud Secrets. Replace placeholders locally in the Secrets editor, not in GitHub:

```toml
APP_ENV = "production"
DATABASE_URL = "postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres"
APP_SECRET_KEY = "GENERATE-A-LONG-RANDOM-VALUE"
AUTO_CREATE_SCHEMA = "false"
SESSION_TIMEOUT_MINUTES = "480"
AI_PROVIDER = "openrouter"
OPENROUTER_API_KEY = ""
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
```

Leave the AI key empty if AI is not needed. The core business workflows do not require AI.

Generate a secret without printing it into source control:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Initialize the database

Before starting the production app, run the migration against the Supabase URL from a local terminal where the URL is set securely:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:PASSWORD@HOST:5432/postgres"
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item Env:DATABASE_URL
```

Or use the included password-prompt script, which does not require putting the database password in chat or source files:

```powershell
.\scripts\migrate_supabase.ps1
```

The script asks for the pooler host, pooler user, port, and password. It uses a 10-second connection timeout. Do not use `db.PROJECT_REF.supabase.co` if that direct host is unavailable on your network.

Do not use `AUTO_CREATE_SCHEMA=true` in production.

### Network alternative: Supabase SQL Editor

If your computer cannot reach the Supabase pooler ports, run the schema through Supabase itself:

1. Run `python scripts/export_schema_sql.py` locally.
2. Open Supabase **SQL Editor**.
3. Open the generated local `schema.sql` file and copy its complete contents.
4. Paste it into a new SQL query and click **Run**.
5. Confirm the tables appear under **Table Editor**.

This avoids exposing the database password and avoids local firewall/IPv6 problems. The generated file contains schema only, not secrets or application data.

## 4. Deploy the app

1. Push the complete project to a private GitHub repository.
2. Open Streamlit Community Cloud.
3. Create an app from the repository and choose `app.py`.
4. Add the Secrets shown above.
5. Deploy and wait for the health/startup check.
6. Use the HTTPS URL provided by Streamlit.

## 5. Free acceptance test

Use demo data first:

1. Create the owner account.
2. Add a product with stock.
3. Add a customer and record a partial-payment sale.
4. Confirm stock decreased and receivable exists.
5. Add a supplier and confirm a purchase.
6. Confirm stock increased and payable exists.
7. Record the remaining customer and supplier payments.
8. Test a return, refund, and cancellation.
9. Check Reports and Audit History.
10. Upload and search a CSV document.
11. Confirm employee permissions with a separate employee account.
12. Confirm the AI Analyst remains optional and read-only.

Do not enter real records until this test is successful.

## Cost and limits

This path can be free for a small pilot, but it is not an unlimited production guarantee. Free projects may sleep, have storage/compute limits, lack contractual uptime, and require manual backups. Upgrade when the business depends on continuous availability or larger data volume.

GST, invoice legality, accounting policy, data retention, and tax treatment still require review by an appropriately qualified professional in India.
