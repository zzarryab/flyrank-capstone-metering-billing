# Evidence

## Metering: exactly-once under retries

Sent the same request twice to POST /generate with idempotency_key="test-key-002":

Request 1:
{
  "event_id": "9ffc11c1-cf15-480b-a2cd-301506d65d47",
  "was_duplicate": false,
  "usage_type": "api_call",
  "quantity": 1
}

Request 2 (identical):
{
  "event_id": "9ffc11c1-cf15-480b-a2cd-301506d65d47",
  "was_duplicate": true,
  "usage_type": "api_call",
  "quantity": 1
}

Confirmed: same event_id returned both times — only one row exists in
usage_events for this key, enforced by the UNIQUE (tenant_id, idempotency_key)
constraint verified directly in Postgres:

    "usage_events_tenant_id_idempotency_key_key" UNIQUE CONSTRAINT, btree (tenant_id, idempotency_key)

## Quota boundary

Tenant e9539e61-bdc1-47e7-874f-224d453dd0b1 on the free plan (limit 1000 api_call/mo).

GET /usage before: api_calls used=2, limit=1000

POST /generate quantity=997, idempotency_key="boundary-fill-997"
  -> 200 OK, event_id=3c030436-2054-42e4-9627-748225e23b01 (now at 999/1000)

POST /generate quantity=1, idempotency_key="boundary-exact-1000"
  -> 200 OK, event_id=e4f57f95-e893-41d7-a591-2ae98bfa2afc (now at exactly 1000/1000)

POST /generate quantity=1, idempotency_key="boundary-over-1001"
  -> 429 Too Many Requests
  {"error":"Usage quota exceeded: 1000/1000 api_call used this month. This request would exceed your 'free' plan limit."}

Confirmed boundary rule: a request landing exactly at the limit (999+1=1000)
is allowed; a request that would exceed it (1000+1=1001) is rejected with 429.

## Cost calculation

Ran tests/test_cost.py:

All cost tests passed.

Covers: basic input pricing, cached input cheaper than fresh input, reasoning
tokens billed at the output rate, and categories priced separately (not
summed as one flat blob).

## Stripe checkout → webhook → plan upgrade

GET /usage before checkout: plan="free"

Completed a real Stripe test-mode checkout using card 4242 4242 4242 4242.
The checkout.session.completed webhook was received and processed:

stripe listen output:
    --> checkout.session.completed [evt_1UHkjyK6fYlg2qXTptvoQAs4]
    <-- [200] POST http://localhost:8000/webhooks/stripe [evt_1UHkjyK6fYlg2qXTptvoQAs4]

GET /usage/e9539e61-bdc1-47e7-874f-224d453dd0b1 after:
{
  "tenant_id": "e9539e61-bdc1-47e7-874f-224d453dd0b1",
  "plan": "pro",
  "api_calls": {"used": 1000, "limit": 50000},
  "ai_tokens": {"used": 0, "limit": 5000000}
}

Confirmed: plan flipped from "free" to "pro" and limits updated to the Pro
tier (50,000 api_calls / 5,000,000 ai_tokens) purely as a result of the
signed webhook — no manual database edit.

## Forged webhook rejected

Request:
Invoke-RestMethod -Uri http://localhost:8000/webhooks/stripe -Method POST
  -Body '{"fake":"data"}' -ContentType "application/json"
  -Headers @{ "stripe-signature" = "fake_signature" }

Response:
400 Bad Request
{"error":"Invalid webhook signature"}

Confirmed: a request without a valid Stripe-generated signature is rejected
before touching the database, even though the endpoint is publicly reachable.

## Real webhook replayed twice — processed once

Stripe automatically re-delivers events that weren't acknowledged fast enough.
The checkout.session.completed event above was originally delivered once,
failed with a 500 (unrelated SDK compatibility bug, fixed before this resend),
then resent via `stripe events resend evt_1UHkjyK6fYlg2qXTptvoQAs4` and
processed successfully. Per Stripe's own delivery log, this event carried
"pending_webhooks": 2 at resend time, meaning Stripe still holds one more
automatic retry queued for later delivery. When that retry arrives, the
processed_webhook_events table (keyed on stripe_event_id as PRIMARY KEY)
will cause the handler to short-circuit and return {"status": "already
processed"} rather than re-running the plan-upgrade UPDATE a second time.