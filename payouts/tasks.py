import logging
import time
from uuid import UUID

from django.db import transaction
from django.db.utils import OperationalError

from celery import current_task
from celery import shared_task  # type: ignore[import-untyped]
from payouts.models import PayoutRequest

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


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
    try:
        payout = PayoutRequest.objects.get(pk=uid)
    except PayoutRequest.DoesNotExist:
        logger.warning("PayoutRequest %s not found", payout_id)
        return
    if payout.status != PayoutRequest.Status.PENDING:
        logger.info("PayoutRequest %s has status %s, skipping", payout_id, payout.status)
        return
    try:
        with transaction.atomic():
            payout.status = PayoutRequest.Status.PROCESSING
            payout.save(update_fields=["status", "updated_at"])
        logger.info("Processing payout %s amount=%s %s", payout_id, payout.amount, payout.currency)
        time.sleep(1)
        with transaction.atomic():
            payout.status = PayoutRequest.Status.COMPLETED
            payout.save(update_fields=["status", "updated_at"])
        logger.info("Completed payout %s", payout_id)
    except Exception as exc:
        logger.exception("Failed to process payout %s: %s", payout_id, exc)
        task = current_task()
        current_retry = getattr(task.request, "retries", 0) if task else 0
        if current_retry >= MAX_RETRIES:
            with transaction.atomic():
                payout.refresh_from_db()
                if payout.status in (
                    PayoutRequest.Status.PENDING,
                    PayoutRequest.Status.PROCESSING,
                ):
                    payout.status = PayoutRequest.Status.FAILED
                    payout.save(update_fields=["status", "updated_at"])
                    logger.info("Marked payout %s as FAILED after max retries", payout_id)
        raise
