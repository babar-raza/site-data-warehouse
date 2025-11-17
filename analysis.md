1. **Repo map (folders, key files, purpose)**

* **Root**

  * `README.md` – Product overview, feature list, first-run promises (16 months ingestion, API-only mode).
  * `docker-compose.yml` – Defines core services: `warehouse` (Postgres), `api_ingestor`, `mcp`, `insights_api`, `metrics_exporter`, `scheduler`, `prometheus`.
  * `deploy*.sh/.bat`, `start-collection*.sh/.bat`, `stop*.sh/.bat`, `health-check*.sh/.bat`, `validate-setup*.sh/.bat` – Operational scripts for deployment, quick start, health checks.
  * `bootstrap.py` – Phase 0 bootstrap script; currently a mock stub for property / BigQuery discovery (body missing, only report-writing at the bottom).
  * `requirements.txt` – Python dependencies.

* **`docs/`**

  * `ARCHITECTURE.md` – System architecture, components, data flow, scheduler responsibilities, API-only notes.
  * `API_REFERENCE.md` – HTTP-level API contract for MCP and Insights APIs (documented endpoints and payloads).
  * `DEPLOYMENT.md` – Deployment instructions, service URLs, scheduler schedule (daily + weekly + “BigQuery sync”).
  * `DEVELOPMENT.md` – Dev guide, project structure, testing and coding standards.
  * `IMPROVEMENTS.md` – Change log / improvements, especially Windows / scripts / automation; describes “start-collection” workflow including BigQuery extraction.
  * `RATE_LIMITING.md` – Design of rate limiter (token bucket, exponential backoff, quotas).
  * `WINDOWS_QUICKSTART.md` – Windows-specific setup, scripts, troubleshooting.

* **`compose/`**

  * `dockerfiles/` – Currently empty (future per-service Dockerfiles).
  * `init-db/00_init.sh`, `init-db/01_schema.sql` – DB bootstrap, schema loading via SQL.
  * `prometheus/prometheus.yml` – Prometheus scrape config (targets metrics_exporter at port 9090).
  * `.placeholder` – Phase notes; mentions a future `bq_extractor.yml` that does not exist.

* **`sql/`**

  * `01_schema.sql` – Creates `gsc` schema, core fact table `gsc.fact_gsc_daily`, watermarks, and indexes.
  * `03_transforms.sql` – Defines 4 main semantic views:

    * `gsc.vw_page_health_28d`
    * `gsc.vw_query_winners_losers_28d_vs_prev`
    * `gsc.vw_directory_trends`
    * `gsc.vw_brand_nonbrand_split`
  * `.placeholder` – Notes that more SQL DDL/migrations can be added.

* **`ingestors/api/`**

  * `api_ingestor.py` – Older Phase 3 ingestor (less advanced); connects to GSC API and warehouse; largely superseded by `gsc_api_ingestor.py`.
  * `gsc_api_ingestor.py` – Main Search Analytics API ingestor:

    * Uses `EnterprisRateLimiter` for per-property rate limiting.
    * Reads config from env (including `INGEST_DAYS`).
    * Reads properties and watermarks from Postgres, calls GSC Search Analytics API, writes into `gsc.fact_gsc_daily`, updates watermarks.
  * `rate_limiter.py` – Enterprise token-bucket rate limiter with exponential backoff, per-property tracking, metrics.
  * `test_api_ingestor.py` – Ingestor-specific tests (not part of `tests/` but kept nearby).
  * `report/phase-3/` – Placeholder folder for ingestor reports.

* **`transform/`**

  * `apply_transforms.py` – Phase 4 transform runner:

    * Connects to warehouse.
    * Executes `03_transforms.sql` to create / refresh views.
    * Writes sample queries / diagnostics to `report/phase-4`.

* **`mcp/`**

  * `mcp_server.py` – Phase 5 MCP server:

    * FastAPI-based HTTP API if FastAPI is installed.
    * Tools: `get_page_health`, `get_query_trends`, `find_cannibalization`, `suggest_actions`.
    * Exposes routes like `GET /`, `GET /health`, `POST /tools/get_*`, `GET /tools/schemas`.
    * Connects to Postgres and queries the semantic views.
  * `.placeholder` – Phase notes.

* **`insights_api/`**

  * `insights_api.py` – Phase 6 optional HTTP API for dashboards:

    * FastAPI app with routes under `/api`.
    * Endpoints: `/api`, `/api/health`, `/api/summary`, `/api/timeseries`, `/api/top-pages`, `/api/top-queries`, `/api/property/{property_url}/metrics`, `/api/directory/{directory_path}/metrics`, `/api/trends`, `/api/metabase/{dataset_name}`.
    * Uses the same warehouse and views for analytics.

* **`scheduler/`**

  * `scheduler.py` – APScheduler-based orchestrator:

    * Schedules daily and weekly jobs that shell out to `gsc_api_ingestor.py` and `apply_transforms.py`.
    * Runs reconciliation and cannibalization refresh jobs.
    * Tracks metrics in-memory and logs them.
  * `metrics_exporter.py` – Flask app on port 9090:

    * `/metrics` – Prometheus metrics pulled from DB.
    * `/health` – health check.
    * `/` – simple index JSON.

* **`tests/`**

  * `test_api_ingestor.py` – Unit tests covering GSC API ingestor behavior and rate limiting.
  * `test_mcp_server.py` – Tests MCP tool calls and output shape using mocks.
  * `test_rate_limiter.py` – Token bucket and `EnterprisRateLimiter` tests.
  * `conftest.py` – Shared fixtures (mock DB, fake GSC responses, etc).

* **`secrets/`**

  * `README.md` – Explains service account JSON files and DB password handling.
  * Template files for service account credentials and DB password.

* **`htmlcov/`**

  * Coverage HTML report for earlier test runs.

---

2. **Runtime flows (orchestration, agents, jobs, websockets, UI→backend, MCP endpoints)**

* **Ingestion orchestration**

  * Daily ingestion is orchestrated by `scheduler/scheduler.py`:

    * APScheduler creates a job `daily_pipeline` scheduled with a cron trigger (02:00 UTC) which calls `run_daily_pipeline()` (around lines 323–333).
    * `run_daily_pipeline()` sequentially calls:

      * `run_api_ingestion()` → invokes `python gsc_api_ingestor.py` via `subprocess.run` (lines ~248–253).
      * `run_transforms()` → invokes `python apply_transforms.py`.
      * `check_watermarks()` → DB sanity checks.
    * Each subprocess run is wrapped with logging, timing, and metric updates.

  * **GSC API ingestion flow (`gsc_api_ingestor.py`)**:

    1. Load config from env, including rate-limiting (`REQUESTS_PER_MINUTE`, `REQUESTS_PER_DAY`), `INGEST_DAYS` with default 30 days (lines 585 etc).
    2. Initialize `EnterprisRateLimiter` from `rate_limiter.py`.
    3. Connect to Postgres using DSN from env.
    4. Fetch list of properties that require API ingestion (SQL against `gsc.ingest_watermarks`).
    5. For each property:

       * Compute `start_date` and `end_date` based on watermark and `INGEST_DAYS`.
       * In a loop:

         * Use `rate_limiter.acquire(property)` to respect quotas; sleep if necessary.
         * Call GSC Search Analytics API (if GSC client present).
         * Upsert rows into `gsc.fact_gsc_daily` using `psycopg2` and `execute_values`.
         * Update watermarks.
    6. Return ingestion summary (rows, date range) for logging.

  * **Transforms flow (`apply_transforms.py`)**:

    1. Connect to Postgres using env DSN.
    2. Execute `03_transforms.sql` to create or replace views:

       * Page health (28d).
       * Query winners/losers.
       * Directory trends.
       * Brand vs non-brand split.
    3. Write `sample_queries.json` and other diagnostic outputs into `report/phase-4`.
    4. Log created views count and timing.

* **Scheduler jobs**

  * Implemented in `scheduler/scheduler.py`:

    * Uses `BlockingScheduler` and `CronTrigger` from `apscheduler.schedulers.blocking` and `apscheduler.triggers.cron` at the top.
    * Jobs:

      * `daily_pipeline`: runs every day at 02:00 UTC (API ingestion + transforms + watermark checks).
      * `weekly_maintenance`: runs Sundays at 03:00 UTC, calling:

        * `reconcile_recent_data()` – DB stats for last 7 days.
        * `run_transforms()` – same transforms script.
        * `refresh_cannibalization_analysis()` – placeholder query for cannibalization (no materialized view created, but hooks are present).
    * Metrics:

      * `metrics` dict tracks counts, last run, last error.
      * Updated by helper `update_metrics()` each time a task runs.

* **MCP server runtime (agents / tools perspective)**

  * File: `mcp/mcp_server.py`.

  * On import:

    * Tries to import FastAPI, uvicorn, Pydantic; falls back to non-HTTP mode if missing.
    * Defines DB wrapper for Postgres with local caching.
    * Defines Pydantic models for tool inputs/outputs (page health request, cannibalization request, action suggestions, etc).

  * If FastAPI is available:

    * Creates FastAPI `app`.
    * Registers HTTP routes (around lines 278–281, 694–698):

      * `GET /` → `root()` – server info + list of tool names.
      * `GET /health` → `health_check()` – DB connectivity and cache stats.
      * `POST /tools/get_page_health` → `get_page_health(request)`.
      * `POST /tools/get_query_trends` → `get_query_trends(request)`.
      * `POST /tools/find_cannibalization` → `find_cannibalization(request)`.
      * `POST /tools/suggest_actions` → `suggest_actions(request)`.
      * `GET /tools/schemas` → `get_tool_schemas()` – returns JSON schemas for tools.

  * Tool runtimes:

    * `get_page_health` queries `gsc.vw_page_health_28d` with filters and returns pages with health scores and trends.
    * `get_query_trends` queries `gsc.vw_query_winners_losers_28d_vs_prev`.
    * `find_cannibalization` runs a query to find multiple URLs competing for same query.
    * `suggest_actions` executes a series of queries against page and query views, synthesizes recommended actions (OPTIMIZATION / RECOVERY) with severity and expected impact.

* **Insights REST API runtime**

  * File: `insights_api/insights_api.py`.
  * When FastAPI available:

    * Creates `app` and registers routes (lines 633–641, 713):

      * `GET /api` → `api_root()` – list of endpoints.
      * `GET /api/health` → `api_health()` – DB status and version.
      * `GET /api/summary` → `get_summary()` – high-level metrics over N days.
      * `GET /api/timeseries` → `get_timeseries()` – metric timeseries (daily/weekly).
      * `GET /api/top-pages` → `get_top_pages()` – top pages for a period.
      * `GET /api/top-queries` → `get_top_queries()` – top queries.
      * `GET /api/property/{property_url}/metrics` → `get_property_metrics()`.
      * `GET /api/directory/{directory_path}/metrics` → `get_directory_metrics()`.
      * `GET /api/trends` → `get_trends()` – trend summary based on views.
      * `GET /api/metabase/{dataset_name}` → `metabase_dataset()` – pre-baked datasets for BI tools.
    * All endpoints query the `gsc` schema and semantic views via shared DB helper.

* **Metrics & monitoring runtime**

  * File: `scheduler/metrics_exporter.py`.
  * Flask app:

    * `GET /metrics` → Responds in Prometheus text format with:

      * General pipeline metrics (rows processed, last run timestamps) pulled from DB tables / views.
    * `GET /health` → Simple JSON with DB status and timestamp.
    * `GET /` → JSON describing available endpoints.
  * Prometheus:

    * Configured via `compose/prometheus/prometheus.yml` to scrape `metrics_exporter:9090/metrics` every 30 seconds.

* **UI → backend**

  * This repo does not contain a web UI.
  * Expected UI integrations:

    * Dashboards (Metabase, Grafana, etc.) hit `insights_api` endpoints (`/api/summary`, `/api/top-pages`, etc.).
    * LLM / agent clients connect to MCP server via HTTP (or an MCP transport layer outside this repo) hitting endpoints like `/tools/get_page_health`.
  * Any visual / React UI for this is external to this repo.

* **WebSockets**

  * No WebSocket server or client is implemented in this codebase (no references to `websocket` or similar), so runtime is strictly HTTP + DB.

---

3. **Truth vs reality table**

*(File:line numbers are approximate based on current repo state.)*

| Claim                                                                                                                                                     | Where claimed (file:line)                                                                                                                                                                                                                                                 | Reality in code (file:line)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Risk                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **“start-collection” workflow runs a BigQuery extractor container (`bq_extractor`) and script `bq_extractor.py` as step 2**                               | `docs/IMPROVEMENTS.md:81–88` describe “Start-collection scripts” running BigQuery extraction; `docs/DEPLOYMENT.md:96` mentions weekly BigQuery sync; `start-collection.bat:26–27` calls `docker compose --profile ingestion run --rm bq_extractor python bq_extractor.py` | There is **no** `bq_extractor` service in `docker-compose.yml` (no reference to `bq_extractor` at all) and no `bq_extractor.py` file in the repo. `compose/.placeholder:1–4` implies `bq_extractor.yml` is a future phase, not present. Weekly scheduler code (`scheduler/scheduler.py:275–287`) runs reconciliation and transforms only, explicitly labeled “API-ONLY MODE” and never calls a BigQuery extractor.                                                                                                                                      | **High** – Quick-start scripts will fail on step 2; weekly BigQuery sync is not implementable as described.                                                            |
| **Initial deployment “Ingest 16 months of historical data”**                                                                                              | `README.md:16` (“16 Months Data”), `README.md:48–52` (“The initial deployment will: … 4. Ingest 16 months of historical data”)                                                                                                                                            | Default ingestion window is `INGEST_DAYS=30` in `docker-compose.yml:92`. `gsc_api_ingestor.py:378,585` uses `INGEST_DAYS` (default `'30'`) to compute `end_date = start_date + timedelta(days=int(self.config.get('INGEST_DAYS', 30)))`. There is no logic to automatically ingest 16 months by default, and deployment docs set `INGEST_DAYS=30` in `docs/DEPLOYMENT.md:195`.                                                                                                                                                                          | **High** – Users will expect a 16-month backfill from a default run, but will get ~30 days unless they manually override env vars (which docs do not explain clearly). |
| **MCP HTTP API exposes REST endpoints `GET /tools` and `POST /call-tool`**                                                                                | `docs/API_REFERENCE.md:34–40` documents `GET /tools`; `docs/API_REFERENCE.md:56–60` documents `POST /call-tool` as the primary invocation endpoint                                                                                                                        | Actual FastAPI routes in `mcp/mcp_server.py` are: `app.get("/")` and `app.get("/health")` (lines 278–279), `app.post("/tools/get_page_health")`, `app.post("/tools/get_query_trends")`, `app.post("/tools/find_cannibalization")`, `app.post("/tools/suggest_actions")`, and `app.get("/tools/schemas")` (lines 694–698). There is **no** `GET /tools` returning the list and no `POST /call-tool` endpoint.                                                                                                                                            | **Medium–High** – Any client or MCP adapter coded against `API_REFERENCE.md` will fail with 404s.                                                                      |
| **Insights REST API endpoint names and routes** – `GET /api/page-health`, `GET /api/query-trends`, `GET /api/directory-trends`, `GET /api/brand-nonbrand` | `docs/API_REFERENCE.md:195` (`GET /api/health`), 210 (`GET /api/page-health`), 243 (`GET /api/query-trends`), 273 (`GET /api/directory-trends`), 301 (`GET /api/brand-nonbrand`)                                                                                          | Actual FastAPI routes in `insights_api/insights_api.py` are: `GET /api`, `/api/health`, `/api/summary`, `/api/timeseries`, `/api/top-pages`, `/api/top-queries`, `/api/property/{property_url}/metrics`, `/api/directory/{directory_path}/metrics`, `/api/trends`, `/api/metabase/{dataset_name}` (lines 633–641, 713). There are **no** handlers for `/api/page-health`, `/api/query-trends`, `/api/directory-trends`, or `/api/brand-nonbrand`. Functionality is similar (top pages/queries, trends), but paths and response shapes differ from docs. | **High** – Dashboards or services using documented endpoints will not work.                                                                                            |
| **Weekly scheduler performs “weekly reconciliation and BigQuery sync”**                                                                                   | `docs/DEPLOYMENT.md:93–97` lists “Sunday at 03:00 UTC: Weekly reconciliation and BigQuery sync”                                                                                                                                                                           | `scheduler/scheduler.py:275–287` defines `weekly_maintenance()` as “reconciliation and cannibalization refresh (API-ONLY MODE)”; the job list includes `('Data Reconciliation', reconcile_recent_data)`, `('SQL Transforms Refresh', run_transforms)`, and `('Cannibalization Refresh', refresh_cannibalization_analysis)`. No BigQuery sync or BigQuery job is invoked.                                                                                                                                                                                | **Medium** – Operational runbooks expecting BigQuery sync will be misleading; functionally it still performs some weekly tasks, but not as described.                  |
| **Phase 0 bootstrap performs real property & BigQuery dataset discovery**                                                                                 | `bootstrap.py:2–5` docstring describes Phase 0 discovering GSC properties and BigQuery bulk export datasets                                                                                                                                                               | The implementation body is effectively missing: line `...` after imports indicates stub code; only the final report-writing block remains (`bootstrap.py:114–125`), which depends on variables (`status`, `properties`, `bq_tables`) that are never defined. It cannot actually run as-is and does not call any Google APIs.                                                                                                                                                                                                                            | **Medium** – Only used if someone manually invokes `bootstrap.py`; but if they do, it will raise errors. Docs oversell its readiness.                                  |

---

4. **Missing pieces list with minimal surfaces to implement**

1) **BigQuery extractor service + script**

   * **Gap**: `start-collection.bat/.sh` and docs assume a `bq_extractor` container and `bq_extractor.py`, but they do not exist; `docker-compose.yml` has no such service.
   * **Minimal surface to implement**:

     * Add `bq_extractor.py` under a new folder, e.g. `ingestors/bq/`:

       * Reads BigQuery config from env / secrets.
       * Uses BigQuery API to export data into Postgres (or intermediate storage) for up to 16 months.
       * Writes meaningful logs and exit codes.
     * Add `compose/bq_extractor.yml` and/or a `bq_extractor` service in `docker-compose.yml` referenced by `start-collection` scripts.
     * Decide whether API-only mode should **truly** avoid BigQuery; if yes, adjust docs and scripts instead (see point 2).

2) **Historical 16-month backfill vs current 30-day default**

   * **Gap**: README promises 16 months automatically; config and code default to 30 days via `INGEST_DAYS`.
   * **Minimal surfaces to implement** (choose one of these strategies):

     * **Option A – Implement promised behavior:**

       * For first run, detect empty `gsc.fact_gsc_daily` and temporarily set `INGEST_DAYS` to ~480 days inside `gsc_api_ingestor.py` (or via env override in `deploy-api-only` script).
       * After initial run, switch back to 30-day window for daily scheduler.
       * Update docs to explain this first-run behavior explicitly.
     * **Option B – Align docs to reality:**

       * Update `README.md` and `DEPLOYMENT.md` to state default backfill is `INGEST_DAYS` (30 by default) and show how to change it to 480 days if the user wants the full 16 months.

3) **MCP HTTP contract mismatch**

   * **Gap**: Docs describe `GET /tools`, `POST /call-tool`; implementation provides only `/` + `/health` + `/tools/get_*` + `/tools/schemas`.
   * **Minimal surfaces to implement**:

     * In `mcp/mcp_server.py`:

       * Add `GET /tools` route that returns the same tool listing structure as documented in `API_REFERENCE.md`.
       * Add `POST /call-tool` endpoint that:

         * Accepts body `{ "tool": "...", "arguments": {...} }`.
         * Dispatches to the appropriate `get_*` / `find_cannibalization` / `suggest_actions` function.
         * Returns `{ "result": ..., "metadata": ... }` as documented.
     * Optionally keep existing `/tools/get_*` routes for backwards compatibility, but make `API_REFERENCE.md` describe both or prefer the new contract.

4) **Insights REST API endpoint mapping**

   * **Gap**: API reference lists high-level endpoints (`/api/page-health`, `/api/query-trends`, `/api/directory-trends`, `/api/brand-nonbrand`) that do not exist; similar functionality lives under different paths.
   * **Minimal surfaces to implement**:

     * In `insights_api/insights_api.py`, add thin wrapper routes:

       * `GET /api/page-health` → internally call `get_top_pages` / page-health query on `vw_page_health_28d`.
       * `GET /api/query-trends` → call existing logic for `vw_query_winners_losers_28d_vs_prev` (currently exposed via `/api/trends` or `/api/top-queries`).
       * `GET /api/directory-trends` → adapt `get_directory_metrics`.
       * `GET /api/brand-nonbrand` → query `vw_brand_nonbrand_split`.
     * Ensure responses conform to the JSON examples in `API_REFERENCE.md` or update the docs to match actual semantics.

5) **Phase 0 bootstrap implementation**

   * **Gap**: `bootstrap.py` is a non-functional mock but presented as “Phase 0: Bootstrap, Credentials, and Property Discovery”.
   * **Minimal surfaces to implement**:

     * Implement a small, robust `main()`:

       * Validate secrets (e.g., check that GSC service account JSON exists).
       * Connect to Search Console API and list properties.
       * Optionally detect BigQuery export datasets if in non-API-only mode.
       * Populate the `status`, `properties`, `bq_tables` structures used at the bottom and then write the reports.
     * Alternatively, if Phase 0 is intentionally out-of-scope in API-only mode:

       * Mark `bootstrap.py` explicitly as a development-only mock in both code comments and docs and remove it from any operational runbooks.

6) **Docs alignment for scheduler behavior**

   * **Gap**: `DEPLOYMENT.md` claims weekly BigQuery sync; scheduler actually runs weekly maintenance in API-only mode only.
   * **Minimal surfaces to implement**:

     * Either:

       * Introduce a BigQuery sync task into `weekly_maintenance()` (once BigQuery extraction is implemented), or
       * Update `DEPLOYMENT.md` automated schedules section to say “Weekly reconciliation and transforms (API-only mode; BigQuery sync not applicable)” to avoid confusion.

Overall, the core ingestion, transforms, rate limiting, scheduler, MCP tools, and Insights API are present and reasonably wired. The main discrepancies are around **BigQuery-related promises**, **initial backfill depth**, and **HTTP endpoint contracts** for MCP and Insights APIs. Fixing those minimal surfaces will make the system behavior line up with the documentation and prevent most “does not work as described” issues.
