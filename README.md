# Finance Data Processing and Access Control Backend

**Assessment submission:** a **REST** JSON API (Django + Django REST Framework) for a finance dashboard: **users and roles**, **financial records**, **aggregated dashboard data**, **server-side access control**, **validation and consistent errors**, and **SQLite persistence**. Roles are **viewer**, **analyst**, and **admin**. Authentication uses **JWT**; **inactive** users get **401** even when the token is syntactically valid.

The repo includes an **automated test suite** (`accounts/tests/`, `finance/tests/`)—API integration tests with **`APIClient`**, focused **unit tests** for dashboard helpers and permissions, and checks for **error JSON shape**, **throttling**, and **RBAC**. Run them with **`python manage.py test accounts finance`** (see [**Tests**](#readme-section-tests) under [Quick start](#readme-section-quick-start)).

This README is the **single handoff document**: setup, how the work maps to the brief, [**Assumptions**](#readme-section-assumptions), [**Design decisions**](#readme-section-design-decisions), [API reference](#readme-section-api-reference), [Error responses](#readme-section-error-responses), and pointers for reviewers. It is intentionally **not** production-hardened; the goal is a clear, reviewable backend.

---

<span id="readme-section-assignment-map"></span>

## How this maps to the assessment brief

The following table in this [section](#readme-section-assignment-map) maps each **core requirement** in the assignment to concrete behavior in this repo.

### Core requirements (brief “Core Requirements”)

| # | Brief asks for | How it is implemented |
|---|----------------|------------------------|
| **1** | User/role management, active/inactive, role restrictions | Custom `accounts.User` (`role`: viewer/analyst/admin; `status`: active/inactive). Admin-only **`/api/users/`** for CRUD. `is_active` stays aligned with `status`. |
| **2** | Financial entries (amount, type, category, date, notes), CRUD, filtering | **`/api/records/`** with `FinancialRecord`; fields match the brief. **django-filter** on list: `date_from`, `date_to`, `category`, `type`. **Soft delete** on standard `DELETE`; optional **hard delete** on `.../permanent/`. |
| **3** | Dashboard summaries: totals, by category, recent activity, trends | **`GET /api/dashboard/summary/`** returns `totals`, `by_category`, `recent_activity`, `monthly_trend` (UTC calendar-month buckets; see [Dashboard analytics rules](#readme-section-dashboard-analytics)). Logic lives in **`finance/services.py`** to keep the view thin. Monthly trend demonstrates aggregated time-series design. |
| **4** | Access control by role | DRF **permission classes** (`IsAdmin`, `IsAnalystOrAdmin`, `CanAccessDashboard`) plus `get_permissions` on the records viewset. Enforced on the server for every request (see [Roles and permissions](#readme-section-roles-permissions)). |
| **5** | Validation, useful errors, appropriate status codes | Serializer validation; custom [`config.exceptions.custom_exception_handler`](config/exceptions.py) normalizes JSON to **`detail`** + **`code`** (and **`fields`** on **400**). **401 / 403 / 404 / 429** — see [Error responses](#readme-section-error-responses). |
| **6** | Data persistence | **SQLite** (`db.sqlite3` at project root), Django ORM + migrations. Suitable for local/dev and assessment; easy to swap for PostgreSQL later. |

### Optional enhancements (brief “Optional Enhancements”)

| Enhancement | Status |
|-------------|--------|
| Authentication (tokens) | **Yes** — JWT via **djangorestframework-simplejwt**; obtain + refresh in [Obtain JWT](#readme-section-obtain-jwt). |
| Pagination | **Yes** — page size **20** on list endpoints. |
| Search | **Partial** — list **filtering** by date range, category, and type (not full-text search on notes). |
| Soft delete | **Yes** — `deleted_at`; default manager hides soft-deleted rows; detail returns **404**. |
| Rate limiting | **Yes** — DRF throttling (global + scoped JWT limits); see [Implementation notes](#readme-section-implementation-notes). |
| Unit / integration tests | **Yes** — `python manage.py test accounts finance` (RBAC, dashboard, filters, errors, throttling, etc.); details under [Tests](#readme-section-tests). |

<span id="readme-section-assumptions"></span>

### Assumptions (documented, reasonable defaults)

These are explicit product choices where the brief left room to interpret.

| Topic | Assumption |
|-------|------------|
| **Tenancy** | Single organization: no `tenant_id` or multi-customer isolation. |
| **Currency** | One currency: `amount` is a **Decimal** (no FX, no multi-currency). |
| **Time** | **UTC** in the database; API datetimes are ISO 8601 (with `Z` or offset where documented). |
| **Record scope** | Financial records are **global** to the app (not a separate ledger per viewer). **`created_by`** records which user created the row for audit. |
| **Roles** | Three roles with the behavior in [Roles and permissions](#readme-section-roles-permissions) (viewer cannot list raw records; analyst read-only on records; admin mutates records and users). |
| **Inactive users** | **401 Unauthorized** (not 403): the assignment asks for clear auth semantics — an inactive account is treated as **not allowed to use the API** with that JWT. |

<span id="readme-section-dashboard-analytics"></span>

### Dashboard analytics rules (summary)

All dashboard aggregates use only **non–soft-deleted** rows (`deleted_at` null). Optional query params **`date_from`** / **`date_to`** (`YYYY-MM-DD`) filter **`occurred_at`** by **calendar day in UTC**, inclusive of both days, and apply to **every** section of the response (totals, by category, recent activity, and the data feeding monthly buckets).

- **Totals:** sum of `amount` for `type=income`, for `type=expense`, and **net** = income − expense.
- **By category:** group by `(category, type)`, sum amounts, sort by **category** then **type**.
- **Recent activity:** order by **`occurred_at` desc**, then **`id` desc**; limit from **`recent_limit`** (default 10, max 50).
- **Monthly trend:** bucket by **UTC calendar month**; each bucket includes income, expense, and net. If neither date param is set, the range defaults to the **last six UTC months including the current month**; if dates are set, the month range follows documented rules in [`finance/services.py`](finance/services.py) (function `_trend_month_bounds`).

<span id="readme-section-design-decisions"></span>

### Design decisions (why built this way)

| Decision | Rationale |
|----------|-----------|
| **Django + DRF** | Fits relational data, migrations, admin, and a conventional REST surface; keeps ORM, auth, and validation in well-understood layers. |
| **Email as login** | `USERNAME_FIELD = email`, `username = None` — avoids a redundant username and matches “manage users” with a natural identifier. |
| **`status` + `is_active` sync** | Inactive users must not access the API; syncing `is_active` with `status` keeps Django admin and JWT checks aligned. |
| **`ActiveUserJWTAuthentication`** | Single enforcement point: after JWT validation, reject **`status != active`** with **401** and a stable **`code`** (`user_inactive`). |
| **Permission classes per role** | DRF **`BasePermission`** subclasses (`IsAdmin`, `IsAnalystOrAdmin`, `CanAccessDashboard`) instead of ad-hoc checks in views — easy to read and test. |
| **Soft delete + optional hard delete** | **DELETE** `/api/records/{id}/` sets **`deleted_at`** (audit-friendly). **DELETE** `/api/records/{id}/permanent/` removes the row (admin-only) so evaluators can see both patterns. |
| **Dashboard in `finance/services.py`** | Aggregations stay **testable** and keep the HTTP view thin (assignment emphasizes business logic and structure). |
| **Unified exception handler** | Normalizes **400/401/403/404/429** bodies to **`detail` + `code`** (and **`fields`** on validation errors) so clients and tests see one contract. |
| **django-filter on records list** | Declarative filters for **date_from**, **date_to**, **category**, **type** — matches “filtering” requirement without bespoke query parsing in the view. |
| **SQLite** | Meets “persistence” with zero external services; swap **`DATABASES`** in settings for PostgreSQL when needed. |
| **Rate limiting** | DRF throttling + **LocMem** cache: demonstrates **429** handling; documented limitation for multi-worker deployments. |
| **Automated tests** | **`accounts/tests/`** and **`finance/tests/`** use Django **`TestCase`** / **`SimpleTestCase`** and DRF **`APIClient`** so behavior stays verifiable without a manual checklist; see [Tests](#readme-section-tests). |

### Tradeoffs and limitations (honest scope)

- **Not production-ready:** debug-oriented settings, no deployment hardening narrative (TLS, secrets rotation, WAF, etc.).
- **Throttling:** **LocMem** is per process — use a shared cache (e.g. Redis) for multiple workers.
- **Trends:** **Monthly** only; no weekly series in the API.
- **Search:** filtering by **category** / **type** / **dates**, not full-text search across **notes**.

### Mapping to evaluation criteria (for reviewers)

| Criterion | Where to look |
|-----------|----------------|
| **Backend design / separation of concerns** | `accounts/` vs `finance/` vs `config/`; dashboard logic in **`finance/services.py`**; permissions in **`accounts/permissions.py`**. |
| **Logical thinking / business rules** | [Roles and permissions](#readme-section-roles-permissions) matrix; soft vs permanent delete; [Dashboard analytics rules](#readme-section-dashboard-analytics); inactive user → **401**. |
| **Functionality** | Run **`python manage.py test accounts finance`**; exercise [Example `curl` flows](#readme-section-curl). |
| **Code quality** | Small, named permissions; viewsets with `get_permissions` where actions differ; serializers for validation. |
| **Data modeling** | `accounts/models.py` (`User`), `finance/models.py` (`FinancialRecord`, managers for soft delete). |
| **Validation / reliability** | Serializers + [`config/exceptions.py`](config/exceptions.py); [Tests](#readme-section-tests) cover RBAC, 404 shape, dashboard math, throttling, query validation. |
| **Documentation** | This file (setup, [Assumptions](#readme-section-assumptions), [Design decisions](#readme-section-design-decisions), [API reference](#readme-section-api-reference), [Error responses](#readme-section-error-responses), [Tests](#readme-section-tests)). |
| **Additional thoughtfulness** | JWT + inactive handling, unified errors, rate limits, soft delete + audit field **`created_by`**, tests. |

### Quick file pointers

- **RBAC:** [`accounts/permissions.py`](accounts/permissions.py), [`finance/views.py`](finance/views.py), [`accounts/views.py`](accounts/views.py)
- **Aggregations:** [`finance/services.py`](finance/services.py) (`build_dashboard_summary`)
- **Errors:** [`config/exceptions.py`](config/exceptions.py) — see also [Error responses](#readme-section-error-responses)
- **Tests:** [`accounts/tests/`](accounts/tests/), [`finance/tests/`](finance/tests/) — see [Tests](#readme-section-tests)

---

## Requirements

- Python **3.11+** (3.12 recommended)
- Dependencies: [requirements.txt](requirements.txt) (Django ~5.2, DRF, Simple JWT, django-filter, python-dotenv)

---

<span id="readme-section-quick-start"></span>

## Quick start

### 1. Virtual environment and install

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

Copy the example file and edit values:

```bash
cp .env.example .env
```

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret; **required** for any real use. Use a long random string. |
| `DEBUG` | `True` / `False` (default `True` if unset in code paths that default). |
| `ALLOWED_HOSTS` | Comma-separated hostnames. In `DEBUG`, `localhost`, `127.0.0.1`, and `testserver` are added automatically if missing. |

If `SECRET_KEY` is missing, Django will fail at startup when it tries to use it.

### 3. Database and superuser

The app uses **SQLite** at the project root:

| Item | Path |
|------|------|
| SQLite file | `<project_root>/db.sqlite3` |

```bash
python manage.py migrate
python manage.py createsuperuser
```

`createsuperuser` prompts for **email** (not username), **password**, and **name** (required display field), plus optional flags. The custom user model uses **email** as `USERNAME_FIELD`.

### 4. Run the server

```bash
python manage.py runserver
```

API base URL (default): `http://127.0.0.1:8000/api/`

Django admin: `http://127.0.0.1:8000/admin/`

<span id="readme-section-tests"></span>

### 5. Tests

```bash
python manage.py test accounts finance
```

The suite is **57** automated test methods across the two apps (count may change if you add cases). It is not exhaustive end-to-end coverage, but it **does** lock in the behaviors the brief cares about:

| Area | Examples (modules) |
|------|---------------------|
| **Role-based API access** | Users API and records/dashboard routes — viewer vs analyst vs admin (`test_api_role_access_control.py` in both apps). |
| **Auth / errors** | **401** / **403** JSON shape, inactive JWT user, unified **400** validation payload (`test_exception_handling.py`, `test_unified_errors.py`, `test_exception_contract.py`). |
| **Permission classes** | Direct unit tests on `IsAdmin`, `IsAnalystOrAdmin`, `CanAccessDashboard` (`test_permission_classes.py`). |
| **Financial records** | List **filters** (`test_record_filters.py`), **404** for missing/soft-deleted detail (`test_record_not_found.py`), **soft vs permanent delete** (`test_record_delete.py`). |
| **Dashboard** | Aggregations and date filtering via **`build_dashboard_summary`**, plus API validation for bad dashboard query params (`test_dashboard_summary.py`, `test_services.py`). |
| **Rate limiting** | **429** + `throttled` on JWT obtain when limits are tightened in the test (`test_throttling.py`). |

Tests use an **in-memory SQLite** database created by Django’s test runner; no separate DB setup is required.

---

## Project layout

| Path | Role |
|------|------|
| `config/` | Django settings, root `urls.py`, unified **exception handler** (`config/exceptions.py`). |
| `accounts/` | `User` model (email login, `name`, `role`, `status`), JWT auth subclass, permissions, user API. |
| `finance/` | `FinancialRecord` model (soft delete), filters, serializers, views, **dashboard aggregation** (`finance/services.py`). |

<span id="readme-section-implementation-notes"></span>

### Implementation notes

- **Authentication:** `ActiveUserJWTAuthentication` — after JWT validation, users with `status != active` are rejected with **401** and code `user_inactive`.
- **Authorization:** Custom permissions (`IsAdmin`, `IsAnalystOrAdmin`, `CanAccessDashboard`) check `user.role`.
- **Soft delete:** Default manager on `FinancialRecord` hides rows with `deleted_at` set. List/detail/update use that manager, so missing or soft-deleted rows return **404**.
- **Hard delete:** `DELETE /api/records/{id}/permanent/` removes the row from the database (admin only); works for active or already soft-deleted rows.
- **Dashboard:** Aggregations run in [`finance/services.py`](finance/services.py) (totals, by category, recent activity, monthly trend). Query params `date_from` / `date_to` filter all sections by `occurred_at` calendar day (UTC, inclusive). HTTP surface: [Dashboard summary](#readme-section-dashboard-summary).
- **Pagination:** List endpoints use **page size 20** (`PageNumberPagination`); responses include `count`, `next`, `previous`, `results`.
- **OpenAPI:** `drf-spectacular` is listed in `requirements.txt` but **not** wired in `urls.py`; there is no live schema URL unless you add it.
- **Rate limiting:** DRF throttling uses Django’s **default cache** (`LocMemCache`; [`CACHES` in `config/settings.py`](config/settings.py)). **Anonymous** and **authenticated** traffic each have global limits; **JWT** endpoints use **scoped** limits (`jwt_obtain`, `jwt_refresh`) via `accounts/jwt_throttled_views.py`. Exact strings are in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` (relaxed automatically during `manage.py test` so the suite does not hit limits). Excess requests return **429** with `code: "throttled"` (same `detail`/`code` envelope as other API errors). For multiple app processes, replace `LocMemCache` with **Redis** (or similar) so counters are shared.

---

<span id="readme-section-roles-permissions"></span>

## Roles and permissions

| Action | Viewer | Analyst | Admin |
|--------|:------:|:-------:|:-----:|
| `POST /api/auth/token/`, `POST /api/auth/token/refresh/` | Yes | Yes | Yes |
| `GET /api/dashboard/summary/` | Yes | Yes | Yes |
| `GET /api/records/`, `GET /api/records/{id}/` | No | Yes | Yes |
| `POST`, `PATCH`, `DELETE` on `/api/records/...` | No | No | Yes |
| `DELETE /api/records/{id}/permanent/` | No | No | Yes |
| `/api/users/` (all methods) | No | No | Yes |

**User delete:** Admins cannot delete **their own** account via the API ( **403** ).

---

<span id="readme-section-api-reference"></span>

## API reference

Send JSON with `Content-Type: application/json` where a body is used. Authenticated requests:

```http
Authorization: Bearer <access_token>
```

<span id="readme-section-obtain-jwt"></span>

### Obtain JWT

**`POST /api/auth/token/`**

Request body (email-based user model):

```json
{
  "email": "you@example.com",
  "password": "your-password"
}
```

Success **200** (shape from Simple JWT), typically:

```json
{
  "refresh": "<refresh_token>",
  "access": "<access_token>"
}
```

**`POST /api/auth/token/refresh/`**

```json
{
  "refresh": "<refresh_token>"
}
```

Success **200** includes a new `access` token.

Token lifetimes ([`config/settings.py`](config/settings.py) **SIMPLE_JWT**): access **60 minutes**, refresh **7 days** (defaults in repo).

---

### Users (admin only)

Base: `/api/users/`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/` | Paginated list. |
| `POST` | `/api/users/` | Create user (`name`, `email`, `password`, `role`, `status`). |
| `GET` | `/api/users/{id}/` | Detail. |
| `PATCH` | `/api/users/{id}/` | Partial update; optional `password` (write-only). |
| `DELETE` | `/api/users/{id}/` | Hard delete; **403** if `id` is the current user. |

**Example user (response fields):** `id`, `email`, `name`, `role`, `status`, `created_at`, `updated_at` (no password).

---

### Financial records

Base: `/api/records/`

| Method | Path | Who | Description |
|--------|------|-----|-------------|
| `GET` | `/api/records/` | Analyst, Admin | Paginated list. |
| `POST` | `/api/records/` | Admin | Create. |
| `GET` | `/api/records/{id}/` | Analyst, Admin | Detail (**404** if missing or soft-deleted). |
| `PATCH` | `/api/records/{id}/` | Admin | Partial update. |
| `DELETE` | `/api/records/{id}/` | Admin | **Soft delete** (`deleted_at` set). **404** if already soft-deleted (not in queryset). |
| `DELETE` | `/api/records/{id}/permanent/` | Admin | **Hard delete** from DB (active or soft-deleted). |

**List query parameters** (optional):

| Param | Description |
|-------|-------------|
| `date_from` | `YYYY-MM-DD` — `occurred_at` date ≥ this day (inclusive). |
| `date_to` | `YYYY-MM-DD` — `occurred_at` date ≤ this day (inclusive). |
| `category` | Exact match. |
| `type` | `income` or `expense`. |
| `page` | Page number for pagination. |

**Create / update body (typical):**

```json
{
  "amount": "150.00",
  "type": "expense",
  "category": "travel",
  "occurred_at": "2026-03-15T10:30:00Z",
  "notes": "Conference"
}
```

- `amount` — decimal string, **≥ 0**.
- `type` — `income` or `expense`.
- `created_by` is **read-only**; set automatically on create from the authenticated user.

**Example record (response):** `id`, `amount`, `type`, `category`, `occurred_at`, `notes`, `created_by`, `created_at`, `updated_at`.

---

<span id="readme-section-dashboard-summary"></span>

### Dashboard summary

**`GET /api/dashboard/summary/`** — Viewer, Analyst, Admin.

Optional query parameters:

| Param | Description |
|-------|-------------|
| `date_from` | `YYYY-MM-DD` — filter all aggregates to this `occurred_at` calendar day onward (inclusive). |
| `date_to` | `YYYY-MM-DD` — inclusive end calendar day. |
| `recent_limit` | Recent activity row count; default **10**, maximum **50**. |

Success **200** body (amounts as strings with two decimals):

```json
{
  "totals": {
    "income": "5000.00",
    "expense": "3200.00",
    "net": "1800.00"
  },
  "by_category": [
    { "category": "salary", "type": "income", "total": "5000.00" }
  ],
  "recent_activity": [
    {
      "id": 10,
      "amount": "120.00",
      "type": "expense",
      "category": "meals",
      "occurred_at": "2026-04-02T09:00:00Z",
      "notes": null
    }
  ],
  "monthly_trend": [
    {
      "period_start": "2026-01-01T00:00:00Z",
      "income": "1000.00",
      "expense": "400.00",
      "net": "600.00"
    }
  ]
}
```


Invalid `date_from` / `date_to` → **400** with `validation_error` and `fields` (see [Error responses](#readme-section-error-responses)).

---

<span id="readme-section-error-responses"></span>

## Error responses

The app uses a **custom DRF exception handler** (`config.exceptions.custom_exception_handler`). Responses are normalized to JSON with at least **`detail`** (string) and **`code`** (string).

| HTTP | Typical `code` | Notes |
|------|----------------|--------|
| **400** | `validation_error` | Serializer or query validation; may include **`fields`**: `{ "field_name": ["message", ...] }`. |
| **401** | `not_authenticated`, `token_not_valid`, `user_inactive`, … | Missing/invalid JWT or inactive user. |
| **403** | `permission_denied` | Authenticated but not allowed for the action. |
| **404** | `not_found` | Missing resource or soft-deleted record where hidden. |
| **429** | `throttled` | Rate limit exceeded (see [Implementation notes](#readme-section-implementation-notes) for scopes and defaults). |

Example **401**:

```json
{
  "detail": "User is inactive.",
  "code": "user_inactive"
}
```

Example **400** (validation):

```json
{
  "detail": "Enter a valid date (YYYY-MM-DD).",
  "code": "validation_error",
  "fields": {
    "date_from": ["Enter a valid date (YYYY-MM-DD)."]
  }
}
```

The full contract is also described in the module docstring of [`config/exceptions.py`](config/exceptions.py).

**HTTP semantics (auth vs authorization):** missing or invalid token → **401**. Valid token but **inactive** user → **401** (`user_inactive`). Valid active user but wrong role → **403** (`permission_denied`).

---

<span id="readme-section-curl"></span>

## Example `curl` flows

Replace host, email, password, and tokens as needed.

**1. Login**

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"your-password\"}"
```

**2. List records (analyst or admin)**

```bash
curl -s http://127.0.0.1:8000/api/records/ \
  -H "Authorization: Bearer ACCESS_TOKEN_HERE"
```

**3. Create record (admin)**

```bash
curl -s -X POST http://127.0.0.1:8000/api/records/ \
  -H "Authorization: Bearer ACCESS_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d "{\"amount\":\"25.50\",\"type\":\"expense\",\"category\":\"office\",\"occurred_at\":\"2026-04-01T12:00:00Z\"}"
```

**4. Dashboard (any role with dashboard access)**

```bash
curl -s "http://127.0.0.1:8000/api/dashboard/summary/?date_from=2026-01-01&date_to=2026-12-31" \
  -H "Authorization: Bearer ACCESS_TOKEN_HERE"
```

**5. Refresh access token**

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\":\"REFRESH_TOKEN_HERE\"}"
```

---
