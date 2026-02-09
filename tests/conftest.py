from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def valid_payout_payload() -> dict:
    return {
        "amount": "100.50",
        "currency": "USD",
        "recipient_details": {"account": "12345678", "bank": "Test Bank", "name": "Recipient"},
        "description": "Test payout",
    }


@pytest.fixture
def created_payout_id(api_client: APIClient, valid_payout_payload: dict) -> str:
    with patch("payouts.views.process_payout_request"):
        response = api_client.post("/api/payouts/", valid_payout_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


@pytest.fixture
def payout_instance(valid_payout_payload: dict):  # type: ignore[no-untyped-def]
    from payouts.models import PayoutRequest

    def _factory(status: str = PayoutRequest.Status.PENDING, **kwargs: object) -> PayoutRequest:
        params = {
            "amount": valid_payout_payload["amount"],
            "currency": valid_payout_payload["currency"],
            "recipient_details": valid_payout_payload["recipient_details"],
            "status": status,
            **kwargs,
        }
        return PayoutRequest.objects.create(**params)

    return _factory
