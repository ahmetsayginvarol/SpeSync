# SpeSync — Project Overview & Advanced Version Plan

## What Is SpeSync?

SpeSync is a **cruise ship restaurant pre-order management system**. It lets restaurant managers take dining pre-orders from guests, routes those orders to the correct galley section (Hot/Cold/Pastry), and gives kitchen staff a real-time view of what they need to prepare — all before guests arrive at the restaurant.

The system runs across three user roles: restaurant managers enter orders, galley (kitchen) staff view and action them, and admins manage the configuration (voyages, venues, users, guest manifests).

---

## Current Architecture

### Apps (all Python desktop, Windows-only)

| File | Role | Size |
|---|---|---|
| `restaurant_app.py` | Restaurant manager order entry | 250 KB |
| `admin_app.py` | System administration | 147 KB |
| `galley_app.py` | Kitchen staff order viewer | 76 KB |
| `dert.py` | Experimental/dev copy of restaurant_app | 124 KB |

Each app is a **single monolithic Python file** packaged as a Windows `.exe` with PyInstaller.

### Tech Stack

- **UI:** Python + tkinter + ttkbootstrap (Windows-only single-instance via WinDLL mutex)
- **Database:** SQLite (default) or MySQL (configurable via `db_config.json`)
- **Auth:** bcrypt password hashing, role-based (admin / restaurant / galley)
- **PDF Export:** ReportLab
- **Packaging:** PyInstaller (`.spec` files for Admin, Restaurant/Suite, Galley)

### Database Schema

All three apps share one database (`orders.db`):

```
users           id, username, password_hash, role
venues          id, name, breakfast_available, lunch_available, dinner_available
allergies       id, name
guests          id, cabin_number, first_name, last_name, voyage_id
preorders       id, manager, cabin_number, guest_name, dish, pax,
                allergy_notes, special_requests, service_time_slot,
                galley_section, standing_order, venue_id, service_date,
                chef_flag, chef_remark, voyage_id
voyages         id, code, start_date, end_date
app_config      key, value  (current_voyage_id, timezone, cutoff_hour, …)
import_mappings column mapping for guest CSV imports
```

### Key Features (Current)

**Restaurant App**
- Cabin autocomplete with guest occupant selection
- Multi-dish order composition per occupant
- Allergy multi-select, galley section assignment, time slot selection
- Standing orders (auto-repeat daily across a voyage)
- Unsaved order tracking with visual indicators
- PDF export of daily orders (landscape, formatted table)
- Guest CSV import with column mapping

**Admin App**
- User management (CRUD with roles)
- Voyage lifecycle (create, switch, archive)
- Venue configuration (meal period availability)
- Allergy list management
- Database backup/restore
- Audit log viewer
- Excel/CSV guest manifest import
- SQLite ↔ MySQL connection switching

**Galley App**
- Filter orders by venue / date / time slot
- Chef remarks and flags on individual orders
- PDF export (per-venue or all-venues for a date)
- Inline order editing

---

## Current Limitations

1. **Monolithic files** — 250KB single-file apps are hard to test, navigate, and maintain.
2. **Windows-only** — WinDLL mutex and `os.startfile` make cross-platform deployment impossible.
3. **No real-time sync** — all multi-user coordination is implicit via shared DB; no push notifications or live updates.
4. **No test coverage** — zero unit or integration tests.
5. **No REST API** — no way to integrate with other ship systems (POS, PMS, cabin displays).
6. **Dated UI** — tkinter is functional but limits UX: no search-as-you-type, no drag-and-drop, no mobile access.
7. **Secrets in repo** — `db_config.json` and `orders.db` are committed; credentials are plaintext.
8. **No CI/CD** — no automated builds, linting, or testing pipeline.
9. **Dead code** — `dert.py` is an obsolete experimental copy; `SpeciSync *.spec` files are renamed duplicates.

---

## Advanced Version — Vision

The advanced version keeps the core domain logic (orders, venues, guests, galleys, voyages) but rebuilds on a modern, cross-platform, multi-user architecture.

### Target Architecture

```
┌─────────────────────┐    WebSocket / REST    ┌──────────────────────────┐
│  Web Frontend        │ ◄──────────────────► │  FastAPI Backend          │
│  (React / Next.js)   │                       │  - REST API              │
│                      │                       │  - WebSocket hub         │
│  Screens:            │                       │  - Auth (JWT + bcrypt)   │
│  - Restaurant order  │                       │  - Business logic        │
│  - Galley board      │                       └──────────┬───────────────┘
│  - Admin panel       │                                  │
│  - Reports           │                       ┌──────────▼───────────────┐
└─────────────────────┘                       │  PostgreSQL               │
                                               │  (replaces SQLite/MySQL)  │
                                               └───────────────────────────┘
```

### Planned Modules

#### Backend (`/backend`)
```
backend/
  app/
    api/
      routes/
        orders.py       # CRUD + standing order logic
        venues.py
        guests.py
        voyages.py
        users.py
        reports.py      # PDF generation endpoint
    core/
      auth.py           # JWT + bcrypt
      config.py         # env-based settings (no committed secrets)
      database.py       # SQLAlchemy + async engine
    models/             # SQLAlchemy ORM models
    schemas/            # Pydantic request/response schemas
    services/           # Business logic (standing orders, cutoff, sync)
    websocket/          # Real-time order board push
  tests/
    unit/
    integration/
  Dockerfile
  requirements.txt
```

#### Frontend (`/frontend`)
```
frontend/
  src/
    pages/
      restaurant/       # Order entry flow
      galley/           # Kitchen order board (auto-refreshing)
      admin/            # User/venue/voyage management
      reports/          # PDF download, order history
    components/
      OrderForm/
      OrderGrid/
      AllergyBadge/
      StandingOrderToggle/
    hooks/
      useOrders.ts      # WebSocket-backed live data
      useAuth.ts
    lib/
      api.ts            # Typed API client (auto-generated from OpenAPI)
  Dockerfile
```

#### DevOps (`/infra`)
```
docker-compose.yml      # Postgres + backend + frontend + nginx
.github/workflows/
  ci.yml                # lint, typecheck, test on PR
  build.yml             # Docker image build on merge
.env.example            # template (no real secrets committed)
```

### Feature Upgrades

| Area | Current | Advanced |
|---|---|---|
| Real-time sync | None (shared DB polling) | WebSocket push to all connected clients |
| Mobile / tablet | No | Responsive web UI (galley boards on kitchen tablets) |
| Auth | bcrypt in DB | JWT + refresh tokens, session management |
| Reporting | Local PDF via ReportLab | Server-side PDF API endpoint, downloadable anywhere |
| Guest import | CSV/Excel via file dialog | Drag-and-drop upload via web UI, background processing |
| Standing orders | App-side copy logic | Server-side scheduled job (APScheduler / Celery) |
| Audit log | Admin app viewer | Centralized, queryable, exportable |
| Multi-venue | DB flag per order | Venue-scoped WebSocket channels |
| Printing | `os.startfile` PDF | Print-ready web view + direct thermal printer support |
| Deployment | Manual .exe distribution | Docker Compose, one-command setup |
| Testing | None | pytest (backend), Vitest + Playwright (frontend) |

### Migration Strategy

1. **Phase 1 — Backend API:** Build FastAPI app mirroring the existing SQLite schema exactly. Run in parallel with existing apps. No UI changes yet.
2. **Phase 2 — Web UI (Admin):** Replace `admin_app.py` with web admin panel. Lowest risk — infrequent use.
3. **Phase 3 — Web UI (Galley):** Replace `galley_app.py`. Kitchen tablets get a live-updating board.
4. **Phase 4 — Web UI (Restaurant):** Replace `restaurant_app.py`. Most complex; needs careful parity with standing orders, field locking, and offline fallback.
5. **Phase 5 — Cleanup:** Remove `dert.py`, old `.spec` files, committed DB, and `db_config.json`. Harden secrets management.

---

## Development Branch

All advanced-version work happens on: **`claude/project-md-advanced-version-7aP5s`**

---

## Running the Current App (Reference)

```bash
# Install dependencies
pip install ttkbootstrap bcrypt reportlab pillow openpyxl pyexcel pyexcel-xls pyexcel-xlsx

# Run restaurant manager app
python restaurant_app.py

# Run galley (kitchen) app
python galley_app.py

# Run admin app
python admin_app.py

# Build Windows executables
pyinstaller "SpeSync Suite.spec"
pyinstaller "SpeSync Admin.spec"
pyinstaller "SpeSync Galley.spec"
```

Database defaults to `orders.db` (SQLite) in the same directory. Switch to MySQL by editing `db_config.json`.

---

## File Inventory

| File | Status | Notes |
|---|---|---|
| `restaurant_app.py` | Active | Main restaurant manager app |
| `admin_app.py` | Active | Admin configuration app |
| `galley_app.py` | Active | Kitchen staff viewer |
| `dert.py` | Obsolete | Experimental copy of restaurant_app — to be deleted |
| `db_config.json` | Active | DB connection (do not commit real credentials) |
| `orders.db` | Dev only | Should not be committed to production repo |
| `icon.ico` | Active | Shared app icon |
| `SpeSync Suite.spec` | Active | PyInstaller spec for restaurant app |
| `SpeSync Admin.spec` | Active | PyInstaller spec for admin app |
| `SpeSync Galley.spec` | Active | PyInstaller spec for galley app |
| `SpeciSync *.spec` | Obsolete | Old renamed duplicates — to be deleted |
| `version_info*.txt` | Active | Windows PE version metadata |
| `*.log` | Dev only | Should not be committed |
