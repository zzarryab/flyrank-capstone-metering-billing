# Usage Metering & Billing Engine

A backend service that meters usage, enforces plan quotas, calculates costs
(including AI token pricing rules), and syncs subscription status with Stripe
— built as a FlyRank Internship capstone.

## Architecture

Client → POST /generate (idempotency_key)
→ MeterService.record() — dedupe via unique (tenant_id, idempotency_key)
→ QuotaService.check() — 429 if over limit
→ usage_events table

GET /usage/:id → rollup(usage_events) → { used, limit, cost }

POST /checkout → Stripe Checkout session (test mode)
Stripe → signed webhook → /webhooks/stripe
→ verify signature (forged → 400)
→ dedupe by stripe_event_id
→ update tenant plan/status


## How to run

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env   # then fill in your Stripe test keys
uvicorn src.main:app --reload --port 8000
```

In a separate terminal, forward Stripe webhooks:
```powershell
stripe listen --forward-to localhost:8000/webhooks/stripe --all-snapshot
```

## Plans

| Plan | API calls/mo | AI tokens/mo | Price |
|---|---|---|---|
| Free | 1,000 | 100,000 | $0 |
| Pro | 50,000 | 5,000,000 | $29/mo |

## Concepts implemented (5 required)

| # | Concept | Where it lives |
|---|---|---|
| 1 | API endpoints | `src/main.py` — /generate, /usage, /checkout, /webhooks/stripe |
| 2 | Database | PostgreSQL via Docker — `src/db.py`, tenants/usage_events tables |
| 3 | Idempotency | `src/services/metering.py` — unique constraint + app-level check |
| 4 | Cost calculation / money math | `src/services/cost.py` — token pricing rules, integer cents |
| 5 | Webhook receiver (swap) | `/webhooks/stripe` — signed, verified, deduplicated |

## Limitations

- API call overage billing is not implemented (documented stretch goal, out of core scope).
- Token category tracking (input/cached/output/reasoning) is simplified in the /usage rollup — the pricing logic itself is fully correct and tested (see tests/test_cost.py), but per-event category breakdown would need richer metadata capture, which is a natural next step.
- No proration for mid-cycle plan changes.