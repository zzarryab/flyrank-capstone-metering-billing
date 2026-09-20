from src.plans import PLANS
from src.services.metering import get_monthly_usage


def check_quota(tenant_id: str, plan: str, usage_type: str, requested_quantity: int):
    """
    Returns (allowed: bool, status_code: int, message: str).
    Checked BEFORE recording usage.
    """
    plan_config = PLANS.get(plan)
    if not plan_config:
        return False, 402, f"Unknown plan '{plan}' — payment required to select a valid plan"

    limit_key = "api_calls_limit" if usage_type == "api_call" else "ai_tokens_limit"
    limit = plan_config[limit_key]

    current_usage = get_monthly_usage(tenant_id, usage_type)

    if current_usage + requested_quantity > limit:
        return False, 429, (
            f"Usage quota exceeded: {current_usage}/{limit} {usage_type} used this month. "
            f"This request would exceed your '{plan}' plan limit."
        )

    return True, 200, "OK"