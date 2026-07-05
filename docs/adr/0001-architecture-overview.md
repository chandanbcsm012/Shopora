# ADR-0001: Architecture Overview

## Status
Accepted

## Context
We are building an e-commerce platform. Given the scope of a first working
increment, we start with a **modular monolith** rather than microservices:
one deployable FastAPI backend with clearly separated modules (auth,
catalog, orders), each owning its own models/schemas/service/router/tests.
Modules communicate via in-process service calls (function imports), never
by reaching into another module's database models directly. This keeps the
option open to extract a module into its own service later (inventory,
payments, notifications, search, AI, fraud, analytics are designed as
future modules/services behind the same contract style — see
`docs/FUTURE_MODULES.md`).

## Decision
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL.
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS.
- Auth: JWT access tokens + rotating refresh tokens, RBAC via a `role` claim.
- API style: REST, versioned under `/api/v1`, JSON:API-lite envelope (see
  `docs/CONTRACTS.md`).
- One Postgres database for the monolith; each module owns its own tables
  (prefixed by module where ambiguous) and must not query another module's
  tables directly — it calls that module's service layer instead.
- Local dev via `docker-compose.yml` (postgres + backend + frontend).

## Consequences
- Fast to build and reason about for the foundation slice.
- Clear module boundaries make future extraction to microservices
  (inventory, payments, notifications, search, AI, fraud, analytics)
  straightforward: each module already looks like a service.
- Cross-module calls are synchronous Python calls for now; when extracted,
  they become HTTP/event calls using the same DTOs already defined in
  `docs/CONTRACTS.md`.
