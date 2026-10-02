# Backend API contract

The FastAPI backend runs on `:8000`. All routes are under `/api`, and Next.js proxies `/api/*` to the backend, so the browser stays same-origin.
Auth is a JWT in an httpOnly cookie named `session`. Request and response bodies use the models in `backend/app/schemas/report.py`, mirrored in `frontend/lib/types.ts`.
Errors use the shape `{"detail": "message"}` with a 4xx or 5xx status.

## Auth
| Method | Path | Body → Response |
|---|---|---|
| POST | `/api/auth/signup` | `{company_name, full_name, email, password, role: "designer"\|"viewer"}` → `Me` (sets cookie). The company is matched by email domain: the first user creates it and later users join it. |
| POST | `/api/auth/login` | `{email, password}` → `Me` (sets cookie) |
| POST | `/api/auth/logout` | → `{ok: true}` |
| GET | `/api/auth/me` | → `Me = {id, email, full_name, role, company: {id, name, domain}, snowflake_connected: bool}` |

## Snowflake connection (one per company)
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/connection` | → `{connected, account, user, warehouse, role, default_table, last_tested_at}`. The token is never returned. |
| PUT | `/api/connection` | `{account, user, token, warehouse?, role?, default_table?}` → tests the connection, saves it with the token encrypted, and returns `{ok, info}`. On failure it returns 400 with `detail`. |
| POST | `/api/connection/test` | → `{ok, info?, error?}` |

## Schema introspection
| Method | Path | Response |
|---|---|---|
| GET | `/api/schema/tables` | `[{table: "DB.SCHEMA.NAME", kind: "TABLE"\|"VIEW"}]` |
| GET | `/api/schema/columns?table=` | `[{name, type: "string"\|"number"\|"date"}]` |
| GET | `/api/schema/values?table=&column=&q=` | `[value, ...]`: distinct values, up to 500, used for client and other dropdowns |

## Archetypes
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/archetypes` | → `ArchetypeSpec[]`: builtin plus this company's custom archetypes (`kind: "custom"`, `id: "custom:<id>"`) |
| POST | `/api/archetypes/custom` | `{name, description, base?: ArchetypeConfig, sql?: string, suggested_widgets?}` → `ArchetypeSpec`. SQL is validated as a single read-only SELECT. |
| DELETE | `/api/archetypes/custom/{id}` | → `{ok: true}` |

## Widgets
| Method | Path | Body → Response |
|---|---|---|
| POST | `/api/widgets/preview` | `{widget: WidgetSpec, params: ParamDef[], values: {name: value}, default_source?: DataSource}` → `WidgetData`. Errors are returned in `WidgetData.error` with status 200 so one bad widget doesn't break the canvas. |

## Report formats
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/formats` | → `ReportFormat[]` |
| POST | `/api/formats` | `ReportFormatBody` → `ReportFormat` |
| GET / PUT / DELETE | `/api/formats/{id}` | PUT takes a `ReportFormatBody` and bumps `version` |
| POST | `/api/formats/{id}/duplicate` | → `ReportFormat` |

## Runs (generated reports)
| Method | Path | Body → Response |
|---|---|---|
| POST | `/api/runs` | `{format_id, values: {param_name: value}}` → `Run`. This is synchronous: it executes every widget, fills narrative text widgets with the LLM, and renders the PDF. |
| GET | `/api/runs` | → `RunSummary[] = {id, format_id, format_name, values, status, error, created_by_name, created_at, pdf_url}` |
| GET | `/api/runs/{id}` | → `Run = RunSummary + {snapshot: {format: ReportFormatBody, values, data: {widget_id: WidgetData}, generated_at, company_name}}` |
| GET | `/api/runs/{id}/pdf` | → `application/pdf` (`?download=1` sets `Content-Disposition: attachment`) |
| GET | `/api/print/runs/{id}?token=` | → `Run`. Authenticates with a short-lived signed print token instead of the cookie, and is used by the headless Chromium PDF renderer. |

`values` formats: a client, select or string param takes a string. A `date_range` param takes `{start: "YYYY-MM-DD", end: "YYYY-MM-DD"}`. A number param takes a number.
Narrative text widgets (`options.narrative = true`) return their generated text in `WidgetData.meta.text`.

## Agent (open-source LLM through an OpenAI-compatible endpoint: Ollama or Voyager)
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/agent/health` | → `{ok, model, base_url}` |
| POST | `/api/agent/widget` | `{prompt, table?, params?: ParamDef[], existing_widgets?: WidgetSpec[]}` → `{widget: WidgetSpec, explanation}` |
| POST | `/api/agent/report` | `{prompt, table?}` → `{format: ReportFormatBody, explanation}` |
