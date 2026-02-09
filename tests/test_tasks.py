from unittest.mock import patch

import pytest
from django.utils import timezone
from payouts.models import PayoutRequest
from payouts.tasks import process_payout_request, recover_stuck_processing_payouts


@pytest.mark.django_db
class TestRecoverStuckProcessingPayouts:
    def test_marks_stuck_processing_as_failed(self, payout_instance):  # type: ignore[no-untyped-def]
        payout = payout_instance(status=PayoutRequest.Status.PROCESSING)
        old_updated = timezone.now() - timezone.timedelta(minutes=20)
        PayoutRequest.objects.filter(pk=payout.pk).update(updated_at=old_updated)
        payout.refresh_from_db()
        count = recover_stuck_processing_payouts()
        assert count == 1
        payout.refresh_from_db()
        assert payout.status == PayoutRequest.Status.FAILED

    def test_ignores_recent_processing(self, payout_instance):  # type: ignore[no-untyped-def]
        payout = payout_instance(status=PayoutRequest.Status.PROCESSING)
        count = recover_stuck_processing_payouts()
        assert count == 0
        payout.refresh_from_db()
        assert payout.status == PayoutRequest.Status.PROCESSING

    def test_returns_zero_when_none_stuck(self, payout_instance):  # type: ignore[no-untyped-def]
        payout_instance(status=PayoutRequest.Status.PENDING)
        assert recover_stuck_processing_payouts() == 0


@pytest.mark.django_db
class TestProcessPayoutTask:
    def test_task_processes_pending_payout(self, payout_instance):  # type: ignore[no-untyped-def]
        payout = payout_instance()
        with patch("payouts.tasks.time.sleep"):
            process_payout_request(str(payout.id))
        payout.refresh_from_db()
        assert payout.status == PayoutRequest.Status.COMPLETED

    def test_task_skips_non_pending(self, payout_instance):  # type: ignore[no-untyped-def]
        payout = payout_instance(status=PayoutRequest.Status.CANCELLED)
        with patch("payouts.tasks.time.sleep") as mock_sleep:
            process_payout_request(str(payout.id))
        mock_sleep.assert_not_called()
        payout.refresh_from_db()
        assert payout.status == PayoutRequest.Status.CANCELLED
