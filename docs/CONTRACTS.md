# Shared Contracts

Every agent/module MUST follow these. Do not invent alternate formats.

## Conventions
- All entity IDs: UUID v4, string form in JSON.
- All timestamps: UTC, ISO-8601, fields `created_at` / `updated_at`.
- Money: stored as integer **minor units** (cents) in `amount_cents` +
  `currency` (ISO 4217, e.g. `"USD"`). Never floats.
- API base path: `/api/v1`.
- Auth header: `Authorization: Bearer <access_token>`.

## Error envelope
All non-2xx JSON responses:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Product not found",
    "details": {}
  }
}
```
Codes live in `backend/app/shared/error_codes.py` as an `ErrorCode(str, Enum)`.
Baseline codes every module reuses: `VALIDATION_ERROR`, `NOT_AUTHENTICATED`,
`NOT_AUTHORIZED`, `RESOURCE_NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`,
`INTERNAL_ERROR`. Modules may add their own (e.g. `INSUFFICIENT_STOCK`)
but must register them in that same enum — no ad hoc strings.

## Pagination
Query params: `page` (default 1), `page_size` (default 20, max 100).
Response envelope:
```json
{ "items": [...], "total": 132, "page": 1, "page_size": 20 }
```

## Auth
- Access token: JWT, 15 min expiry, claims `{sub: user_id, role, exp, iat}`.
- Refresh token: opaque random string, stored hashed in `refresh_tokens`
  table, 7 day expiry, rotated on every use (old one revoked).
- Roles (as of the "User Invitation & Roles" addition below):
  `super_admin`, `admin`, `manager`, `customer`, ranked in that order.
  `require_role(*roles)` dependency (extended to accept multiple roles)
  guards role-gated routes — e.g. `require_role("admin", "super_admin")`.

## Core data contracts (fields every module codes against)

### User (owned by `auth`)
`id, email (unique), hashed_password, full_name, role, is_active, created_at, updated_at`

### RefreshToken (owned by `auth`)
`id, user_id (FK users), token_hash, expires_at, revoked_at (nullable), created_at`

### Category (owned by `catalog`)
`id, name, slug (unique), parent_id (FK categories, nullable), created_at, updated_at`

### Brand (owned by `catalog`)
`id, name, slug (unique), created_at, updated_at`

### Product (owned by `catalog`)
`id, name, slug (unique), description, brand_id (FK brands, nullable),
category_id (FK categories), price_cents, currency, sku (unique),
stock_quantity, is_active, created_at, updated_at`

> `stock_quantity` is a placeholder single-warehouse counter. The future
> Inventory module owns real stock ledgers/reservations; catalog exposes
> `get_available_stock(product_id)` today and will delegate to Inventory
> later without changing callers' contract (see `docs/FUTURE_MODULES.md`).

### ProductImage (owned by `catalog`)
`id, product_id (FK products), url, alt_text, sort_order`

### Cart / CartItem (owned by `orders`)
Cart: `id, user_id (FK users, unique), created_at, updated_at`
CartItem: `id, cart_id (FK carts), product_id (FK products), quantity, unit_price_cents`

### Order / OrderItem (owned by `orders`)
Order: `id, user_id (FK users), status, total_cents, currency, created_at, updated_at`
`status` enum: `pending, paid, shipped, delivered, cancelled`
OrderItem: `id, order_id (FK orders), product_id (FK products), product_name_snapshot, quantity, unit_price_cents`

## Cross-module service calls (in-process, this slice)
- `orders` calls `catalog.service.get_product_for_order(product_id) -> ProductOrderView`
  (raises `NOT_FOUND` / returns None if inactive or out of stock).
- `orders` calls `auth.dependencies.get_current_user` like any router does
  (FastAPI dependency, not a raw import of the User model).

## REST endpoints (v1)

### auth
- `POST /api/v1/auth/register` -> 201 User (no password)
- `POST /api/v1/auth/login` -> `{access_token, refresh_token, token_type: "bearer"}`
- `POST /api/v1/auth/refresh` -> same shape, rotates refresh token
- `POST /api/v1/auth/logout` -> 204, revokes refresh token
- `GET /api/v1/auth/me` -> current User

### catalog
- `GET /api/v1/categories` / `POST` (admin)
- `GET /api/v1/brands` / `POST` (admin)
- `GET /api/v1/products` (filters: `category_id`, `brand_id`, `q`, pagination)
- `GET /api/v1/products/{id}`
- `POST /api/v1/products` (admin) / `PATCH` / `DELETE`

### orders
- `GET /api/v1/cart` -> current user's cart (creates empty one if absent)
- `POST /api/v1/cart/items` `{product_id, quantity}`
- `PATCH /api/v1/cart/items/{item_id}` `{quantity}`
- `DELETE /api/v1/cart/items/{item_id}`
- `POST /api/v1/orders/checkout` -> creates Order from current cart, empties cart
- `GET /api/v1/orders` -> current user's orders (paginated)
- `GET /api/v1/orders/{id}`

## Admin Panel additions (foundation scope)

Added to support a frontend-only admin experience (setup wizard, user role
management, category/brand/product CRUD, image upload). Scope is
deliberately limited to what the existing schema already supports well —
no product variants, no granular multi-role RBAC (still just
`admin`/`customer`), no media library/reuse, no audit log, no soft deletes.
See `docs/FUTURE_MODULES.md` for what's deferred.

### New error codes (`app/shared/error_codes.py`)
- `SETUP_ALREADY_COMPLETED` (409) — bootstrap attempted when an admin already exists
- `CANNOT_MODIFY_OWN_ACCOUNT` (400) — self-lockout prevention on role/status changes
- `CATEGORY_IN_USE` (409) — delete blocked: category has products or child categories
- `BRAND_IN_USE` (409) — delete blocked: brand has products
- `UNSUPPORTED_FILE_TYPE` (415) — media upload: not an accepted image type
- `FILE_TOO_LARGE` (413) — media upload: exceeds 5MB limit

### `auth` module extensions (owns User; extend, don't duplicate)
- `GET /api/v1/auth/bootstrap-status` — **public**, no auth. Returns
  `{"admin_exists": bool}` (`SELECT EXISTS(... WHERE role='admin')`). Used
  by the frontend to decide whether to show the setup wizard.
- `POST /api/v1/auth/bootstrap` — **public**, but self-limiting: raises
  `SETUP_ALREADY_COMPLETED` (409) if any admin already exists. Body
  `{email, password, full_name}` (same shape as `UserCreate`). Creates a
  user with `role="admin"`, then behaves like login — returns `TokenPair`
  (201) so the wizard can log the new admin in immediately, matching the
  existing register→auto-login pattern in `AuthContext`.
- `GET /api/v1/users` — admin only (`require_role("admin")`). Query:
  `page`, `page_size`, `q` (case-insensitive match on email or full_name,
  same pattern as catalog's product search). Returns `Page[UserOut]`.
- `PATCH /api/v1/users/{user_id}/role` — admin only. Body
  `{"role": "admin" | "customer"}`. Returns updated `UserOut`. Raises
  `CANNOT_MODIFY_OWN_ACCOUNT` if `user_id` is the caller's own id.
- `PATCH /api/v1/users/{user_id}/status` — admin only. Body
  `{"is_active": bool}`. Returns updated `UserOut`. Raises
  `CANNOT_MODIFY_OWN_ACCOUNT` if `user_id` is the caller's own id.

### `catalog` module extensions (owns Category/Brand/Product; extend, don't duplicate)
- `Category` gets one new nullable column: `image_url: str | None`
  (migration required). Added to `CategoryCreate`/`CategoryUpdate`/`CategoryOut`.
- `PATCH /api/v1/categories/{id}` — admin only. Partial update (name, slug,
  parent_id, image_url). Reuses the existing slug-uniqueness check.
- `DELETE /api/v1/categories/{id}` — admin only. Raises `CATEGORY_IN_USE`
  (409) if any `Product.category_id` or `Category.parent_id` references it
  — do not let a raw FK `IntegrityError` bubble up as a 500.
- `PATCH /api/v1/brands/{id}` — admin only. Partial update (name, slug).
- `DELETE /api/v1/brands/{id}` — admin only. Raises `BRAND_IN_USE` (409) if
  any `Product.brand_id` references it.
- No changes to `Brand`'s schema (name/slug only, matches today).

### New `media` module (`app/modules/media/`) — new module, nothing to extend
- `POST /api/v1/media/upload` — admin only, `multipart/form-data`, field
  name `file`. Validates content-type is one of `image/jpeg`, `image/png`,
  `image/webp`, `image/gif` (else `UNSUPPORTED_FILE_TYPE`, 415) and size
  ≤ 5MB (else `FILE_TOO_LARGE`, 413). Saves under
  `backend/media_storage/<uuid>.<ext>` (gitignored — not committed) and
  returns `{"url": "/media/<uuid>.<ext>"}` (200). `/media` is mounted in
  `app/main.py` as a `StaticFiles` directory serving `media_storage/`.
  This is the URL you put directly into `ProductImage.url` /
  `Category.image_url` — there is no separate "media library" of reusable
  assets in this slice, just direct upload-then-reference.

### Frontend-only additions
- `RequireAdmin` route guard (parallel to `ProtectedRoute`): redirects to
  `/login` if unauthenticated, or to `/` if authenticated but
  `user.role !== "admin"`.
- New routes: `/admin/setup`, `/admin` (redirects to `/admin/products`),
  `/admin/categories`, `/admin/brands`, `/admin/products`,
  `/admin/products/new`, `/admin/products/:id/edit`, `/admin/users`.
- Nav shows an "Admin" link only when `user?.role === "admin"`.

## User Invitation, Password Reset & Audit Log (foundation scope)

Extends the Admin Panel: email-based user invitation (replacing the idea of
an admin ever typing/sending a password), self-service password reset, and
an audit trail of admin actions. Deliberately excludes (see
`docs/FUTURE_MODULES.md`): a configurable permission matrix (roles are
still just 4 fixed strings, not DB-configurable), a background job queue
(email is sent via FastAPI's built-in `BackgroundTasks`, not
Celery/Redis), soft-delete/optimistic-locking, and demo data for entities
with no backend model (warehouses, coupons, reviews, variants, suppliers,
delivery partners, analytics).

### Role hierarchy
`super_admin > admin > manager > customer`. Enforced in
`auth.service` when assigning roles, not just at the route level:
- `super_admin` may invite/assign any role, including `admin`/`super_admin`.
- `admin` may invite/assign `manager` or `customer` only — NOT `admin` or
  `super_admin` (raises `INSUFFICIENT_ROLE_PRIVILEGE`, 403).
- `manager` cannot access user-management endpoints at all
  (`require_role("admin", "super_admin")` on those routes).
- `manager` (in addition to `admin`/`super_admin`) DOES get catalog
  write access — update catalog's `require_admin` gate to
  `require_role("admin", "super_admin", "manager")`.
- The existing self-modification guard (`CANNOT_MODIFY_OWN_ACCOUNT`) still
  applies on top of the hierarchy check.

### New error codes
- `INVITATION_INVALID` (404), `INVITATION_EXPIRED` (410),
  `INVITATION_ALREADY_ACCEPTED` (409)
- `RESET_TOKEN_INVALID` (404), `RESET_TOKEN_EXPIRED` (410)
- `INSUFFICIENT_ROLE_PRIVILEGE` (403) — role-hierarchy violation on invite/role-assignment

### New config (`app/core/config.py` — already added by the Main Coordinator)
`frontend_url`, `invitation_token_expire_hours` (48),
`password_reset_token_expire_minutes` (60),
`password_reset_rate_limit_per_hour` (3), `smtp_host`/`smtp_port`/
`smtp_use_tls`/`smtp_username`/`smtp_password`/`smtp_from_email`/
`smtp_from_name` (defaults point at the Mailpit service already added to
`docker-compose.yml`, host `localhost` port `1025` for local dev since the
backend runs via the venv, not the containerized `backend` service).

### New `email` module (`app/modules/email/`) — new module, no DB table
- `service.py`: `send_email(to: str, subject: str, html_body: str) -> None`
  using stdlib `smtplib`/`email.mime` (no new pip dependency). Reads
  SMTP settings from `app.core.config.settings`.
- `templates.py`: two plain Python string-template functions —
  `invitation_email(full_name, role, accept_url, expires_at) -> str` (HTML)
  and `password_reset_email(full_name, reset_url, expires_at) -> str` (HTML).
  Keep them simple (inline styles, a heading, a button-styled link) — no
  templating engine dependency needed for two templates.
- Callers use FastAPI's `BackgroundTasks.add_task(send_email, ...)` from
  the router layer so the HTTP response doesn't block on SMTP.

### New `audit` module (`app/modules/audit/`) — owns `AuditLog`
- `models.py`: `AuditLog(id, actor_user_id [FK users, nullable], action
  [str], resource_type [str], resource_id [str, nullable], ip_address
  [str, nullable], user_agent [str, nullable], before_state [JSON,
  nullable], after_state [JSON, nullable], created_at)`. No `updated_at` —
  audit rows are append-only/immutable.
- `service.py`: `async def log_action(db, *, actor_user_id, action,
  resource_type, resource_id=None, ip_address=None, user_agent=None,
  before=None, after=None) -> None` — other modules call this directly
  (it's infrastructure, like the `media` module, not a business-domain
  module other modules must avoid touching).
- Actions to log (string values, dot-namespaced): `user.invited`,
  `user.invitation_accepted`, `user.role_changed`, `user.status_changed`,
  `user.password_reset_requested`, `user.password_reset_completed`.
- `router.py`: `GET /api/v1/audit-logs` (admin/super_admin only) — paginated
  (`Page[AuditLogOut]`), filterable by `action`, `resource_type`,
  `actor_user_id`, sorted newest-first.

### `auth` module extensions
- New models: `Invitation(id, email, full_name, role, notes [nullable],
  invited_by_user_id [FK users], token_hash, expires_at, accepted_at
  [nullable], created_at)`, `PasswordResetToken(id, user_id [FK users],
  token_hash, expires_at, used_at [nullable], created_at)` — same
  opaque-token + SHA-256-hash-for-lookup pattern as `RefreshToken`
  (`generate_refresh_token()`/`hash_refresh_token()`/`verify_refresh_token()`
  in `app/core/security.py` are generic enough to reuse verbatim for both
  new token types — do not write new hashing helpers).
- `POST /api/v1/users/invite` (admin/super_admin only) body
  `{email, full_name, role, notes?}`. Enforces the role hierarchy (see
  above). Creates an inactive `User` (`is_active=False`, a random unusable
  `hashed_password` placeholder — login already rejects inactive users, so
  this is belt-and-suspenders, not the primary safeguard) if one doesn't
  already exist for that email (409 `EMAIL_ALREADY_REGISTERED` if it
  does), plus an `Invitation` row, sends the invitation email in the
  background, logs `user.invited`. Returns the created `Invitation`
  (without the raw token) or 201 with minimal info — the frontend doesn't
  need the token, only confirmation.
- `GET /api/v1/auth/invitations/{token}` (public) → validates the token
  (raises `INVITATION_INVALID`/`INVITATION_EXPIRED`/`INVITATION_ALREADY_ACCEPTED`
  as appropriate), returns `{email, full_name, role, expires_at}` so the
  frontend can show context before the user sets a password.
- `POST /api/v1/auth/accept-invitation` (public) body `{token, password}`
  → validates token, sets the user's real password, `is_active=True`,
  marks `accepted_at`, logs `user.invitation_accepted`, returns `TokenPair`
  (auto-login — same pattern as register/bootstrap).
- `POST /api/v1/auth/forgot-password` (public) body `{email}` → **always**
  returns 202 regardless of whether the email exists (no user
  enumeration). If a matching *active* user exists, rate-limit by
  counting `PasswordResetToken` rows created for that email in the last
  hour (`password_reset_rate_limit_per_hour`; exceeding it silently no-ops
  — still return 202, don't leak rate-limit state either) — otherwise
  create a token, email the reset link, log
  `user.password_reset_requested`.
- `POST /api/v1/auth/reset-password` (public) body `{token, new_password}`
  → validates token (`RESET_TOKEN_INVALID`/`RESET_TOKEN_EXPIRED`), updates
  `hashed_password`, marks the token used, **revokes all of that user's
  `RefreshToken` rows** (invalidate existing sessions), logs
  `user.password_reset_completed`. Returns 204 — do NOT auto-login here
  (unlike invitation-accept); the user logs in fresh, which is the more
  conventional/secure UX for a reset flow specifically.
- `UserRoleUpdate` schema's role field becomes a `Literal["super_admin",
  "admin", "manager", "customer"]` (was `Literal["admin", "customer"]`);
  `update_user_role` service function gets the same hierarchy check as
  invite.
- `PATCH /api/v1/users/{user_id}/role` and `.../status` are otherwise
  unchanged (still self-modification-guarded) but now also call
  `audit.service.log_action` for `user.role_changed`/`user.status_changed`,
  capturing before/after role or status.

### Migration
One new revision adding `invitations`, `password_reset_tokens`,
`audit_logs` tables. No changes to the existing `users` table — `role` was
already a free `String(20)` column (not a Postgres enum), so widening the
allowed values is a pure application-layer change.

### Frontend-only additions
- Public routes: `/accept-invitation` (reads `?token=`), `/forgot-password`,
  `/reset-password` (reads `?token=`). "Forgot password?" link added to
  `Login.tsx`.
- Admin: an "Invite user" action on `/admin/users` (form: full name,
  email, role — role `<select>` options filtered client-side to what the
  current user is allowed to assign, mirroring the backend hierarchy rule
  as a UX nicety, not a security boundary). New `/admin/audit-logs` page
  (admin/super_admin only), paginated table of actions.
- `RequireAdmin` (or a variant) now admits `manager` too, since managers
  get catalog access — `AdminLayout`'s tab bar conditionally shows
  "Users"/"Audit Logs" tabs only for `admin`/`super_admin`, while
  Categories/Brands/Products show for `admin`/`super_admin`/`manager`.
- Nav's "Admin" link visible for `admin`/`super_admin`/`manager` (was
  `admin`-only).

## Checkout, Addresses, Payments & Invoices (foundation scope)

Extends checkout with real address selection and a real (if simulated)
payment adapter architecture. Deliberately excludes (see
`docs/FUTURE_MODULES.md`): real payment gateways (Razorpay/Stripe/etc —
the adapter interface is built so one drops in later without touching
checkout logic), coupons/discounts, tax and shipping-rate calculation,
returns/exchanges/partial cancellation, warehouse/delivery-partner
assignment, shipment tracking, CSV/Excel export. `reportlab==5.0.0` is a
new dependency (already added to `requirements.txt`, installs cleanly as
a pure-Python wheel — verified before this work started).

### New error codes
`INVALID_PAYMENT_METHOD` (400), `PAYMENT_FAILED` (402),
`PAYMENT_NOT_REFUNDABLE` (409), `REFUND_EXCEEDS_PAYMENT_AMOUNT` (409),
`INVOICE_NOT_AVAILABLE` (404 — invoice requested before payment succeeded).

### New `addresses` module (`app/modules/addresses/`) — owns `Address`
Self-service address book, one module, not folded into `auth` (identity)
or `orders` (transactional) since it's neither.

`Address` fields: `id, user_id [FK users], full_name, phone,
alternate_phone [nullable], company [nullable], address_line1,
address_line2 [nullable], landmark [nullable], city, district [nullable],
state, country, postal_code, delivery_instructions [nullable],
address_type [str: "home"|"office"|"warehouse"|"other"],
is_default_shipping [bool, default False], is_default_billing [bool,
default False], created_at, updated_at`. Hard delete (matches every
other entity in this app — no soft-delete/restore anywhere yet). No
latitude/longitude.

Setting `is_default_shipping=True` (or `is_default_billing=True`) on one
address must clear that same flag on the user's other addresses in the
same transaction (only one default of each kind at a time) — do this in
the service layer, not via a DB constraint.

Endpoints (own router, mounted at `/api/v1`, all scoped to
`get_current_user` — a user only ever sees their own addresses):
- `GET /addresses` → `list[AddressOut]` (no pagination needed, address
  books are small; plain array like categories/brands).
- `POST /addresses` → 201 `AddressOut`.
- `PATCH /addresses/{id}` → `AddressOut`. 404 if missing or not owned by
  the caller (don't leak existence of other users' addresses — a 404,
  not a 403, for "exists but not yours").
- `DELETE /addresses/{id}` → 204. Same ownership check.

Cross-module contract consumed by `orders`: `async def
get_address_for_user(db, address_id, user_id) -> Address | None` —
returns `None` if missing or not owned by that user (mirrors
`catalog.get_available_product`'s "None means not usable" convention).
`orders` calls this, never queries the `addresses` table directly.

### New `payments` module (`app/modules/payments/`) — owns `Payment` + the provider adapter
`Payment` fields: `id, order_id [FK orders, unique — one payment per
order in this scope], method [str: "cod"|"test_card"], status [str:
"pending"|"authorized"|"captured"|"failed"|"cancelled"|"refunded"|
"partially_refunded"|"expired"], amount_cents, currency,
refunded_amount_cents [default 0], provider_reference [nullable str],
failure_reason [nullable str], created_at, updated_at`.

Adapter interface (`providers.py`), so a real gateway later implements
the same shape without touching `orders`:
```python
class PaymentOutcome(BaseModel):
    status: str  # one of the Payment.status values
    provider_reference: str | None = None
    failure_reason: str | None = None

class PaymentProvider(Protocol):
    method: ClassVar[str]
    async def process(self, payment: Payment, **kwargs) -> PaymentOutcome: ...
    async def refund(self, payment: Payment, amount_cents: int) -> PaymentOutcome: ...
```
Two implementations:
- `CODProvider` (`method = "cod"`): `process()` always returns
  `status="pending"` (cash isn't collected until delivery — this is
  intentional, not a bug; see the Order-status note below).
  `refund()` returns `PAYMENT_NOT_REFUNDABLE` (raise the `AppError`) —
  nothing was captured, there's nothing to refund.
- `TestCardProvider` (`method = "test_card"`): **does not collect or
  accept any real card number/expiry/CVV — there is no card-data field
  anywhere in this method.** `process(self, payment, outcome:
  Literal["succeed","decline"] = "succeed")`: `"succeed"` →
  `status="captured"`, `provider_reference=f"TEST-{uuid4().hex[:12]}"`;
  `"decline"` → `status="failed"`, `failure_reason="Test card declined (simulated)"`.
  `refund()`: if `payment.status not in ("captured", "partially_refunded")`
  or the requested amount exceeds what's left to refund, raise the
  matching `AppError`; otherwise return `status="refunded"` (full) or
  `"partially_refunded"` (partial) with a fresh fake
  `provider_reference`.
- `get_provider(method: str) -> PaymentProvider`: registry lookup,
  raises `AppError(INVALID_PAYMENT_METHOD, ..., 400)` for anything else.

No standalone payment endpoints in this module — `orders` drives payment
processing as part of checkout/refund (see below) and exposes payment
status as part of the order response, since a payment has no independent
lifecycle outside its order in this scope.

### `orders` module extensions
- `Order` gains two new **nullable** FK columns: `shipping_address_id`,
  `billing_address_id` (→ `addresses.id`, raw FK, no cross-module model
  import — same pattern as the existing `user_id` FK). Nullable because
  existing rows predate this column; the API layer requires both for new
  checkouts, the DB does not enforce it.
- New `OrderStatusHistory`: `id, order_id [FK orders], from_status
  [nullable — null for the initial creation], to_status, note [nullable],
  created_at`. Append-only, no `updated_at`. Every `Order.status` write,
  anywhere (checkout, payment result, admin status change), inserts one
  of these — **never** update `Order.status` without also inserting a
  history row in the same transaction.
- New `Invoice`: `id, order_id [FK orders, unique], sequence_number
  [Integer, `Identity(start=1)`, unique, not null — safe concurrent
  auto-increment, NOT tied to the UUID primary key], created_at`. The
  human-readable `invoice_number` (e.g. `INV-000123`) is a
  `@computed_field` in the Pydantic schema (`f"INV-{sequence_number:06d}"`),
  not a stored column — same pattern as `line_total_cents`/`subtotal_cents`
  elsewhere in this module. An `Invoice` row is created only when an
  order's payment succeeds (see checkout flow below); attempting to
  fetch/download one before that raises `INVOICE_NOT_AVAILABLE`.
- New `invoice_pdf.py`: `generate_invoice_pdf(order, invoice,
  shipping_address, billing_address) -> bytes` using `reportlab`
  (`SimpleDocTemplate` + `Table`/`Paragraph`, rendered to an in-memory
  `io.BytesIO` — PDFs are generated on demand, never persisted to disk,
  so "re-download"/"admin regenerate" just means "call this function
  again", always fresh from current order data). Content: "Shopora"
  text header (no logo asset exists — plain text is fine),
  invoice number + date, order id, bill-to address, ship-to address, a
  line-item table (SKU, product name, quantity, unit price, line total —
  see the `OrderItem.sku_snapshot` addition below), order total, payment
  method + status, order status. No tax/shipping/discount line items
  (none are calculated anywhere in this app — do not fabricate numbers
  for them), no QR code (explicitly deferred).
- `OrderItem` gains one new column: `sku_snapshot [str]`, populated at
  checkout time alongside the existing `product_name_snapshot` (same
  transaction, same source — `ProductOrderView` would need a `sku`
  field added, or fetch it from the same `get_available_product` call
  path; use whichever is less invasive to the existing checkout code).
  This is the only reason the invoice can show real SKUs.
- **`POST /orders/checkout` (existing endpoint — EXTEND, do not create a
  new one) now requires a body**: `{shipping_address_id: str,
  billing_address_id: str, payment_method: "cod" | "test_card",
  test_card_outcome?: "succeed" | "decline"}` (`test_card_outcome`
  defaults to `"succeed"`, ignored for `"cod"`). Flow:
  1. Existing cart/stock validation (unchanged).
  2. Resolve both addresses via `addresses.get_address_for_user` — 404
     (`RESOURCE_NOT_FOUND`) if either is missing/not owned.
  3. Create the `Order` (+ `OrderItem`s, + the two address FKs) at
     `status="pending"`, insert the `(null → pending)` history row, empty
     the cart — all as today, just with addresses attached.
  4. Create a `Payment` row (`status="pending"`, `amount_cents =
     order.total_cents`), call `get_provider(payment_method).process(...)`.
  5. If the outcome is `"captured"` or `"pending"` (COD): update the
     `Payment` row, transition `Order.status` to `"paid"` (yes, even for
     COD, where cash hasn't literally been collected yet — "paid" here
     means "order confirmed, payment method accepted"; the `Payment.status`
     field is what distinguishes "cash still owed" (`pending`) from
     "already charged" (`captured"), so the real distinction isn't
     lost, just not surfaced as a separate `Order.status` value), insert
     the matching history row, create the `Invoice` (next
     `sequence_number`), and schedule the confirmation email via
     `BackgroundTasks` (see below). Commit. Return the `OrderOut` (extend
     its schema with `payment_status`, `invoice_number` fields).
  6. If the outcome is `"failed"`: update the `Payment` row, transition
     `Order.status` to `"cancelled"`, insert the history row, **commit
     this audit trail** (the failed attempt is real and should be
     visible in order history / admin view), then raise
     `AppError(PAYMENT_FAILED, payment.failure_reason, 402)` — the
     endpoint returns an error, not a 201, even though a (cancelled)
     `Order` row now exists.
- `GET /orders/{id}` (existing) response (`OrderOut`) gains
  `shipping_address`/`billing_address` (embedded `AddressOut`, nullable),
  `payment_status`, `invoice_number` (nullable — only present once an
  `Invoice` exists).
- `GET /orders/{id}/invoice` (new, owner or admin/super_admin) → raw
  `application/pdf` response (not JSON — see the frontend note on binary
  responses below), `Content-Disposition: attachment;
  filename="{invoice_number}.pdf"`. Raises `INVOICE_NOT_AVAILABLE` (404)
  if no `Invoice` exists yet for that order.
- `GET /orders/{id}/timeline` (new, owner or admin/super_admin) →
  `list[OrderStatusHistoryOut]`, oldest first.
- New `admin_router` in `orders/router.py` (same split pattern as
  `auth`'s `router`/`admin_router`), mounted at `/api/v1`:
  - `GET /admin/orders` (admin/super_admin only) — `Page[OrderOut]`,
    filterable by `status`, sortable newest-first by default.
  - `PATCH /admin/orders/{id}/status` (admin/super_admin only) — body
    `{status: "pending"|"paid"|"shipped"|"delivered"|"cancelled", note?:
    str}`. Inserts the history row. No business-rule validation of
    "legal" transitions in this foundation scope (an admin can set any
    status) — just always record history.
  - `POST /admin/orders/{id}/refund` (admin/super_admin only) — body
    `{amount_cents?: int}` (omitted = full remaining refund). Calls
    `get_provider(payment.method).refund(...)`, updates the `Payment`
    row (`status`, `refunded_amount_cents`), does **not** change
    `Order.status` (a refunded order is still "delivered"/whatever it
    was — refund is a payment-level fact, not an order-status one).

### `email` module extension
One new template function in the existing `templates.py`:
`order_confirmation_email(full_name, order, shipping_address) -> str`
(HTML — customer name, order id, ordered items with quantity/price,
shipping address, payment method + status, order total, a line
mentioning the invoice is available from "My Orders"). Sent via
`BackgroundTasks.add_task(send_email, ...)` from the checkout route,
reusing `send_email` exactly as invitations/password-resets already do —
**never send synchronously in the request path.**

### Frontend-only additions
- New page `/addresses` (Address Book): list saved addresses as cards,
  add/edit (inline form or a `ConfirmDialog`-adjacent modal, consistent
  with how `Categories.tsx` handles its create/edit form), delete behind
  `ConfirmDialog`, a way to mark one as default shipping / default
  billing.
- `Nav.tsx`: add an "Addresses" link next to "Orders" for authenticated
  users.
- `Checkout.tsx` rewrite: address selection (pick a saved address or add
  one inline — reuse the address form from the Address Book page rather
  than duplicating it), payment method selection (COD, or "Test Card"
  with a `"succeed"`/`"decline"` choice clearly labeled as a demo/test
  path — no card-number-shaped input field anywhere), then the existing
  order review/total, then "Place order". A single page with clear
  sections, not a routed multi-step wizard with its own progress bar —
  matches this app's existing preference for simple, un-nested flows.
- `OrderDetail.tsx`: payment status `Badge`, a "Download Invoice" button
  when `invoice_number` is present, and the order status timeline
  (`GET /orders/{id}/timeline`) rendered as a simple vertical list.
- **Binary download handling**: `api/client.ts`'s `apiRequest<T>` assumes
  a JSON response — the invoice endpoint returns a PDF. Add a small
  dedicated function (e.g. `downloadInvoice(orderId)` in a new
  `api/invoices.ts` or alongside `api/orders.ts`) that does its own
  `fetch` with the Bearer header, reads `.blob()`, and triggers a browser
  download (`URL.createObjectURL` + a temporary `<a download>` click) —
  don't force this through `apiRequest<T>`'s JSON assumption.
- New admin pages: `/admin/orders` (list, filter by status, search — same
  table/pagination/skeleton/empty-state conventions as every other admin
  list page) and `/admin/orders/:id` (items, both addresses, payment
  info + a refund action behind `ConfirmDialog`, a status-change control,
  the timeline, a download-invoice button). Add the "Orders" tab to
  `AdminLayout` (admin/super_admin only, same visibility rule as
  Users/Audit Logs).

## INR Currency & GST (foundation scope)

Adds proper multi-currency formatting (was silently hardcoded to `en-US`
regardless of the order's actual currency — a real latent bug) and a GST
tax engine for INR orders. Deliberately excludes: per-product tax
rates/HSN-SAC codes (no such field exists on `Product` — one flat
`default_gst_rate_percent` applies to every line item), a database-backed
admin Settings page (config stays environment-variable-driven, which the
brief itself allows: "Configuration should be environment/config driven
where possible"), real GSTIN checksum/government verification (format
regex only), discounts before/after tax (no coupon/discount system
exists), and payment-gateway-specific INR/webhook updates (no real
gateway is wired up yet — COD/Test Card don't inspect currency at all,
so they already "work" in any currency).

### Config additions (`app/core/config.py`)
`gst_enabled: bool = False`, `default_gst_rate_percent: float = 18.0`,
`seller_state: str = "Maharashtra"`, `seller_gstin: str | None = None`,
`tax_inclusive_pricing: bool = False`.

### New `orders/tax.py` (pure functions, no DB access, easy to unit test)
```python
class TaxBreakdown(BaseModel):
    taxable_amount_cents: int
    cgst_cents: int
    sgst_cents: int
    igst_cents: int
    tax_total_cents: int
    grand_total_cents: int
    effective_tax_rate_percent: float

def calculate_gst(subtotal_cents: int, buyer_state: str | None) -> TaxBreakdown | None:
    ...
```
Returns `None` if `settings.gst_enabled` is `False` or `buyer_state` is
falsy (nothing to compute against). Otherwise: if
`settings.tax_inclusive_pricing`, `subtotal_cents` already includes tax —
back it out (`taxable = subtotal / (1 + rate/100)`); else `subtotal_cents`
is pre-tax and tax is added on top. Compare `buyer_state` to
`settings.seller_state` **case-insensitively, trimmed** — equal ⇒
intrastate ⇒ split `default_gst_rate_percent` evenly into `cgst`+`sgst`
(each half); not equal ⇒ interstate ⇒ full rate as `igst`, `cgst`/`sgst`
zero. Round to the nearest cent/paise using the same "never float
arithmetic on money" discipline as the rest of this codebase (integer
cents in, integer cents out — use `Decimal` internally if needed, not
raw float division). Only invoked at checkout when `order.currency ==
"INR"` — GST is India-specific and doesn't apply to other currencies.

### `Order` model additions (all nullable — backward compatible)
`taxable_amount_cents, cgst_cents, sgst_cents, igst_cents,
tax_total_cents, grand_total_cents` (all `Integer`, nullable). **`Order.total_cents`
keeps its existing meaning** (sum of line items, pre-tax) for backward
compatibility — every existing order/test that reads `total_cents`
continues to work unchanged. When GST applies, `grand_total_cents` is the
actual amount charged/displayed as the order's bottom line; frontend code
must display `order.grand_total_cents ?? order.total_cents` everywhere a
"Total" is shown (Checkout review, `OrderDetail`, `Orders` list, admin
order views), not `total_cents` alone. The amount passed to
`payments.service.create_payment` (`amount_cents`) must likewise be
`grand_total_cents ?? total_cents`, not always `total_cents` — the
customer is charged the tax-inclusive amount when GST applies.

### `addresses` module addition
`Address` gains one new nullable column: `gstin: str | None` (buyer's
GSTIN, for B2B). Validate format only (not checksum, not government
lookup) via a regex in the Pydantic schema:
`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$` (standard
15-character GSTIN shape) — reject with `VALIDATION_ERROR` if present but
malformed; the field itself stays optional.

### `orders` checkout integration
After computing the existing pre-tax `total_cents` (unchanged), if
`order.currency == "INR"`: call `calculate_gst(total_cents,
shipping_address.state)`, and if it returns a breakdown, store all six
new fields on the `Order` and use `grand_total_cents` as the amount
charged (see above). If it returns `None` (GST disabled or no state),
leave the six new fields `null` and behave exactly as before.

### Invoice PDF (`invoice_pdf.py`)
When the order has a non-null `tax_total_cents`, add a tax breakdown
section to the summary table (Taxable Amount, CGST, SGST, IGST, Grand
Total) between the existing item table and the payment method/status
lines — reuse the existing `_money()` helper, don't hardcode `$`/`₹`
symbols (the existing `_money` already prefixes with the currency code
string like `"INR 1234.56"`, keep that convention, don't switch to a
locale-formatted symbol in the PDF).

### Frontend
- `src/lib/format.ts`'s `formatMoney(amountCents, currency)`: fix the
  hardcoded `'en-US'` locale — pick the `Intl.NumberFormat` locale from
  the currency itself (`INR` → `'en-IN'`, everything else → `'en-US'` as
  the existing default). `Intl.NumberFormat('en-IN', {style:'currency',
  currency:'INR'})` already produces correct lakh/crore grouping
  natively — no custom grouping logic needed.
- Admin `ProductForm.tsx`: the currency field becomes a real `<select>`
  (`USD`, `INR`) instead of a fixed/implicit value, if it isn't already
  one.
- `Addresses.tsx`'s `AddressForm`: add an optional GSTIN input field.
- Everywhere an order/cart "Total" is displayed (`Checkout.tsx`,
  `OrderDetail.tsx`, `Orders.tsx`, `admin/Orders.tsx`,
  `admin/OrderDetail.tsx`): prefer `grand_total_cents` over `total_cents`
  when present, and show a tax breakdown line (Subtotal / CGST / SGST /
  IGST / Total) when the order carries tax fields — same "only render if
  present" pattern already used for `payment_status`/`invoice_number`.

## Storefront: Homepage, Filtering, Wishlist & Static Pages (foundation scope)

Rebuilds the storefront's front door into a real marketing homepage
(product browsing moves from `/` to `/products`), adds price/stock
filtering and sorting to the product listing, adds a backend-synced
wishlist, and adds static informational pages. Deliberately excludes
(see `docs/FUTURE_MODULES.md`): product videos/360° view, variants
(color/size), reviews/ratings/Q&A, a compare feature, a dedicated Sale
page with countdown timers (no discount/sale-price field exists on
`Product`), dark mode, and voice search — none of these have supporting
data or infrastructure today, and this pass does not fabricate fake data
to simulate them (e.g. no fake "1,204 sold" or star ratings with no
underlying reviews).

### New error codes
None — every new mutation here (wishlist add/remove, newsletter/contact
submission) reuses existing codes (`RESOURCE_NOT_FOUND`,
`VALIDATION_ERROR`).

### New `wishlist` module (`app/modules/wishlist/`) — owns `WishlistItem`
`WishlistItem` fields: `id, user_id [FK users], product_id [FK products],
created_at`. Unique constraint on `(user_id, product_id)` — adding an
already-wishlisted product is idempotent (returns the existing row, not a
conflict error). Raw `ForeignKey("products.id")` column, no cross-module
model import, same discipline as every other module.

Endpoints (own router, mounted at `/api/v1`, all behind
`get_current_user` — a user only ever sees their own wishlist):
- `GET /wishlist` → `list[WishlistItemOut]` (`{id, product_id,
  created_at}` — deliberately NOT embedding product details; the frontend
  enriches by calling `catalogApi.getProduct(product_id)` per item, the
  exact same client-side enrichment pattern `CartContext` already uses
  for cart line items, including tolerating a 404 for a
  deleted/deactivated product rather than crashing the page). Plain
  array, no pagination (wishlists are small, same reasoning as
  addresses/categories/brands).
- `POST /wishlist` body `{product_id}` → 201 `WishlistItemOut`. Validates
  the product exists (raises `RESOURCE_NOT_FOUND` if not — check via a
  raw Core table reference to `products`, the same technique
  `catalog.service`'s new `_order_items_table`/`_cart_items_table` and
  `orders.service`'s `_products_table` already use for cross-module
  existence checks without a model import) but does NOT require the
  product to be active — a customer can wishlist something that later
  goes out of stock or inactive and still see it listed (mirroring how
  cart/orders already handle "product no longer available" gracefully).
- `DELETE /wishlist/{product_id}` → 204, idempotent (204 whether or not
  it was actually wishlisted — removing something not there is not an
  error).

### `catalog` module extensions — product listing filters/sort
Extend `list_products` (and both the public `GET /products` and admin
`GET /admin/products` routes, which both call it) with:
- `min_price_cents: int | None`, `max_price_cents: int | None` — filter
  on `Product.price_cents` range (both optional, independently usable).
- `in_stock_only: bool = False` — when `True`, filter
  `Product.stock_quantity > 0`.
- `sort: Literal["newest", "price_asc", "price_desc", "name_asc",
  "name_desc"] = "newest"` — replaces the current hardcoded
  `order_by(Product.created_at.desc())`; `"newest"` preserves that exact
  existing behavior (default, backward compatible — no existing caller
  that doesn't pass `sort` sees any change).

### New `site` module (`app/modules/site/`) — owns `NewsletterSubscriber`, `ContactMessage`
Small, honest backend for two forms that would otherwise be fake UI that
goes nowhere (this project's "don't build a demo/placeholder interface"
standard applies to marketing-site chrome too, not just checkout).
- `NewsletterSubscriber`: `id, email [unique], created_at`.
- `ContactMessage`: `id, name, email, subject, message, created_at`.
- `POST /newsletter/subscribe` (public) body `{email}` → 202, no body.
  Idempotent and always the same response whether or not that email was
  already subscribed (no enumeration leak — same reasoning as
  `forgot-password`).
- `POST /contact` (public) body `{name, email, subject, message}` → 201,
  no body needed beyond success.
- `GET /admin/contact-messages` (admin/super_admin only) → `Page[ContactMessageOut]`,
  newest first — submitted messages aren't a black hole; an admin can
  actually read them. No admin view needed for newsletter subscribers in
  this scope (nothing actionable to do with one row at a time yet).

### Migration
One new revision: `wishlist_items`, `newsletter_subscribers`,
`contact_messages` tables. No changes to existing tables.

### Frontend-only additions
- **Routing change**: `/` becomes a new marketing homepage; product
  browsing (the existing `ProductList.tsx`) moves to `/products`. Update
  `Nav.tsx`'s "Products" link accordingly, add a "Home" link.
- **Homepage** (`Home.tsx`): hero banner (auto-rotating slider, manual
  prev/next + dot navigation, pause-on-hover, lazy-loaded images — a
  small static array of slides is fine, no CMS/backend needed; prefer
  real category/product images over generic stock-photo placeholders
  where one is available), a category showcase grid (real categories via
  `listCategories()`, using each category's `image_url` when set), a
  "New Arrivals" product rail (real data — `listProducts({sort: "newest"})`,
  which is just today's default order), a brand showcase grid (real
  brands via `listBrands()`). No fabricated "Flash Sale"/"Best Sellers"/
  "Trending" sections, since there's no real signal (order counts,
  ratings) to back them.
- **Footer** (new shared component, rendered once in `App.tsx`'s layout
  alongside `Nav`): links to every static page below, a newsletter
  signup form (calls `POST /newsletter/subscribe`, client + server
  validated), and plain-text/simple-icon payment method indicators
  reflecting what this store actually accepts (Cash on Delivery, Card
  (test mode)) — not fake real-card-network logos implying acceptance of
  payment methods that don't exist here.
- **Product listing page** (`ProductList.tsx`, now at `/products`): add a
  price-range filter (min/max number inputs), an in-stock-only checkbox,
  a sort `<select>` (mirroring the 5 options above), and a breadcrumb
  trail (Home / Products / [Category name if filtered]).
- **Wishlist**: new `WishlistContext` (mirrors `CartContext`'s exact
  shape/pattern — fetch on auth change, enrich with product data, expose
  `isWishlisted(productId)`/`toggleWishlist(productId)`), a heart-toggle
  button added to product cards (`ProductList.tsx`) and `ProductDetail.tsx`,
  and a new `/wishlist` page (behind `ProtectedRoute`) listing saved
  products with a remove action and an add-to-cart shortcut. Nav gets a
  wishlist link/icon for authenticated users.
- **Static pages** (new, under `src/pages/`): `About.tsx`, `Contact.tsx`
  (real form posting to `POST /contact`), `PrivacyPolicy.tsx`,
  `TermsAndConditions.tsx`, `ShippingPolicy.tsx`, `ReturnPolicy.tsx`,
  `RefundPolicy.tsx`, `CookiePolicy.tsx`, `FAQ.tsx` (accordion-style Help
  Center covering order/shipping/payment/returns questions), `NotFound.tsx`
  (wired as the router's catch-all `*` route), `MaintenancePage.tsx`
  (exists and is routable, but nothing automatically redirects to it —
  there's no real health-check/feature-flag infra to drive that, and
  faking one would be exactly the "placeholder interface" this pass is
  supposed to avoid). Write real, specific content grounded in what this
  store actually does (COD + simulated test-card payment only, no real
  carrier integration, GST handling per the existing tax engine, etc.) —
  not generic lorem-ipsum-style boilerplate, and don't claim policies
  (e.g. specific return windows, specific carriers) this app has no
  mechanism to actually honor; keep concrete specifics (company legal
  name, registered address, support phone number) as clearly-marked
  placeholders since those are real business details, not something to
  invent.

## Ownership boundary reminder
Only edit files under your module's directory. If you need a change to a
shared file (`app/shared/*`, `app/core/*`, `docs/CONTRACTS.md`,
`app/main.py` router registration), stop and flag it instead of editing
it — the Main Coordinator integrates router wiring.
