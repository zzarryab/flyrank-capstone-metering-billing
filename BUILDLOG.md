# Build Log — AI usage

- Used Claude to scaffold the FastAPI project structure and initial Postgres schema — reviewed and adjusted table names to match my design doc.
- Debugged a psycopg dict-to-jsonb adaptation error (`cannot adapt type 'dict'`) — learned that psycopg3 needs metadata wrapped in `Json()` before it can be inserted into a jsonb column.
- Debugged a Stripe SDK version mismatch in the webhook handler: `event["data"]["object"]` returns a typed Session object in the installed stripe version, not a plain dict, so `.get()` failed with an AttributeError. Fixed by calling `.to_dict()` before using dict-style access.
- Proved idempotency by sending identical `/generate` requests with the same idempotency_key twice — confirmed same event_id returned both times.
- Proved the quota boundary rule directly: a tenant at 999/1000 requesting 1 more succeeds (lands at exactly 1000); requesting 1 more after that returns 429.
- Completed a full Stripe test-mode checkout, verified the webhook flipped the tenant from Free to Pro, and confirmed a forged webhook (fake signature) is correctly rejected with 400.
- Wrote the token pricing tests myself after understanding the cached/reasoning token rules from the brief; used AI to double check my cent-based math.