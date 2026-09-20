import os
import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from src.db import init_db, get_connection
from src.services.metering import record_usage, get_monthly_usage
from src.services.quota import check_quota
from src.plans import PLANS

app = FastAPI()
init_db()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "price_your_id_here")


class GenerateRequest(BaseModel):
    tenant_id: str
    usage_type: str  # 'api_call' or 'ai_tokens'
    quantity: int
    idempotency_key: str
    metadata: Optional[dict] = None


class CheckoutRequest(BaseModel):
    tenant_id: str


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def get_tenant(tenant_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    return row


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", status_code=200)
def generate(body: GenerateRequest):
    """The dummy billable endpoint: records usage, checks quota, returns cost."""
    if body.usage_type not in ("api_call", "ai_tokens"):
        raise HTTPException(status_code=400, detail="usage_type must be 'api_call' or 'ai_tokens'")
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    tenant = get_tenant(body.tenant_id)

    allowed, status_code, message = check_quota(
        body.tenant_id, tenant["plan"], body.usage_type, body.quantity
    )
    if not allowed:
        raise HTTPException(status_code=status_code, detail=message)

    event, was_duplicate = record_usage(
        body.tenant_id, body.usage_type, body.quantity, body.idempotency_key, body.metadata
    )

    return {
        "event_id": str(event["id"]),
        "was_duplicate": was_duplicate,
        "usage_type": event["usage_type"],
        "quantity": event["quantity"],
    }


@app.get("/usage/{tenant_id}")
def usage(tenant_id: str):
    tenant = get_tenant(tenant_id)
    plan_config = PLANS[tenant["plan"]]

    api_calls_used = get_monthly_usage(tenant_id, "api_call")
    tokens_used = get_monthly_usage(tenant_id, "ai_tokens")

    return {
        "tenant_id": tenant_id,
        "plan": tenant["plan"],
        "api_calls": {
            "used": api_calls_used,
            "limit": plan_config["api_calls_limit"],
        },
        "ai_tokens": {
            "used": tokens_used,
            "limit": plan_config["ai_tokens_limit"],
        },
    }


@app.post("/checkout")
def create_checkout(body: CheckoutRequest):
    tenant = get_tenant(body.tenant_id)

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRO_PRICE_ID, "quantity": 1}],
        success_url="http://localhost:8000/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:8000/cancel",
        client_reference_id=body.tenant_id,
        metadata={"tenant_id": body.tenant_id},
    )
    return {"checkout_url": session.url}


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Deduplicate: has this exact event already been processed?
    conn = get_connection()
    existing = conn.execute(
        "SELECT 1 FROM processed_webhook_events WHERE stripe_event_id = %s",
        (event["id"],),
    ).fetchone()
    if existing:
        conn.close()
        return {"status": "already processed"}

    event_type = event["type"]
    data = event["data"]["object"].to_dict()

    if event_type == "checkout.session.completed":
        tenant_id = data.get("client_reference_id") or data.get("metadata", {}).get("tenant_id")
        if tenant_id:
            conn.execute(
                "UPDATE tenants SET plan = 'pro', stripe_customer_id = %s, stripe_subscription_id = %s, subscription_status = 'active' WHERE id = %s",
                (data["customer"], data["subscription"], tenant_id),
            )

    elif event_type == "customer.subscription.updated":
        conn.execute(
            "UPDATE tenants SET subscription_status = %s WHERE stripe_subscription_id = %s",
            (data["status"], data["id"]),
        )

    elif event_type == "customer.subscription.deleted":
        conn.execute(
            "UPDATE tenants SET plan = 'free', subscription_status = 'canceled' WHERE stripe_subscription_id = %s",
            (data["id"],),
        )

    conn.execute(
        "INSERT INTO processed_webhook_events (stripe_event_id) VALUES (%s)",
        (event["id"],),
    )
    conn.commit()
    conn.close()

    return {"status": "processed"}