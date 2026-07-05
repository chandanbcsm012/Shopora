# Future Modules (out of scope for the foundation slice)

These were requested as part of the full platform vision but are **not**
implemented yet. Listed here so the foundation slice's contracts don't
paint us into a corner. Each row is the extension point already reserved
in the current code/contracts.

| Module | Future home | Extension point already in place |
|---|---|---|
| Inventory (warehouses, ledgers, reservations, QR/barcode) | new `inventory` module/service | `catalog.service.get_available_stock(product_id)` — swap its implementation to call Inventory instead of reading `Product.stock_quantity` |
| Real payment gateways (Razorpay/Stripe/PhonePe/Paytm/Cashfree, UPI, real cards/net-banking) | new provider classes in `app/modules/payments/providers.py` | the `PaymentProvider` protocol + `get_provider()` registry already exist (backing `cod`/`test_card`) — a real gateway is one more class implementing `process()`/`refund()`, no changes to `orders` checkout logic |
| Coupons/discounts, shipping-rate calculation | extend `orders` checkout | `Order.total_cents` is a straight sum of line items today (GST is now handled — see the tax engine); no discount/shipping line exists anywhere, including on invoices (deliberately not fabricated) |
| Returns/exchanges, partial cancellation, warehouse & delivery-partner assignment, shipment tracking | new modules/columns | none of these have any schema representation yet — `Order.status` is a fixed 5-value enum with no return/exchange states |
| Product variants (color/size), reviews/ratings/Q&A, compare, product video/360° view | new columns/modules | `Product` has no variant, review, or video fields; the wishlist/homepage build deliberately doesn't fabricate ratings or "sold count" data to back fake "Best Sellers"/"Trending" sections |
| Dedicated Sale page with countdown timers, discount/sale pricing | extend `catalog` | no `sale_price_cents`/`sale_ends_at` field exists on `Product` |
| Dark mode, voice search | frontend | design tokens are light-theme-only today; search is text-only (Web Speech API would be the natural addition, not attempted here) |
| CSV/Excel export (admin orders, users, products) | frontend admin pages | every admin list already supports filtering/pagination server-side; export would consume the same list endpoints |
| Multi-channel Notifications (SMS/push/Slack/webhook, retries, DLQ, preferences) | standalone service, Redis Streams (dev) / Kafka (prod) | `app/modules/email` already sends transactional HTML email (invitations, password resets) via stdlib `smtplib` against Mailpit locally — a real notifications platform would add channels beyond email and a retry/DLQ layer, not replace this |
| Search (OpenSearch, facets, geo) | new `search` module/service | `catalog` product schema already has the fields (name, description, category, brand, price) a search index would project |
| AI (recommendations, forecasting, LLM assistant) | new `ai` module/service | reads catalog + orders data via their service layers, never raw tables |
| Fraud Detection | new `fraud` module/service | hooks into `orders` checkout as a pre-commit check returning allow/deny + risk score |
| Analytics (ClickHouse/Superset/Grafana) | new `analytics` pipeline | consumes the same domain events as Notifications |
| DevOps (Docker/K8s/Helm/CI/CD/monitoring) | `infra/` | `docker-compose.yml` in repo root is the local-dev precursor (now includes Postgres + Mailpit); production infra not built |
| Configurable/granular RBAC (DB-backed Role + Permission tables, resource×action matrix editable from the admin panel) | extend `auth` module | today's 4-role hierarchy (`super_admin > admin > manager > customer`) is a fixed set of string checks in `auth.service`/`require_role`, not a data-driven permission model |
| Background job queue (Celery/RQ/arq + broker) | new infra | email sending currently uses FastAPI's built-in `BackgroundTasks` (in-process, not durable/retryable) — fine for a handful of transactional emails, not for high-volume or must-not-lose-it jobs |
| Soft deletes / optimistic locking | schema-wide | all deletes are hard deletes today; no `deleted_at`/`version` columns anywhere |
| Dedicated cross-cutting Testing/Docs teams | ongoing | each module owns its own tests/docs for now; a shared test/docs pass happens at integration checkpoints |

**Built, not deferred:** an admin panel (`/admin`) with category/brand/product
CRUD, image upload, user role/status management, email-based user
invitation, self-service password reset, an audit log of admin actions,
a customer address book, checkout with address + payment-method
selection (COD and a simulated Test Card adapter — no real gateway, no
card-data collection anywhere), PDF invoice generation/download, order
status history, and admin order management (list/filter/status-change/
refund) — see `docs/CONTRACTS.md`'s "Admin Panel additions", "User
Invitation, Password Reset & Audit Log", and "Checkout, Addresses,
Payments & Invoices" sections.

Do not start building the remaining rows until what's already built is
working and reviewed.
