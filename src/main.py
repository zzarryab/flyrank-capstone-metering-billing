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


class GenerateRequest(BaseModel):
    tenant_id: str
    usage_type: str  # 'api_call' or 'ai_tokens'
    quantity: int
    idempotency_key: str
    metadata: Optional[dict] = None


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