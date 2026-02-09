from unittest.mock import patch

import pytest
from payouts.models import PayoutRequest
from rest_framework import status


@pytest.mark.django_db
class TestPayoutCreate:
    def test_create_payout_success(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        with patch("payouts.views.process_payout_request") as mock_task:
            response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["amount"] == "100.50"
        assert data["currency"] == "USD"
        assert data["recipient_details"] == valid_payout_payload["recipient_details"]
        assert data["status"] == PayoutRequest.Status.PENDING
        assert "created_at" in data
        assert "updated_at" in data
        assert data["description"] == "Test payout"
        assert PayoutRequest.objects.filter(pk=data["id"]).exists()
        mock_task.delay.assert_called_once_with(data["id"])

    def test_celery_task_called_on_create(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        with patch("payouts.views.process_payout_request") as mock_task:
            response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        payout_id = response.json()["id"]
        mock_task.delay.assert_called_once_with(payout_id)


@pytest.mark.django_db
class TestPayoutValidation:
    def test_create_invalid_amount_zero(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        valid_payout_payload["amount"] = "0"
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "amount" in response.json()

    def test_create_invalid_amount_negative(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        valid_payout_payload["amount"] = "-10"
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_invalid_currency_short(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        valid_payout_payload["currency"] = "US"
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "currency" in response.json()

    def test_create_invalid_currency_not_allowed(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        valid_payout_payload["currency"] = "XXX"
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_missing_recipient_details(self, api_client, valid_payout_payload):  # type: ignore[no-untyped-def]
        valid_payout_payload["recipient_details"] = {}
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPayoutListAndRetrieve:
    def test_list_payouts_empty(self, api_client):  # type: ignore[no-untyped-def]
        response = api_client.get("/api/payouts/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == []

    def test_list_payouts_with_filter(self, api_client, created_payout_id):  # type: ignore[no-untyped-def]
        response = api_client.get("/api/payouts/?status=PENDING")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) >= 1

    def test_list_invalid_status_returns_400(self, api_client):  # type: ignore[no-untyped-def]
        response = api_client.get("/api/payouts/?status=INVALID")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in response.json()

    def test_retrieve_payout(self, api_client, created_payout_id):  # type: ignore[no-untyped-def]
        response = api_client.get(f"/api/payouts/{created_payout_id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == created_payout_id

    def test_retrieve_404(self, api_client):  # type: ignore[no-untyped-def]
        response = api_client.get("/api/payouts/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPayoutUpdateAndDelete:
    def test_patch_status(self, api_client, created_payout_id):  # type: ignore[no-untyped-def]
        response = api_client.patch(
            f"/api/payouts/{created_payout_id}/",
            {"status": PayoutRequest.Status.CANCELLED},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == PayoutRequest.Status.CANCELLED

    def test_patch_status_completed_rejected(self, api_client, created_payout_id):  # type: ignore[no-untyped-def]
        response = api_client.patch(
            f"/api/payouts/{created_payout_id}/",
            {"status": PayoutRequest.Status.COMPLETED},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in response.json()

    def test_delete_payout(self, api_client, created_payout_id):  # type: ignore[no-untyped-def]
        response = api_client.delete(f"/api/payouts/{created_payout_id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not PayoutRequest.objects.filter(pk=created_payout_id).exists()
