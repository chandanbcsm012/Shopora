"""Plain string-template HTML emails. No templating engine dependency —
inline CSS, f-strings, and a simple button-styled link are enough for two
templates (per docs/CONTRACTS.md)."""
from __future__ import annotations

from datetime import datetime

_BUTTON_STYLE = (
    "display:inline-block;padding:12px 24px;background-color:#2563eb;"
    "color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;"
)

_WRAPPER_STYLE = (
    "font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;"
    "padding:24px;color:#111827;"
)


def _format_expiry(expires_at: datetime) -> str:
    return expires_at.strftime("%Y-%m-%d %H:%M UTC")


def invitation_email(full_name: str, role: str, accept_url: str, expires_at: datetime) -> str:
    return f"""\
<html>
  <body style="{_WRAPPER_STYLE}">
    <h1 style="font-size:20px;">You've been invited to Shopora</h1>
    <p>Hi {full_name},</p>
    <p>
      You have been invited to join Shopora with the role
      <strong>{role}</strong>. Click the button below to set your password
      and activate your account.
    </p>
    <p style="margin:32px 0;">
      <a href="{accept_url}" style="{_BUTTON_STYLE}">Accept invitation</a>
    </p>
    <p>This invitation link expires on <strong>{_format_expiry(expires_at)}</strong>.</p>
    <p>If the button doesn't work, copy and paste this link into your browser:</p>
    <p style="word-break:break-all;"><a href="{accept_url}">{accept_url}</a></p>
  </body>
</html>
"""


def order_confirmation_email(full_name: str, order, shipping_address) -> str:
    """`order` is an `app.modules.orders.schemas.OrderOut` (has `.id`,
    `.items`, `.total_cents`, `.currency`, `.payment_status`), and
    `shipping_address` is an `app.modules.addresses.schemas.AddressOut | None`
    -- both plain Pydantic DTOs, not SQLAlchemy models, so this template has
    no cross-module model dependency."""
    item_rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e5e7eb;'>{item.product_name_snapshot}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:center;'>{item.quantity}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:right;'>"
        f"{order.currency} {item.unit_price_cents / 100:.2f}</td>"
        f"</tr>"
        for item in order.items
    )

    if shipping_address is not None:
        address_block = (
            f"{shipping_address.full_name}<br/>"
            f"{shipping_address.address_line1}<br/>"
            f"{(shipping_address.address_line2 + '<br/>') if shipping_address.address_line2 else ''}"
            f"{shipping_address.city}, {shipping_address.state} {shipping_address.postal_code}<br/>"
            f"{shipping_address.country}"
        )
    else:
        address_block = "N/A"

    return f"""\
<html>
  <body style="{_WRAPPER_STYLE}">
    <h1 style="font-size:20px;">Your order is confirmed</h1>
    <p>Hi {full_name},</p>
    <p>Thanks for your order! Here's a summary:</p>
    <p><strong>Order ID:</strong> {order.id}</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr>
          <th style="text-align:left;padding:6px 8px;border-bottom:2px solid #111827;">Item</th>
          <th style="text-align:center;padding:6px 8px;border-bottom:2px solid #111827;">Qty</th>
          <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #111827;">Price</th>
        </tr>
      </thead>
      <tbody>
        {item_rows}
      </tbody>
    </table>
    <p><strong>Order total:</strong> {order.currency} {order.total_cents / 100:.2f}</p>
    <p><strong>Payment status:</strong> {order.payment_status or "N/A"}</p>
    <p><strong>Shipping to:</strong><br/>{address_block}</p>
    <p>You can download your invoice and track this order any time from "My Orders".</p>
  </body>
</html>
"""


def password_reset_email(full_name: str, reset_url: str, expires_at: datetime) -> str:
    return f"""\
<html>
  <body style="{_WRAPPER_STYLE}">
    <h1 style="font-size:20px;">Reset your password</h1>
    <p>Hi {full_name},</p>
    <p>
      We received a request to reset your Shopora password. Click
      the button below to choose a new password.
    </p>
    <p style="margin:32px 0;">
      <a href="{reset_url}" style="{_BUTTON_STYLE}">Reset password</a>
    </p>
    <p>This link expires on <strong>{_format_expiry(expires_at)}</strong>.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    <p>If the button doesn't work, copy and paste this link into your browser:</p>
    <p style="word-break:break-all;"><a href="{reset_url}">{reset_url}</a></p>
  </body>
</html>
"""
