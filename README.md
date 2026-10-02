# Agentic Reports

Built for the MLH Hacktoberfest x Sunhacks hackathon. Agentic Reports is a report-generation platform that connects to **Snowflake**. Report designers build reusable report formats on a drag-and-drop canvas, either by placing KPIs, tables and charts themselves or by asking an open-source LLM in natural language. Anyone in the company can then generate a client-specific **PDF** from a saved format by picking runtime arguments such as client and time period.

## What it does
- **Sign up with company credentials.** Users with the same email domain share a company workspace. The company connects Snowflake once with a Programmatic Access Token, which is stored encrypted.
- **Report designer.** A 12-column canvas with 11 widget types: KPI, table, bar, stacked bar, line, area, pie, donut, scatter, text and heading. Every widget shows live Snowflake data as you edit it. You can declare runtime parameters (client, period, …) and preview the report with sample values.
- **Archetypes.** Each widget uses an archetype, a compute operation that turns raw rows into chart-ready data before display. There are 9 builtin archetypes:
  - `aggregate`
  - `time_series`
  - `top_n`
  - `share_of_total`
  - `period_over_period`
  - `kpi_summary`
  - `moving_average`
  - `pivot`
  - `distribution`

  Companies can also define **custom archetypes**: either a preset of a builtin with fixed parameters, or a read-only SQL template validated with sqlglot. All archetypes compile to parameterised Snowflake SQL, with values bound rather than concatenated into the query.
- **Agent.** Ask "show quarterly revenue by territory as a stacked bar" to add a widget, or "draft a client quarterly review" to lay out a whole report. The LLM picks an archetype and its parameters, which are validated against the schema; it never writes raw SQL. At generation time it also writes the executive-summary narrative.
- **Generate.** Pick a format, client and period to get a PDF, rendered by headless Chromium from a print page. Run history keeps every generated report.

## Stack
| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (Node 26), React 19, Tailwind v4, react-grid-layout v2, Recharts 3, zustand |
| Backend | FastAPI (Python 3.14), SQLModel/SQLite for app metadata, snowflake-connector-python, pandas, sqlglot, Playwright |
| LLM | Any OpenAI-compatible endpoint. Defaults to local **Ollama `qwen3:8b`**; a hosted endpoint such as Voyager only needs different config |
| Data | Kaggle [sample-sales-data](https://www.kaggle.com/datasets/kyanyoga/sample-sales-data) in `DEMO_CORP.SALES`: 2,823 order lines, 92 B2B clients, 2003–2005 (see `data/README.md`) |

```
frontend/  Next.js app (proxies /api/* to the backend)
backend/   FastAPI app: auth, connection, schema, archetypes engine, formats, runs, PDF, agent
data/      Kaggle → Snowflake loader
scripts/   demo hosting (Cloudflare quick tunnel), Snowflake demo role, connection check
docs/API.md  HTTP contract
```

## Run locally
```bash
make setup     # Python 3.14 venv + Chromium for PDFs + npm install (Node 26, see .nvmrc)
make data      # one-time: load the Kaggle dataset into Snowflake (needs SNOWFLAKE_* env)
make seed      # demo company "Classic Models Inc." + 2 sample report formats
make dev       # backend :8000 + frontend :3000
make test      # backend tests (live Snowflake / Ollama tests run when available)
```
Snowflake credentials come from `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_API` (PAT), `SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_ROLE`. A PAT also needs a network policy on the user (Snowflake error 390432 otherwise). Run `ollama serve` with `qwen3:8b` pulled for the AI features. Without it, they fall back gracefully.

Demo logins: `designer@classicmodels.com` / `viewer@classicmodels.com`, password `demo1234`.

## Hosting the demo (Cloudflare quick tunnel)
```bash
scripts/demo_start.sh     # seed, build, start both servers on 127.0.0.1, open tunnel, print public URL
scripts/demo_status.sh    # processes, local health, public URL reachability, sleep warnings
scripts/demo_stop.sh      # close the tunnel first, then stop the servers
```
- Nothing listens on a public interface. Only the `*.trycloudflare.com` tunnel to Next.js (:3000) is exposed, and Next proxies `/api` to FastAPI.
- `DEMO_MODE=1`: every company created at signup gets the demo Snowflake connection and the sample formats, so judges can sign up with any email and start immediately. The login page shows one-click demo accounts. The shared demo company's connection can't be changed.
- The URL changes whenever cloudflared restarts. Keep the laptop awake with the lid open.
- **Read-only Snowflake access for the public demo (recommended):** `scripts/snowflake_demo_role.py` creates the `DEMO_READER` role, which can only `SELECT` from `DEMO_CORP.SALES`. Create a PAT restricted to that role (Snowsight → profile → Settings → Authentication → *Programmatic access tokens* → Generate, role `DEMO_READER`), then add `export SNOWFLAKE_DEMO_API=<token>` to `~/.bashrc`. `demo_start.sh` then queries as `DEMO_READER` instead of your admin role.

## Demo script (≈3 min)
1. Open the public URL and click **Try as designer**. The dashboard shows two saved formats.
2. Open **Client Quarterly Review** in the designer. Every widget shows live Snowflake data. Change the preview client to show the data update.
3. Click **Ask the agent** and type *"show quarterly revenue by territory as a stacked bar chart"*. The widget appears with its archetype filled in. Open the inspector to show the archetype params and the generated SQL.
4. Drag a pie chart from the palette, set its archetype to `share_of_total` on `PRODUCT_LINE`, then save.
5. Log out and click **Try as viewer**. Go to **Generate**, pick *Client Quarterly Review*, client **Euro Shopping Channel** and period **2004**. The PDF shows an AI executive summary, $375.3K sales (+78.5% vs 2003), the trend, product mix, deal-size share and top products.
