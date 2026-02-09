from unittest.mock import patch

import pytest
from payouts.models import PayoutRequest
from payouts.tasks import process_payout_request


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
