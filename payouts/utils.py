import hashlib
import json
from uuid import UUID

from payouts.models import PayoutAuditLog


def format_choices_error(prefix: str, allowed: set[str] | frozenset[str]) -> str:
    return f"{prefix}: {', '.join(sorted(allowed))}."


def hash_request_body(data: object) -> str:
    """Canonical hash of request body for idempotency replay detection."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def log_payout_status_change(payout_id: UUID | str, old_status: str, new_status: str) -> None:
    PayoutAuditLog.objects.create(
        payout_id=payout_id,
        action="status_change",
        old_value=old_status,
        new_value=new_status,
    )


def log_payout_delete(payout_id: UUID | str, status: str) -> None:
    PayoutAuditLog.objects.create(
        payout_id=payout_id,
        action="delete",
        old_value=status,
        new_value="",
    )
