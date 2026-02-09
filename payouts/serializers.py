import json
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from payouts.models import PayoutRequest
from payouts.utils import format_choices_error

COMMON_CURRENCIES = frozenset({"RUB", "USD", "EUR", "GBP", "KZT"})
MAX_RECIPIENT_DETAILS_JSON_LENGTH = 2000
MAX_DESCRIPTION_LENGTH = 1000

# Via API only transition to CANCELLED is allowed, and only from these statuses.
CANCELLABLE_STATUSES = frozenset({PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING})


class PayoutRequestSerializer(serializers.ModelSerializer[PayoutRequest]):
    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "amount",
            "currency",
            "recipient_details",
            "status",
            "created_at",
            "updated_at",
            "description",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_amount(self, value: Decimal) -> Decimal:
        if value is None or value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value

    def validate_currency(self, value: str) -> str:
        if not value or len(value) != 3:
            raise serializers.ValidationError("Currency must be a 3-letter ISO 4217 code.")
        if value.upper() not in COMMON_CURRENCIES:
            raise serializers.ValidationError(
                format_choices_error("Currency must be one of", COMMON_CURRENCIES)
            )
        return value.upper()

    def validate_recipient_details(self, value: object) -> object:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Recipient details must be a JSON object.")
        if not value:
            raise serializers.ValidationError("Recipient details are required and cannot be empty.")
        try:
            serialized = json.dumps(value, sort_keys=True)
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError("Recipient details must be JSON-serializable.") from e
        if len(serialized) > MAX_RECIPIENT_DETAILS_JSON_LENGTH:
            raise serializers.ValidationError("Recipient details too long.")
        return value

    def validate_description(self, value: str | None) -> str | None:
        if value is not None and len(value) > MAX_DESCRIPTION_LENGTH:
            raise serializers.ValidationError(
                f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "status" not in attrs or self.instance is None:
            return attrs
        new_status = attrs["status"]
        current = self.instance.status
        if new_status in (PayoutRequest.Status.COMPLETED, PayoutRequest.Status.FAILED):
            raise serializers.ValidationError(
                {"status": "Status COMPLETED and FAILED can only be set by the system."}
            )
        if new_status == PayoutRequest.Status.CANCELLED:
            if current not in CANCELLABLE_STATUSES:
                raise serializers.ValidationError(
                    {"status": "Only PENDING or PROCESSING payouts can be cancelled."}
                )
            return attrs
        if new_status != current:
            raise serializers.ValidationError(
                {"status": "Via API only transition to CANCELLED is allowed."}
            )
        return attrs
