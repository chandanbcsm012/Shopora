# Shopora

A small but real e-commerce platform: FastAPI + PostgreSQL backend, React +
Vite + Tailwind frontend, and an admin panel covering catalog, users, and
order management. Built as a modular monolith so future modules (real
payment gateways, inventory, search, analytics — see
[`docs/FUTURE_MODULES.md`](docs/FUTURE_MODULES.md)) can be added without
reworking what's already here.

## What's here

- **Storefront**: a real homepage (hero slider, category/brand/new-arrivals
  rails built from live catalog data), product browsing with price/stock
  filters and sorting, a wishlist, cart, an address book, checkout
  (address + payment method selection), order history with PDF invoices
  and a status timeline, and static pages (About, Contact, FAQ/Help
  Center, Privacy/Terms/Shipping/Return/Refund/Cookie policies, 404).
- **Payments**: a provider-adapter architecture (Cash on Delivery, and a
  simulated Test Card path for demos — no real gateway, no card data ever
  collected or stored) that a real gateway (Razorpay/Stripe/etc.) can plug
  into later without touching checkout logic.
- **INR & GST**: products/orders can be priced in INR (formatted with
  correct lakh/crore grouping) with an opt-in CGST/SGST/IGST tax engine
  based on buyer vs. seller state — see [INR & GST configuration](#inr--gst-configuration) below.
- **Admin panel** (`/admin`): one-time setup wizard for the first
  administrator, then category/brand/product CRUD (with image upload),
  order management (status changes, refunds, invoices), a 4-tier role
  hierarchy (`super_admin > admin > manager > customer`) with email-based
  user invitations, self-service password reset, an audit log of admin
  actions, and a view of submitted contact-form messages — no SQL or API
  tools required for day-to-day use.
- **Email**: transactional email (invitations, password resets, order
  confirmations) sent over real SMTP to [Mailpit](https://mailpit.axllent.org/)
  locally (web inbox at http://localhost:8025) — swap the SMTP settings
  for a real provider in production.
- **Auth**: JWT access tokens + rotating refresh tokens.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/CONTRACTS.md`](docs/CONTRACTS.md) for the system design and API
contracts (the latter is the authoritative, continuously-updated spec for
every module), and [`docs/database.md`](docs/database.md) for the schema.

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker (for PostgreSQL and Mailpit)

## Quick start

```bash
./scripts/setup.sh   # creates the backend venv, installs deps, starts
                      # Postgres + Mailpit, runs migrations, installs
                      # frontend deps (safe to re-run any time)

./scripts/run.sh      # starts Postgres (if needed) + backend + frontend,
                       # streams both logs, Ctrl+C stops both app servers
```

Then open:

| What | URL |
|---|---|
| Storefront | http://localhost:5173 |
| **Admin setup** (first run only) | http://localhost:5173/admin/setup |
| Backend API | http://127.0.0.1:8000 |
| Interactive API docs | http://127.0.0.1:8000/docs |
| Mailpit (dev email inbox) | http://localhost:8025 |

### First-time setup

The admin panel starts with no administrator account. Visit
`/admin/setup` once to create the first one — that account is created as
`super_admin` (the top of the role hierarchy) and the setup page
permanently disables itself afterward (`GET /api/v1/auth/bootstrap-status`
reports whether an admin-tier account already exists). From there:
- Create categories, brands, and products through `/admin`.
- Invite other users (with a role you're permitted to assign — see
  [Role hierarchy](#role-hierarchy)) from `/admin/users`; they receive a
  real email (via Mailpit locally) with a link to set their own password.

### Sample data (optional)

To populate the catalog with ~100 real sample products (from the free
[DummyJSON](https://dummyjson.com) API) instead of adding them by hand:

```bash
cd backend && source .venv/bin/activate
python -m scripts.seed_products            # first 100 products
python -m scripts.seed_products --limit 194  # the full DummyJSON catalog
```

Safe to re-run — it skips anything already seeded.

## Manual setup (if you'd rather not use the scripts)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd .. && docker compose up -d db mailpit
cd backend && alembic upgrade head
uvicorn app.main:app --reload &          # http://127.0.0.1:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

## Running tests

```bash
# Backend (from backend/, venv active)
pytest -v      # 293 tests

# Frontend
cd frontend
npm run build   # typecheck + production build
npm test        # vitest — 46 tests
npm run lint    # oxlint
```

All of the above pass cleanly as of this writing, and the full purchase
journey (register → browse/filter → wishlist → address → cart → checkout
→ invoice → confirmation email → admin order management) has been
verified against a real running Postgres/Mailpit stack, not just unit
tests in isolation.

## Role hierarchy

`super_admin > admin > manager > customer`, enforced server-side (not
just hidden UI):
- `super_admin` can invite/assign any role, including other admins.
- `admin` can invite/assign `manager`/`customer` only.
- `manager` gets catalog (categories/brands/products) access in `/admin`
  but not user management, audit logs, or contact messages.
- All role/status changes are recorded in the audit log
  (`/admin/audit-logs`), and an account can never modify its own role or
  active status (self-lockout protection).

## INR & GST configuration

GST is **off by default** — enabling it is entirely opt-in and only ever
applies to orders priced in `INR` (other currencies are unaffected).
Configure via `backend/.env` (copy from `.env.example`) or environment
variables:

| Variable | Default | Meaning |
|---|---|---|
| `GST_ENABLED` | `false` | Master switch. When `false`, INR orders behave exactly like USD ones (no tax fields). |
| `DEFAULT_GST_RATE_PERCENT` | `18.0` | Flat rate applied to every order line (no per-product/HSN rates in this slice). |
| `SELLER_STATE` | `Maharashtra` | Your business's state, compared against the buyer's shipping address state to decide intrastate vs. interstate. |
| `SELLER_GSTIN` | unset | Your business's GSTIN, shown on invoices when set. |
| `TAX_INCLUSIVE_PRICING` | `false` | If `true`, product prices are treated as already including GST (tax is backed out of the price rather than added on top). |

**Tax logic**: buyer state == seller state (case-insensitive) →
CGST + SGST (rate split evenly); buyer state != seller state → IGST
(full rate). Example at the default 18% rate on a ₹100.01 order:

```
Intrastate (buyer in Maharashtra):  CGST ₹9.00 + SGST ₹9.00 = ₹18.00 tax → Grand Total ₹118.01
Interstate (buyer in Karnataka):    IGST ₹18.00                          → Grand Total ₹118.01
```

Buyers can optionally attach a GSTIN to a saved address (format-validated,
not government-verified) for B2B invoices — visible on the invoice PDF
and the order detail page.

A product's currency (`USD`/`INR`) is set per-product in `/admin/products`;
`formatMoney` on the frontend automatically uses Indian digit grouping
(`₹1,00,000.00`) for INR via `Intl.NumberFormat('en-IN', ...)`.

## Project structure

```
backend/
  app/
    main.py                # FastAPI app, router + static-file mounts
    core/                   # config, db session, JWT/password hashing, error handling
    shared/                  # Base model, pagination, error codes
    modules/
      auth/                  # users, JWT auth, roles, invitations, password reset
      catalog/                # categories, brands, products, listing filters/sort
      orders/                  # cart, checkout, invoices, tax engine, order history
      addresses/                # customer address book
      payments/                  # payment provider adapters (COD, Test Card)
      wishlist/                   # customer wishlist
      site/                        # newsletter signup, contact form
      media/                        # image upload (served from media_storage/)
      email/                         # transactional email (SMTP + HTML templates)
      audit/                          # admin action audit log
  migrations/                # Alembic
  scripts/seed_products.py   # DummyJSON sample-data importer
  tests/, app/modules/*/tests/

frontend/
  src/
    api/                  # typed fetch clients (one file per backend module)
    components/            # Nav, Footer, ProductCard, RequireAdmin/RequireRole
    components/ui/          # shared design-system components
    context/                 # AuthContext, CartContext, WishlistContext
    pages/                    # storefront pages (Home, ProductList, static pages, ...)
    pages/admin/               # admin panel pages
    hooks/

docs/
  ARCHITECTURE.md, CONTRACTS.md, FUTURE_MODULES.md, database.md, adr/

scripts/
  setup.sh, run.sh         # project setup / dev-server orchestration
```

## Environment variables

Backend configuration lives in `backend/app/core/config.py`; copy
`backend/.env.example` to `backend/.env` to override anything (database
URL, JWT secret, token lifetimes, CORS origins, SMTP settings, GST
settings — see [INR & GST configuration](#inr--gst-configuration) above).

Frontend: copy `frontend/.env.example` to `frontend/.env` to override
`VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

## Troubleshooting

- **`docker: command not found` / Docker errors** — install/start Docker
  Desktop; `./scripts/setup.sh` checks for this and will tell you.
- **Port already in use** — something else is bound to 8000, 5173, or
  8025 (Mailpit); stop it or edit the port in `scripts/run.sh` /
  `frontend/vite.config.ts` / `docker-compose.yml`.
- **Migrations fail to connect** — confirm Postgres is healthy:
  `docker compose ps` / `docker compose logs db`.
- **Invitation/password-reset/order-confirmation emails not arriving** —
  check Mailpit is running (`docker compose ps mailpit`) and its web inbox
  at http://localhost:8025; in production, point `SMTP_*` settings at a
  real provider.
- **Forgot every admin password** — promote an account directly in the
  database as a last resort: `docker exec learn2-db-1 psql -U ecommerce -d ecommerce -c "UPDATE users SET role='super_admin' WHERE email='you@example.com';"`,
  then use the admin panel's Users page going forward instead of SQL.
