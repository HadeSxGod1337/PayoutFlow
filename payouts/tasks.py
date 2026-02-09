import logging
import time
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from celery import current_task, shared_task  # type: ignore[import-untyped]
from payouts.models import PayoutRequest
from payouts.utils import log_payout_status_change

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# Minutes after which a payout in PROCESSING is considered stuck (configurable via settings).
PROCESSING_STUCK_MINUTES = getattr(
    settings,
    "PAYOUT_PROCESSING_STUCK_MINUTES",
    15,
)


@shared_task(  # type: ignore[untyped-decorator]
    autoretry_for=(OperationalError, ConnectionError, OSError),
    retry_backoff=True,
    max_retries=MAX_RETRIES,
)
def process_payout_request(payout_id: str) -> None:
    try:
        uid = UUID(payout_id)
    except ValueError:
        logger.exception("Invalid payout_id: %s", payout_id)
        return
    payout = None
    try:
        with transaction.atomic():
            payout = (
                PayoutRequest.objects.select_for_update(skip_locked=True)
                .filter(pk=uid, status=PayoutRequest.Status.PENDING)
                .first()
            )
            if payout is not None:
                log_payout_status_change(payout.id, payout.status, PayoutRequest.Status.PROCESSING)
                payout.status = PayoutRequest.Status.PROCESSING
                payout.save(update_fields=["status", "updated_at"])
        if payout is None:
            existing = PayoutRequest.objects.filter(pk=uid).first()
            if existing is None:
                logger.warning("PayoutRequest %s not found", payout_id)
            else:
                logger.info(
                    "PayoutRequest %s has status %s, skipping (locked or not PENDING)",
                    payout_id,
                    existing.status,
                )
            return
        logger.info("Processing payout %s amount=%s %s", payout_id, payout.amount, payout.currency)
        time.sleep(1)
        with transaction.atomic():
            payout = (
                PayoutRequest.objects.select_for_update()
                .filter(pk=uid, status=PayoutRequest.Status.PROCESSING)
                .first()
            )
            if payout is None:
                logger.info(
                    "PayoutRequest %s no longer PROCESSING (e.g. cancelled), not setting COMPLETED",
                    payout_id,
                )
                return
            log_payout_status_change(payout.id, payout.status, PayoutRequest.Status.COMPLETED)
            payout.status = PayoutRequest.Status.COMPLETED
            payout.save(update_fields=["status", "updated_at"])
        logger.info("Completed payout %s", payout_id)
    except Exception as exc:
        logger.exception("Failed to process payout %s: %s", payout_id, exc)
        task = current_task()
        current_retry = getattr(task.request, "retries", 0) if task else 0
        if current_retry >= MAX_RETRIES and payout is not None:
            with transaction.atomic():
                payout.refresh_from_db()
                if payout.status in (
                    PayoutRequest.Status.PENDING,
                    PayoutRequest.Status.PROCESSING,
                ):
                    old_status = payout.status
                    log_payout_status_change(payout.id, old_status, PayoutRequest.Status.FAILED)
                    payout.status = PayoutRequest.Status.FAILED
                    payout.save(update_fields=["status", "updated_at"])
                    logger.info("Marked payout %s as FAILED after max retries", payout_id)
        raise


@shared_task  # type: ignore[untyped-decorator]
def recover_stuck_processing_payouts() -> int:
    """
    Find payouts stuck in PROCESSING longer than PAYOUT_PROCESSING_STUCK_MINUTES
    and mark them as FAILED. Returns the number of payouts updated.
    """
    threshold = timezone.now() - timedelta(minutes=PROCESSING_STUCK_MINUTES)
    stuck = PayoutRequest.objects.filter(
        status=PayoutRequest.Status.PROCESSING,
        updated_at__lt=threshold,
    )
    count = stuck.count()
    if count:
        for payout in stuck:
            log_payout_status_change(payout.id, payout.status, PayoutRequest.Status.FAILED)
        updated = stuck.update(
            status=PayoutRequest.Status.FAILED,
            updated_at=timezone.now(),
        )
        logger.warning(
            "Marked %s payout(s) stuck in PROCESSING (older than %s min) as FAILED",
            updated,
            PROCESSING_STUCK_MINUTES,
        )
        return updated
    return 0
