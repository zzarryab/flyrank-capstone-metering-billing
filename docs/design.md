# Design — Usage Metering & Billing Engine

## Problem
SaaS products need to know: how much has a customer used, what does it cost,
and have they hit their plan's limit? This service answers all three, safely
under retries and concurrent requests.

## Data model

### tenants
| column | type | notes |
|---|---|---|
| id | uuid | primary key |
| name | text | |
| plan | text | 'free' or 'pro' |
| stripe_customer_id | text | nullable, set after first checkout |
| stripe_subscription_id | text | nullable |
| subscription_status | text | 'active', 'canceled', etc. |
| created_at | timestamptz | |

### usage_events
| column | type | notes |
|---|---|---|
| id | uuid | primary key |
| tenant_id | uuid | foreign key → tenants |
| usage_type | text | 'api_call' or 'ai_tokens' |
| quantity | integer | count or token count |
| idempotency_key | text | unique per tenant+key |
| metadata | jsonb | e.g. token breakdown |
| created_at | timestamptz | |

Unique constraint: (tenant_id, idempotency_key) — this is how retries are
deduplicated.

### plans (config, not a DB table — pinned in code)
| plan | api_calls/mo | ai_tokens/mo | price |
|---|---|---|---|
| free | 1,000 | 100,000 | $0 |
| pro | 50,000 | 5,000,000 | $29/mo |

### processed_webhook_events
| column | type | notes |
|---|---|---|
| stripe_event_id | text | primary key — dedupes Stripe webhook replays |
| processed_at | timestamptz | |

## API contract

- `POST /generate` — the dummy billable endpoint. Body: `{tenant_id, usage_type, quantity, idempotency_key}`.
  Records usage (idempotently), checks quota, returns 200/429/402.
- `GET /usage/{tenant_id}` — rollup: used, limit, cost, for the current month.
- `POST /checkout` — creates a Stripe Checkout session for upgrading to Pro.
- `POST /webhooks/stripe` — Stripe webhook receiver.

## Idempotency strategy

Every billable request carries a client-supplied `idempotency_key`. Before
inserting a usage_event, we check for an existing row with the same
`(tenant_id, idempotency_key)`. If found, we return the original result
instead of creating a new event — enforced by a unique DB constraint, not
just an application-level check (so it's safe even under concurrent retries).

## Non-goal

This capstone does not implement invoicing, proration, or overage billing.
Those are documented as stretch goals, not core.